# ocr_utils.py
import cv2
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import re
import numpy as np
import os

# If needed on Windows, uncomment and set tesseract path:
# pytesseract.pytesseract.tesseract_cmd = r"C:/Program Files/Tesseract-OCR/tesseract.exe"

def preprocess_image(img, target_width=1200):
    if isinstance(img, Image.Image):
        img = np.array(img)
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    h, w = gray.shape[:2]
    if w < target_width:
        scale = target_width / w
        gray = cv2.resize(gray, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_LINEAR)
    gray = cv2.medianBlur(gray, 3)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th

def image_to_text(img_np):
    config = r'--oem 3 --psm 6'
    return pytesseract.image_to_string(img_np, config=config)

def ocr_from_image(path):
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"Image not found: {path}")
    pre = preprocess_image(img)
    return image_to_text(pre)

def ocr_from_pdf(path, dpi=300):
    pages = convert_from_path(path, dpi=dpi)
    texts = []
    for p in pages:
        pre = preprocess_image(p)
        texts.append(image_to_text(pre))
    return "\n".join(texts)

_patterns = {
    "Age": r"age[:\s]*([0-9]{1,3})",
    "Sex": r"(?:sex|gender)[:\s]*([mf]|male|female)\b",
    "ChestPainType": r"(?:chest pain type|chestpain|cp type|cp)[:\s]*([A-Za-z0-9]{2,6})",
    "RestingBP": r"(?:resting bp|resting blood pressure|restbp)[:\s]*([0-9]{2,3})",
    "Cholesterol": r"(?:cholesterol|chol)[:\s]*([0-9]{2,4})",
    "FastingBS": r"(?:fasting bs|fasting blood sugar|fbs)[:\s]*([01])\b",
    "RestingECG": r"(?:resting ecg|rest ecg|ecg)[:\s]*([A-Za-z0-9 ]{2,12})",
    "MaxHR": r"(?:max heart rate|maxhr|max hr)[:\s]*([0-9]{2,3})",
    "ExerciseAngina": r"(?:exercise angina|exerciseangina|exang)[:\s]*([yn]|yes|no)\b",
    "Oldpeak": r"(?:oldpeak|st depression|old peak)[:\s]*([0-9]+(?:\.[0-9]+)?)",
    "ST_Slope": r"(?:st slope|slope)[:\s]*([A-Za-z]+)",
    "HeartDisease": r"(?:heart disease|heartdisease|target|hd)[:\s]*([01])\b"
}

_loose_number_re = re.compile(r"([0-9]+(?:\.[0-9]+)?)")

def norm_sex(s):
    if s is None: return None
    s = str(s).strip().lower()
    if s.startswith('m'): return 'M'
    if s.startswith('f'): return 'F'
    return None

def norm_yesno(s):
    if s is None: return None
    s = str(s).strip().lower()
    if s in ('y','yes','true','1'): return 'Y'
    if s in ('n','no','false','0'): return 'N'
    return None

def to_int_or_float(s):
    if s is None: return None
    s = str(s).strip()
    if re.fullmatch(r"[0-9]+", s):
        return int(s)
    try:
        return float(s)
    except:
        return None

def parse_medical_values(text):
    text_low = text.lower()
    out = {k: None for k in _patterns.keys()}

    # 1) label-based
    for key, pat in _patterns.items():
        m = re.search(pat, text_low, flags=re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if key == "Sex":
                out[key] = norm_sex(val)
            elif key == "ExerciseAngina":
                out[key] = norm_yesno(val)
            elif key in ("FastingBS","HeartDisease"):
                out[key] = int(val) if val.isdigit() else None
            elif key in ("RestingBP","Cholesterol","MaxHR","Age","Oldpeak"):
                out[key] = to_int_or_float(val)
            else:
                out[key] = val.upper() if isinstance(val, str) else val

    # 2) basic numeric fallback
    nums = [float(x) for x in _loose_number_re.findall(text_low)]
    def pick(nums, low, high):
        for n in nums:
            if low <= n <= high:
                return int(n) if float(n).is_integer() else n
        return None

    if out["Age"] is None:
        out["Age"] = pick(nums, 1, 120)
    if out["RestingBP"] is None:
        out["RestingBP"] = pick(nums, 50, 250)
    if out["Cholesterol"] is None:
        out["Cholesterol"] = pick(nums, 50, 800)
    if out["MaxHR"] is None:
        out["MaxHR"] = pick(nums, 60, 230)
    if out["Oldpeak"] is None:
        out["Oldpeak"] = pick(nums, 0, 12)

    # normalize some categorical
    if out["ChestPainType"] is not None:
        out["ChestPainType"] = out["ChestPainType"].upper()
    if out["RestingECG"] is not None:
        out["RestingECG"] = out["RestingECG"].strip().capitalize()
    if out["ST_Slope"] is not None:
        out["ST_Slope"] = out["ST_Slope"].strip().capitalize()

    return out

def ocr_to_row(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        text = ocr_from_pdf(path)
    else:
        text = ocr_from_image(path)
    parsed = parse_medical_values(text)
    row = {
        "Age": int(parsed["Age"]) if parsed["Age"] is not None else None,
        "Sex": parsed["Sex"],
        "ChestPainType": parsed["ChestPainType"],
        "RestingBP": int(parsed["RestingBP"]) if parsed["RestingBP"] is not None else None,
        "Cholesterol": float(parsed["Cholesterol"]) if parsed["Cholesterol"] is not None else None,
        "FastingBS": int(parsed["FastingBS"]) if parsed["FastingBS"] is not None else None,
        "RestingECG": parsed["RestingECG"],
        "MaxHR": int(parsed["MaxHR"]) if parsed["MaxHR"] is not None else None,
        "ExerciseAngina": parsed["ExerciseAngina"],
        "Oldpeak": float(parsed["Oldpeak"]) if parsed["Oldpeak"] is not None else None,
        "ST_Slope": parsed["ST_Slope"],
        "HeartDisease": int(parsed["HeartDisease"]) if parsed["HeartDisease"] is not None else None
    }
    return row
