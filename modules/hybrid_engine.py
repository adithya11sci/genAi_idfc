
import logging
import time
import json
from pathlib import Path
from typing import Dict, List, Any

from .config import API_KEYS
from .key_manager import RoundRobinKeyManager
from .gemini_extractor import GeminiExtractor
from .ocr_extractor import EasyOCRExtractor

logger = logging.getLogger(__name__)

# Global key manager
key_manager = RoundRobinKeyManager(API_KEYS)

class HybridExtractor:
    """
    Hybrid extractor that tries Gemini first, falls back to EasyOCR
    Combines results for best accuracy
    """
    
    def __init__(self):
        self.gemini = GeminiExtractor(key_manager)
        self.easyocr = EasyOCRExtractor()
        logger.info("Hybrid extractor initialized")
    
    def extract(self, image_path: str) -> Dict[str, Any]:
        """Extract using hybrid approach"""
        doc_id = Path(image_path).stem
        start_time = time.time()
        
        # Try Gemini first (better accuracy)
        result = None
        if self.gemini.initialized:
            result = self.gemini.extract(image_path)
            if result:
                logger.info(f"Gemini extraction successful for {doc_id}")
        
        # Fallback to EasyOCR if Gemini fails
        if result is None and self.easyocr.initialized:
            logger.info(f"Falling back to EasyOCR for {doc_id}")
            result = self.easyocr.extract(image_path)
            if result:
                logger.info(f"EasyOCR extraction successful for {doc_id}")
        
        # If both fail, return empty result
        if result is None:
            result = {
                'dealer_name': None,
                'model_name': None,
                'horse_power': None,
                'asset_cost': None,
                'signature_present': False,
                'signature_bbox': None,
                'stamp_present': False,
                'stamp_bbox': None,
                'confidence': 0.0,
                'extraction_method': 'failed'
            }
        
        processing_time = time.time() - start_time
        
        # Format output
        return {
            "doc_id": doc_id,
            "fields": {
                "dealer_name": result.get('dealer_name'),
                "model_name": result.get('model_name'),
                "horse_power": result.get('horse_power'),
                "asset_cost": result.get('asset_cost'),
                "signature": {
                    "present": result.get('signature_present', False),
                    "bbox": result.get('signature_bbox')
                },
                "stamp": {
                    "present": result.get('stamp_present', False),
                    "bbox": result.get('stamp_bbox')
                }
            },
            "confidence": result.get('confidence', 0.0),
            "processing_time_sec": round(processing_time, 2),
            "cost_estimate_usd": 0.0003 if result.get('extraction_method') == 'gemini' else 0.0,
            "extraction_method": result.get('extraction_method', 'unknown')
        }
    
    def process_batch(self, image_paths: List[str], output_path: str) -> List[Dict]:
        """Process multiple documents"""
        results = []
        
        try:
            from tqdm import tqdm
            iterator = tqdm(image_paths, desc="Processing")
        except:
            iterator = image_paths
        
        for path in iterator:
            try:
                result = self.extract(path)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed: {path}: {e}")
                results.append({"doc_id": Path(path).stem, "error": str(e)})
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        return results
