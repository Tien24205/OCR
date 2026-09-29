"""Contact saving and detail UI shared by review and directory pages."""
import json
from uuid import uuid4

import streamlit as st

from lib import api
from lib.fields import FIELD_LABELS, edit_fields, buffered_draft


def organization_picker(prefix, current=None):
    choices = {o["id"]: o for o in api.organization_choices()["items"]}
    options = [None, *choices]
    selected = st.selectbox("Doanh nghiệp liên kết", options,
        index=options.index(current) if current in options else 0,
        format_func=lambda oid: "Tạo từ danh thiếp / dùng doanh nghiệp của lượt tra cứu" if oid is None
        else f"{choices[oid]['name'] or '(chưa có tên)'} · {oid[:8]}", key=f"{prefix}:org")
    st.caption("Liên kết chỉ chọn doanh nghiệp; tên và website đã lưu của doanh nghiệp đó không bị ghi đè.")
    return {"mode": "link", "id": selected} if selected else {"mode": "new"}


def render_save_contact(scan):
    if scan["status"] == "committed":
        st.success("Bản quét đã được lưu thành hồ sơ.")
        if scan.get("contact_id") and st.button("Mở hồ sơ đã lưu"):
            st.session_state.selected_contact_id = scan["contact_id"]
            st.switch_page("app_pages/contacts.py")
        return
    if scan["status"] != "ocr_done" or not scan.get("draft"):
        return
    st.subheader("Lưu hồ sơ đối tác")
    st.caption("Hồ sơ dùng bản nháp đã lưu ở trên. Hãy lưu các chỉnh sửa và kiểm tra trên ảnh trước khi xác nhận.")
    prefix = f"commit:{scan['id']}:{scan.get('draft_revision', 0)}"
    try:
        organization = organization_picker(prefix)
        candidates = [x for x in api.scan_duplicates(scan["id"], organization.get("id"))["items"] if x["score"] >= 60]
    except api.ApiError as exc:
        st.error(exc.message)
        return
    target = None
    action = "check"
    if candidates:
        st.warning("Hồ sơ này có thể đã được lưu trước đó. Chọn một trong hai cách xử lý.",
                   icon=":material/content_copy:")
        by_id = {x["id"]: x for x in candidates}
        with st.container(horizontal=True, vertical_alignment="bottom"):
            target_id = st.selectbox("Hồ sơ có thể trùng", list(by_id),
                format_func=lambda cid: f"{by_id[cid]['name']} · {by_id[cid]['company']} · {by_id[cid]['score']} điểm", key=f"{prefix}:target")
            if st.button("Mở hồ sơ cũ", icon=":material/open_in_new:", key=f"{prefix}:view"):
                st.session_state.selected_contact_id = target_id
                st.switch_page("app_pages/contacts.py")
        target = by_id[target_id]
        st.caption("Lý do nghi trùng: " + "; ".join(target["reasons"]))
        # index=None: KHONG chon san. Gop nham vao ho so nguoi khac la loi kho
        # go nhat, nen nguoi dung phai tu chon truoc khi nut Luu hien ra.
        selected = st.radio(
            "Cách xử lý", ["merge", "new"], index=None, key=f"{prefix}:action",
            format_func={"merge": "Gộp hồ sơ", "new": "Lưu mới"}.get,
            captions=["Giữ nguyên hồ sơ cũ, chỉ bổ sung email, số điện thoại, địa chỉ… chưa có. "
                      "Không xoá thông tin nào; ghi chú được nối thêm.",
                      "Tạo một hồ sơ riêng, hồ sơ cũ giữ nguyên."])
        if selected is None:
            return
        action = selected
    note = st.text_area("Ghi chú hồ sơ", max_chars=10000, key=f"{prefix}:note")
    approved = st.checkbox("Tôi đã kiểm tra bản nháp và lựa chọn lưu hồ sơ", key=f"{prefix}:approved")
    if st.button("Xác nhận lưu hồ sơ", type="primary", disabled=not approved, key=f"{prefix}:save"):
        body = {"scan_id": scan["id"], "revision": scan.get("draft_revision", 0),
                "organization": organization, "duplicate_action": action, "note": note}
        if action == "merge":
            body.update(target_contact_id=target["id"], target_version=target["version"])
        signature = json.dumps(body, sort_keys=True, ensure_ascii=False)
        pending = st.session_state.get(f"{prefix}:pending")
        if not pending or pending["signature"] != signature:
            pending = {"signature": signature, "key": str(uuid4())}
            st.session_state[f"{prefix}:pending"] = pending
        try:
            result = api.save_contact(body, pending["key"])
        except api.ApiError as exc:
            st.error(exc.message)
            if exc.code in {"SCAN_COMMITTED", "DRAFT_CONFLICT"}:
                st.info("Bấm Tải lại bản nháp đã lưu để lấy trạng thái mới nhất.")
        else:
            st.session_state.scan_result = {**scan, "status": "committed", "contact_id": result["id"]}
            st.session_state.selected_contact_id = result["id"]
            st.rerun()


def _dong_hop_xoa() -> None:
    st.session_state.pop("dang_xoa_ho_so", None)


@st.dialog("Xoá hồ sơ", on_dismiss=_dong_hop_xoa)
def _xac_nhan_xoa(contact_id: str, ten: str) -> None:
    """Hoi lai truoc khi xoa: xoa la xoa HAN, khong co thung rac."""
    st.markdown(f"Xoá hồ sơ **{ten}**?")
    st.warning("Hồ sơ, các bản quét của nó và ảnh gốc sẽ bị xoá vĩnh viễn, "
               "không khôi phục được. Việc xoá được ghi vào nhật ký hoạt động.",
               icon=":material/warning:")
    dong_y = st.checkbox("Tôi hiểu và muốn xoá hẳn", key=f"xoa-ok:{contact_id}")
    with st.container(horizontal=True):
        if st.button("Xoá vĩnh viễn", type="primary", icon=":material/delete_forever:",
                     disabled=not dong_y, key=f"xoa-that:{contact_id}"):
            try:
                ket_qua = api.delete_contact(contact_id)
            except api.ApiError as exc:
                st.error(exc.message, icon=":material/error:")
                return
            _dong_hop_xoa()
            st.session_state.pop(f"contact_detail:{contact_id}", None)
            st.session_state.pop("selected_contact_id", None)
            st.session_state["contact_deleted_notice"] = (
                f"Đã xoá hồ sơ {ten} cùng {ket_qua.get('scans', 0)} bản quét.")
            st.rerun()
        if st.button("Huỷ", key=f"xoa-huy:{contact_id}"):
            _dong_hop_xoa()
            st.rerun()


def render_contact_detail(contact_id):
    cache_key = f"contact_detail:{contact_id}"
    with st.container(horizontal=True):
        if st.button("Tải lại hồ sơ", key=f"refresh:{contact_id}"):
            st.session_state.pop(cache_key, None)
        # Nho trang thai "dang mo hop xoa" trong phien: mot lan chay lai ca
        # trang (vd. bang tu lam moi) khong duoc dong hop giua chung.
        if st.button("Xoá hồ sơ", icon=":material/delete:", key=f"delete:{contact_id}"):
            st.session_state.dang_xoa_ho_so = contact_id
    try:
        if cache_key not in st.session_state:
            st.session_state[cache_key] = api.get_contact(contact_id)
        contact = st.session_state[cache_key]
    except api.ApiError as exc:
        st.error(exc.message)
        return
    if st.session_state.get("dang_xoa_ho_so") == contact_id:
        _xac_nhan_xoa(contact_id, contact["full_name_original"] or "chưa có tên")
    st.subheader(contact["full_name_original"] or "Hồ sơ chưa có tên")
    st.caption(f"Đã duyệt · {contact['reviewed_at']}")
    for field, label in FIELD_LABELS.items():
        items = contact["draft"]["fields"][field]
        if items:
            st.markdown(f"**{label}**")
            for item in items:
                st.text(item["value"] + (f" · Máy lẻ {item['extension']}" if item.get("extension") else ""))
                st.caption("Người dùng sửa" if item.get("source") == "user" else "Từ OCR")
    if contact.get("note"):
        st.text(contact["note"])
    st.markdown("**Thông tin bổ sung có nguồn**")
    accepted = [claim for job in contact["research"] if job.get("is_current_organization")
                for claim in job["enrichments"] if claim["decision"] == "accepted"]
    if not accepted:
        st.caption("Chưa có thông tin bổ sung được duyệt.")
    for claim in accepted:
        with st.container(border=True):
            st.text(f"{claim['attribute']}: {claim['value']}")
            st.text(claim["source_url"])
            st.caption(f"{claim['fetched_at']} · {claim['status']}")
            st.text(claim["evidence_snippet"])
    with st.expander("Các bản quét và kết quả tra cứu gốc"):
        for scan in contact["scans"]:
            if scan["is_mock"]:
                st.warning("Bản quét này dùng OCR giả lập.")
            st.text(scan["raw_text"] or "")
            if st.button("Mở bản quét", key=f"open-scan:{scan['id']}"):
                st.session_state.current_scan_id = scan["id"]
                st.session_state.pop("scan_result", None)
                st.session_state.pop("scan_poll", None)
                st.switch_page("app_pages/review.py")
        st.json(contact["research"])
    if st.toggle("Chỉnh sửa hồ sơ", key=f"edit-contact:{contact_id}"):
        prefix = f"profile:{contact_id}:{contact['version']}"
        buffer = st.session_state.get(f"{prefix}:buffer")
        try:
            organization = organization_picker(prefix, (contact.get("organization") or {}).get("id"))
        except api.ApiError as exc:
            st.error(exc.message)
            return
        if buffer:
            st.error(buffer["error"])
        draft = buffered_draft(contact["draft"], buffer["fields"]) if buffer else contact["draft"]
        with st.form(f"{prefix}:form", enter_to_submit=False):
            fields = edit_fields(draft, f"{prefix}:{st.session_state.get(prefix + ':nonce', 0)}")
            note = st.text_area("Ghi chú", value=buffer["note"] if buffer else contact.get("note") or "", max_chars=10000)
            submitted = st.form_submit_button("Lưu thay đổi hồ sơ")
        if submitted:
            try:
                updated = api.edit_contact(contact_id, {"version": contact["version"], "fields": fields,
                                             "organization": organization, "note": note})
            except api.ApiError as exc:
                st.session_state[f"{prefix}:buffer"] = {"fields": fields, "note": note, "error": exc.message}
                st.session_state[f"{prefix}:nonce"] = st.session_state.get(f"{prefix}:nonce", 0) + 1
                st.error(exc.message)
            else:
                st.session_state[cache_key] = updated
                st.session_state.pop(f"{prefix}:buffer", None)
                st.session_state["contact_saved_notice"] = True
                st.rerun()
