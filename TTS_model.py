# from TTS.api import TTS
# import datetime
# import pandas as pd

# class text_to_speech:
#     def __init__(self):
#         self. tts = TTS(
#                 model_name="tts_models/multilingual/multi-dataset/xtts_v2",
#                 progress_bar=True,
#                 gpu=False  # set True if you have CUDA
#             )
#         self.token = pd.read_csv("ttsToken.csv")
    
#     def generate(self,text:str,lang:str):
#         langToken = self.getToken(lang)
        
#         now = datetime.datetime.now().strftime("%m%d%Y%H%M%S")
#         directoryPath = "output/"
#         filename = f"{now}.wav"
#         finalOutputPath = directoryPath+filename
        
#         self.tts.tts_to_file(
#             text=text,
#             # speaker_wav=r"sample\japanese\female.wav",   # reference voice
#             speaker_wav=self.getVoiceSample(lang),   # reference voice
#             language=langToken,
#             file_path = finalOutputPath,
#             speed = 1.0,
#             length_penalty=1.5
#         )
        
#         print(f"saved at: {finalOutputPath}")
        
#         return filename
    
#     def getToken(self,lang:str):
#         langtoken = self.token.loc[self.token["Language"].str.lower() == lang.lower()]
#         if (len(langtoken) > 0):
#             return langtoken.values[0][1]
        
#     def getVoiceSample(self,lang):
#         return f"sample/{lang}/female.wav"
        
# if __name__ == "__main__":
#     tts = text_to_speech()
#     tts.generate("ツクーバ大学の研究者達は 驚くべきロボット床を作りました", "japanese")

import torch
import os
import datetime
import soundfile as sf
import numpy as np
from kokoro import KModel, KPipeline

class KokoroTTS:
    def __init__(self):
        base_path = "models"
        model_path = os.path.join(base_path, "kokoro-v1_0.pth")
        config_path = os.path.join(base_path, "config.json")
        self.voices_path = os.path.join(base_path, "voices")
        
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Loading local model from {model_path}...")

        # Load the Model ONCE
        self.model = KModel(config=config_path, model=model_path).to(self.device)
        self.model.eval()

        # Create two separate pipelines to handle the rules for each language
        self.pipelines = {
            'japanese': KPipeline(lang_code='j', model=self.model, device=self.device),
            'english': KPipeline(lang_code='a', model=self.model, device=self.device) # 'a' for American English
        }

    def generate(self, text: str, lang: str = 'english'):
        now = datetime.datetime.now().strftime("%m%d%Y%H%M%S")
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"{now}.wav")

        # Select the correct pipeline rules
        pipeline = self.pipelines.get(lang.lower())
        if not pipeline:
            print(f"Error: Language {lang} not supported.")
            return None

        # Load the specific voice tensor
        voice_file = os.path.join(self.voices_path, f"{lang}.pt")
        if not os.path.exists(voice_file):
            print(f"Error: Voice file not found at {voice_file}")
            return None
        
        voice_pack = torch.load(voice_file, weights_only=True).to(self.device)

        # Generate using the SELECTED pipeline
        generator = pipeline(text, voice=voice_pack, speed=1.0)

        all_audio = []
        for _, (_, _, audio) in enumerate(generator):
            if audio is not None:
                all_audio.append(audio)

        if all_audio:
            sf.write(output_file, np.concatenate(all_audio), 24000)
            print(f"Success! Generated {lang} audio: {output_file}")
            return output_file
        return None

if __name__ == "__main__":
    tts = KokoroTTS()
    
    # Use English pipeline + English voice
    # (Make sure you have an english voice file like af_bella.pt or similar)
    tts.generate("Hello, how are you? I'm fine, thank you.",lang="english")
    
    # Use Japanese pipeline + Japanese voice
    tts.generate("こんにちは、お元気ですか？",lang="japanese")