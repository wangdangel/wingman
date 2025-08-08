import win32gui, win32con
from mss import mss
from PIL import Image
import pytesseract

def _get_window_rect(hwnd):
    rect = win32gui.GetWindowRect(hwnd)
    x1,y1,x2,y2 = rect
    return x1,y1,x2,y2

def screenshot_region(hwnd, crop_pct):
    x1,y1,x2,y2 = _get_window_rect(hwnd)
    w,h = x2-x1, y2-y1
    left = int(x1 + crop_pct['left'] * w)
    top = int(y1 + crop_pct['top'] * h)
    right = int(x1 + crop_pct['right'] * w)
    bottom = int(y1 + crop_pct['bottom'] * h)
    with mss() as sct:
        img = sct.grab({"left": left, "top": top, "width": right-left, "height": bottom-top})
        pil = Image.frombytes("RGB", img.size, img.rgb)
    return pil

def ocr_text(pil_image, lang="eng"):
    return pytesseract.image_to_string(pil_image, lang=lang)

def ocr_window_region(hwnd, crop_pct, lang="eng"):
    pil = screenshot_region(hwnd, crop_pct)
    text = ocr_text(pil, lang=lang)
    return text, pil
