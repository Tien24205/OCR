"""Streamlit page tests; provider calls are represented by API responses."""
from io import BytesIO
from pathlib import Path
import time

from PIL import Image
import pytest
from streamlit.testing.v1 import AppTest

from lib import api

REVIEW = str(Path(__file__).resolve().parents[1] / "app_pages/review.py")


@pytest.fixture
def page(monkeypatch):
    out = BytesIO()
    Image.new("RGB", (20, 12), "white").save(out, format="PNG")
    monkeypatch.setattr(api, "get_image", lambda ref: out.getvalue())

    # CHAN MOI LOI GOI MANG THAT, khong chan tung ham mot.
    #
    # Trang nay con goi `list_scans`, `organization_choices` va
    # `scan_duplicates` ngoai `get_scan`. Khi backend khong chay, MOI loi goi
    # khong duoc chan mat ~2,5s moi bao loi - vuot timeout 3s mac dinh cua
    # AppTest, va test do vi mot ly do khong lien quan gi den thu dang kiem.
    #
    # Chan o `_request` chu khong o tung ham: moi loi goi deu di qua day, nen
    # trang co them API moi cung khong lam sau test nay do lai. Trang da duoc
    # thiet ke de chay tiep khi cac loi goi phu that bai, nen ApiError o day
    # dung la duong ma no von xu ly.
    def _khong_goi_mang(method, path, **kwargs):
        raise api.ApiError("BACKEND_UNREACHABLE", f"(test) {method} {path}",
                           retryable=True, status=0)

    monkeypatch.setattr(api, "_request", _khong_goi_mang)
    at = AppTest.from_file(REVIEW)
    at.session_state["current_scan_id"] = "scan-1"
    return at


def result(name="山田 太郎"):
    return {"id": "scan-1", "status": "ocr_done", "image_ref": "a" * 64,
            "raw_text": name, "is_mock": True, "ocr_provider": "mock:synthetic", "extractor": "test",
            "draft": {"fields": {"full_names": [{"value": name, "needs_review": False}]}},
            "grounding": {"counts": {"exact": 1}, "report": {}}}


@pytest.mark.parametrize("name", ["Jane Doe", "山田 太郎"])
def test_shows_terminal_draft_and_stops_polling(page, monkeypatch, name):
    calls = []
    def fetch(scan_id):
        calls.append(scan_id)
        return result(name)
    monkeypatch.setattr(api, "get_scan", fetch)
    page.run()
    assert not page.exception
    assert any(item.value == name for item in page.text)
    assert any("mock" in item.value for item in page.warning)
    page.run()
    assert calls == ["scan-1"]


def test_polling_pending_then_completed(page, monkeypatch):
    values = iter([{"id": "scan-1", "status": "processing"}, result()])
    monkeypatch.setattr(api, "get_scan", lambda scan_id: next(values))
    page.run()
    assert not page.exception and page.status
    page.run()
    assert not page.exception and page.session_state["scan_result"]["status"] == "ocr_done"


def test_timeout_stops_polling_and_manual_check_is_read_only(page, monkeypatch):
    calls = []
    monkeypatch.setattr(api, "get_scan", lambda scan_id: calls.append(scan_id) or result())
    page.session_state["scan_poll"] = {"id": "scan-1", "started": time.monotonic() - 61, "error": None}
    page.run()
    assert not page.exception and "60 giây" in page.warning[0].value
    page.run()
    assert calls == []
    page.button[0].click().run()
    assert not page.exception and calls == ["scan-1"]


def test_network_error_stops_poll_and_shows_message(page, monkeypatch):
    calls = []
    def unavailable(scan_id):
        calls.append(scan_id)
        raise api.ApiError("BACKEND_UNREACHABLE", "Mất kết nối backend", True, 0)
    monkeypatch.setattr(api, "get_scan", unavailable)
    page.run()
    assert not page.exception and "Mất kết nối" in page.warning[0].value
    page.run()
    assert calls == ["scan-1"]


def test_retry_sends_post_once_and_shows_preserved_ocr(page, monkeypatch):
    failure = {**result(), "status": "failed", "error_code": "EXTRACT_BAD_SCHEMA",
               "error_message": "Trích xuất lỗi", "draft": None, "can_retry": True, "retry_count": 0}
    page.session_state["scan_result"] = failure
    calls = []
    monkeypatch.setattr(api, "retry_scan", lambda scan_id: calls.append(scan_id) or {"status": "pending"})
    monkeypatch.setattr(api, "get_scan", lambda scan_id: result())
    page.run()
    assert not page.exception and page.error[0].value == "Trích xuất lỗi"
    assert any(item.value == "山田 太郎" for item in page.text)
    page.button[0].click().run()
    page.run()
    assert not page.exception and calls == ["scan-1"]
