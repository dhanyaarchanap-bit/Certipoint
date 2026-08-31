"""
OCR and Image/PDF Preprocessing Engine.
Extracts text from images and PDF files using pdfplumber, pytesseract, and OpenCV.
"""

import os
import shutil
import logging
from typing import Dict, Any, Tuple, Optional, Union
import numpy as np
from PIL import Image
import cv2
import pdfplumber
import pytesseract

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Search for Tesseract Binary on Windows / Linux / macOS
TESSERACT_SEARCH_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    os.path.expanduser(r"~\AppData\Local\Tesseract-OCR\tesseract.exe"),
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
    "/opt/homebrew/bin/tesseract"
]


def find_and_configure_tesseract() -> bool:
    """Detect and configure Tesseract executable path."""
    # 1. Check if already in PATH
    which_path = shutil.which("tesseract")
    if which_path:
        pytesseract.pytesseract.tesseract_cmd = which_path
        return True

    # 2. Check environment variable
    env_path = os.environ.get("TESSERACT_CMD")
    if env_path and os.path.exists(env_path):
        pytesseract.pytesseract.tesseract_cmd = env_path
        return True

    # 3. Check known installation directories
    for path in TESSERACT_SEARCH_PATHS:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return True

    return False


# Attempt initial configuration
IS_TESSERACT_AVAILABLE = find_and_configure_tesseract()


def is_tesseract_installed() -> bool:
    """Return whether Tesseract OCR engine is detected."""
    global IS_TESSERACT_AVAILABLE
    if not IS_TESSERACT_AVAILABLE:
        IS_TESSERACT_AVAILABLE = find_and_configure_tesseract()
    return IS_TESSERACT_AVAILABLE


def preprocess_image_cv2(image_input: Union[str, bytes, Image.Image, np.ndarray]) -> np.ndarray:
    """
    Advanced OpenCV image preprocessing pipeline for high OCR accuracy:
    1. Color space conversion to Grayscale
    2. Bilateral filtering for edge-preserving noise reduction
    3. Contrast Limited Adaptive Histogram Equalization (CLAHE)
    4. Otsu's optimal thresholding binarization
    """
    # Load into OpenCV BGR / Gray format
    if isinstance(image_input, str):
        img = cv2.imread(image_input)
        if img is None:
            pil_img = Image.open(image_input).convert("RGB")
            img = np.array(pil_img)[:, :, ::-1]
    elif isinstance(image_input, bytes):
        nparr = np.frombuffer(image_input, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            import io
            pil_img = Image.open(io.BytesIO(image_input)).convert("RGB")
            img = np.array(pil_img)[:, :, ::-1]
    elif isinstance(image_input, Image.Image):
        pil_img = image_input.convert("RGB")
        img = np.array(pil_img)[:, :, ::-1]
    elif isinstance(image_input, np.ndarray):
        img = image_input.copy()
    else:
        raise ValueError(f"Unsupported image input type: {type(image_input)}")

    # Convert to grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    # Resize if resolution is too low for OCR
    h, w = gray.shape
    if w < 1000 or h < 800:
        scale = max(1000.0 / w, 800.0 / h)
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

    # 1. Bilateral filter (smooths noise while preserving text edges)
    denoised = cv2.bilateralFilter(gray, 9, 75, 75)

    # 2. CLAHE (Adaptive histogram equalization for uneven lighting / shadows)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast = clahe.apply(denoised)

    # 3. Otsu binarization
    _, thresh = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return thresh


def extract_text_from_image(image_input: Union[str, bytes, Image.Image, np.ndarray]) -> Tuple[str, float, str]:
    """
    Extract text from an image with preprocessing and confidence metrics.
    If Tesseract is installed, uses OpenCV + Pytesseract.
    If Tesseract is missing, provides metadata-assisted fallback and logs guidance.
    Returns (extracted_text, ocr_quality_score, method_used).
    """
    if is_tesseract_installed():
        try:
            processed_img = preprocess_image_cv2(image_input)

            # Run pytesseract data extraction to get confidence scores
            data = pytesseract.image_to_data(processed_img, output_type=pytesseract.Output.DICT)
            confidences = []

            n_boxes = len(data["text"])
            for i in range(n_boxes):
                word = data["text"][i].strip()
                conf = float(data["conf"][i])
                if word and conf > 0:
                    confidences.append(conf)

            full_text = pytesseract.image_to_string(processed_img, config="--psm 6")
            if not full_text.strip():
                full_text = pytesseract.image_to_string(processed_img, config="--psm 3")

            avg_conf = float(np.mean(confidences)) if confidences else 75.0
            return full_text.strip(), avg_conf, "Tesseract OCR (OpenCV Preprocessed)"

        except Exception as e:
            logger.error(f"Image OCR failed: {str(e)}")
            try:
                if isinstance(image_input, (str, bytes)):
                    import io
                    pil_img = Image.open(image_input if isinstance(image_input, str) else io.BytesIO(image_input))
                    direct_text = pytesseract.image_to_string(pil_img)
                    return direct_text.strip(), 65.0, "Tesseract OCR (Direct)"
            except Exception:
                pass

    # Fallback when Tesseract is not installed on the system
    # Check image attributes and attempt basic metadata extraction
    try:
        if isinstance(image_input, (str, bytes)):
            import io
            pil_img = Image.open(image_input if isinstance(image_input, str) else io.BytesIO(image_input))
            w, h = pil_img.size
            quality_score = 65.0 if w >= 800 and h >= 600 else 45.0
            
            # Check for embedded text in PNG / EXIF metadata if present
            meta_texts = []
            for k, v in pil_img.info.items():
                if isinstance(v, str) and len(v.strip()) > 3:
                    meta_texts.append(f"{k}: {v}")
            
            combined_meta = "\n".join(meta_texts)
            if combined_meta:
                return combined_meta, quality_score, "Image Metadata Stream"
            
            return "", quality_score, "Image Uploaded (Tesseract engine optional for scanned text)"
    except Exception as e:
        logger.warning(f"Image metadata inspection failed: {e}")

    return "", 50.0, "Image Uploaded"


def extract_text_from_pdf(pdf_path_or_bytes: Union[str, bytes]) -> Tuple[str, float, str]:
    """
    Extract text from PDF file using pdfplumber native text extraction,
    with OCR fallback if PDF contains scanned image pages.
    Returns (extracted_text, confidence_score, method_used).
    """
    extracted_text_chunks = []
    has_native_text = False

    try:
        import io
        pdf_source = io.BytesIO(pdf_path_or_bytes) if isinstance(pdf_path_or_bytes, bytes) else pdf_path_or_bytes

        with pdfplumber.open(pdf_source) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text and len(page_text.strip()) > 30:
                    extracted_text_chunks.append(page_text.strip())
                    has_native_text = True
                else:
                    # If page has little or no text stream, render to image and apply OCR
                    if is_tesseract_installed():
                        try:
                            page_img = page.to_image(resolution=300).original
                            ocr_text, _, _ = extract_text_from_image(page_img)
                            if ocr_text:
                                extracted_text_chunks.append(ocr_text)
                        except Exception as e:
                            logger.warning(f"PDF page {page_idx} OCR rendering failed: {e}")

        combined_text = "\n\n".join(extracted_text_chunks).strip()

        if combined_text:
            conf = 95.0 if has_native_text else 85.0
            method = "PDF Native Stream (pdfplumber)" if has_native_text else "PDF OCR Stream"
            return combined_text, conf, method
        else:
            return "", 20.0, "Empty PDF content"

    except Exception as e:
        logger.error(f"PDF extraction failed: {str(e)}")
        return "", 0.0, f"PDF Extraction Error: {str(e)}"


def process_certificate_file(file_path_or_bytes: Union[str, bytes], file_name: str) -> Dict[str, Any]:
    """
    Unified entry point to extract text and analyze any uploaded certificate (PDF or Image).
    Returns a structured dictionary with raw text, OCR quality confidence, and metadata.
    """
    ext = os.path.splitext(file_name)[1].lower()

    if ext == ".pdf":
        raw_text, ocr_conf, method = extract_text_from_pdf(file_path_or_bytes)
        file_type = "PDF Document"
    elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"]:
        raw_text, ocr_conf, method = extract_text_from_image(file_path_or_bytes)
        file_type = f"Image ({ext.replace('.', '').upper()})"
    else:
        return {
            "success": False,
            "raw_text": "",
            "ocr_confidence": 0.0,
            "method": "Unsupported Format",
            "file_type": "Unknown",
            "error": f"Unsupported file extension '{ext}'. Please upload PDF, JPG, JPEG, or PNG."
        }

    return {
        "success": True if raw_text else False,
        "raw_text": raw_text,
        "ocr_confidence": ocr_conf,
        "method": method,
        "file_type": file_type,
        "tesseract_available": is_tesseract_installed()
    }
