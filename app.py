import streamlit as st
import yt_dlp
import os
import tempfile

# Set up the webpage
st.set_page_config(page_title="Free YouTube Downloader", page_icon="🎥")
st.title("🎥 Free YouTube Downloader")
st.write("Paste a YouTube link below to download the video or audio.")

# User Inputs
url = st.text_input("Enter YouTube Video URL:")
format_option = st.radio("Select Format:", ["Video (MP4)", "Audio (MP3)"])

if st.button("Fetch Download Link"):
    if not url:
        st.warning("Please enter a valid YouTube URL.")
    else:
        with st.spinner("Downloading from YouTube... Please wait."):
            try:
                # Create a temporary folder on the Streamlit server
                temp_dir = tempfile.mkdtemp()
                
                # Configure yt-dlp settings
                ydl_opts = {
                    'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                    'quiet': True,
                    'no_warnings': True,
                }
                
                # Set formats based on user choice
                if format_option == "Video (MP4)":
                    # Download best video and best audio, then merge to MP4
                    ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                else:
                    # Download best audio and convert to MP3
                    ydl_opts['format'] = 'bestaudio/best'
                    ydl_opts['postprocessors'] =[{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }]

                # Start the download process
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=True)
                    file_path = ydl.prepare_filename(info_dict)
                    
                    # Adjust file extension if MP3 was selected
                    if format_option == "Audio (MP3)":
                        file_path = os.path.splitext(file_path)[0] + '.mp3'

                    file_name = os.path.basename(file_path)

                    # Read the downloaded file into memory for the user to download
                    with open(file_path, "rb") as file:
                        file_bytes = file.read()
                        
                    st.success(f"✅ Successfully processed: {info_dict.get('title', 'Video')}")
                    
                    # Display the final Download Button
                    st.download_button(
                        label="⬇️ Download File to Your Device",
                        data=file_bytes,
                        file_name=file_name,
                        mime="video/mp4" if format_option == "Video (MP4)" else "audio/mpeg"
                    )
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.info("Note: Because this is hosted on a cloud server, YouTube's anti-bot systems might occasionally block the download. Try another video if this happens.")
