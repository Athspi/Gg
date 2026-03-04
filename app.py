import streamlit as st
import yt_dlp

# Set up the page
st.set_page_config(page_title="YouTube Video API", page_icon="🎥")

st.title("🎥 Free YouTube Video Downloader API")
st.write("Enter a YouTube URL below to extract the direct MP4 download link.")

# Input box for the user
video_url = st.text_input("YouTube Video URL:", placeholder="https://www.youtube.com/watch?v=...")

# A button to trigger the extraction
if st.button("Extract Download Link"):
    if video_url:
        with st.spinner("Extracting video data... Please wait."):
            # Configure yt-dlp to NOT download, but just fetch the direct URL
            ydl_opts = {
                'format': 'best',
                'quiet': True,
                'noplaylist': True
            }
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=False)
                    
                    # Create our API-style JSON response
                    api_response = {
                        "success": True,
                        "title": info.get('title', 'Unknown Title'),
                        "duration_seconds": info.get('duration', 0),
                        "thumbnail": info.get('thumbnail', ''),
                        "download_url": info.get('url', '')
                    }
                    
                    # 1. Display as JSON (API format)
                    st.subheader("JSON Output (API Format):")
                    st.json(api_response)
                    
                    # 2. Provide a clickable Download Button
                    st.subheader("Direct Download:")
                    st.markdown(f"[**➡️ Right-Click and 'Save Link As' to Download MP4**]({api_response['download_url']})", unsafe_allow_html=True)
                    
                    # 3. Provide the raw text link to copy easily
                    st.text_input("Raw MP4 Link (Copy this):", api_response['download_url'])

            except Exception as e:
                # If there's an error (e.g., age restricted, invalid link)
                st.error("Failed to extract video.")
                st.json({
                    "success": False,
                    "error": str(e)
                })
    else:
        st.warning("Please enter a valid YouTube URL.")
