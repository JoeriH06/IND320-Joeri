import streamlit as st
st.write("secrets keys:", list(st.secrets.keys()))
st.set_page_config(page_title="IND320 Project", page_icon="📊", layout="centered")
st.title("Home")
st.markdown("---")
col1, col2 = st.columns([2, 3])

with col1:
    st.image(
        "https://framerusercontent.com/images/uWEtm8wdAW1prhgeNYuzWf2gESQ.png?width=500&height=500",
        use_container_width=True,
    )

with col2:
    st.subheader("Welcome, this is my homepage for the IND320 project")
    st.write(
        """
        This is the **IND320 Project homepage**.  
        
        Use the sidebar on the left to navigate through the pages:
        - **About** → learn what this project is about  
        - **Table** → see the data in a table :) 
        - **Plot** → explore the dataset interactively  
        - **Meme Zone** → take a break and have fun  
        """
    )
    st.success("Pick a page from the sidebar and enjoy exploring!")


st.markdown("---")
st.caption("Created by Joeri Harreman, 2025")
