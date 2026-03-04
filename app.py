import streamlit as st
import yt_dlp
import re

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
}
.hero-sub{
    font-family:'Space Mono',monospace;font-size:.72rem;color:#444;
    letter-spacing:3px;text-transform:uppercase;margin-bottom:2rem;
}
.stTextInput>div>div>input{
    background:#0f0f18!important;border:1.5px solid #2a2a3e!important;
    border-radius:10px!important;color:#e8e8e8!important;
    font-family:'Space Mono',monospace!important;font-size:.82rem!important;padding:.7rem 1rem!important;
}
.stTextInput>div>div>input:focus{border-color:#ff4d4d!important;box-shadow:0 0 0 2px rgba(255,77,77,.12)!important;}
.stSelectbox>div>div{background:#0f0f18!important;border:1.5px solid #2a2a3e!important;border-radius:10px!important;color:#e8e8e8!important;}
.stButton>button{
    background:linear-gradient(135deg,#ff4d4d,#ff7a3c)!important;color:#fff!important;
    border:none!important;border-radius:10px!important;font-family:'Syne',sans-serif!important;
    font-weight:700!important;font-size:.92rem!important;padding:.6rem 1.8rem!important;width:100%;
}
.stButton>button:hover{opacity:.85!important;transform:translateY(-1px)!important;}
.dl-btn{
    display:block;width:100%;padding:.65rem 1.8rem;
    background:linear-gradient(135deg,#22c55e,#16a34a);color:#fff!important;
    border:none;border-radius:10px;font-family:'Syne',sans-serif;font-weight:700;
    font-size:.92rem;text-align:center;text-decoration:none!important;
    cursor:pointer;margin-top:.5rem;box-sizing:border-box;
}
.dl-btn:hover{opacity:.85;}
.vtitle{font-family:'Syne',sans-serif;font-weight:700;font-size:1.05rem;color:#e8e8e8;margin:.6rem 0 .2rem;}
.badge{
    display:inline-block;background:#1a1a28;border:1px solid #252538;
    border-radius:6px;padding:2px 9px;font-family:'Space Mono',monospace;
    font-size:.68rem;color:#777;margin-right:5px;
}
.fmt-card{
    background:#0f0f18;border:1.5px solid #1e1e2e;border-radius:12px;
    padding:1rem 1.2rem;margin:.5rem 0;
}
.fmt-label{font-family:'Syne',sans-serif;font-weight:700;font-size:.95rem;color:#e8e8e8;}
.fmt-note{font-family:'Space Mono',monospace;font-size:.68rem;color:#555;margin-top:.15rem;}
.divider{border:none;border-top:1px solid #1a1a28;margin:1.4rem 0;}
.info-box{
    background:#0d1a0d;border:1px solid #1a3a1a;border-radius:10px;
    padding:.8rem 1rem;font-family:'Space Mono',monospace;font-size:.75rem;color:#4ade80;
    margin:.8rem 0;
}
.warn-box{
    background:#1a140d;border:1px solid #3a2a1a;border-radius:10px;
    padding:.8rem 1rem;font-family:'Space Mono',monospace;font-size:.75rem;color:#fb923c;
    margin:.8rem 0;
}
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

def human_size(b) -> str:
    if not b: return "? MB"
    if b >= 1_073_741_824: return f"{b/1_073_741_824:.1f} GB"
    if b >= 1_048_576:     return f"{b/1_048_576:.1f} MB"
    return f"{b/1024:.0f} KB"


# ─────────────────────────────────────────────────────────────────────────────
# YT-DLP OPTIONS
# ─────────────────────────────────────────────────────────────────────────────

def ydl_opts_info() -> dict:
    """Options for info extraction only — no download."""
    return {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.youtube.com/",
            "Origin": "https://www.youtube.com",
        },
        "extractor_args": {
            "youtube": {
                # ios client returns pre-signed CDN URLs — user's browser can fetch these directly
                "player_client": ["ios", "android", "web"],
            }
        },
        "retries": 5,
        "socket_timeout": 30,
    }


# ─────────────────────────────────────────────────────────────────────────────
# FETCH INFO
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=240)
def fetch_info(url: str) -> dict:
    with yt_dlp.YoutubeDL(ydl_opts_info()) as ydl:
        return ydl.extract_info(url, download=False)


# ─────────────────────────────────────────────────────────────────────────────
# BUILD FORMAT OPTIONS FROM REAL AVAILABLE FORMATS
# Returns list of dicts with: label, url, ext, filesize, note, is_audio
# ─────────────────────────────────────────────────────────────────────────────

def build_formats(info: dict) -> list[dict]:
    raw = info.get("formats", [])
    options = []
    seen_heights = set()

    # ── 1. Audio-only → MP3 label ────────────────────────────────────────────
    audio_fmts = [
        f for f in raw
        if f.get("vcodec") == "none"
        and f.get("acodec") not in (None, "none")
        and f.get("url")
    ]
    if audio_fmts:
        best = max(audio_fmts, key=lambda f: f.get("abr") or f.get("tbr") or 0)
        abr = best.get("abr") or best.get("tbr") or "?"
        options.append({
            "label":    "🎵  Audio only  (MP3/M4A best quality)",
            "url":      best["url"],
            "ext":      best.get("ext", "m4a"),
            "filesize": best.get("filesize") or best.get("filesize_approx"),
            "note":     f"{abr} kbps · audio only",
            "is_audio": True,
            "filename": f"{info.get('title','audio')}.{best.get('ext','m4a')}",
        })

    # ── 2. Muxed (progressive) — video+audio combined, single file ───────────
    muxed = [
        f for f in raw
        if f.get("vcodec") not in (None, "none")
        and f.get("acodec") not in (None, "none")
        and f.get("url")
    ]
    for f in sorted(muxed, key=lambda f: f.get("height") or 0, reverse=True):
        h = f.get("height") or 0
        if h and h not in seen_heights:
            seen_heights.add(h)
            ext = f.get("ext", "mp4")
            options.append({
                "label":    f"🎬  {h}p  · {ext.upper()}  (single file — recommended)",
                "url":      f["url"],
                "ext":      ext,
                "filesize": f.get("filesize") or f.get("filesize_approx"),
                "note":     f"{h}p muxed · {f.get('vcodec','?')} · {f.get('fps','?')}fps",
                "is_audio": False,
                "filename": f"{info.get('title','video')}_{h}p.{ext}",
            })

    # ── 3. DASH video-only streams (no audio) ────────────────────────────────
    dash_v = [
        f for f in raw
        if f.get("vcodec") not in (None, "none")
        and f.get("acodec") in (None, "none")
        and f.get("url")
    ]
    for f in sorted(dash_v, key=lambda f: f.get("height") or 0, reverse=True):
        h = f.get("height") or 0
        if h and h not in seen_heights:
            seen_heights.add(h)
            ext = f.get("ext", "mp4")
            options.append({
                "label":    f"🎬  {h}p  · {ext.upper()}  (video only — no audio)",
                "url":      f["url"],
                "ext":      ext,
                "filesize": f.get("filesize") or f.get("filesize_approx"),
                "note":     f"{h}p DASH video-only · {f.get('vcodec','?')}",
                "is_audio": False,
                "filename": f"{info.get('title','video')}_{h}p_video.{ext}",
            })

    # ── Fallback ─────────────────────────────────────────────────────────────
    if not options:
        # last resort: grab url from the info itself
        url = info.get("url")
        ext = info.get("ext", "mp4")
        if url:
            options.append({
                "label":    "🎬  Best available (auto)",
                "url":      url,
                "ext":      ext,
                "filesize": None,
                "note":     "auto-selected best format",
                "is_audio": False,
                "filename": f"{info.get('title','video')}.{ext}",
            })

    return options


# ─────────────────────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="hero-title">YT Downloader</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Free · No login · No limits</div>', unsafe_allow_html=True)

url_input = st.text_input("url", placeholder="https://youtube.com/watch?v=...", label_visibility="collapsed")

c1, _ = st.columns([1, 2])
with c1:
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
                fmts = build_formats(info)
                st.session_state.update({
                    "info": info,
                    "url": url_input,
                    "fmts": fmts,
                })
            except Exception as exc:
                st.error(f"Fetch failed: {exc}")

# ── Display ────────────────────────────────────────────────────────────────────
if st.session_state.get("info"):
    info = st.session_state["info"]
    fmts = st.session_state["fmts"]

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    thumb = info.get("thumbnail")
    if thumb:
        st.image(thumb, width="stretch")

    st.markdown(f'<div class="vtitle">{info.get("title","Unknown")}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<span class="badge">⏱ {fmt_dur(info.get("duration"))}</span>'
        f'<span class="badge">👁 {fmt_views(info.get("view_count"))}</span>'
        f'<span class="badge">📺 {info.get("uploader","—")}</span>',
        unsafe_allow_html=True,
    )

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # How this works explanation
    st.markdown(
        '<div class="info-box">'
        '✅ <b>No server download = No 403.</b><br>'
        'We extract the direct YouTube CDN URL and your browser downloads it straight from YouTube — bypasses all server-side blocks.'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Format selector ────────────────────────────────────────────────────────
    labels     = [f["label"] for f in fmts]
    chosen_idx = st.selectbox(
        "Format & Quality",
        range(len(labels)),
        format_func=lambda i: labels[i],
    )
    chosen = fmts[chosen_idx]

    size_str = human_size(chosen["filesize"]) if chosen["filesize"] else "size unknown"
    st.caption(f"{chosen['note']}  ·  ~{size_str}")

    if chosen["is_audio"]:
        st.markdown(
            '<div class="warn-box">🎵 Audio-only file. To convert to MP3 use <b>VLC</b> or <b>ffmpeg</b> locally after download.</div>',
            unsafe_allow_html=True,
        )

    # ── Direct download link — opens in user's browser, no server involved ────
    direct_url = chosen["url"]
    filename   = chosen["filename"]

    # Clean filename for HTML attribute
    safe_name = re.sub(r'[^\w\s\-.]', '', filename)[:100]

    # The key trick: <a href="DIRECT_CDN_URL" download> in user's browser
    # This downloads from YouTube's CDN directly using the user's IP — never 403
    st.markdown(
        f'<a class="dl-btn" href="{direct_url}" download="{safe_name}" target="_blank">'
        f'⬇️&nbsp; Download &nbsp;{safe_name[:50]}{"…" if len(safe_name)>50 else ""}'
        f'</a>',
        unsafe_allow_html=True,
    )

    # Copy URL fallback
    with st.expander("📋 Or copy direct URL (open in browser / IDM / aria2)"):
        st.code(direct_url, language=None)
        st.caption(
            "Paste this URL into:\n"
            "- **IDM / Internet Download Manager** for fastest speeds\n"
            "- **VLC** → Media → Open Network Stream\n"
            "- **aria2c** in terminal: `aria2c \"<URL>\"`\n"
            "- Any browser address bar → right-click → Save As"
        )

    st.markdown(
        '<div class="warn-box">'
        '⚠️ <b>Note:</b> YouTube CDN URLs expire in ~6 hours. Download right away. '
        'Click "Fetch Info" again if the link stops working.'
        '</div>',
        unsafe_allow_html=True,
    )

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown('<hr class="divider">', unsafe_allow_html=True)
st.markdown(
    '<p style="font-family:\'Space Mono\',monospace;font-size:.62rem;color:#2a2a2a;text-align:center;">'
    'Powered by yt-dlp · Personal/educational use only · Respect creators & YouTube ToS'
    '</p>',
    unsafe_allow_html=True,
)
