
import streamlit as st
import os
import json
import requests
from gtts import gTTS
from google import genai
from google.genai import types
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips

# --- SETUP KEYS ---
GEMINI_KEY = st.secrets["GEMINI_KEY"]
PEXELS_KEY = st.secrets["PEXELS_KEY"]

client = genai.Client(api_key=GEMINI_KEY)

# --- UTILITY FUNCTIONS ---
def download_video(url, filename):
    try:
        response = requests.get(url, stream=True)
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024*1024):
                if chunk: f.write(chunk)
        return True
    except: return False

def get_pexels_video(keywords, orientation="landscape"):
    url = f"https://api.pexels.com/v1/videos/search?query={keywords}&per_page=1&orientation={orientation}"
    headers = {"Authorization": PEXELS_KEY}
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if data.get('videos'):
            video_files = data['videos'][0]['video_files']
            return next((f['link'] for f in video_files if f['quality'] == 'hd'), video_files[0]['link'])
    except: return None
    return None

def generate_voiceover(text, lang_code, filename="voiceover.mp3"):
    print(f"🗣️ AI Voiceover ban raha hai language code: {lang_code} ke sath...")
    tts = gTTS(text=text, lang=lang_code)
    tts.save(filename)
    audio = AudioFileClip(filename)
    duration = audio.duration
    audio.close()
    return filename, duration

def create_smart_video(script_scenes, total_audio_duration, final_audio_path, video_mode, orientation_tag, output_filename="smart_output.mp4"):
    num_scenes = len(script_scenes)
    time_per_scene = total_audio_duration / num_scenes
    downloaded_files = []
    clips = []

    target_size = (1280, 720) if video_mode == "YouTube Video (16:9)" else (720, 1280)

    for i, scene in enumerate(script_scenes):
        url = get_pexels_video(scene['search_keywords'], orientation=orientation_tag)
        if url:
            temp_name = f"temp_{i}.mp4"
            if download_video(url, temp_name):
                downloaded_files.append((temp_name, time_per_scene))

    try:
        for file_path, duration in downloaded_files:
            raw_clip = VideoFileClip(file_path).resize(newsize=target_size)
            clips.append(raw_clip.subclip(0, min(raw_clip.duration, duration)))

        final_video_only = concatenate_videoclips(clips, method="compose")
        final_audio = AudioFileClip(final_audio_path)
        final_video_with_audio = final_video_only.set_audio(final_audio)
        final_video_with_audio.write_videofile(output_filename, fps=24, codec="libx264", audio_codec="aac", logger=None)
        return output_filename
    except: return None
    finally:
        for file_path, _ in downloaded_files:
            try: os.remove(file_path)
            except: pass

def analyze_script(user_script):
    # AI ab video description ke sath-sath voiceover_text (asli script ki lines) ko bhi alag karega
    prompt = f"""
    You are an expert video editor. Analyze the following video script and break it down into consecutive visual scenes.
    For each scene, capture the exact spoken lines from the script for the voiceover, provide a clear visual description in English, and 2-3 English keywords for stock footage.
    Respond strictly in JSON format as a list of objects like this:
    [
        {{"scene_number": 1, "voiceover_text": "Exact spoken line from the script", "visual_description": "Description of video", "search_keywords": "running dog"}}
    ]
    Script: "{user_script}"
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return json.loads(response.text)
    except: return None

# --- STREAMLIT WEBSITE UI ---
st.set_page_config(page_title="Premium AI Video Editor", page_icon="🎬", layout="wide")
st.title("🎬 Premium Script-To-Video AI Tool")
st.write("Apni script daaliye, scenes review kijiye, aur ek click mein poori edited video download kijiye!")

# Sidebar Settings
st.sidebar.header("⚙️ Video Settings")
video_mode = st.sidebar.selectbox("Video Format Chunye:", ["YouTube Video (16:9)", "Shorts / Reels (9:16)"])
voice_lang = st.sidebar.selectbox("Voiceover Language:", ["Hindi (Indian Accent)", "English (Global Accent)"])

lang_map = {"Hindi (Indian Accent)": "hi", "English (Global Accent)": "en"}
orientation_tag = "landscape" if video_mode == "YouTube Video (16:9)" else "portrait"

user_script = st.text_area("Yahan apni YouTube script paste karein:", height=150, placeholder="Ek sher jungle mein ghoom raha tha...")

if 'scenes_data' not in st.session_state:
    st.session_state.scenes_data = None
if 'user_script_old' not in st.session_state:
    st.session_state.user_script_old = ""

if user_script != st.session_state.user_script_old:
    st.session_state.scenes_data = None
    st.session_state.user_script_old = user_script

if st.button("Pehle Scenes Check Karein 👀"):
    if not user_script:
        st.warning("Pehle koi script toh likho, bhai!")
    else:
        with st.spinner("AI aapki script se individual scenes nikaal raha hai..."):
            scenes = analyze_script(user_script)
            if scenes:
                st.session_state.scenes_data = scenes
            else:
                st.error("AI script samajh nahi paya. Keys check karein.")

# Preview Display
if st.session_state.scenes_data:
    st.success("🎉 AI ne aapki script ke hisaab se niche diye gaye videos dhoondhe hain:")

    for scene in st.session_state.scenes_data:
        st.write(f"### 🎬 Scene {scene['scene_number']}")
        # Ab screen par voiceover ki asli line alag se dikhegi review ke liye
        st.write(f"**🗣️ Line to speak:** {scene.get('voiceover_text', '')}")
        st.write(f"**🖼️ Video Style:** {scene['visual_description']}")

        preview_url = get_pexels_video(scene['search_keywords'], orientation=orientation_tag)
        if preview_url:
            st.video(preview_url)
        else:
            st.info("Is scene ke liye preview video nahi mila.")
        st.markdown("---")

    st.write("### 🚀 Sab sahi hai? Toh ab final video banayein!")

    if st.button("🔥 Full Video Jodh Kar Download Karein"):
        with st.spinner("🎛️ Audio voiceover ban raha hai aur videos cut kiye ja rahe hain..."):

            # AB VOICE OVER MEIN ASLI SCRIPT KA TEXT JAYEGA (Visual plan nahi)
            full_voiceover_text = " ".join([sc.get('voiceover_text', '') for sc in st.session_state.scenes_data])

            # Agar AI se voiceover text khali reh gaya toh backup ke liye user ki direct script use kar lenge
            if not full_voiceover_text.strip():
                full_voiceover_text = user_script

            audio_file, total_duration = generate_voiceover(full_voiceover_text, lang_map[voice_lang])

            final_video_path = create_smart_video(st.session_state.scenes_data, total_duration, audio_file, video_mode, orientation_tag)

            if final_video_path and os.path.exists(final_video_path):
                st.balloons()
                st.success("🏆 Aapki final edited video taiyar hai!")
                st.video(final_video_path)

                with open(final_video_path, "rb") as file:
                    st.download_button(
                        label="⬇️ Final Video Download Karein",
                        data=file,
                        file_name="ai_premium_video.mp4",
                        mime="video/mp4"
                    )
            else:
                st.error("Video merge karne mein dikkat aayi.")
