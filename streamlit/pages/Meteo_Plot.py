import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path
from sidebar import navigation

# ---------------------------------------------------------
# Page Setup
# ---------------------------------------------------------
st.set_page_config(page_title="Meteorology Plot", layout="wide")
st.title("🌦️ Meteorology Plot – Weather Trends & Variables")

navigation()

st.markdown("""
Explore hourly/daily **meteorological variables** from ERA5 / Open-Meteo.

You can:
- Visualize **any single variable** or **all variables**
- Select a **month or a month range**
- Interactively explore trends, zoom, hover, compare  
""")

# ---------------------------------------------------------
# Load Data
# ---------------------------------------------------------
@st.cache_data
def load_data() -> pd.DataFrame:
    csv_path = Path(__file__).resolve().parents[1] / "Data" / "open_meteo_clean.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found at: {csv_path}")

    df = pd.read_csv(csv_path)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
    return df


try:
    data = load_data()
except Exception as e:
    st.error(f"❌ Failed to load data:\n\n{e}")
    st.stop()

if "time" not in data.columns or not pd.api.types.is_datetime64_any_dtype(data["time"]):
    st.error("❌ The dataset does not contain a valid 'time' column.")
    st.stop()

# ---------------------------------------------------------
# Extract numeric columns & month list
# ---------------------------------------------------------
numeric_cols = data.select_dtypes(include="number").columns.tolist()

if not numeric_cols:
    st.warning("⚠️ No numeric meteorological variables found to plot.")
    st.stop()

data["month"] = data["time"].dt.to_period("M")
months = sorted(data["month"].dropna().unique().tolist())
month_labels = [str(m) for m in months]

# ---------------------------------------------------------
# UI: Configuration
# ---------------------------------------------------------
st.subheader("⚙️ Plot Configuration")

# --- Variable selection ---
col_var = st.columns([1])[0]
col_choice = col_var.selectbox(
    "Variable:",
    options=["All variables"] + numeric_cols,
    index=0,
)

# --- Month range slider (clean centered UI) ---
st.markdown("### Month range")

col_left, col_slider, col_right = st.columns([1, 6, 1])
with col_slider:
    start_label, end_label = st.select_slider(
        label="Select month range",
        options=month_labels,
        value=(month_labels[0], month_labels[-1]),
    )

st.markdown("---")

# ---------------------------------------------------------
# Filter Data
# ---------------------------------------------------------
start_period = pd.Period(start_label, freq="M")
end_period = pd.Period(end_label, freq="M")
mask = data["month"].between(start_period, end_period)
df = data.loc[mask].copy()

# ---------------------------------------------------------
# Summary row
# ---------------------------------------------------------
st.subheader("📊 Summary")
c1, c2 = st.columns(2)
c1.metric("Rows selected", len(df))
c2.metric("Months in range", f"{start_label} → {end_label}")

# ---------------------------------------------------------
# Build Plot
# ---------------------------------------------------------
title_text = (
    col_choice if col_choice != "All variables"
    else "All meteorological variables"
)
subtitle_text = f"{start_label} → {end_label}"

if col_choice == "All variables":

    plot_df = df.melt(
        id_vars=["time"],
        value_vars=numeric_cols,
        var_name="Variable",
        value_name="Value"
    )

    chart = (
        alt.Chart(plot_df)
        .mark_line()
        .encode(
            x=alt.X("time:T", title="Time"),
            y=alt.Y("Value:Q", title="Value"),
            color=alt.Color("Variable:N", title="Variable"),
            tooltip=["time:T", "Variable:N", "Value:Q"],
        )
        .properties(title={"text": title_text, "subtitle": subtitle_text})
        .interactive()
    )

else:

    plot_df = df[["time", col_choice]].rename(columns={col_choice: "Value"})

    chart = (
        alt.Chart(plot_df)
        .mark_line()
        .encode(
            x=alt.X("time:T", title="Time"),
            y=alt.Y("Value:Q", title=col_choice),
            tooltip=["time:T", "Value:Q"],
        )
        .properties(title={"text": title_text, "subtitle": subtitle_text})
        .interactive()
    )

# ---------------------------------------------------------
# Display Plot
# ---------------------------------------------------------
st.subheader("📈 Trend Plot")
st.altair_chart(chart, use_container_width=True)

# ---------------------------------------------------------
# Data Preview
# ---------------------------------------------------------
with st.expander("📄 Show data preview"):
    st.dataframe(
        df[["time"] + numeric_cols].reset_index(drop=True),
        use_container_width=True
    )
