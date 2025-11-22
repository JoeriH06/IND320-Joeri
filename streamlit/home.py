import streamlit as st

st.set_page_config(
    page_title="IND320 – Energy & Weather Analytics",
    page_icon="📊",
    layout="centered",
)

# ---- Header ----
st.title("IND320 – Energy & Weather Analytics")
st.markdown(
    "<p style='color: gray;'>Streamlit interface for production, consumption, "
    "meteorology and forecasting tasks.</p>",
    unsafe_allow_html=True,
)

st.divider()

# ---- Short orientation ----
st.markdown(
    """
    This application brings together the main components of the IND320 project:

    - Ingesting and structuring energy data (Bronze → Silver → Gold)
    - Combining Elhub data with meteorological data
    - Analysing anomalies and building forecasting models

    Use the **sidebar** to navigate between the different analysis pages.
    """
)

st.divider()

# ---- Section overview ----
st.subheader("Navigation overview")

st.markdown(
    """
    ### 1. Energy production & consumption
    - **Price Dashboard** – Hourly production by price area and group (MongoDB-backed).
    - **Map & Choropleth** – Price area overview with group and time selection.
    - **Sliding Correlation** – Correlation between meteorological variables and energy.
    - **Forecasting (SARIMAX)** – Configurable time-series models with confidence intervals.

    ### 2. Meteorology & anomalies
    - **Table / Plot** – Cleaned Open-Meteo data for inspection and basic analysis.
    - **STL & Spectrogram** – Decomposition and frequency analysis of production series.
    - **Outliers & Anomalies (Weather)** – Detection of unusual conditions using DCT/SPC and LOF.

    ### 3. Miscellaneous
    - **Meme Zone** – Informal content related to the project.
    """
)

st.info(
    "Tip: Start with **Price Dashboard** or **Map & Choropleth** to get an overview of "
    "the data, then move on to correlation and forecasting."
)

st.divider()
st.caption("IND320 project – Joeri Harreman, 2025")
