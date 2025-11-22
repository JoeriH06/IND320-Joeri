import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta
from pymongo import MongoClient
import certifi
from statsmodels.tsa.statespace.sarimax import SARIMAX
import plotly.graph_objects as go
import requests

# ---------------------------------------------------------
# Page config
# ---------------------------------------------------------
st.set_page_config(page_title="A4 – Forecasting (SARIMAX)", layout="wide")
st.title("A4 – Forecasting of Energy Production / Consumption (SARIMAX)")

st.markdown(
    """
This page performs **SARIMAX time–series forecasting** on Elhub energy data.

You can:
- Select **price area**, **production group**, and **aggregation**
- Configure **SARIMA and seasonal** parameters
- Choose **training interval** and **forecast horizon**
- Optionally include **meteorological variables as exogenous regressors**
    """
)

# ---------------------------------------------------------
# Constants
# ---------------------------------------------------------
ERA5_URL = "https://archive-api.open-meteo.com/v1/era5"

METEO_VARS = [
    "temperature_2m",
    "precipitation",
    "windspeed_10m",
    "windgusts_10m",
]

PRICE_AREAS = {
    "NO1": {"lat": 59.9139, "lon": 10.7522},
    "NO2": {"lat": 58.1467, "lon": 7.9956},
    "NO3": {"lat": 63.4305, "lon": 10.3951},
    "NO4": {"lat": 69.6492, "lon": 18.9553},
    "NO5": {"lat": 60.3913, "lon": 5.3221},
}

# ---------------------------------------------------------
# Load energy from MongoDB
# ---------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=True)
def load_energy_df() -> pd.DataFrame:
    cfg = st.secrets["mongo"]
    client = MongoClient(
        cfg["uri"],
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=8000,
    )
    client.admin.command("ping")
    col = client[cfg.get("database", "elhub")][cfg.get("collection", "df_clean")]
    df = pd.DataFrame(list(col.find({}, {"_id": 0})))
    return df

try:
    df = load_energy_df()
except Exception as e:
    st.error(f"MongoDB connection failed: {e}")
    st.stop()

if df.empty:
    st.error("No energy data available in MongoDB.")
    st.stop()

df["starttime"] = pd.to_datetime(df["starttime"], utc=True, errors="coerce")
df["quantitykwh"] = pd.to_numeric(df["quantitykwh"], errors="coerce")
df = df.dropna(subset=["starttime", "quantitykwh"])
df = df.set_index("starttime").sort_index()

# ---------------------------------------------------------
# ERA5 loader
# ---------------------------------------------------------
@st.cache_data(show_spinner=True)
def fetch_era5_hourly(lat: float, lon: float, start_date: str, end_date: str, tz: str = "UTC") -> pd.DataFrame:
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
    df_m = pd.DataFrame(hourly)
    df_m["time"] = pd.to_datetime(df_m["time"])
    return df_m.set_index("time").sort_index()

# ---------------------------------------------------------
# UI: selectors
# ---------------------------------------------------------
left, right = st.columns([1, 2])

with left:
    st.subheader("Selection")

    price_area = st.selectbox(
        "Price area",
        sorted(df["pricearea"].dropna().unique())
    )

    group = st.selectbox(
        "Production group",
        ["All"] + sorted(df["productiongroup"].dropna().unique())
    )

    freq = st.selectbox("Aggregation", ["Hourly", "Daily"], index=1)

    st.markdown("#### SARIMA Parameters")
    p = st.number_input("p", 0, 5, 1)
    d = st.number_input("d", 0, 2, 1)
    q = st.number_input("q", 0, 5, 1)

    P = st.number_input("P", 0, 3, 1)
    D = st.number_input("D", 0, 2, 1)
    Q = st.number_input("Q", 0, 3, 1)

    s = st.number_input(
        "Seasonal period (s)",
        0, 400, 24,
        help="Hourly data: 24. Daily data: 7 (weekly)."
    )

    horizon = st.number_input("Forecast horizon (steps)", 1, 300, 48)

    # training range
    min_dt = df.index.min().date()
    max_dt = df.index.max().date()
    train_start, train_end = st.date_input(
        "Training interval",
        value=(min_dt, max_dt),
        min_value=min_dt,
        max_value=max_dt,
    )
    if isinstance(train_start, list):
        train_start, train_end = train_start

    st.markdown("#### Exogenous meteorological variables (optional)")
    use_exog = st.checkbox("Include weather as exogenous variables", value=False)

    if use_exog:
        exog_vars = st.multiselect(
            "Select meteorological variables",
            METEO_VARS,
            default=["temperature_2m"],
        )
    else:
        exog_vars = []

    run_btn = st.button("Run SARIMAX forecast", type="primary")

# ---------------------------------------------------------
# Build energy series
# ---------------------------------------------------------
series = df[df["pricearea"] == price_area].copy()
if group != "All":
    series = series[series["productiongroup"] == group]

if series.empty:
    with right:
        st.error("No energy data after filtering by price area and group.")
    st.stop()

if freq == "Hourly":
    y = series["quantitykwh"].resample("H").sum()
else:
    y = series["quantitykwh"].resample("D").sum()

y = y.loc[str(train_start):str(train_end)].dropna()

if not run_btn:
    with right:
        st.info("Configure parameters on the left and click **Run SARIMAX forecast**.")
    st.stop()

if len(y) < 10:
    st.error("Too few data points in the selected training interval.")
    st.stop()

# ---------------------------------------------------------
# Prepare exogenous data if requested
# (train only; forecast exog = last observed value repeated)
# ---------------------------------------------------------
exog_train = None
exog_forecast = None

if use_exog and exog_vars:
    coords = PRICE_AREAS.get(price_area, PRICE_AREAS["NO5"])

    exog_start_date = train_start.isoformat()
    exog_end_date = train_end.isoformat()

    with st.spinner("Fetching ERA5 data for exogenous variables (training period)…"):
        try:
            meteo_df = fetch_era5_hourly(
                lat=coords["lat"],
                lon=coords["lon"],
                start_date=exog_start_date,
                end_date=exog_end_date,
                tz="UTC",
            )
        except Exception as e:
            st.error(f"Failed to fetch ERA5 data: {e}")
            st.stop()

    # Aggregate to same frequency as y
    if freq == "Hourly":
        exog_all = meteo_df[exog_vars]
    else:
        exog_all = meteo_df[exog_vars].resample("D").mean()

    # Ensure timezone alignment
    if exog_all.index.tz is None:
        exog_all.index = exog_all.index.tz_localize("UTC")

    # Align with y and clean
    exog_train = exog_all.reindex(y.index)
    exog_train = exog_train.replace([np.inf, -np.inf], np.nan)
    mask_train = exog_train.notna().all(axis=1)

    if not mask_train.all():
        dropped = (~mask_train).sum()
        st.warning(f"Dropping {dropped} training rows with incomplete exogenous data.")

    y = y[mask_train]
    exog_train = exog_train[mask_train]

    if len(y) < 10:
        st.error("Too few data points remain after aligning with exogenous variables.")
        st.stop()

    # Build future exog by repeating the last observed exog value
    last_time = y.index[-1]
    if freq == "Hourly":
        future_index = pd.date_range(
            start=last_time + timedelta(hours=1),
            periods=int(horizon),
            freq="H",
            tz="UTC",
        )
    else:
        future_index = pd.date_range(
            start=last_time + timedelta(days=1),
            periods=int(horizon),
            freq="D",
            tz="UTC",
        )

    last_exog = exog_train.iloc[-1]
    exog_forecast = pd.DataFrame(
        [last_exog.values] * int(horizon),
        index=future_index,
        columns=exog_train.columns,
    )

# ---------------------------------------------------------
# Fit model
# ---------------------------------------------------------
with st.spinner("Fitting SARIMAX model…"):
    order = (int(p), int(d), int(q))
    seasonal_order = (int(P), int(D), int(Q), int(s)) if s > 0 else (0, 0, 0, 0)

    try:
        model = SARIMAX(
            y,
            order=order,
            seasonal_order=seasonal_order,
            exog=exog_train,
            enforce_stationarity=False,
            enforce_invertibility=False,
        ).fit(disp=False)
    except Exception as e:
        st.error(f"Model fitting failed: {e}")
        st.stop()

# ---------------------------------------------------------
# Forecast
# ---------------------------------------------------------
with st.spinner("Forecasting future steps…"):
    forecast_res = model.get_forecast(
        steps=int(horizon),
        exog=exog_forecast if (use_exog and exog_vars) else None,
    )
    forecast = forecast_res.predicted_mean
    ci = forecast_res.conf_int()

# ---------------------------------------------------------
# Plot results
# ---------------------------------------------------------
with right:
    st.subheader("Forecast result")

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=y.index, y=y, mode="lines",
        name="Observed",
        line=dict(width=2)
    ))

    fig.add_trace(go.Scatter(
        x=forecast.index, y=forecast,
        mode="lines", name="Forecast",
        line=dict(width=2, dash="dash")
    ))

    fig.add_trace(go.Scatter(
        x=forecast.index.tolist() + forecast.index[::-1].tolist(),
        y=ci.iloc[:, 0].tolist() + ci.iloc[:, 1][::-1].tolist(),
        fill="toself",
        name="Confidence interval",
        opacity=0.25,
        line=dict(width=0),
        hoverinfo="skip",
    ))

    title_suffix = f" – exog: {', '.join(exog_vars)}" if use_exog and exog_vars else ""
    fig.update_layout(
        title=f"SARIMAX Forecast – {price_area} ({group}){title_suffix}",
        xaxis_title="Time",
        yaxis_title="kWh",
        legend=dict(orientation="h"),
    )

    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Model summary"):
        st.text(model.summary())
