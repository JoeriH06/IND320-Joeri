import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
from sidebar import navigation

# ---------------------------------------------------------
# Page config
# ---------------------------------------------------------
st.set_page_config(page_title="Snow Drift & Wind Rose", layout="wide")
st.title("❄️Snow Drift & Wind Rose (Tabler 2003)")

navigation()

st.markdown("""
This tool computes **snow-drift transport (Qt)** using hourly ERA5 weather data  
and the **Tabler (2003)** formula.

### Features
- ✔ July → June seasonal analysis  
- ✔ Qt per season and month  
- ✔ Required **fence height**  
- ✔ **Wind rose** of snow-transport directions  
- ✔ Coordinates selectable *on this page or from the Map page*
""")

# ---------------------------------------------------------
# Constants
# ---------------------------------------------------------
DEFAULT_T = 3000
DEFAULT_F = 30000
DEFAULT_THETA = 0.5

# ---------------------------------------------------------
# Snow Drift Functions
# ---------------------------------------------------------
def compute_Qupot(hourly_wind_speeds, dt=3600):
    return sum((u ** 3.8) * dt for u in hourly_wind_speeds) / 233_847

def sector_index(direction):
    return int(((direction + 11.25) % 360) // 22.5)

def compute_sector_transport(hourly_wind_speeds, hourly_wind_dirs, dt=3600):
    sectors = [0.0] * 16
    for u, d in zip(hourly_wind_speeds, hourly_wind_dirs):
        sectors[sector_index(d)] += ((u ** 3.8) * dt) / 233_847
    return sectors

def compute_snow_transport(T, F, theta, Swe, hourly_wind_speeds):
    Qupot = compute_Qupot(hourly_wind_speeds)
    Qspot = 0.5 * T * Swe
    Srwe = theta * Swe
    Qinf = (0.5 * T * Srwe) if Qupot > Qspot else Qupot
    Qt = Qinf * (1 - 0.14 ** (F / T))
    return {
        "Qupot (kg/m)": Qupot,
        "Qspot (kg/m)": Qspot,
        "Srwe (mm)": Srwe,
        "Qinf (kg/m)": Qinf,
        "Qt (kg/m)": Qt,
        "Control": "Snowfall controlled" if Qupot > Qspot else "Wind controlled",
    }

def compute_fence_height(Qt, fence_type):
    Qt_t = Qt / 1000
    factors = {"wyoming": 8.5, "slat-and-wire": 7.7, "solid": 2.9}
    f = factors.get(fence_type.lower(), 8.5)
    return (Qt_t / f) ** (1 / 2.2)

def compute_year_and_month_results(df, T, F, theta):
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"])
    df["season_year"] = df["time"].apply(lambda dt: dt.year if dt.month >= 7 else dt.year - 1)
    df["month"] = df["time"].dt.month

    yearly, monthly = [], []

    for s, g in df.groupby("season_year"):
        g = g.copy()
        g["Swe_hourly"] = np.where(g["temperature_2m"] < 1.0, g["precipitation"], 0)
        Swe = g["Swe_hourly"].sum()
        ws = g["windspeed_10m"].tolist()

        yr = compute_snow_transport(T, F, theta, Swe, ws)
        yr["season"] = f"{s}-{s+1}"
        yearly.append(yr)

        for m, gm in g.groupby("month"):
            gm = gm.copy()
            Swe_m = gm["Swe_hourly"].sum()
            ws_m = gm["windspeed_10m"].tolist()
            if Swe_m == 0 or len(ws_m) == 0:
                continue
            mm = compute_snow_transport(T, F, theta, Swe_m, ws_m)
            mm["season"] = f"{s}-{s+1}"
            mm["month"] = m
            monthly.append(mm)

    return pd.DataFrame(yearly), pd.DataFrame(monthly)

def compute_average_sector(df):
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"])
    df["season_year"] = df["time"].apply(lambda dt: dt.year if dt.month >= 7 else dt.year - 1)

    all_sectors = []
    for _, g in df.groupby("season_year"):
        g["Swe_hourly"] = np.where(g["temperature_2m"] < 1.0, g["precipitation"], 0)
        ws = g["windspeed_10m"].tolist()
        wd = g["winddirection_10m"].tolist()
        all_sectors.append(compute_sector_transport(ws, wd))

    return np.mean(all_sectors, axis=0) if all_sectors else np.zeros(16)

# ---------------------------------------------------------
# ERA5 loader
# ---------------------------------------------------------
@st.cache_data(show_spinner=True)
def fetch_era5_hourly(lat, lon, start_date, end_date):
    r = requests.get(
        "https://archive-api.open-meteo.com/v1/era5",
        params={
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": "temperature_2m,precipitation,windspeed_10m,winddirection_10m",
            "timezone": "UTC",
        },
        timeout=60
    )
    r.raise_for_status()
    df = pd.DataFrame(r.json()["hourly"])
    df["time"] = pd.to_datetime(df["time"])
    return df

# ---------------------------------------------------------
# TOP CONFIGURATION PANEL
# ---------------------------------------------------------
st.subheader("⚙️ Configuration")

cfg = st.container()

with cfg:

    # Row 1 – coordinates
    st.markdown("### Coordinates")

    saved_coord = st.session_state.get("clicked_coord")

    if saved_coord:
        st.success(f"Loaded coord from map: **({saved_coord[0]:.4f}, {saved_coord[1]:.4f})**")
        default_lat, default_lon = saved_coord
    else:
        st.info("No stored coordinate found. Using default (65.0, 12.0).")
        default_lat, default_lon = 65.0, 12.0

    colA, colB = st.columns(2)
    with colA:
        lat = st.number_input("Latitude", -90.0, 90.0, float(default_lat))
    with colB:
        lon = st.number_input("Longitude", -180.0, 180.0, float(default_lon))

    if st.button("📍 Update coordinate"):
        st.session_state["clicked_coord"] = (lat, lon)
        st.success(f"Stored coordinate: ({lat:.4f}, {lon:.4f})")

    # Row 2 — Season range
    st.markdown("### Season Range (July → June)")
    c1, c2 = st.columns(2)
    with c1:
        current_year = date.today().year
        start_year = st.selectbox("Start season year", list(range(current_year - 15, current_year + 1)), index=10)
    with c2:
        end_year = st.selectbox("End season year", list(range(start_year, current_year + 1)), index=2)

    # Row 3 — Drift parameters
    st.markdown("### Snow-Drift Parameters")
    c3, c4, c5 = st.columns(3)
    with c3:
        T = st.number_input("T (transport distance, m)", 500, 10000, DEFAULT_T, step=500)
    with c4:
        F = st.number_input("F (fetch distance, m)", 1000, 100000, DEFAULT_F, step=500)
    with c5:
        theta = st.slider("Relocation coefficient θ", 0.1, 1.0, DEFAULT_THETA, 0.05)

    st.markdown("### Fence Type")
    fence_type = st.selectbox("Choose fence", ["Wyoming", "Slat-and-wire", "Solid"])

    st.markdown("---")
    run = st.button("🚀 Run Computation", type="primary")

# ---------------------------------------------------------
# STOP if not run
# ---------------------------------------------------------
if not run:
    st.info("Adjust configuration above and click *Run Computation*.")
    st.stop()

# ---------------------------------------------------------
# FETCH ERA5 DATA
# ---------------------------------------------------------
with st.spinner("Fetching ERA5 data…"):
    df_raw = fetch_era5_hourly(
        lat, lon,
        f"{start_year}-07-01",
        f"{end_year+1}-06-30"
    )

# ---------------------------------------------------------
# CALCULATE RESULTS
# ---------------------------------------------------------
with st.spinner("Computing snow drift metrics…"):
    yearly, monthly = compute_year_and_month_results(df_raw, T, F, theta)
    avg_sector = compute_average_sector(df_raw)

yearly["Qt (tonnes/m)"] = yearly["Qt (kg/m)"] / 1000
yearly["Fence height (m)"] = yearly["Qt (kg/m)"].apply(lambda q: compute_fence_height(q, fence_type))

# ---------------------------------------------------------
# Plot builders
# ---------------------------------------------------------
def plot_yearly_bar():
    return px.bar(
        yearly,
        x="season",
        y="Qt (tonnes/m)",
        title="Annual Snow Transport (Qt)",
        labels={"Qt (tonnes/m)": "Qt [tonnes/m]"},
        color="Control"
    )

def plot_monthly_bar():
    if monthly.empty:
        return None
    mdf = monthly.copy()
    mdf["Qt (tonnes/m)"] = mdf["Qt (kg/m)"] / 1000
    mdf["month_name"] = mdf["month"].map({
        1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
        7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"
    })
    return px.bar(
        mdf,
        x="month_name", y="Qt (tonnes/m)",
        color="season",
        barmode="group",
        title="Monthly Qt per Season"
    )

def plot_wind_rose():
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
            "S","SSW","SW","WSW","W","WNW","NW","NNW"]

    theta_deg = np.arange(0, 360, 360/16)
    r_vals = avg_sector / 1000.0

    fig = go.Figure()

    fig.add_trace(go.Barpolar(
        r=r_vals,
        theta=theta_deg,
        text=dirs,
        marker=dict(
            color=r_vals,
            colorscale="Blues",
            line=dict(color="white", width=1)  # outline for clarity
        ),
        hovertemplate="Dir %{text}<br>Qt: %{r:.2f} t/m<extra></extra>"
    ))

    fig.update_layout(
        title="Wind Rose – Mean Transport Direction",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                tickfont=dict(color="white", size=14),   # <-- bright white
                angle=90,
                showline=True,
                linewidth=2,
                linecolor="white",                       # <-- visible gridline
                gridcolor="rgba(255,255,255,0.25)",      # <-- softer grid
            ),
            angularaxis=dict(
                tickvals=theta_deg,
                ticktext=dirs,
                tickfont=dict(color="white", size=15),   # <-- bright white labels
                rotation=90,
                direction="clockwise",
                gridcolor="rgba(255,255,255,0.25)",      # <-- visible grid
                linecolor="white",
            ),
        ),
    )

    return fig


def season_table():
    return yearly[["season", "Qt (tonnes/m)", "Control", "Fence height (m)"]]

# ---------------------------------------------------------
# DISPLAY 2×2 LAYOUT
# ---------------------------------------------------------
st.subheader("📊 Results")

c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(plot_yearly_bar(), use_container_width=True)
with c2:
    monthly_fig = plot_monthly_bar()
    if monthly_fig:
        st.plotly_chart(monthly_fig, use_container_width=True)
    else:
        st.info("No monthly snowfall detected.")

c3, c4 = st.columns(2)
with c3:
    st.markdown("### Fence Height Table")
    st.dataframe(season_table(), use_container_width=True)

with c4:
    st.plotly_chart(plot_wind_rose(), use_container_width=True)
