import streamlit as st
import pandas as pd

st.title("Table")
st.write("ℹ️ One row per series, with a mini line chart for the first month.")

@st.cache_data
def load_data(path) -> pd.DataFrame:
    csv_path = Path(__file__).resolve().parents[2] / "Data" / "open-meteo-subset.csv"
    
    df = pd.read_csv(csv_path)
    # Here we change the time column to datetime (yyyy-mm-dd) for consistency
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
    return df

# Here we load the dataset from the subfolder and use caching for efficiency
data = load_data()

# Here we put the raw data (from cache) in an expanding table to show that caching worked
with st.expander("Raw imported data", expanded=False):
    st.dataframe(data, use_container_width=True)

# Here we check the "time" column
# we ensure that the column exists in the DataFrame
# and we ensure that it is of a datetime dtype (so .dt operations are safe)
if "time" not in data.columns or not pd.api.types.is_datetime64_any_dtype(data["time"]):
    st.error("The 'time' column could not be parsed as datetime.")
    st.stop()

# Now we filter the first month based on the minimum timestamp
first_ts = data["time"].min()
mask = (data["time"].dt.year == first_ts.year) & (data["time"].dt.month == first_ts.month)
first_month = data.loc[mask].copy()

# Here we build a table with one row per numeric column
numeric_cols = first_month.select_dtypes(include="number").columns.tolist()
if not numeric_cols:
    st.warning("No numeric series found to plot.")
else:
    # we create a new df with only the columns and the values
    reshaped = pd.DataFrame(
        {
            "Series": numeric_cols,\
            # this builds one list per column -> emperature_2m	[2.3, 3.1, 4.0, …] windspeed_10m	[12.1, 14.3, 11.0, …]
            "First Month Trend": [first_month[c].tolist() for c in numeric_cols],
        }
    )

    # Here we set min and max values to keep line charts on the same scale
    y_min = first_month[numeric_cols].min().min()
    y_max = first_month[numeric_cols].max().max()

    # Here we display the final overview table with inline line charts
    st.subheader("Series overview (first month)")
    st.dataframe(
        reshaped,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Series": st.column_config.TextColumn("Series"),
            "First Month Trend": st.column_config.LineChartColumn(
                "First Month Trend",
                y_min=y_min,
                y_max=y_max,
            ),
        },
    )
