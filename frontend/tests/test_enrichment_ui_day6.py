"""Frontend research polling, without external services."""
import time
from pathlib import Path

from streamlit.testing.v1 import AppTest

from lib import api


def app(monkeypatch):
    monkeypatch.setattr(api, "health", lambda: {"env": "test", "config": {
        "ocr_provider": "mock", "ocr_credentials_present": False, "gemini_key_present": False,
        "gemini_model_set": False, "extractor": "heuristic", "enrich_enabled": True}})
    monkeypatch.setattr(api, "get_image", lambda ref: b"bad-image")
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "streamlit_app.py"), default_timeout=15)
    at.session_state["current_scan_id"] = "scan-1"
    at.session_state["scan_result"] = {"id": "scan-1", "status": "ocr_done", "image_ref": "a" * 64,
                                       "draft_revision": 0, "draft": {"fields": {}}, "raw_text": "山田 太郎"}
    at.session_state["research:scan-1:0"] = {"job": {"status": "processing", "organization_id": "org-1"},
                                           "started": time.monotonic() - 61, "poll_error": None}
    return at


def test_timeout_does_not_start_another_research_job(monkeypatch):
    at = app(monkeypatch)
    calls = []
    monkeypatch.setattr(api, "get_research", lambda org_id: calls.append(org_id) or {
        "status": "done", "organization_id": org_id, "draft_revision": 0, "enrichments": [], "reason": "NO_DOMAIN_ON_CARD"})
    at.switch_page("app_pages/review.py").run()
    assert not at.exception and any("60 giây" in item.value for item in at.warning)
    assert calls == []
    next(button for button in at.button if button.label == "Kiểm tra trạng thái").click().run()
    assert not at.exception and calls == ["org-1"]


def test_network_error_stops_polling_and_keeps_ocr(monkeypatch):
    at = app(monkeypatch)
    at.session_state["research:scan-1:0"]["started"] = time.monotonic()
    calls = []
    def fail(org_id):
        calls.append(org_id)
        raise api.ApiError("BACKEND_UNREACHABLE", "Mất kết nối", True, 0)
    monkeypatch.setattr(api, "get_research", fail)
    at.switch_page("app_pages/review.py").run()
    assert not at.exception and any(item.value == "Mất kết nối" for item in at.warning)
    at.run()
    assert calls == ["org-1"] and any(item.value == "山田 太郎" for item in at.text)
