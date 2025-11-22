import streamlit as st
import pandas as pd
import numpy as np
import requests
from pymongo import MongoClient
import certifi
import plotly.express as px

# ---------------------------------------------------------
# Page configuration
# ---------------------------------------------------------
st.set_page_config(page_title="A3 – Sliding Correlation", layout="wide")
st.title("A3 – Sliding Correlation (Meteorology ↔ Energy)")

st.markdown(
    """
This page compares **meteorological variables** and **energy production** using a
**sliding window correlation**:

1. Choose a **price area** and **production group**.
2. Select a **meteorological variable**.
3. Set the **window length** (hours) and **lag** (meteorology leads/lags energy).
4. Inspect how correlation changes over time, especially around extreme events.
    """
)

# ---------------------------------------------------------
# Constants / simple configuration
# ---------------------------------------------------------
ERA5_URL = "https://archive-api.open-meteo.com/v1/era5"

PRICE_AREAS = {
    "NO1": {"city": "Oslo",         "lat": 59.9139, "lon": 10.7522},
    "NO2": {"city": "Kristiansand", "lat": 58.1467, "lon": 7.9956},
    "NO3": {"city": "Trondheim",    "lat": 63.4305, "lon": 10.3951},
    "NO4": {"city": "Tromsø",       "lat": 69.6492, "lon": 18.9553},
    "NO5": {"city": "Bergen",       "lat": 60.3913, "lon": 5.3221},
}

METEO_VARS = [
    "temperature_2m",
    "precipitation",
    "windspeed_10m",
    "windgusts_10m",
    "winddirection_10m",
]


# ---------------------------------------------------------
# Data loaders
# ---------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=True)
def load_energy_from_mongo() -> pd.DataFrame:
    """Load cleaned Elhub production data from MongoDB (df_clean)."""
    try:
        cfg = st.secrets["mongo"]
        client = MongoClient(
            cfg["uri"],
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=8000,
        )
        client.admin.command("ping")
        col = client[cfg.get("database", "elhub")][cfg.get("collection", "df_clean")]
        df = pd.DataFrame(list(col.find({}, {"_id": 0})))
    except Exception as e:
        raise RuntimeError(f"MongoDB connection failed: {e}")

    if df.empty:
        raise RuntimeError("MongoDB collection 'df_clean' is empty.")

    df["starttime"] = pd.to_datetime(df["starttime"], utc=True, errors="coerce")
    df["quantitykwh"] = pd.to_numeric(df["quantitykwh"], errors="coerce")
    df = df.dropna(subset=["starttime", "quantitykwh"])
    df = df.set_index("starttime").sort_index()

    return df


@st.cache_data(show_spinner=True)
def fetch_era5_hourly(lat: float, lon: float, start_date: str, end_date: str, tz: str = "UTC") -> pd.DataFrame:
    """
    Fetch hourly ERA5 data for selected meteorological variables from Open-Meteo.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(METEO_VARS),
        "timezone": tz,
    }
    r = requests.get(ERA5_URL, params=params, timeout=60)
    r.raise_for_status()
    hourly = r.json().get("hourly", {})
    df = pd.DataFrame(hourly)
    df["time"] = pd.to_datetime(df["time"])
    return df.set_index("time").sort_index()


# ---------------------------------------------------------
# Sliding correlation helper
# ---------------------------------------------------------
def sliding_corr(df: pd.DataFrame, window_hours: int) -> pd.DataFrame:
    """Compute rolling Pearson correlation between 'energy_kwh' and 'meteo'."""
    corr = df["energy_kwh"].rolling(window=window_hours).corr(df["meteo"])
    out = pd.DataFrame({"time": df.index, "corr": corr})
    return out.dropna()


# ---------------------------------------------------------
# UI – selectors
# ---------------------------------------------------------
try:
    energy_full = load_energy_from_mongo()
except Exception as e:
    st.error(str(e))
    st.stop()

left, right = st.columns([1.1, 1.9])

with left:
    st.subheader("Series selection")

    price_areas = sorted(energy_full["pricearea"].dropna().unique())
    price_area = st.selectbox(
        "Price area",
        price_areas,
        help="Elspot price area for the production data.",
    )

    groups = ["All"] + sorted(energy_full["productiongroup"].dropna().unique())
    group = st.selectbox(
        "Production group",
        groups,
        index=0,
        help="Choose a specific production group or 'All' to aggregate.",
    )

    meteo_var = st.selectbox(
        "Meteorological variable",
        METEO_VARS,
        index=0,
        help="Variable from ERA5 archive to correlate with energy.",
    )

    window_hours = st.slider(
        "Window length (hours)",
        min_value=24,
        max_value=24 * 60,
        value=24 * 14,
        step=24,
        help="Size of the rolling window for correlation.",
    )

    lag_hours = st.slider(
        "Lag (hours, meteorology → energy)",
        min_value=-72,
        max_value=72,
        value=0,
        step=6,
        help="Positive lag means meteorology leads energy by this many hours.",
    )

    # Date range based on energy data in this price area
    e_sub = energy_full[energy_full["pricearea"] == price_area]
    if e_sub.empty:
        st.error(f"No energy data for price area {price_area}.")
        st.stop()

    min_dt = e_sub.index.min()
    max_dt = e_sub.index.max()

    start_date, end_date = st.date_input(
        "Date range",
        value=(min_dt.date(), max_dt.date()),
        min_value=min_dt.date(),
        max_value=max_dt.date(),
        help="Time interval used both for energy and ERA5 data.",
    )
    if isinstance(start_date, list):
        start_date, end_date = start_date

    run_btn = st.button("Run sliding correlation", type="primary")


# ---------------------------------------------------------
# Main logic
# ---------------------------------------------------------
if not run_btn:
    with right:
        st.info(
            "Configure the series, meteorological variable, window and lag on the left, "
            "then click **Run sliding correlation**."
        )
    st.stop()

coords = PRICE_AREAS.get(price_area, PRICE_AREAS["NO5"])

with st.spinner("Fetching ERA5 data and preparing time series…"):
    try:
        meteo_df = fetch_era5_hourly(
            lat=coords["lat"],
            lon=coords["lon"],
            start_date=str(start_date),
            end_date=str(end_date),
            tz="UTC",
        )
    except Exception as e:
        st.error(f"Failed to fetch ERA5 data: {e}")
        st.stop()

# Energy series
series_e = energy_full[energy_full["pricearea"] == price_area].copy()
if group != "All":
    series_e = series_e[series_e["productiongroup"] == group]

if series_e.empty:
    with right:
        st.error("No energy data after filtering by price area and group.")
    st.stop()

# Aggregate to hourly sum
series_e = (
    series_e["quantitykwh"]
    .resample("H").sum()
    .rename("energy_kwh")
)

series_e = series_e.loc[str(start_date):str(end_date)]

series_m = meteo_df[meteo_var].rename("meteo")

# Apply lag
if lag_hours != 0:
    series_m = series_m.shift(int(lag_hours), freq="H")

# ---- FIX: force UTC on both ----
if series_m.index.tz is None:
    series_m.index = series_m.index.tz_localize("UTC")

if series_e.index.tz is None:
    # unlikely, but safe
    series_e.index = series_e.index.tz_localize("UTC")
else:
    series_e.index = series_e.index.tz_convert("UTC")

# Now join
df_join = pd.concat([series_e, series_m], axis=1).dropna()


if df_join.empty:
    with right:
        st.warning(
            "No overlapping data between energy and meteorology after alignment "
            "(check date range and lag)."
        )
    st.stop()

# Compute sliding correlation
corr_df = sliding_corr(df_join, window_hours)

with right:
    st.subheader("Sliding correlation over time")

    if corr_df.empty:
        st.warning(
            "Correlation window is longer than the available data or there are too few points. "
            "Try reducing the window length."
        )
    else:
        title = (
            f"Sliding correlation: {meteo_var} vs energy in {price_area} "
            f"({group}) – window={window_hours} h, lag={lag_hours} h"
        )
        fig_corr = px.line(
            corr_df,
            x="time",
            y="corr",
            title=title,
            labels={"time": "Time", "corr": "Correlation"},
        )
        fig_corr.update_yaxes(range=[-1, 1])
        st.plotly_chart(fig_corr, use_container_width=True)

    st.subheader("Aligned series (for context)")
    st.line_chart(df_join, use_container_width=True)

    with st.expander("Data sample"):
        st.write(df_join.head())
