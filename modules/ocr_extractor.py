
import logging
import re
from typing import Optional, Dict, Any

try:
    import cv2
    import numpy as np
except ImportError:
    pass

logger = logging.getLogger(__name__)

class EasyOCRExtractor:
    """EasyOCR-based document extractor (offline, always works)"""
    
    def __init__(self):
        self.reader = None
        self.initialized = False
        try:
            import easyocr
            self.reader = easyocr.Reader(['en', 'hi'], gpu=False)
            self.initialized = True
            logger.info("EasyOCR extractor initialized")
        except Exception as e:
            logger.warning(f"EasyOCR initialization failed: {e}")
    
    def extract(self, image_path: str) -> Optional[Dict[str, Any]]:
        """Extract fields using EasyOCR + pattern matching"""
        if not self.initialized:
            return None
        
        try:
            # Read image
            image = cv2.imread(image_path)
            if image is None:
                return None
            
            # OCR
            results = self.reader.readtext(image)
            
            # Combine all text
            full_text = ' '.join([r[1] for r in results]).lower()
            
            # Extract dealer name
            dealer_name = None
            dealer_patterns = [
                r'([\w\s]+(?:motors?|tractors?|agencies?|enterprises?|pvt\.?\s*ltd\.?|limited))',
                r'([\w\s]+(?:auto|dealer|agro))',
            ]
            for pattern in dealer_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    dealer_name = match.group(1).strip().title()
                    break
            
            # Extract model name
            model_name = None
            brands = ['mahindra', 'swaraj', 'sonalika', 'tata', 'john deere', 'kubota', 
                     'new holland', 'escort', 'massey', 'eicher', 'farmtrac', 'force', 'vst']
            for brand in brands:
                pattern = rf'({brand})\s*(\d{{2,4}})\s*(di|fe|hp|plus|max|turbo)?'
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    model_name = f"{match.group(1).title()} {match.group(2)}"
                    if match.group(3):
                        model_name += f" {match.group(3).upper()}"
                    break
            
            # Extract horse power
            horse_power = None
            hp_patterns = [r'(\d{2,3})\s*(?:hp|h\.p\.)', r'(?:hp|horse\s*power)[:\s]*(\d{2,3})']
            for pattern in hp_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    horse_power = match.group(1)
                    break
            
            # Extract asset cost
            asset_cost = None
            cost_patterns = [
                r'(?:total|net|amount|cost|price)[:\s]*(?:rs\.?|₹)?\s*([\d,]+)',
                r'(?:rs\.?|₹)\s*([\d,]+)',
                r'([\d,]{6,})'  # Any 6+ digit number
            ]
            for pattern in cost_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    cost_str = match.group(1).replace(',', '')
                    try:
                        cost = int(cost_str)
                        if 100000 <= cost <= 3000000:  # Valid tractor price range
                            asset_cost = cost
                            break
                    except:
                        pass
            
            # Detect signature (look for handwritten marks in lower region)
            h, w = image.shape[:2]
            lower_region = image[int(h*0.6):, :]
            gray = cv2.cvtColor(lower_region, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            signature_present = False
            signature_bbox = None
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if 500 < area < 50000:
                    x, y, cw, ch = cv2.boundingRect(cnt)
                    aspect = cw / max(ch, 1)
                    if 1.5 < aspect < 10:  # Signature-like shape
                        signature_present = True
                        signature_bbox = [x, int(h*0.6) + y, x + cw, int(h*0.6) + y + ch]
                        break
            
            # Detect stamp (look for colored circular regions)
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # Blue stamp
            blue_mask = cv2.inRange(hsv, np.array([100, 50, 50]), np.array([130, 255, 255]))
            # Red stamp
            red_mask1 = cv2.inRange(hsv, np.array([0, 50, 50]), np.array([10, 255, 255]))
            red_mask2 = cv2.inRange(hsv, np.array([170, 50, 50]), np.array([180, 255, 255]))
            
            stamp_mask = cv2.bitwise_or(blue_mask, cv2.bitwise_or(red_mask1, red_mask2))
            stamp_contours, _ = cv2.findContours(stamp_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            stamp_present = False
            stamp_bbox = None
            for cnt in stamp_contours:
                area = cv2.contourArea(cnt)
                if area > 1000:
                    x, y, cw, ch = cv2.boundingRect(cnt)
                    aspect = cw / max(ch, 1)
                    if 0.5 < aspect < 2:  # Roughly circular
                        stamp_present = True
                        stamp_bbox = [x, y, x + cw, y + ch]
                        break
            
            return {
                'dealer_name': dealer_name,
                'model_name': model_name,
                'horse_power': horse_power,
                'asset_cost': asset_cost,
                'signature_present': signature_present,
                'signature_bbox': signature_bbox,
                'stamp_present': stamp_present,
                'stamp_bbox': stamp_bbox,
                'confidence': 0.6,
                'extraction_method': 'easyocr'
            }
            
        except Exception as e:
            logger.error(f"EasyOCR extraction failed: {e}")
            return None
