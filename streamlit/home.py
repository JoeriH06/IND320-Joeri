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

# ---- What this project contains ----
st.subheader("What you can explore")
st.markdown(
    """
This application brings together the main components of the **IND320** project:

- Structuring & transforming energy data  
- Integrating meteorology with production & consumption  
- Detecting anomalies  
- Building forecasting models  

Use the **left sidebar** to navigate through the different analysis modules.
"""
)

st.info(
    "Tip: Start with **Price Dashboard** or **Map & Energy** to get an overview of the data."
)

st.divider()
st.caption("IND320 Project — Joeri Harreman, 2025")
