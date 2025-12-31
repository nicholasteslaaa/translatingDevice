import sounddevice as sd
from scipy.io.wavfile import write
import os
from STT_model import speech_to_text
from translator import translator
from TTS_model import text_to_speech
from playsound import playsound 

class MicrophoneRecorder:
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.stt = speech_to_text()
        self.translateModel = translator()
        self.tts = text_to_speech()

    def record(self, duration=5, filename="input_mic.wav"):
        print(f"--- Recording for {duration} seconds ---")
        
        # Capture audio from mic
        # mono (channels=1) is best for speech recognition
        recording = sd.rec(int(duration * self.sample_rate), 
                           samplerate=self.sample_rate, 
                           channels=1)
        
        sd.wait()  # Wait until recording is finished
        print("--- Recording Finished ---")
        
        
        # Save as WAV file
        write(filename, self.sample_rate, recording)
        text = self.stt.transcribe(filename,"english")
        print(text)
        translatedText = self.translateModel.translate(text,"english","japanese")
        print(translatedText)
        ttsFilename = self.tts.generate(translatedText,"japanese")
        playsound(f"D:/education/ProjectPribadi/translatorMic/output/{ttsFilename}")
        return filename

if __name__ == "__main__":
    mic = MicrophoneRecorder()
    mic.record()