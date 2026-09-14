from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select, func

from app.models import Scan, Organization, Contact, EnrichmentJob
from app.services.enrich import worker
from app.services.enrich.fetcher import Page, FetchError
from app.services.enrich.summarize import Claim, SummaryError
from test_pipeline_day4 import system, send, providers


def ready(system, monkeypatch, *, website=True):
    calls, _, _ = providers(monkeypatch)
    scan_id = send(system)
    with system.factory() as db:
        scan = db.get(Scan, scan_id)
        grounding = deepcopy(scan.grounding_json)
        grounding["fields"]["websites"] = [{"value": "https://company.example"}] if website else []
        grounding["fields"]["emails"] = []
        scan.grounding_json = grounding
        db.commit()
    return scan_id, calls


def fake_sources(monkeypatch, *, failure=None, summary_failure=None):
    fetched, summaries = [], []
    text = "Example Inc.\nIndustry: manufacturing.\nProducts: industrial sensors.\nCompany size: 120 employees (2024)."
    def fetch(url):
        fetched.append(url)
        if failure:
            raise FetchError(failure)
        return Page(url, "Example official company profile", text, [], "2026-09-11T00:00:00+00:00")
    def extract(pages):
        summaries.append(pages)
        if summary_failure:
            raise SummaryError(summary_failure)
        return [Claim(attribute=attribute, value=value, evidence_snippet=snippet, source_url=pages[0].url)
                for attribute, value, snippet in [
                    ("industry", "manufacturing", "Industry: manufacturing."),
                    ("products_services", "industrial sensors", "Products: industrial sensors."),
                    ("company_size", "120 employees (2024)", "Company size: 120 employees (2024).")]]
    monkeypatch.setattr(worker, "SafeFetcher", lambda config: SimpleNamespace(fetch=fetch))
    monkeypatch.setattr(worker, "GeminiSummarizer", lambda config: SimpleNamespace(extract=extract, close=lambda: None))
    return fetched, summaries


def start(system, scan_id, revision=0):
    response = system.client.post(f"/api/scans/{scan_id}/enrich", json={"revision": revision})
    assert response.status_code == 202, response.text
    return system.client.get(f"/api/organizations/{response.json()['organization_id']}").json()["research"]


def evidence(system, scan_id):
    with system.factory() as db:
        scan = db.get(Scan, scan_id)
        return deepcopy((scan.status, scan.raw_text, scan.extraction_json, scan.grounding_json))


def test_enrichment_success_sources_and_decisions_do_not_change_scan(system, monkeypatch):
    scan_id, ocr_calls = ready(system, monkeypatch)
    fetched, summaries = fake_sources(monkeypatch)
    before = evidence(system, scan_id)
    job = start(system, scan_id)
    assert job["status"] == "done" and not job["reason"]
    assert len(fetched) == 5 and len(summaries) == 1
    assert len(job["enrichments"]) == 3
    for row in job["enrichments"]:
        assert row["status"] == "verified" and row["value"] in row["evidence_snippet"]
        assert row["source_url"] == "https://company.example/" and row["fetched_at"]
    row_id = job["enrichments"][0]["id"]
    accepted = system.client.patch(f"/api/enrichments/{row_id}", json={"decision": "accepted"}).json()
    assert next(row for row in accepted["enrichments"] if row["id"] == row_id)["decision"] == "accepted"
    rejected = system.client.patch(f"/api/enrichments/{row_id}", json={"decision": "rejected"}).json()
    assert next(row for row in rejected["enrichments"] if row["id"] == row_id)["decision"] == "rejected"
    assert evidence(system, scan_id) == before and ocr_calls == {"ocr": 1, "extract": 1}
    with system.factory() as db:
        assert db.scalar(select(func.count()).select_from(Contact)) == 0
        stored = db.get(EnrichmentJob, job["id"])
        assert len(stored.metadata_json["sources"]) == 5


def test_no_domain_and_no_external_calls_preserves_ocr(system, monkeypatch):
    scan_id, _ = ready(system, monkeypatch, website=False)
    fetched, summaries = fake_sources(monkeypatch)
    before = evidence(system, scan_id)
    job = start(system, scan_id)
    assert job["reason"] == "NO_DOMAIN_ON_CARD" and job["status"] == "done"
    assert all(row["status"] == "not_found" and row["value"] is None for row in job["enrichments"])
    assert fetched == summaries == [] and evidence(system, scan_id) == before
    assert system.client.patch(f"/api/enrichments/{job['enrichments'][0]['id']}", json={"decision": "accepted"}).status_code == 409


@pytest.mark.parametrize("failure", ["FETCH_FAILED", "ROBOTS_DISALLOWED", "BLOCKED_ADDRESS", "DNS_FAILED"])
def test_fetch_failure_never_fails_the_scan(system, monkeypatch, failure):
    scan_id, _ = ready(system, monkeypatch)
    fetched, summaries = fake_sources(monkeypatch, failure=failure)
    before = evidence(system, scan_id)
    job = start(system, scan_id)
    assert job["reason"] == failure and all(row["value"] is None for row in job["enrichments"])
    assert summaries == [] and evidence(system, scan_id) == before


def test_missing_summarizer_keeps_download_evidence_and_not_found(system, monkeypatch):
    scan_id, _ = ready(system, monkeypatch)
    fake_sources(monkeypatch, summary_failure="SUMMARIZER_NOT_CONFIGURED")
    job = start(system, scan_id)
    assert job["reason"] == "SUMMARIZER_NOT_CONFIGURED"
    assert len(job["pages"]) == 5 and all(row["status"] == "not_found" for row in job["enrichments"])


def test_repeated_start_is_cached_retry_is_bounded(system, monkeypatch):
    scan_id, _ = ready(system, monkeypatch)
    fetched, _ = fake_sources(monkeypatch)
    first = start(system, scan_id)
    second = start(system, scan_id)
    assert first == second and len(fetched) == 5
    worker.run_enrichment(first["id"], system.config, system.factory)
    assert len(fetched) == 5
    url = f"/api/organizations/{first['organization_id']}/enrich"
    assert system.client.post(url).status_code == 202
    assert system.client.post(url).status_code == 202
    assert system.client.post(url).status_code == 409
    assert len(fetched) == 15
    assert system.client.patch(f"/api/enrichments/{first['enrichments'][0]['id']}", json={"decision": "accepted"}).status_code == 409


def test_snapshot_tracks_draft_revision_without_overwriting_old_research(system, monkeypatch):
    scan_id, _ = ready(system, monkeypatch)
    fake_sources(monkeypatch)
    first = start(system, scan_id)
    with system.factory() as db:
        scan = db.get(Scan, scan_id)
        scan.grounding_json = {**scan.grounding_json, "draft_revision": 1}
        db.commit()
    assert system.client.post(f"/api/scans/{scan_id}/enrich", json={"revision": 0}).status_code == 409
    assert system.client.get(f"/api/scans/{scan_id}").json()["enrichment"] is None
    second = start(system, scan_id, 1)
    assert second["id"] != first["id"] and second["draft_revision"] == 1


def test_conflicting_claims_require_one_selected_value(system, monkeypatch):
    scan_id, _ = ready(system, monkeypatch)
    fake_sources(monkeypatch)
    job = start(system, scan_id)
    from app.models import Enrichment
    with system.factory() as db:
        first = db.get(Enrichment, job["enrichments"][0]["id"])
        first.status = "conflicting"
        alternative = Enrichment(organization_id=first.organization_id, attribute=first.attribute,
                                value="alternative", status="conflicting", source_url="https://company.example/about",
                                evidence_snippet="An alternative source statement.")
        db.add(alternative)
        db.flush()
        stored = db.get(EnrichmentJob, job["id"])
        stored.result_ids = stored.result_ids + [alternative.id]
        first_id, second_id = first.id, alternative.id
        db.commit()
    system.client.patch(f"/api/enrichments/{first_id}", json={"decision": "accepted"})
    result = system.client.patch(f"/api/enrichments/{second_id}", json={"decision": "accepted"}).json()
    decisions = {row["id"]: row["decision"] for row in result["enrichments"]}
    assert decisions[first_id] == "rejected" and decisions[second_id] == "accepted"


def test_ui_research_and_review_through_real_api(system, monkeypatch):
    from streamlit.testing.v1 import AppTest
    from lib import api
    scan_id, _ = ready(system, monkeypatch)
    fake_sources(monkeypatch)
    monkeypatch.setattr(api, "_client", lambda: system.client)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[3] / "frontend/streamlit_app.py"), default_timeout=20)
    at.session_state["current_scan_id"] = scan_id
    at.session_state["scan_result"] = system.client.get(f"/api/scans/{scan_id}").json()
    at.switch_page("app_pages/review.py").run()
    next(button for button in at.button if button.label == "Tra cứu doanh nghiệp").click().run()
    assert not at.exception
    assert any(text.value == "manufacturing" for text in at.text)
    assert any(text.value == "industrial sensors" for text in at.text)
    assert any(text.value == "https://company.example/" for text in at.text)
    next(button for button in at.button if button.label == "Duyệt").click().run()
    assert not at.exception and any(caption.value == "Đã duyệt" for caption in at.caption)
    next(button for button in at.button if button.label == "Bác bỏ").click().run()
    assert not at.exception and any(caption.value == "Đã bác bỏ" for caption in at.caption)
