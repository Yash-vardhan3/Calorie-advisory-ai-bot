import os
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image
import azure.cognitiveservices.speech as speechsdk
import io
import streamlit as st
import json
import requests
import streamlit.components.v1 as components

# Load environment variables
load_dotenv()

# Configure Google Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Azure Speech Service credentials
subscription_key = os.getenv("AZURE_SPEECH_SUBSCRIPTION_KEY")
service_region = os.getenv("AZURE_SPEECH_SERVICE_REGION")

# Initialize session state for conversation history and user preferences
if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []
if 'user_preferences' not in st.session_state:
    st.session_state.user_preferences = {}
if 'transcribed_text' not in st.session_state:
    st.session_state.transcribed_text = ""

# Function to generate response from Google Gemini API
def get_gemini_response(input_text, image_parts, prompt):
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content([input_text, image_parts[0] if image_parts else None, prompt])
    return response.text

# Function to handle multi-turn conversations
def handle_conversation(user_input):
    # Append user input to conversation history
    st.session_state.conversation_history.append(f"User: {user_input}")

    # Generate a response based on the conversation history
    conversation_context = " ".join(st.session_state.conversation_history)
    prompt = f"Continue the conversation based on the following context: {conversation_context}"
    
    # Call Gemini API to get response
    response_text = get_gemini_response(user_input, None, prompt)
    
    # Append bot response to conversation history
    st.session_state.conversation_history.append(f"Bot: {response_text}")
    
    return response_text

# Function to handle dynamic responses based on user preferences
def personalize_response(text):
    if 'name' in st.session_state.user_preferences:
        name = st.session_state.user_preferences['name']
        return text.replace("{name}", name)
    return text

# Function to convert text to speech using Azure
def text_to_speech_azure(text, subscription_key, service_region):
    speech_config = speechsdk.SpeechConfig(subscription=subscription_key, region=service_region)
    audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
    
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    result = synthesizer.speak_text_async(text).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        return result.audio_data
    else:
        return None

# Function to set up the image data for Gemini API
def input_image_setup(uploaded_file):
    if uploaded_file is not None:
        bytes_data = uploaded_file.getvalue()
        image_parts = [{"mime_type": uploaded_file.type, "data": bytes_data}]
        return image_parts
    return None

# Function to handle speech-to-text conversion
def speech_to_text():
    speech_config = speechsdk.SpeechConfig(subscription=subscription_key, region=service_region)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config)
    
    st.info("Listening...")
    
    result = speech_recognizer.recognize_once_async().get()
    
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        st.session_state.transcribed_text = result.text
        st.success(f"Recognized: {result.text}")
    elif result.reason == speechsdk.ResultReason.NoMatch:
        st.warning("No speech could be recognized")
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = speechsdk.CancellationDetails.from_result(result)
        st.error(f"Speech Recognition canceled: {cancellation_details.reason}")
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            st.error(f"Error details: {cancellation_details.error_details}")

# Initialize Streamlit app
st.set_page_config(page_title="Calorie Doctor", layout="wide")
st.header("Welcome to Your Personal Calorie Doctor!")

# Inject Tailwind CSS
st.markdown("""
    <style>
    @import url('https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css');
    </style>
""", unsafe_allow_html=True)

# Sidebar for audio input
with st.sidebar:
    st.header("Audio Input")
    if st.button("Capture Audio Input"):
        with st.spinner("Listening..."):
            speech_to_text()

    # Inject Watson Assistant script below the audio input button
    watson_script = """
    <script>
      window.watsonAssistantChatOptions = {
        integrationID: "56e4d9e6-aa05-43a4-89c0-f642d91961f0",
        region: "au-syd",
        serviceInstanceID: "2633d9e6-87e6-4d43-9765-028742da70fe",
        onLoad: async (instance) => { await instance.render(); }
      };
      setTimeout(function(){
        const t=document.createElement('script');
        t.src="https://web-chat.global.assistant.watson.appdomain.cloud/versions/" + (window.watsonAssistantChatOptions.clientVersion || 'latest') + "/WatsonAssistantChatEntry.js";
        document.head.appendChild(t);
      });
    </script>
    """

    # Include IBM Watson Assistant script
    components.html(watson_script, height=500)  # Adjust the height as needed

# UI Elements for image upload and input
uploaded_file = st.file_uploader("Upload a picture of your meal...", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="Uploaded Image.", use_column_width=True)

input_prompt = """
As your personal Calorie Doctor, I'm here to help you understand the nutritional content of your food. 
Please review the image of your meal and answer the following questions:

1. Based on the image, is this food healthy? I will provide you with a detailed analysis of the nutritional content and factors affecting the healthiness of the food.
2. Calculate the total calorie count for the food items in the image. I'll provide you with the total calories and a breakdown of each item with its calorie content.

Let's get started on keeping your diet in check!
"""

input_text = st.text_input("Input Prompt:", key="input", value=st.session_state.transcribed_text)

# Handle conversation
if input_text:
    with st.spinner("Processing..."):
        response_text = handle_conversation(input_text)
        
        # Personalize response if needed
        response_text = personalize_response(response_text)
        
        # Display the response
        st.subheader("Here's What Your Calorie Doctor Says:")
        st.write(response_text)
        
        # Convert text response to audio
        with st.spinner("Converting text to speech..."):
            audio_content = text_to_speech_azure(response_text, subscription_key, service_region)
        
        if audio_content:
            st.audio(io.BytesIO(audio_content), format='audio/wav')
        else:
            st.error("Error converting text to speech.")

# Tabs for additional features
tab1, tab2 = st.tabs(["Overview", "Settings"])

with tab1:
    st.write("This tab can be used to show an overview of the analysis results or additional information.")

with tab2:
    st.header("Settings")
    
    st.subheader("Language Preferences")
    language = st.selectbox("Choose Language", ["English", "Spanish", "French", "German"])
    
    st.subheader("Theme Settings")
    dark_mode = st.checkbox("Dark Mode")
    
    st.subheader("Voice Settings")
    voice = st.selectbox("Choose Voice", ["Male", "Female"])
    speed = st.slider("Speech Speed", 0.5, 2.0, 1.0)

    st.session_state.user_preferences = {
        "language": language,
        "dark_mode": dark_mode,
        "voice": voice,
        "speed": speed
    }

# Handle user inputs and image processing
if uploaded_file and input_text:
    image_parts = input_image_setup(uploaded_file)
    with st.spinner("Processing image and input..."):
        response = get_gemini_response(input_text, image_parts, input_prompt)
        st.write("Response from Gemini API:", response)
