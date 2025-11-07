import streamlit as st
import random

st.set_page_config(page_title="Meme Page", page_icon="😂", layout="centered")

st.title("Meme Zone")
st.write("Because every project deserves a laugh. And I need some practice ;)")

# List of meme URLs ( Can change to any meme I want )
memes = [
    "https://pbs.twimg.com/media/DXJnAlSU8AAzPl-.jpg",  # Drake meme
    "https://blog.zegocloud.com/wp-content/uploads/2024/02/programming-meme-2.jpg",    # code last year meme
    "https://economistwritingeveryday.com/wp-content/uploads/2024/02/goog.jpg", # Senior coder meme
]

# Initialize session state for meme URL if not already set
if "meme_url" not in st.session_state:
    st.session_state["meme_url"] = random.choice(memes)
    
# Setting columns left for button, right for meme display
left, right = st.columns([1, 2])

# Initializing the button with random meme
with left:
    st.subheader("Pick your meme")
    if st.button("🎲 Random Meme"):
        # exclude the currently shown meme
        available = [m for m in memes if m != st.session_state["meme_url"]]
        if available:
            st.session_state["meme_url"] = random.choice(available)
            
# Displaying the meme
try:
    st.image(meme_url, use_container_width=True)
except TypeError:
    # Older Streamlit
    st.image(meme_url, use_column_width=True)
