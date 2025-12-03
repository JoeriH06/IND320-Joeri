import streamlit as st, pandas as pd, plotly.express as px
from statsmodels.tsa.seasonal import STL
from scipy.signal import spectrogram
from pymongo import MongoClient
import certifi, numpy as np
from sidebar import navigation

st.set_page_config(page_title="B3 – STL & Spectrogram", layout="wide")
st.title("B3 – STL Decomposition & Spectrogram (Energy Series)")

navigation()

@st.cache_data(ttl=300, show_spinner=True)
def load_mongo_df() -> pd.DataFrame:
    cfg = st.secrets["mongo"]
    client = MongoClient(cfg["uri"], tlsCAFile=certifi.where(), serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    col = client[cfg.get("database", "elhub")][cfg.get("collection", "df_clean")]
    df = pd.DataFrame(list(col.find({}, {"_id": 0})))
    return df

df = load_mongo_df()
if df.empty:
    st.error("No data in MongoDB collection.")
    st.stop()

# Coerce types
df["starttime"] = pd.to_datetime(df["starttime"], utc=True, errors="coerce")
df["quantitykwh"] = pd.to_numeric(df["quantitykwh"], errors="coerce")
df = df.dropna(subset=["starttime","quantitykwh"])

area = st.selectbox("Price area", sorted(df["pricearea"].dropna().unique()), index=0, key="newA_area")
group = st.selectbox("Production group (optional)", ["All"] + sorted(df["productiongroup"].dropna().unique()), index=0, key="newA_group")

series = df[df["pricearea"]==area]
if group != "All":
    series = series[series["productiongroup"]==group]
y = series.set_index("starttime").sort_index()["quantitykwh"].resample("H").sum().interpolate()

tab_stl, tab_spec = st.tabs(["STL decomposition", "Spectrogram"])

with tab_stl:
    period = st.number_input("Period (samples)", value=24, min_value=4, step=1)
    seasonal = st.number_input("Seasonal smoother (odd)", value=13, min_value=3, step=2)
    trend = st.number_input("Trend smoother (odd)", value=201, min_value=5, step=2)
    robust = st.toggle("Robust", value=True)
    res = STL(y, period=period, seasonal=seasonal, trend=trend, robust=robust).fit()
    st.line_chart(pd.DataFrame({"observed": y, "trend": res.trend, "seasonal": res.seasonal, "remainder": res.resid}), use_container_width=True)

with tab_spec:
    window_len = st.number_input("Window length (samples)", value=24*14, min_value=8, step=8)
    overlap = st.slider("Overlap", 0.0, 0.95, 0.5)
    dt_ns = np.median(np.diff(y.index.asi8)); fs = 1.0 / (dt_ns/3.6e12) if dt_ns>0 else 1.0
    nper = int(window_len); nover = int(overlap*nper); nover = min(nover, nper-1)
    f, t, Sxx = spectrogram(y.values, fs=fs, window="hann", nperseg=nper, noverlap=nover, detrend="constant", scaling="density", mode="psd")
    t0 = y.index[0]; tdt = pd.to_datetime(t0) + pd.to_timedelta(t, unit="h")
    # quick px.imshow-like plotly figure:
    import plotly.graph_objects as go
    fig = go.Figure(data=go.Heatmap(x=tdt, y=f, z=Sxx, colorscale="Viridis"))
    fig.update_layout(title=f"Spectrogram — {area} ({group})", xaxis_title="Time", yaxis_title="Hz")
    st.plotly_chart(fig, use_container_width=True)
