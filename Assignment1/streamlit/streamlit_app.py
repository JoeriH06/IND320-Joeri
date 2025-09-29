import streamlit as st
from streamlit_option_menu import option_menu
# import pandas as pd
# import numpy as np

st.set_page_config(page_title="IND320 Project HomePage", page_icon="📊", layout="wide")
st.title("IND320 Project")

with st.sidebar:
    selected = option_menu(
        menu_title="Menu",
        options=["home", "about", "context"],
        icons=["house-heart-fill", "calendar2-heart-fill"],
        menu_icon="heart-eyes-fill",
        default_index=0,
    )

if selected == "none":
    st.title(f"Welcome to the {selected} page")

elif selected == "context":
    st.title(f"Welcome to the {selected} page")

elif selected == "about":
    st.title(f"Welcome to the {selected} page")
