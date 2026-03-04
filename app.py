import streamlit as st
import yt_dlp
import os
import tempfile
import re
from pathlib import Path

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="YT Downloader",
    page_icon="▶️",
    layout="centered",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Syne', sans-serif; }
.stApp { background: #0a0a0f; color: #e8e8e8; }
#MainMenu, footer, header { visibility: hidden; }
.hero-title {
    font-family: 'Syne', sans-serif; font-weight: 800; font-size: 3rem;
    letter-spacing: -2px;
    background: linear-gradient(135deg, #ff4d4d 0%, #ff9a3c 50%, #ffe066 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; margin-bottom: 0.1rem;
}
.hero-sub {
    font-family: 'Space Mono', monospace; font-size: 0.75rem; color: #444;
    letter-spacing: 3px; text-transform: uppercase; margin-bottom: 2rem;
}
.stTextInput > div > div > input {
    background: #0f0f18 !important; border: 1.5px solid #2a2a3e !important;
    border-radius: 10px !important; color: #e8e8e8 !important;
    font-family: 'Space Mono', monospace !important; font-size: 0.85rem !important;
}
.stTextInput > div > div > input:focus {
    border-color: #ff4d4d !important; box-shadow: 0 0 0 2px rgba(255,77,77,0.15) !important;
}
.stSelectbox > div > div {
    background: #0f0f18 !important; border: 1.5px solid #2a2a3e !important;
    border-radius: 10px !important; color: #e8e8e8 !important;
}
.stButton > button {
    background: linear-gradient(135deg, #ff4d4d, #ff7a3c) !important;
    color: white !important; border: none !important; border-radius: 10px !important;
    font-family: 'Syne', sans-serif !important; font-weight: 700 !important;
    font-size: 0.95rem !important; width: 100%;
}
.stButton > button:hover { opacity: 0.88 !important; }
.stDownloadButton > button {
    background: linear-gradient(135deg, #22c55e, #16a34a) !important;
    color: white !important; border: none !important; border-radius: 10px !important;
    font-family: 'Syne', sans-serif !important; font-weight: 700 !important;
    font-size: 0.95rem !important; width: 100%;
}
.video-title {
    font-family: 'Syne', sans-serif; font-weight: 700; font-size: 1.05rem;
    color: #e8e8e8; margin: 0.5rem 0 0.25rem 0;
}
.badge {
    display: inline-block; background: #1e1e2e; border: 1px solid #2a2a3e;
    border-radius: 6px; padding: 2px 10px; font-family: 'Space Mono', monospace;
    font-size: 0.68rem; color: #777; margin-right: 5px;
}
.divider { border: none; border-top: 1px solid #1a1a2e; margin: 1.5rem 0; }
.fmt-table { font-family: 'Space Mono', monospace; font-size: 0.72rem; color: #666; margin: 0.3rem 0 0.8rem 0; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def is_valid_url(url: str) -> bool:
    return bool(re.match(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+", url.strip()))

def fmt_duration(sec) -> str:
    if not sec: return "—"
    h, r = divmod(int(sec), 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def fmt_views(n) -> str:
    if not n: return "—"
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M views"
    if n >= 1_000:     return f"{n/1_000:.1f}K views"
    return f"{n} views"

def is_bot_error(e: Exception) -> bool:
    s = str(e).lower()
    return any(k in s for k in ("sign in", "bot", "cookies", "confirm your age",
                                 "login required", "not a bot"))


# ── Client configs ────────────────────────────────────────────────────────────
CLIENT_CONFIGS = [
    {
        "extractor_args": {"youtube": {"player_client": ["ios"]}},
        "http_headers": {"User-Agent": "com.google.ios.youtube/19.29.1 (iPhone16,2; U; CPU iOS 17_5_1 like Mac OS X)"},
    },
    {
        "extractor_args": {"youtube": {"player_client": ["web"]}},
        "http_headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"},
    },
    {
        "extractor_args": {"youtube": {"player_client": ["android_embedded"]}},
        "http_headers": {"User-Agent": "com.google.android.youtube/17.36.4(Linux; U; Android 12)"},
    },
    {
        "extractor_args": {"youtube": {"player_client": ["tv_embedded"]}},
        "http_headers": {"User-Agent": "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.0) AppleWebKit/538.1"},
    },
]

COMMON_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "retries": 5,
    "fragment_retries": 5,
    "socket_timeout": 30,
    "nocheckcertificate": True,
}

FORMAT_MAP = {
    "🎵  MP3 Audio":              ("bestaudio/best", True),
    "🎬  Best available video":   ("bestvideo+bestaudio/best", False),
    "🎬  1080p  (or best below)": ("bestvideo[height<=1080]+bestaudio/best[height<=1080]/best", False),
    "🎬  720p  (or best below)":  ("bestvideo[height<=720]+bestaudio/best[height<=720]/best",   False),
    "🎬  480p  (or best below)":  ("bestvideo[height<=480]+bestaudio/best[height<=480]/best",   False),
    "🎬  360p  (or best below)":  ("bestvideo[height<=360]+bestaudio/best[height<=360]/best",   False),
    "🎬  240p  (smallest)":       ("bestvideo[height<=240]+bestaudio/best[height<=240]/best",   False),
}


# ── Core helpers ──────────────────────────────────────────────────────────────

def _build_opts(client_cfg: dict, extra: dict, cookie_path: str | None) -> dict:
    opts = {**COMMON_OPTS, **client_cfg}
    opts.update(extra)
    if cookie_path:
        opts["cookiefile"] = cookie_path
    return opts


def save_cookie_upload(uploaded) -> str | None:
    """Persist uploaded cookies.txt to a temp file for this session."""
    if uploaded is None:
        return None
    # Re-use same temp file unless a new file was uploaded
    if st.session_state.get("_last_cookie_name") != uploaded.name:
        old = st.session_state.pop("cookie_tmp_path", None)
        if old and os.path.exists(old):
            os.unlink(old)
        st.session_state["_last_cookie_name"] = uploaded.name
    if "cookie_tmp_path" not in st.session_state:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="wb")
        tmp.write(uploaded.getvalue())
        tmp.flush()
        st.session_state["cookie_tmp_path"] = tmp.name
    return st.session_state["cookie_tmp_path"]


@st.cache_data(show_spinner=False, ttl=300)
def fetch_info(url: str, cookie_path: str | None) -> dict:
    last_err = None
    for cfg in CLIENT_CONFIGS:
        try:
            opts = _build_opts(cfg, {"skip_download": True}, cookie_path)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    return info
        except Exception as e:
            last_err = e
            if is_bot_error(e):
                break  # cookies required — no point retrying other clients
    raise RuntimeError(str(last_err))


def get_available_formats(info: dict) -> list:
    out, seen = [], set()
    for f in reversed(info.get("formats", [])):
        h     = f.get("height") or 0
        ext   = f.get("ext", "?")
        has_v = f.get("vcodec", "none") not in (None, "none")
        has_a = f.get("acodec", "none") not in (None, "none")
        key   = (h, ext, has_v, has_a)
        if key not in seen:
            seen.add(key)
            out.append({"format_id": f.get("format_id"), "ext": ext, "height": h,
                        "has_video": has_v, "has_audio": has_a,
                        "note": f.get("format_note", ""),
                        "filesize": f.get("filesize") or f.get("filesize_approx") or 0})
    return out


def download_video(url: str, fmt_string: str, is_audio: bool,
                   cookie_path: str | None) -> tuple:
    last_err = None
    for cfg in CLIENT_CONFIGS:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                pp = ([{"key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3", "preferredquality": "192"}]
                      if is_audio else [])
                extra = {
                    "format": fmt_string,
                    "outtmpl": os.path.join(tmpdir, "%(title)s.%(ext)s"),
                    "postprocessors": pp,
                    "merge_output_format": "mp4" if not is_audio else None,
                    "format_sort": ["res", "ext:mp4:m4a:webm", "codec:h264:aac", "size", "br"],
                }
                opts = _build_opts(cfg, extra, cookie_path)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                files = sorted(
                    [f for f in Path(tmpdir).iterdir() if f.is_file()],
                    key=lambda f: f.stat().st_size, reverse=True,
                )
                if files:
                    return files[0].read_bytes(), files[0].name
        except Exception as e:
            last_err = e
            if is_bot_error(e):
                break
            if any(k in str(e).lower() for k in
                   ("403", "http error", "timed out", "not available", "format", "unavailable")):
                continue
            raise
    raise RuntimeError(str(last_err))


# ── UI ─────────────────────────────────────────────────────────────────────────
st.markdown('<div class="hero-title">YT Downloader</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Free · No Login · No Limits</div>', unsafe_allow_html=True)

url_input = st.text_input(
    "url", placeholder="https://youtube.com/watch?v=...", label_visibility="collapsed",
)

# ── Cookie panel ───────────────────────────────────────────────────────────────
with st.expander("🍪  Upload cookies.txt  (only needed if YouTube blocks the request)"):
    st.markdown("""
**How to get your cookies.txt in 30 seconds:**

1. Install [**Get cookies.txt LOCALLY**](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) (Chrome/Edge) or [**cookies.txt**](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/) (Firefox)
2. Open **youtube.com** while logged in to your Google account
3. Click the extension icon → **Export** → save the file
4. Upload it below ↓

> Your cookies are only used for this download session and are never stored.
""")
    cookie_file = st.file_uploader(
        "Drop cookies.txt here", type=["txt"], label_visibility="collapsed",
    )
    if cookie_file:
        st.success("✅ Cookies loaded — bot detection will be bypassed.")

cookie_path = save_cookie_upload(cookie_file if "cookie_file" in dir() and cookie_file else None)

# ── Fetch button ───────────────────────────────────────────────────────────────
c1, _ = st.columns([1, 2])
with c1:
    fetch_btn = st.button("🔍  Fetch Info")

if fetch_btn:
    if not url_input:
        st.error("Paste a YouTube URL above.")
    elif not is_valid_url(url_input):
        st.error("Doesn't look like a valid YouTube URL.")
    else:
        with st.spinner("Fetching video info…"):
            try:
                info = fetch_info(url_input, cookie_path)
                st.session_state.update({
                    "info": info, "url": url_input,
                    "dl_data": None, "dl_filename": None, "dl_audio": None,
                })
            except Exception as e:
                err = str(e)
                st.error(f"Fetch failed: {err}")
                if is_bot_error(Exception(err)):
                    st.warning(
                        "**YouTube triggered a bot / sign-in check.**\n\n"
                        "👉 Open the **🍪 Upload cookies.txt** panel above, "
                        "export your browser cookies from youtube.com, upload the file, then retry."
                    )

# ── Video panel ────────────────────────────────────────────────────────────────
if st.session_state.get("info"):
    info = st.session_state["info"]
    url  = st.session_state["url"]

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    thumb = info.get("thumbnail")
    if thumb:
        st.image(thumb, use_container_width=True)

    st.markdown(
        f'<div class="video-title">{info.get("title", "Unknown title")}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div>'
        f'<span class="badge">⏱ {fmt_duration(info.get("duration"))}</span>'
        f'<span class="badge">👁 {fmt_views(info.get("view_count"))}</span>'
        f'<span class="badge">📺 {info.get("uploader", "—")}</span>'
        f'</div>', unsafe_allow_html=True,
    )

    avail = get_available_formats(info)
    video_heights = sorted(
        {f["height"] for f in avail if f["has_video"] and f["height"] > 0}, reverse=True,
    )
    if video_heights:
        st.markdown(
            f'<div class="fmt-table">📐 Available: '
            f'{"  ·  ".join(f"{h}p" for h in video_heights[:8])}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    chosen = st.selectbox("Format & quality", list(FORMAT_MAP.keys()), index=1)
    fmt_string, is_audio = FORMAT_MAP[chosen]

    if st.button("⬇️  Download Now"):
        with st.spinner("Downloading…"):
            try:
                data, fname = download_video(url, fmt_string, is_audio, cookie_path)
                st.session_state.update({
                    "dl_data": data, "dl_filename": fname, "dl_audio": is_audio,
                })
            except Exception as e:
                err = str(e)
                st.error(err)
                if is_bot_error(Exception(err)):
                    st.warning(
                        "**Bot check triggered during download.**\n\n"
                        "👉 Upload `cookies.txt` in the **🍪** panel above and retry."
                    )
                else:
                    st.info("Try **Best available video** or **MP3 Audio** — these always work.\n\n"
                            "Age-gated / DRM content requires cookies.")

    if st.session_state.get("dl_data"):
        fname  = st.session_state["dl_filename"]
        is_aud = st.session_state["dl_audio"]
        mime   = "audio/mpeg" if is_aud else "video/mp4"
        label  = fname[:55] + ("…" if len(fname) > 55 else "")
        st.success("✅ Ready to save!")
        st.download_button(
            label=f"💾  Save  {label}",
            data=st.session_state["dl_data"],
            file_name=fname,
            mime=mime,
        )

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown('<hr class="divider">', unsafe_allow_html=True)
st.markdown(
    '<p style="font-family:\'Space Mono\',monospace;font-size:0.62rem;'
    'color:#2a2a3e;text-align:center;">'
    'Powered by yt-dlp · Personal use only · Respect YouTube ToS'
    '</p>', unsafe_allow_html=True,
)
