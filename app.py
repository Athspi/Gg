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

html, body, [class*="css"] { font-family: 'Syne', sans-serif; }

.stApp { background: #0a0a0f; color: #e8e8e8; }

#MainMenu, footer, header { visibility: hidden; }

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

.stTextInput > div > div > input {
    background: #0f0f18 !important;
    border: 1.5px solid #2a2a3e !important;
    border-radius: 10px !important;
    color: #e8e8e8 !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.85rem !important;
    padding: 0.75rem 1rem !important;
}
.stTextInput > div > div > input:focus {
    border-color: #ff4d4d !important;
    box-shadow: 0 0 0 2px rgba(255,77,77,0.15) !important;
}

.stSelectbox > div > div {
    background: #0f0f18 !important;
    border: 1.5px solid #2a2a3e !important;
    border-radius: 10px !important;
    color: #e8e8e8 !important;
}

.stButton > button {
    background: linear-gradient(135deg, #ff4d4d, #ff7a3c) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    padding: 0.65rem 2rem !important;
    width: 100%;
}
.stButton > button:hover { opacity: 0.88 !important; transform: translateY(-1px) !important; }

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

.video-title {
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    font-size: 1.1rem;
    color: #e8e8e8;
    margin: 0.5rem 0 0.2rem 0;
}

.video-meta { font-family: 'Space Mono', monospace; font-size: 0.72rem; color: #555; }

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

.divider { border: none; border-top: 1px solid #1e1e2e; margin: 1.5rem 0; }

.stAlert { border-radius: 10px !important; font-family: 'Space Mono', monospace !important; font-size: 0.8rem !important; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_valid_youtube_url(url: str) -> bool:
    return bool(re.match(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+", url.strip()))


def fmt_duration(seconds) -> str:
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


# ── yt-dlp base options — fixes HTTP 403 Forbidden ────────────────────────────
BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    # Spoof Chrome browser headers so YouTube doesn't block with 403
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.youtube.com/",
    },
    # Android + web player clients are less throttled than the default
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "web"],
        }
    },
    "retries": 5,
    "fragment_retries": 5,
    "socket_timeout": 30,
}


@st.cache_data(show_spinner=False, ttl=300)
def fetch_info(url: str):
    opts = {**BASE_OPTS, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


FORMAT_MAP = {
    "🎵  MP3 Audio (best quality)":   ("bestaudio/best",                                               True),
    "🎬  MP4 1080p":                   ("bestvideo[height<=1080][ext=mp4]+bestaudio/best[height<=1080]", False),
    "🎬  MP4 720p":                    ("bestvideo[height<=720][ext=mp4]+bestaudio/best[height<=720]",   False),
    "🎬  MP4 480p":                    ("bestvideo[height<=480][ext=mp4]+bestaudio/best[height<=480]",   False),
    "🎬  MP4 360p":                    ("bestvideo[height<=360][ext=mp4]+bestaudio/best[height<=360]",   False),
    "🎬  MP4 240p (smallest)":         ("bestvideo[height<=240][ext=mp4]+bestaudio/best[height<=240]",   False),
}


def download_video(url: str, fmt_str: str, is_audio: bool) -> tuple[bytes, str]:
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
            **BASE_OPTS,
            "format": fmt_str,
            "outtmpl": out_template,
            "postprocessors": postprocessors,
            "merge_output_format": None if is_audio else "mp4",
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        files = list(Path(tmpdir).iterdir())
        if not files:
            raise FileNotFoundError("Download produced no output file.")

        out_file = max(files, key=lambda f: f.stat().st_size)
        return out_file.read_bytes(), out_file.name


# ── UI ────────────────────────────────────────────────────────────────────────

st.markdown('<div class="hero-title">YT Downloader</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Free · No login · No limits</div>', unsafe_allow_html=True)

url = st.text_input(
    "YouTube URL",
    placeholder="https://youtube.com/watch?v=...",
    label_visibility="collapsed",
)

col_fetch, _ = st.columns([1, 2])
with col_fetch:
    fetch_btn = st.button("🔍  Fetch Video Info")

# ── Fetch info ─────────────────────────────────────────────────────────────────
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
                # Clear any previous download data
                st.session_state.pop("dl_data",     None)
                st.session_state.pop("dl_filename", None)
                st.session_state.pop("dl_audio",    None)
            except Exception as e:
                st.error(f"Could not fetch video: {e}")

# ── Show info + download ───────────────────────────────────────────────────────
if "info" in st.session_state:
    info = st.session_state["info"]
    url  = st.session_state["url"]

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ✅ FIXED: width='stretch' instead of use_container_width=True
    thumb = info.get("thumbnail")
    if thumb:
        st.image(thumb, width="stretch")

    st.markdown(
        f'<div class="video-title">{info.get("title","Unknown title")}</div>',
        unsafe_allow_html=True,
    )
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
    chosen_label = st.selectbox(
        "Select format & quality",
        list(FORMAT_MAP.keys()),
        index=1,
    )
    fmt_str, is_audio = FORMAT_MAP[chosen_label]

    # Trigger download
    if st.button("⬇️  Download Now"):
        with st.spinner("Downloading… please wait"):
            try:
                file_bytes, filename = download_video(url, fmt_str, is_audio)
                st.session_state["dl_data"]     = file_bytes
                st.session_state["dl_filename"] = filename
                st.session_state["dl_audio"]    = is_audio
            except Exception as e:
                err = str(e)
                st.error(f"Download failed: {err}")
                if "403" in err:
                    st.info(
                        "💡 **Try these fixes:**\n"
                        "- Switch to a different quality (e.g. 720p instead of 1080p)\n"
                        "- Some videos are region-locked or DRM-protected\n"
                        "- Wait a minute then retry"
                    )

    # Show save button after successful download
    if "dl_data" in st.session_state:
        fname  = st.session_state["dl_filename"]
        is_aud = st.session_state["dl_audio"]
        mime   = "audio/mpeg" if is_aud else "video/mp4"

        st.success("✅ Ready! Click below to save your file.")
        st.download_button(
            label=f"💾  Save  {fname[:55]}{'…' if len(fname) > 55 else ''}",
            data=st.session_state["dl_data"],
            file_name=fname,
            mime=mime,
        )

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown('<hr class="divider">', unsafe_allow_html=True)
st.markdown(
    '<p style="font-family:\'Space Mono\',monospace;font-size:0.65rem;'
    'color:#333;text-align:center;">'
    'Powered by yt-dlp · Personal/educational use only · Respect creators & YouTube ToS'
    '</p>',
    unsafe_allow_html=True,
)
