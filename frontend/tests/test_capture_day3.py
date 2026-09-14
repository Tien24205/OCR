"""Exercise both input branches with supplied bytes, not a physical camera."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
import streamlit as st
from streamlit.testing.v1 import AppTest

from lib import api

CAPTURE = str(Path(__file__).resolve().parents[1] / "app_pages/capture.py")


def upload(data=None):
    if data is None:
        out = BytesIO()
        Image.new("RGB", (20, 12), "white").save(out, format="PNG")
        data = out.getvalue()
    return SimpleNamespace(name="card.png", type="image/png", getvalue=lambda: data)


@pytest.mark.parametrize("mode,widget", [("Chụp bằng camera", "camera_input"), ("Tải ảnh lên", "file_uploader")])
def test_each_input_sends_bytes_only_when_clicked(monkeypatch, mode, widget):
    destinations = []
    monkeypatch.setattr(st, "switch_page", destinations.append)
    item = upload()
    monkeypatch.setattr(st, widget, lambda *args, **kwargs: item)
    calls = []
    def save(name, data, mime):
        calls.append((name, data, mime))
        return {"id": "scan-1", "status": "pending"}
    monkeypatch.setattr(api, "create_scan", save)
    at = AppTest.from_file(CAPTURE)
    at.session_state["capture_mode"] = mode
    at.run()
    assert not at.exception
    assert calls == []
    at.button[0].click().run()
    assert not at.exception
    assert calls == [(item.name, item.getvalue(), item.type)]
    assert at.session_state["current_scan_id"] == "scan-1"
    assert destinations == ["app_pages/review.py"]
    assert "Đã lưu ảnh" in at.success[0].value
    at.run()
    assert len(calls) == 1  # An ordinary rerun must not submit again.


def test_invalid_image_shows_error_before_preview(monkeypatch):
    monkeypatch.setattr(st, "camera_input", lambda *a, **k: upload(b"not an image"))
    at = AppTest.from_file(CAPTURE).run()
    assert not at.exception
    assert at.error
    assert not at.button


def test_upload_api_failure_is_visible(monkeypatch):
    monkeypatch.setattr(st, "camera_input", lambda *a, **k: upload())
    def fail(*args):
        raise api.ApiError("SCAN_SAVE_FAILED", "Chưa lưu được ảnh.", True, 500)
    monkeypatch.setattr(api, "create_scan", fail)
    at = AppTest.from_file(CAPTURE).run()
    at.button[0].click().run()
    assert not at.exception
    assert at.error[0].value == "Chưa lưu được ảnh."
    assert not at.success
