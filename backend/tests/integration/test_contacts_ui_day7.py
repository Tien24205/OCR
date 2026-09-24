from copy import deepcopy
from pathlib import Path

from streamlit.testing.v1 import AppTest

from lib import api
from test_pipeline_day4 import system
from test_contacts_day7 import ready, save, detail, edit_body

APP = str(Path(__file__).resolve().parents[3] / "frontend/streamlit_app.py")


def button(at, label):
    return next(x for x in at.button if x.label == label)


def toggle(at, label):
    """Cong tac theo NHAN, khong theo chi so.

    LOI DA SUA: hai test duoi day tung dung `at.toggle[0]`, va no gay hong
    ngay khi trang Ho so them mot cong tac khac o phia tren ("Hien day du
    email va so dien thoai"). Khi do chung bat nham cong tac, nut "Luu thay
    doi ho so" khong bao gio xuat hien, va loi hien ra la `StopIteration` -
    mot cau khong noi gi ve nguyen nhan that.

    Tim theo nhan thi them bao nhieu widget o tren cung khong sao.
    """
    return next(x for x in at.toggle if x.label == label)


def test_save_ui_retries_same_request_after_lost_response(system, monkeypatch):
    scan = ready(system, monkeypatch)
    monkeypatch.setattr(api, "_client", lambda: system.client)
    original = api.save_contact
    calls = []
    def lost_response(body, key):
        calls.append((deepcopy(body), key))
        result = original(body, key)
        if len(calls) == 1:
            raise api.ApiError("BACKEND_UNREACHABLE", "Mất phản hồi sau khi lưu", True, 0)
        return result
    monkeypatch.setattr(api, "save_contact", lost_response)
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state.current_scan_id = scan["id"]
    at.session_state.scan_result = scan
    at.switch_page("app_pages/review.py").run()
    assert not at.exception
    assert button(at, "Xác nhận lưu hồ sơ").disabled
    at.checkbox[0].check().run()
    button(at, "Xác nhận lưu hồ sơ").click().run()
    assert not at.exception and any("Mất phản hồi" in x.value for x in at.error)
    at.run()
    assert len(calls) == 1
    button(at, "Xác nhận lưu hồ sơ").click().run()
    assert not at.exception and calls[0] == calls[1]
    assert at.session_state.scan_result["status"] == "committed"
    assert system.client.get("/api/contacts").json()["total"] == 1


def test_duplicate_ui_requires_choice_before_creating_new(system, monkeypatch):
    first = ready(system, monkeypatch)
    save(system, first)
    second = ready(system, monkeypatch)
    monkeypatch.setattr(api, "_client", lambda: system.client)
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state.current_scan_id = second["id"]
    at.session_state.scan_result = second
    at.switch_page("app_pages/review.py").run()
    assert not at.exception
    assert at.radio[0].options == ["Xem hồ sơ cũ", "Cập nhật hồ sơ này", "Tạo hồ sơ mới"]
    assert not any(x.label == "Xác nhận lưu hồ sơ" for x in at.button)
    at.radio[0].set_value("Tạo hồ sơ mới").run()
    at.checkbox[0].check().run()
    button(at, "Xác nhận lưu hồ sơ").click().run()
    assert not at.exception and system.client.get("/api/contacts").json()["total"] == 2


def test_directory_search_export_and_edit_preserve_japanese(system, monkeypatch):
    scan = ready(system, monkeypatch)
    cid = save(system, scan).json()["id"]
    monkeypatch.setattr(api, "_client", lambda: system.client)
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state.selected_contact_id = cid
    at.switch_page("app_pages/contacts.py").run()
    assert not at.exception
    at.text_input[0].set_value("山田").run()
    assert len(at.dataframe[0].value) == 1
    button(at, "Chuẩn bị file xuất").click().run()
    assert at.session_state.contact_exports["csv"].startswith(b"\xef\xbb\xbf")
    toggle(at, "Chỉnh sửa hồ sơ").set_value(True).run()
    prefix = f"profile:{cid}:1:0:full_names"
    at.session_state[prefix] = {"edited_rows": {0: {"value": "山田 花子"}}, "added_rows": [], "deleted_rows": []}
    button(at, "Lưu thay đổi hồ sơ").click().run()
    assert not at.exception
    assert detail(system, cid)["full_name_original"] == "山田 花子"
    assert detail(system, cid)["draft"]["fields"]["full_names"][1]["value"] == "Taro Yamada"


def test_profile_ui_does_not_overwrite_a_newer_version(system, monkeypatch):
    scan = ready(system, monkeypatch)
    cid = save(system, scan).json()["id"]
    monkeypatch.setattr(api, "_client", lambda: system.client)
    at = AppTest.from_file(APP, default_timeout=15)
    at.session_state.selected_contact_id = cid
    at.switch_page("app_pages/contacts.py").run()
    toggle(at, "Chỉnh sửa hồ sơ").set_value(True).run()
    other = edit_body(detail(system, cid))
    other["fields"]["full_names"][0]["value"] = "新しい名前"
    assert system.client.patch(f"/api/contacts/{cid}", json=other).status_code == 200
    at.session_state[f"profile:{cid}:1:0:full_names"] = {
        "edited_rows": {0: {"value": "stale name"}}, "added_rows": [], "deleted_rows": []}
    button(at, "Lưu thay đổi hồ sơ").click().run()
    assert not at.exception and any("đã thay đổi" in x.value for x in at.error)
    assert detail(system, cid)["full_name_original"] == "新しい名前"
    assert at.session_state[f"profile:{cid}:1:buffer"]["fields"]["full_names"][0]["value"] == "stale name"
