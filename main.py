import os
from fastapi import FastAPI, UploadFile, File, Request, Query
from fastapi.responses import FileResponse # Add this import at the top
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from playsound import playsound
import wave
import time
from pydub import AudioSegment

# Import your custom modules
from translator import translator
from TTS_model import text_to_speech
from STT_model import speech_to_text

# Global variables for models
translatorModel = None
ttsModel = None
sttModel = None

# Configuration matches your ESP32 settings
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2 

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load models ONCE when the server starts
    global translatorModel, ttsModel, sttModel
    print("--- Loading AI Models (this may take a moment) ---")
    translatorModel = translator()
    ttsModel = text_to_speech()
    sttModel = speech_to_text()
    print("--- All Models Loaded Successfully ---")
    yield
    # Clean up on shutdown if necessary
    print("--- Shutting down server ---")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/translatingVoice")
async def translating_voice(file: UploadFile = File(...)):
    # 1. Save the uploaded file temporarily so the STT model can read it
    temp_path = "temp_input.webm"
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        english_text = sttModel.transcribe(temp_path,"english")
        print(f"User said: {english_text}")
        
        japanese_text = translatorModel.translate(english_text, "english", "japanese")
        print(f"translated: {japanese_text}")
        
        japanese_tts = ttsModel.generate(japanese_text,"japanese")
        playsound(japanese_tts)
        
        english_text = translatorModel.translate(japanese_text, "japanese", "english")
        print(f"translated: {english_text}")
        
        english_tts = ttsModel.generate(english_text,"english")
        playsound(english_tts)  

        return {
            "original_text": english_text,
            "translated_text": japanese_text,
            "status": "success"
        }
    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}
    finally:
        # Clean up the temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
@app.post("/upload")
async def receive_audio(request: Request,SourceLanguage:str = Query(...),OutputLanguage:str = Query(...)):
    # 1. Read the raw bytes from the ESP32 POST body
    audio_data = await request.body()
    
    if not audio_data:
        return {"status": "error", "message": "No data received"}

    print(SourceLanguage)
    print(OutputLanguage)
    # 2. Create a unique filename
    filename = f"output/rec_{int(time.time())}.wav"

    # 3. Use the wave library to save it with a proper header
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(SAMPLE_WIDTH)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(audio_data)

    print(f"Received {len(audio_data)} bytes. Saved to {filename}")
    
    source_text = sttModel.transcribe(filename,SourceLanguage)
    print(f"User said: {source_text}")
    
    output_text = translatorModel.translate(source_text, SourceLanguage, OutputLanguage)
    print(f"translated: {output_text}")
    
    output_tts = ttsModel.generate(output_text, OutputLanguage)
    
    # 1. Process audio to 16k 16-bit Mono
    # audio = AudioSegment.from_file(output_tts)
    # audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    # audio.export(output_tts, format="wav")
    
    playsound(output_tts)
    
    # if os.path.exists(output_tts):
    #     return FileResponse(path=output_tts, media_type="audio/wav")
    
    return {"status": "error", "message": "TTS generation failed"}

if __name__ == "__main__":
    uvicorn.run(app, host="192.168.1.4", port=8000)