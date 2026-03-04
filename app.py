import streamlit as st
from pytubefix import YouTube
from pytubefix.cli import on_progress
import time

st.set_page_config(page_title="YouTube Fix 2.0", page_icon="🔧")

st.title("🔧 YouTube Downloader (pytubefix)")
st.write("This version uses 'pytubefix' to bypass the 'Sign in to confirm' error.")

url = st.text_input("YouTube URL:")

if st.button("Generate Download Link"):
    if url:
        try:
            with st.spinner("Bypassing 'Sign in to confirm' check..."):
                # Initialize YouTube object with PoToken support
                # 'use_po_token=True' is the magic command that fixes the bot error
                yt = YouTube(url, use_po_token=True)
                
                # Get the video title
                title = yt.title
                st.success(f"Video Found: {title}")
                
                # Get the thumbnail
                st.image(yt.thumbnail_url, width=300)
                
                # Extract the best progressive stream (MP4 with audio)
                stream = yt.streams.get_highest_resolution()
                
                # Get the direct URL
                download_url = stream.url
                
                # Display JSON for API usage
                st.subheader("API Response")
                st.json({
                    "status": "success",
                    "title": title,
                    "download_url": download_url
                })
                
                # Create a clickable button
                st.subheader("Download")
                st.markdown(
                    f'<a href="{download_url}" target="_blank" style="background-color: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">Download MP4</a>', 
                    unsafe_allow_html=True
                )
                
                st.caption("If the video opens in a new tab, right-click it and choose 'Save Video As'.")

        except Exception as e:
            st.error("Error occurred:")
            st.code(str(e))
            st.warning("If you see a 'PO Token' error, the server IP might be blacklisted permanently.")
