import streamlit as st

def navigation():
    st.sidebar.title("Navigation")

    # --- ENERGY ---
    with st.sidebar.expander("⚡ Energy Production & Consumption", expanded=True):
        st.page_link("home.py", label="Home")
        st.page_link("pages/A1_PriceDashboard.py", label="Price Dashboard")
        st.page_link("pages/A2_Map_and_Energy.py", label="Map & Energy")
        st.page_link("pages/A3_Sliding_Correlation.py", label="Sliding Correlation")
        st.page_link("pages/A4_Forecasting_SARIMAX.py", label="Forecasting")

    # --- METEOROLOGY ---
    with st.sidebar.expander("🌦️ Meteorology", expanded=True):
        st.page_link("pages/B1_Meteo_Table.py", label="Meteo Table")
        st.page_link("pages/B2_Meteo_Plot.py", label="Meteo Plot")
        st.page_link("pages/B3_STL_and_Spectrogram.py", label="STL & Spectrogram")
        st.page_link("pages/B4_Weather_Anomalies.py", label="Weather Anomalies")

    # --- SNOW + MISC ---
    with st.sidebar.expander("❄️ Snow", expanded=True):
        st.page_link("pages/C1_SnowDrift.py", label="Snow Drift")
