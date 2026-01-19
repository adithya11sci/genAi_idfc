
import os
from huggingface_hub import hf_hub_download
import shutil

MODEL_REPO = "bartowski/Qwen2.5-7B-Instruct-GGUF"
MODEL_FILE = "Qwen2.5-7B-Instruct-Q4_K_M.gguf"
DEST_DIR = "models"
DEST_PATH = os.path.join(DEST_DIR, "model.gguf")

def setup_model():
    if not os.path.exists(DEST_DIR):
        os.makedirs(DEST_DIR)
        
    if os.path.exists(DEST_PATH):
        print(f"Model already exists at {DEST_PATH}")
        return

    print(f"Downloading {MODEL_FILE} from {MODEL_REPO}...")
    try:
        model_path = hf_hub_download(repo_id=MODEL_REPO, filename=MODEL_FILE)
        print(f"Download complete: {model_path}")
        
        print(f"Copying to {DEST_PATH}...")
        shutil.copy(model_path, DEST_PATH)
        print("Model setup complete!")
    except Exception as e:
        print(f"Failed to download model: {e}")

if __name__ == "__main__":
    setup_model()
