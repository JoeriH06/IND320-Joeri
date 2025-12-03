import streamlit as st
import pandas as pd
from pathlib import Path
from sidebar import navigation


# ---------------------------------------------------------
# Page Setup
# ---------------------------------------------------------
st.set_page_config(page_title="Meteorology Table", layout="wide")
st.title("🌦️ Meteorology Table (Open-Meteo / ERA5)")

navigation()

st.markdown("""
This page displays processed ERA5/Open-Meteo meteorological data and automatically  
generates an **overview of all numeric variables** with sparkline-style trend charts  
for the **first month of available data**.

Use this page to quickly inspect:
- Available meteorological variables  
- The range and shape of their early-period behaviour  
- Whether the imported dataset looks correct  
""")

# ---------------------------------------------------------
# Data Loader
# ---------------------------------------------------------
@st.cache_data
def load_data() -> pd.DataFrame:
    csv_path = Path(__file__).resolve().parents[1] / "Data" / "open_meteo_clean.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found at: {csv_path}")

    df = pd.read_csv(csv_path)

    # Normalize datetime column
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)

    return df


# ---------------------------------------------------------
# Load Data
# ---------------------------------------------------------
try:
    data = load_data()
except Exception as e:
    st.error(f"❌ Failed to load meteorology data:\n\n{e}")
    st.stop()

# ---------------------------------------------------------
# Raw Data Viewer
# ---------------------------------------------------------
with st.expander("📄 View raw imported data"):
    st.dataframe(data, use_container_width=True)

# ---------------------------------------------------------
# Validate time column
# ---------------------------------------------------------
if "time" not in data.columns or not pd.api.types.is_datetime64_any_dtype(data["time"]):
    st.error("❌ The dataset does not contain a valid 'time' column.")
    st.stop()

# ---------------------------------------------------------
# Extract First Month
# ---------------------------------------------------------
first_ts = data["time"].min()
month_mask = (
    (data["time"].dt.year == first_ts.year) &
    (data["time"].dt.month == first_ts.month)
)
first_month = data.loc[month_mask].copy()

if first_month.empty:
    st.warning("⚠️ No data found for the first month of the dataset.")
    st.stop()

st.markdown(f"### 📅 First Month Extracted: **{first_ts.strftime('%B %Y')}**")

# ---------------------------------------------------------
# Build Overview Table w/ Inline Line Charts
# ---------------------------------------------------------
numeric_cols = first_month.select_dtypes(include="number").columns.tolist()

if not numeric_cols:
    st.warning("⚠️ No numeric meteorological variables found.")
    st.stop()

reshaped = pd.DataFrame({
    "Series": numeric_cols,
    "First Month Trend": [first_month[col].tolist() for col in numeric_cols],
})

# Shared scale for consistent sparkline charts
y_min = first_month[numeric_cols].min().min()
y_max = first_month[numeric_cols].max().max()

# ---------------------------------------------------------
# Final Overview Table
# ---------------------------------------------------------
st.subheader("📊 Meteorological Variable Overview")
st.caption("Each sparkline shows all values for the **first month** of available data.")

st.dataframe(
    reshaped,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Series": st.column_config.TextColumn("Variable"),
        "First Month Trend": st.column_config.LineChartColumn(
            "Trend (First Month)",
            y_min=y_min,
            y_max=y_max,
        ),
    },
)
