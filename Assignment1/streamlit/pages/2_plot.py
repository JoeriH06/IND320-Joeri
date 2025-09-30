import streamlit as st
import pandas as pd
import altair as alt

st.title("Plot")
st.write("ℹ️ Plot the imported data with column and month selection.")

@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    # Here we load the CSV and normalize the time column to datetime (UTC)
    df = pd.read_csv(path)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
    return df

# Here we load the dataset from the subfolder and use caching for efficiency
data = load_data("../../Data/open-meteo-subset.csv")

# Here we validate the time column so that .dt operations are safe.
if "time" not in data.columns or not pd.api.types.is_datetime64_any_dtype(data["time"]):
    st.error("The 'time' column could not be parsed as datetime.")
    st.stop()

# Here we get the list of numeric columns to plot.
numeric_cols = data.select_dtypes(include="number").columns.tolist()
if not numeric_cols:
    st.warning("No numeric columns found to plot.")
    st.stop()

# Here we build month options from the data (YYYY-MM strings).
data["month"] = data["time"].dt.to_period("M")
months = sorted(data["month"].dropna().unique().tolist())
month_labels = [str(m) for m in months]

# Here we create the UI controls (column picker + month range)
col_choice = st.selectbox(
    "Choose a column to plot (or all columns):",
    options=["All columns"] + numeric_cols,
    index=0,
)

# Here we create a month range selector; defaults to the first month.
start_label, end_label = st.select_slider(
    "Select a month range:",
    options=month_labels,
    value=(month_labels[0], month_labels[0]),
)

# Here we filter the dataframe to the selected month range.
start_period = pd.Period(start_label, freq="M")
end_period = pd.Period(end_label, freq="M")
mask = data["month"].between(start_period, end_period)
df = data.loc[mask].copy()

# Here we format the title and axis labels.
title_text = f"Data column: {col_choice if col_choice != 'All columns' else 'All series'}"
subtitle_text = f"From {start_label} to {end_label}"

# Here we build the chart (Altair) with clean formatting.
if col_choice == "All columns":
    # Melt long for multi-series plotting.
    plot_df = df.melt(id_vars=["time"], value_vars=numeric_cols, var_name="Series", value_name="Value")
    chart = (
        alt.Chart(plot_df)
        .mark_line()
        .encode(
            x=alt.X("time:T", title="Time"),
            y=alt.Y("Value:Q", title="Value"),
            color=alt.Color("Series:N", title="Series"),
            tooltip=["time:T", "Series:N", "Value:Q"],
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
            y=alt.Y("Value:Q", title=f"{col_choice}"),
            tooltip=["time:T", "Value:Q"],
        )
        .properties(title={"text": title_text, "subtitle": subtitle_text})
        .interactive()
    )

# Here we display the final chart.
st.altair_chart(chart, use_container_width=True)

# Here we show a preview of the selected data range.
with st.expander("Show preview of filtered data", expanded=False):
    st.dataframe(
        df[["time"] + numeric_cols].reset_index(drop=True),
        use_container_width=True
    )

# I used this website to get ideas for the altair plots:
# https://altair-viz.github.io/gallery/index.html#example-gallery
