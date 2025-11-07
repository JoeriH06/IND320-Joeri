import streamlit as st
import random

st.set_page_config(page_title="Meme Page", page_icon="😂", layout="centered")

st.title("Meme Zone")
st.write("Because every project deserves a laugh. And I need some practice ;)")

# List of meme URLs (feel free to swap these)
memes = [
    "https://pbs.twimg.com/media/DXJnAlSU8AAzPl-.jpg",  # Drake meme
    "https://blog.zegocloud.com/wp-content/uploads/2024/02/programming-meme-2.jpg",  # coding meme
    "https://economistwritingeveryday.com/wp-content/uploads/2024/02/goog.jpg",       # senior coder meme
]

# Initialize once
if "meme_url" not in st.session_state:
    st.session_state["meme_url"] = random.choice(memes)

left, right = st.columns([1, 2])

with left:
    st.subheader("Pick your meme")
    if st.button("🎲 Random Meme"):
        # avoid repeating the same meme immediately
        choices = [m for m in memes if m != st.session_state["meme_url"]] or memes
        st.session_state["meme_url"] = random.choice(choices)

with right:
    meme_url = st.session_state["meme_url"]
    # Backward compatibility: some Streamlit builds don't support use_container_width
    try:
        st.image(meme_url, use_container_width=True)
    except TypeError:
        st.image(meme_url, use_column_width=True)
