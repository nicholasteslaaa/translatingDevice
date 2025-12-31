from playsound import playsound
from translator import translator
from TTS_model import text_to_speech

translatorModel = translator()
ttsModel = text_to_speech()

firstInput = input("english input: ")
japaneseText = translatorModel.translate(firstInput,"english","japanese")
voice = ttsModel.generate(japaneseText,"japanese")
playsound(f"D:/education/ProjectPribadi/translatorMic/output/{voice}")

englishText = translatorModel.translate(japaneseText,"japanese","english")
voice = ttsModel.generate(englishText,"english")
playsound(f"D:/education/ProjectPribadi/translatorMic/output/{voice}")


# now = datetime.datetime.now().strftime("%m%d%Y%H%M%S")
# tts.tts_to_file(
#     text="Halo, Apakabar",
#     speaker_wav=r"sample\english\female.wav",   # reference voice
#     language="en",
#     file_path=f"output\{now}.wav"
# )

