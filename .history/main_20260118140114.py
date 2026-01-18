"""
IDFC GenAI - Hybrid Document AI Extractor
Combines Gemini AI (for accuracy) with EasyOCR (for reliability)

Supports:
  - Single file processing: python main.py -i invoice.png -o result.json
  - Batch folder processing: python main.py -i train/ -o results.json
  - Method selection: --method hybrid|gemini|ocr
  
Supported Formats:
  - Images: PNG, JPG, JPEG, BMP, TIFF, WEBP, GIF
  - Documents: PDF (converts each page to image)
"""

import json
import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime
from modules.hybrid_engine import HybridExtractor
from modules.gemini_extractor import GeminiExtractor
from modules.ocr_extractor import EasyOCRExtractor
from modules.config import API_KEYS
from modules.key_manager import RoundRobinKeyManager

# Try to import PDF libraries
try:
    import fitz  # PyMuPDF
    PDF_SUPPORT = True
except ImportError:
    try:
        from pdf2image import convert_from_path
        PDF_SUPPORT = True
    except ImportError:
        PDF_SUPPORT = False
        print("⚠️  PDF support not available. Install pdf2image or PyMuPDF for PDF support.")


# ═══════════════════════════════════════════════════════════════════════════════
#                              OUTPUT FORMATTING
# ═══════════════════════════════════════════════════════════════════════════════

def print_header():
    """Print application header"""
    print("\n" + "═" * 70)
    print("║" + " " * 68 + "║")
    print("║" + "🚜  IDFC GenAI - Hybrid Document AI Extractor  📄".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("═" * 70)


def print_config(method: str, input_path: str, output_path: str, file_count: int):
    """Print configuration summary"""
    print("\n┌" + "─" * 68 + "┐")
    print("│" + " CONFIGURATION ".center(68) + "│")
    print("├" + "─" * 68 + "┤")
    print(f"│  📌 Method      : {method.upper():<47} │")
    print(f"│  📂 Input       : {input_path:<47} │")
    print(f"│  💾 Output      : {output_path:<47} │")
    print(f"│  📄 Files Found : {file_count:<47} │")
    print("└" + "─" * 68 + "┘")


def print_single_result(output: dict):
    """Print formatted result for single file extraction"""
    fields = output.get('fields', {})
    signature = fields.get('signature', {})
    stamp = fields.get('stamp', {})
    
    print("\n┌" + "─" * 68 + "┐")
    print("│" + " ✅ EXTRACTION RESULTS ".center(68) + "│")
    print("├" + "─" * 68 + "┤")
    print(f"│  📋 Document ID   : {str(output.get('doc_id', 'N/A')):<45} │")
    print("├" + "─" * 68 + "┤")
    print("│" + " 📊 EXTRACTED FIELDS ".center(68) + "│")
    print("├" + "─" * 68 + "┤")
    print(f"│  🏭 Dealer Name   : {str(fields.get('dealer_name') or 'Not Found'):<45} │")
    print(f"│  🚜 Model Name    : {str(fields.get('model_name') or 'Not Found'):<45} │")
    print(f"│  🐎 Horse Power   : {str(fields.get('horse_power') or 'Not Found'):<45} │")
    print(f"│  💰 Asset Cost    : {str(fields.get('asset_cost') or 'Not Found'):<45} │")
    print("├" + "─" * 68 + "┤")
    print("│" + " 🔍 VERIFICATION ".center(68) + "│")
    print("├" + "─" * 68 + "┤")
    sig_status = "✅ Present" if signature.get('present') else "❌ Not Found"
    stamp_status = "✅ Present" if stamp.get('present') else "❌ Not Found"
    print(f"│  ✍️  Signature     : {sig_status:<45} │")
    print(f"│  🏵️  Stamp         : {stamp_status:<45} │")
    print("├" + "─" * 68 + "┤")
    print("│" + " 📈 METADATA ".center(68) + "│")
    print("├" + "─" * 68 + "┤")
    confidence = output.get('confidence', 0)
    conf_bar = "█" * int(confidence * 10) + "░" * (10 - int(confidence * 10))
    print(f"│  🎯 Confidence    : [{conf_bar}] {confidence:.1%:<32} │")
    print(f"│  ⚡ Method        : {str(output.get('extraction_method', 'unknown')):<45} │")
    proc_time = output.get('processing_time_sec', 0)
    print(f"│  ⏱️  Process Time  : {proc_time:.2f} seconds{'':<35} │")
    cost = output.get('cost_estimate_usd', 0)
    print(f"│  💵 Cost Estimate : ${cost:.4f}{'':<42} │")
    print("└" + "─" * 68 + "┘")


def print_batch_summary(results: list, output_path: str):
    """Print formatted summary for batch processing"""
    total = len(results)
    successful = sum(1 for r in results if r.get('confidence', 0) > 0)
    failed = total - successful
    avg_confidence = sum(r.get('confidence', 0) for r in results) / total if total > 0 else 0
    total_time = sum(r.get('processing_time_sec', 0) for r in results)
    total_cost = sum(r.get('cost_estimate_usd', 0) for r in results)
    
    print("\n╔" + "═" * 68 + "╗")
    print("║" + " 📊 BATCH PROCESSING SUMMARY ".center(68) + "║")
    print("╠" + "═" * 68 + "╣")
    print(f"║  📄 Total Documents    : {total:<41} ║")
    print(f"║  ✅ Successful         : {successful:<41} ║")
    print(f"║  ❌ Failed             : {failed:<41} ║")
    print("╠" + "═" * 68 + "╣")
    print("║" + " 📈 STATISTICS ".center(68) + "║")
    print("╠" + "═" * 68 + "╣")
    conf_bar = "█" * int(avg_confidence * 10) + "░" * (10 - int(avg_confidence * 10))
    print(f"║  🎯 Avg Confidence     : [{conf_bar}] {avg_confidence:.1%:<28} ║")
    print(f"║  ⏱️  Total Time         : {total_time:.2f} seconds{'':<31} ║")
    print(f"║  ⚡ Avg Time/Doc       : {(total_time/total if total else 0):.2f} seconds{'':<31} ║")
    print(f"║  💵 Total Cost         : ${total_cost:.4f}{'':<38} ║")
    print("╠" + "═" * 68 + "╣")
    print("║" + " 📋 DOCUMENT RESULTS ".center(68) + "║")
    print("╠" + "═" * 68 + "╣")
    
    # Show each document result briefly
    for i, result in enumerate(results[:10]):  # Show first 10
        doc_id = result.get('doc_id', 'unknown')[:20]
        conf = result.get('confidence', 0)
        status = "✅" if conf > 0.5 else "⚠️" if conf > 0 else "❌"
        dealer = (result.get('fields', {}).get('dealer_name') or 'N/A')[:20]
        print(f"║  {status} {doc_id:<20} │ Conf: {conf:.0%} │ Dealer: {dealer:<15} ║")
    
    if total > 10:
        print(f"║  ... and {total - 10} more documents{'':<41} ║")
    
    print("╚" + "═" * 68 + "╝")


def print_footer(output_path: str):
    """Print footer with output location"""
    print("\n┌" + "─" * 68 + "┐")
    print(f"│  💾 Results saved to: {output_path:<43} │")
    print(f"│  🕐 Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<46} │")
    print("└" + "─" * 68 + "┘\n")


# ═══════════════════════════════════════════════════════════════════════════════
#                              FILE HANDLING
# ═══════════════════════════════════════════════════════════════════════════════

# Supported file formats
IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp', '.gif',
                    '.PNG', '.JPG', '.JPEG', '.BMP', '.TIFF', '.TIF', '.WEBP', '.GIF']
PDF_EXTENSIONS = ['.pdf', '.PDF']
ALL_EXTENSIONS = IMAGE_EXTENSIONS + PDF_EXTENSIONS


def convert_pdf_to_images(pdf_path: str, output_dir: str = None) -> list:
    """
    Convert PDF file to images (one per page).
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save converted images (uses temp dir if None)
        
    Returns:
        List of paths to converted image files
    """
    if not PDF_SUPPORT:
        print(f"❌ PDF support not available. Please install pdf2image or PyMuPDF.")
        return []
    
    pdf_name = Path(pdf_path).stem
    
    # Create output directory
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="idfc_pdf_")
    else:
        os.makedirs(output_dir, exist_ok=True)
    
    image_paths = []
    
    try:
        # Try PyMuPDF first (faster)
        import fitz
        doc = fitz.open(pdf_path)
        
        print(f"  📄 Converting PDF ({len(doc)} pages)...")
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # Render at 300 DPI for good quality
            mat = fitz.Matrix(300/72, 300/72)
            pix = page.get_pixmap(matrix=mat)
            
            output_path = os.path.join(output_dir, f"{pdf_name}_page_{page_num + 1}.png")
            pix.save(output_path)
            image_paths.append(output_path)
            
        doc.close()
        print(f"  ✅ Converted {len(image_paths)} pages from PDF")
        
    except ImportError:
        # Fallback to pdf2image
        try:
            from pdf2image import convert_from_path
            
            print(f"  📄 Converting PDF to images...")
            images = convert_from_path(pdf_path, dpi=300)
            
            for i, image in enumerate(images):
                output_path = os.path.join(output_dir, f"{pdf_name}_page_{i + 1}.png")
                image.save(output_path, 'PNG')
                image_paths.append(output_path)
                
            print(f"  ✅ Converted {len(image_paths)} pages from PDF")
            
        except Exception as e:
            print(f"❌ Failed to convert PDF: {e}")
            return []
    
    except Exception as e:
        print(f"❌ Failed to convert PDF: {e}")
        return []
    
    return image_paths


def get_image_files(input_path: Path) -> list:
    """
    Get list of image files from input path.
    Supports single file or directory with multiple files.
    Handles PDF conversion automatically.
    
    Supported formats:
        - Images: PNG, JPG, JPEG, BMP, TIFF, WEBP, GIF
        - Documents: PDF (each page converted to image)
    """
    
    if input_path.is_file():
        # Single file mode
        suffix = input_path.suffix.lower()
        
        # Handle PDF files
        if suffix == '.pdf':
            if not PDF_SUPPORT:
                print(f"❌ PDF support not available. Install: pip install PyMuPDF pdf2image")
                return []
            print(f"  📄 Detected PDF file: {input_path.name}")
            return convert_pdf_to_images(str(input_path))
        
        # Handle image files
        elif input_path.suffix in IMAGE_EXTENSIONS:
            return [str(input_path)]
        
        # Try unknown format anyway
        else:
            print(f"⚠️  Warning: {input_path.suffix} format - attempting to process anyway...")
            return [str(input_path)]
    
    elif input_path.is_dir():
        # Batch folder mode
        image_paths = []
        pdf_paths = []
        
        # Collect image files
        for ext in IMAGE_EXTENSIONS:
            image_paths.extend([str(p) for p in input_path.glob(f'*{ext}')])
        
        # Collect PDF files
        for ext in PDF_EXTENSIONS:
            pdf_paths.extend([str(p) for p in input_path.glob(f'*{ext}')])
        
        # Convert PDFs to images
        if pdf_paths:
            print(f"  📁 Found {len(pdf_paths)} PDF file(s) - converting...")
            for pdf_path in pdf_paths:
                converted = convert_pdf_to_images(pdf_path)
                image_paths.extend(converted)
        
        return sorted(set(image_paths))
    
    else:
        return []


def create_extractor(method: str):
    """Create appropriate extractor based on method"""
    if method == 'gemini':
        key_manager = RoundRobinKeyManager(API_KEYS)
        extractor = GeminiExtractor(key_manager)
        if not extractor.initialized:
            print("⚠️  Gemini not available, falling back to hybrid mode")
            return HybridExtractor()
        return extractor
    
    elif method == 'ocr':
        extractor = EasyOCRExtractor()
        if not extractor.initialized:
            print("❌ EasyOCR not available")
            return None
        return extractor
    
    else:  # hybrid (default)
        return HybridExtractor()


def process_single_file(extractor, image_path: str, method: str) -> dict:
    """Process a single invoice file and return formatted result"""
    if method in ['gemini', 'ocr']:
        # Direct extractor returns raw result
        result = extractor.extract(image_path)
        doc_id = Path(image_path).stem
        
        return {
            "doc_id": doc_id,
            "source_file": str(image_path),
            "fields": {
                "dealer_name": result.get('dealer_name') if result else None,
                "model_name": result.get('model_name') if result else None,
                "horse_power": result.get('horse_power') if result else None,
                "asset_cost": result.get('asset_cost') if result else None,
                "signature": {
                    "present": result.get('signature_present', False) if result else False,
                    "bbox": result.get('signature_bbox') if result else None
                },
                "stamp": {
                    "present": result.get('stamp_present', False) if result else False,
                    "bbox": result.get('stamp_bbox') if result else None
                }
            },
            "confidence": result.get('confidence', 0) if result else 0,
            "processing_time_sec": result.get('processing_time_sec', 0) if result else 0,
            "cost_estimate_usd": 0.0003 if result and result.get('extraction_method') == 'gemini' else 0.0,
            "extraction_method": result.get('extraction_method', 'unknown') if result else 'failed',
            "timestamp": datetime.now().isoformat()
        }
    else:
        # Hybrid extractor returns formatted result
        result = extractor.extract(image_path)
        result["source_file"] = str(image_path)
        result["timestamp"] = datetime.now().isoformat()
        return result


def process_batch_files(extractor, image_paths: list, output_path: str, method: str) -> list:
    """Process multiple invoice files with progress tracking"""
    results = []
    total = len(image_paths)
    
    print("\n┌" + "─" * 68 + "┐")
    print("│" + " 🔄 BATCH PROCESSING ".center(68) + "│")
    print("└" + "─" * 68 + "┘\n")
    
    for i, path in enumerate(image_paths, 1):
        doc_name = Path(path).name[:30]
        progress = f"[{i}/{total}]"
        print(f"  {progress} Processing: {doc_name}...", end=" ", flush=True)
        
        try:
            result = process_single_file(extractor, path, method)
            results.append(result)
            conf = result.get('confidence', 0)
            status = "✅" if conf > 0.5 else "⚠️" if conf > 0 else "❌"
            print(f"{status} Done (Confidence: {conf:.0%})")
        except Exception as e:
            print(f"❌ Failed: {str(e)[:30]}")
            results.append({
                "doc_id": Path(path).stem,
                "source_file": str(path),
                "error": str(e),
                "confidence": 0,
                "extraction_method": "failed",
                "timestamp": datetime.now().isoformat()
            })
    
    # Save results
    batch_output = {
        "batch_info": {
            "total_documents": total,
            "successful": sum(1 for r in results if r.get('confidence', 0) > 0),
            "failed": sum(1 for r in results if r.get('confidence', 0) == 0),
            "extraction_method": method,
            "processed_at": datetime.now().isoformat()
        },
        "documents": results
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(batch_output, f, indent=2, ensure_ascii=False)
    
    return results


# ═══════════════════════════════════════════════════════════════════════════════
#                              MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='IDFC GenAI - Hybrid Document AI Extractor',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Single file:   python main.py -i invoice.png -o result.json
  Batch folder:  python main.py -i train/ -o results.json
  Gemini only:   python main.py -i invoice.png -o result.json --method gemini
  OCR only:      python main.py -i invoice.png -o result.json --method ocr
        """
    )
    parser.add_argument('-i', '--input', required=True, 
                        help='Input image file OR directory containing images')
    parser.add_argument('-o', '--output', required=True, 
                        help='Output JSON file path')
    parser.add_argument('--method', choices=['hybrid', 'gemini', 'ocr'], default='hybrid',
                        help='Extraction method: hybrid (default), gemini, or ocr')
    
    args = parser.parse_args()
    
    # Print header
    print_header()
    
    # Get image files
    input_path = Path(args.input)
    image_paths = get_image_files(input_path)
    
    if not image_paths:
        print(f"\n❌ Error: No valid files found at '{args.input}'")
        print("   Supported formats:")
        print("   - Images: PNG, JPG, JPEG, BMP, TIFF, WEBP, GIF")
        print("   - Documents: PDF (auto-converts to images)")
        return 1
    
    # Determine mode
    is_single_file = len(image_paths) == 1
    mode = "📄 SINGLE FILE" if is_single_file else "📁 BATCH FOLDER"
    
    # Print configuration
    print_config(args.method, args.input, args.output, len(image_paths))
    print(f"\n  🔧 Mode: {mode}")
    
    # Create extractor
    extractor = create_extractor(args.method)
    if extractor is None:
        return 1
    
    # Process based on mode
    if is_single_file:
        # ═══════════════════════════════════════════════════════════════════
        #                        SINGLE FILE MODE
        # ═══════════════════════════════════════════════════════════════════
        print("\n  ⏳ Processing single document...")
        output = process_single_file(extractor, image_paths[0], args.method)
        
        # Save result
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        # Print formatted result
        print_single_result(output)
    
    else:
        # ═══════════════════════════════════════════════════════════════════
        #                        BATCH FOLDER MODE
        # ═══════════════════════════════════════════════════════════════════
        results = process_batch_files(extractor, image_paths, args.output, args.method)
        
        # Print batch summary
        print_batch_summary(results, args.output)
    
    # Print footer
    print_footer(args.output)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
