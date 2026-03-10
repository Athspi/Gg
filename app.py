"""
YT Downloader v3.0 — Streamlit UI + FastAPI REST
═══════════════════════════════════════════════════════════════
• Streamlit UI  →  port 8501  (default)
• FastAPI REST  →  port 8000  (background thread, started ONCE at module level)

NEW in v3.0:
  ─ Search tab — live YouTube search with thumbnail cards
  ─ "Use in Downloader" button on search results
  ─ Playlist detection + /api/playlist endpoint
  ─ Subtitle/caption extraction (manual + auto) in UI + /api/subtitles
  ─ POST /api/batch — up to 10 URLs in one call
  ─ /api/stream now returns ffmpeg clip command (start/end params)
  ─ Richer metadata: upload_date, tags, categories, comment_count
  ─ Quick preset buttons: 🎵 Audio / 📺 720p / 📺 1080p / 📺 Best
  ─ Inline embed player toggle (YouTube iframe)
  ─ ✂️ Clip/Trim UI with ffmpeg command builder
  ─ Session-scoped download history (last 20)
  ─ aria2c / curl copy snippets in the URL expander
  ─ X-Request-Count + X-Powered-By headers on every API response
  ─ POST badge in API docs

API Endpoints:
  GET  /health
  GET  /api/info?url=
  GET  /api/formats?url=
  GET  /api/stream?url=&format_id=&start=&end=
  GET  /api/search?q=&max_results=5
  GET  /api/subtitles?url=&lang=en
  GET  /api/playlist?url=&max_items=50
  POST /api/batch   body: {"urls":[...], "format_id":"optional"}
  Swagger UI → http://localhost:8000/docs
  ReDoc      → http://localhost:8000/redoc
"""

# ── std-lib ────────────────────────────────────────────────────────────────────
import re
import threading
import urllib.parse
from datetime import datetime
from typing import List, Optional

# ── FastAPI ────────────────────────────────────────────────────────────────────
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import yt_dlp

# ══════════════════════════════════════════════════════════════════════════════
# SHARED YT-DLP HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _ydl_base() -> dict:
    return {
        "quiet":             True,
        "no_warnings":       True,
        "skip_download":     True,
        "geo_bypass":        True,
        "nocheckcertificate":True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer":         "https://www.youtube.com/",
            "Origin":          "https://www.youtube.com",
        },
        "extractor_args": {
            "youtube": {"player_client": ["ios", "android", "web"]}
        },
        "retries":       5,
        "socket_timeout":30,
    }


def _extract(url: str, extra: dict = None) -> dict:
    opts = {**_ydl_base(), **(extra or {})}
    with yt_dlp.YoutubeDL(opts) as ydl:
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


def _rich_meta(info: dict) -> dict:
    """Extract richer metadata fields added in v3.0."""
    upload_raw = info.get("upload_date")          # "YYYYMMDD"
    upload_fmt = None
    if upload_raw and len(upload_raw) == 8:
        try:
            upload_fmt = datetime.strptime(upload_raw, "%Y%m%d").strftime("%b %d, %Y")
        except Exception:
            pass
    return {
        "id":            info.get("id"),
        "title":         info.get("title"),
        "uploader":      info.get("uploader"),
        "uploader_url":  info.get("uploader_url") or info.get("channel_url"),
        "channel_id":    info.get("channel_id"),
        "duration":      info.get("duration"),
        "view_count":    info.get("view_count"),
        "like_count":    info.get("like_count"),
        "comment_count": info.get("comment_count"),
        "thumbnail":     info.get("thumbnail"),
        "description":   (info.get("description") or "")[:800],
        "webpage_url":   info.get("webpage_url"),
        "upload_date":   upload_fmt or upload_raw,
        "categories":    info.get("categories") or [],
        "tags":          (info.get("tags") or [])[:20],
        "is_live":       info.get("is_live", False),
        "age_limit":     info.get("age_limit", 0),
    }


# ══════════════════════════════════════════════════════════════════════════════
# FASTAPI APP
# ══════════════════════════════════════════════════════════════════════════════

api = FastAPI(
    title="YT Downloader API",
    description=(
        "Extract YouTube video info & direct CDN stream URLs via yt-dlp.\n\n"
        "No 403 — CDN URLs are downloaded by the **caller's** browser/IP, not the server.\n\n"
        "**v3.0 additions**: `/api/subtitles`, `/api/playlist`, `POST /api/batch`, "
        "richer metadata (upload_date, tags, categories), clip timestamps on `/api/stream`."
    ),
    version="3.0.0",
)
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── simple in-memory request counter (adds X-Request-Count header) ────────────
_request_counts: dict = {}

@api.middleware("http")
async def _add_headers(request: Request, call_next):
    ip = (request.client.host if request.client else "unknown")
    _request_counts[ip] = _request_counts.get(ip, 0) + 1
    response = await call_next(request)
    response.headers["X-Request-Count"] = str(_request_counts[ip])
    response.headers["X-Powered-By"]    = "yt-dlp + FastAPI"
    return response


# ── Pydantic models ────────────────────────────────────────────────────────────
class BatchRequest(BaseModel):
    urls:      List[str]
    format_id: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@api.get("/health", tags=["status"])
def health():
    return {
        "status":    "ok",
        "service":   "YT Downloader API",
        "version":   "3.0.0",
        "endpoints": [
            "/health", "/api/info", "/api/formats", "/api/stream",
            "/api/search", "/api/subtitles", "/api/playlist", "/api/batch",
        ],
    }


@api.get("/api/info", tags=["youtube"])
def get_info(url: str = Query(..., description="Full YouTube URL")):
    """Full metadata (v3: upload_date, tags, categories, comment_count) + all formats."""
    try:
        info = _extract(url)
    except Exception as e:
        raise HTTPException(400, detail=str(e))
    meta = _rich_meta(info)
    meta["formats"] = _parse_formats(info)
    return meta


@api.get("/api/formats", tags=["youtube"])
def get_formats(url: str = Query(..., description="Full YouTube URL")):
    """Lighter — returns only the format list (skips description/tags)."""
    try:
        info = _extract(url)
    except Exception as e:
        raise HTTPException(400, detail=str(e))
    return {"id": info.get("id"), "title": info.get("title"), "formats": _parse_formats(info)}


@api.get("/api/stream", tags=["youtube"])
def get_stream(
    url:       str           = Query(...,  description="Full YouTube URL"),
    format_id: Optional[str] = Query(None, description="Format ID from /api/formats. Omit for best."),
    start:     Optional[int] = Query(None, description="Clip start time in seconds (informational — generates ffmpeg command)"),
    end:       Optional[int] = Query(None, description="Clip end time in seconds"),
):
    """
    Returns a single direct CDN URL.
    If **start** / **end** are provided the response also includes a ready-to-run
    `ffmpeg_clip_cmd` string so you can trim without re-encoding.
    """
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

        result = {
            "id":         info.get("id"),
            "title":      info.get("title"),
            "format_id":  format_id or "best",
            "ext":        ext,
            "height":     height,
            "stream_url": stream_url,
            "expires_in": "~6 hours",
        }
        if start is not None or end is not None:
            s = start or 0
            e = end   or info.get("duration") or "END"
            result["clip_start"]    = s
            result["clip_end"]      = e
            result["ffmpeg_clip_cmd"] = (
                f'ffmpeg -ss {s} -to {e} -i "{stream_url}" -c copy clip.{ext}'
            )
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, detail=str(e))


@api.get("/api/search", tags=["youtube"])
def search(
    q:           str = Query(...,  description="Search query"),
    max_results: int = Query(5, ge=1, le=20, description="Number of results (1-20)"),
):
    """Search YouTube. Returns title, url, thumbnail, duration, views, upload_date."""
    try:
        opts = {**_ydl_base(), "default_search": "ytsearch", "noplaylist": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{q}", download=False)
        results = []
        for e in (info.get("entries") or []):
            if not e:
                continue
            results.append({
                "id":          e.get("id"),
                "title":       e.get("title"),
                "uploader":    e.get("uploader"),
                "duration":    e.get("duration"),
                "view_count":  e.get("view_count"),
                "thumbnail":   e.get("thumbnail"),
                "upload_date": e.get("upload_date"),
                "url":         e.get("webpage_url") or f"https://youtube.com/watch?v={e.get('id')}",
            })
        return {"query": q, "count": len(results), "results": results}
    except Exception as e:
        raise HTTPException(400, detail=str(e))


@api.get("/api/subtitles", tags=["youtube"])
def get_subtitles(
    url:  str = Query(...,  description="Full YouTube URL"),
    lang: str = Query("en", description="Language code, e.g. en, es, fr, de, ja"),
):
    """
    Returns all available subtitle/caption tracks (manual + auto-generated).
    Use the returned URLs directly in your player or with `ffmpeg -i <url>`.
    """
    try:
        opts = {
            **_ydl_base(),
            "writesubtitles":    True,
            "writeautomaticsub": True,
            "subtitleslangs":    [lang, "en"],
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        subs = info.get("subtitles", {})
        auto = info.get("automatic_captions", {})
        all_lang = sorted(set(list(subs.keys()) + list(auto.keys())))

        def _tracks(d: dict, kind: str) -> list:
            out = []
            for lc, tracks in d.items():
                for t in (tracks or []):
                    if t.get("url"):
                        out.append({"lang": lc, "kind": kind, "ext": t.get("ext"), "url": t["url"]})
            return out

        return {
            "id":               info.get("id"),
            "title":            info.get("title"),
            "available_langs":  all_lang,
            "manual_subtitles": _tracks(subs, "manual"),
            "auto_captions":    _tracks(auto, "auto"),
        }
    except Exception as e:
        raise HTTPException(400, detail=str(e))


@api.get("/api/playlist", tags=["youtube"])
def get_playlist(
    url:       str = Query(...,  description="YouTube playlist or channel URL"),
    max_items: int = Query(50, ge=1, le=200, description="Max entries to return (1-200)"),
):
    """
    Lists all videos in a playlist (flat extract — fast, no format resolution).
    Each entry includes id, title, url, thumbnail, duration.
    """
    try:
        opts = {
            **_ydl_base(),
            "extract_flat": "in_playlist",
            "playlistend":  max_items,
            "noplaylist":   False,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        entries = []
        for e in (info.get("entries") or []):
            if not e:
                continue
            vid_id = e.get("id")
            entries.append({
                "id":        vid_id,
                "title":     e.get("title"),
                "uploader":  e.get("uploader"),
                "duration":  e.get("duration"),
                "url":       e.get("url") or f"https://youtube.com/watch?v={vid_id}",
                "thumbnail": (
                    e.get("thumbnail")
                    or f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg"
                ),
            })

        return {
            "playlist_id":    info.get("id"),
            "playlist_title": info.get("title"),
            "uploader":       info.get("uploader"),
            "count":          len(entries),
            "entries":        entries,
        }
    except Exception as e:
        raise HTTPException(400, detail=str(e))


@api.post("/api/batch", tags=["youtube"])
def batch_info(body: BatchRequest):
    """
    Fetch metadata + stream URL for up to **10** URLs in one call.

    Request body:
    ```json
    {"urls": ["https://youtu.be/aaa", "https://youtu.be/bbb"], "format_id": "22"}
    ```
    Failed URLs return `{"status": "error", "error": "..."}` instead of raising.
    """
    if len(body.urls) > 10:
        raise HTTPException(400, detail="Max 10 URLs per batch request.")
    results = []
    for url in body.urls:
        try:
            opts = {**_ydl_base(), "format": body.format_id or "best[ext=mp4]/best"}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            meta = _rich_meta(info)
            meta["stream_url"]    = (
                info.get("url") or (info.get("formats") or [{}])[-1].get("url")
            )
            meta["formats_count"] = len(info.get("formats") or [])
            results.append({"url": url, "status": "ok", **meta})
        except Exception as e:
            results.append({"url": url, "status": "error", "error": str(e)})
    return {"count": len(results), "results": results}


# ══════════════════════════════════════════════════════════════════════════════
# START API THREAD — module-level (avoids Streamlit ScriptRunContext warning)
# ══════════════════════════════════════════════════════════════════════════════

_API_PORT = 8000

def _run_api():
    uvicorn.run(api, host="0.0.0.0", port=_API_PORT, log_level="error")

if not hasattr(threading, "_yt_api_started"):
    _t = threading.Thread(target=_run_api, daemon=True, name="yt-api")
    _t.start()
    threading._yt_api_started = True  # type: ignore[attr-defined]


# ══════════════════════════════════════════════════════════════════════════════
# STREAMLIT  (imported AFTER thread is started)
# ══════════════════════════════════════════════════════════════════════════════

import streamlit as st

st.set_page_config(page_title="YT Downloader + API", page_icon="▶️", layout="centered")

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Syne', sans-serif; }
.stApp { background: #08080f; color: #e8e8e8; }
#MainMenu, footer, header { visibility: hidden; }

/* ── Hero ── */
.hero-title {
    font-family: 'Syne', sans-serif; font-weight: 800; font-size: 2.8rem;
    letter-spacing: -2px;
    background: linear-gradient(135deg, #ff4d4d 0%, #ff9a3c 50%, #ffe066 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.hero-sub {
    font-family: 'Space Mono', monospace; font-size: .7rem; color: #444;
    letter-spacing: 3px; text-transform: uppercase; margin-bottom: 1.5rem;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: #0f0f1a; border-radius: 10px; padding: 4px; gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent; border-radius: 8px; color: #555;
    font-family: 'Syne', sans-serif; font-weight: 700;
    font-size: .85rem; padding: .4rem 1.2rem;
}
.stTabs [aria-selected="true"] { background: #1e1e30 !important; color: #e8e8e8 !important; }

/* ── Inputs ── */
.stTextInput > div > div > input {
    background: #0f0f18 !important; border: 1.5px solid #2a2a3e !important;
    border-radius: 10px !important; color: #e8e8e8 !important;
    font-family: 'Space Mono', monospace !important;
    font-size: .82rem !important; padding: .7rem 1rem !important;
}
.stTextInput > div > div > input:focus {
    border-color: #ff4d4d !important;
    box-shadow: 0 0 0 2px rgba(255,77,77,.12) !important;
}
.stSelectbox > div > div {
    background: #0f0f18 !important; border: 1.5px solid #2a2a3e !important;
    border-radius: 10px !important; color: #e8e8e8 !important;
}
.stNumberInput > div > div > input {
    background: #0f0f18 !important; border: 1.5px solid #2a2a3e !important;
    border-radius: 10px !important; color: #e8e8e8 !important;
    font-family: 'Space Mono', monospace !important;
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #ff4d4d, #ff7a3c) !important;
    color: #fff !important; border: none !important; border-radius: 10px !important;
    font-family: 'Syne', sans-serif !important; font-weight: 700 !important;
    font-size: .9rem !important; padding: .6rem 1.6rem !important; width: 100%;
}
.stButton > button:hover { opacity: .85 !important; transform: translateY(-1px) !important; }

/* ── Download anchor button ── */
.dl-btn {
    display: block; width: 100%; padding: .65rem 1.8rem;
    background: linear-gradient(135deg, #22c55e, #16a34a);
    color: #fff !important; border: none; border-radius: 10px;
    font-family: 'Syne', sans-serif; font-weight: 700; font-size: .9rem;
    text-align: center; text-decoration: none !important;
    cursor: pointer; margin-top: .5rem; box-sizing: border-box;
}
.dl-btn:hover { opacity: .85; }

/* ── Search result cards ── */
.search-card {
    background: #0c0c18; border: 1px solid #1e1e2e; border-radius: 12px;
    padding: .85rem 1rem; margin: .55rem 0;
    display: flex; gap: 12px; align-items: flex-start;
}
.search-thumb { width: 136px; min-width: 136px; border-radius: 8px; object-fit: cover; }
.search-info  { flex: 1; min-width: 0; }
.search-title {
    font-family: 'Syne', sans-serif; font-weight: 700; font-size: .92rem;
    color: #e8e8e8; margin-bottom: .25rem;
    overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
}
.search-meta {
    font-family: 'Space Mono', monospace; font-size: .65rem;
    color: #555; margin-bottom: .5rem;
}
.open-btn {
    display: inline-block; padding: 3px 14px;
    background: #1a1a28; color: #aaa !important;
    border: 1px solid #2a2a3e; border-radius: 7px;
    font-family: 'Syne', sans-serif; font-weight: 700;
    font-size: .75rem; text-decoration: none !important;
}

/* ── API cards ── */
.api-card {
    background: #0c0c18; border: 1px solid #1e1e2e; border-radius: 12px;
    padding: 1rem 1.2rem; margin: .5rem 0;
}
.api-method {
    display: inline-block; padding: 2px 10px; border-radius: 5px;
    font-family: 'Space Mono', monospace; font-size: .72rem;
    font-weight: 700; margin-right: 8px;
}
.get  { background: #0d2a0d; color: #4ade80; border: 1px solid #1a3a1a; }
.post { background: #1a1a0d; color: #facc15; border: 1px solid #3a3a1a; }
.api-path { font-family: 'Space Mono', monospace; font-size: .85rem; color: #e8e8e8; }
.api-desc {
    font-family: 'Space Mono', monospace; font-size: .68rem;
    color: #555; margin-top: .25rem;
}

/* ── Misc utility ── */
.vtitle {
    font-family: 'Syne', sans-serif; font-weight: 700;
    font-size: 1.05rem; color: #e8e8e8; margin: .6rem 0 .2rem;
}
.badge {
    display: inline-block; background: #1a1a28; border: 1px solid #252538;
    border-radius: 6px; padding: 2px 9px;
    font-family: 'Space Mono', monospace; font-size: .68rem;
    color: #777; margin-right: 5px; margin-bottom: 4px;
}
.badge-green { background: #0d2a0d; border-color: #1a3a1a; color: #4ade80; }
.badge-red   { background: #2a0d0d; border-color: #3a1a1a; color: #f87171; }
.divider     { border: none; border-top: 1px solid #1a1a28; margin: 1.2rem 0; }
.info-box {
    background: #0d1a0d; border: 1px solid #1a3a1a; border-radius: 10px;
    padding: .75rem 1rem; font-family: 'Space Mono', monospace;
    font-size: .73rem; color: #4ade80; margin: .7rem 0;
}
.warn-box {
    background: #1a140d; border: 1px solid #3a2a1a; border-radius: 10px;
    padding: .75rem 1rem; font-family: 'Space Mono', monospace;
    font-size: .73rem; color: #fb923c; margin: .7rem 0;
}
.sub-section {
    font-family: 'Syne', sans-serif; font-weight: 700; font-size: .8rem;
    color: #555; letter-spacing: 2px; text-transform: uppercase;
    margin: 1rem 0 .4rem;
}
.hist-item {
    background: #0c0c18; border: 1px solid #1a1a28; border-radius: 8px;
    padding: .45rem .8rem; margin: .25rem 0;
    font-family: 'Space Mono', monospace; font-size: .7rem; color: #777;
    display: flex; justify-content: space-between; align-items: center; gap: 8px;
}
.hist-title { color: #aaa; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.hist-time  { color: #333; font-size: .6rem; white-space: nowrap; }
.streamlit-expanderHeader {
    background: #0c0c18 !important; border: 1px solid #1e1e2e !important;
    border-radius: 10px !important;
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def is_valid_yt(url: str) -> bool:
    return bool(re.match(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+", url.strip()))

def is_playlist(url: str) -> bool:
    return "playlist?list=" in url or ("/playlist?" in url) or (
        "list=" in url and "watch" not in url
    )

def fmt_dur(s) -> str:
    if not s: return "—"
    h, r = divmod(int(s), 3600)
    m, sec = divmod(r, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"

def fmt_views(n) -> str:
    if not n: return "—"
    return f"{n/1e6:.1f}M" if n >= 1e6 else f"{n/1e3:.1f}K" if n >= 1e3 else str(n)

def human_size(b) -> str:
    if not b: return "?"
    if b >= 1_073_741_824: return f"{b/1_073_741_824:.1f} GB"
    if b >= 1_048_576:     return f"{b/1_048_576:.1f} MB"
    return f"{b/1024:.0f} KB"

def yt_embed_html(video_id: str) -> str:
    return (
        f'<div style="border-radius:12px;overflow:hidden;margin:.8rem 0;">'
        f'<iframe width="100%" height="240" '
        f'src="https://www.youtube.com/embed/{video_id}" '
        f'frameborder="0" allowfullscreen '
        f'style="border-radius:12px;display:block;"></iframe></div>'
    )

@st.cache_data(show_spinner=False, ttl=240)
def cached_info(url: str) -> dict:
    return _extract(url)

@st.cache_data(show_spinner=False, ttl=120)
def cached_search(q: str, n: int) -> list:
    opts = {**_ydl_base(), "default_search": "ytsearch", "noplaylist": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{n}:{q}", download=False)
    results = []
    for e in (info.get("entries") or []):
        if not e:
            continue
        results.append({
            "id":          e.get("id"),
            "title":       e.get("title"),
            "uploader":    e.get("uploader"),
            "duration":    e.get("duration"),
            "view_count":  e.get("view_count"),
            "thumbnail":   e.get("thumbnail"),
            "upload_date": e.get("upload_date"),
            "url":         e.get("webpage_url") or f"https://youtube.com/watch?v={e.get('id')}",
        })
    return results


def build_ui_formats(info: dict) -> list:
    raw, out, seen = info.get("formats", []), [], set()

    # ── audio-only — best bitrate ──────────────────────────────────────────
    af = [
        f for f in raw
        if f.get("vcodec") == "none"
        and f.get("acodec") not in (None, "none")
        and f.get("url")
    ]
    if af:
        b = max(af, key=lambda f: f.get("abr") or f.get("tbr") or 0)
        out.append({
            "label":    f"🎵 Audio  ({b.get('abr','?')} kbps · {b.get('ext','m4a')})",
            "url":      b["url"],
            "ext":      b.get("ext", "m4a"),
            "filesize": b.get("filesize") or b.get("filesize_approx"),
            "is_audio": True,
            "filename": f"{info.get('title','audio')}.{b.get('ext','m4a')}",
        })

    # ── muxed (video + audio) ─────────────────────────────────────────────
    for f in sorted(
        [
            f for f in raw
            if f.get("vcodec") not in (None, "none")
            and f.get("acodec") not in (None, "none")
            and f.get("url")
        ],
        key=lambda f: f.get("height") or 0, reverse=True,
    ):
        h = f.get("height") or 0
        if h and h not in seen:
            seen.add(h)
            ext = f.get("ext", "mp4")
            out.append({
                "label":    f"🎬 {h}p {ext.upper()} — video+audio",
                "url":      f["url"],
                "ext":      ext,
                "filesize": f.get("filesize") or f.get("filesize_approx"),
                "is_audio": False,
                "filename": f"{info.get('title','video')}_{h}p.{ext}",
            })

    # ── video-only DASH ───────────────────────────────────────────────────
    for f in sorted(
        [
            f for f in raw
            if f.get("vcodec") not in (None, "none")
            and f.get("acodec") in (None, "none")
            and f.get("url")
        ],
        key=lambda f: f.get("height") or 0, reverse=True,
    ):
        h = f.get("height") or 0
        if h and h not in seen:
            seen.add(h)
            ext = f.get("ext", "mp4")
            out.append({
                "label":    f"🎬 {h}p {ext.upper()} — video only (no audio)",
                "url":      f["url"],
                "ext":      ext,
                "filesize": f.get("filesize") or f.get("filesize_approx"),
                "is_audio": False,
                "filename": f"{info.get('title','video')}_{h}p_video.{ext}",
            })

    if not out and info.get("url"):
        out.append({
            "label":    "🎬 Best available",
            "url":      info["url"],
            "ext":      info.get("ext", "mp4"),
            "filesize": None,
            "is_audio": False,
            "filename": f"{info.get('title','video')}.{info.get('ext','mp4')}",
        })
    return out


def add_history(title: str, url: str, fmt_label: str):
    if "history" not in st.session_state:
        st.session_state.history = []
    st.session_state.history.insert(0, {
        "title": title,
        "url":   url,
        "fmt":   fmt_label,
        "time":  datetime.now().strftime("%H:%M:%S"),
    })
    st.session_state.history = st.session_state.history[:20]


# ── Session state defaults ─────────────────────────────────────────────────────
for _k, _v in [
    ("info", None), ("url", None), ("fmts", None),
    ("history", []), ("search_results", []), ("search_q", ""),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════

st.markdown('<div class="hero-title">YT Downloader</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="hero-sub">UI + REST API · port {_API_PORT} · yt-dlp · No 403 · v3.0</div>',
    unsafe_allow_html=True,
)

tab_dl, tab_search, tab_api = st.tabs(["▶️  Downloader", "🔍  Search", "🔌  API Docs"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — DOWNLOADER
# ══════════════════════════════════════════════════════════════════════════════

with tab_dl:
    url_in = st.text_input(
        "url",
        placeholder="https://youtube.com/watch?v=...  or  playlist URL",
        label_visibility="collapsed",
    )
    ca, cb, cc = st.columns([2, 1, 1])
    with ca:
        go = st.button("🔍 Fetch Info")
    with cb:
        show_embed = st.checkbox("Embed player", value=False)
    with cc:
        show_desc  = st.checkbox("Description",  value=False)

    if go:
        u = (url_in or "").strip()
        if not u:
            st.error("Paste a YouTube URL above.")
        elif not is_valid_yt(u):
            st.error("Not a valid YouTube URL.")
        else:
            if is_playlist(u):
                st.warning(
                    "⚠️ Playlist detected — fetching first video only for the Downloader tab. "
                    f"Use the API endpoint `/api/playlist?url=...` for the full list."
                )
            with st.spinner("Fetching…"):
                try:
                    info = cached_info(u)
                    st.session_state.update({"info": info, "url": u, "fmts": build_ui_formats(info)})
                except Exception as exc:
                    st.error(f"Fetch failed: {exc}")

    # ── Video result ─────────────────────────────────────────────────────────
    if st.session_state.get("info"):
        info  = st.session_state["info"]
        fmts  = st.session_state["fmts"]
        vid_id = info.get("id", "")

        st.markdown('<hr class="divider">', unsafe_allow_html=True)

        # Thumbnail or embed player
        if show_embed and vid_id:
            st.markdown(yt_embed_html(vid_id), unsafe_allow_html=True)
        else:
            thumb = info.get("thumbnail")
            if thumb:
                st.image(thumb, use_column_width=True)

        # Title
        title_safe = info.get("title", "Unknown")
        st.markdown(f'<div class="vtitle">{title_safe}</div>', unsafe_allow_html=True)

        # Metadata badges
        upload_raw = info.get("upload_date", "")
        year = upload_raw[:4] if upload_raw else "—"
        live_badge = '<span class="badge badge-red">🔴 LIVE</span>' if info.get("is_live") else ""
        st.markdown(
            f'<span class="badge">⏱ {fmt_dur(info.get("duration"))}</span>'
            f'<span class="badge">👁 {fmt_views(info.get("view_count"))}</span>'
            f'<span class="badge">👍 {fmt_views(info.get("like_count"))}</span>'
            f'<span class="badge">📺 {info.get("uploader","—")}</span>'
            f'<span class="badge">📅 {year}</span>'
            f'{live_badge}',
            unsafe_allow_html=True,
        )

        # Tags
        tags = (info.get("tags") or [])[:8]
        if tags:
            tag_html = "".join(f'<span class="badge">{t}</span>' for t in tags)
            st.markdown(tag_html, unsafe_allow_html=True)

        # Optional description
        if show_desc:
            desc = (info.get("description") or "").strip()
            if desc:
                with st.expander("📄 Description"):
                    st.text(desc[:1200] + ("…" if len(desc) > 1200 else ""))

        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        st.markdown(
            '<div class="info-box">✅ Direct CDN link — your browser downloads from YouTube\'s CDN. '
            'Zero server bytes = zero 403.</div>',
            unsafe_allow_html=True,
        )

        # ── Format selector ──────────────────────────────────────────────────
        labels = [f["label"] for f in fmts]
        idx    = st.selectbox("Format", range(len(labels)), format_func=lambda i: labels[i])
        chosen = fmts[idx]

        col_sz, col_ext = st.columns(2)
        col_sz.caption(f"Size: ~{human_size(chosen['filesize'])}")
        col_ext.caption(f"Container: {chosen['ext'].upper()}")

        # ── Quick presets ────────────────────────────────────────────────────
        st.markdown('<div class="sub-section">Quick Presets</div>', unsafe_allow_html=True)
        pc1, pc2, pc3, pc4 = st.columns(4)

        def _best_idx(want_audio=False, want_height=None):
            for i, f in enumerate(fmts):
                if want_audio and f["is_audio"]:
                    return i
                if not want_audio and not f["is_audio"]:
                    if want_height and str(want_height) in f["label"]:
                        return i
                    elif not want_height:
                        return i
            return idx  # fallback

        with pc1:
            if st.button("🎵 Audio Only"):
                idx    = _best_idx(want_audio=True)
                chosen = fmts[idx]
        with pc2:
            if st.button("📺 720p"):
                idx    = _best_idx(want_height=720)
                chosen = fmts[idx]
        with pc3:
            if st.button("📺 1080p"):
                idx    = _best_idx(want_height=1080)
                chosen = fmts[idx]
        with pc4:
            if st.button("📺 Best"):
                idx    = _best_idx()
                chosen = fmts[idx]

        # ── Download link ────────────────────────────────────────────────────
        safe_name = re.sub(r'[^\w\s\-.]', '', chosen["filename"])[:100]
        st.markdown(
            f'<a class="dl-btn" href="{chosen["url"]}" download="{safe_name}" target="_blank">'
            f'⬇️&nbsp; Download &nbsp;{safe_name[:52]}{"…" if len(safe_name) > 52 else ""}</a>',
            unsafe_allow_html=True,
        )

        # ── URL copy + CLI snippets ─────────────────────────────────────────
        with st.expander("📋 Copy URL / CLI snippets (aria2c · curl · VLC)"):
            st.code(chosen["url"], language=None)
            st.markdown("**aria2c**")
            st.code(f'aria2c "{chosen["url"]}" -o "{safe_name}"', language="bash")
            st.markdown("**curl**")
            st.code(f'curl -L "{chosen["url"]}" -o "{safe_name}"', language="bash")
            st.markdown("**VLC**")
            st.code(f'vlc "{chosen["url"]}"', language="bash")

        # ── Clip / Trim builder ─────────────────────────────────────────────
        with st.expander("✂️ Clip / Trim with ffmpeg"):
            cs, ce = st.columns(2)
            clip_s = cs.number_input("Start (seconds)", min_value=0,
                                     value=0, step=5, key="clip_start")
            clip_e = ce.number_input("End (seconds)", min_value=1,
                                     value=int(info.get("duration") or 60),
                                     step=5, key="clip_end")
            st.code(
                f'ffmpeg -ss {clip_s} -to {clip_e} -i "{chosen["url"]}" -c copy clip.{chosen["ext"]}',
                language="bash",
            )
            st.caption("Tip: `-c copy` is instant (no re-encode). For format conversion drop that flag.")

        # ── Subtitles ───────────────────────────────────────────────────────
        with st.expander("💬 Subtitle / Caption URLs"):
            sub_lang = st.text_input("Language code (e.g. en, es, fr, ja)", value="en", key="sub_lang")
            if st.button("Fetch Subtitle Tracks"):
                with st.spinner("Fetching subtitle tracks…"):
                    try:
                        sub_opts = {
                            **_ydl_base(),
                            "writesubtitles":    True,
                            "writeautomaticsub": True,
                            "subtitleslangs":    [sub_lang.strip() or "en", "en"],
                        }
                        with yt_dlp.YoutubeDL(sub_opts) as ydl:
                            si = ydl.extract_info(st.session_state["url"], download=False)
                        all_subs = {
                            **{f"[manual] {k}": v for k, v in (si.get("subtitles") or {}).items()},
                            **{f"[auto]   {k}": v for k, v in (si.get("automatic_captions") or {}).items()},
                        }
                        if all_subs:
                            for lang_key, tracks in all_subs.items():
                                for t in (tracks or []):
                                    if t.get("url"):
                                        st.markdown(f"**{lang_key}** · `{t.get('ext','?')}`")
                                        st.code(t["url"], language=None)
                        else:
                            st.info("No subtitles found for this video.")
                    except Exception as exc:
                        st.error(f"Subtitle fetch failed: {exc}")

        # Record in session history
        add_history(title_safe, st.session_state["url"], chosen["label"])

        st.markdown(
            '<div class="warn-box">⚠️ CDN URLs expire in ~6 hours. '
            'Download immediately — click Fetch again if the link stops working.</div>',
            unsafe_allow_html=True,
        )

        # ── Download history ─────────────────────────────────────────────────
        hist = st.session_state.get("history") or []
        if hist:
            st.markdown('<hr class="divider">', unsafe_allow_html=True)
            st.markdown('<div class="sub-section">Session History</div>', unsafe_allow_html=True)
            for h in hist[:8]:
                st.markdown(
                    f'<div class="hist-item">'
                    f'<span class="hist-title">▶ {h["title"]}</span>'
                    f'<span class="hist-time">{h["time"]} · {h["fmt"][:28]}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            if st.button("🗑 Clear history"):
                st.session_state.history = []
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — SEARCH
# ══════════════════════════════════════════════════════════════════════════════

with tab_search:
    st.markdown("### 🔍 Search YouTube")
    sq1, sq2 = st.columns([4, 1])
    with sq1:
        search_q = st.text_input(
            "sq", placeholder="lofi hip hop · Python tutorial · MrBeast ...",
            label_visibility="collapsed", key="search_input",
        )
    with sq2:
        n_results = st.number_input(
            "Max", min_value=1, max_value=20, value=6, step=1,
        )

    if st.button("🔍 Search"):
        sq = (search_q or "").strip()
        if not sq:
            st.error("Enter a search query.")
        else:
            with st.spinner(f'Searching "{sq}"…'):
                try:
                    st.session_state.search_results = cached_search(sq, int(n_results))
                    st.session_state.search_q       = sq
                except Exception as exc:
                    st.error(f"Search failed: {exc}")

    results = st.session_state.get("search_results") or []
    if results:
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        st.caption(f"{len(results)} results for **{st.session_state.get('search_q','')}**")
        for r in results:
            thumb   = r.get("thumbnail", "")
            title   = r.get("title", "Unknown")
            uploader= r.get("uploader", "—")
            dur     = fmt_dur(r.get("duration"))
            views   = fmt_views(r.get("view_count"))
            vid_url = r.get("url", "")

            # Card HTML
            st.markdown(
                f'<div class="search-card">'
                f'<img class="search-thumb" src="{thumb}" '
                f'     onerror="this.style.display=\'none\'">'
                f'<div class="search-info">'
                f'  <div class="search-title">{title}</div>'
                f'  <div class="search-meta">'
                f'    📺 {uploader} &nbsp;·&nbsp; ⏱ {dur} &nbsp;·&nbsp; 👁 {views}'
                f'  </div>'
                f'  <a class="open-btn" href="{vid_url}" target="_blank">Open on YouTube ↗</a>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
            # Load into Downloader
            if st.button(f"⬇ Use in Downloader", key=f"use_{r['id']}"):
                with st.spinner("Loading formats…"):
                    try:
                        fetched = cached_info(vid_url)
                        st.session_state.update({
                            "info": fetched,
                            "url":  vid_url,
                            "fmts": build_ui_formats(fetched),
                        })
                        st.success("✅ Loaded! Switch to the **▶️ Downloader** tab.")
                    except Exception as exc:
                        st.error(f"Failed to load: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — API DOCS
# ══════════════════════════════════════════════════════════════════════════════

with tab_api:
    st.markdown(f"### 🔌 REST API — port {_API_PORT}")
    st.markdown(
        f"Swagger UI → http://localhost:{_API_PORT}/docs  \n"
        f"ReDoc      → http://localhost:{_API_PORT}/redoc"
    )
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    ENDPOINTS = [
        {
            "method": "GET",
            "path":   "/health",
            "desc":   "Health check + full endpoint list.",
            "example":  f"curl http://localhost:{_API_PORT}/health",
            "response": '{"status":"ok","version":"3.0.0","endpoints":[...]}',
        },
        {
            "method": "GET",
            "path":   "/api/info?url={youtube_url}",
            "desc":   "Full metadata (title, uploader, upload_date, tags, categories, like/view/comment count) + all formats.",
            "example":  f'curl "http://localhost:{_API_PORT}/api/info?url=https://youtu.be/dQw4w9WgXcQ"',
            "response": '{"id":"dQw4w9WgXcQ","title":"...","upload_date":"Oct 25, 2009","tags":[...],"categories":[...],"formats":[...]}',
        },
        {
            "method": "GET",
            "path":   "/api/formats?url={youtube_url}",
            "desc":   "Format list only — lighter than /api/info (no description/tags).",
            "example":  f'curl "http://localhost:{_API_PORT}/api/formats?url=https://youtu.be/dQw4w9WgXcQ"',
            "response": '{"id":"...","title":"...","formats":[{"format_id":"22","kind":"muxed","ext":"mp4","height":720,"url":"..."},...]}',
        },
        {
            "method": "GET",
            "path":   "/api/stream?url={url}&format_id={id}&start={s}&end={e}",
            "desc":   "Single CDN URL. Omit format_id for best. start/end (seconds) adds a ready-to-run ffmpeg clip command.",
            "example":  f'curl "http://localhost:{_API_PORT}/api/stream?url=https://youtu.be/dQw4w9WgXcQ&format_id=22&start=10&end=90"',
            "response": '{"title":"...","stream_url":"...","expires_in":"~6 hours","ffmpeg_clip_cmd":"ffmpeg -ss 10 -to 90 -i \'...\' -c copy clip.mp4"}',
        },
        {
            "method": "GET",
            "path":   "/api/search?q={query}&max_results=5",
            "desc":   "Search YouTube — returns title, url, thumbnail, duration, views, upload_date.",
            "example":  f'curl "http://localhost:{_API_PORT}/api/search?q=lofi+hip+hop&max_results=3"',
            "response": '{"query":"lofi hip hop","count":3,"results":[{"id":"...","title":"...","url":"...","thumbnail":"...","duration":3600}]}',
        },
        {
            "method": "GET",
            "path":   "/api/subtitles?url={youtube_url}&lang=en",
            "desc":   "Returns manual + auto subtitle/caption track URLs. Works with any yt-dlp-supported lang code.",
            "example":  f'curl "http://localhost:{_API_PORT}/api/subtitles?url=https://youtu.be/dQw4w9WgXcQ&lang=en"',
            "response": '{"available_langs":["en","es","fr"],"manual_subtitles":[...],"auto_captions":[{"lang":"en","kind":"auto","ext":"vtt","url":"..."}]}',
        },
        {
            "method": "GET",
            "path":   "/api/playlist?url={playlist_url}&max_items=50",
            "desc":   "List all videos in a playlist or channel (flat extract — fast, no per-video format resolution).",
            "example":  f'curl "http://localhost:{_API_PORT}/api/playlist?url=https://youtube.com/playlist?list=PLxxxx&max_items=20"',
            "response": '{"playlist_title":"...","count":20,"entries":[{"id":"...","title":"...","url":"...","thumbnail":"...","duration":300},...]}',
        },
        {
            "method": "POST",
            "path":   "/api/batch",
            "desc":   "Batch metadata + stream URL for up to 10 URLs. Failed URLs return status=error without aborting the batch.",
            "example":  (
                f'curl -X POST http://localhost:{_API_PORT}/api/batch \\\n'
                f'  -H "Content-Type: application/json" \\\n'
                f'  -d \'{{"urls":["https://youtu.be/aaa","https://youtu.be/bbb"],"format_id":"22"}}\''
            ),
            "response": '{"count":2,"results":[{"url":"...","status":"ok","title":"...","stream_url":"..."},{"url":"...","status":"error","error":"..."}]}',
        },
    ]

    for ep in ENDPOINTS:
        mclass = "get" if ep["method"] == "GET" else "post"
        st.markdown(
            f'<div class="api-card">'
            f'<span class="api-method {mclass}">{ep["method"]}</span>'
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

    # ── Python code sample ───────────────────────────────────────────────────
    st.markdown("### 🐍 Python")
    st.code(f"""\
import requests

BASE = "http://localhost:{_API_PORT}"

# ── Full info + formats ───────────────────────────────────────────────────────
info = requests.get(f"{{BASE}}/api/info",
                    params={{"url": "https://youtu.be/dQw4w9WgXcQ"}}).json()
print(info["title"], "|", info["upload_date"], "|", info["tags"][:3])

# Best muxed stream — open in browser or IDM (never 403)
muxed      = [f for f in info["formats"] if f["kind"] == "muxed"]
stream_url = muxed[0]["url"]

# ── Search ────────────────────────────────────────────────────────────────────
res = requests.get(f"{{BASE}}/api/search",
                   params={{"q": "lofi", "max_results": 3}}).json()
for r in res["results"]:
    print(r["title"], r["url"])

# ── Subtitles ─────────────────────────────────────────────────────────────────
subs = requests.get(f"{{BASE}}/api/subtitles",
                    params={{"url": "https://youtu.be/dQw4w9WgXcQ", "lang": "en"}}).json()
for s in subs["auto_captions"]:
    print(s["lang"], s["ext"], s["url"])

# ── Playlist ──────────────────────────────────────────────────────────────────
pl = requests.get(f"{{BASE}}/api/playlist",
                  params={{"url": "https://youtube.com/playlist?list=PLxxxx",
                           "max_items": 10}}).json()
for v in pl["entries"]:
    print(v["title"], v["url"])

# ── Batch (POST) ──────────────────────────────────────────────────────────────
batch = requests.post(f"{{BASE}}/api/batch", json={{
    "urls": [
        "https://youtu.be/dQw4w9WgXcQ",
        "https://youtu.be/9bZkp7q19f0",
    ],
    "format_id": "22",   # optional — omit for best
}}).json()
for r in batch["results"]:
    print(r["status"], r.get("title"), (r.get("stream_url") or "")[:60])
""", language="python")

    # ── JS code sample ────────────────────────────────────────────────────────
    st.markdown("### 🌐 JavaScript / fetch")
    st.code(f"""\
const BASE = "http://localhost:{_API_PORT}";

// ── Full info ─────────────────────────────────────────────────────────────────
const info = await fetch(`${{BASE}}/api/info?url=https://youtu.be/dQw4w9WgXcQ`)
               .then(r => r.json());
const best = info.formats.find(f => f.kind === "muxed");

// Trigger browser download
const a    = document.createElement("a");
a.href     = best.url;
a.download = `${{info.title}}.${{best.ext}}`;
a.click();

// ── Search ────────────────────────────────────────────────────────────────────
const search = await fetch(`${{BASE}}/api/search?q=lofi&max_results=3`)
                 .then(r => r.json());
search.results.forEach(v => console.log(v.title, v.url));

// ── Batch POST ────────────────────────────────────────────────────────────────
const batch = await fetch(`${{BASE}}/api/batch`, {{
  method:  "POST",
  headers: {{"Content-Type": "application/json"}},
  body:    JSON.stringify({{ urls: ["https://youtu.be/dQw4w9WgXcQ"] }}),
}}).then(r => r.json());
console.log(batch.results[0].stream_url);
""", language="javascript")


# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown('<hr class="divider">', unsafe_allow_html=True)
st.markdown(
    '<p style="font-family:\'Space Mono\',monospace;font-size:.62rem;'
    'color:#2a2a2a;text-align:center;">'
    'Powered by yt-dlp + FastAPI + Streamlit · v3.0 · Personal / educational use only'
    '</p>',
    unsafe_allow_html=True,
)
