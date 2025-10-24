import streamlit as st
import pandas as pd
import plotly.express as px
import urllib.parse
from pymongo import MongoClient
from pymongo.errors import OperationFailure

st.set_page_config(page_title="Price Dashboard", page_icon="💹", layout="wide")

# ---------- MONGODB CONNECTION ----------
HOST_DEFAULT = "cluster1.vihi1ie.mongodb.net"
APPNAME_DEFAULT = "cluster1"

@st.cache_resource(show_spinner=False)
def get_mongo_client() -> MongoClient:
    cfg = st.secrets["mongo"]
    uri = cfg.get("uri")
    if not uri or "mongodb+srv://" not in uri:
        user = cfg["user"]
        password = urllib.parse.quote_plus(cfg["password"])
        dbname = cfg.get("database", "elhub")
        uri = (
            f"mongodb+srv://{user}:{password}@{HOST_DEFAULT}/"
            f"{dbname}?retryWrites=true&w=majority&appName={APPNAME_DEFAULT}"
        )
    return MongoClient(uri, tls=True, serverSelectionTimeoutMS=8000)

@st.cache_data(ttl=600, show_spinner=True)
def load_data() -> pd.DataFrame:
    cfg = st.secrets["mongo"]
    client = get_mongo_client()
    db = client[cfg.get("database", "elhub")]
    collection = db[cfg.get("collection", "df")]
    try:
        data = list(collection.find({}, {"_id": 0}))
    except OperationFailure as e:
        st.cache_resource.clear()
        st.error(f"❌ MongoDB authentication failed: {getattr(e, 'details', {}) or str(e)}")
        st.stop()

    df = pd.DataFrame(data)
    if df.empty:
        st.error("⚠️ No data found in MongoDB. Check your database/collection names.")
        st.stop()

    # Normalize columns & types
    df.columns = [c.lower() for c in df.columns]
    for c in ("pricearea", "productiongroup", "quantitykwh", "starttime"):
        if c not in df.columns:
            st.error(f"❌ Missing expected column '{c}' in your data.")
            st.stop()

    df["starttime"] = pd.to_datetime(df["starttime"], errors="coerce", utc=True)
    df["month"] = df["starttime"].dt.month
    return df

with st.spinner("Loading data from MongoDB..."):
    df = load_data()

# SIDEBAR CONTROLS
with st.sidebar:
    st.header("Filters")
    month_names = {
        0: "All year", 1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August", 9: "September",
        10: "October", 11: "November", 12: "December",
    }

    # price area
    price_areas = sorted(df["pricearea"].dropna().unique().tolist())
    price_area = st.radio("Price area", price_areas, index=0)

    # month
    month = st.selectbox("Month", list(month_names.keys()), format_func=lambda x: month_names[x], index=0)

    # groups
    all_groups = sorted(df["productiongroup"].dropna().unique().tolist())
    if hasattr(st, "pills"):
        selected_groups = st.pills(
            "Production group(s)",
            options=all_groups,
            selection_mode="multi",
            default=all_groups,
            key="selected_groups",
        )
    else:
        selected_groups = st.multiselect("Production group(s)", options=all_groups, default=all_groups, key="selected_groups")

# FILTERED DATA 
f = df[df["pricearea"] == price_area].copy()
if month != 0:
    f = f[f["month"] == month]
if selected_groups:
    f = f[f["productiongroup"].isin(selected_groups)]

# Basic aggregations for KPIs
total_mwh = (f["quantitykwh"].sum() / 1000.0) if not f.empty else 0.0
start_d = f["starttime"].min()
end_d = f["starttime"].max()

# KPI HEADER
k1, k2, k3 = st.columns([1.1, 1, 1])
k1.metric("Total production (MWh)", f"{total_mwh:,.0f}")
k2.metric("Groups shown", f"{len(selected_groups) if selected_groups else 0}")
k3.metric("Date range", f"{start_d.date() if pd.notna(start_d) else '—'} → {end_d.date() if pd.notna(end_d) else '—'}")

st.markdown("---")

# TABS LAYOUT
tab1, tab2, tab3 = st.tabs(["🧭 Overview", "🧩 Composition", "📄 Data"])

with tab1:
    c1, c2 = st.columns([1, 1])

    with c1:
        st.subheader(f"Share by group — {price_area} ({month_names[month]})")
        pie_df = f.copy()
        pie_data = (
            pie_df.groupby("productiongroup", as_index=False)["quantitykwh"]
            .sum()
            .sort_values("quantitykwh", ascending=False)
        )
        fig_pie = px.pie(
            pie_data,
            values="quantitykwh",
            names="productiongroup",
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        st.subheader(f"Trend — {price_area} ({month_names[month]})")
        line_data = (
            f.groupby(["starttime", "productiongroup"], as_index=False)["quantitykwh"]
            .sum()
            .sort_values("starttime")
        )
        fig_line = px.line(
            line_data,
            x="starttime",
            y="quantitykwh",
            color="productiongroup",
        )
        st.plotly_chart(fig_line, use_container_width=True)

with tab2:
    st.subheader(f"Stacked composition over time — {price_area} ({month_names[month]})")
    area_data = (
        f.groupby(["starttime", "productiongroup"], as_index=False)["quantitykwh"]
        .sum()
        .sort_values("starttime")
    )
    # stacked area via px.area
    fig_area = px.area(
        area_data,
        x="starttime",
        y="quantitykwh",
        color="productiongroup",
        groupnorm=None,
    )
    st.plotly_chart(fig_area, use_container_width=True)

with tab3:
    st.subheader("Current selection — data preview")
    st.dataframe(
        f.sort_values(["starttime", "productiongroup"]).reset_index(drop=True),
        use_container_width=True,
        height=420,
    )

# ---------- EXPANDER ----------
with st.expander("ℹ️ About the data"):
    st.markdown(
        """
        *Source:* Elhub API – hourly production data (2021)  
        Data processed in Spark and stored in MongoDB (collection: **df**)  
        This page shows production shares and trends for a selected price area, month, and one or more production groups.
        """
    )
