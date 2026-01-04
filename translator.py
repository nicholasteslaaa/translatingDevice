import ctranslate2
import transformers
import pandas as pd
import os

class translator:
    def __init__(self):
        # 1. Use the LOCAL path for everything
        model_path = "nllb_3.3B_ct2"
        print(f"Loading {model_path} via CTranslate2...")

        self.translator = ctranslate2.Translator(model_path, device="cuda", device_index=0)
        
        # Load tokenizer from the local folder we created
        self.tokenizer = transformers.AutoTokenizer.from_pretrained(model_path)
        self.token_df = pd.read_csv("translatorToken.csv")
    
    def translate(self, textSource: str, source: str, output: str):
        source_lang = self.getToken(source)
        target_lang = self.getToken(output)
        
        if not source_lang or not target_lang:
            return "Error: Language code not found."

        # 2. PROPER TOKENIZATION
        # We set the src_lang so the tokenizer adds the correct special token
        self.tokenizer.src_lang = source_lang
        
        # encode() automatically adds the </s> and the source lang token (e.g., eng_Latn)
        source_tokens = self.tokenizer.convert_ids_to_tokens(
            self.tokenizer.encode(textSource)
        )

        # 3. TRANSLATION WITH TARGET PREFIX
        # Updated translation logic inside your class
        results = self.translator.translate_batch(
            [source_tokens], 
            target_prefix=[[target_lang]],
            beam_size=5,            
            repetition_penalty=1.2, 
            # ADD THESE TWO LINES:
            num_hypotheses=1,       
            max_batch_size=1024,
            # This prevents the model from choosing the "boring/safe" word
            no_repeat_ngram_size=3 
        )

        # 4. CLEAN DECODING
        # results[0].hypotheses[0] will be: ['jpn_Jpan', 'なぜ', '私の', '脇', ...]
        # We MUST remove the first token (the target lang tag)
        target_tokens = results[0].hypotheses[0][1:] 
        
        return self.tokenizer.decode(
            self.tokenizer.convert_tokens_to_ids(target_tokens), 
            skip_special_tokens=True
        )

    def getToken(self, lang: str):
        langtoken = self.token_df.loc[self.token_df["Language"].str.lower() == lang.lower()]
        if not langtoken.empty:
            return langtoken.values[0][1]
        return None
    
if __name__ == "__main__":
    translatorModel = translator()
    
    # Test 1: The Armpit Test
    # Target should be: なぜ私の脇は臭いのですか？
    print("--- Test 1: Anatomy Accuracy ---")
    input_text = "can you makem e some noodle?"
    print(f"input: {input_text}")
    eng_to_jap = translatorModel.translate(input_text, "English", "Japanese")
    print(f"eng_to_jap: {eng_to_jap}")
    jap_to_eng = translatorModel.translate(eng_to_jap, "Japanese", "English")
    print(f"jap_to_eng: {jap_to_eng}")

    # Test 2: Nuance Test
    # Checking if it understands "stinky" vs just "smell"
    print("\n--- Test 2: Nuance ---")
    input_text = "My armpits are really stinks."
    print(f"input: {input_text}")
    eng_to_jap = translatorModel.translate(input_text, "English", "Japanese")
    print(f"eng_to_jap: {eng_to_jap}")
    jap_to_eng = translatorModel.translate(eng_to_jap, "Japanese", "English")
    print(f"jap_to_eng: {jap_to_eng}")