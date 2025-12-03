import streamlit as st
import numpy as np
import pandas as pd
import requests
import altair as alt
from scipy.fft import dct, idct
from sklearn.neighbors import LocalOutlierFactor
from sidebar import navigation

st.set_page_config(page_title="B4 – Weather Anomalies", layout="wide")
st.title("B4 – Weather & Production Anomalies (DCT / SPC / LOF)")

navigation()

# --- Common helpers (paste into pages that need weather) ---

PRICE_AREAS = {
    "NO1": {"city": "Oslo",         "lat": 59.9139, "lon": 10.7522},
    "NO2": {"city": "Kristiansand", "lat": 58.1467, "lon": 7.9956},
    "NO3": {"city": "Trondheim",    "lat": 63.4305, "lon": 10.3951},
    "NO4": {"city": "Tromsø",       "lat": 69.6492, "lon": 18.9553},
    "NO5": {"city": "Bergen",       "lat": 60.3913, "lon": 5.3221},
}

ERA5_URL = "https://archive-api.open-meteo.com/v1/era5"
ERA5_VARS = [
    "temperature_2m",
    "precipitation",
    "windspeed_10m",
    "windgusts_10m",
    "winddirection_10m",
]


@st.cache_data(show_spinner=True)
def fetch_era5(lat: float, lon: float, year: int = 2021, tz: str = "Europe/Oslo") -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "hourly": ",".join(ERA5_VARS),
        "timezone": tz,
    }
    r = requests.get(ERA5_URL, params=params, timeout=60)
    r.raise_for_status()
    hourly = r.json().get("hourly", {})
    df = pd.DataFrame(hourly)
    df["time"] = pd.to_datetime(df["time"])
    return df.set_index("time").sort_index()


def get_selected_area() -> str:
    area = st.session_state.get("area")
    if area not in PRICE_AREAS:
        st.info(
            "No area selected yet; defaulting to NO5 (Bergen). "
            "Open 'Price Dashboard' to change."
        )
        area = "NO5"
    return area


# --- main logic ---

area = get_selected_area()
coords = PRICE_AREAS[area]
df = fetch_era5(coords["lat"], coords["lon"], year=2021)

tab_out, tab_lof = st.tabs(["Temperature — DCT/SPC", "Precipitation — LOF"])

# -------------------------------------------------------------------
# TAB 1: Temperature — DCT/SPC with raw-space control limits
# -------------------------------------------------------------------
with tab_out:
    st.write("High-pass filter via DCT to compute SATV; SPC limits via robust MAD.")

    freq_cutoff = st.slider("DCT low-freq cutoff", 40, 120, 60, step=5)
    n_std = st.slider("Sigma (MAD)", 2.0, 4.0, 3.0, step=0.5)

    temp = df["temperature_2m"].to_numpy(float)
    n = temp.size
    k = max(1, min(freq_cutoff, n - 1))

    # DCT-based separation
    coeffs = dct(temp, norm="ortho")
    hp = coeffs.copy()
    hp[:k] = 0  # zero out low-frequency part -> keep high-freq (SATV)
    satv = idct(hp, norm="ortho")

    # Robust limits in SATV space
    med = np.median(satv)
    mad = np.median(np.abs(satv - med))
    rstd = 1.4826 * mad or (np.std(satv) or 1e-9)
    lo, hi = med - n_std * rstd, med + n_std * rstd

    # Transform limits back to raw space:
    # trend = low-frequency component = original - SATV
    trend = temp - satv
    lower_raw = trend + lo
    upper_raw = trend + hi

    # Outliers are still detected in SATV space
    mask = (satv < lo) | (satv > hi)

    # Build a dataframe for plotting
    spc_df = df[["temperature_2m"]].copy()
    spc_df["time"] = spc_df.index
    spc_df["outlier"] = mask
    spc_df["lower"] = lower_raw
    spc_df["upper"] = upper_raw

    # Base temperature line (raw data)
    base = (
        alt.Chart(spc_df)
        .mark_line()
        .encode(
            x=alt.X("time:T", title="Time"),
            y=alt.Y("temperature_2m:Q", title="Temperature (°C)"),
        )
    )

    # Control limits band in raw space (from SATV limits transformed back)
    band = (
        alt.Chart(spc_df)
        .mark_area(opacity=0.15)
        .encode(
            x="time:T",
            y="lower:Q",
            y2="upper:Q",
            tooltip=[
                "time:T",
                alt.Tooltip("lower:Q", title="Lower limit"),
                alt.Tooltip("upper:Q", title="Upper limit"),
            ],
        )
    )

    # Red circles on outlier points
    outliers_layer = (
        alt.Chart(spc_df[spc_df["outlier"]])
        .mark_circle(size=40, color="red")
        .encode(
            x="time:T",
            y="temperature_2m:Q",
            tooltip=["time:T", "temperature_2m:Q"],
        )
    )

    st.altair_chart(base + band + outliers_layer, use_container_width=True)

    st.metric("Outliers", int(mask.sum()))

    with st.expander("Show outlier timestamps"):
        st.dataframe(
            pd.DataFrame(
                {
                    "time": df.index[mask],
                    "temperature_2m": df["temperature_2m"][mask],
                }
            ).reset_index(drop=True),
            use_container_width=True,
        )

# -------------------------------------------------------------------
# TAB 2: Precipitation — Local Outlier Factor
# -------------------------------------------------------------------
with tab_lof:
    st.write("Local Outlier Factor (contamination default 1%).")

    prop = st.slider("Proportion of outliers", 0.005, 0.05, 0.01, step=0.005)
    z = df[["precipitation"]].fillna(0.0)

    lof = LocalOutlierFactor(contamination=prop)
    pred = lof.fit_predict(z)  # -1 = outlier
    mask = pred == -1

    lof_df = df[["precipitation"]].copy()
    lof_df["time"] = lof_df.index
    lof_df["outlier"] = mask

    base_p = (
        alt.Chart(lof_df)
        .mark_line()
        .encode(
            x=alt.X("time:T", title="Time"),
            y=alt.Y("precipitation:Q", title="Precipitation (mm)"),
        )
    )

    outliers_p = (
        alt.Chart(lof_df[lof_df["outlier"]])
        .mark_circle(size=40, color="red")
        .encode(
            x="time:T",
            y="precipitation:Q",
            tooltip=["time:T", "precipitation:Q"],
        )
    )

    st.altair_chart(base_p + outliers_p, use_container_width=True)
    st.metric("Anomalies", int(mask.sum()))

    with st.expander("Show anomaly timestamps"):
        st.dataframe(
            pd.DataFrame(
                {
                    "time": df.index[mask],
                    "precipitation": df["precipitation"][mask],
                }
            ).reset_index(drop=True),
            use_container_width=True,
        )
