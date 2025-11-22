import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

# ---------------------------------------------------------
# Page configuration
# ---------------------------------------------------------
st.set_page_config(page_title="Snow drift & Wind Rose", layout="wide")
st.title("Snow Drift Calculation & Wind Rose")

st.markdown(
    """
This page implements the **Tabler (2003)** snow-drift model based on hourly
meteorological data from the **Open-Meteo ERA5 archive**.

- A **season** is defined as **1 July – 30 June** (next year)
- Snowfall counts when **temperature < +1 °C**
- You can choose a **year range** and a **fence type**
- Results are expressed as **Qt (kg/m)** and **tonnes/m**, with
  corresponding **fence height** per season.
    """
)

# ---------------------------------------------------------
# Require coordinate from the Map page
# ---------------------------------------------------------
coord = st.session_state.get("clicked_coord")

if coord is None:
    st.warning(
        "No coordinate has been selected yet. "
        "Please go to the **Map & Energy** page, choose a point and store it, "
        "then return to this page."
    )
    st.stop()

lat0, lon0 = coord

st.info(f"Using coordinate from map page: **lat = {lat0:.4f}, lon = {lon0:.4f}**")

# ---------------------------------------------------------
# Parameters (Tabler 2003, as in supplied script)
# ---------------------------------------------------------
DEFAULT_T = 3000       # Maximum transport distance [m]
DEFAULT_F = 30000      # Fetch distance [m]
DEFAULT_THETA = 0.5    # Relocation coefficient

# ---------------------------------------------------------
# Snow-drift core functions (adapted from Snow_drift.py)
# ---------------------------------------------------------

def compute_Qupot(hourly_wind_speeds, dt=3600):
    """
    Potential wind-driven snow transport (Qupot) [kg/m], using u^3.8.
    """
    total = sum((u ** 3.8) * dt for u in hourly_wind_speeds) / 233_847
    return total

def sector_index(direction):
    """Return 0–15 index for a 16-sector rose."""
    return int(((direction + 11.25) % 360) // 22.5)

def compute_sector_transport(hourly_wind_speeds, hourly_wind_dirs, dt=3600):
    """
    Cumulative transport for each of 16 wind sectors [kg/m].
    """
    sectors = [0.0] * 16
    for u, d in zip(hourly_wind_speeds, hourly_wind_dirs):
        idx = sector_index(d)
        sectors[idx] += ((u ** 3.8) * dt) / 233_847
    return sectors

def compute_snow_transport(T, F, theta, Swe, hourly_wind_speeds, dt=3600):
    """
    Snow drifting according to Tabler (2003).

    Returns dict with Qupot, Qspot, Srwe, Qinf, Qt and control type.
    """
    Qupot = compute_Qupot(hourly_wind_speeds, dt)
    Qspot = 0.5 * T * Swe       # Snowfall-limited [kg/m]
    Srwe = theta * Swe          # Relocated water equivalent [mm]

    if Qupot > Qspot:
        Qinf = 0.5 * T * Srwe
        control = "Snowfall controlled"
    else:
        Qinf = Qupot
        control = "Wind controlled"

    Qt = Qinf * (1 - 0.14 ** (F / T))

    return {
        "Qupot (kg/m)": Qupot,
        "Qspot (kg/m)": Qspot,
        "Srwe (mm)": Srwe,
        "Qinf (kg/m)": Qinf,
        "Qt (kg/m)": Qt,
        "Control": control,
    }

def compute_yearly_results(df, T, F, theta):
    """
    Compute seasonal snow drift parameters for each July–June season.

    df must have columns:
      - time (datetime index or column)
      - temperature_2m
      - precipitation
      - windspeed_10m
    """
    if "time" not in df.columns:
        df = df.reset_index().rename(columns={"index": "time"})

    df = df.copy()
    df["time"] = pd.to_datetime(df["time"])
    # season year: July–Dec → current year, Jan–Jun → previous year
    df["season"] = df["time"].apply(lambda dt: dt.year if dt.month >= 7 else dt.year - 1)

    seasons = sorted(df["season"].unique())
    results = []

    for s in seasons:
        season_start = pd.Timestamp(year=s, month=7, day=1)
        season_end = pd.Timestamp(year=s + 1, month=6, day=30, hour=23, minute=59)
        df_season = df[(df["time"] >= season_start) & (df["time"] <= season_end)]
        if df_season.empty:
            continue

        # hourly Swe: precipitation when T < +1°C
        df_season["Swe_hourly"] = np.where(
            df_season["temperature_2m"] < 1.0,
            df_season["precipitation"],
            0.0,
        )
        total_Swe = df_season["Swe_hourly"].sum()    # mm
        wind_speeds = df_season["windspeed_10m"].tolist()

        res = compute_snow_transport(T, F, theta, total_Swe, wind_speeds)
        res["season"] = f"{s}-{s + 1}"
        results.append(res)

    return pd.DataFrame(results)

def compute_average_sector(df):
    """
    Average directional breakdown over all seasons (16 sectors).
    df must have:
      - time
      - temperature_2m
      - precipitation
      - windspeed_10m
      - winddirection_10m
    """
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"])
    df["season"] = df["time"].apply(lambda dt: dt.year if dt.month >= 7 else dt.year - 1)

    sectors_list = []
    for s, group in df.groupby("season"):
        group = group.copy()
        group["Swe_hourly"] = np.where(
            group["temperature_2m"] < 1.0,
            group["precipitation"],
            0.0,
        )
        ws = group["windspeed_10m"].tolist()
        wdir = group["winddirection_10m"].tolist()
        sectors = compute_sector_transport(ws, wdir)
        sectors_list.append(sectors)

    if not sectors_list:
        return np.zeros(16)

    return np.mean(sectors_list, axis=0)

def compute_fence_height(Qt, fence_type):
    """
    Necessary effective fence height (m) for a given Qt (kg/m).
    """
    Qt_tonnes = Qt / 1000.0
    ft = fence_type.lower()
    if ft == "wyoming":
        factor = 8.5
    elif ft in ["slat-and-wire", "slat and wire"]:
        factor = 7.7
    elif ft == "solid":
        factor = 2.9
    else:
        raise ValueError("Unsupported fence type. Choose 'Wyoming', 'Slat-and-wire', or 'Solid'.")

    H = (Qt_tonnes / factor) ** (1 / 2.2)
    return H

# ---------------------------------------------------------
# Open-Meteo ERA5 loader
# ---------------------------------------------------------
ERA5_URL = "https://archive-api.open-meteo.com/v1/era5"

@st.cache_data(show_spinner=True)
def fetch_era5_hourly(lat, lon, start_date, end_date, tz="UTC"):
    """
    Fetch hourly ERA5 data for snow-drift variables.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(
            [
                "temperature_2m",
                "precipitation",
                "windspeed_10m",
                "winddirection_10m",
            ]
        ),
        "timezone": tz,
    }
    r = requests.get(ERA5_URL, params=params, timeout=60)
    r.raise_for_status()
    h = r.json().get("hourly", {})
    df = pd.DataFrame(h)
    df["time"] = pd.to_datetime(df["time"])
    # rename to simpler names used above
    return df[["time", "temperature_2m", "precipitation", "windspeed_10m", "winddirection_10m"]]

# ---------------------------------------------------------
# UI – controls
# ---------------------------------------------------------
left, right = st.columns([1.1, 1.9])

with left:
    st.subheader("Settings")

    # year range for seasons
    current_year = date.today().year
    start_year, end_year = st.select_slider(
        "Season range (July–June)",
        options=list(range(current_year - 10, current_year + 1)),
        value=(current_year - 4, current_year - 1),
        help="Example: selecting 2020–2023 gives seasons 2020–2021, …, 2023–2024.",
    )

    fence_type = st.selectbox(
        "Fence type",
        ["Wyoming", "Slat-and-wire", "Solid"],
        index=0,
        help="Used to estimate required fence height from Qt.",
    )

    T = st.number_input("Maximum transport distance T [m]", 500, 10000, DEFAULT_T, step=500)
    F = st.number_input("Fetch distance F [m]", 1000, 100000, DEFAULT_F, step=1000)
    theta = st.slider("Relocation coefficient θ", 0.1, 1.0, DEFAULT_THETA, step=0.05)

    run_btn = st.button("Compute snow drift", type="primary")

# ---------------------------------------------------------
# Main computation
# ---------------------------------------------------------
if not run_btn:
    with right:
        st.info("Choose a season range and parameters on the left, then click **Compute snow drift**.")
    st.stop()

# determine full date span needed (1 July start_year → 30 June end_year+1)
start_date_str = f"{start_year}-07-01"
end_date_str = f"{end_year + 1}-06-30"

with st.spinner("Fetching ERA5 data for the selected coordinate…"):
    try:
        met_df = fetch_era5_hourly(lat0, lon0, start_date_str, end_date_str)
    except Exception as e:
        st.error(f"Failed to fetch ERA5 data: {e}")
        st.stop()

if met_df.empty:
    st.error("No meteorological data returned for this period and location.")
    st.stop()

with st.spinner("Computing seasonal snow drift and wind rose…"):
    yearly_df = compute_yearly_results(met_df, T, F, theta)
    # filter to requested seasons
    mask = yearly_df["season"].apply(lambda s: int(s.split("-")[0]) >= start_year and int(s.split("-")[0]) <= end_year)
    yearly_df = yearly_df.loc[mask].reset_index(drop=True)

    avg_sectors = compute_average_sector(met_df)

if yearly_df.empty:
    st.warning("No seasons found in the selected range after processing.")
    st.stop()

# add convenience columns
yearly_df["Qt (tonnes/m)"] = yearly_df["Qt (kg/m)"] / 1000.0

# fence heights
heights = []
for _, row in yearly_df.iterrows():
    Qt_val = row["Qt (kg/m)"]
    H = compute_fence_height(Qt_val, fence_type)
    heights.append(H)
yearly_df[f"{fence_type} fence height (m)"] = heights

overall_avg = yearly_df["Qt (kg/m)"].mean()
overall_avg_tonnes = overall_avg / 1000.0

# ---------------------------------------------------------
# Right column – plots and tables
# ---------------------------------------------------------
with right:
    st.subheader("Seasonal snow drift (Qt)")

    st.markdown(
        f"Overall average Qt over selected seasons: **{overall_avg_tonnes:.1f} tonnes/m**"
    )

    # bar chart of Qt per season
    fig_bar = px.bar(
        yearly_df,
        x="season",
        y="Qt (tonnes/m)",
        labels={"season": "Season (July–June)", "Qt (tonnes/m)": "Qt [tonnes/m]"},
        title="Mean annual snow transport per season",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # table
    st.markdown("**Table of seasons and fence heights**")
    display_cols = ["season", "Qt (tonnes/m)", "Control", f"{fence_type} fence height (m)"]
    st.dataframe(
        yearly_df[display_cols].style.format(
            {"Qt (tonnes/m)": "{:.1f}", f"{fence_type} fence height (m)": "{:.2f}"}
        ),
        use_container_width=True,
    )

    # wind rose (Plotly)
    st.subheader("Average directional distribution (wind rose)")

    num_sectors = 16
    directions = [
        "N", "NNE", "NE", "ENE",
        "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW",
        "W", "WNW", "NW", "NNW",
    ]
    angles_deg = np.arange(0, 360, 360 / num_sectors)

    avg_sectors_tonnes = avg_sectors / 1000.0  # kg/m → tonnes/m

    fig_rose = go.Figure()
    fig_rose.add_trace(
        go.Barpolar(
            r=avg_sectors_tonnes,
            theta=angles_deg,
            text=directions,
            hovertemplate="Direction: %{text}<br>Qt: %{r:.2f} tonnes/m<extra></extra>",
        )
    )
    fig_rose.update_layout(
        polar=dict(
            angularaxis=dict(
                tickmode="array",
                tickvals=angles_deg,
                ticktext=directions,
                direction="clockwise",
                rotation=90,  # 0° at north
            )
        ),
        title=f"Average snow transport by direction<br>Overall Qt: {overall_avg_tonnes:.1f} tonnes/m",
        showlegend=False,
    )
    st.plotly_chart(fig_rose, use_container_width=True)
