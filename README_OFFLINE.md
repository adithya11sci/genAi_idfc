# 🚜 IDFC GenAI - Offline Edition

**Status**: ✅ 100% Offline Capable | 🔒 Privacy First | 🧠 Local LLM

This version of the project is configured to run **without an internet connection** by leveraging a local Large Language Model (LLM) instead of cloud APIs.

---

## 🚀 Quick Start (Offline Mode)

### 1. Initial Setup (One-time)
Before going offline, you must download the AI brain (Model weights).
```bash
# This downloads the Qwen 2.5 7B model (~4.6 GB)
python setup_model.py
```
> **Note**: This model is optimized for 16GB VRAM systems. It provides superior accuracy.

### 2. Running the Extractor
Once the model is in `models/model.gguf`, simply run the tool as usual. It will automatically detect the offline model.

```bash
# Process a single invoice
python main.py --input train/sample_invoice.png --output result.json

# Process an entire folder
python main.py --input train/ --output batch_results.json
```

---

## 📦 **How to Package for Submission (Zip-and-Ship)**

To submit this project so the evaluator needs **ZERO downloads**:

1.  **Download Model First**: Run `python setup_model.py` on your machine.
2.  **Verify**: Ensure `models/model.gguf` exists (approx 4.6GB).
3.  **Zip It**: Zip the entire `genAi_idfc` folder *including* the `models` folder.
4.  **Submit**: Send the Zip file.

**The Evaluator simply needs to:**
1. Unzip.
2. Run `python main.py` (or build the Docker image).
3. **It will work instantly without internet.**

**"Using CPU... This module is much faster with a GPU"**
*   This is normal. The system is optimized to run on standard CPUs, but will use an NVIDIA GPU if available for 10x speed.

**"UnicodeEncodeError"**
*   This has been fixed in the latest update. If you see it, ensure your terminal supports UTF-8, though we have removed all special characters for compatibility.

---
**Team Convolve**
