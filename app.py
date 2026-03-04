import streamlit as st
import yt_dlp
import os
import tempfile
import re
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="YT Downloader", page_icon="▶️", layout="centered")

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');
html,body,[class*="css"]{font-family:'Syne',sans-serif;}
.stApp{background:#0a0a0f;color:#e8e8e8;}
#MainMenu,footer,header{visibility:hidden;}
.hero-title{
    font-family:'Syne',sans-serif;font-weight:800;font-size:3rem;letter-spacing:-2px;
    background:linear-gradient(135deg,#ff4d4d 0%,#ff9a3c 55%,#ffe066 100%);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
    margin-bottom:0;
}
.hero-sub{
    font-family:'Space Mono',monospace;font-size:.72rem;color:#444;
    letter-spacing:3px;text-transform:uppercase;margin-bottom:2rem;
}
.stTextInput>div>div>input{
    background:#0f0f18!important;border:1.5px solid #2a2a3e!important;border-radius:10px!important;
    color:#e8e8e8!important;font-family:'Space Mono',monospace!important;
    font-size:.82rem!important;padding:.7rem 1rem!important;
}
.stTextInput>div>div>input:focus{border-color:#ff4d4d!important;box-shadow:0 0 0 2px rgba(255,77,77,.12)!important;}
.stSelectbox>div>div{background:#0f0f18!important;border:1.5px solid #2a2a3e!important;border-radius:10px!important;color:#e8e8e8!important;}
.stButton>button{
    background:linear-gradient(135deg,#ff4d4d,#ff7a3c)!important;color:#fff!important;
    border:none!important;border-radius:10px!important;font-family:'Syne',sans-serif!important;
    font-weight:700!important;font-size:.92rem!important;padding:.6rem 1.8rem!important;width:100%;
}
.stButton>button:hover{opacity:.85!important;transform:translateY(-1px)!important;}
.stDownloadButton>button{
    background:linear-gradient(135deg,#22c55e,#16a34a)!important;color:#fff!important;
    border:none!important;border-radius:10px!important;font-family:'Syne',sans-serif!important;
    font-weight:700!important;font-size:.92rem!important;padding:.6rem 1.8rem!important;width:100%;
}
.vtitle{font-family:'Syne',sans-serif;font-weight:700;font-size:1.05rem;color:#e8e8e8;margin:.6rem 0 .2rem;}
.badge{
    display:inline-block;background:#1a1a28;border:1px solid #252538;border-radius:6px;
    padding:2px 9px;font-family:'Space Mono',monospace;font-size:.68rem;color:#777;margin-right:5px;
}
.divider{border:none;border-top:1px solid #1a1a28;margin:1.4rem 0;}
.stAlert{border-radius:10px!important;font-family:'Space Mono',monospace!important;font-size:.78rem!important;}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def is_valid_yt(url: str) -> bool:
    return bool(re.match(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+", url.strip()))

def fmt_dur(s) -> str:
    if not s: return "—"
    h, r = divmod(int(s), 3600)
    m, sec = divmod(r, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"

def fmt_views(n) -> str:
    if not n: return "—"
    return f"{n/1e6:.1f}M views" if n>=1e6 else f"{n/1e3:.1f}K views" if n>=1e3 else f"{n} views"


# ─────────────────────────────────────────────────────────────────────────────
# YT-DLP BASE OPTIONS
# ─────────────────────────────────────────────────────────────────────────────

def base_opts() -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.youtube.com/",
            "Origin": "https://www.youtube.com",
        },
        # ios gives pre-signed URLs — avoids 403 almost entirely
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "android", "web"],
            }
        },
        "retries": 10,
        "fragment_retries": 10,
        "file_access_retries": 5,
        "socket_timeout": 30,
    }


# ─────────────────────────────────────────────────────────────────────────────
# FETCH INFO + LIST REAL AVAILABLE FORMATS
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=300)
def fetch_info(url: str) -> dict:
    opts = {**base_opts(), "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def get_available_formats(info: dict) -> list[dict]:
    """
    Parse the real format list from yt-dlp info and build a clean
    menu of options the user can actually download — no guessing.
    """
    raw = info.get("formats", [])
    options = []

    # ── Audio only ──────────────────────────────────────────────────────────
    audio_fmts = [
        f for f in raw
        if f.get("vcodec") == "none" and f.get("acodec") != "none"
        and f.get("url")
    ]
    if audio_fmts:
        best_audio = max(audio_fmts, key=lambda f: f.get("abr") or f.get("tbr") or 0)
        options.append({
            "label": "🎵  MP3 Audio (best quality)",
            "format_id": best_audio["format_id"],
            "is_audio": True,
            "ext": "mp3",
            "note": f"{best_audio.get('abr', '?')} kbps",
        })

    # ── Muxed (video+audio in one stream) — preferred, no merge needed ──────
    muxed = [
        f for f in raw
        if f.get("vcodec") != "none"
        and f.get("acodec") != "none"
        and f.get("url")
    ]
    seen_heights = set()
    for f in sorted(muxed, key=lambda f: f.get("height") or 0, reverse=True):
        h = f.get("height") or 0
        if h and h not in seen_heights:
            seen_heights.add(h)
            options.append({
                "label": f"🎬  MP4 {h}p  (fast · single file)",
                "format_id": f["format_id"],
                "is_audio": False,
                "ext": "mp4",
                "note": f"{h}p muxed",
            })

    # ── DASH video-only + best audio (gives higher resolutions) ─────────────
    dash_video = [
        f for f in raw
        if f.get("vcodec") != "none"
        and f.get("acodec") == "none"
        and f.get("url")
        and (f.get("ext") in ("mp4", "webm") or "mp4" in (f.get("vcodec") or ""))
    ]
    dash_heights = set()
    for f in sorted(dash_video, key=lambda f: f.get("height") or 0, reverse=True):
        h = f.get("height") or 0
        if h and h not in seen_heights and h not in dash_heights:
            dash_heights.add(h)
            seen_heights.add(h)
            label_ext = f.get("ext", "mp4")
            options.append({
                "label": f"🎬  {label_ext.upper()} {h}p  (needs merge)",
                "format_id": f"{f['format_id']}+bestaudio/best",
                "is_audio": False,
                "ext": "mp4",
                "note": f"{h}p DASH",
            })

    # ── Absolute fallback ────────────────────────────────────────────────────
    if not options:
        options.append({
            "label": "🎬  Best available (auto)",
            "format_id": "best",
            "is_audio": False,
            "ext": "mp4",
            "note": "auto",
        })

    return options


# ─────────────────────────────────────────────────────────────────────────────
# DOWNLOAD
# ─────────────────────────────────────────────────────────────────────────────

def download_video(url: str, format_id: str, is_audio: bool, out_ext: str) -> tuple[bytes, str]:
    with tempfile.TemporaryDirectory() as tmpdir:
        out_tpl = os.path.join(tmpdir, "%(title)s.%(ext)s")

        postprocessors = []
        if is_audio:
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            })

        opts = {
            **base_opts(),
            "format": format_id,
            "outtmpl": out_tpl,
            "postprocessors": postprocessors,
            "merge_output_format": None if is_audio else out_ext,
            "keepvideo": False,
        }

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        files = [f for f in Path(tmpdir).iterdir() if f.is_file()]
        if not files:
            raise FileNotFoundError("yt-dlp produced no output file.")

        out_file = max(files, key=lambda f: f.stat().st_size)
        return out_file.read_bytes(), out_file.name


# ─────────────────────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="hero-title">YT Downloader</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Free · No login · No limits</div>', unsafe_allow_html=True)

url_input = st.text_input("url", placeholder="https://youtube.com/watch?v=...", label_visibility="collapsed")

col1, _ = st.columns([1, 2])
with col1:
    fetch_btn = st.button("🔍 Fetch Info")

# ── Fetch ──────────────────────────────────────────────────────────────────────
if fetch_btn:
    url_input = (url_input or "").strip()
    if not url_input:
        st.error("Paste a YouTube URL above.")
    elif not is_valid_yt(url_input):
        st.error("Not a valid YouTube URL.")
    else:
        with st.spinner("Fetching video info…"):
            try:
                info = fetch_info(url_input)
                st.session_state.update({
                    "info": info,
                    "url": url_input,
                    "dl_data": None,
                    "dl_filename": None,
                    "dl_audio": None,
                    "fmt_options": get_available_formats(info),
                })
            except Exception as exc:
                st.error(f"Fetch failed: {exc}")

# ── Display + download ─────────────────────────────────────────────────────────
if st.session_state.get("info"):
    info        = st.session_state["info"]
    url_dl      = st.session_state["url"]
    fmt_options = st.session_state["fmt_options"]

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    thumb = info.get("thumbnail")
    if thumb:
        st.image(thumb, width="stretch")          # ✅ fixed deprecation

    st.markdown(f'<div class="vtitle">{info.get("title","Unknown")}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<span class="badge">⏱ {fmt_dur(info.get("duration"))}</span>'
        f'<span class="badge">👁 {fmt_views(info.get("view_count"))}</span>'
        f'<span class="badge">📺 {info.get("uploader","—")}</span>',
        unsafe_allow_html=True,
    )

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ── Format selector — built from REAL available formats ──────────────────
    labels      = [f["label"] for f in fmt_options]
    chosen_idx  = st.selectbox("Format & Quality", range(len(labels)), format_func=lambda i: labels[i])
    chosen_fmt  = fmt_options[chosen_idx]

    st.caption(f"Format ID: `{chosen_fmt['format_id']}`  ·  {chosen_fmt['note']}")

    if st.button("⬇️ Download Now"):
        with st.spinner("Downloading… please wait ⏳"):
            try:
                data, fname = download_video(
                    url_dl,
                    chosen_fmt["format_id"],
                    chosen_fmt["is_audio"],
                    chosen_fmt["ext"],
                )
                st.session_state.update({
                    "dl_data": data,
                    "dl_filename": fname,
                    "dl_audio": chosen_fmt["is_audio"],
                })
                st.success("✅ Done! Click below to save.")
            except Exception as exc:
                err = str(exc)
                st.error(f"Download failed: {err}")
                if "403" in err:
                    st.warning("**403 tip:** Switch to a 'fast · single file' format or MP3 — these avoid DASH stream issues.")
                if "not available" in err.lower():
                    st.warning("**Format unavailable:** Choose a different quality — use the ones marked 'fast · single file' first.")

    if st.session_state.get("dl_data"):
        fname  = st.session_state["dl_filename"]
        is_aud = st.session_state["dl_audio"]
        mime   = "audio/mpeg" if is_aud else "video/mp4"
        label  = fname[:55] + ("…" if len(fname) > 55 else "")
        st.download_button(
            label=f"💾 Save  {label}",
            data=st.session_state["dl_data"],
            file_name=fname,
            mime=mime,
        )

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown('<hr class="divider">', unsafe_allow_html=True)
st.markdown(
    '<p style="font-family:\'Space Mono\',monospace;font-size:.62rem;color:#2a2a2a;text-align:center;">'
    'Powered by yt-dlp · Personal/educational use only'
    '</p>',
    unsafe_allow_html=True,
)
