import ctranslate2
import transformers
import pandas as pd
import torch

class translator:
    def __init__(self):
        model_path = "nllb_3.3B_ct2"
        print(f"Loading {model_path} via CTranslate2...")
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.compute_type = "int8_float16" if (self.device == "cuda") else "int8"
        
        self.translator = ctranslate2.Translator(model_path, device=self.device, device_index=0, compute_type=self.compute_type)
        
        self.tokenizer = transformers.AutoTokenizer.from_pretrained(model_path)
        self.token_df = pd.read_csv("translatorToken.csv")
    
    def translate(self, textSource: str, source: str, output: str):
        source_lang = self.getToken(source)
        target_lang = self.getToken(output)
        
        if not source_lang or not target_lang:
            return "Error: Language code not found."

        self.tokenizer.src_lang = source_lang
        
        input_ids = self.tokenizer(textSource, return_tensors="pt").input_ids[0].tolist()
        source_tokens = self.tokenizer.convert_ids_to_tokens(input_ids)

        results = self.translator.translate_batch(
            [source_tokens], 
            target_prefix=[[target_lang]],
            beam_size=5,
            max_batch_size=1024,
            repetition_penalty=1.1
        )

        target_tokens = results[0].hypotheses[0]
        if target_tokens[0] == target_lang:
            target_tokens = target_tokens[1:]
        
        return self.tokenizer.decode(
            self.tokenizer.convert_tokens_to_ids(target_tokens), 
            skip_special_tokens=True
        )

    def getToken(self, lang: str):
        langtoken = self.token_df.loc[self.token_df["Language"].str.lower() == lang.lower()]
        if not langtoken.empty:
            return langtoken.values[0][1]
        return None
    