import streamlit as st
import numpy as np
import pandas as pd
import requests
import altair as alt
from scipy.fft import dct, idct
from sklearn.neighbors import LocalOutlierFactor
from sidebar import navigation

# ---------------------------------------------------------
# PAGE SETUP
# ---------------------------------------------------------
st.set_page_config(page_title="B4 – Weather Anomalies", layout="wide")
st.title("🌡️ B4 – Weather & Production Anomalies (DCT • SPC • LOF)")

navigation()

st.markdown("""
This dashboard highlights **meteorological anomalies** using:

- **DCT high-pass filtering + SPC** (for temperature)
- **Local Outlier Factor (LOF)** (for precipitation)

Use the tabs to explore different anomaly detection methods.
""")

# ---------------------------------------------------------
# STATIC CONFIG
# ---------------------------------------------------------
PRICE_AREAS = {
    "NO1": {"city": "Oslo", "lat": 59.9139, "lon": 10.7522},
    "NO2": {"city": "Kristiansand", "lat": 58.1467, "lon": 7.9956},
    "NO3": {"city": "Trondheim", "lat": 63.4305, "lon": 10.3951},
    "NO4": {"city": "Tromsø", "lat": 69.6492, "lon": 18.9553},
    "NO5": {"city": "Bergen", "lat": 60.3913, "lon": 5.3221},
}

ERA5_URL = "https://archive-api.open-meteo.com/v1/era5"
ERA5_VARS = [
    "temperature_2m", "precipitation", "windspeed_10m",
    "windgusts_10m", "winddirection_10m"
]

# ---------------------------------------------------------
# FETCH WEATHER
# ---------------------------------------------------------
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
    df = pd.DataFrame(r.json().get("hourly", {}))
    df["time"] = pd.to_datetime(df["time"])
    return df.set_index("time").sort_index()

# ---------------------------------------------------------
# AREA PICKER
# ---------------------------------------------------------
st.subheader("📍 Data Selection")

cols = st.columns(3)
with cols[0]:
    area = st.selectbox("Price area", sorted(PRICE_AREAS.keys()))
with cols[1]:
    year = st.selectbox("Year", [2021, 2022, 2023], index=0)
with cols[2]:
    st.write("")  # spacing

coords = PRICE_AREAS[area]
df = fetch_era5(coords["lat"], coords["lon"], year=year)

st.markdown("---")

# ---------------------------------------------------------
# TABS
# ---------------------------------------------------------
tab_stl, tab_lof = st.tabs(["🌡️ Temperature — DCT/SPC", "🌧️ Precipitation — LOF"])

# =========================================================
# TAB 1 — DCT / SPC
# =========================================================
with tab_stl:

    st.subheader("🔎 Temperature Anomaly Detection (DCT + SPC)")

    # ---------------- Controls ----------------
    with st.container():
        st.markdown("### ⚙️ Parameters")

        c1, c2, c3 = st.columns([1,1,1])

        with c1:
            freq_cutoff = st.slider("DCT low-frequency cutoff", 40, 120, 60, step=5)
        with c2:
            n_std = st.slider("Sigma threshold", 2.0, 4.0, 3.0, step=0.5)
        with c3:
            st.metric("Year loaded", year)

    st.markdown("### 📈 Temperature with SPC Control Limits")

    # -----------------------------------------------------
    # Computation
    # -----------------------------------------------------
    temp = df["temperature_2m"].to_numpy(float)
    n = temp.size
    k = max(1, min(freq_cutoff, n - 1))

    coeffs = dct(temp, norm="ortho")
    hp = coeffs.copy()
    hp[:k] = 0
    satv = idct(hp, norm="ortho")

    med = np.median(satv)
    mad = np.median(np.abs(satv - med))
    rstd = 1.4826 * mad if mad > 0 else np.std(satv)

    lo, hi = med - n_std * rstd, med + n_std * rstd

    trend = temp - satv
    lower_raw = trend + lo
    upper_raw = trend + hi

    mask = (satv < lo) | (satv > hi)

    spc_df = df[["temperature_2m"]].copy()
    spc_df["time"] = spc_df.index
    spc_df["outlier"] = mask
    spc_df["lower"] = lower_raw
    spc_df["upper"] = upper_raw

    # ---------------------------------------------------------
    # Plot
    # ---------------------------------------------------------
    base = alt.Chart(spc_df).mark_line().encode(
        x="time:T", y=alt.Y("temperature_2m:Q", title="Temperature (°C)")
    )

    band = alt.Chart(spc_df).mark_area(opacity=0.15).encode(
        x="time:T", y="lower:Q", y2="upper:Q"
    )

    outliers = alt.Chart(spc_df[spc_df["outlier"]]).mark_circle(size=45, color="red").encode(
        x="time:T", y="temperature_2m:Q",
        tooltip=["time:T","temperature_2m:Q"]
    )

    st.altair_chart(base + band + outliers, use_container_width=True)

    st.metric("Detected anomalies", int(mask.sum()))

    with st.expander("📄 Show anomaly timestamps"):
        outlier_df = pd.DataFrame({
            "time": df.index[mask],
            "temperature_2m": df["temperature_2m"][mask],
        }).reset_index(drop=True)
        st.dataframe(outlier_df, use_container_width=True)

# =========================================================
# TAB 2 — LOF for precipitation
# =========================================================
with tab_lof:

    st.subheader("🌧️ Precipitation Anomaly Detection (LOF)")

    cA, cB = st.columns(2)
    with cA:
        prop = st.slider("Proportion of anomalies", 0.005, 0.05, 0.01, step=0.005)
    with cB:
        st.metric("Year loaded", year)

    z = df[["precipitation"]].fillna(0.0)

    lof = LocalOutlierFactor(contamination=prop)
    pred = lof.fit_predict(z)

    mask = pred == -1

    lof_df = df.copy()
    lof_df["time"] = lof_df.index
    lof_df["outlier"] = mask

    base2 = alt.Chart(lof_df).mark_line().encode(
        x="time:T",
        y=alt.Y("precipitation:Q", title="Precipitation (mm)")
    )

    out2 = alt.Chart(lof_df[lof_df["outlier"]]).mark_circle(size=45, color="red").encode(
        x="time:T",
        y="precipitation:Q",
        tooltip=["time:T","precipitation:Q"]
    )

    st.altair_chart(base2 + out2, use_container_width=True)

    st.metric("Detected anomalies", int(mask.sum()))

    with st.expander("📄 Show anomaly timestamps"):
        outlier_df = pd.DataFrame({
            "time": df.index[mask],
            "precipitation": df["precipitation"][mask],
        }).reset_index(drop=True)
        st.dataframe(outlier_df, use_container_width=True)
