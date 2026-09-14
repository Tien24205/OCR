from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError

from app.models import Scan, Contact
from app.services.normalize import FIELDS
from test_pipeline_day4 import system, send, providers


def request_body(scan):
    return {"revision": scan["draft_revision"], "fields": {
        field: [{key: item.get(key, "") for key in ("id", "value", "label", "extension")}
                for item in scan["draft"]["fields"][field]] for field in FIELDS}}


def ready(system, monkeypatch):
    calls, _, _ = providers(monkeypatch)
    scan_id = send(system)
    return system.client.get(f"/api/scans/{scan_id}").json(), calls


def test_edit_add_remove_persist_japanese_and_preserve_ocr_evidence(system, monkeypatch):
    before, calls = ready(system, monkeypatch)
    scan_id = before["id"]
    with system.factory() as db:
        scan = db.get(Scan, scan_id)
        evidence = deepcopy((scan.raw_text, scan.extraction_json, scan.grounding_json["fields"], scan.grounding_json["report"]))
    body = request_body(before)
    body["fields"]["full_names"][0]["value"] = " 山田　太郎 "
    body["fields"]["full_names"].append({"value": "Taro Yamada"})
    body["fields"]["emails"] = []
    body["fields"]["addresses"] = [{"value": "〒100-0001\n東京都千代田区"}]
    response = system.client.patch(f"/api/scans/{scan_id}/draft", json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["draft_revision"] == 1 and result["draft_saved_at"]
    fields = result["draft"]["fields"]
    assert fields["full_names"][0]["value"] == "山田 太郎" and fields["full_names"][0]["source"] == "user"
    assert fields["full_names"][1]["source"] == "user" and fields["emails"] == []
    assert fields["company_names"][0]["source"] == "ocr"
    assert fields["addresses"][0]["value"] == "〒100-0001\n東京都千代田区"
    with system.factory() as db:  # Fresh session reads the committed DB.
        scan = db.get(Scan, scan_id)
        assert evidence == (scan.raw_text, scan.extraction_json, scan.grounding_json["fields"], scan.grounding_json["report"])
        assert scan.status == "ocr_done" and scan.contact_id is None
        assert db.scalar(select(func.count()).select_from(Contact)) == 0
    assert system.client.get(f"/api/scans/{scan_id}").json() == result
    assert calls == {"ocr": 1, "extract": 1}


def test_unchanged_values_keep_provenance_even_on_repeated_save(system, monkeypatch):
    before, _ = ready(system, monkeypatch)
    response = system.client.patch(f"/api/scans/{before['id']}/draft", json=request_body(before))
    assert response.json()["draft"] == before["draft"]
    again = response.json()
    response = system.client.patch(f"/api/scans/{before['id']}/draft", json=request_body(again))
    assert response.json()["draft"] == before["draft"]


def test_stale_revision_rejected_without_overwrite(system, monkeypatch):
    before, _ = ready(system, monkeypatch)
    path = f"/api/scans/{before['id']}/draft"
    body = request_body(before)
    assert system.client.patch(path, json=body).status_code == 200
    body["fields"]["full_names"][0]["value"] = "stale edit"
    assert system.client.patch(path, json=body).status_code == 409
    assert system.client.get(f"/api/scans/{before['id']}").json()["draft"]["fields"]["full_names"][0]["value"] == "Jane Doe"


@pytest.mark.parametrize("invalid", ["source", "unknown_id", "duplicate_id", "long_value", "missing_group"])
def test_draft_validates_untrusted_input(system, monkeypatch, invalid):
    before, _ = ready(system, monkeypatch)
    body = request_body(before)
    row = body["fields"]["full_names"][0]
    if invalid == "source":
        row["source"] = "ocr"
    elif invalid == "unknown_id":
        row["id"] = "someone-elses-row"
    elif invalid == "duplicate_id":
        body["fields"]["full_names"].append(dict(row))
    elif invalid == "long_value":
        row["value"] = "x" * 4097
    else:
        del body["fields"]["emails"]
    response = system.client.patch(f"/api/scans/{before['id']}/draft", json=body)
    assert response.status_code == 422
    assert system.client.get(f"/api/scans/{before['id']}").json()["draft_revision"] == 0


def test_draft_db_failure_is_reported_and_rolls_back(system, monkeypatch):
    before, _ = ready(system, monkeypatch)
    with patch("sqlalchemy.orm.Session.commit", side_effect=SQLAlchemyError("private-internal-error")):
        response = system.client.patch(f"/api/scans/{before['id']}/draft", json=request_body(before))
    assert response.status_code == 500 and "private-internal-error" not in response.text
    assert system.client.get(f"/api/scans/{before['id']}").json()["draft_revision"] == 0


def test_editing_phone_metadata_marks_user_but_keeps_other_rows(system, monkeypatch):
    before, _ = ready(system, monkeypatch)
    body = request_body(before)
    body["fields"]["phones"][0].update(label="fax", extension="９")
    response = system.client.patch(f"/api/scans/{before['id']}/draft", json=body).json()
    phone = response["draft"]["fields"]["phones"][0]
    assert phone["source"] == "user" and phone["label"] == "fax" and phone["extension"] == "9"


@pytest.mark.parametrize("status", ["pending", "processing", "failed", "committed"])
def test_only_completed_ocr_draft_is_editable(system, monkeypatch, status):
    before, _ = ready(system, monkeypatch)
    with system.factory() as db:
        db.get(Scan, before["id"]).status = status
        db.commit()
    assert system.client.patch(f"/api/scans/{before['id']}/draft", json=request_body(before)).status_code == 409


def test_actual_editor_submission_round_trips_through_backend(system, monkeypatch):
    from streamlit.testing.v1 import AppTest
    from lib import api

    before, calls = ready(system, monkeypatch)
    monkeypatch.setattr(api, "_client", lambda: system.client)
    app = Path(__file__).resolve().parents[3] / "frontend/streamlit_app.py"
    at = AppTest.from_file(str(app), default_timeout=15)
    at.session_state["current_scan_id"] = before["id"]
    at.session_state["scan_result"] = before
    at.switch_page("app_pages/review.py").run()
    assert not at.exception
    key = f"draft:{before['id']}:0:0:full_names"
    # AppTest has no cell-edit helper: supply the documented DataEditorState.
    at.session_state[key] = {"edited_rows": {0: {"value": "山田 太郎"}}, "added_rows": [], "deleted_rows": []}
    at.button[0].click().run()
    assert not at.exception
    assert at.session_state["scan_result"]["draft"]["fields"]["full_names"][0]["value"] == "山田 太郎"
    assert at.session_state["scan_result"]["draft"]["fields"]["full_names"][0]["source"] == "user"
    assert at.success
    at.switch_page("app_pages/capture.py").run()
    at.switch_page("app_pages/review.py").run()
    assert not at.exception
    assert any(item.value == "山田 太郎" for item in at.text)
    assert calls == {"ocr": 1, "extract": 1}
    # A second edit uses the saved baseline, not the previous editor delta.
    second_key = f"draft:{before['id']}:1:0:full_names"
    at.session_state[second_key] = {"edited_rows": {0: {"value": "山田 花子"}}, "added_rows": [], "deleted_rows": []}
    at.button[0].click().run()
    assert not at.exception
    assert at.session_state["scan_result"]["draft"]["fields"]["full_names"][0]["value"] == "山田 花子"


def test_failed_form_submit_preserves_edits_and_retries_only_on_click(system, monkeypatch):
    from streamlit.testing.v1 import AppTest
    from lib import api

    before, _ = ready(system, monkeypatch)
    monkeypatch.setattr(api, "_client", lambda: system.client)
    real_save = api.save_draft
    calls = []
    def flaky_save(*args):
        calls.append(deepcopy(args))
        if len(calls) == 1:
            raise api.ApiError("DRAFT_SAVE_FAILED", "Chưa lưu được bản nháp", True, 500)
        return real_save(*args)
    monkeypatch.setattr(api, "save_draft", flaky_save)
    app = Path(__file__).resolve().parents[3] / "frontend/streamlit_app.py"
    at = AppTest.from_file(str(app), default_timeout=15)
    at.session_state["current_scan_id"] = before["id"]
    at.session_state["scan_result"] = before
    at.switch_page("app_pages/review.py").run()
    assert not calls
    prefix = f"draft:{before['id']}:0:0:"
    at.session_state[prefix + "full_names"] = {"edited_rows": {0: {"value": "鈴木 一郎"}}, "added_rows": [], "deleted_rows": []}
    at.session_state[prefix + "emails"] = {"edited_rows": {}, "added_rows": [{"value": "New@EXAMPLE.COM"}], "deleted_rows": [0]}
    at.button[0].click().run()
    assert not at.exception and at.error
    assert at.session_state["scan_result"]["draft_revision"] == 0
    at.run()
    assert len(calls) == 1  # No automatic write on rerun.
    at.button[0].click().run()
    assert not at.exception and len(calls) == 2
    assert calls[0] == calls[1]
    saved = at.session_state["scan_result"]["draft"]["fields"]
    assert saved["full_names"][0]["value"] == "鈴木 一郎"
    assert [item["value"] for item in saved["emails"]] == ["New@example.com"]
