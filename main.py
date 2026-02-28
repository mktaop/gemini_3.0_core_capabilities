#pip install google-genai st-copy streamlit
#make sure you have at least version 1.52 for google-genai and 1.50 for streamlit
import streamlit as st, os, wave, io, base64, warnings
from google import genai
from google.genai import types
from st_copy import copy_button
warnings.filterwarnings('ignore') 

def setup():
    st.set_page_config(page_title="Multi-Purpose Chatbot",
                       page_icon="🔥",
                       layout="centered",)

    st.markdown("""
    <style>
        section.stMain .block-container {
            padding-top: 2rem;
            padding-bottom: 1rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    hide_menu_style = """
            <style>
            #MainMenu {visibility: hidden;}
            </style>
            """
    st.markdown(hide_menu_style, unsafe_allow_html=True,)
    
    st.sidebar.subheader(":orange[Options]", divider='blue')


def create_wav_file(raw_pcm_data):
    """Wraps raw 24kHz PCM data from Gemini into a playable WAV format."""
    memory_file = io.BytesIO()
    with wave.open(memory_file, 'wb') as wav_file:
        wav_file.setnchannels(1)        # sets to mono
        wav_file.setsampwidth(2)       # sets it to 16-bit
        wav_file.setframerate(24000)   # this is Gemini default output rate
        wav_file.writeframes(raw_pcm_data)
    return memory_file.getvalue()


def play_ghost_audio(audio_bytes):
    """Plays audio in the background via hidden HTML injection."""
    b64 = base64.b64encode(audio_bytes).decode()
    md = f"""
        <audio autoplay style="display:none">
            <source src="data:audio/wav;base64,{b64}" type="audio/wav">
        </audio>
    """
    st.components.v1.html(md, height=0)


def get_clear():
    clear_button=st.sidebar.button("🗑️ Clear Chat", key="clear")
    return clear_button


def audio_choice():
    """Collect user input whether they want to receive an audio response along with the text response."""
    audio_choice = st.sidebar.radio("Audio response",[
                                       "No", "Yes"])
    return audio_choice

def main():
    """Main Code."""
  
    st.header(":blue[:material/search: Explore Gemini 3's capabilities]", anchor=False,)
    
    if get_clear():
        st.session_state.chat_history = []
        st.rerun()
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # we check for whether the user wants to receive audio response as well
    # for a production grade app, we should store this in the session state so we can default it to No upon an rerun, etc
    audio_or_not = audio_choice()

    # we need to set accept file/audio to True and define which file types we want to allow for upload
    # if you want to let the user upload multiple files, then set accept_file="multiple"
    chat_data = st.chat_input("Ask a question or upload a file...", 
                               accept_file=True, 
                               file_type=["pdf","jpg","mp3","mp4","mpg","png","gif","csv","mov"],
                               accept_audio=True,
                               audio_sample_rate=44100)
    if chat_data:
        message_parts = []
      
        """We check for all 3 possible types of input and append it if there."""
        if chat_data.text:
            message_parts.append(types.Part.from_text(text=chat_data.text))
        # if files then we loop through each and append to send to the model
        # this automatically detects mime type and will use files.upload to upload them
        if chat_data.files:
            for uploaded_file in chat_data.files:
                mime_type = uploaded_file.type 
                
                sample_doc = client.files.upload(
                    file=uploaded_file,
                    config=dict(mime_type=mime_type)
                )
                while sample_doc.state.name == "PROCESSING":
                    time.sleep(2)
                    sample_doc = client.files.get(name=sample_doc.name)
                message_parts.append(
                    types.Part.from_uri(
                        file_uri=sample_doc.uri, 
                        mime_type=sample_doc.mime_type
                    )
                )
        if chat_data.audio:
                message_parts.append(types.Part.from_bytes(data=chat_data.audio.read(), mime_type="audio/wav"))

        user_content = types.Content(role="user", parts=message_parts)
        st.session_state.chat_history.append(user_content)
      
        with st.chat_message("user"):
            if chat_data.text:
                st.markdown(chat_data.text)
            if chat_data.files:
                st.caption(f"Sent {len(chat_data.files)} file(s) to Gemini model")
            if chat_data.audio:
                st.caption("Sent [Voice Question]")

        with st.chat_message("assistant", avatar="🧞‍♀️"):
            try:
                chat = client.chats.create(
                    model=model_id, 
                    history=st.session_state.chat_history[:-1],
                    config=types.GenerateContentConfig(
                        response_mime_type="text/plain",
                        thinking_config=types.ThinkingConfig(thinking_level="high",
                                                            include_thoughts=True),
                    )
                )
                response = chat.send_message(message_parts)                 
                st.markdown(response.text)
              
                # this where we show the copy to clipboard icon
                copy_button(
                            response.text,
                            tooltip="Copy model response",
                            copied_label="Copied!",
                            icon="st" 
                           )

                model_content = types.Content(
                    role="model", 
                    parts=[types.Part.from_text(text=response.text)]
                )
                st.session_state.chat_history.append(model_content)
                st.session_state.response_data = response
              
                # see model's thoughts in formulating the response
                with st.expander("See Model's Thought Summaries"):
                    st.write(response.candidates[0].content.parts[0].text)
                
                if audio_or_not == "Yes":
                    with st.spinner("🔊 Generating voice..."):
                        audio_response = client.models.generate_content(
                            model="gemini-2.5-flash-preview-tts",
                            contents=[f"Please read this aloud in the language the response is in: {response.text}"],
                            config=types.GenerateContentConfig(
                                          response_modalities=["AUDIO"],
                                          speech_config=types.SpeechConfig(
                                             voice_config=types.VoiceConfig(
                                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                                   voice_name='Kore',
                                                )
                                             )
                                          ),
                        )
                        )
                    
                        # check for 'data' in the parts
                        for part in audio_response.candidates[0].content.parts:
                            if part.inline_data:
                                # Wrap in WAV header so browser recognizes it
                                playable_wav = create_wav_file(part.inline_data.data)
                                # Autoplay via hidden Ghost Player
                                play_ghost_audio(playable_wav)
           
            except Exception as e:
                st.error(f"Error: {e}")
                           



if __name__ == '__main__':
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    client = genai.Client(api_key=GOOGLE_API_KEY)
    model_id = "gemini-3-flash-preview"
    setup()
    main()
    
