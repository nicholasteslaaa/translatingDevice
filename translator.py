from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import pandas as pd

class translator:
    def __init__(self):
        model_name = "facebook/nllb-200-distilled-600M"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        self.token = pd.read_csv("translatorToken.csv")
    
    def translate(self,textSource:str,source:str,output:str):
        # set source language
        sourceToken = self.getToken(source)
        outputToken = self.getToken(output)
        
        if (not sourceToken):
            return
        
        self.tokenizer.src_lang = sourceToken

        text_en = textSource

        inputs = self.tokenizer(text_en, return_tensors="pt")

        # force Japanese output
        generated_tokens = self.model.generate(
            **inputs,
            forced_bos_token_id=self.tokenizer.lang_code_to_id[outputToken]
        )

        text_ja = self.tokenizer.decode(generated_tokens[0], skip_special_tokens=True)
        print("Japanese:", text_ja)
        return text_ja
    
    def getToken(self,lang:str):
        langtoken = self.token.loc[self.token["Language"].str.lower() == lang.lower()]
        if (len(langtoken) > 0):
            return langtoken.values[0][1]
        
if __name__ == "__main__":
    translatorModel = translator()
    translated = translatorModel.translate("Hello good afternoon, my name is nicholas","english","japanese")
    print(translated)
    