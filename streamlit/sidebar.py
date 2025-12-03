import streamlit as st

def navigation():
    st.sidebar.title("Navigation")

    # --- ENERGY ---
    with st.sidebar.expander("⚡ Energy Production & Consumption", expanded=True):
        st.page_link("home.py", label="Home")
        st.page_link("pages/PriceDashboard.py", label="Price Dashboard")
        st.page_link("pages/Map_and_Energy.py", label="Map & Energy")
        st.page_link("pages/Sliding_Correlation.py", label="Sliding Correlation")
        st.page_link("pages/Forecasting_SARIMAX.py", label="Forecasting")

    # --- METEOROLOGY ---
    with st.sidebar.expander("🌦️ Meteorology", expanded=True):
        st.page_link("pages/Meteo_Table.py", label="Meteo Table")
        st.page_link("pages/Meteo_Plot.py", label="Meteo Plot")
        st.page_link("pages/STL_and_Spectrogram.py", label="STL & Spectrogram")
        st.page_link("pages/Weather_Anomalies.py", label="Weather Anomalies")

    # --- SNOW + MISC ---
    with st.sidebar.expander("❄️ Snow", expanded=True):
        st.page_link("pages/SnowDrift.py", label="Snow Drift")
