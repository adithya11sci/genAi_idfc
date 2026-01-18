
import logging
import time
import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

from .config import API_KEYS
from .key_manager import RoundRobinKeyManager
from .gemini_extractor import GeminiExtractor
from .ocr_extractor import EasyOCRExtractor

logger = logging.getLogger(__name__)

# Global key manager
key_manager = RoundRobinKeyManager(API_KEYS)


class HybridExtractor:
    """
    Hybrid extractor that combines Gemini AI (primary) with EasyOCR (fallback).
    
    Features:
        - Automatic failover: If Gemini fails, falls back to EasyOCR
        - Processing time tracking for each document
        - Cost estimation for API usage
        - Structured output format with confidence scores
    """
    
    def __init__(self):
        """Initialize hybrid extractor with both engines"""
        self.gemini = GeminiExtractor(key_manager)
        self.easyocr = EasyOCRExtractor()
        
        # Status tracking
        self.gemini_available = self.gemini.initialized
        self.easyocr_available = self.easyocr.initialized
        
        logger.info(f"Hybrid extractor initialized | Gemini: {self.gemini_available} | EasyOCR: {self.easyocr_available}")
    
    def extract(self, image_path: str) -> Dict[str, Any]:
        """
        Extract invoice data using hybrid approach.
        
        Strategy:
            1. Try Gemini Vision first (better accuracy)
            2. Fall back to EasyOCR if Gemini fails
            3. Return structured result with metadata
        
        Args:
            image_path: Path to the invoice image
            
        Returns:
            Structured dictionary with extracted fields and metadata
        """
        doc_id = Path(image_path).stem
        start_time = time.time()
        extraction_method = 'failed'
        
        result = None
        
        # ───────────────────────────────────────────────────────────────────
        # PRIMARY: Try Gemini Vision API
        # ───────────────────────────────────────────────────────────────────
        if self.gemini_available:
            try:
                result = self.gemini.extract(image_path)
                if result and result.get('confidence', 0) > 0:
                    extraction_method = 'gemini'
                    logger.info(f"✅ Gemini extraction successful for {doc_id}")
            except Exception as e:
                logger.warning(f"⚠️ Gemini failed for {doc_id}: {e}")
                result = None
        
        # ───────────────────────────────────────────────────────────────────
        # FALLBACK: Try EasyOCR if Gemini fails
        # ───────────────────────────────────────────────────────────────────
        if result is None and self.easyocr_available:
            logger.info(f"🔄 Falling back to EasyOCR for {doc_id}")
            try:
                result = self.easyocr.extract(image_path)
                if result and result.get('confidence', 0) > 0:
                    extraction_method = 'easyocr'
                    logger.info(f"✅ EasyOCR extraction successful for {doc_id}")
            except Exception as e:
                logger.error(f"❌ EasyOCR failed for {doc_id}: {e}")
                result = None
        
        # ───────────────────────────────────────────────────────────────────
        # HANDLE FAILURE: Return empty result structure
        # ───────────────────────────────────────────────────────────────────
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
            logger.error(f"❌ All extraction methods failed for {doc_id}")
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # ───────────────────────────────────────────────────────────────────
        # FORMAT OUTPUT: Structured JSON response
        # ───────────────────────────────────────────────────────────────────
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
            "cost_estimate_usd": 0.0003 if extraction_method == 'gemini' else 0.0,
            "extraction_method": extraction_method
        }
    
    def process_batch(self, image_paths: List[str], output_path: str) -> List[Dict]:
        """
        Process multiple documents in batch mode.
        
        Features:
            - Progress tracking with status updates
            - Combined output with batch statistics
            - Error handling for individual documents
        
        Args:
            image_paths: List of paths to invoice images
            output_path: Path to save the combined JSON output
            
        Returns:
            List of extraction results for all documents
        """
        results = []
        total = len(image_paths)
        batch_start_time = time.time()
        
        # Try to use tqdm for progress bar if available
        try:
            from tqdm import tqdm
            iterator = tqdm(image_paths, desc="📄 Processing invoices", unit="doc")
            use_tqdm = True
        except ImportError:
            iterator = image_paths
            use_tqdm = False
        
        # ───────────────────────────────────────────────────────────────────
        # PROCESS EACH DOCUMENT
        # ───────────────────────────────────────────────────────────────────
        for i, path in enumerate(iterator):
            if not use_tqdm:
                print(f"  [{i+1}/{total}] Processing: {Path(path).name}...", end=" ", flush=True)
            
            try:
                result = self.extract(path)
                result["source_file"] = str(path)
                result["timestamp"] = datetime.now().isoformat()
                results.append(result)
                
                if not use_tqdm:
                    status = "✅" if result.get('confidence', 0) > 0.5 else "⚠️"
                    print(f"{status} Done")
                    
            except Exception as e:
                logger.error(f"❌ Failed to process {path}: {e}")
                error_result = {
                    "doc_id": Path(path).stem,
                    "source_file": str(path),
                    "error": str(e),
                    "confidence": 0,
                    "extraction_method": "failed",
                    "timestamp": datetime.now().isoformat()
                }
                results.append(error_result)
                
                if not use_tqdm:
                    print(f"❌ Failed: {str(e)[:30]}")
        
        # ───────────────────────────────────────────────────────────────────
        # CALCULATE BATCH STATISTICS
        # ───────────────────────────────────────────────────────────────────
        batch_time = time.time() - batch_start_time
        successful = sum(1 for r in results if r.get('confidence', 0) > 0)
        failed = total - successful
        total_cost = sum(r.get('cost_estimate_usd', 0) for r in results)
        avg_confidence = sum(r.get('confidence', 0) for r in results) / total if total > 0 else 0
        
        # ───────────────────────────────────────────────────────────────────
        # SAVE COMBINED OUTPUT
        # ───────────────────────────────────────────────────────────────────
        batch_output = {
            "batch_info": {
                "total_documents": total,
                "successful": successful,
                "failed": failed,
                "success_rate": f"{(successful/total*100):.1f}%" if total > 0 else "0%",
                "avg_confidence": round(avg_confidence, 3),
                "total_processing_time_sec": round(batch_time, 2),
                "avg_time_per_doc_sec": round(batch_time / total, 2) if total > 0 else 0,
                "total_cost_usd": round(total_cost, 4),
                "processed_at": datetime.now().isoformat()
            },
            "documents": results
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(batch_output, f, indent=2, ensure_ascii=False)
        
        # Print summary
        print(f"\n{'═' * 50}")
        print(f"📊 Batch Complete: {successful}/{total} successful ({failed} failed)")
        print(f"⏱️  Total time: {batch_time:.2f}s | Avg: {batch_time/total:.2f}s per doc")
        print(f"💵 Total cost: ${total_cost:.4f}")
        print(f"{'═' * 50}")
        
        return results
