
import logging
import json
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class LocalLLMExtractor:
    """
    Local LLM Extractor using llama-cpp-python.
    Runs completely offline using a GGUF model.
    """
    
    def __init__(self, model_path: str = "models/model.gguf"):
        self.llm = None
        self.initialized = False
        
        if os.path.exists(model_path):
            try:
                # Import here to avoid hard dependency if not installed
                from llama_cpp import Llama
                
                logger.info(f"Loading Local LLM from {model_path}...")
                # Load model - adjust n_gpu_layers based on available hardware, -1 means all if possible
                self.llm = Llama(
                    model_path=model_path,
                    n_ctx=4096,      # Context window
                    n_gpu_layers=-1, # Offload to GPU if available
                    n_threads=4,     # CPU threads
                    verbose=False
                )
                self.initialized = True
                logger.info("✅ Local LLM initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Local LLM: {e}")
                logger.warning("Please ensure 'llama-cpp-python' is installed and the model file is valid.")
        else:
            logger.warning(f"⚠️ Local LLM model not found at {model_path}. Run 'setup_model.py' to download it.")

    def extract(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract fields from text using the Local LLM.
        """
        if not self.initialized:
            logger.warning("Local LLM not initialized, skipping extraction.")
            return None
            
        if not text or len(text.strip()) < 10:
            logger.warning("Input text too short for LLM extraction.")
            return None
            
        system_prompt = """You are a precise document extraction AI. 
Your task is to extract specific information from the invoice text provided.
Return the output ONLY as a valid JSON object. Do not add markdown or explanations.
"""

        user_prompt = f"""Extract the following fields from the text below:
1. "dealer_name": The name of the tractor dealer or agency.
2. "model_name": The model of the tractor (e.g., Swaraj 744, Mahindra 575).
3. "horse_power": The HP of the tractor (e.g., 50 HP).
4. "asset_cost": The total cost or price of the tractor (number only, remove currency symbols).

If a field is not found, set it to null.

Invoice Text:
{text}
"""
        
        try:
            # Use JSON mode if supported or just prompt engineering
            response = self.llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={
                    "type": "json_object",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "dealer_name": {"type": ["string", "null"]},
                            "model_name": {"type": ["string", "null"]},
                            "horse_power": {"type": ["string", "null"]},
                            "asset_cost": {"type": ["number", "string", "null"]},
                        },
                        "required": ["dealer_name", "model_name", "horse_power", "asset_cost"]
                    }
                },
                temperature=0.1, # Low temperature for factual extraction
                max_tokens=512
            )
            
            content = response['choices'][0]['message']['content']
            
            # Parse JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Fallback clean up if model adds markdown
                clean_content = content.replace('```json', '').replace('```', '').strip()
                data = json.loads(clean_content)
            
            # Post-process asset_cost to be an integer if possible
            if data.get('asset_cost'):
                if isinstance(data['asset_cost'], str):
                    # Remove commas and non-numeric chars except digits
                    cost_str = ''.join(filter(str.isdigit, data['asset_cost']))
                    if cost_str:
                        data['asset_cost'] = int(cost_str)
                elif isinstance(data['asset_cost'], (int, float)):
                    data['asset_cost'] = int(data['asset_cost'])
                    
            return data
            
        except Exception as e:
            logger.error(f"Local LLM extraction failed: {e}")
            return None
