import streamlit as st

st.set_page_config(page_title="IND320 Project", page_icon="📊", layout="wide")

st.title("IND320 – Project Home")
st.markdown("""
This app accompanies my Jupyter Notebook (`main.ipynb`).

**Navigation**
Use the sidebar to open:
- About
- Data Table (first-month sparkline table)
- Plot (choose column(s) and month range)
""")

with st.sidebar:
    st.header("Navigation")
    st.page_link("streamlit_app.py", label="🏠 Home", icon="🏠")
    st.page_link("pages/1_About.py", label="ℹ️ About")
    st.page_link("pages/2_Data_Table.py", label="📋 Data Table")
    st.page_link("pages/3_Plot.py", label="📈 Plot")

st.divider()
st.subheader("Links")
st.markdown("""
- GitHub: [My Repository](https://github.com/JoeriH06/IND320)
- Streamlit: will run at `https://<reponame>-<username>.streamlit.app`
""")
