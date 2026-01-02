import os
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from playsound import playsound

# Import your custom modules
from translator import translator
from TTS_model import text_to_speech
from STT_model import speech_to_text

# Global variables for models
translatorModel = None
ttsModel = None
sttModel = None

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
        indonesian_text = sttModel.transcribe(temp_path,"indonesian")
        print(f"User said: {indonesian_text}")
        
        japanese_text = translatorModel.translate(indonesian_text, "indonesian", "japanese")
        print(f"translated: {japanese_text}")
        
        japanese_tts = ttsModel.generate(japanese_text,"japanese")
        playsound(japanese_tts)
        
        english_text = translatorModel.translate(japanese_text, "japanese", "english")
        print(f"translated: {english_text}")
        
        english_tts = ttsModel.generate(english_text,"english")
        playsound(english_tts)
    
        # japanese_text = translatorModel.translate(english_text, "english", "japanese")
        # print(f"Translated: {japanese_text}")
        
        # voice_file = ttsModel.generate(japanese_text, "japanese")
        # print(f"out: {voice_file}")
        # playsound(voice_file)
        
        # japanese_text_out = sttModel.transcribe(voice_file,"japanese")
        # print(japanese_text_out)
        
        # english_text_out = translatorModel.translate(japanese_text_out,"japanese","english")
        # print(english_text_out)
        
        # voice_file_out = ttsModel.generate(english_text_out,"english")
        # playsound(voice_file_out)        

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

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="127.0.0.1",
        port=8000,
        reload=False  # Keep FALSE to avoid reloading heavy models on every save
    )