import streamlit as st
import yt_dlp

st.set_page_config(page_title="YouTube API Fix", page_icon="🔓")

st.title("🔓 Anti-Block YouTube Downloader")
st.write("This version uses 'Android Client' emulation to bypass HTTP 403 errors.")

video_url = st.text_input("YouTube Video URL:", placeholder="https://www.youtube.com/watch?v=...")

if st.button("Get Link"):
    if video_url:
        with st.spinner("Bypassing YouTube security..."):
            
            # --- THE FIX IS HERE ---
            # We configure yt-dlp to pretend it is an Android device.
            # This often bypasses the 403 Forbidden error on cloud servers.
            ydl_opts = {
                'format': 'best',
                'quiet': True,
                'noplaylist': True,
                # 1. Force IPv4 (sometimes helps with blocks)
                'force_ipv4': True,
                # 2. Use the Android API client instead of the Web client
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                        'player_skip': ['webpage', 'configs', 'js'], 
                    }
                },
                # 3. Spoof the User Agent
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                }
            }
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Extract info
                    info = ydl.extract_info(video_url, download=False)
                    
                    # Prepare data
                    video_title = info.get('title', 'Unknown')
                    direct_url = info.get('url', None)
                    thumbnail = info.get('thumbnail')
                    
                    if direct_url:
                        st.success(f"Success! Found: {video_title}")
                        
                        # Show Thumbnail
                        if thumbnail:
                            st.image(thumbnail, width=300)
                        
                        # JSON Output for API use
                        st.subheader("API Response (JSON)")
                        st.json({
                            "status": "success",
                            "title": video_title,
                            "url": direct_url
                        })
                        
                        # Download Button
                        st.markdown(f'<a href="{direct_url}" target="_blank" style="display: inline-block; padding: 10px 20px; background-color: #FF0000; color: white; text-decoration: none; border-radius: 5px;">Download Video (MP4)</a>', unsafe_allow_html=True)
                        
                        st.info("Note: If the link opens a player, right-click the video and select 'Save Video As'.")
                    else:
                        st.error("Could not find a playable URL. The video might be restricted.")

            except Exception as e:
                st.error("Still getting an error? YouTube updates their blocks daily.")
                st.code(str(e))
                st.write("Try a different video to verify if it's a specific video block.")
    else:
        st.warning("Please enter a URL.")
