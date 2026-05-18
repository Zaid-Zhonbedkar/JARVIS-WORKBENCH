"""
JARVIS Vision Module
Screen capture, OCR, and AI-powered screen understanding.
Uses OpenCV + pytesseract + optional LLaVA vision model.
"""

import time
import threading
from pathlib import Path
from core.config import Config


class VisionModule:
    """
    Provides screen capture, OCR text extraction,
    and AI vision-based screen understanding.
    """

    def __init__(self, config: Config):
        self.config = config
        self._screenshot_dir = config.get_screenshot_path()
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._last_screenshot = None
        self._ocr_cache = {}

    # ------------------------------------------------------------------ #
    #  Screen capture
    # ------------------------------------------------------------------ #

    def capture_screen(self, region: tuple = None) -> "np.ndarray":
        """
        Capture the current screen (or a region).
        region: (x, y, width, height) or None for full screen.
        Returns numpy array (BGR).
        """
        import cv2
        import numpy as np

        try:
            # Try mss (fastest cross-platform screen capture)
            import mss
            with mss.mss() as sct:
                if region:
                    monitor = {"top": region[1], "left": region[0], "width": region[2], "height": region[3]}
                else:
                    monitor = sct.monitors[1]  # primary monitor
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                self._last_screenshot = img
                return img
        except ImportError:
            pass

        # Fallback: PIL
        from PIL import ImageGrab
        img_pil = ImageGrab.grab(bbox=region)
        import numpy as np
        img = np.array(img_pil)
        img = img[:, :, ::-1].copy()  # RGB to BGR
        self._last_screenshot = img
        return img

    def save_screenshot(self, suffix: str = "") -> Path:
        """Capture and save a screenshot. Returns path."""
        img = self.capture_screen()
        import cv2
        ts = time.strftime("%Y%m%d_%H%M%S")
        name = f"screen_{ts}{suffix}.png"
        path = self._screenshot_dir / name
        cv2.imwrite(str(path), img)
        return path

    # ------------------------------------------------------------------ #
    #  OCR
    # ------------------------------------------------------------------ #

    def ocr_screen(self, region: tuple = None) -> str:
        """
        Run OCR on the current screen (or region).
        Returns extracted text.
        """
        try:
            import pytesseract
            import cv2

            img = self.capture_screen(region)
            # Preprocess for better OCR accuracy
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
            text = pytesseract.image_to_string(gray, lang="eng")
            return text.strip()
        except ImportError:
            return "[pytesseract not installed]"
        except Exception as e:
            return f"[OCR error: {e}]"

    def ocr_image(self, image_path: str) -> str:
        """Run OCR on a specific image file."""
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(image_path)
            return pytesseract.image_to_string(img).strip()
        except Exception as e:
            return f"[OCR error: {e}]"

    def extract_text_blocks(self, region: tuple = None) -> list[dict]:
        """
        Return OCR results as structured blocks with bounding boxes.
        Useful for finding clickable UI elements.
        """
        try:
            import pytesseract
            import cv2

            img = self.capture_screen(region)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)

            blocks = []
            for i in range(len(data["text"])):
                text = data["text"][i].strip()
                if text and int(data["conf"][i]) > 50:
                    blocks.append({
                        "text": text,
                        "x": data["left"][i],
                        "y": data["top"][i],
                        "w": data["width"][i],
                        "h": data["height"][i],
                        "conf": data["conf"][i],
                    })
            return blocks
        except Exception as e:
            return [{"text": f"Error: {e}", "x": 0, "y": 0, "w": 0, "h": 0, "conf": 0}]

    # ------------------------------------------------------------------ #
    #  AI screen understanding
    # ------------------------------------------------------------------ #

    def describe_screen(self) -> str:
        """
        Use a vision model (LLaVA via Ollama) to describe the current screen.
        Falls back to OCR if vision model is unavailable.
        """
        try:
            path = self.save_screenshot("_describe")
            return self._llava_describe(str(path))
        except Exception as e:
            print(f"[Vision] LLaVA unavailable ({e}), falling back to OCR")
            return self.ocr_screen()

    def _llava_describe(self, image_path: str) -> str:
        """Send image to LLaVA via Ollama for description."""
        import base64
        import httpx

        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        payload = {
            "model": self.config.vision.vision_model,
            "prompt": (
                "Describe what is on this computer screen in detail. "
                "Note any text, open applications, and what the user might be doing."
            ),
            "images": [b64],
            "stream": False,
        }
        host = self.config.ai.ollama_host
        r = httpx.post(f"{host}/api/generate", json=payload, timeout=30)
        r.raise_for_status()
        return r.json().get("response", "")

    def find_text_on_screen(self, target: str) -> dict | None:
        """
        Find where a piece of text appears on screen.
        Returns bounding box dict or None.
        """
        blocks = self.extract_text_blocks()
        target_lower = target.lower()
        for block in blocks:
            if target_lower in block["text"].lower():
                return block
        return None

    # ------------------------------------------------------------------ #
    #  OpenCV utilities
    # ------------------------------------------------------------------ #

    def detect_active_window_region(self) -> tuple:
        """
        Try to detect the active/focused window region.
        Returns (x, y, w, h).
        """
        try:
            import subprocess
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowgeometry", "--shell"],
                capture_output=True, text=True
            )
            geo = {}
            for line in result.stdout.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    geo[k.strip()] = int(v.strip())
            return (geo.get("X", 0), geo.get("Y", 0), geo.get("WIDTH", 1920), geo.get("HEIGHT", 1080))
        except Exception:
            return (0, 0, 1920, 1080)

    def compare_screens(self, img1, img2) -> float:
        """
        Return similarity score between two screen captures (0.0-1.0).
        Useful for detecting screen changes.
        """
        import cv2
        import numpy as np
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        score, _ = cv2.quality.QualitySSIM_compute(gray1, gray2)
        return float(score[0])
