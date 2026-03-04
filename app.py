import streamlit as st
from pytube import YouTube, Playlist
import os
import tempfile
import re
from pathlib import Path
import time

# Page configuration
st.set_page_config(
    page_title="YouTube Downloader",
    page_icon="🎥",
    layout="centered"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .stButton > button {
        width: 100%;
        background-color: #FF0000;
        color: white;
        font-weight: bold;
    }
    .stTextInput > div > div > input {
        border-radius: 10px;
    }
    .success-message {
        padding: 1rem;
        border-radius: 10px;
        background-color: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
    }
    .error-message {
        padding: 1rem;
        border-radius: 10px;
        background-color: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
    }
</style>
""", unsafe_allow_html=True)

# Title and description
st.title("🎥 YouTube Video Downloader")
st.markdown("Download YouTube videos and playlists easily!")

# Sidebar for settings
with st.sidebar:
    st.header("⚙️ Settings")
    
    # Download options
    download_format = st.selectbox(
        "Download Format",
        ["MP4 (Video)", "MP3 (Audio only)"]
    )
    
    video_quality = st.selectbox(
        "Video Quality (for MP4)",
        ["Highest", "720p", "480p", "360p"]
    )
    
    st.markdown("---")
    st.markdown("### ℹ️ How to use")
    st.markdown("""
    1. Paste a YouTube URL (video or playlist)
    2. Click download
    3. Wait for processing
    4. Save your file
    """)
    
    st.markdown("---")
    st.markdown("### ⚠️ Note")
    st.markdown("""
    - Downloads may take a few moments
    - Large playlists process one video at a time
    - Files are temporarily stored and deleted after download
    """)

def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    # Replace invalid characters with underscore
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
    # Replace spaces with underscores
    filename = filename.replace(" ", "_")
    # Limit filename length
    if len(filename) > 100:
        filename = filename[:100]
    return filename

def get_video_info(url):
    """Get video information"""
    try:
        yt = YouTube(url)
        return {
            'title': yt.title,
            'thumbnail': yt.thumbnail_url,
            'length': yt.length,
            'views': yt.views,
            'author': yt.author
        }
    except Exception as e:
        st.error(f"Error fetching video info: {str(e)}")
        return None

def download_video(url, download_format, quality):
    """Download a single video"""
    try:
        yt = YouTube(url, on_progress_callback=progress_function)
        
        # Create progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Create temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            if download_format == "MP3 (Audio only)":
                # Download audio
                stream = yt.streams.filter(only_audio=True).first()
                filename = sanitize_filename(yt.title) + ".mp3"
                filepath = stream.download(output_path=temp_dir, filename=filename)
                status_text.text("Converting to MP3...")
            else:
                # Download video based on quality
                if quality == "Highest":
                    stream = yt.streams.get_highest_resolution()
                else:
                    stream = yt.streams.filter(res=quality, progressive=True).first()
                    if not stream:
                        stream = yt.streams.get_highest_resolution()
                        st.warning(f"Quality {quality} not available. Downloading highest quality instead.")
                
                filename = sanitize_filename(yt.title) + ".mp4"
                filepath = stream.download(output_path=temp_dir, filename=filename)
            
            progress_bar.progress(100)
            status_text.text("Download complete!")
            time.sleep(1)
            
            # Read file for download
            with open(filepath, 'rb') as f:
                video_bytes = f.read()
            
            return video_bytes, filename
            
    except Exception as e:
        st.error(f"Download failed: {str(e)}")
        return None, None

def progress_function(stream, chunk, bytes_remaining):
    """Callback function for download progress"""
    file_size = stream.filesize
    bytes_downloaded = file_size - bytes_remaining
    percentage = int((bytes_downloaded / file_size) * 100)
    
    # Update progress bar
    if 'progress_bar' in st.session_state:
        st.session_state.progress_bar.progress(percentage / 100)
    if 'status_text' in st.session_state:
        st.session_state.status_text.text(f"Downloading: {percentage}%")

def download_playlist(url, download_format, quality, max_videos):
    """Download a playlist"""
    try:
        playlist = Playlist(url)
        st.info(f"Playlist: {playlist.title} - {len(playlist.video_urls)} videos found")
        
        downloaded_files = []
        
        # Limit number of videos
        video_urls = list(playlist.video_urls)[:max_videos]
        
        for idx, video_url in enumerate(video_urls, 1):
            st.markdown(f"**Processing video {idx}/{len(video_urls)}**")
            
            video_bytes, filename = download_video(video_url, download_format, quality)
            
            if video_bytes and filename:
                downloaded_files.append((video_bytes, filename))
                st.success(f"✓ Downloaded: {filename}")
            
            if idx < len(video_urls):
                st.markdown("---")
        
        return downloaded_files
        
    except Exception as e:
        st.error(f"Playlist download failed: {str(e)}")
        return []

# Main app interface
download_type = st.radio(
    "Select download type:",
    ["Single Video", "Playlist"],
    horizontal=True
)

url = st.text_input(
    "Enter YouTube URL:",
    placeholder="https://www.youtube.com/watch?v=..."
)

if download_type == "Playlist":
    col1, col2 = st.columns(2)
    with col1:
        max_videos = st.number_input(
            "Max videos to download",
            min_value=1,
            max_value=50,
            value=10
        )
    with col2:
        st.markdown("### ")
        st.markdown("*Limited to 50 videos*")

# Download button
if st.button("🚀 Download", type="primary"):
    if not url:
        st.error("Please enter a YouTube URL")
    else:
        # Initialize session state for progress tracking
        st.session_state.progress_bar = st.progress(0)
        st.session_state.status_text = st.empty()
        
        with st.spinner("Processing..."):
            if download_type == "Single Video":
                # Show video info
                info = get_video_info(url)
                if info:
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        st.image(info['thumbnail'], use_container_width=True)
                    with col2:
                        st.markdown(f"**Title:** {info['title']}")
                        st.markdown(f"**Author:** {info['author']}")
                        st.markdown(f"**Length:** {info['length']} seconds")
                        st.markdown(f"**Views:** {info['views']:,}")
                
                # Download video
                video_bytes, filename = download_video(url, download_format, video_quality)
                
                if video_bytes and filename:
                    st.session_state.progress_bar.empty()
                    st.session_state.status_text.empty()
                    
                    st.markdown('<div class="success-message">✅ Download ready!</div>', 
                              unsafe_allow_html=True)
                    
                    # Create download button
                    st.download_button(
                        label="📥 Click here to save file",
                        data=video_bytes,
                        file_name=filename,
                        mime="application/octet-stream"
                    )
            
            else:  # Playlist
                downloaded = download_playlist(url, download_format, video_quality, max_videos)
                
                if downloaded:
                    st.success(f"✅ Downloaded {len(downloaded)} videos!")
                    
                    # Create download buttons for each file
                    for video_bytes, filename in downloaded:
                        st.download_button(
                            label=f"📥 Save {filename}",
                            data=video_bytes,
                            file_name=filename,
                            mime="application/octet-stream",
                            key=filename
                        )

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        Made with ❤️ using Streamlit and pytube<br>
        For educational purposes only. Please respect copyright laws.
    </div>
    """,
    unsafe_allow_html=True
)
