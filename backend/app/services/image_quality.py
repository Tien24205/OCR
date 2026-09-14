"""Image Quality Agent: Assesses image before OCR."""
from __future__ import annotations

import io
from PIL import Image, ImageStat, ImageFilter
import logging

logger = logging.getLogger(__name__)


class ImageQualityAgent:
    """Evaluates image quality metrics to decide if OCR should proceed."""

    def __init__(self):
        pass

    def assess(self, image_bytes: bytes) -> dict:
        """Bounded signed Laplacian variance; thresholds are uncalibrated rules.

        EXIF orientation is handled at upload. Portrait aspect is only a hint:
        pixels alone cannot reliably establish upside-down/mirrored text.
        """
        try:
            with Image.open(io.BytesIO(image_bytes)) as source:
                width, height = source.size
                gray = source.convert("L")
                gray.thumbnail((512, 512))
                stat = ImageStat.Stat(gray)
                brightness, contrast = stat.mean[0], stat.stddev[0]
                w, h = gray.size
                pixels = gray.tobytes()
                total = squares = count = 0
                for y in range(1, h - 1):
                    for x in range(1, w - 1):
                        i = y * w + x
                        lap = 4 * pixels[i] - pixels[i-1] - pixels[i+1] - pixels[i-w] - pixels[i+w]
                        total += lap
                        squares += lap * lap
                        count += 1
                variance = max(0.0, squares / count - (total / count)**2) if count else 0.0
            issues = []
            if brightness < 40:
                issues.append("too_dark")
            if brightness > 240:
                issues.append("too_bright")
            if contrast < 20:
                issues.append("low_contrast")
            if variance < 20:
                issues.append("blurry")
            if height > width:
                issues.append("check_orientation")
            severe = contrast < 4 or variance < 2 or min(width, height) < 32
            return {"action": "recapture" if severe else "warn" if issues else "accept",
                    "issues": issues, "orientation": "portrait_check" if height > width else "unknown",
                    "metrics": {"brightness": round(brightness, 2), "contrast": round(contrast, 2),
                                "laplacian_variance": round(variance, 2)}}
        except (OSError, ValueError):
            return {"action": "recapture", "issues": ["image_unreadable"], "metrics": {}, "orientation": "unknown"}

    def evaluate(self, image_bytes: bytes) -> dict:
        """
        Evaluate image brightness, contrast, and blurriness.
        Returns a dict of metrics and an assessment flag.
        """
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("L")  # Convert to grayscale
            
            # Brightness & Contrast (using RMS contrast)
            stat = ImageStat.Stat(image)
            brightness = stat.mean[0]
            contrast = stat.stddev[0]
            
            # Blurriness estimate using Laplacian variance approximation
            # Since PIL doesn't have cv2.Laplacian, we use FIND_EDGES as a proxy
            edges = image.filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(edges)
            blur_score = edge_stat.var[0]
            
            # Thresholds (heuristics, may need tuning based on actual dataset)
            is_too_dark = brightness < 40
            is_too_bright = brightness > 240
            is_low_contrast = contrast < 20
            is_blurry = blur_score < 100  # Low edge variance -> blurry
            
            is_acceptable = not (is_too_dark or is_too_bright or is_low_contrast or is_blurry)
            
            issues = []
            if is_too_dark:
                issues.append("too_dark")
            if is_too_bright:
                issues.append("too_bright")
            if is_low_contrast:
                issues.append("low_contrast")
            if is_blurry:
                issues.append("blurry")

            return {
                "acceptable": is_acceptable,
                "issues": issues,
                "metrics": {
                    "brightness": round(brightness, 2),
                    "contrast": round(contrast, 2),
                    "blur_score": round(blur_score, 2),
                }
            }
        except Exception as e:
            logger.warning(f"ImageQualityAgent failed to evaluate: {e}")
            # Fallback to acceptable if evaluation fails
            return {"acceptable": True, "issues": [], "metrics": {}}


def contrast_variant(image_bytes: bytes) -> bytes:
    """Same geometry, reproducible contrast change; no guessed rotation."""
    from PIL import ImageOps, ImageEnhance
    with Image.open(io.BytesIO(image_bytes)) as source:
        image = ImageEnhance.Contrast(ImageOps.autocontrast(source.convert("RGB"))).enhance(1.5)
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()
