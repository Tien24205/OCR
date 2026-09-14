from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.config import BACKEND_DIR, Settings
from app.services.providers import build_ocr, build_extractor
from app.services.ocr.base import OcrError
from app.services.extract.base import ExtractionError


def test_relative_credentials_anchor_to_backend():
    config = Settings(_env_file=None, google_application_credentials="./secrets/test.json")
    assert config.credentials_path == (BACKEND_DIR / "secrets/test.json").resolve()


def test_google_factory_explicitly_passes_config_credentials(monkeypatch, tmp_path):
    from app.services.ocr import google_vision
    client = Mock()
    client.annotate_image.return_value = SimpleNamespace(
        error=SimpleNamespace(message=""), full_text_annotation=SimpleNamespace(text="山田 太郎", pages=[]))
    constructor = Mock(return_value=client)
    monkeypatch.setattr(google_vision.vision.ImageAnnotatorClient, "from_service_account_file", constructor)
    config = Settings(_env_file=None, ocr_provider="google", google_application_credentials=str(tmp_path / "test.json"))
    provider = build_ocr(config)
    constructor.assert_called_once_with(str(config.credentials_path))
    result = provider.recognize(b"test", "image/png")
    assert result.raw_text == "山田 太郎"
    args = client.annotate_image.call_args.kwargs
    assert args["timeout"] == 20 and args["retry"] is None
    # Doi chieu voi cau hinh thay vi mot danh sach co dinh: goi y ngon ngu la
    # gia tri cau hinh duoc, va da doi tu "ja,en" sang bon ngon ngu cua de goc.
    assert list(args["request"].image_context.language_hints) == config.language_hint_list
    assert set(config.language_hint_list) == {"ja", "en", "ko", "zh"}
    provider.close()
    client.transport.close.assert_called_once()


def test_gemini_factory_sets_schema_and_timeout_and_preserves_japanese(monkeypatch):
    from app.services.extract import gemini
    client = Mock()
    client.models.generate_content.return_value = SimpleNamespace(text='{"full_names":[{"value":"山田 太郎"}]}')
    constructor = Mock(return_value=client)
    monkeypatch.setattr(gemini.genai, "Client", constructor)
    config = Settings(_env_file=None, extractor="gemini", gemini_api_key="unit-test-key", gemini_model="test-model")
    extractor = build_extractor(config)
    assert constructor.call_args.kwargs["http_options"].timeout == 30000
    assert constructor.call_args.kwargs["http_options"].retry_options.attempts == 1
    result = extractor.extract(b"test", "image/png", "山田 太郎")
    assert result.full_names[0].value == "山田 太郎"
    call = client.models.generate_content.call_args.kwargs
    assert call["model"] == "test-model" and call["config"].response_schema is gemini.CardExtraction
    extractor.close()
    client.close.assert_called_once()


def test_gemini_invalid_output_has_no_provider_content_in_error(monkeypatch):
    from app.services.extract import gemini
    client = Mock()
    client.models.generate_content.return_value = SimpleNamespace(text="private-canary-bad-json")
    monkeypatch.setattr(gemini.genai, "Client", lambda **kwargs: client)
    extractor = gemini.GeminiExtractor("unit-test-key", "test-model")
    with pytest.raises(ExtractionError) as caught:
        extractor.extract(b"test", "image/png", "test")
    assert caught.value.code == "EXTRACT_BAD_SCHEMA"
    assert "private-canary" not in caught.value.message


def test_unknown_configuration_does_not_fall_back_to_mock():
    with pytest.raises(OcrError):
        build_ocr(Settings(_env_file=None, ocr_provider="typo"))
    with pytest.raises(ExtractionError):
        build_extractor(Settings(_env_file=None, extractor="typo"))
