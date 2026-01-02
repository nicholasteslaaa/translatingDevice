from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import pandas as pd
import torch # 1. Import torch to check for CUDA

class translator:
    def __init__(self):
        model_name = "facebook/nllb-200-3.3B"
        
        # 2. Check if GPU is available
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {self.device}")

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        # 3. Move model to GPU
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(self.device)
        
        self.token = pd.read_csv("translatorToken.csv")
    
    def translate(self, textSource: str, source: str, output: str):
        sourceToken = self.getToken(source)
        outputToken = self.getToken(output)
        
        if not sourceToken:
            print(f"Error: Language '{source}' not found in CSV.")
            return
        
        self.tokenizer.src_lang = sourceToken

        # 4. Move inputs to the same device as the model
        inputs = self.tokenizer(textSource, return_tensors="pt").to(self.device)

        forced_id = self.tokenizer.convert_tokens_to_ids(outputToken)

        generated_tokens = self.model.generate(
            **inputs,
            forced_bos_token_id=forced_id,
            max_length=100,      # Prevent cutting off sentences
            num_beams=5,         # Look at 5 different variations to find the best one
            no_repeat_ngram_size=2 # Prevents the model from getting stuck in a loop
        )

        text_ja = self.tokenizer.decode(generated_tokens[0], skip_special_tokens=True)
        return text_ja
    
    def getToken(self, lang: str):
        langtoken = self.token.loc[self.token["Language"].str.lower() == lang.lower()]
        if (len(langtoken) > 0):
            return langtoken.values[0][1]
        
if __name__ == "__main__":
    translatorModel = translator()
    translated = translatorModel.translate("excuseme", "english", "japanese")
    print(translated)
    