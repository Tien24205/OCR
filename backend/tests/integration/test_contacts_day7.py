"""Real API/SQLite transactions; synthetic OCR does not measure recognition quality."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import csv
import io
import json
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError

from app.models import Contact, ContactProfile, ContactEmail, ContactPhone, Address, Organization, Scan, IdempotencyKey
from app.services.dedupe import duplicate_candidates
from test_pipeline_day4 import system, send, providers
from test_draft_day5 import request_body
from test_enrichment_day6 import fake_sources, start


def ready(system, monkeypatch, name="山田 太郎"):
    providers(monkeypatch, f"{name}\n株式会社サンプル\njane@example.com\nTel: 03-1234-5678", name, "株式会社サンプル")
    sid = send(system)
    scan = system.client.get(f"/api/scans/{sid}").json()
    body = request_body(scan)
    body["fields"]["full_names"].append({"value": "Taro Yamada"})
    body["fields"]["company_names"].append({"value": "Sample Company"})
    body["fields"]["phones"].append({"value": "+81 90-1234-5678", "label": "mobile", "extension": "012"})
    body["fields"]["addresses"] = [{"value": "〒100-0001\n東京都千代田区"}]
    body["fields"]["websites"] = [{"value": "https://sample.example"}, {"value": "https://sample.example/en"}]
    return system.client.patch(f"/api/scans/{sid}/draft", json=body).json()


def save(system, scan, key=None, **kwargs):
    return system.client.post("/api/contacts", json={"scan_id": scan["id"], "revision": scan["draft_revision"], **kwargs},
                              headers={"Idempotency-Key": key or str(uuid4())})


def detail(system, contact_id):
    response = system.client.get(f"/api/contacts/{contact_id}")
    assert response.status_code == 200, response.text
    return response.json()


def edit_body(contact):
    return {"version": contact["version"], "fields": request_body({"draft_revision": 0, "draft": contact["draft"]})["fields"],
            "note": contact["note"] or "", "organization": {"mode": "link", "id": contact["organization"]["id"]}}


def test_atomic_save_unicode_multivalues_provenance_and_exports(system, monkeypatch):
    scan = ready(system, monkeypatch)
    with system.factory() as db:
        s = db.get(Scan, scan["id"])
        original = deepcopy((s.raw_text, s.extraction_json, s.grounding_json))
    response = save(system, scan, note="=HYPERLINK(\"https://example.com\")")
    assert response.status_code == 201, response.text
    cid = response.json()["id"]
    result = detail(system, cid)
    assert result["draft"] == scan["draft"]
    assert result["version"] == 1 and result["review_status"] == "reviewed"
    with system.factory() as db:
        s = db.get(Scan, scan["id"])
        assert (s.raw_text, s.extraction_json, s.grounding_json) == original
        assert s.status == "committed" and s.contact_id == cid
        assert db.scalar(select(func.count()).select_from(ContactEmail)) == 1
        assert db.scalar(select(func.count()).select_from(ContactPhone)) == 2
        assert db.scalar(select(func.count()).select_from(Address)) == 1
    for q in ["山田", "ＴＡＲＯ　ＹＡＭＡＤＡ", "サンプル", "Sample Company", "JANE@EXAMPLE.COM", "０３１２３４"]:
        found = system.client.get("/api/contacts", params={"q": q}).json()
        assert found["total"] == 1, (q, found)
    assert system.client.get("/api/contacts", params={"q": "%"}).json()["total"] == 0
    exported = system.client.get("/api/export?format=json").json()["contacts"][0]
    assert exported == result
    content = system.client.get("/api/export?format=csv").content
    assert content.startswith(b"\xef\xbb\xbf")
    row = next(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    assert json.loads(row["full_names"]) == ["山田 太郎", "Taro Yamada"]
    assert json.loads(row["phones"]) == ["03-1234-5678", "+81 90-1234-5678 ext. 012"]
    assert row["note"].startswith("'=HYPERLINK")


def test_idempotency_replay_mismatch_and_other_key(system, monkeypatch):
    scan = ready(system, monkeypatch)
    first = save(system, scan, "stable-key")
    assert first.status_code == 201, first.text
    assert save(system, scan, "stable-key").json() == first.json()
    assert save(system, scan, "stable-key", note="different").status_code == 409
    assert save(system, scan, "another-key").status_code == 409
    with system.factory() as db:
        assert db.scalar(select(func.count()).select_from(Contact)) == 1
        assert db.scalar(select(func.count()).select_from(IdempotencyKey)) == 1


def test_concurrent_same_key_returns_one_contact(system, monkeypatch):
    scan = ready(system, monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: save(system, scan, "concurrent"), range(2)))
    assert [r.status_code for r in responses] == [201, 201], [r.text for r in responses]
    assert responses[0].json() == responses[1].json()
    assert system.client.get("/api/contacts").json()["total"] == 1


@pytest.mark.parametrize("failure", ["commit", "child"])
def test_transaction_rolls_back_every_table_and_key(system, monkeypatch, failure):
    scan = ready(system, monkeypatch)
    if failure == "commit":
        mocked = patch("sqlalchemy.orm.Session.commit", side_effect=SQLAlchemyError("private failure"))
    else:
        from app import contact_routes
        original = contact_routes.project_contact
        def fail(*args):
            original(*args)
            args[0].flush()
            raise SQLAlchemyError("private failure")
        mocked = patch.object(contact_routes, "project_contact", fail)
    with mocked:
        response = save(system, scan, "rollback")
    assert response.status_code == 500 and "private failure" not in response.text
    with system.factory() as db:
        for model in (Contact, ContactProfile, Organization, ContactEmail, ContactPhone, Address, IdempotencyKey):
            assert db.scalar(select(func.count()).select_from(model)) == 0
        assert db.get(Scan, scan["id"]).status == "ocr_done"
    assert save(system, scan, "rollback").status_code == 201


def test_duplicate_requires_explicit_choice_and_update_retains_scans(system, monkeypatch):
    first = ready(system, monkeypatch)
    cid = save(system, first).json()["id"]
    second = ready(system, monkeypatch)
    candidates = system.client.get(f"/api/scans/{second['id']}/duplicates").json()["items"]
    assert candidates[0]["score"] == 100 and "Quét lại cùng ảnh" in candidates[0]["reasons"]
    assert save(system, second).json()["error"]["code"] == "DUPLICATE_REVIEW_REQUIRED"
    response = save(system, second, duplicate_action="update", target_contact_id=cid, target_version=1)
    assert response.status_code == 201, response.text
    result = detail(system, cid)
    assert result["version"] == 2 and len(result["scans"]) == 2
    assert system.client.get("/api/contacts").json()["total"] == 1
    third = ready(system, monkeypatch)
    assert save(system, third, duplicate_action="new").status_code == 201
    assert system.client.get("/api/contacts").json()["total"] == 2
    assert system.client.get(f"/api/contacts/{cid}/duplicates").json()["items"][0]["score"] == 100


def test_merge_keeps_old_values_and_only_adds_new_ones(system, monkeypatch):
    """Gop khac cap nhat: khong bao gio lam mat du lieu cu, khong nhan doi
    gia tri da co, va ho so gop xong van sua tiep duoc (ma dong khong lap)."""
    first = ready(system, monkeypatch)
    cid = save(system, first, note="gặp ở hội chợ").json()["id"]
    before = detail(system, cid)

    second = ready(system, monkeypatch)
    body = request_body(second)
    body["fields"]["emails"].append({"value": "Taro.New@Example.jp"})
    body["fields"]["phones"] = [{"value": "03 1234 5678"}]          # cung so, khac cach viet
    body["fields"]["addresses"] = []                                 # o trong KHONG xoa dia chi cu
    second = system.client.patch(f"/api/scans/{second['id']}/draft", json=body).json()

    response = save(system, second, duplicate_action="merge", target_contact_id=cid,
                    target_version=1, note="gọi lại tuần sau")
    assert response.status_code == 201, response.text
    assert response.json()["id"] == cid

    after = detail(system, cid)
    f, cu = after["draft"]["fields"], before["draft"]["fields"]
    assert after["version"] == 2 and len(after["scans"]) == 2
    assert [x["value"] for x in f["full_names"]] == [x["value"] for x in cu["full_names"]]
    assert [x["value"] for x in f["emails"]] == ["jane@example.com", "Taro.New@example.jp"]
    assert len(f["phones"]) == len(cu["phones"])
    assert f["addresses"] == cu["addresses"]
    assert after["note"] == "gặp ở hội chợ\n\ngọi lại tuần sau"
    ids = [x["id"] for field in f.values() for x in field]
    assert len(ids) == len(set(ids))
    assert system.client.patch(f"/api/contacts/{cid}", json=edit_body(after)).status_code == 200
    assert system.client.get("/api/contacts").json()["total"] == 1


def test_stale_edit_and_stale_duplicate_update_cannot_overwrite(system, monkeypatch):
    scan = ready(system, monkeypatch)
    cid = save(system, scan).json()["id"]
    before = detail(system, cid)
    body = edit_body(before)
    body["fields"]["emails"] = [{"value": "new@example.jp"}]
    response = system.client.patch(f"/api/contacts/{cid}", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["draft"]["fields"]["emails"][0]["source"] == "user"
    assert system.client.patch(f"/api/contacts/{cid}", json=body).status_code == 409
    second = ready(system, monkeypatch)
    assert save(system, second, duplicate_action="update", target_contact_id=cid, target_version=1).status_code == 409
    result = detail(system, cid)
    assert result["version"] == 2 and result["draft"]["fields"]["emails"][0]["value"] == "new@example.jp"
    assert system.client.get(f"/api/scans/{scan['id']}").json()["draft"] == scan["draft"]


def test_org_link_does_not_overwrite_shared_company(system, monkeypatch):
    scan = ready(system, monkeypatch)
    with system.factory() as db:
        org = Organization(name_original="会社 Original", name_norm="original", website="https://original.example")
        db.add(org)
        db.commit()
        oid = org.id
    cid = save(system, scan, organization={"mode": "link", "id": oid}).json()["id"]
    result = detail(system, cid)
    assert result["organization"]["id"] == oid and result["organization"]["name_original"] == "会社 Original"
    assert result["draft"]["fields"]["company_names"][0]["value"] == "株式会社サンプル"


def test_enrichment_reused_sources_and_review_decision_exported(system, monkeypatch):
    scan = ready(system, monkeypatch)
    fake_sources(monkeypatch)
    research = start(system, scan["id"], scan["draft_revision"])
    claim = research["enrichments"][0]
    system.client.patch(f"/api/enrichments/{claim['id']}", json={"decision": "accepted"})
    cid = save(system, scan).json()["id"]
    result = detail(system, cid)
    assert result["organization"]["id"] == research["organization_id"]
    assert any(x["decision"] == "accepted" for x in result["research"][0]["enrichments"])
    row = next(csv.DictReader(io.StringIO(system.client.get("/api/export?format=csv").content.decode("utf-8-sig"))))
    accepted = json.loads(row["accepted_enrichments"])
    assert len(accepted) == 1 and accepted[0]["evidence_snippet"] == claim["evidence_snippet"]


@pytest.mark.parametrize("case", ["key_missing", "stale_revision", "bad_org", "unknown_target", "empty", "provenance"])
def test_invalid_save_is_rejected_without_committing(system, monkeypatch, case):
    scan = ready(system, monkeypatch)
    if case == "key_missing":
        response = system.client.post("/api/contacts", json={"scan_id": scan["id"], "revision": scan["draft_revision"]})
    elif case == "stale_revision":
        response = save(system, {**scan, "draft_revision": 99})
    elif case == "bad_org":
        response = save(system, scan, organization={"mode": "link", "id": "missing"})
    elif case == "unknown_target":
        response = save(system, scan, duplicate_action="update", target_contact_id="missing", target_version=1)
    elif case == "provenance":
        response = save(system, scan, source="ocr")
    else:
        body = request_body(scan)
        body["fields"] = {key: [] for key in body["fields"]}
        scan = system.client.patch(f"/api/scans/{scan['id']}/draft", json=body).json()
        response = save(system, scan)
    assert response.status_code in {404, 409, 422}, response.text
    assert system.client.get("/api/contacts").json()["total"] == 0


@pytest.mark.parametrize("signal,expected", [("name", 25), ("email", 100), ("mobile", 80), ("domain", 60), ("organization", 70)])
def test_dedupe_strongest_signal_not_name_only_merge(system, monkeypatch, signal, expected):
    scan = ready(system, monkeypatch)
    cid = save(system, scan).json()["id"]
    draft = deepcopy(scan["draft"])
    for field in ("emails", "phones", "websites"):
        if {"email": "emails", "mobile": "phones", "domain": "websites"}.get(signal) != field:
            draft["fields"][field] = []
    with system.factory() as db:
        org_id = db.get(Contact, cid).organization_id if signal == "organization" else None
        result = duplicate_candidates(db, draft, organization_id=org_id)
    assert result[0]["score"] == expected
