import streamlit as st
import pandas as pd
import plotly.express as px
import json
from pathlib import Path
from sidebar import navigation

st.markdown("""
    <style>
        section[data-testid="stSidebar"] {display: none;}
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Page configuration
# ---------------------------------------------------------
st.set_page_config(page_title="Energy Map (NO1–NO5)", layout="wide")
st.title("Energy Map by Price Area (NO1–NO5)")

navigation()

st.markdown(
    """
This page shows a map of energy **production** or **consumption**
aggregated over a chosen **date interval** and **energy group**.

Use the controls on the right to select:
- the **dataset** (production vs. consumption),
- the **energy group**,
- the **date range**, and
- optionally a **price area to highlight**.

The map colours each price area (NO1–NO5) by the **average kWh** over the selected time period.
    """
)

# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------
DATA_ROOT = Path(__file__).resolve().parents[1] / "Data"
GOLD_DIR = DATA_ROOT / "gold"
GEOJSON_PATH = DATA_ROOT / "geo" / "price_areas.geojson"

PROD_GROUP_PATH = GOLD_DIR / "production_daily_by_group.csv"
CONS_GROUP_PATH = GOLD_DIR / "consumption_daily_by_group.csv"

# ---------------------------------------------------------
# Mapping between our priceArea codes and the GeoJSON IDs
# ---------------------------------------------------------
PRICEAREA_TO_GEOID = {
    "NO1": "NO 1",
    "NO2": "NO 2",
    "NO3": "NO 3",
    "NO4": "NO 4",
    "NO5": "NO 5",
}

# ---------------------------------------------------------
# Data loaders
# ---------------------------------------------------------
@st.cache_data(show_spinner=True)
def load_gold_daily(kind: str) -> pd.DataFrame:
    """Load Gold daily-by-group data for production or consumption."""
    if kind == "production":
        path = PROD_GROUP_PATH
    else:
        path = CONS_GROUP_PATH

    if not path.exists():
        raise FileNotFoundError(
            f"Required data file missing: {path}\n"
            "Please ensure the Gold CSV files are placed in streamlit/Data/gold/."
        )

    df = pd.read_csv(path, parse_dates=["date"])

    df["priceArea"] = df["priceArea"].astype(str).str.upper()
    if kind == "production":
        df["group"] = df["productionGroup"].astype(str).str.upper()
    else:
        df["group"] = df["consumptionGroup"].astype(str).str.upper()

    return df


@st.cache_data(show_spinner=True)
def load_geojson():
    """Load price-area GeoJSON and return it together with the ID field."""
    if not GEOJSON_PATH.exists():
        raise FileNotFoundError(
            f"GeoJSON not found: {GEOJSON_PATH}\n"
            "Download 'NVE Elspot områder / ElSpot_omraade' as GeoJSON and "
            "save it as 'streamlit/Data/geo/price_areas.geojson'."
        )

    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        gj = json.load(f)

    id_field = "ElSpotOmr"
    props = gj["features"][0]["properties"]
    if id_field not in props:
        raise ValueError(
            f"Expected GeoJSON property '{id_field}' not found. "
            f"Available properties: {list(props.keys())}"
        )

    geo_ids = sorted({feat["properties"][id_field] for feat in gj["features"]})
    return gj, id_field, geo_ids


# ---------------------------------------------------------
# Load data with error handling
# ---------------------------------------------------------
try:
    geojson, id_field, geo_ids = load_geojson()
except Exception as e:
    st.error(f"Could not load GeoJSON data.\n\n**Details:** {e}")
    st.stop()

kind = st.radio(
    "Dataset",
    ["Production", "Consumption"],
    horizontal=True,
    help="Choose whether to view energy production or consumption."
)
kind_key = "production" if kind == "Production" else "consumption"

try:
    df = load_gold_daily(kind_key)
except Exception as e:
    st.error(f"Could not load the selected dataset.\n\n**Details:** {e}")
    st.stop()

if df.empty:
    st.error("The dataset is empty. No data available.")
    st.stop()

# ---------------------------------------------------------
# Sidebar Filters
# ---------------------------------------------------------
left, right = st.columns([2, 1])

with right:
    st.subheader("Filters")

    # Energy group selection
    groups_avail = sorted(df["group"].dropna().unique().tolist())
    sel_group = st.selectbox(
        "Energy group",
        options=groups_avail,
        index=0,
        help="Select which energy source or category to display."
    )

    # Date range
    min_date = df["date"].min().date()
    max_date = df["date"].max().date()
    start_date, end_date = st.date_input(
        "Date interval (aggregation period)",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        help="Data will be averaged over this date range."
    )

    # Handle older Streamlit list behavior
    if isinstance(start_date, list):
        start_date, end_date = start_date

    st.caption(f"Selected interval: **{start_date} → {end_date}**")

    # Highlight selection
    highlight_area = st.selectbox(
        "Highlight price area (red outline)",
        ["None"] + sorted(df["priceArea"].unique().tolist()),
        index=0,
        help="Optionally emphasize one price area on the map."
    )

# ---------------------------------------------------------
# Filter + aggregate
# ---------------------------------------------------------
mask = (
    (df["group"] == sel_group) &
    (df["date"].dt.date >= start_date) &
    (df["date"].dt.date <= end_date)
)
filt = df.loc[mask].copy()

if filt.empty:
    st.warning("No data available for this combination of filters.")
    st.stop()

agg = (
    filt.groupby("priceArea", as_index=False)["quantityKwh_sum"]
        .mean()
        .rename(columns={"quantityKwh_sum": "mean_quantity"})
)

agg["geo_id"] = agg["priceArea"].map(PRICEAREA_TO_GEOID)

st.caption(f"Average calculated over **{len(filt['date'].unique())}** day(s).")

# ---------------------------------------------------------
# Map
# ---------------------------------------------------------
with left:
    st.subheader("Map of price areas")

    zmax = agg["mean_quantity"].max()

    fig = px.choropleth_mapbox(
        agg,
        geojson=geojson,
        locations="geo_id",
        featureidkey=f"properties.{id_field}",
        color="mean_quantity",
        color_continuous_scale="Viridis",
        range_color=(0, zmax),
        mapbox_style="carto-positron",
        zoom=3.7,
        center={"lat": 64.5, "lon": 12.0},
        opacity=0.5,
        hover_name="priceArea",
        labels={"mean_quantity": "Mean kWh (avg over period)"},
    )

    # Highlight selected area with red overlay
    if highlight_area != "None":
        hi = agg[agg["priceArea"] == highlight_area].copy()
        if not hi.empty:
            highlight_id = hi["geo_id"].iloc[0]

            hi_geojson = {
                "type": "FeatureCollection",
                "features": [
                    feat for feat in geojson["features"]
                    if feat["properties"][id_field] == highlight_id
                ],
            }

            fig.add_choroplethmapbox(
                geojson=hi_geojson,
                locations=[highlight_id],
                z=[1],
                featureidkey=f"properties.{id_field}",
                showscale=False,
                marker_line_width=3,
                marker_line_color="red",
                colorscale=[
                    [0, "rgba(255, 0, 0, 0.5)"],
                    [1, "rgba(255, 0, 0, 0.5)"],
                ],
                hoverinfo="skip",
                name=f"Highlighted area: {highlight_area}",
            )

    # Add a marker for stored coordinates
    clicked = st.session_state.get("clicked_coord")
    if clicked is not None:
        lat, lon = clicked
        fig.add_scattermapbox(
            lat=[lat],
            lon=[lon],
            mode="markers",
            marker={"size": 14},
            name="Selected point",
        )

    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------
# Coordinate selection
# ---------------------------------------------------------
st.markdown("#### Coordinate for snow drift / local analysis")
st.caption(
    "This coordinate is shared across pages via "
    "`st.session_state['clicked_coord']` and can be used for snow drift or local calculations."
)

col1, col2 = st.columns(2)
with col1:
    lat = st.number_input(
        "Latitude",
        value=float(st.session_state.get("clicked_coord", (65.0, 12.0))[0]),
        format="%.4f",
    )
with col2:
    lon = st.number_input(
        "Longitude",
        value=float(st.session_state.get("clicked_coord", (65.0, 12.0))[1]),
        format="%.4f",
    )

if st.button("Store coordinate"):
    st.session_state["clicked_coord"] = (lat, lon)
    st.success(f"Stored coordinate: ({lat:.4f}, {lon:.4f})")

# ---------------------------------------------------------
# Debug / data table
# ---------------------------------------------------------
with st.expander("Show aggregated data table"):
    st.dataframe(agg, use_container_width=True)
