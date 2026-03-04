"""
YT Downloader — Streamlit UI + built-in REST API
═════════════════════════════════════════════════
• Streamlit UI  →  port 8501  (default)
• FastAPI REST  →  port 8000  (background thread, started ONCE at module level)

API Endpoints:
  GET  /health
  GET  /api/info?url=<youtube_url>
  GET  /api/formats?url=<youtube_url>
  GET  /api/stream?url=<youtube_url>&format_id=<id>
  GET  /api/search?q=<query>&max_results=5
  Swagger UI  →  http://localhost:8000/docs
"""

# ── std-lib imports FIRST, before streamlit ──────────────────────────────────
import re
import threading
import urllib.parse

# ── FastAPI (started at module level — avoids ScriptRunContext warning) ───────
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import yt_dlp

# ─────────────────────────────────────────────────────────────────────────────
# SHARED YT-DLP HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _ydl_base() -> dict:
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
            "youtube": {"player_client": ["ios", "android", "web"]}
        },
        "retries": 5,
        "socket_timeout": 30,
    }


def _extract(url: str) -> dict:
    with yt_dlp.YoutubeDL(_ydl_base()) as ydl:
        return ydl.extract_info(url, download=False)


def _parse_formats(info: dict) -> list:
    raw, out, seen = info.get("formats", []), [], set()
    for f in sorted(raw, key=lambda x: x.get("height") or 0, reverse=True):
        if not f.get("url"):
            continue
        vcodec = f.get("vcodec", "none")
        acodec = f.get("acodec", "none")
        h      = f.get("height")
        ext    = f.get("ext", "?")

        if   vcodec == "none" and acodec != "none": kind = "audio"
        elif vcodec != "none" and acodec != "none": kind = "muxed"
        elif vcodec != "none":                       kind = "video"
        else: continue

        key = f"{kind}-{h}-{ext}"
        if key in seen:
            continue
        seen.add(key)

        out.append({
            "format_id": f["format_id"],
            "kind":      kind,
            "ext":       ext,
            "height":    h,
            "fps":       f.get("fps"),
            "vcodec":    vcodec,
            "acodec":    acodec,
            "abr":       f.get("abr"),
            "tbr":       f.get("tbr"),
            "filesize":  f.get("filesize") or f.get("filesize_approx"),
            "url":       f["url"],
            "note":      f.get("format_note", ""),
        })
    return out


# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI APP
# ─────────────────────────────────────────────────────────────────────────────

api = FastAPI(
    title="YT Downloader API",
    description=(
        "Extract YouTube video info & direct CDN stream URLs via yt-dlp.\n\n"
        "**No 403** — CDN URLs are downloaded by the caller's browser/IP, not the server."
    ),
    version="2.1.0",
)
api.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@api.get("/health", tags=["status"])
def health():
    return {"status": "ok", "service": "YT Downloader API", "version": "2.1.0"}


@api.get("/api/info", tags=["youtube"])
def get_info(url: str = Query(..., description="Full YouTube URL")):
    """Full metadata + all available formats with direct CDN URLs."""
    try:
        info = _extract(url)
    except Exception as e:
        raise HTTPException(400, detail=str(e))
    return {
        "id":          info.get("id"),
        "title":       info.get("title"),
        "uploader":    info.get("uploader"),
        "duration":    info.get("duration"),
        "view_count":  info.get("view_count"),
        "like_count":  info.get("like_count"),
        "thumbnail":   info.get("thumbnail"),
        "description": (info.get("description") or "")[:500],
        "webpage_url": info.get("webpage_url"),
        "formats":     _parse_formats(info),
    }


@api.get("/api/formats", tags=["youtube"])
def get_formats(url: str = Query(..., description="Full YouTube URL")):
    """Lighter version — returns only the format list."""
    try:
        info = _extract(url)
    except Exception as e:
        raise HTTPException(400, detail=str(e))
    return {"id": info.get("id"), "title": info.get("title"), "formats": _parse_formats(info)}


@api.get("/api/stream", tags=["youtube"])
def get_stream(
    url:       str  = Query(...,  description="Full YouTube URL"),
    format_id: str  = Query(None, description="Format ID from /api/formats. Omit for best."),
):
    """Returns a single direct CDN URL. Open in browser or download manager."""
    try:
        opts = {**_ydl_base(), "format": format_id if format_id else "best[ext=mp4]/best"}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if format_id:
            match = next((f for f in info.get("formats", []) if f["format_id"] == format_id), None)
            if not match:
                raise HTTPException(404, detail=f"format_id '{format_id}' not found")
            stream_url = match["url"]
            ext        = match.get("ext", "mp4")
            height     = match.get("height")
        else:
            stream_url = info.get("url") or (info.get("formats") or [{}])[-1].get("url")
            ext        = info.get("ext", "mp4")
            height     = info.get("height")

        if not stream_url:
            raise HTTPException(500, detail="Could not extract stream URL")

        return {
            "id": info.get("id"), "title": info.get("title"),
            "format_id": format_id or "best",
            "ext": ext, "height": height,
            "stream_url": stream_url, "expires_in": "~6 hours",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, detail=str(e))


@api.get("/api/search", tags=["youtube"])
def search(
    q:           str = Query(...,  description="Search query"),
    max_results: int = Query(5, ge=1, le=20, description="Number of results (1-20)"),
):
    """Search YouTube — returns video metadata list."""
    try:
        opts = {**_ydl_base(), "default_search": "ytsearch", "noplaylist": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{q}", download=False)
        results = []
        for e in (info.get("entries") or []):
            if not e: continue
            results.append({
                "id": e.get("id"), "title": e.get("title"),
                "uploader": e.get("uploader"), "duration": e.get("duration"),
                "view_count": e.get("view_count"), "thumbnail": e.get("thumbnail"),
                "url": e.get("webpage_url") or f"https://youtube.com/watch?v={e.get('id')}",
            })
        return {"query": q, "results": results}
    except Exception as e:
        raise HTTPException(400, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# START API THREAD ONCE AT MODULE LEVEL  ← fixes ScriptRunContext warning
# ─────────────────────────────────────────────────────────────────────────────

_API_PORT = 8000

def _run_api():
    uvicorn.run(api, host="0.0.0.0", port=_API_PORT, log_level="error")

# Module-level flag — persists across Streamlit reruns, no session_state needed
if not hasattr(threading, "_yt_api_started"):
    _t = threading.Thread(target=_run_api, daemon=True, name="yt-api")
    _t.start()
    threading._yt_api_started = True   # type: ignore[attr-defined]


# ─────────────────────────────────────────────────────────────────────────────
# STREAMLIT  (imported AFTER thread is started)
# ─────────────────────────────────────────────────────────────────────────────
import streamlit as st

st.set_page_config(page_title="YT Downloader + API", page_icon="▶️", layout="centered")

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');
html,body,[class*="css"]{font-family:'Syne',sans-serif;}
.stApp{background:#08080f;color:#e8e8e8;}
#MainMenu,footer,header{visibility:hidden;}

.hero-title{
    font-family:'Syne',sans-serif;font-weight:800;font-size:2.8rem;letter-spacing:-2px;
    background:linear-gradient(135deg,#ff4d4d 0%,#ff9a3c 50%,#ffe066 100%);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.hero-sub{
    font-family:'Space Mono',monospace;font-size:.7rem;color:#444;
    letter-spacing:3px;text-transform:uppercase;margin-bottom:1.5rem;
}
.stTabs [data-baseweb="tab-list"]{background:#0f0f1a;border-radius:10px;padding:4px;gap:4px;}
.stTabs [data-baseweb="tab"]{
    background:transparent;border-radius:8px;color:#555;
    font-family:'Syne',sans-serif;font-weight:700;font-size:.85rem;padding:.4rem 1.2rem;
}
.stTabs [aria-selected="true"]{background:#1e1e30!important;color:#e8e8e8!important;}
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
    font-weight:700!important;font-size:.9rem!important;padding:.6rem 1.6rem!important;width:100%;
}
.stButton>button:hover{opacity:.85!important;transform:translateY(-1px)!important;}
.dl-btn{
    display:block;width:100%;padding:.65rem 1.8rem;
    background:linear-gradient(135deg,#22c55e,#16a34a);color:#fff!important;
    border:none;border-radius:10px;font-family:'Syne',sans-serif;font-weight:700;
    font-size:.9rem;text-align:center;text-decoration:none!important;
    cursor:pointer;margin-top:.5rem;box-sizing:border-box;
}
.dl-btn:hover{opacity:.85;}
.api-card{
    background:#0c0c18;border:1px solid #1e1e2e;border-radius:12px;
    padding:1rem 1.2rem;margin:.5rem 0;
}
.api-method{
    display:inline-block;padding:2px 10px;border-radius:5px;
    font-family:'Space Mono',monospace;font-size:.72rem;font-weight:700;margin-right:8px;
}
.get{background:#0d2a0d;color:#4ade80;border:1px solid #1a3a1a;}
.api-path{font-family:'Space Mono',monospace;font-size:.85rem;color:#e8e8e8;}
.api-desc{font-family:'Space Mono',monospace;font-size:.68rem;color:#555;margin-top:.25rem;}
.vtitle{font-family:'Syne',sans-serif;font-weight:700;font-size:1.05rem;color:#e8e8e8;margin:.6rem 0 .2rem;}
.badge{
    display:inline-block;background:#1a1a28;border:1px solid #252538;
    border-radius:6px;padding:2px 9px;font-family:'Space Mono',monospace;
    font-size:.68rem;color:#777;margin-right:5px;
}
.divider{border:none;border-top:1px solid #1a1a28;margin:1.2rem 0;}
.info-box{
    background:#0d1a0d;border:1px solid #1a3a1a;border-radius:10px;
    padding:.75rem 1rem;font-family:'Space Mono',monospace;font-size:.73rem;color:#4ade80;margin:.7rem 0;
}
.warn-box{
    background:#1a140d;border:1px solid #3a2a1a;border-radius:10px;
    padding:.75rem 1rem;font-family:'Space Mono',monospace;font-size:.73rem;color:#fb923c;margin:.7rem 0;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def is_valid_yt(url: str) -> bool:
    return bool(re.match(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+", url.strip()))

def fmt_dur(s) -> str:
    if not s: return "—"
    h, r = divmod(int(s), 3600); m, sec = divmod(r, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"

def fmt_views(n) -> str:
    if not n: return "—"
    return f"{n/1e6:.1f}M" if n>=1e6 else f"{n/1e3:.1f}K" if n>=1e3 else str(n)

def human_size(b) -> str:
    if not b: return "?"
    if b>=1_073_741_824: return f"{b/1_073_741_824:.1f} GB"
    if b>=1_048_576:     return f"{b/1_048_576:.1f} MB"
    return f"{b/1024:.0f} KB"


@st.cache_data(show_spinner=False, ttl=240)
def cached_info(url: str) -> dict:
    return _extract(url)


def build_ui_formats(info: dict) -> list:
    raw, out, seen = info.get("formats", []), [], set()
    # audio
    af = [f for f in raw if f.get("vcodec")=="none" and f.get("acodec") not in (None,"none") and f.get("url")]
    if af:
        b = max(af, key=lambda f: f.get("abr") or f.get("tbr") or 0)
        out.append({"label":f"🎵 Audio  ({b.get('abr','?')} kbps · {b.get('ext','m4a')})",
                    "url":b["url"],"ext":b.get("ext","m4a"),
                    "filesize":b.get("filesize") or b.get("filesize_approx"),
                    "is_audio":True,"filename":f"{info.get('title','audio')}.{b.get('ext','m4a')}"})
    # muxed
    for f in sorted([f for f in raw if f.get("vcodec") not in (None,"none") and f.get("acodec") not in (None,"none") and f.get("url")],
                    key=lambda f: f.get("height") or 0, reverse=True):
        h = f.get("height") or 0
        if h and h not in seen:
            seen.add(h); ext = f.get("ext","mp4")
            out.append({"label":f"🎬 {h}p {ext.upper()} — video+audio","url":f["url"],"ext":ext,
                        "filesize":f.get("filesize") or f.get("filesize_approx"),
                        "is_audio":False,"filename":f"{info.get('title','video')}_{h}p.{ext}"})
    # video-only dash
    for f in sorted([f for f in raw if f.get("vcodec") not in (None,"none") and f.get("acodec") in (None,"none") and f.get("url")],
                    key=lambda f: f.get("height") or 0, reverse=True):
        h = f.get("height") or 0
        if h and h not in seen:
            seen.add(h); ext = f.get("ext","mp4")
            out.append({"label":f"🎬 {h}p {ext.upper()} — video only (no audio)","url":f["url"],"ext":ext,
                        "filesize":f.get("filesize") or f.get("filesize_approx"),
                        "is_audio":False,"filename":f"{info.get('title','video')}_{h}p_video.{ext}"})
    if not out and info.get("url"):
        out.append({"label":"🎬 Best available","url":info["url"],"ext":info.get("ext","mp4"),
                    "filesize":None,"is_audio":False,"filename":f"{info.get('title','video')}.{info.get('ext','mp4')}"})
    return out


# ─────────────────────────────────────────────────────────────────────────────
# UI LAYOUT
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="hero-title">YT Downloader</div>', unsafe_allow_html=True)
st.markdown(f'<div class="hero-sub">UI + REST API · port {_API_PORT} · No 403</div>', unsafe_allow_html=True)

tab_dl, tab_api = st.tabs(["▶️  Downloader", "🔌  API Docs"])


# ── TAB 1: DOWNLOADER ─────────────────────────────────────────────────────────
with tab_dl:
    url_in = st.text_input("url", placeholder="https://youtube.com/watch?v=...", label_visibility="collapsed")
    c1, _ = st.columns([1, 2])
    with c1:
        go = st.button("🔍 Fetch Info")

    if go:
        u = (url_in or "").strip()
        if not u:
            st.error("Paste a YouTube URL above.")
        elif not is_valid_yt(u):
            st.error("Not a valid YouTube URL.")
        else:
            with st.spinner("Fetching…"):
                try:
                    info = cached_info(u)
                    st.session_state.update({"info": info, "url": u, "fmts": build_ui_formats(info)})
                except Exception as exc:
                    st.error(f"Fetch failed: {exc}")

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
        st.markdown(
            '<div class="info-box">✅ Direct CDN link — your browser downloads straight from YouTube. Zero server bytes = zero 403.</div>',
            unsafe_allow_html=True,
        )

        labels = [f["label"] for f in fmts]
        idx    = st.selectbox("Format", range(len(labels)), format_func=lambda i: labels[i])
        chosen = fmts[idx]
        st.caption(f"~{human_size(chosen['filesize'])}")

        safe_name = re.sub(r'[^\w\s\-.]', '', chosen["filename"])[:100]
        st.markdown(
            f'<a class="dl-btn" href="{chosen["url"]}" download="{safe_name}" target="_blank">'
            f'⬇️&nbsp; Download &nbsp;{safe_name[:50]}{"…" if len(safe_name)>50 else ""}</a>',
            unsafe_allow_html=True,
        )
        with st.expander("📋 Copy direct URL (IDM / aria2 / VLC)"):
            st.code(chosen["url"], language=None)

        st.markdown(
            '<div class="warn-box">⚠️ CDN URLs expire in ~6 hours. Download immediately. Click Fetch again if link stops working.</div>',
            unsafe_allow_html=True,
        )


# ── TAB 2: API DOCS ──────────────────────────────────────────────────────────
with tab_api:
    st.markdown(f"### 🔌 REST API — port `{_API_PORT}`")
    st.markdown(
        f"**Swagger UI** → `http://localhost:{_API_PORT}/docs`  \n"
        f"**ReDoc**      → `http://localhost:{_API_PORT}/redoc`"
    )
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    ENDPOINTS = [
        {
            "path": "/health",
            "desc": "Health check.",
            "example": f"curl http://localhost:{_API_PORT}/health",
            "response": '{"status":"ok","service":"YT Downloader API","version":"2.1.0"}',
        },
        {
            "path": f"/api/info?url={{youtube_url}}",
            "desc": "Full metadata + all formats with direct CDN URLs.",
            "example": f'curl "http://localhost:{_API_PORT}/api/info?url=https://youtu.be/dQw4w9WgXcQ"',
            "response": '{"id":"dQw4w9WgXcQ","title":"...","duration":212,"formats":[{"format_id":"22","kind":"muxed","ext":"mp4","height":720,"url":"https://..."},...]}',
        },
        {
            "path": "/api/formats?url={youtube_url}",
            "desc": "Format list only — lighter than /api/info.",
            "example": f'curl "http://localhost:{_API_PORT}/api/formats?url=https://youtu.be/dQw4w9WgXcQ"',
            "response": '{"id":"...","title":"...","formats":[...]}',
        },
        {
            "path": "/api/stream?url={youtube_url}&format_id={id}",
            "desc": "Single direct CDN URL for one format. Omit format_id for best available.",
            "example": f'curl "http://localhost:{_API_PORT}/api/stream?url=https://youtu.be/dQw4w9WgXcQ&format_id=22"',
            "response": '{"title":"...","format_id":"22","ext":"mp4","height":720,"stream_url":"https://...","expires_in":"~6 hours"}',
        },
        {
            "path": "/api/search?q={query}&max_results=5",
            "desc": "Search YouTube. Returns title, url, thumbnail, duration, views.",
            "example": f'curl "http://localhost:{_API_PORT}/api/search?q=lofi+hip+hop&max_results=3"',
            "response": '{"query":"lofi hip hop","results":[{"id":"...","title":"...","url":"...","thumbnail":"...","duration":3600}]}',
        },
    ]

    for ep in ENDPOINTS:
        st.markdown(
            f'<div class="api-card">'
            f'<span class="api-method get">GET</span>'
            f'<span class="api-path">{ep["path"]}</span>'
            f'<div class="api-desc">{ep["desc"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        with st.expander(f"Example — {ep['path'].split('?')[0]}"):
            st.markdown("**Request:**")
            st.code(ep["example"], language="bash")
            st.markdown("**Response:**")
            st.code(ep["response"], language="json")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown("### 🐍 Python")
    st.code(f"""import requests

BASE = "http://localhost:{_API_PORT}"

# Get all formats
info = requests.get(f"{{BASE}}/api/info", params={{"url": "https://youtu.be/dQw4w9WgXcQ"}}).json()
print(info["title"])

# Best muxed (video+audio) stream URL
muxed = [f for f in info["formats"] if f["kind"] == "muxed"]
stream_url = muxed[0]["url"]   # open this in your browser or IDM — never 403

# Search
res = requests.get(f"{{BASE}}/api/search", params={{"q": "lofi", "max_results": 3}}).json()
for r in res["results"]:
    print(r["title"], r["url"])
""", language="python")

    st.markdown("### 🌐 JavaScript")
    st.code(f"""const BASE = "http://localhost:{_API_PORT}";

const info = await fetch(`${{BASE}}/api/info?url=https://youtu.be/dQw4w9WgXcQ`).then(r=>r.json());
const best = info.formats.find(f => f.kind === "muxed");

// Trigger browser download
const a = document.createElement("a");
a.href = best.url;
a.download = `${{info.title}}.${{best.ext}}`;
a.click();
""", language="javascript")


# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown('<hr class="divider">', unsafe_allow_html=True)
st.markdown(
    '<p style="font-family:\'Space Mono\',monospace;font-size:.62rem;color:#2a2a2a;text-align:center;">'
    'Powered by yt-dlp + FastAPI + Streamlit · Personal/educational use only'
    '</p>',
    unsafe_allow_html=True,
)
