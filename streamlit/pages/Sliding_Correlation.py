import streamlit as st
import pandas as pd
import numpy as np
import requests
from pymongo import MongoClient
import certifi
import plotly.express as px
from sidebar import navigation

st.markdown("""
    <style>
        section[data-testid="stSidebar"] {display: none;}
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Page configuration
# ---------------------------------------------------------
st.set_page_config(page_title="Sliding Correlation", layout="wide")
st.title("📈 Sliding Correlation (Meteorology ↔ Energy)")

navigation()

st.markdown("""
Use this tool to explore **how meteorological conditions affect energy production**
over time using a **sliding-window correlation**.

**Workflow:**
1. Select **price area**, **production group**, and a **weather variable**  
2. Adjust **window size** and **lag offset**  
3. Click **Run** → inspect correlation + aligned series
""")

# ---------------------------------------------------------
# Constants
# ---------------------------------------------------------
ERA5_URL = "https://archive-api.open-meteo.com/v1/era5"

PRICE_AREAS = {
    "NO1": {"city": "Oslo", "lat": 59.9139, "lon": 10.7522},
    "NO2": {"city": "Kristiansand", "lat": 58.1467, "lon": 7.9956},
    "NO3": {"city": "Trondheim", "lat": 63.4305, "lon": 10.3951},
    "NO4": {"city": "Tromsø", "lat": 69.6492, "lon": 18.9553},
    "NO5": {"city": "Bergen", "lat": 60.3913, "lon": 5.3221},
}

METEO_VARS = [
    "temperature_2m",
    "precipitation",
    "windspeed_10m",
    "windgusts_10m",
    "winddirection_10m",
]

# ---------------------------------------------------------
# Data loading
# ---------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=True)
def load_energy_from_mongo() -> pd.DataFrame:
    cfg = st.secrets["mongo"]
    client = MongoClient(cfg["uri"], tlsCAFile=certifi.where())
    col = client[cfg.get("database", "elhub")][cfg.get("collection", "df_clean")]
    df = pd.DataFrame(list(col.find({}, {"_id": 0})))

    df["starttime"] = pd.to_datetime(df["starttime"], utc=True, errors="coerce")
    df["quantitykwh"] = pd.to_numeric(df["quantitykwh"], errors="coerce")
    df = df.dropna(subset=["starttime", "quantitykwh"])
    return df.set_index("starttime").sort_index()


@st.cache_data(show_spinner=True)
def fetch_era5_hourly(lat, lon, start_date, end_date):
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(METEO_VARS),
        "timezone": "UTC",
    }
    r = requests.get(ERA5_URL, params=params)
    r.raise_for_status()
    df = pd.DataFrame(r.json().get("hourly", {}))
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df.set_index("time").sort_index()

# ---------------------------------------------------------
# Helper
# ---------------------------------------------------------
def sliding_corr(df, window_hours):
    corr = df["energy_kwh"].rolling(window_hours).corr(df["meteo"])
    return pd.DataFrame({"time": df.index, "corr": corr}).dropna()

# ---------------------------------------------------------
# UI – Controls (no sidebar)
# ---------------------------------------------------------
try:
    energy_full = load_energy_from_mongo()
except Exception as e:
    st.error(str(e))
    st.stop()

st.subheader("⚙️ Configuration")

col1, col2 = st.columns(2)

with col1:
    price_area = st.selectbox(
        "Price Area",
        sorted(energy_full["pricearea"].dropna().unique())
    )

    groups = ["All"] + sorted(energy_full["productiongroup"].dropna().unique())
    group = st.selectbox("Production Group", groups)

    meteo_var = st.selectbox("Meteorological Variable", METEO_VARS)

with col2:
    window_hours = st.slider("Window Size (hours)", 24, 24*60, 24*14, step=24)
    lag_hours = st.slider("Lag (hours, meteo → energy)", -72, 72, 0, step=6)

    df_area = energy_full[energy_full["pricearea"] == price_area]
    start_date, end_date = st.date_input(
        "Date Range",
        value=(df_area.index.min().date(), df_area.index.max().date())
    )

run_btn = st.button("🚀 Run Sliding Correlation", type="primary")

if not run_btn:
    st.info("Adjust the configuration above and click **Run**.")
    st.stop()

# ---------------------------------------------------------
# Fetching & Preparing Data
# ---------------------------------------------------------
coords = PRICE_AREAS[price_area]

with st.spinner("Fetching ERA5 and preparing data..."):
    meteo_df = fetch_era5_hourly(
        coords["lat"], coords["lon"], str(start_date), str(end_date)
    )

    e = energy_full[energy_full["pricearea"] == price_area].copy()
    if group != "All":
        e = e[e["productiongroup"] == group]

    energy_hourly = (
        e["quantitykwh"].resample("H").sum()
    ).rename("energy_kwh").loc[str(start_date):str(end_date)]

    meteo_series = meteo_df[meteo_var].rename("meteo").shift(lag_hours, freq="H")

    # ---------------------------------------------------------
    # FIX: FORCE BOTH SERIES TO BE TZ-AWARE UTC
    # ---------------------------------------------------------
    if energy_hourly.index.tz is None:
        energy_hourly.index = energy_hourly.index.tz_localize("UTC")
    else:
        energy_hourly.index = energy_hourly.index.tz_convert("UTC")

    if meteo_series.index.tz is None:
        meteo_series.index = meteo_series.index.tz_localize("UTC")
    else:
        meteo_series.index = meteo_series.index.tz_convert("UTC")

    df_join = pd.concat([energy_hourly, meteo_series], axis=1).dropna()

if df_join.empty:
    st.warning("No overlapping data after applying filters, date range, or lag.")
    st.stop()

corr_df = sliding_corr(df_join, window_hours)

# ---------------------------------------------------------
# Dashboard Section
# ---------------------------------------------------------
st.subheader("📊 Summary")
c1, c2, c3 = st.columns(3)
c1.metric("Data Points", len(df_join))
c2.metric("Window (hours)", window_hours)
c3.metric("Lag (hours)", lag_hours)

# ---------------- Correlation Plot --------------------
st.subheader("📈 Sliding Correlation Over Time")
fig_corr = px.line(
    corr_df, x="time", y="corr",
    labels={"time": "Time", "corr": "Correlation"}
)
fig_corr.update_yaxes(range=[-1, 1])
st.plotly_chart(fig_corr, use_container_width=True)

# ---------------- Time-Series Plot --------------------
st.subheader("🔍 Aligned Time Series")
st.line_chart(df_join, use_container_width=True)

# ---------------- Raw Data ----------------------------
with st.expander("🗂 Data Preview"):
    st.write(df_join.head())
