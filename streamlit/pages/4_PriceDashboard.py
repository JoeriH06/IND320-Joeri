import streamlit as st
import pandas as pd
import plotly.express as px
from pymongo import MongoClient
import certifi

st.set_page_config(page_title="Price Dashboard", layout="wide")


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

# Left: area radio + pie
with left:
    st.subheader("Area & Composition")
    price_areas = sorted(df["pricearea"].dropna().unique())
    area = st.radio("Select price area", price_areas, index=0, key="p4_area")

    pie_data = (df[df["pricearea"] == area]
                .groupby("productiongroup", as_index=False)["quantitykwh"]
                .sum().sort_values("quantitykwh", ascending=False))
    if pie_data.empty:
        st.info("No data for selected area.")
    else:
        st.plotly_chart(
            px.pie(pie_data, values="quantitykwh", names="productiongroup",
                   title=f"Production share — {area}"),
            use_container_width=True
        )

# Right: pills/multiselect + month + line
with right:
    st.subheader("Groups & Monthly Trend")
    all_groups = sorted(df["productiongroup"].dropna().unique())
    if hasattr(st, "pills"):
        groups = st.pills("Production group(s)", options=all_groups, selection_mode="multi",
                          default=all_groups, key="p4_groups")
    else:
        groups = st.multiselect("Production group(s)", options=all_groups,
                                default=all_groups, key="p4_groups")

    sel_month = st.selectbox("Month", options=list(month_names.keys()),
                             index=0, format_func=lambda m: month_names[m], key="p4_month")

    f = df[(df["pricearea"] == area) & (df["month"] == sel_month)]
    if groups:
        f = f[f["productiongroup"].isin(groups)]

    if f.empty:
        st.info("No rows for this combination of area, groups, and month.")
    else:
        line_data = (f.groupby(["starttime","productiongroup"], as_index=False)["quantitykwh"]
                     .sum().sort_values("starttime"))
        st.plotly_chart(
            px.line(line_data, x="starttime", y="quantitykwh", color="productiongroup",
                    title=f"Hourly production — {area} — {month_names[sel_month]}"),
            use_container_width=True
        )

# Expander
with st.expander("ℹ️ About the data"):
    st.markdown(
        """
        **Source:** Elhub Energy Data API (`PRODUCTION_PER_GROUP_MBA_HOUR`).  
        Data stored in MongoDB (database: `elhub`, collection: `df_clean`).  
        Charts show hourly production (kWh) by price area and group.
        """
    )
