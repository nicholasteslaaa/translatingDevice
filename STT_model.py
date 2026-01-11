from faster_whisper import WhisperModel
import torch
import pandas as pd

class speech_to_text:
    def __init__(self, model_size="base"):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.compute_type = "int8_float16" if (self.device == "cuda") else "int8"
        self.model = WhisperModel("deepdml/faster-whisper-large-v3-turbo-ct2", device=self.device, compute_type=self.compute_type)
        self.token = pd.read_csv("ttsToken.csv")

    def transcribe(self, audio_path, lang=None): # Added lang parameter
        # If lang is provided (e.g., "ja"), it skips detection.
        # If lang is None, it auto-detects.
        if (lang != None):
            lang = self.getToken(lang)
        
        segments, info = self.model.transcribe(
            audio_path, 
            beam_size=5, 
            language=lang  # <--- This is where you specify the language
        )

        if lang:
            print(f"Manual Language Set: {lang}")
        else:
            print(f"Detected language '{info.language}' with probability {info.language_probability:.2f}")

        full_text = ""
        for segment in segments:
            full_text += segment.text + " "
        
        return full_text.strip()
    
    def getToken(self,lang:str):
        langtoken = self.token.loc[self.token["Language"].str.lower() == lang.lower()]
        if (len(langtoken) > 0):
            return langtoken.values[0][1]

# # Example usage:
stt = speech_to_text()

# # Force Japanese transcription
# text = stt.transcribe("output/12312025201215.wav", lang="japanese") 
# print(f"You said: {text}")


# # Force English transcription
# text = stt.transcribe("output/12312025201204.wav", lang="en")

# print(f"You said: {text}")