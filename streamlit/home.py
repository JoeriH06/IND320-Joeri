import streamlit as st
from sidebar import navigation

st.set_page_config(
    page_title="IND320 - Energy & Weather Analytics",
    page_icon="📊",
    layout="centered",
)

navigation()
# ---- Header ----
st.title("IND320 – Interactive Energy & Meteorology Dashboard")
st.markdown(
    "<p style='color: gray; font-size: 1.1rem;'>A unified interface for exploring "
    "energy production, consumption, meteorology, forecasting, and anomalies.</p>",
    unsafe_allow_html=True,
)

st.divider()

# ---- How the app is organised ----
st.subheader("📁 App Structure")
st.markdown(
    """
### **A — Energy production & consumption**
Analysis of Elhub data (Bronze → Silver → Gold).

### **B — Meteorology & anomalies**
Weather insights based on Open-Meteo and ERA5, including anomaly detection.

### **C — Snow & misc**
Snow-drift modelling and a light-hearted misc section.
"""
)

st.divider()

# ---- What this project contains ----
st.subheader("🔍 What you can explore")
st.markdown(
    """
This application brings together the main components of the **IND320** project:

- Structuring & transforming energy data  
- Integrating meteorology with production & consumption  
- Detecting anomalies  
- Building forecasting models  

Use the **left sidebar** to navigate through each analysis module.
"""
)

st.divider()

# ---- Section overview ----
st.subheader("🧭 Navigation Overview")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
### ⚡ Energy
- Price Dashboard  
- Map & Choropleth  
- Sliding Correlation  
- SARIMAX Forecasting  
"""
    )

with col2:
    st.markdown(
        """
### 🌦️ Meteorology
- Meteo Table  
- Meteo Plot  
- STL & Spectrogram  
- Weather Anomalies  
"""
    )

with col3:
    st.markdown(
        """
### ❄️ Misc
- Snow-Drift Model  
- Meme Zone  
"""
    )

st.info(
    "Tip: Start with **Price Dashboard** or **Map & Choropleth** to get an overview of the data."
)

st.divider()
st.caption("IND320 Project — Joeri Harreman, 2025")
