import os
from huggingface_hub import snapshot_download

repo = "nicsap/NLLB-3.3B-int8"
local_dir = "./NLLB-3.3B-int8"

print(f"Starting download for {repo}...")

try:
    snapshot_download(
        repo_id=repo,
        local_dir=local_dir,
        local_dir_use_symlinks=False,  # Essential for Windows to avoid admin issues
        revision="main"
    )
    print(f"✅ Success! Model downloaded to {os.path.abspath(local_dir)}")
except Exception as e:
    print(f"❌ Failed: {e}")