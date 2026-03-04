import streamlit as st
import yt_dlp
import os
import tempfile
import re
from pathlib import Path

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="YT Downloader",
    page_icon="▶️",
    layout="centered",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Syne', sans-serif;
}

/* Dark background */
.stApp {
    background: #0a0a0f;
    color: #e8e8e8;
}

/* Hide default Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }

/* Hero title */
.hero-title {
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    font-size: 3.2rem;
    line-height: 1.1;
    letter-spacing: -2px;
    background: linear-gradient(135deg, #ff4d4d 0%, #ff9a3c 50%, #ffe066 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.2rem;
}

.hero-sub {
    font-family: 'Space Mono', monospace;
    font-size: 0.78rem;
    color: #555;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-bottom: 2.5rem;
}

/* Card containers */
.card {
    background: #12121a;
    border: 1px solid #1e1e2e;
    border-radius: 16px;
    padding: 1.5rem;
    margin: 1rem 0;
}

/* Input styling */
.stTextInput > div > div > input {
    background: #0f0f18 !important;
    border: 1.5px solid #2a2a3e !important;
    border-radius: 10px !important;
    color: #e8e8e8 !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.85rem !important;
    padding: 0.75rem 1rem !important;
    transition: border-color 0.2s;
}
.stTextInput > div > div > input:focus {
    border-color: #ff4d4d !important;
    box-shadow: 0 0 0 2px rgba(255,77,77,0.15) !important;
}

/* Select box */
.stSelectbox > div > div {
    background: #0f0f18 !important;
    border: 1.5px solid #2a2a3e !important;
    border-radius: 10px !important;
    color: #e8e8e8 !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #ff4d4d, #ff7a3c) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    padding: 0.65rem 2rem !important;
    transition: opacity 0.2s, transform 0.1s !important;
    width: 100%;
}
.stButton > button:hover {
    opacity: 0.88 !important;
    transform: translateY(-1px) !important;
}

/* Download button */
.stDownloadButton > button {
    background: linear-gradient(135deg, #22c55e, #16a34a) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    padding: 0.65rem 2rem !important;
    width: 100%;
}

/* Video info */
.video-title {
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    font-size: 1.1rem;
    color: #e8e8e8;
    margin: 0.5rem 0 0.2rem 0;
}

.video-meta {
    font-family: 'Space Mono', monospace;
    font-size: 0.72rem;
    color: #555;
    margin: 0;
}

.badge {
    display: inline-block;
    background: #1e1e2e;
    border: 1px solid #2a2a3e;
    border-radius: 6px;
    padding: 2px 10px;
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    color: #888;
    margin-right: 6px;
}

/* Divider */
.divider {
    border: none;
    border-top: 1px solid #1e1e2e;
    margin: 1.5rem 0;
}

/* Format tag */
.fmt-mp4  { color: #ff7a3c; }
.fmt-mp3  { color: #a78bfa; }
.fmt-webm { color: #38bdf8; }

/* Progress / spinner override */
.stSpinner > div {
    border-top-color: #ff4d4d !important;
}

/* Alerts */
.stAlert {
    border-radius: 10px !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.8rem !important;
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_valid_youtube_url(url: str) -> bool:
    pattern = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"
    return bool(re.match(pattern, url.strip()))


def fmt_duration(seconds: int) -> str:
    if not seconds:
        return "—"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_views(n) -> str:
    if not n:
        return "—"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M views"
    if n >= 1_000:
        return f"{n/1_000:.1f}K views"
    return f"{n} views"


@st.cache_data(show_spinner=False)
def fetch_info(url: str):
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def build_format_options(info: dict) -> dict:
    """Return a dict of label → yt-dlp format string."""
    options = {}

    # MP3 audio
    options["🎵  MP3 Audio (best)"] = "bestaudio[ext=m4a]/bestaudio/best"

    # Video + audio combos
    for height in [1080, 720, 480, 360, 240]:
        label = f"🎬  MP4 {height}p"
        fmt   = f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}][ext=mp4]/best[height<={height}]"
        options[label] = fmt

    return options


def download_video(url: str, fmt_str: str, is_audio: bool) -> tuple[bytes, str]:
    """Download and return (bytes, filename)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_template = os.path.join(tmpdir, "%(title)s.%(ext)s")

        postprocessors = []
        if is_audio:
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            })

        ydl_opts = {
            "format": fmt_str,
            "outtmpl": out_template,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": postprocessors,
            "merge_output_format": "mp4" if not is_audio else None,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        files = list(Path(tmpdir).iterdir())
        if not files:
            raise FileNotFoundError("Download produced no output file.")

        out_file = files[0]
        data = out_file.read_bytes()
        return data, out_file.name


# ── UI ────────────────────────────────────────────────────────────────────────

st.markdown('<div class="hero-title">YT Downloader</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Free · No login · No limits</div>', unsafe_allow_html=True)

# URL input
url = st.text_input(
    "YouTube URL",
    placeholder="https://youtube.com/watch?v=...",
    label_visibility="collapsed",
)

col_fetch, _ = st.columns([1, 2])
with col_fetch:
    fetch_btn = st.button("🔍  Fetch Video Info")

# ── Fetch info ────────────────────────────────────────────────────────────────
if fetch_btn:
    if not url:
        st.error("Please paste a YouTube URL first.")
    elif not is_valid_youtube_url(url):
        st.error("That doesn't look like a valid YouTube URL.")
    else:
        with st.spinner("Fetching video info…"):
            try:
                info = fetch_info(url)
                st.session_state["info"] = info
                st.session_state["url"]  = url
            except Exception as e:
                st.error(f"Could not fetch video: {e}")

# ── Show info + download ──────────────────────────────────────────────────────
if "info" in st.session_state:
    info = st.session_state["info"]
    url  = st.session_state["url"]

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # Thumbnail + metadata
    thumb = info.get("thumbnail")
    if thumb:
        st.image(thumb, use_container_width=True)

    st.markdown(f'<div class="video-title">{info.get("title","Unknown title")}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="video-meta">'
        f'<span class="badge">⏱ {fmt_duration(info.get("duration"))}</span>'
        f'<span class="badge">👁 {fmt_views(info.get("view_count"))}</span>'
        f'<span class="badge">📺 {info.get("uploader","—")}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # Format selector
    format_options = build_format_options(info)
    chosen_label = st.selectbox(
        "Select format & quality",
        list(format_options.keys()),
        index=1,  # default 1080p
    )
    fmt_str  = format_options[chosen_label]
    is_audio = "MP3" in chosen_label

    # Download button
    if st.button("⬇️  Download"):
        with st.spinner("Downloading… this may take a moment"):
            try:
                file_bytes, filename = download_video(url, fmt_str, is_audio)
                ext  = "mp3" if is_audio else "mp4"
                mime = "audio/mpeg" if is_audio else "video/mp4"

                st.success("✅ Ready! Click below to save your file.")
                st.download_button(
                    label=f"💾  Save  {filename[:60]}",
                    data=file_bytes,
                    file_name=filename,
                    mime=mime,
                )
            except Exception as e:
                st.error(f"Download failed: {e}")
                st.info("Tip: Some videos are geo-restricted or age-gated and cannot be downloaded.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown('<hr class="divider">', unsafe_allow_html=True)
st.markdown(
    '<p style="font-family:\'Space Mono\',monospace;font-size:0.65rem;color:#333;text-align:center;">'
    'Powered by yt-dlp · For personal/educational use only · Respect creators & YouTube ToS'
    '</p>',
    unsafe_allow_html=True,
)
