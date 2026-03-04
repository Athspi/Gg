import streamlit as st
import yt_dlp
import os
import tempfile
import re
from pathlib import Path

# ─── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="YT Vault",
    page_icon="⬇️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap');

:root {
    --bg: #0a0a0f;
    --surface: #12121a;
    --border: #1e1e2e;
    --accent: #ff3f3f;
    --accent2: #ff8c42;
    --text: #f0f0f0;
    --muted: #6b6b80;
    --success: #00e5a0;
}

* { box-sizing: border-box; }

html, body, [class*="css"] {
    font-family: 'Syne', sans-serif;
    background-color: var(--bg) !important;
    color: var(--text) !important;
}

.stApp { background: var(--bg) !important; }

/* Hide Streamlit default elements */
#MainMenu, footer, header { visibility: hidden; }

/* Hero */
.hero {
    text-align: center;
    padding: 3rem 1rem 2rem;
}
.hero-title {
    font-size: 4rem;
    font-weight: 800;
    letter-spacing: -2px;
    background: linear-gradient(135deg, #ff3f3f 0%, #ff8c42 50%, #ffd700 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0;
    line-height: 1;
}
.hero-sub {
    font-family: 'Space Mono', monospace;
    font-size: 0.8rem;
    color: var(--muted);
    letter-spacing: 3px;
    margin-top: 0.5rem;
    text-transform: uppercase;
}
.divider {
    width: 60px;
    height: 3px;
    background: linear-gradient(90deg, #ff3f3f, #ff8c42);
    margin: 1.5rem auto;
    border-radius: 2px;
}

/* Input area */
.stTextInput > div > div > input {
    background: var(--surface) !important;
    border: 2px solid var(--border) !important;
    border-radius: 12px !important;
    color: var(--text) !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.85rem !important;
    padding: 0.9rem 1.2rem !important;
    transition: border-color 0.2s;
}
.stTextInput > div > div > input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(255,63,63,0.15) !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #ff3f3f, #ff8c42) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    padding: 0.8rem 2.5rem !important;
    width: 100% !important;
    letter-spacing: 0.5px !important;
    transition: all 0.2s !important;
    cursor: pointer !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(255,63,63,0.35) !important;
}
.stButton > button:active {
    transform: translateY(0) !important;
}

/* Download button special */
.stDownloadButton > button {
    background: linear-gradient(135deg, #00e5a0, #00bcd4) !important;
    color: #0a0a0f !important;
    border: none !important;
    border-radius: 12px !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 800 !important;
    font-size: 1rem !important;
    padding: 0.8rem 2rem !important;
    width: 100% !important;
    letter-spacing: 0.5px !important;
    transition: all 0.2s !important;
}
.stDownloadButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(0,229,160,0.35) !important;
}

/* Video info card */
.video-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 1.5rem;
    margin: 1.5rem 0;
    position: relative;
    overflow: hidden;
}
.video-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #ff3f3f, #ff8c42, #ffd700);
}
.video-title {
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 0.8rem;
    line-height: 1.4;
    color: var(--text);
}
.video-meta {
    font-family: 'Space Mono', monospace;
    font-size: 0.75rem;
    color: var(--muted);
    display: flex;
    gap: 1.5rem;
    flex-wrap: wrap;
    margin-top: 0.5rem;
}
.meta-item {
    display: flex;
    align-items: center;
    gap: 0.4rem;
}
.badge {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    font-weight: 700;
    background: rgba(255,63,63,0.15);
    color: #ff6b6b;
    border: 1px solid rgba(255,63,63,0.3);
    margin-right: 0.4rem;
}

/* Select box */
.stSelectbox > div > div {
    background: var(--surface) !important;
    border: 2px solid var(--border) !important;
    border-radius: 12px !important;
    color: var(--text) !important;
}

/* Radio */
.stRadio > div {
    gap: 1rem;
}

/* Alert / status */
.status-box {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    font-family: 'Space Mono', monospace;
    font-size: 0.8rem;
    color: var(--muted);
    margin: 1rem 0;
}
.status-ok { 
    border-color: rgba(0,229,160,0.4) !important;
    color: var(--success) !important;
    background: rgba(0,229,160,0.05) !important;
}
.status-err {
    border-color: rgba(255,63,63,0.4) !important;
    color: #ff6b6b !important;
    background: rgba(255,63,63,0.05) !important;
}

/* Spinner */
.stSpinner > div {
    border-top-color: var(--accent) !important;
}

/* Section label */
.section-label {
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.5rem;
}

/* Progress */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #ff3f3f, #ff8c42) !important;
}

/* Thumbnail */
.thumb-container {
    border-radius: 10px;
    overflow: hidden;
    border: 2px solid var(--border);
}
</style>
""", unsafe_allow_html=True)


# ─── Hero Header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <h1 class="hero-title">YT VAULT</h1>
    <p class="hero-sub">⚡ YouTube Video & Audio Downloader</p>
    <div class="divider"></div>
</div>
""", unsafe_allow_html=True)


# ─── Helper Functions ───────────────────────────────────────────────────────────
def format_duration(seconds):
    if not seconds:
        return "Unknown"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def format_views(views):
    if not views:
        return "Unknown"
    if views >= 1_000_000:
        return f"{views/1_000_000:.1f}M"
    if views >= 1_000:
        return f"{views/1_000:.1f}K"
    return str(views)

def is_valid_youtube_url(url):
    patterns = [
        r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)',
    ]
    return any(re.search(p, url) for p in patterns)

def get_video_info(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info

def get_format_options(info):
    formats = info.get('formats', [])
    video_options = {}
    audio_options = {}

    for f in formats:
        # Video formats
        if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
            height = f.get('height')
            if height:
                label = f"{height}p"
                if label not in video_options:
                    video_options[label] = f['format_id']

        # Audio only formats
        if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
            abr = f.get('abr')
            if abr:
                label = f"{int(abr)}kbps"
                if label not in audio_options:
                    audio_options[label] = f['format_id']

    # Sort
    def height_key(s):
        try: return int(s.replace('p',''))
        except: return 0

    def abr_key(s):
        try: return int(s.replace('kbps',''))
        except: return 0

    sorted_video = dict(sorted(video_options.items(), key=lambda x: height_key(x[0]), reverse=True))
    sorted_audio = dict(sorted(audio_options.items(), key=lambda x: abr_key(x[0]), reverse=True))
    return sorted_video, sorted_audio

def download_video(url, format_id, output_dir, mode='video'):
    output_template = os.path.join(output_dir, '%(title)s.%(ext)s')

    if mode == 'audio':
        ydl_opts = {
            'format': f'{format_id}',
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
    else:
        ydl_opts = {
            'format': f'{format_id}+bestaudio/best[height<=1080]',
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4',
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # Find the downloaded file
    files = list(Path(output_dir).glob('*'))
    if files:
        return max(files, key=os.path.getctime)
    return None


# ─── Main UI ───────────────────────────────────────────────────────────────────

# URL Input
st.markdown('<div class="section-label">🔗 Paste YouTube URL</div>', unsafe_allow_html=True)
url = st.text_input(
    label="url_input",
    placeholder="https://www.youtube.com/watch?v=...",
    label_visibility="collapsed"
)

fetch_btn = st.button("🔍 Fetch Video Info", use_container_width=True)

# Session state
if 'video_info' not in st.session_state:
    st.session_state.video_info = None
if 'video_formats' not in st.session_state:
    st.session_state.video_formats = {}
if 'audio_formats' not in st.session_state:
    st.session_state.audio_formats = {}

# Fetch video info
if fetch_btn:
    if not url:
        st.markdown('<div class="status-box status-err">⚠️ Please enter a YouTube URL first.</div>', unsafe_allow_html=True)
    elif not is_valid_youtube_url(url):
        st.markdown('<div class="status-box status-err">⚠️ Invalid YouTube URL. Please check and try again.</div>', unsafe_allow_html=True)
    else:
        with st.spinner("Fetching video info..."):
            try:
                info = get_video_info(url)
                st.session_state.video_info = info
                vid_fmts, aud_fmts = get_format_options(info)
                st.session_state.video_formats = vid_fmts
                st.session_state.audio_formats = aud_fmts
                st.session_state.download_file = None
            except Exception as e:
                st.markdown(f'<div class="status-box status-err">❌ Error: {str(e)}</div>', unsafe_allow_html=True)
                st.session_state.video_info = None

# Show video info
if st.session_state.video_info:
    info = st.session_state.video_info

    # Thumbnail + Info
    col1, col2 = st.columns([1, 2])
    with col1:
        thumb = info.get('thumbnail') or (info.get('thumbnails') or [{}])[-1].get('url', '')
        if thumb:
            st.markdown('<div class="thumb-container">', unsafe_allow_html=True)
            st.image(thumb, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        title = info.get('title', 'Unknown Title')
        channel = info.get('uploader', 'Unknown Channel')
        duration = format_duration(info.get('duration'))
        views = format_views(info.get('view_count'))
        upload_date = info.get('upload_date', '')
        if upload_date:
            upload_date = f"{upload_date[6:8]}/{upload_date[4:6]}/{upload_date[:4]}"

        st.markdown(f"""
        <div class="video-card">
            <div class="video-title">{title}</div>
            <div class="video-meta">
                <div class="meta-item">📺 {channel}</div>
                <div class="meta-item">⏱️ {duration}</div>
                <div class="meta-item">👁️ {views} views</div>
                <div class="meta-item">📅 {upload_date}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Mode selection
    st.markdown('<div class="section-label">🎛️ Download Mode</div>', unsafe_allow_html=True)
    mode = st.radio(
        "Mode",
        options=["🎬 Video (MP4)", "🎵 Audio Only (MP3)"],
        horizontal=True,
        label_visibility="collapsed"
    )

    # Format selection
    if "Video" in mode:
        vid_fmts = st.session_state.video_formats
        if vid_fmts:
            st.markdown('<div class="section-label">📐 Video Quality</div>', unsafe_allow_html=True)
            quality = st.selectbox(
                "Quality",
                options=list(vid_fmts.keys()),
                label_visibility="collapsed"
            )
            selected_format_id = vid_fmts[quality]
            dl_mode = 'video'
            file_ext = 'mp4'
        else:
            st.markdown('<div class="status-box status-err">No video formats found for this URL.</div>', unsafe_allow_html=True)
            selected_format_id = None
    else:
        aud_fmts = st.session_state.audio_formats
        if aud_fmts:
            st.markdown('<div class="section-label">🔊 Audio Quality</div>', unsafe_allow_html=True)
            quality = st.selectbox(
                "Audio Quality",
                options=list(aud_fmts.keys()),
                label_visibility="collapsed"
            )
            selected_format_id = aud_fmts[quality]
            dl_mode = 'audio'
            file_ext = 'mp3'
        else:
            # fallback to bestaudio
            selected_format_id = 'bestaudio'
            dl_mode = 'audio'
            file_ext = 'mp3'
            quality = "Best"

    st.markdown("")

    # Download button
    download_btn = st.button("⚡ Download Now", use_container_width=True)

    if download_btn and selected_format_id:
        with st.spinner("Downloading... please wait ⏳"):
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    out_file = download_video(url, selected_format_id, tmpdir, mode=dl_mode)
                    if out_file and out_file.exists():
                        file_bytes = out_file.read_bytes()
                        clean_title = re.sub(r'[^\w\s-]', '', info.get('title', 'video'))[:50].strip()
                        safe_name = f"{clean_title}.{file_ext}"

                        st.markdown('<div class="status-box status-ok">✅ Download ready! Click below to save.</div>', unsafe_allow_html=True)
                        st.download_button(
                            label=f"💾 Save {safe_name}",
                            data=file_bytes,
                            file_name=safe_name,
                            mime="video/mp4" if dl_mode == 'video' else "audio/mpeg",
                            use_container_width=True
                        )
                    else:
                        st.markdown('<div class="status-box status-err">❌ Download failed. Try a different quality.</div>', unsafe_allow_html=True)
            except Exception as e:
                st.markdown(f'<div class="status-box status-err">❌ Error during download: {str(e)}</div>', unsafe_allow_html=True)

# ─── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding: 3rem 0 1rem; font-family: 'Space Mono', monospace; 
     font-size: 0.7rem; color: #3a3a4a; letter-spacing: 1px;">
    YT VAULT — FOR PERSONAL & EDUCATIONAL USE ONLY<br>
    <span style="color:#ff3f3f;">⚠️</span> Respect YouTube ToS & Content Creator Rights
</div>
""", unsafe_allow_html=True)
