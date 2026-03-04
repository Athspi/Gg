import streamlit as st
import yt_dlp
import os

st.set_page_config(page_title="YouTube Downloader Pro", layout="centered")

st.title("📥 YouTube Downloader PRO")
st.write("Download videos in different qualities or extract audio")

url = st.text_input("🔗 Enter YouTube URL")

quality = st.selectbox(
    "🎬 Select Quality",
    ["Best", "720p", "480p", "360p", "Audio (MP3)"]
)

# 🔍 Get video info
def get_video_info(url):
    ydl_opts = {'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

# 📥 Download function
def download_video(url, quality):
    output_path = "downloads"
    os.makedirs(output_path, exist_ok=True)

    if quality == "Audio (MP3)":
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{output_path}/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        }
    else:
        format_map = {
            "Best": "best",
            "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
            "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
        }

        ydl_opts = {
            'format': format_map[quality],
            'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

        if quality == "Audio (MP3)":
            filename = filename.rsplit(".", 1)[0] + ".mp3"

    return filename


# 🎯 Show info
if url:
    try:
        info = get_video_info(url)
        st.image(info.get("thumbnail"))
        st.subheader(info.get("title"))
        st.caption(f"👁 {info.get('view_count')} views")
    except:
        st.warning("Could not fetch video info")

# 🚀 Download button
if st.button("🚀 Download"):
    if url:
        try:
            with st.spinner("Downloading... ⏳"):
                file_path = download_video(url, quality)

            st.success("✅ Download complete!")

            with open(file_path, "rb") as f:
                st.download_button(
                    label="📥 Download File",
                    data=f,
                    file_name=os.path.basename(file_path)
                )

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
    else:
        st.warning("⚠️ Enter a URL first")
