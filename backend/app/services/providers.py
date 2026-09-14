"""Construct only the configured provider; never silently switch to a mock."""
from app.config import Settings
from app.services.ocr.base import OcrError
from app.services.extract.base import ExtractionError


def build_ocr(config: Settings):
    if config.ocr_provider == "mock":
        from app.services.ocr.mock import MockOcrProvider
        return MockOcrProvider()
    if config.ocr_provider == "google":
        from app.services.ocr.google_vision import GoogleVisionProvider
        return GoogleVisionProvider(config.language_hint_list, config.ocr_timeout_s, config.credentials_path)
    raise OcrError("OCR_NOT_CONFIGURED", "OCR_PROVIDER phải là google hoặc mock.")


def build_extractor(config: Settings):
    if config.extractor == "heuristic":
        from app.services.extract.heuristic import HeuristicExtractor
        return HeuristicExtractor()
    if config.extractor == "gemini":
        from app.services.extract.gemini import GeminiExtractor
        return GeminiExtractor(config.gemini_api_key, config.gemini_model,
                               config.gemini_temperature, config.extract_timeout_s)
    raise ExtractionError("EXTRACTOR_NOT_CONFIGURED", "EXTRACTOR phải là gemini hoặc heuristic.")
