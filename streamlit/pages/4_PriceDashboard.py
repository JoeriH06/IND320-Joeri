# --------------------- Page 4: Two-Column Analysis --------------------------
import streamlit as st
import pandas as pd
import plotly.express as px

def render_page_four(df: pd.DataFrame):
    # Ensure expected columns and normalized types
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    required = {"pricearea", "productiongroup", "starttime", "quantitykwh"}
    missing = required - set(df.columns)
    if missing:
        st.error(f"❌ Missing required columns in your data: {sorted(missing)}")
        st.stop()

    df["starttime"] = pd.to_datetime(df["starttime"], errors="coerce", utc=True)
    df = df.dropna(subset=["starttime"])
    df["quantitykwh"] = pd.to_numeric(df["quantitykwh"], errors="coerce").fillna(0.0)
    df["month"] = df["starttime"].dt.month

    month_names = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }

    st.markdown("### Page 4 — Left/Right Split")

    left, right = st.columns(2, gap="large")

    # -------- Left: price area radio + pie chart --------------------------------
    with left:
        st.subheader("Area & Composition")
        price_areas = sorted(df["pricearea"].dropna().unique().tolist())
        if not price_areas:
            st.warning("No price areas found in data.")
            st.stop()

        area = st.radio("Select price area", price_areas, index=0, key="p4_area")

        # Pie = share by production group for the selected area (whole year)
        pie_data = (
            df[df["pricearea"] == area]
            .groupby("productiongroup", as_index=False)["quantitykwh"]
            .sum()
            .sort_values("quantitykwh", ascending=False)
        )
        if pie_data.empty:
            st.info("No data for the selected price area.")
        else:
            fig_pie = px.pie(
                pie_data,
                values="quantitykwh",
                names="productiongroup",
                title=f"Production share — {area}",
            )
            st.plotly_chart(fig_pie, use_container_width=True)

    # -------- Right: pills + month selector + line plot -------------------------
    with right:
        st.subheader("Groups & Monthly Trend")

        # Groups selector (pills if available, else multiselect)
        all_groups = sorted(df["productiongroup"].dropna().unique().tolist())
        if hasattr(st, "pills"):
            selected_groups = st.pills(
                "Production group(s)",
                options=all_groups,
                selection_mode="multi",
                default=all_groups,
                key="p4_groups",
            )
        else:
            selected_groups = st.multiselect(
                "Production group(s)", options=all_groups, default=all_groups, key="p4_groups"
            )

        # Month selector
        sel_month = st.selectbox(
            "Month",
            options=list(month_names.keys()),
            index=0,
            format_func=lambda m: month_names[m],
            key="p4_month",
        )

        # Filter: by area + month + groups
        f = df[(df["pricearea"] == area) & (df["month"] == sel_month)]
        if selected_groups:
            f = f[f["productiongroup"].isin(selected_groups)]

        # Line plot (hourly trend for selected month/groups)
        if f.empty:
            st.info("No rows for this combination of price area, groups, and month.")
        else:
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
                title=f"Hourly production — {area} — {month_names[sel_month]}",
            )
            fig_line.update_layout(legend_title_text="Group")
            st.plotly_chart(fig_line, use_container_width=True)

    # -------- Expander below the two columns ------------------------------------
    with st.expander("ℹ️ About the data"):
        st.markdown(
            """
            **Source:** Elhub Energy Data API (dataset: `PRODUCTION_PER_GROUP_MBA_HOUR`).  
            The data is preprocessed and stored in MongoDB, then loaded into this app.  
            Charts show hourly production in kWh, aggregated by price area and production group.
            """
        )
