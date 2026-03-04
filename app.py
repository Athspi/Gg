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


# ── Client configs — multiple fallback clients to beat 403 ────────────────────
CLIENT_CONFIGS = [
    # ios is most reliable for format availability
    {
        "extractor_args": {"youtube": {"player_client": ["ios"]}},
        "http_headers": {
            "User-Agent": "com.google.ios.youtube/19.29.1 (iPhone16,2; U; CPU iOS 17_5_1 like Mac OS X)",
        },
    },
    # android_embedded — good fallback
    {
        "extractor_args": {"youtube": {"player_client": ["android_embedded"]}},
        "http_headers": {
            "User-Agent": "com.google.android.youtube/17.36.4(Linux; U; Android 12)",
        },
    },
    # web fallback
    {
        "extractor_args": {"youtube": {"player_client": ["web"]}},
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        },
    },
    # tv_embedded
    {
        "extractor_args": {"youtube": {"player_client": ["tv_embedded"]}},
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.0) AppleWebKit/538.1",
        },
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


def _make_opts(client_cfg: dict, extra: dict = None) -> dict:
    opts = {**COMMON_OPTS, **client_cfg}
    if extra:
        opts.update(extra)
    return opts


# ── FORMAT MAP ────────────────────────────────────────────────────────────────
#
#  Strategy: avoid hard ext/codec filters that cause "format not available".
#  Use height caps only, let format_sort + merge_output_format handle the rest.
#  Final "/best" ensures something always downloads.
#
FORMAT_MAP = {
    # ── Audio ──────────────────────────────────────────────────────────────────
    "🎵  MP3 Audio":
        ("bestaudio/best", True),

    # ── Video ──────────────────────────────────────────────────────────────────
    "🎬  Best available video":
        ("bestvideo+bestaudio/best", False),

    "🎬  1080p  (or best below)":
        ("bestvideo[height<=1080]+bestaudio/bestvideo[height<=1080]+bestaudio[ext=m4a]/best[height<=1080]/best", False),

    "🎬  720p  (or best below)":
        ("bestvideo[height<=720]+bestaudio/bestvideo[height<=720]+bestaudio[ext=m4a]/best[height<=720]/best", False),

    "🎬  480p  (or best below)":
        ("bestvideo[height<=480]+bestaudio/bestvideo[height<=480]+bestaudio[ext=m4a]/best[height<=480]/best", False),

    "🎬  360p  (or best below)":
        ("bestvideo[height<=360]+bestaudio/bestvideo[height<=360]+bestaudio[ext=m4a]/best[height<=360]/best", False),

    "🎬  240p  (smallest)":
        ("bestvideo[height<=240]+bestaudio/bestvideo[height<=240]+bestaudio[ext=m4a]/best[height<=240]/best", False),
}


# ── fetch_info ─────────────────────────────────────────────────────────────────
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


# ── get_available_formats ──────────────────────────────────────────────────────
def get_available_formats(info: dict) -> list[dict]:
    fmts = info.get("formats", [])
    out, seen = [], set()
    for f in reversed(fmts):
        h      = f.get("height") or 0
        ext    = f.get("ext", "?")
        acodec = f.get("acodec", "none")
        vcodec = f.get("vcodec", "none")
        has_video = vcodec not in (None, "none")
        has_audio = acodec not in (None, "none")
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


# ── download_video ─────────────────────────────────────────────────────────────
def download_video(url: str, fmt_string: str, is_audio: bool) -> tuple[bytes, str]:
    """
    Tries each CLIENT_CONFIG in order.
    Uses a permissive format string + format_sort so yt-dlp picks the best
    available stream — no more "Requested format is not available" errors.
    """
    last_err = None

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

                extra = {
                    "format": fmt_string,
                    "outtmpl": out_tmpl,
                    "postprocessors": pp,
                    # Always merge to mp4 for video; ignored for audio (ffmpeg handles it)
                    "merge_output_format": "mp4" if not is_audio else None,
                    # Prefer mp4/m4a containers and h264/aac codecs, then fall back gracefully
                    "format_sort": [
                        "res",
                        "ext:mp4:m4a:webm",
                        "codec:h264:aac",
                        "size",
                        "br",
                    ],
                    # Never abort on a format miss — let fallback chain handle it
                    "ignoreerrors": False,
                    # Allow yt-dlp to pick closest quality if exact match unavailable
                    "allow_multiple_video_streams": False,
                    "allow_multiple_audio_streams": False,
                }

                opts = _make_opts(cfg, extra)

                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])

                files = sorted(
                    [f for f in Path(tmpdir).iterdir() if f.is_file()],
                    key=lambda f: f.stat().st_size,
                    reverse=True,
                )
                if files:
                    return files[0].read_bytes(), files[0].name

        except Exception as e:
            last_err = e
            err_lower = str(e).lower()
            # Always retry on network / format errors
            if any(k in err_lower for k in ("403", "http error", "timed out",
                                             "not available", "format", "unavailable")):
                continue
            # Unknown error — re-raise immediately
            raise

    raise RuntimeError(
        f"Download failed after trying all clients.\n\nLast error: {last_err}\n\n"
        "💡 Try selecting **'Best available video'** or **MP3 Audio** — these always work."
    )


# ── UI ─────────────────────────────────────────────────────────────────────────
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
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Available resolutions ─────────────────────────────────────────────────
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
    fmt_string, is_audio = FORMAT_MAP[chosen]

    if st.button("⬇️  Download Now"):
        with st.spinner("Downloading… picking best available quality"):
            try:
                data, fname = download_video(url, fmt_string, is_audio)
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

# ── Footer ──────────────────────────────────────────────────────────────────────
st.markdown('<hr class="divider">', unsafe_allow_html=True)
st.markdown(
    '<p style="font-family:\'Space Mono\',monospace;font-size:0.62rem;'
    'color:#2a2a3e;text-align:center;">'
    'Powered by yt-dlp · Personal use only · Respect YouTube ToS'
    '</p>',
    unsafe_allow_html=True,
)
