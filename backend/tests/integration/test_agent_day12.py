from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app import pipeline
from app.models import Scan
from app.services.agent_orchestrator import AgenticOrchestrator
from app.services.image_quality import ImageQualityAgent
from app.services.ocr.base import OcrResult, OcrBlock, OcrError
from app.services.extract.base import CardExtraction, ExtractedValue, ExtractionError
from test_pipeline_day4 import system, send, providers


def enable(system, monkeypatch):
    system.config.agent_enabled = True
    monkeypatch.setattr(ImageQualityAgent, "assess", lambda self, image: {
        "action": "accept", "issues": [], "metrics": {}, "orientation": "unknown"})


def scan_result(system, sid):
    response = system.client.get(f"/api/scans/{sid}")
    assert response.status_code == 200, response.text
    return response.json()


def test_severe_image_stops_before_providers_and_cannot_retry_same_image(system, monkeypatch):
    system.config.agent_enabled = True
    calls, _, _ = providers(monkeypatch)
    sid = send(system)  # White image, actual quality assessment.
    result = scan_result(system, sid)
    assert result["status"] == "failed" and result["error_code"] == "IMAGE_RECAPTURE_REQUIRED"
    assert not result["can_retry"] and calls == {"ocr": 0, "extract": 0}
    assert system.client.post(f"/api/scans/{sid}/retry").status_code == 409


def test_warning_continues_and_records_all_stages(system, monkeypatch):
    enable(system, monkeypatch)
    monkeypatch.setattr(ImageQualityAgent, "assess", lambda self, image: {
        "action": "warn", "issues": ["check_orientation"], "metrics": {}, "orientation": "portrait_check"})
    providers(monkeypatch)
    result = scan_result(system, send(system))
    assert result["status"] == "ocr_done"
    agents = {x["agent"] for x in result["grounding"]["agent_decisions"]}
    assert {"image_quality_agent", "ocr_agent", "grounding_agent", "normalize_agent", "enrichment_agent"} <= agents


def test_missing_names_retries_prompt_preserves_first_extraction_and_saves_selected(system, monkeypatch):
    enable(system, monkeypatch)
    calls, _, extractor = providers(monkeypatch)
    original_extract = extractor.extract
    extractor.extract = lambda *args: CardExtraction()
    attempts = []
    def alternate(*args):
        attempts.append(1)
        return original_extract(*args)
    extractor.extract_retry = alternate
    sid = send(system)
    result = scan_result(system, sid)
    assert result["status"] == "ocr_done" and len(attempts) == 1
    assert result["draft"]["fields"]["full_names"][0]["value"] == "Jane Doe"
    with system.factory() as db:
        scan = db.get(Scan, sid)
        assert scan.extraction_json["full_names"] == []
        assert len(scan.ocr_payload["agent_work"]["extraction_attempts"]) == 2
        assert scan.ocr_payload["agent_work"]["selected_extraction"] == 1
    saved = system.client.post("/api/contacts", json={"scan_id": sid, "revision": 0}, headers={"Idempotency-Key": "agent-save"})
    assert saved.status_code == 201, saved.text
    contact = system.client.get(f"/api/contacts/{saved.json()['id']}").json()
    assert contact["draft"] == result["draft"]


def test_hallucinated_alternative_is_not_selected(system, monkeypatch):
    enable(system, monkeypatch)
    _, _, extractor = providers(monkeypatch)
    extractor.extract = lambda *args: CardExtraction(emails=[ExtractedValue(value="jane@example.com")])
    extractor.extract_retry = lambda *args: CardExtraction(full_names=[ExtractedValue(value="Invented Person")])
    sid = send(system)
    result = scan_result(system, sid)
    assert result["draft"]["fields"]["full_names"] == []
    assert result["draft"]["fields"]["emails"][0]["value"] == "jane@example.com"
    assert result["grounding"]["agent_warnings"]
    with system.factory() as db:
        assert db.get(Scan, sid).ocr_payload["agent_work"]["selected_extraction"] == 0


def test_low_confidence_changes_image_and_keeps_first_ocr(system, monkeypatch):
    enable(system, monkeypatch)
    _, ocr, _ = providers(monkeypatch)
    inputs = []
    def recognize(image, mime):
        inputs.append((image, mime))
        text = "Jane" if len(inputs) == 1 else "Jane Doe\nExample Inc.\njane@example.com"
        return OcrResult(text, "mock:synthetic", "test", blocks=[OcrBlock(text, (0,0,30,20), 0.3 if len(inputs)==1 else 0.95)])
    ocr.recognize = recognize
    # A non-uniform, low-contrast image gives a genuinely different contrast variant.
    from PIL import Image
    from io import BytesIO
    image = Image.new("RGB", (80,40), (100,100,100))
    for x in range(10,70):
        image.putpixel((x,20), (130,130,130))
    output = BytesIO()
    image.save(output, format="PNG")
    system.image = output.getvalue()
    sid = send(system)
    result = scan_result(system, sid)
    assert len(inputs) == 2 and inputs[0][0] != inputs[1][0]
    assert result["raw_text"] == "Jane"
    assert result["ocr_text_for_draft"].startswith("Jane Doe")
    assert result["draft"]["fields"]["full_names"][0]["value"] == "Jane Doe"


def test_global_two_retry_budget_cannot_multiply_across_stages(system, monkeypatch):
    enable(system, monkeypatch)
    _, ocr, extractor = providers(monkeypatch)
    original = ocr.recognize
    calls = []
    def flaky(*args):
        calls.append(1)
        if len(calls) < 3:
            raise OcrError("OCR_TIMEOUT", "synthetic", retryable=True)
        return original(*args)
    ocr.recognize = flaky
    extractor.extract = lambda *args: CardExtraction()
    alternatives = []
    extractor.extract_retry = lambda *args: alternatives.append(1) or CardExtraction()
    sid = send(system)
    result = scan_result(system, sid)
    assert result["status"] == "ocr_done" and len(calls) == 3 and not alternatives
    assert len([x for x in result["grounding"]["agent_decisions"] if x["action"] == "retry"]) == 2


def test_nonretryable_error_is_not_repeated_or_exposed(system, monkeypatch):
    enable(system, monkeypatch)
    _, ocr, _ = providers(monkeypatch)
    calls = []
    def fail(*args):
        calls.append(1)
        raise OcrError("OCR_NOT_CONFIGURED", "secret-canary")
    ocr.recognize = fail
    sid = send(system)
    result = scan_result(system, sid)
    assert result["status"] == "failed" and len(calls) == 1
    assert "secret-canary" not in str(result)


def test_resume_reuses_ocr_checkpoint_and_duplicate_run_is_noop(system, monkeypatch):
    enable(system, monkeypatch)
    calls, _, extractor = providers(monkeypatch)
    original = extractor.extract
    extractor.extract = lambda *args: (_ for _ in ()).throw(ExtractionError("BAD", "synthetic"))
    sid = send(system)
    assert scan_result(system, sid)["status"] == "failed"
    extractor.extract = original
    assert system.client.post(f"/api/scans/{sid}/retry").status_code == 202
    result = scan_result(system, sid)
    assert result["status"] == "ocr_done" and calls["ocr"] == 1
    pipeline.run_scan(sid, system.config, system.factory)
    assert calls == {"ocr": 1, "extract": 1}


def test_alternate_failure_keeps_grounded_result(system, monkeypatch):
    enable(system, monkeypatch)
    _, _, extractor = providers(monkeypatch)
    extractor.extract = lambda *args: CardExtraction(emails=[ExtractedValue(value="jane@example.com")])
    extractor.extract_retry = lambda *args: (_ for _ in ()).throw(RuntimeError("secret-canary"))
    result = scan_result(system, send(system))
    assert result["status"] == "ocr_done"
    assert result["draft"]["fields"]["emails"] and "secret-canary" not in str(result)


def test_auto_enrichment_failure_does_not_fail_ocr(system, monkeypatch):
    from app.services.enrich import worker
    from app.models import EnrichmentJob
    from sqlalchemy import select
    enable(system, monkeypatch)
    system.config.agent_auto_enrich = True
    providers(monkeypatch)
    def fail(*args):
        raise RuntimeError("synthetic network error")
    monkeypatch.setattr(worker, "run_enrichment", fail)
    sid = send(system)
    assert scan_result(system, sid)["status"] == "ocr_done"
    with system.factory() as db:
        job = db.scalar(select(EnrichmentJob).where(EnrichmentJob.scan_id == sid))
        assert job.status == "done" and job.reason == "ENRICH_FAILED"


def test_manual_query_uses_company_only_when_no_domain(system, monkeypatch):
    from app.services.enrich import worker
    from app.models import Organization, EnrichmentJob
    enable(system, monkeypatch)
    providers(monkeypatch)
    sid = send(system)
    draft = scan_result(system, sid)["draft"]
    draft["fields"]["emails"] = []
    with system.factory() as db:
        org = Organization(name_original="Example Inc.", name_norm="exampleinc.")
        db.add(org); db.flush()
        job = EnrichmentJob(scan_id=sid, organization_id=org.id, draft_revision=0, snapshot=draft)
        db.add(job); db.commit(); job_id = job.id
    worker.run_enrichment(job_id, system.config, system.factory)
    with system.factory() as db:
        job = db.get(EnrichmentJob, job_id)
        assert job.reason == "NO_DOMAIN_ON_CARD"
        assert job.metadata_json["manual_search_query"] == "Example Inc. official website"


def test_quality_laplacian_and_orientation_hints():
    from PIL import Image, ImageDraw
    from io import BytesIO
    def assess(image):
        out = BytesIO(); image.save(out, format="PNG")
        return ImageQualityAgent().assess(out.getvalue())
    blank = Image.new("RGB", (200,100), "white")
    assert assess(blank)["action"] == "recapture"
    ImageDraw.Draw(blank).rectangle((30,20,160,80), fill="black")
    assert assess(blank)["metrics"]["laplacian_variance"] > 2
    portrait = assess(blank.transpose(Image.Transpose.ROTATE_90))
    assert portrait["orientation"] == "portrait_check" and "check_orientation" in portrait["issues"]


def test_recapture_ui_offers_new_image_without_retry(system, monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    from lib import api
    system.config.agent_enabled = True
    providers(monkeypatch)
    sid = send(system)
    monkeypatch.setattr(api, "_client", lambda: system.client)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[3] / "frontend/streamlit_app.py"), default_timeout=15)
    at.session_state.current_scan_id = sid
    at.session_state.scan_result = scan_result(system, sid)
    at.switch_page("app_pages/review.py").run()
    assert not at.exception
    assert any(x.label == "Chụp hoặc tải ảnh mới" for x in at.button)
    assert not any(x.label == "Thử xử lý lại" for x in at.button)


def test_gemini_alternative_uses_different_instruction_without_relaxing_grounding():
    from app.services.extract.gemini import GeminiExtractor, SYSTEM_INSTRUCTION
    calls = []
    def generate(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text=CardExtraction().model_dump_json())
    extractor = object.__new__(GeminiExtractor)
    extractor._client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    extractor._model, extractor._temperature = "test", 0.0
    extractor.extract(b"image", "image/png", "OCR text")
    extractor.extract_retry(b"image", "image/png", "OCR text")
    assert calls[0]["config"].system_instruction == SYSTEM_INSTRUCTION
    assert calls[1]["config"].system_instruction.startswith(SYSTEM_INSTRUCTION)
    assert "SECOND PASS" in calls[1]["config"].system_instruction
    assert calls[1]["config"].response_schema == CardExtraction


def test_grounding_feedback_can_trigger_retry_without_missing_critical_fields(system, monkeypatch):
    enable(system, monkeypatch)
    _, _, extractor = providers(monkeypatch)
    good = CardExtraction(full_names=[ExtractedValue(value="Jane Doe")],
                          company_names=[ExtractedValue(value="Example Inc.")])
    bad = good.model_copy(deep=True)
    bad.emails = [ExtractedValue(value=f"invented{i}@elsewhere.org") for i in range(4)]
    extractor.extract = lambda *args: bad
    calls = []
    extractor.extract_retry = lambda *args: calls.append(1) or good
    sid = send(system)
    result = scan_result(system, sid)
    assert calls == [1] and result["grounding"]["counts"]["unverified"] == 0
    with system.factory() as db:
        assert len(db.get(Scan, sid).extraction_json["emails"]) == 4
