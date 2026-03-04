import streamlit as st
import yt_dlp
import os
import tempfile
import re
from pathlib import Path

st.set_page_config(
    page_title="YT Vault",
    page_icon="⬇️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap');
:root {
    --bg:#0a0a0f; --surface:#12121a; --border:#1e1e2e;
    --accent:#ff3f3f; --text:#f0f0f0; --muted:#6b6b80; --success:#00e5a0;
}
*{box-sizing:border-box;}
html,body,[class*="css"]{font-family:'Syne',sans-serif;background-color:var(--bg)!important;color:var(--text)!important;}
.stApp{background:var(--bg)!important;}
#MainMenu,footer,header{visibility:hidden;}
.hero{text-align:center;padding:3rem 1rem 2rem;}
.hero-title{
    font-size:4rem;font-weight:800;letter-spacing:-2px;
    background:linear-gradient(135deg,#ff3f3f 0%,#ff8c42 50%,#ffd700 100%);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
    background-clip:text;margin:0;line-height:1;
}
.hero-sub{font-family:'Space Mono',monospace;font-size:.8rem;color:var(--muted);letter-spacing:3px;margin-top:.5rem;text-transform:uppercase;}
.divider{width:60px;height:3px;background:linear-gradient(90deg,#ff3f3f,#ff8c42);margin:1.5rem auto;border-radius:2px;}
.stTextInput>div>div>input{
    background:var(--surface)!important;border:2px solid var(--border)!important;
    border-radius:12px!important;color:var(--text)!important;
    font-family:'Space Mono',monospace!important;font-size:.85rem!important;padding:.9rem 1.2rem!important;
}
.stTextInput>div>div>input:focus{border-color:var(--accent)!important;box-shadow:0 0 0 3px rgba(255,63,63,.15)!important;}
.stButton>button{
    background:linear-gradient(135deg,#ff3f3f,#ff8c42)!important;color:white!important;
    border:none!important;border-radius:12px!important;font-family:'Syne',sans-serif!important;
    font-weight:700!important;font-size:1rem!important;padding:.8rem 2.5rem!important;
    width:100%!important;letter-spacing:.5px!important;transition:all .2s!important;
}
.stButton>button:hover{transform:translateY(-2px)!important;box-shadow:0 8px 25px rgba(255,63,63,.35)!important;}
.stDownloadButton>button{
    background:linear-gradient(135deg,#00e5a0,#00bcd4)!important;color:#0a0a0f!important;
    border:none!important;border-radius:12px!important;font-family:'Syne',sans-serif!important;
    font-weight:800!important;font-size:1rem!important;padding:.8rem 2rem!important;width:100%!important;
}
.stDownloadButton>button:hover{transform:translateY(-2px)!important;box-shadow:0 8px 25px rgba(0,229,160,.35)!important;}
.video-card{
    background:var(--surface);border:1px solid var(--border);border-radius:16px;
    padding:1.5rem;margin:1.5rem 0;position:relative;overflow:hidden;
}
.video-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#ff3f3f,#ff8c42,#ffd700);}
.video-title{font-size:1.1rem;font-weight:600;margin-bottom:.8rem;line-height:1.4;color:var(--text);}
.video-meta{font-family:'Space Mono',monospace;font-size:.75rem;color:var(--muted);display:flex;gap:1.5rem;flex-wrap:wrap;margin-top:.5rem;}
.stSelectbox>div>div{background:var(--surface)!important;border:2px solid var(--border)!important;border-radius:12px!important;color:var(--text)!important;}
.status-box{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1rem 1.2rem;font-family:'Space Mono',monospace;font-size:.8rem;color:var(--muted);margin:1rem 0;}
.status-ok{border-color:rgba(0,229,160,.4)!important;color:var(--success)!important;background:rgba(0,229,160,.05)!important;}
.status-err{border-color:rgba(255,63,63,.4)!important;color:#ff6b6b!important;background:rgba(255,63,63,.05)!important;}
.section-label{font-family:'Space Mono',monospace;font-size:.7rem;letter-spacing:2px;text-transform:uppercase;color:var(--muted);margin-bottom:.5rem;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1 class="hero-title">YT VAULT</h1>
    <p class="hero-sub">&#9889; YouTube Video &amp; Audio Downloader</p>
    <div class="divider"></div>
</div>
""", unsafe_allow_html=True)

# ── Helpers ────────────────────────────────────────────────────────────────────
def format_duration(s):
    if not s: return "Unknown"
    h, r = divmod(int(s), 3600); m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def format_views(v):
    if not v: return "Unknown"
    if v>=1_000_000: return f"{v/1_000_000:.1f}M"
    if v>=1_000: return f"{v/1_000:.1f}K"
    return str(v)

def is_valid_yt(url):
    return bool(re.search(r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)', url))

# ── yt-dlp base options — fixes HTTP 403 ──────────────────────────────────────
BASE = {
    'quiet': True,
    'no_warnings': True,
    'socket_timeout': 30,
    'nocheckcertificate': True,
    'http_headers': {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/122.0.0.0 Safari/537.36'
        ),
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://www.youtube.com/',
    },
    # Use Android + Web client to bypass 403 on direct stream URLs
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'],
            'skip': ['hls', 'dash'],
        }
    },
}

def get_info(url):
    with yt_dlp.YoutubeDL({**BASE, 'extract_flat': False}) as ydl:
        return ydl.extract_info(url, download=False)

def get_formats(info):
    fmts = info.get('formats', [])
    vid, aud = {}, {}
    for f in fmts:
        vc, ac, h, abr = f.get('vcodec','none'), f.get('acodec','none'), f.get('height'), f.get('abr')
        if vc!='none' and ac!='none' and h:
            lbl = f"{h}p"
            if lbl not in vid: vid[lbl] = f['format_id']
        if vc=='none' and ac!='none' and abr:
            lbl = f"{int(abr)}kbps"
            if lbl not in aud: aud[lbl] = f['format_id']
    sh = lambda x: int(x[0].replace('p',''))   if x[0].replace('p','').isdigit()   else 0
    sa = lambda x: int(x[0].replace('kbps','')) if x[0].replace('kbps','').isdigit() else 0
    return dict(sorted(vid.items(),key=sh,reverse=True)), dict(sorted(aud.items(),key=sa,reverse=True))

def do_download(url, fmt_id, outdir, mode):
    tmpl = os.path.join(outdir, '%(title)s.%(ext)s')
    if mode == 'audio':
        opts = {**BASE, 'format': f'{fmt_id}/bestaudio/best', 'outtmpl': tmpl,
                'postprocessors': [{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'192'}]}
    else:
        # Chain of fallbacks — avoids 403 by preferring pre-muxed mp4
        fmt = (f'{fmt_id}+bestaudio[ext=m4a]/{fmt_id}+bestaudio/'
               'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/'
               'bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best')
        opts = {**BASE, 'format': fmt, 'outtmpl': tmpl, 'merge_output_format': 'mp4'}
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    files = list(Path(outdir).glob('*'))
    return max(files, key=os.path.getctime) if files else None

# ── Main UI ───────────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">&#128279; Paste YouTube URL</div>', unsafe_allow_html=True)
url = st.text_input("url", placeholder="https://www.youtube.com/watch?v=...", label_visibility="collapsed")
fetch_btn = st.button("&#128269; Fetch Video Info")

for k in ('info','vfmts','afmts'):
    if k not in st.session_state:
        st.session_state[k] = None if k=='info' else {}

if fetch_btn:
    if not url:
        st.markdown('<div class="status-box status-err">&#9888;&#65039; Enter a URL first.</div>', unsafe_allow_html=True)
    elif not is_valid_yt(url):
        st.markdown('<div class="status-box status-err">&#9888;&#65039; Not a valid YouTube URL.</div>', unsafe_allow_html=True)
    else:
        with st.spinner("Fetching…"):
            try:
                info = get_info(url)
                st.session_state.info = info
                vf, af = get_formats(info)
                st.session_state.vfmts = vf
                st.session_state.afmts = af
            except Exception as e:
                st.markdown(f'<div class="status-box status-err">&#10060; {e}</div>', unsafe_allow_html=True)
                st.session_state.info = None

if st.session_state.info:
    info = st.session_state.info
    col1, col2 = st.columns([1, 2])
    with col1:
        thumb = info.get('thumbnail') or (info.get('thumbnails') or [{}])[-1].get('url','')
        if thumb:
            st.image(thumb, width=220)   # width= replaces deprecated use_container_width
    with col2:
        title = info.get('title','Unknown Title')
        ch    = info.get('uploader','Unknown')
        dur   = format_duration(info.get('duration'))
        views = format_views(info.get('view_count'))
        ud    = info.get('upload_date','')
        if len(ud)==8: ud = f"{ud[6:]}/{ud[4:6]}/{ud[:4]}"
        st.markdown(f"""
        <div class="video-card">
          <div class="video-title">{title}</div>
          <div class="video-meta">
            <span>&#128250; {ch}</span><span>&#9201; {dur}</span>
            <span>&#128065; {views} views</span><span>&#128197; {ud}</span>
          </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="section-label">&#127897; Download Mode</div>', unsafe_allow_html=True)
    mode = st.radio("Mode", ["🎬 Video (MP4)", "🎵 Audio Only (MP3)"], horizontal=True, label_visibility="collapsed")

    if "Video" in mode:
        vf = st.session_state.vfmts
        if vf:
            st.markdown('<div class="section-label">&#128208; Quality</div>', unsafe_allow_html=True)
            q = st.selectbox("q", list(vf.keys()), label_visibility="collapsed")
            sel, dl_mode, ext = vf[q], 'video', 'mp4'
        else:
            st.markdown('<div class="status-box status-err">No combined formats. Try Audio mode.</div>', unsafe_allow_html=True)
            sel, dl_mode, ext = None, 'video', 'mp4'
    else:
        af = st.session_state.afmts
        q  = None
        if af:
            st.markdown('<div class="section-label">&#128266; Audio Quality</div>', unsafe_allow_html=True)
            q   = st.selectbox("aq", list(af.keys()), label_visibility="collapsed")
            sel = af[q]
        else:
            sel = 'bestaudio/best'
        dl_mode, ext = 'audio', 'mp3'

    st.markdown("")
    dl_btn = st.button("&#9889; Download Now")

    if dl_btn and sel:
        with st.spinner("Downloading… &#9203;"):
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    out = do_download(url, sel, tmp, dl_mode)
                    if out and Path(out).exists():
                        data = Path(out).read_bytes()
                        name = re.sub(r'[^\w\s-]','', info.get('title','video'))[:50].strip()
                        fname = f"{name}.{ext}"
                        st.markdown('<div class="status-box status-ok">&#9989; Ready! Click below to save.</div>', unsafe_allow_html=True)
                        st.download_button(   # no use_container_width — CSS handles width
                            label=f"&#128190; Save  {fname}",
                            data=data,
                            file_name=fname,
                            mime="video/mp4" if dl_mode=='video' else "audio/mpeg",
                        )
                    else:
                        st.markdown('<div class="status-box status-err">&#10060; File not found after download.</div>', unsafe_allow_html=True)
            except Exception as e:
                err = str(e)
                hint = " — YouTube blocked the stream. Try Audio mode or lower quality." if "403" in err else ""
                st.markdown(f'<div class="status-box status-err">&#10060; {err}{hint}</div>', unsafe_allow_html=True)

st.markdown("""
<div style="text-align:center;padding:3rem 0 1rem;font-family:'Space Mono',monospace;font-size:.7rem;color:#3a3a4a;letter-spacing:1px;">
    YT VAULT &#8212; PERSONAL &amp; EDUCATIONAL USE ONLY<br>
    <span style="color:#ff3f3f;">&#9888;&#65039;</span> Respect YouTube ToS &amp; Creator Rights
</div>""", unsafe_allow_html=True)
