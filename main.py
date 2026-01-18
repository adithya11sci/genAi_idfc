"""
IDFC GenAI - Hybrid Document AI Extractor
Combines Gemini AI (for accuracy) with EasyOCR (for reliability)
"""

import json
from pathlib import Path
from modules.hybrid_engine import HybridExtractor
from modules.gemini_extractor import GeminiExtractor
from modules.ocr_extractor import EasyOCRExtractor
from modules.config import API_KEYS
from modules.key_manager import RoundRobinKeyManager

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Hybrid Document AI Extractor')
    parser.add_argument('-i', '--input', required=True, help='Input image or directory')
    parser.add_argument('-o', '--output', required=True, help='Output JSON file')
    parser.add_argument('--method', choices=['hybrid', 'gemini', 'ocr'], default='hybrid',
                       help='Extraction method: hybrid (default), gemini, or ocr')
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("IDFC GenAI - Hybrid Document AI Extractor")
    print("="*60)
    print(f"Method: {args.method.upper()}")
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print("="*60 + "\n")
    
    # Get image files
    input_path = Path(args.input)
    if input_path.is_file():
        image_paths = [str(input_path)]
    elif input_path.is_dir():
        extensions = ['.png', '.jpg', '.jpeg']
        image_paths = []
        for ext in extensions:
            image_paths.extend([str(p) for p in input_path.glob(f'*{ext}')])
        image_paths = sorted(set(image_paths))
    else:
        print(f"Error: {args.input} not found")
        return 1
    
    print(f"Found {len(image_paths)} document(s)")
    
    # Create extractor based on method
    if args.method == 'gemini':
        key_manager = RoundRobinKeyManager(API_KEYS)
        extractor = GeminiExtractor(key_manager)
        if not extractor.initialized:
            print("Gemini not available, using hybrid")
            extractor = HybridExtractor()
    elif args.method == 'ocr':
        extractor = EasyOCRExtractor()
        if not extractor.initialized:
            print("EasyOCR not available")
            return 1
    else:
        extractor = HybridExtractor()
    
    # Process
    if len(image_paths) == 1:
        if hasattr(extractor, 'extract'):
            if args.method in ['gemini', 'ocr']:
                result = extractor.extract(image_paths[0])
                # Wrap in standard format
                doc_id = Path(image_paths[0]).stem
                output = {
                    "doc_id": doc_id,
                    "fields": {
                        "dealer_name": result.get('dealer_name') if result else None,
                        "model_name": result.get('model_name') if result else None,
                        "horse_power": result.get('horse_power') if result else None,
                        "asset_cost": result.get('asset_cost') if result else None,
                        "signature": {"present": result.get('signature_present', False) if result else False, "bbox": result.get('signature_bbox') if result else None},
                        "stamp": {"present": result.get('stamp_present', False) if result else False, "bbox": result.get('stamp_bbox') if result else None}
                    },
                    "confidence": result.get('confidence', 0) if result else 0,
                    "extraction_method": result.get('extraction_method', 'unknown') if result else 'failed'
                }
            else:
                output = extractor.extract(image_paths[0])
        
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print("\n" + "="*60)
        print("EXTRACTION RESULTS")
        print("="*60)
        fields = output.get('fields', {})
        print(f"Document ID: {output.get('doc_id')}")
        print(f"Dealer Name: {fields.get('dealer_name', 'N/A')}")
        print(f"Model Name: {fields.get('model_name', 'N/A')}")
        print(f"Horse Power: {fields.get('horse_power', 'N/A')}")
        print(f"Asset Cost: {fields.get('asset_cost', 'N/A')}")
        print(f"Signature: {fields.get('signature', {}).get('present', False)}")
        print(f"Stamp: {fields.get('stamp', {}).get('present', False)}")
        print(f"Confidence: {output.get('confidence', 0):.2f}")
        print(f"Method: {output.get('extraction_method', 'unknown')}")
        print("="*60)
    else:
        extractor.process_batch(image_paths, args.output)
    
    print(f"\nResults saved to {args.output}")
    return 0


if __name__ == "__main__":
    exit(main())
