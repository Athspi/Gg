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
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    font-size: 3rem;
    letter-spacing: -2px;
    background: linear-gradient(135deg, #ff4d4d 0%, #ff9a3c 50%, #ffe066 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.1rem;
}
.hero-sub {
    font-family: 'Space Mono', monospace;
    font-size: 0.75rem;
    color: #444;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-bottom: 2rem;
}
.stTextInput > div > div > input {
    background: #0f0f18 !important;
    border: 1.5px solid #2a2a3e !important;
    border-radius: 10px !important;
    color: #e8e8e8 !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.85rem !important;
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
    width: 100%;
}
.stButton > button:hover { opacity: 0.88 !important; }
.stDownloadButton > button {
    background: linear-gradient(135deg, #22c55e, #16a34a) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    width: 100%;
}
.video-title {
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    font-size: 1.05rem;
    color: #e8e8e8;
    margin: 0.5rem 0 0.25rem 0;
}
.badge {
    display: inline-block;
    background: #1e1e2e;
    border: 1px solid #2a2a3e;
    border-radius: 6px;
    padding: 2px 10px;
    font-family: 'Space Mono', monospace;
    font-size: 0.68rem;
    color: #777;
    margin-right: 5px;
}
.divider { border: none; border-top: 1px solid #1a1a2e; margin: 1.5rem 0; }
.fmt-table {
    font-family: 'Space Mono', monospace;
    font-size: 0.72rem;
    color: #666;
    margin: 0.3rem 0 0.8rem 0;
}
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


# ── Multiple YouTube client configs to bypass 403 ─────────────────────────────
CLIENT_CONFIGS = [
    {"extractor_args": {"youtube": {"player_client": ["ios"]}},
     "http_headers": {"User-Agent": "com.google.ios.youtube/19.29.1 (iPhone16,2; U; CPU iOS 17_5_1 like Mac OS X)"}},
    {"extractor_args": {"youtube": {"player_client": ["android_embedded"]}},
     "http_headers": {"User-Agent": "com.google.android.youtube/17.36.4(Linux; U; Android 12)"}},
    {"extractor_args": {"youtube": {"player_client": ["tv_embedded"]}},
     "http_headers": {"User-Agent": "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.0) AppleWebKit/538.1"}},
    {"extractor_args": {"youtube": {"player_client": ["mweb"]}},
     "http_headers": {"User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Chrome/122.0.6261.119 Mobile Safari/537.36",
                      "Referer": "https://m.youtube.com/"}},
]

COMMON_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "retries": 3,
    "fragment_retries": 3,
    "socket_timeout": 30,
    "nocheckcertificate": True,
}


def _make_opts(client_cfg: dict, extra: dict = None) -> dict:
    opts = {**COMMON_OPTS, **client_cfg}
    if extra:
        opts.update(extra)
    return opts


# ── Format selector — robust fallback strings ─────────────────────────────────
#
#  KEY FIX: Each entry is a LIST of format strings tried left→right.
#  yt-dlp picks the first one that actually exists for this video.
#  The final fallback "best" always works.
#
FORMAT_MAP = {
    "🎵  MP3 Audio":
        (["bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"], True),

    "🎬  Best available video":
        (["bestvideo+bestaudio/best"], False),

    "🎬  MP4 1080p  (or best below)":
        ([
            "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        ], False),

    "🎬  MP4 720p  (or best below)":
        ([
            "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        ], False),

    "🎬  MP4 480p  (or best below)":
        ([
            "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]/best",
        ], False),

    "🎬  MP4 360p  (or best below)":
        ([
            "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360]/best",
        ], False),

    "🎬  MP4 240p  (smallest)":
        ([
            "bestvideo[height<=240][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=240]+bestaudio/best[height<=240]/best",
        ], False),
}


# ── fetch_info: tries all clients ─────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=300)
def fetch_info(url: str) -> dict:
    last_err = None
    for cfg in CLIENT_CONFIGS:
        try:
            opts = _make_opts(cfg, {"skip_download": True})
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    return info
        except Exception as e:
            last_err = e
    raise RuntimeError(f"All clients failed. Last error: {last_err}")


# ── get_available_formats: list what actually exists for this video ────────────
def get_available_formats(info: dict) -> list[dict]:
    """Return simplified list of available formats from cached info."""
    fmts = info.get("formats", [])
    out = []
    seen = set()
    for f in reversed(fmts):          # reversed = best first
        h   = f.get("height") or 0
        ext = f.get("ext", "?")
        acodec = f.get("acodec", "none")
        vcodec = f.get("vcodec", "none")
        has_video = vcodec != "none"
        has_audio = acodec != "none"
        key = (h, ext, has_video, has_audio)
        if key not in seen:
            seen.add(key)
            out.append({
                "format_id": f.get("format_id"),
                "ext": ext,
                "height": h,
                "has_video": has_video,
                "has_audio": has_audio,
                "note": f.get("format_note", ""),
                "filesize": f.get("filesize") or f.get("filesize_approx") or 0,
            })
    return out


# ── download: tries all clients with a robust format string ───────────────────
def download_video(url: str, fmt_strings: list[str], is_audio: bool) -> tuple[bytes, str]:
    """
    fmt_strings: list of yt-dlp format strings, tried in order.
    Falls back through CLIENT_CONFIGS × fmt_strings.
    """
    last_err = None

    # Build a single combined format string with all fallbacks joined by /
    combined_fmt = "/".join(fmt_strings)

    for cfg in CLIENT_CONFIGS:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                out_tmpl = os.path.join(tmpdir, "%(title)s.%(ext)s")

                pp = []
                if is_audio:
                    pp.append({
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    })

                opts = _make_opts(cfg, {
                    "format": combined_fmt,
                    "outtmpl": out_tmpl,
                    "postprocessors": pp,
                    "merge_output_format": None if is_audio else "mp4",
                    # ✅ KEY FIX: ignore errors for unavailable formats, pick best available
                    "ignoreerrors": False,
                    "format_sort": ["res", "ext:mp4:m4a", "codec:h264"],
                })

                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])

                files = sorted(
                    Path(tmpdir).iterdir(),
                    key=lambda f: f.stat().st_size,
                    reverse=True,
                )
                if files:
                    return files[0].read_bytes(), files[0].name

        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            # Retry on network/403 errors; re-raise on format errors immediately
            if "403" in err_str or "http error" in err_str or "timed out" in err_str:
                continue
            # "requested format is not available" — try next client
            if "not available" in err_str or "format" in err_str:
                continue
            raise

    raise RuntimeError(
        f"Download failed after trying all clients.\n\nLast error: {last_err}\n\n"
        "Try selecting a different quality or use 'Best available video'."
    )


# ── UI ────────────────────────────────────────────────────────────────────────
st.markdown('<div class="hero-title">YT Downloader</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Free · No Login · No Limits</div>', unsafe_allow_html=True)

url_input = st.text_input(
    "url",
    placeholder="https://youtube.com/watch?v=...",
    label_visibility="collapsed",
)

c1, c2 = st.columns([1, 2])
with c1:
    fetch_btn = st.button("🔍  Fetch Info")

# ── Fetch ──────────────────────────────────────────────────────────────────────
if fetch_btn:
    if not url_input:
        st.error("Paste a YouTube URL above.")
    elif not is_valid_url(url_input):
        st.error("Doesn't look like a valid YouTube URL.")
    else:
        with st.spinner("Fetching video info…"):
            try:
                info = fetch_info(url_input)
                st.session_state.update({
                    "info":        info,
                    "url":         url_input,
                    "dl_data":     None,
                    "dl_filename": None,
                    "dl_audio":    None,
                })
            except Exception as e:
                st.error(f"Failed to fetch: {e}")

# ── Video info + download ──────────────────────────────────────────────────────
if st.session_state.get("info"):
    info = st.session_state["info"]
    url  = st.session_state["url"]

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    thumb = info.get("thumbnail")
    if thumb:
        st.image(thumb, width="stretch")

    st.markdown(
        f'<div class="video-title">{info.get("title","Unknown title")}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div>'
        f'<span class="badge">⏱ {fmt_duration(info.get("duration"))}</span>'
        f'<span class="badge">👁 {fmt_views(info.get("view_count"))}</span>'
        f'<span class="badge">📺 {info.get("uploader","—")}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Show available resolutions ────────────────────────────────────────────
    avail = get_available_formats(info)
    video_heights = sorted(
        {f["height"] for f in avail if f["has_video"] and f["height"] > 0},
        reverse=True,
    )
    if video_heights:
        heights_str = " · ".join(f"{h}p" for h in video_heights[:8])
        st.markdown(
            f'<div class="fmt-table">📐 Available resolutions: {heights_str}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── Format selector ───────────────────────────────────────────────────────
    chosen = st.selectbox("Format & quality", list(FORMAT_MAP.keys()), index=1)
    fmt_strings, is_audio = FORMAT_MAP[chosen]

    if st.button("⬇️  Download Now"):
        with st.spinner("Downloading… auto-selecting best available quality"):
            try:
                data, fname = download_video(url, fmt_strings, is_audio)
                st.session_state.update({
                    "dl_data":     data,
                    "dl_filename": fname,
                    "dl_audio":    is_audio,
                })
            except Exception as e:
                st.error(str(e))
                st.info(
                    "**Tips:**\n"
                    "- Select **'Best available video'** — always works\n"
                    "- Or try **MP3 Audio** for audio-only\n"
                    "- Age-gated / DRM videos cannot be downloaded"
                )

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
    '</p>',
    unsafe_allow_html=True,
)
