import torch
import os
import datetime
import soundfile as sf
import numpy as np
from kokoro import KModel, KPipeline

class text_to_speech:
    def __init__(self):
        base_path = "models"
        model_path = os.path.join(base_path, "kokoro-v1_0.pth")
        config_path = os.path.join(base_path, "config.json")
        self.voices_path = os.path.join(base_path, "voices")
        
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Loading local model from {model_path}...")

        self.model = KModel(config=config_path, model=model_path).to(self.device)
        self.model.eval()

        self.pipelines = {
            'japanese': KPipeline(lang_code='j', model=self.model, device=self.device),
            'english': KPipeline(lang_code='a', model=self.model, device=self.device)
        }

    def generate(self, text: str, lang: str = 'english'):
        now = datetime.datetime.now().strftime("%m%d%Y%H%M%S")
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"{now}.wav")

        pipeline = self.pipelines.get(lang.lower())
        if not pipeline:
            print(f"Error: Language '{lang}' not supported.")
            return None

        voice_file = os.path.join(self.voices_path, f"{lang.lower()}.pt")
        if not os.path.exists(voice_file):
            print(f"Error: Voice file not found at {voice_file}")
            return None
        
        voice_pack = torch.load(voice_file, weights_only=True).to(self.device)

        pipeline.voices[lang.lower()] = voice_pack

        try:
            generator = pipeline(text, voice=lang.lower(), speed=1.0)

            all_audio = []
            for _, (_, _, audio) in enumerate(generator):
                if audio is not None:
                    all_audio.append(audio)

            if all_audio:
                sf.write(output_file, np.concatenate(all_audio), 24000)
                print(f"Success! Generated {lang} audio: {output_file}")
                return output_file
        except Exception as e:
            print(f"Generation failed: {e}")
            import traceback
            traceback.print_exc() # This will show exactly where it fails
            return None
    