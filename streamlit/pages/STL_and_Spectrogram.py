import streamlit as st
import pandas as pd
import numpy as np
from pymongo import MongoClient
import certifi
from statsmodels.tsa.seasonal import STL
from scipy.signal import spectrogram
import plotly.graph_objects as go
import plotly.express as px
from sidebar import navigation
from plotly.subplots import make_subplots

st.markdown("""
    <style>
        section[data-testid="stSidebar"] {display: none;}
    </style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# Page setup
# ---------------------------------------------------------
st.set_page_config(page_title="STL & Spectrogram", layout="wide")
st.title("📊 STL Decomposition & Spectrogram (Energy Series)")

navigation()

# ---------------------------------------------------------
# Load data
# ---------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=True)
def load_mongo_df() -> pd.DataFrame:
    cfg = st.secrets["mongo"]
    client = MongoClient(
        cfg["uri"],
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=8000
    )
    client.admin.command("ping")
    col = client[cfg.get("database", "elhub")][cfg.get("collection", "df_clean")]
    df = pd.DataFrame(list(col.find({}, {"_id": 0})))
    return df

df = load_mongo_df()
if df.empty:
    st.error("No data available in MongoDB.")
    st.stop()

# Prepare dataframe
df["starttime"] = pd.to_datetime(df["starttime"], utc=True, errors="coerce")
df["quantitykwh"] = pd.to_numeric(df["quantitykwh"], errors="coerce")
df = df.dropna(subset=["starttime", "quantitykwh"])

# ---------------------------------------------------------
# Configuration panel
# ---------------------------------------------------------
st.subheader("⚙️ Configuration")

col1, col2 = st.columns(2)

with col1:
    area = st.selectbox("Price area", sorted(df["pricearea"].dropna().unique()))
with col2:
    group = st.selectbox(
        "Production group (optional)",
        ["All"] + sorted(df["productiongroup"].dropna().unique())
    )

series = df[df["pricearea"] == area]
if group != "All":
    series = series[series["productiongroup"] == group]

y = (
    series.set_index("starttime")
    .sort_index()["quantitykwh"]
    .resample("H").sum()
    .interpolate()
)

# ---------------------------------------------------------
# Tabs for analysis sections
# ---------------------------------------------------------
tab_stl, tab_spec = st.tabs(["📉 STL Decomposition", "🎛️ Spectrogram"])

# ---------------------------------------------------------
# STL TAB
# ---------------------------------------------------------
with tab_stl:
    st.markdown("### STL Parameters")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        period = st.number_input("Period", value=24, min_value=4, step=1)
    with c2:
        seasonal = st.number_input("Seasonal smoother (odd)", value=13, min_value=3, step=2)
    with c3:
        trend = st.number_input("Trend smoother (odd)", value=201, min_value=5, step=2)
    with c4:
        robust = st.toggle("Robust", value=True)

    st.markdown("---")

    st.markdown("### 📊 STL Components (split into 4 plots)")

    res = STL(
        y,
        period=period,
        seasonal=seasonal,
        trend=trend,
        robust=robust
    ).fit()

    # Build separate subplots using Plotly
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        subplot_titles=["Observed", "Trend", "Seasonal", "Residual"]
    )

    fig.add_trace(go.Scatter(x=y.index, y=y, name="Observed"), row=1, col=1)
    fig.add_trace(go.Scatter(x=y.index, y=res.trend, name="Trend"), row=2, col=1)
    fig.add_trace(go.Scatter(x=y.index, y=res.seasonal, name="Seasonal"), row=3, col=1)
    fig.add_trace(go.Scatter(x=y.index, y=res.resid, name="Residual"), row=4, col=1)

    fig.update_layout(
        height=900,
        showlegend=False,
        title=f"STL Decomposition — {area} ({group})"
    )

    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------
# SPECTROGRAM TAB
# ---------------------------------------------------------
with tab_spec:

    st.markdown("### Spectrogram Parameters")

    c1, c2 = st.columns(2)
    with c1:
        window_len = st.number_input(
            "Window length (samples)",
            value=24 * 14,
            min_value=8,
            step=8
        )
    with c2:
        overlap = st.slider("Overlap", 0.0, 0.95, 0.5)

    st.markdown("---")

    st.markdown("### 🎛️ Power Spectrogram")

    # Determine sampling frequency
    dt_ns = np.median(np.diff(y.index.asi8))
    fs = 1.0 / (dt_ns / 3.6e12) if dt_ns > 0 else 1.0

    nper = int(window_len)
    nover = min(int(overlap * nper), nper - 1)

    f, t, Sxx = spectrogram(
        y.values,
        fs=fs,
        window="hann",
        nperseg=nper,
        noverlap=nover,
        detrend="constant",
        scaling="density",
        mode="psd",
    )

    # Convert spectrogram time scale to timestamps
    start_ts = y.index[0]
    t_axis = pd.to_datetime(start_ts) + pd.to_timedelta(t, unit="h")

    # Build heatmap
    fig_spec = go.Figure(
        data=go.Heatmap(
            x=t_axis,
            y=f,
            z=Sxx,
            colorscale="Viridis"
        )
    )
    fig_spec.update_layout(
        title=f"Spectrogram — {area} ({group})",
        xaxis_title="Time",
        yaxis_title="Frequency (Hz)",
        height=700
    )

    st.plotly_chart(fig_spec, use_container_width=True)
