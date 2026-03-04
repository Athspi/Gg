import streamlit as st
from pytubefix import YouTube

st.set_page_config(page_title="YouTube PO Token Fix", page_icon="🛡️")

st.title("🛡️ YouTube Downloader (Token Fix)")
st.write("Streamlit's server is blocked. You must provide a PO Token to bypass the 'Sign in' error.")

# --- 1. INSTRUCTIONS TO GET TOKEN ---
with st.expander("❓ How to get the PO Token & Visitor Data (Required)", expanded=True):
    st.write("1. Go to this generator tool on your computer: [YouTube PO Token Generator](https://github.com/YunzheZJU/youtube-po-token-generator)")
    st.write("2. Follow the instructions there to run it (or look for a web-based alternative).")
    st.write("3. It will give you a **po_token** and **visitor_data**.")
    st.write("4. Paste them below.")

# --- 2. INPUT FIELDS ---
col1, col2 = st.columns(2)
with col1:
    po_token_input = st.text_input("Paste 'po_token' here:", placeholder="MnQK...")
with col2:
    visitor_data_input = st.text_input("Paste 'visitor_data' here:", placeholder="Cgt...")

url = st.text_input("YouTube Video URL:", placeholder="https://www.youtube.com/watch?v=...")

# --- 3. DOWNLOAD LOGIC ---
if st.button("Download Video"):
    if not url:
        st.warning("Please enter a YouTube URL.")
    elif not po_token_input or not visitor_data_input:
        st.error("❌ You must provide BOTH the PO Token and Visitor Data to bypass the block.")
    else:
        try:
            with st.spinner("Authenticating with PO Token..."):
                
                # We pass the tokens directly to pytubefix.
                # 'use_po_token=True' is REMOVED because we are providing them manually.
                yt = YouTube(
                    url, 
                    po_token=po_token_input, 
                    visitor_data=visitor_data_input
                )
                
                # Fetch details
                title = yt.title
                thumbnail = yt.thumbnail_url
                
                # Success Message
                st.success(f"✅ Authenticated! Found: {title}")
                st.image(thumbnail, width=300)
                
                # Get the Stream (Best MP4)
                stream = yt.streams.get_highest_resolution()
                download_url = stream.url
                
                # --- API JSON OUTPUT ---
                st.subheader("API Response (JSON)")
                st.json({
                    "status": "success",
                    "title": title,
                    "po_token_used": True,
                    "download_url": download_url
                })
                
                # --- DOWNLOAD BUTTON ---
                st.subheader("Download Link")
                st.markdown(
                    f'<a href="{download_url}" target="_blank" style="background-color: #d9534f; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">⬇️ Download MP4</a>', 
                    unsafe_allow_html=True
                )
                st.caption("Right-click the button and select 'Save Link As' if it plays in the browser.")

        except Exception as e:
            st.error("Error:")
            st.code(str(e))
            st.write("If this fails, your PO Token might have expired. Generate a new one.")
