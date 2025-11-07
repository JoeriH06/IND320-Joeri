import streamlit as st, numpy as np, pandas as pd
from scipy.fft import dct, idct
from sklearn.neighbors import LocalOutlierFactor


st.title("Outliers & Anomalies (Weather)")

# --- Common helpers (paste into pages that need weather) ---
import requests, pandas as pd, streamlit as st

PRICE_AREAS = {
    "NO1": {"city": "Oslo",         "lat": 59.9139, "lon": 10.7522},
    "NO2": {"city": "Kristiansand", "lat": 58.1467, "lon": 7.9956},
    "NO3": {"city": "Trondheim",    "lat": 63.4305, "lon": 10.3951},
    "NO4": {"city": "Tromsø",       "lat": 69.6492, "lon": 18.9553},
    "NO5": {"city": "Bergen",       "lat": 60.3913, "lon": 5.3221},
}

ERA5_URL = "https://archive-api.open-meteo.com/v1/era5"
ERA5_VARS = ["temperature_2m","precipitation","windspeed_10m","windgusts_10m","winddirection_10m"]

@st.cache_data(show_spinner=True)
def fetch_era5(lat: float, lon: float, year: int = 2021, tz: str = "Europe/Oslo") -> pd.DataFrame:
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": f"{year}-01-01", "end_date": f"{year}-12-31",
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
        st.info("No area selected yet; defaulting to NO5 (Bergen). Open 'Price Dashboard' to change.")
        area = "NO5"
    return area

# --- shared utils (paste) ---
# PRICE_AREAS, fetch_era5, get_selected_area as above
area = get_selected_area()
coords = PRICE_AREAS[area]
df = fetch_era5(coords["lat"], coords["lon"], year=2021)

tab_out, tab_lof = st.tabs(["Temperature — DCT/SPC", "Precipitation — LOF"])

with tab_out:
    st.write("High-pass filter via DCT to compute SATV; SPC limits via robust MAD.")
    freq_cutoff = st.slider("DCT low-freq cutoff", 40, 120, 60, step=5)
    n_std = st.slider("Sigma (MAD)", 2.0, 4.0, 3.0, step=0.5)
    temp = df["temperature_2m"].to_numpy(float); n = temp.size
    k = max(1, min(freq_cutoff, n-1))
    coeffs = dct(temp, norm="ortho"); hp = coeffs.copy(); hp[:k] = 0; satv = idct(hp, norm="ortho")
    med = np.median(satv); mad = np.median(np.abs(satv-med)); rstd = 1.4826*mad or (np.std(satv) or 1e-9)
    lo, hi = med - n_std*rstd, med + n_std*rstd
    mask = (satv<lo)|(satv>hi)
    st.line_chart(df[["temperature_2m"]], use_container_width=True)
    st.metric("Outliers", int(mask.sum()))
    with st.expander("Show outlier timestamps"):
        st.dataframe(pd.DataFrame({"time": df.index[mask], "temperature_2m": df["temperature_2m"][mask]}).reset_index(drop=True), use_container_width=True)

with tab_lof:
    st.write("Local Outlier Factor (contamination default 1%).")
    prop = st.slider("Proportion of outliers", 0.005, 0.05, 0.01, step=0.005)
    z = df[["precipitation"]].fillna(0.0)
    lof = LocalOutlierFactor(contamination=prop)
    pred = lof.fit_predict(z)  # -1 outlier
    mask = pred == -1
    st.line_chart(df[["precipitation"]], use_container_width=True)
    st.metric("Anomalies", int(mask.sum()))
    with st.expander("Show anomaly timestamps"):
        st.dataframe(pd.DataFrame({"time": df.index[mask], "precipitation": df["precipitation"][mask]}).reset_index(drop=True), use_container_width=True)
