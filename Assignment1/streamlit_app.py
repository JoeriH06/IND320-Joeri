# streamlit_app.py
import streamlit as st

st.set_page_config(page_title="My Project", page_icon="📊")

st.title("Welcome to My Streamlit App 🎉")
st.write("This is a minimal working example connected to my GitHub repo.")

st.header("About this project")
st.markdown("hello")

st.header("Demo interaction")
name = st.text_input("Enter your name")
if name:
    st.success(f"Hello, {name}! 👋 Thanks for visiting my app.")
