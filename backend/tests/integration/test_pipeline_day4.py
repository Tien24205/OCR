"""Real HTTP/SQLite/files + controlled providers; these do not measure OCR accuracy."""
from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app import main, pipeline
from app.config import Settings, get_settings
from app.db import get_db
from app.models import Base, Scan, Contact
from app.services.ocr.base import OcrError, OcrResult
from app.services.extract.base import CardExtraction, ExtractedValue, PhoneValue, ExtractionError


@pytest.fixture
def system(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'day4.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    config = Settings(_env_file=None, image_dir=tmp_path / "images", ocr_provider="mock", extractor="heuristic")
    def database():
        with factory() as db:
            yield db
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(pipeline, "_sleep", lambda seconds: None)
    main.app.dependency_overrides[get_db] = database
    main.app.dependency_overrides[get_settings] = lambda: config
    main.app.dependency_overrides[main.get_session_factory] = lambda: factory
    output = BytesIO()
    Image.new("RGB", (32, 20), "white").save(output, format="PNG")
    with TestClient(main.app) as client:
        yield SimpleNamespace(client=client, factory=factory, config=config, image=output.getvalue())
    main.app.dependency_overrides.clear()
    engine.dispose()


def send(system):
    response = system.client.post("/api/scans", files={"file": ("card.png", system.image, "image/png")})
    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    return response.json()["id"]


def providers(monkeypatch, raw="Jane Doe\nExample Inc.\njane@example.com\nTel: 03-1234-5678", name="Jane Doe", company="Example Inc."):
    calls = {"ocr": 0, "extract": 0}
    def recognize(image, mime):
        calls["ocr"] += 1
        return OcrResult(raw_text=raw, provider="mock:synthetic", provider_version="test", detected_languages=["ja" if name == "山田 太郎" else "en"])
    def extract(image, mime, raw_text):
        calls["extract"] += 1
        return CardExtraction(full_names=[ExtractedValue(value=name)], company_names=[ExtractedValue(value=company)],
                              emails=[ExtractedValue(value="jane@example.com"), ExtractedValue(value="invented@fake.org")],
                              phones=[PhoneValue(value="03-1234-5678", label="tel")])
    ocr = SimpleNamespace(recognize=recognize)
    extractor = SimpleNamespace(name="test", extract=extract)
    monkeypatch.setattr(pipeline, "build_ocr", lambda config: ocr)
    monkeypatch.setattr(pipeline, "build_extractor", lambda config: extractor)
    return calls, ocr, extractor


@pytest.mark.parametrize("name,company", [("Jane Doe", "Example Inc."), ("山田 太郎", "株式会社サンプル")])
def test_pipeline_english_and_japanese_persists_grounded_draft(system, monkeypatch, name, company):
    raw = f"{name}\n{company}\njane@example.com\nTel: 03-1234-5678"
    calls, _, _ = providers(monkeypatch, raw, name, company)
    scan_id = send(system)
    result = system.client.get(f"/api/scans/{scan_id}").json()
    assert result["status"] == "ocr_done" and result["is_mock"]
    assert result["raw_text"] == raw
    fields = result["draft"]["fields"]
    assert fields["full_names"][0]["value"] == name
    assert fields["company_names"][0]["value"] == company
    assert [x["value"] for x in fields["emails"]] == ["jane@example.com"]
    assert fields["phones"][0]["value"] == "03-1234-5678"
    assert fields["addresses"] == []
    assert result["grounding"]["counts"]["unverified"] == 1
    assert result["ms_ocr"] >= 0 and result["ms_extract"] >= 0
    with system.factory() as db:
        scan = db.get(Scan, scan_id)
        assert len(scan.extraction_json["emails"]) == 2  # Original extraction kept.
        assert db.scalar(select(func.count()).select_from(Contact)) == 0
    for _ in range(3):
        assert system.client.get(f"/api/scans/{scan_id}").json() == result
    pipeline.run_scan(scan_id, system.config, system.factory)
    assert calls == {"ocr": 1, "extract": 1}
    image = system.client.get(f"/api/images/{result['image_ref']}")
    assert image.status_code == 200 and image.content == system.image
    assert image.headers["content-type"] == "image/png"


def test_extraction_failure_keeps_ocr_and_retry_resumes_from_checkpoint(system, monkeypatch):
    calls, _, extractor = providers(monkeypatch)
    success = extractor.extract
    def fail(*args):
        # Check from another DB session that OCR evidence was already committed.
        with system.factory() as db:
            scan = db.scalar(select(Scan))
            assert scan.status == "processing" and scan.raw_text.startswith("Jane")
        raise ExtractionError("EXTRACT_BAD_SCHEMA", "Đầu ra không đúng schema.")
    extractor.extract = fail
    scan_id = send(system)
    before = system.client.get(f"/api/scans/{scan_id}").json()
    assert before["status"] == "failed" and before["raw_text"] and before["draft"] is None
    extractor.extract = success
    assert system.client.post(f"/api/scans/{scan_id}/retry").status_code == 202
    after = system.client.get(f"/api/scans/{scan_id}").json()
    assert after["status"] == "ocr_done" and after["retry_count"] == 1
    assert after["raw_text"] == before["raw_text"] and after["ms_ocr"] == before["ms_ocr"]
    assert calls == {"ocr": 1, "extract": 1}
    assert system.client.post(f"/api/scans/{scan_id}/retry").status_code == 409


def test_transient_ocr_retries_twice_then_succeeds(system, monkeypatch):
    calls, ocr, _ = providers(monkeypatch)
    success = ocr.recognize
    attempts = []
    def flaky(*args):
        attempts.append(1)
        if len(attempts) < 3:
            raise OcrError("OCR_UNAVAILABLE", "Tạm thời lỗi", retryable=True)
        return success(*args)
    ocr.recognize = flaky
    scan_id = send(system)
    assert system.client.get(f"/api/scans/{scan_id}").json()["status"] == "ocr_done"
    assert len(attempts) == 3


def test_retry_limit_and_nonretryable_ocr_does_not_loop(system, monkeypatch):
    _, ocr, _ = providers(monkeypatch)
    attempts = []
    def fail(*args):
        attempts.append(1)
        raise OcrError("OCR_NOT_CONFIGURED", "Thiếu cấu hình")
    ocr.recognize = fail
    scan_id = send(system)
    for _ in range(3):
        assert system.client.post(f"/api/scans/{scan_id}/retry").status_code == 202
    assert len(attempts) == 4
    assert system.client.post(f"/api/scans/{scan_id}/retry").status_code == 409
    result = system.client.get(f"/api/scans/{scan_id}").json()
    assert not result["can_retry"] and result["retry_count"] == 3


def test_blank_ocr_is_failure_and_does_not_call_extraction(system, monkeypatch):
    calls, _, _ = providers(monkeypatch, raw=" \n ")
    scan_id = send(system)
    result = system.client.get(f"/api/scans/{scan_id}").json()
    assert result["status"] == "failed" and result["error_code"] == "OCR_EMPTY"
    assert result["raw_text"] == " \n " and calls["extract"] == 0


def test_unknown_provider_exception_is_sanitized(system, monkeypatch):
    _, _, extractor = providers(monkeypatch)
    def fail(*args):
        raise RuntimeError("secret-canary-and-private-card")
    extractor.extract = fail
    scan_id = send(system)
    response = system.client.get(f"/api/scans/{scan_id}")
    assert response.json()["status"] == "failed"
    assert "secret-canary" not in response.text


def test_default_mock_rejects_unknown_image_explicitly(system):
    scan_id = send(system)
    result = system.client.get(f"/api/scans/{scan_id}").json()
    assert result["status"] == "failed" and result["error_code"] == "FIXTURE_MISSING"


def test_missing_records_and_invalid_image_references(system):
    assert system.client.get("/api/scans/missing").status_code == 404
    assert system.client.post("/api/scans/missing/retry").status_code == 404
    for reference in ("file.txt", "g" * 64, "a" * 64):
        assert system.client.get(f"/api/images/{reference}").status_code == 404


@pytest.mark.parametrize("name,company", [("Jane Doe", "Example Inc."), ("山田 太郎", "株式会社サンプル")])
def test_complete_ui_to_api_flow_with_controlled_providers(system, monkeypatch, name, company):
    from pathlib import Path
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    from lib import api

    raw = f"{name}\n{company}\njane@example.com\nTel: 03-1234-5678"
    calls, _, _ = providers(monkeypatch, raw, name, company)
    # Real frontend API wrapper -> TestClient -> DB/worker -> review page.
    monkeypatch.setattr(api, "_client", lambda: system.client)
    monkeypatch.setattr(st, "camera_input", lambda *args, **kwargs: SimpleNamespace(
        name="card.png", type="image/png", getvalue=lambda: system.image))
    app_path = Path(__file__).resolve().parents[3] / "frontend/streamlit_app.py"
    at = AppTest.from_file(str(app_path), default_timeout=15).run()
    assert not at.exception
    at.button[0].click().run()
    assert not at.exception
    assert at.session_state["scan_result"]["status"] == "ocr_done"
    displayed = [item.value for item in at.text]
    assert name in displayed and company in displayed and "jane@example.com" in displayed
    assert "03-1234-5678" in displayed and "invented@fake.org" not in displayed
    at.run()
    assert calls == {"ocr": 1, "extract": 1}
