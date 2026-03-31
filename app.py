import streamlit as st
import yt_dlp
import os
import re
import tempfile
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VAULTDL · YouTube Downloader",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS  — Cyberpunk / Neon-Noir aesthetic
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300&family=Outfit:wght@300;400;600;700;900&display=swap');

:root {
  --bg:      #05050d;
  --surface: #0c0c18;
  --border:  #1a1a30;
  --accent1: #00f0ff;
  --accent2: #ff2d6b;
  --accent3: #ffe500;
  --text:    #d4d4e8;
  --muted:   #3a3a58;
  --success: #00e87a;
  --font-hero: 'Bebas Neue', sans-serif;
  --font-body: 'Outfit', sans-serif;
  --font-mono: 'DM Mono', monospace;
}

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] { font-family: var(--font-body) !important; color: var(--text); }
.stApp { background: var(--bg); min-height: 100vh; }
#MainMenu, footer, header { visibility: hidden !important; }
.block-container { padding-top: 2rem !important; max-width: 780px !important; }

/* Animated grid */
.stApp::before {
  content: '';
  position: fixed; inset: 0;
  background-image:
    linear-gradient(rgba(0,240,255,.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,240,255,.04) 1px, transparent 1px);
  background-size: 44px 44px;
  pointer-events: none; z-index: 0;
}

/* Glow orb */
.stApp::after {
  content: '';
  position: fixed; top: -200px; left: -200px;
  width: 700px; height: 700px;
  background: radial-gradient(circle, rgba(0,240,255,.07) 0%, transparent 70%);
  pointer-events: none; z-index: 0;
  animation: drift 12s ease-in-out infinite alternate;
}
@keyframes drift {
  from { transform: translate(0,0); }
  to   { transform: translate(120px,80px); }
}

/* Hero */
.hero-wrap { position: relative; text-align: center; padding: 3rem 0 2rem; z-index: 1; }
.hero-eyebrow { font-family: var(--font-mono); font-size:.65rem; letter-spacing:6px; color: var(--accent1); text-transform:uppercase; margin-bottom:.6rem; opacity:.8; }
.hero-title {
  font-family: var(--font-hero); font-size: clamp(4rem,14vw,8rem);
  line-height:.92; letter-spacing:4px;
  background: linear-gradient(135deg, var(--accent1) 0%, #fff 40%, var(--accent2) 100%);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
  margin:0; animation: fadeUp .7s ease both;
}
.hero-tagline { font-family: var(--font-mono); font-size:.75rem; color: var(--muted); margin-top:.9rem; letter-spacing:2px; animation: fadeUp .9s ease both; }
.pill-row { display:flex; gap:8px; justify-content:center; margin-top:1.2rem; flex-wrap:wrap; animation: fadeUp 1.1s ease both; }
.pill { background:rgba(0,240,255,.07); border:1px solid rgba(0,240,255,.18); border-radius:999px; padding:4px 14px; font-family: var(--font-mono); font-size:.65rem; color: var(--accent1); letter-spacing:1px; }
.pill.pink { background:rgba(255,45,107,.07); border-color:rgba(255,45,107,.2); color: var(--accent2); }
.pill.yellow { background:rgba(255,229,0,.07); border-color:rgba(255,229,0,.2); color: var(--accent3); }

@keyframes fadeUp { from { opacity:0; transform:translateY(18px); } to { opacity:1; transform:translateY(0); } }

/* Divider */
.neon-divider { border:none; height:1px; background:linear-gradient(90deg,transparent,var(--accent1),transparent); margin:2rem 0; opacity:.25; }

/* Input label */
.input-label { font-family: var(--font-mono); font-size:.65rem; color: var(--accent1); letter-spacing:3px; text-transform:uppercase; margin-bottom:.4rem; }

/* Text input */
.stTextInput > label { display:none !important; }
.stTextInput > div > div { background: var(--surface) !important; border-radius:12px !important; border:1.5px solid var(--border) !important; transition:border-color .2s, box-shadow .2s !important; }
.stTextInput > div > div:focus-within { border-color: var(--accent1) !important; box-shadow:0 0 0 3px rgba(0,240,255,.1), 0 0 24px rgba(0,240,255,.08) !important; }
.stTextInput input { color: var(--text) !important; font-family: var(--font-mono) !important; font-size:.85rem !important; background:transparent !important; padding:.85rem 1.1rem !important; letter-spacing:.5px; }
.stTextInput input::placeholder { color: var(--muted) !important; }

/* Selectbox */
.stSelectbox > label { font-family: var(--font-mono) !important; font-size:.65rem !important; color: var(--accent1) !important; letter-spacing:3px !important; text-transform:uppercase !important; }
.stSelectbox > div > div { background: var(--surface) !important; border:1.5px solid var(--border) !important; border-radius:12px !important; color: var(--text) !important; }
.stSelectbox > div > div:focus-within { border-color: var(--accent2) !important; box-shadow:0 0 0 3px rgba(255,45,107,.1) !important; }

/* Primary button */
.stButton > button {
  width:100% !important;
  background: linear-gradient(135deg, var(--accent1) 0%, #006aff 100%) !important;
  color:#000 !important; font-family: var(--font-body) !important; font-weight:700 !important;
  font-size:.9rem !important; letter-spacing:1.5px !important; text-transform:uppercase !important;
  border:none !important; border-radius:12px !important; padding:.8rem 2rem !important;
  transition:transform .15s, box-shadow .15s, opacity .15s !important;
  box-shadow:0 0 30px rgba(0,240,255,.25) !important;
}
.stButton > button:hover { transform:translateY(-2px) !important; box-shadow:0 0 50px rgba(0,240,255,.4) !important; opacity:.92 !important; }
.stButton > button:active { transform:translateY(0) !important; }

/* Download button */
.stDownloadButton > button {
  width:100% !important;
  background: linear-gradient(135deg, var(--success) 0%, #00a854 100%) !important;
  color:#000 !important; font-family: var(--font-body) !important; font-weight:700 !important;
  font-size:.9rem !important; letter-spacing:1.5px !important; text-transform:uppercase !important;
  border:none !important; border-radius:12px !important; padding:.85rem 2rem !important;
  animation: pulseGlow 2s ease infinite;
}
@keyframes pulseGlow { 0%,100% { box-shadow:0 0 30px rgba(0,232,122,.25); } 50% { box-shadow:0 0 55px rgba(0,232,122,.5); } }
.stDownloadButton > button:hover { transform:translateY(-2px) !important; }

/* Video card */
.vid-card {
  background: var(--surface); border:1px solid var(--border); border-radius:18px;
  overflow:hidden; position:relative; animation: fadeUp .5s ease both;
}
.vid-card::before {
  content:''; position:absolute; inset:0; border-radius:18px; padding:1px;
  background: linear-gradient(135deg, var(--accent1), transparent 60%, var(--accent2));
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: destination-out; mask-composite: exclude; pointer-events:none;
}
.vid-thumb { width:100%; display:block; aspect-ratio:16/9; object-fit:cover; }
.vid-body { padding:1.4rem 1.4rem 1rem; }
.vid-title { font-family: var(--font-body); font-weight:700; font-size:1.05rem; color:#fff; margin:0 0 .7rem; line-height:1.35; }
.meta-row { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:.5rem; }
.meta-chip { background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.08); border-radius:8px; padding:3px 11px; font-family: var(--font-mono); font-size:.68rem; color: var(--muted); }
.meta-chip span { color: var(--text); }
.stat-bar { display:flex; gap:1px; margin:.3rem 0 1rem; }
.stat-seg { height:3px; flex:1; border-radius:2px; background: var(--border); }
.stat-seg.lit { background: linear-gradient(90deg, var(--accent1), var(--accent2)); }

/* Section header */
.section-hdr { font-family: var(--font-mono); font-size:.62rem; letter-spacing:4px; color: var(--accent2); text-transform:uppercase; margin:1.8rem 0 .6rem; }

/* Alerts */
.stAlert { border-radius:12px !important; font-family: var(--font-mono) !important; font-size:.78rem !important; }
.stSpinner > div { border-top-color: var(--accent1) !important; }

/* Success banner */
.success-banner {
  background:rgba(0,232,122,.07); border:1px solid rgba(0,232,122,.2); border-radius:12px;
  padding:.9rem 1.2rem; font-family: var(--font-mono); font-size:.75rem; color: var(--success);
  text-align:center; letter-spacing:1px; margin-bottom:.8rem; animation: fadeUp .4s ease both;
}

/* How it works cards */
.how-card { text-align:center; padding:1.2rem .5rem; }
.how-icon { font-size:2rem; margin-bottom:.5rem; }
.how-step { font-family: var(--font-mono); font-size:.62rem; letter-spacing:2px; margin-bottom:.4rem; }
.how-title { font-family: var(--font-body); font-weight:600; font-size:.85rem; color:#d4d4e8; }
.how-desc { font-family: var(--font-mono); font-size:.65rem; color: var(--muted); margin-top:.3rem; }

/* Progress bar */
.stProgress > div > div > div > div { background: linear-gradient(90deg, var(--accent1), var(--accent2)) !important; }

/* Scrollbar */
::-webkit-scrollbar { width:5px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius:3px; }

/* Footer */
.footer { text-align:center; padding:2.5rem 0 1.5rem; font-family: var(--font-mono); font-size:.6rem; color: var(--muted); letter-spacing:2px; opacity:.6; }
.footer a { color: var(--accent1); text-decoration:none; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def is_valid_youtube_url(url: str) -> bool:
    return bool(re.match(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+", url.strip()))

def fmt_duration(secs):
    if not secs: return "—"
    h, r = divmod(int(secs), 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def fmt_views(n):
    if not n: return "—"
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000: return f"{n/1_000:.0f}K"
    return str(n)

@st.cache_data(show_spinner=False)
def fetch_info(url: str):
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
        return ydl.extract_info(url, download=False)

FORMATS = {
    "⚡  MP4 · 1080p HD":            ("bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]", False),
    "🎬  MP4 · 720p HD":             ("bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",  False),
    "📺  MP4 · 480p":                ("bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]",  False),
    "📱  MP4 · 360p (mobile)":       ("bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]",  False),
    "🎵  MP3 · Audio only (192kbps)":("bestaudio[ext=m4a]/bestaudio/best", True),
}

def download_video(url, fmt_str, is_audio):
    with tempfile.TemporaryDirectory() as tmp:
        pp = [{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"192"}] if is_audio else []
        opts = {
            "format": fmt_str, "outtmpl": os.path.join(tmp, "%(title)s.%(ext)s"),
            "quiet": True, "no_warnings": True, "postprocessors": pp,
            "merge_output_format": None if is_audio else "mp4",
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        files = list(Path(tmp).iterdir())
        if not files: raise FileNotFoundError("No output file produced.")
        f = files[0]
        return f.read_bytes(), f.name


# ─────────────────────────────────────────────────────────────────────────────
# HERO
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-wrap">
  <div class="hero-eyebrow">⚡ Free · Open Source · No Login Required</div>
  <h1 class="hero-title">VAULTDL</h1>
  <p class="hero-tagline">// YouTube video &amp; audio downloader — powered by yt-dlp //</p>
  <div class="pill-row">
    <span class="pill">MP4 1080p</span>
    <span class="pill">MP4 720p</span>
    <span class="pill">MP4 480p</span>
    <span class="pill pink">MP3 Audio</span>
    <span class="pill yellow">ffmpeg engine</span>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown('<hr class="neon-divider">', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# URL INPUT + FETCH
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="input-label">▸ Paste YouTube URL</div>', unsafe_allow_html=True)
url = st.text_input("url", placeholder="https://youtube.com/watch?v=dQw4w9WgXcQ", label_visibility="collapsed")

fetch_btn = st.button("⚡  FETCH VIDEO INFO")

if fetch_btn:
    if not url:
        st.error("Paste a YouTube URL above first.")
    elif not is_valid_youtube_url(url):
        st.error("Invalid YouTube URL — must contain youtube.com or youtu.be")
    else:
        with st.spinner("Connecting to YouTube…"):
            try:
                st.session_state["info"] = fetch_info(url)
                st.session_state["url"]  = url
            except Exception as e:
                st.error(f"Could not fetch video info: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# VIDEO CARD + DOWNLOAD
# ─────────────────────────────────────────────────────────────────────────────
if "info" in st.session_state:
    info = st.session_state["info"]
    url  = st.session_state["url"]

    st.markdown('<hr class="neon-divider">', unsafe_allow_html=True)

    thumb    = info.get("thumbnail", "")
    title    = info.get("title", "Unknown Title")
    uploader = info.get("uploader", "—")
    dur      = fmt_duration(info.get("duration"))
    views    = fmt_views(info.get("view_count"))
    likes    = fmt_views(info.get("like_count"))
    ud       = info.get("upload_date", "")
    if ud and len(ud) == 8:
        ud = f"{ud[6:]}/{ud[4:6]}/{ud[:4]}"

    # sparkline segments
    segs = 24
    lit  = min(segs, max(2, int(info.get("duration", 60)) % segs + 4))
    seg_html = "".join(f'<div class="stat-seg {"lit" if i<lit else ""}"></div>' for i in range(segs))

    st.markdown(f"""
    <div class="vid-card">
      {"<img class='vid-thumb' src='" + thumb + "' />" if thumb else ""}
      <div class="vid-body">
        <div class="vid-title">{title}</div>
        <div class="meta-row">
          <div class="meta-chip">⏱ <span>{dur}</span></div>
          <div class="meta-chip">👁 <span>{views} views</span></div>
          <div class="meta-chip">👍 <span>{likes}</span></div>
          <div class="meta-chip">📺 <span>{uploader}</span></div>
          {"<div class='meta-chip'>📅 <span>" + ud + "</span></div>" if ud else ""}
        </div>
        <div class="stat-bar">{seg_html}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Format picker
    st.markdown('<div class="section-hdr">▸ Select Format &amp; Quality</div>', unsafe_allow_html=True)
    chosen = st.selectbox("FORMAT", list(FORMATS.keys()), index=0, label_visibility="collapsed")
    fmt_str, is_audio = FORMATS[chosen]

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("⬇  DOWNLOAD NOW"):
        prog = st.progress(0, text="Initialising…")
        try:
            prog.progress(10, text="Resolving stream…")
            prog.progress(35, text="Downloading…")
            file_bytes, filename = download_video(url, fmt_str, is_audio)
            prog.progress(85, text="Merging & encoding…")
            prog.progress(100, text="✅ Complete!")
            mime = "audio/mpeg" if is_audio else "video/mp4"
            safe = re.sub(r'[^\w\-_. ]', '_', filename)[:80]
            st.markdown('<div class="success-banner">✅ &nbsp; FILE READY — Click the button below to save</div>', unsafe_allow_html=True)
            st.download_button(f"💾  SAVE FILE  ·  {safe}", data=file_bytes, file_name=safe, mime=mime)
        except Exception as e:
            prog.empty()
            st.error(f"Download failed: {e}")
            st.info("Tip: Some videos are age-gated or geo-blocked. Try another format or video.")

# ─────────────────────────────────────────────────────────────────────────────
# HOW IT WORKS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<hr class="neon-divider">', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
for col, icon, step_color, step, title, desc in [
    (c1, "📋", "var(--accent1)", "STEP 01", "Paste URL",     "Any youtube.com or youtu.be link"),
    (c2, "🎛",  "var(--accent2)", "STEP 02", "Pick Quality",  "1080p · 720p · 480p · MP3"),
    (c3, "💾",  "var(--accent3)", "STEP 03", "Download File", "No watermark · No account"),
]:
    with col:
        st.markdown(f"""
        <div class="how-card">
          <div class="how-icon">{icon}</div>
          <div class="how-step" style="color:{step_color};">{step}</div>
          <div class="how-title">{title}</div>
          <div class="how-desc">{desc}</div>
        </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
  VAULTDL &nbsp;·&nbsp; powered by <a href="https://github.com/yt-dlp/yt-dlp" target="_blank">yt-dlp</a> &amp; ffmpeg
  &nbsp;·&nbsp; personal / educational use only &nbsp;·&nbsp; respect creators &amp; YouTube ToS
</div>
""", unsafe_allow_html=True)
