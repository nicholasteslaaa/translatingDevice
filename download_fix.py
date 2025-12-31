from huggingface_hub import hf_hub_download

# Manually download the specific voice file that failed
hf_hub_download(repo_id="hexgrad/Kokoro-82M", filename="voices/jf_gongitsune.pt")

print("Download successful! You can now run your main script.")