import streamlit as st
import pandas as pd
import plotly.express as px
from pymongo import MongoClient
import certifi

st.set_page_config(page_title="A1 – Price Dashboard", layout="wide")
st.title("A1 – Price Dashboard (Elhub production)")

@st.cache_data(ttl=300, show_spinner=True)
def load_df_from_mongo() -> pd.DataFrame:
    cfg = st.secrets["mongo"]
    client = MongoClient(cfg["uri"], tlsCAFile=certifi.where(), serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    col = client[cfg.get("database", "elhub")][cfg.get("collection", "df_clean")]
    df = pd.DataFrame(list(col.find({}, {"_id": 0})))
    return df

with st.spinner("Loading data from MongoDB…"):
    df = load_df_from_mongo()

if df.empty:
    st.error("No data in MongoDB collection.")
    st.stop()


df = df.copy()
expected = {"pricearea","productiongroup","starttime","quantitykwh"}
missing = expected - set(df.columns)
if missing:
    st.error(f"Missing required columns in Mongo: {sorted(missing)}")
    st.stop()

df["starttime"]   = pd.to_datetime(df["starttime"], utc=True, errors="coerce")
df["quantitykwh"] = pd.to_numeric(df["quantitykwh"], errors="coerce")
df = df.dropna(subset=["starttime","quantitykwh"])
df["month"] = df["starttime"].dt.month

st.caption(f"Loaded {len(df):,} rows from "
           f"{st.secrets['mongo'].get('database','elhub')}.{st.secrets['mongo'].get('collection','df_clean')}")

# ---------- UI ----------
st.markdown("### Page 4 — Left/Right Split")
month_names = {
    1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",
    7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"
}

left, right = st.columns(2, gap="large")

# ---------------- Left: area radio + pie ----------------
with left:
    st.subheader("Area & Composition")
    price_areas = sorted(df["pricearea"].dropna().unique())
    area = st.radio("Select price area", price_areas, index=0, key="p4_area")
    st.session_state["area"] = area
    area_df = df[df["pricearea"] == area]

    pie_data = (
        area_df.groupby("productiongroup", as_index=False)["quantitykwh"]
        .sum()
        .sort_values("quantitykwh", ascending=False)
    )
    if pie_data.empty:
        st.info("No data for selected area.")
    else:
        st.plotly_chart(
            px.pie(pie_data, values="quantitykwh", names="productiongroup",
                   title=f"Production share — {area}"),
            use_container_width=True
        )

# --------------- Right: pills + month + line ---------------
with right:
    st.subheader("Groups & Monthly Trend")

    # Months actually present for this area
    months_avail = sorted(area_df["month"].dropna().unique().tolist())
    month_options = [0] + months_avail          # 0 = All months
    month_labels  = {0: "All months", **{m: month_names[m] for m in months_avail}}

    # Default to the latest month available
    default_month_index = 0 if not months_avail else month_options.index(months_avail[-1])

    sel_month = st.selectbox(
        "Month",
        options=month_options,
        index=default_month_index,
        format_func=lambda m: month_labels.get(m, str(m)),
        key="p4_month",
    )

    # Narrow the dataframe by month (if not "All")
    filt_df = area_df if sel_month == 0 else area_df[area_df["month"] == sel_month]

    # Groups actually present given area(+month)
    groups_avail = sorted(filt_df["productiongroup"].dropna().unique().tolist())

    if hasattr(st, "pills"):
        groups = st.pills("Production group(s)", options=groups_avail,
                          selection_mode="multi", default=groups_avail, key="p4_groups")
    else:
        groups = st.multiselect("Production group(s)", options=groups_avail,
                                default=groups_avail, key="p4_groups")

    if groups:
        filt_df = filt_df[filt_df["productiongroup"].isin(groups)]

    if filt_df.empty:
        st.info("No rows for this combination of area, groups, and month.")
    else:
        line_data = (
            filt_df.groupby(["starttime", "productiongroup"], as_index=False)["quantitykwh"]
            .sum().sort_values("starttime")
        )
        title_month = month_labels[sel_month]
        st.plotly_chart(
            px.line(line_data, x="starttime", y="quantitykwh", color="productiongroup",
                    title=f"Hourly production — {area} — {title_month}"),
            use_container_width=True
        )

# --------------- Expander ---------------
with st.expander("ℹ️ About the data"):
    st.markdown(
        """
        **Source:** Elhub Energy Data API (`PRODUCTION_PER_GROUP_MBA_HOUR`).  
        Data stored in MongoDB (database: `elhub`, collection: `df_clean`).  
        Charts show hourly production (kWh) by price area and production group.
        """
    )
