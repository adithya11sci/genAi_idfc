
import logging
import base64
import io
import json
import time
from typing import Optional, Dict, Any
from PIL import Image

try:
    from google import genai
    from google.genai import types
except ImportError:
    pass

from .config import GEMINI_MODEL
from .key_manager import RoundRobinKeyManager

logger = logging.getLogger(__name__)

class GeminiExtractor:
    """Gemini-based document extractor"""
    
    def __init__(self, key_manager: RoundRobinKeyManager):
        self.key_manager = key_manager
        self.initialized = False
        try:
            self.genai = genai
            self.types = types
            self.initialized = True
            logger.info("Gemini extractor initialized")
        except ImportError:
            logger.warning("google-genai not installed. Gemini extraction disabled.")
        except NameError:
             logger.warning("google-genai not imported. Gemini extraction disabled.")

    
    def extract(self, image_path: str) -> Optional[Dict[str, Any]]:
        """Extract fields using Gemini Vision API"""
        if not self.initialized:
            return None
        
        try:
            # Load and prepare image
            img = Image.open(image_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize to reduce API costs
            max_size = 1024
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            # Get API key (round-robin)
            api_key = self.key_manager.get_key()
            client = self.genai.Client(api_key=api_key)
            
            # Single comprehensive prompt for all fields
            prompt = """Analyze this Indian tractor loan quotation invoice and extract ALL fields.

EXTRACT THESE FIELDS:
1. dealer_name: Business name of dealer/seller (from letterhead)
2. model_name: Tractor model - ONLY brand + number (e.g., "Mahindra 575 DI", "Swaraj 744"). Keep SHORT!
3. horse_power: HP value as number only (e.g., "50")
4. asset_cost: Total price in INR as number (no commas, e.g., 850000)
5. signature_present: true/false - is there a handwritten signature?
6. signature_bbox: [x1,y1,x2,y2] as % of image (0-100), or null
7. stamp_present: true/false - is there an official stamp/seal?
8. stamp_bbox: [x1,y1,x2,y2] as % of image (0-100), or null

Return ONLY JSON (no markdown, no explanation):
{"dealer_name":"string or null","model_name":"string or null","horse_power":"string or null","asset_cost":number or null,"signature_present":true/false,"signature_bbox":[x1,y1,x2,y2] or null,"stamp_present":true/false,"stamp_bbox":[x1,y1,x2,y2] or null,"confidence":0.0-1.0}"""
            
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    self.types.Content(
                        role="user",
                        parts=[
                            self.types.Part.from_text(text=prompt),
                            self.types.Part.from_bytes(
                                data=base64.b64decode(image_base64),
                                mime_type="image/png"
                            )
                        ]
                    )
                ]
            )
            
            # Parse response with robust JSON extraction
            raw_text = response.text.strip() if response.text else ""
            
            if not raw_text:
                logger.warning("Empty response from Gemini")
                return None
            
            # Remove markdown code blocks if present
            if "```" in raw_text:
                import re
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw_text)
                if json_match:
                    raw_text = json_match.group(1).strip()
            
            # Try to find JSON object in text
            if not raw_text.startswith("{"):
                import re
                json_match = re.search(r'\{[\s\S]*\}', raw_text)
                if json_match:
                    raw_text = json_match.group(0)
            
            # Clean any trailing/leading whitespace
            raw_text = raw_text.strip()
            
            result = json.loads(raw_text)
            
            # Convert bbox percentages to pixels
            img_w, img_h = img.size
            if result.get('signature_bbox'):
                bbox = result['signature_bbox']
                result['signature_bbox'] = [
                    int(bbox[0] * img_w / 100), int(bbox[1] * img_h / 100),
                    int(bbox[2] * img_w / 100), int(bbox[3] * img_h / 100)
                ]
            if result.get('stamp_bbox'):
                bbox = result['stamp_bbox']
                result['stamp_bbox'] = [
                    int(bbox[0] * img_w / 100), int(bbox[1] * img_h / 100),
                    int(bbox[2] * img_w / 100), int(bbox[3] * img_h / 100)
                ]
            
            result['extraction_method'] = 'gemini'
            return result
            
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                self.key_manager.mark_rate_limited(api_key)
            logger.warning(f"Gemini extraction failed: {e}")
            return None
