"""
YT Downloader — Streamlit UI + built-in REST API
-------------------------------------------------
API runs on port 8502 in a background thread alongside the Streamlit UI.

REST API endpoints:
  GET /api/info?url=<youtube_url>
  GET /api/formats?url=<youtube_url>
  GET /api/stream?url=<youtube_url>&format_id=<id>
  GET /api/search?q=<query>
  GET /health
"""

import threading
import re
import urllib.parse

import streamlit as st
import yt_dlp
import uvicorn
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI APP  (runs on :8502 in a background thread)
# ─────────────────────────────────────────────────────────────────────────────

api = FastAPI(
    title="YT Downloader API",
    description="Extract YouTube video info & direct stream URLs via yt-dlp",
    version="2.0.0",
)

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ydl_opts() -> dict:
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
    with yt_dlp.YoutubeDL(_ydl_opts()) as ydl:
        return ydl.extract_info(url, download=False)


def _parse_formats(info: dict) -> list[dict]:
    raw   = info.get("formats", [])
    out   = []
    seen  = set()

    for f in sorted(raw, key=lambda x: x.get("height") or 0, reverse=True):
        if not f.get("url"):
            continue
        h      = f.get("height")
        vcodec = f.get("vcodec", "none")
        acodec = f.get("acodec", "none")
        ext    = f.get("ext", "?")

        if vcodec == "none" and acodec != "none":
            kind = "audio"
        elif vcodec != "none" and acodec != "none":
            kind = "muxed"
        elif vcodec != "none":
            kind = "video"
        else:
            continue

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


# ── Endpoints ──────────────────────────────────────────────────────────────────

@api.get("/health")
def health():
    return {"status": "ok", "service": "YT Downloader API v2"}


@api.get("/api/info")
def get_info(url: str = Query(..., description="Full YouTube video URL")):
    """
    Returns full video metadata + all available formats.
    """
    try:
        info = _extract(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    fmts = _parse_formats(info)
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
        "formats":     fmts,
    }


@api.get("/api/formats")
def get_formats(url: str = Query(..., description="Full YouTube video URL")):
    """
    Returns only the list of available formats (lighter response).
    """
    try:
        info = _extract(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "id":      info.get("id"),
        "title":   info.get("title"),
        "formats": _parse_formats(info),
    }


@api.get("/api/stream")
def get_stream_url(
    url:       str = Query(..., description="Full YouTube video URL"),
    format_id: str = Query(None, description="Format ID from /api/formats. Omit for best muxed."),
):
    """
    Returns the direct CDN stream URL for a specific format.
    The returned URL can be opened directly in a browser or download manager.
    Note: CDN URLs expire in ~6 hours.
    """
    try:
        opts = {**_ydl_opts()}
        if format_id:
            opts["format"] = format_id
        else:
            opts["format"] = "best[ext=mp4]/best"

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # For a specific format_id, find the matching format
        if format_id:
            fmts = info.get("formats", [])
            match = next((f for f in fmts if f["format_id"] == format_id), None)
            if not match:
                raise HTTPException(status_code=404, detail=f"format_id '{format_id}' not found")
            stream_url = match.get("url")
            ext        = match.get("ext", "mp4")
            height     = match.get("height")
        else:
            stream_url = info.get("url") or (info.get("formats") or [{}])[-1].get("url")
            ext        = info.get("ext", "mp4")
            height     = info.get("height")

        if not stream_url:
            raise HTTPException(status_code=500, detail="Could not extract stream URL")

        return {
            "id":         info.get("id"),
            "title":      info.get("title"),
            "format_id":  format_id or "best",
            "ext":        ext,
            "height":     height,
            "stream_url": stream_url,
            "expires_in": "~6 hours",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@api.get("/api/search")
def search_youtube(
    q:        str = Query(..., description="Search query"),
    max_results: int = Query(5, ge=1, le=20, description="Number of results"),
):
    """
    Search YouTube and return video metadata (no downloading).
    """
    try:
        opts = {
            **_ydl_opts(),
            "default_search": "ytsearch",
            "noplaylist": True,
        }
        search_url = f"ytsearch{max_results}:{q}"
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(search_url, download=False)

        results = []
        for entry in info.get("entries", []):
            if not entry:
                continue
            results.append({
                "id":         entry.get("id"),
                "title":      entry.get("title"),
                "uploader":   entry.get("uploader"),
                "duration":   entry.get("duration"),
                "view_count": entry.get("view_count"),
                "thumbnail":  entry.get("thumbnail"),
                "url":        entry.get("webpage_url") or f"https://youtube.com/watch?v={entry.get('id')}",
            })
        return {"query": q, "results": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Start API in background thread (only once) ─────────────────────────────────

def _start_api():
    uvicorn.run(api, host="0.0.0.0", port=8502, log_level="error")

if "api_started" not in st.session_state:
    t = threading.Thread(target=_start_api, daemon=True)
    t.start()
    st.session_state["api_started"] = True


# ─────────────────────────────────────────────────────────────────────────────
# STREAMLIT PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
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
    margin-bottom:0;
}
.hero-sub{
    font-family:'Space Mono',monospace;font-size:.7rem;color:#444;
    letter-spacing:3px;text-transform:uppercase;margin-bottom:1.5rem;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"]{background:#0f0f1a;border-radius:10px;padding:4px;gap:4px;}
.stTabs [data-baseweb="tab"]{
    background:transparent;border-radius:8px;color:#666;
    font-family:'Syne',sans-serif;font-weight:700;font-size:.85rem;padding:.4rem 1.2rem;
}
.stTabs [aria-selected="true"]{background:#1e1e30!important;color:#e8e8e8!important;}

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
    padding:1.1rem 1.3rem;margin:.6rem 0;
}
.api-method{
    display:inline-block;padding:2px 10px;border-radius:5px;
    font-family:'Space Mono',monospace;font-size:.72rem;font-weight:700;margin-right:8px;
}
.get{background:#0d2a0d;color:#4ade80;border:1px solid #1a3a1a;}
.api-path{font-family:'Space Mono',monospace;font-size:.85rem;color:#e8e8e8;}
.api-desc{font-family:'Space Mono',monospace;font-size:.68rem;color:#555;margin-top:.3rem;}

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
.code-block{
    background:#0a0a14;border:1px solid #1e1e2e;border-radius:8px;
    padding:.8rem 1rem;font-family:'Space Mono',monospace;font-size:.72rem;
    color:#a5b4fc;margin:.4rem 0;word-break:break-all;line-height:1.6;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS (shared with UI)
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
    return f"{n/1e6:.1f}M" if n>=1e6 else f"{n/1e3:.1f}K" if n>=1e3 else str(n)

def human_size(b) -> str:
    if not b: return "?"
    if b >= 1_073_741_824: return f"{b/1_073_741_824:.1f} GB"
    if b >= 1_048_576:     return f"{b/1_048_576:.1f} MB"
    return f"{b/1024:.0f} KB"


@st.cache_data(show_spinner=False, ttl=240)
def cached_info(url: str) -> dict:
    return _extract(url)


def build_ui_formats(info: dict) -> list[dict]:
    raw, out, seen = info.get("formats", []), [], set()
    # audio
    afmts = [f for f in raw if f.get("vcodec")=="none" and f.get("acodec") not in (None,"none") and f.get("url")]
    if afmts:
        b = max(afmts, key=lambda f: f.get("abr") or f.get("tbr") or 0)
        out.append({"label":f"🎵 Audio only  ({b.get('abr','?')} kbps · {b.get('ext','m4a')})",
                    "url":b["url"],"ext":b.get("ext","m4a"),"filesize":b.get("filesize") or b.get("filesize_approx"),
                    "is_audio":True,"filename":f"{info.get('title','audio')}.{b.get('ext','m4a')}"})
    # muxed
    for f in sorted([f for f in raw if f.get("vcodec") not in (None,"none") and f.get("acodec") not in (None,"none") and f.get("url")],
                    key=lambda f: f.get("height") or 0, reverse=True):
        h = f.get("height") or 0
        if h and h not in seen:
            seen.add(h)
            ext = f.get("ext","mp4")
            out.append({"label":f"🎬 {h}p {ext.upper()} (video+audio)","url":f["url"],"ext":ext,
                        "filesize":f.get("filesize") or f.get("filesize_approx"),
                        "is_audio":False,"filename":f"{info.get('title','video')}_{h}p.{ext}"})
    # dash video-only
    for f in sorted([f for f in raw if f.get("vcodec") not in (None,"none") and f.get("acodec") in (None,"none") and f.get("url")],
                    key=lambda f: f.get("height") or 0, reverse=True):
        h = f.get("height") or 0
        if h and h not in seen:
            seen.add(h)
            ext = f.get("ext","mp4")
            out.append({"label":f"🎬 {h}p {ext.upper()} (video only, no audio)","url":f["url"],"ext":ext,
                        "filesize":f.get("filesize") or f.get("filesize_approx"),
                        "is_audio":False,"filename":f"{info.get('title','video')}_{h}p_video.{ext}"})
    if not out and info.get("url"):
        out.append({"label":"🎬 Best available","url":info["url"],"ext":info.get("ext","mp4"),
                    "filesize":None,"is_audio":False,"filename":f"{info.get('title','video')}.{info.get('ext','mp4')}"})
    return out


# ─────────────────────────────────────────────────────────────────────────────
# UI — HEADER
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="hero-title">YT Downloader</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">UI + REST API · No 403 · No login</div>', unsafe_allow_html=True)

tab_dl, tab_api = st.tabs(["▶️  Downloader", "🔌  API Docs"])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — DOWNLOADER
# ─────────────────────────────────────────────────────────────────────────────
with tab_dl:
    url_input = st.text_input("url", placeholder="https://youtube.com/watch?v=...", label_visibility="collapsed")
    c1, _ = st.columns([1, 2])
    with c1:
        fetch_btn = st.button("🔍 Fetch Info")

    if fetch_btn:
        u = (url_input or "").strip()
        if not u:
            st.error("Paste a YouTube URL above.")
        elif not is_valid_yt(u):
            st.error("Not a valid YouTube URL.")
        else:
            with st.spinner("Fetching…"):
                try:
                    info = cached_info(u)
                    st.session_state.update({
                        "info": info,
                        "url":  u,
                        "fmts": build_ui_formats(info),
                        "dl_data": None,
                    })
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
            '<div class="info-box">✅ Direct CDN download — your browser fetches from YouTube directly. Zero server-side download = zero 403.</div>',
            unsafe_allow_html=True,
        )

        labels     = [f["label"] for f in fmts]
        idx        = st.selectbox("Format", range(len(labels)), format_func=lambda i: labels[i])
        chosen     = fmts[idx]
        sz         = human_size(chosen["filesize"]) if chosen["filesize"] else "?"
        st.caption(f"~{sz}")

        safe_name = re.sub(r'[^\w\s\-.]', '', chosen["filename"])[:100]
        st.markdown(
            f'<a class="dl-btn" href="{chosen["url"]}" download="{safe_name}" target="_blank">'
            f'⬇️&nbsp; Download &nbsp;{safe_name[:50]}{"…" if len(safe_name)>50 else ""}'
            f'</a>',
            unsafe_allow_html=True,
        )
        with st.expander("📋 Copy direct URL (IDM / aria2 / VLC)"):
            st.code(chosen["url"], language=None)

        st.markdown(
            '<div class="warn-box">⚠️ CDN URLs expire in ~6 hours. Download immediately. Re-fetch if the link stops working.</div>',
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — API DOCS
# ─────────────────────────────────────────────────────────────────────────────
with tab_api:
    st.markdown("### 🔌 REST API Reference")
    st.markdown(
        "The API runs on **port 8502** on the same host as this app.  \n"
        "Interactive Swagger docs → `http://localhost:8502/docs`  \n"
        "ReDoc → `http://localhost:8502/redoc`"
    )
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    endpoints = [
        {
            "method": "GET",
            "path":   "/health",
            "desc":   "Check if the API is running.",
            "example": "curl http://localhost:8502/health",
            "response": '{"status":"ok","service":"YT Downloader API v2"}',
        },
        {
            "method": "GET",
            "path":   "/api/info?url={youtube_url}",
            "desc":   "Full video metadata + all available formats with direct CDN URLs.",
            "example": 'curl "http://localhost:8502/api/info?url=https://youtube.com/watch?v=dQw4w9WgXcQ"',
            "response": '{"id":"...","title":"...","duration":212,"formats":[{"format_id":"...","kind":"muxed","ext":"mp4","height":720,"url":"https://..."},...]}',
        },
        {
            "method": "GET",
            "path":   "/api/formats?url={youtube_url}",
            "desc":   "Returns only the format list — lighter/faster than /api/info.",
            "example": 'curl "http://localhost:8502/api/formats?url=https://youtu.be/dQw4w9WgXcQ"',
            "response": '{"id":"...","title":"...","formats":[...]}',
        },
        {
            "method": "GET",
            "path":   "/api/stream?url={youtube_url}&format_id={id}",
            "desc":   "Get the direct CDN stream URL for a specific format_id (from /api/formats). Omit format_id for best available.",
            "example": 'curl "http://localhost:8502/api/stream?url=https://youtu.be/dQw4w9WgXcQ&format_id=137"',
            "response": '{"title":"...","format_id":"137","ext":"mp4","height":1080,"stream_url":"https://...","expires_in":"~6 hours"}',
        },
        {
            "method": "GET",
            "path":   "/api/search?q={query}&max_results=5",
            "desc":   "Search YouTube. Returns video metadata list (title, url, thumbnail, duration, views).",
            "example": 'curl "http://localhost:8502/api/search?q=lofi+hip+hop&max_results=3"',
            "response": '{"query":"lofi hip hop","results":[{"id":"...","title":"...","url":"...","thumbnail":"...","duration":3600},...]}',
        },
    ]

    for ep in endpoints:
        st.markdown(
            f'<div class="api-card">'
            f'<span class="api-method get">{ep["method"]}</span>'
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
    st.markdown("### 🐍 Python example")
    st.code("""
import requests

BASE = "http://localhost:8502"

# 1. Get all formats for a video
info = requests.get(f"{BASE}/api/info", params={"url": "https://youtu.be/dQw4w9WgXcQ"}).json()
print(info["title"])

# 2. Pick the first muxed (video+audio) format
muxed = [f for f in info["formats"] if f["kind"] == "muxed"]
best  = muxed[0]
print(best["height"], best["ext"], best["url"])

# 3. Download it using the direct CDN URL (from your machine — no 403!)
import urllib.request
urllib.request.urlretrieve(best["url"], f"{info['title']}.{best['ext']}")

# 4. Search
results = requests.get(f"{BASE}/api/search", params={"q": "lofi hip hop", "max_results": 3}).json()
for r in results["results"]:
    print(r["title"], r["url"])
""", language="python")

    st.markdown("### 🌐 JavaScript / fetch example")
    st.code("""
const BASE = "http://localhost:8502";

// Get formats
const info = await fetch(`${BASE}/api/info?url=https://youtu.be/dQw4w9WgXcQ`).then(r=>r.json());
const muxed = info.formats.filter(f => f.kind === "muxed");

// Direct download link in browser
const a = document.createElement("a");
a.href = muxed[0].url;
a.download = `${info.title}.${muxed[0].ext}`;
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
