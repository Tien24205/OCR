"""Bounded OCR polling, normalization and review of a separately saved draft."""
import time

import streamlit as st

from lib import api
from lib.fields import buffered_draft, edit_fields, FIELD_LABELS
from lib.enrichment import render_enrichment
from lib.contacts import render_save_contact

MOI_TRANG = 12

TRANG_THAI_VI = {"pending": "đang chờ", "processing": "đang nhận diện",
                 "ocr_done": "chờ kiểm tra", "committed": "đã lưu hồ sơ",
                 "failed": "lỗi"}


@st.cache_data(show_spinner=False, max_entries=64)
def _anh(scan_id: str) -> bytes:
    """Anh nho de chon ban quet.

    Cache duoc: anh cua mot ban quet khong bao gio doi. Khong cache thi moi
    lan chay lai script la mot loat loi goi tai anh - dung cai da tung dung
    gioi han tan suat o trang Quet the.
    """
    return api.get_image(scan_id)


def chon_ban_quet(dang_mo: str | None) -> None:
    """Luoi anh thu nho de mo lai mot ban quet cu.

    VI SAO CAN: truoc day trang nay chi mo duoc ban quet vua gui, vi
    `current_scan_id` song trong phien trinh duyet. Tai lai trang la mat duong
    vao, va nhung ban quet da xu ly xong nam lai trong CSDL khong co cach nao
    mo ra - da tung co 9 ban quet `ocr_done` bi ket kieu do.
    """
    trang = st.session_state.get("scan_trang", 1)
    tim_so = st.session_state.get("scan_tim_so")
    try:
        ket_qua = api.list_scans(limit=MOI_TRANG, page=trang, so=tim_so)
    except api.ApiError as exc:
        st.caption(f"Chưa đọc được danh sách bản quét: {exc.message}")
        return
    items, tong = ket_qua["items"], ket_qua.get("total", len(ket_qua["items"]))
    if not items and not tim_so and trang == 1:
        return
    so_trang = max(1, -(-tong // MOI_TRANG))

    with st.expander(f"Chọn bản quét khác ({tong} bản quét)",
                     expanded=dang_mo is None):
        with st.container(horizontal=True, vertical_alignment="bottom"):
            st.number_input("Tìm theo số thứ tự", min_value=1, step=1, value=None,
                            key="scan_tim_so", placeholder="vd. 42",
                            on_change=lambda: st.session_state.update(scan_trang=1))
            if tim_so:
                st.button("Bỏ tìm", icon=":material/close:", key="scan_bo_tim",
                          on_click=lambda: st.session_state.update(scan_tim_so=None))
        if not items:
            st.caption(f"Không có bản quét #{tim_so}." if tim_so else "Trang này trống.")
        for hang in range(0, len(items), 4):
            for cot, item in zip(st.columns(4), items[hang:hang + 4]):
                with cot:
                    try:
                        st.image(_anh(item["id"]), width="stretch")
                    except Exception:
                        st.caption("(chưa tải được ảnh)")
                    nhan = (item.get("full_name") or item.get("company_name")
                            or TRANG_THAI_VI.get(item["status"], item["status"]))
                    so = f"**#{item['seq']}** · " if item.get("seq") else ""
                    ngay = item["created_at"]
                    st.caption(f"{so}{nhan}\n\n{ngay[8:10]}/{ngay[5:7]} {ngay[11:16]} · "
                               f"{TRANG_THAI_VI.get(item['status'], item['status'])}")
                    if item["id"] == dang_mo:
                        st.caption("**đang mở**")
                    elif st.button("Mở", key=f"mo:{item['id']}", width="stretch"):
                        st.session_state.current_scan_id = item["id"]
                        st.session_state.pop("scan_result", None)
                        st.session_state.pop("scan_poll", None)
                        st.rerun()
        if so_trang > 1 and not tim_so:
            with st.container(horizontal=True, vertical_alignment="center"):
                if st.button("Mới hơn", icon=":material/chevron_left:", disabled=trang <= 1,
                             key="scan_moi_hon"):
                    st.session_state.scan_trang = trang - 1
                    st.rerun()
                st.caption(f"Trang {trang}/{so_trang}")
                if st.button("Cũ hơn", icon=":material/chevron_right:", disabled=trang >= so_trang,
                             key="scan_cu_hon"):
                    st.session_state.scan_trang = trang + 1
                    st.rerun()


scan_id = st.session_state.get("current_scan_id")
if not scan_id:
    st.info("Chưa có bản quét nào. Sang trang **Quét thẻ** để chụp hoặc tải ảnh, "
            "hoặc chọn một bản quét cũ bên dưới.")
    chon_ban_quet(None)
    st.stop()

_dang_mo = st.session_state.get("scan_result") or {}
_so_mo = _dang_mo.get("seq") if _dang_mo.get("id") == scan_id else None
st.caption(f"Bản quét **#{_so_mo}**" if _so_mo else f"Bản quét `{scan_id}`")
chon_ban_quet(scan_id)
poll = st.session_state.get("scan_poll")
if not poll or poll["id"] != scan_id:
    st.session_state.scan_poll = {"id": scan_id, "started": time.monotonic(), "error": None}


def restart_poll() -> None:
    st.session_state.pop("scan_result", None)
    st.session_state.pop("scan_poll", None)
    st.rerun()


@st.fragment(run_every="1s")
def wait_for_ocr() -> None:
    poll = st.session_state.scan_poll
    if time.monotonic() - poll["started"] >= 60:
        poll["error"] = "Đã chờ 60 giây. Backend có thể vẫn đang xử lý; bấm Kiểm tra lại để xem trạng thái mới."
        st.rerun()
    try:
        result = api.get_scan(scan_id)
    except api.ApiError as exc:
        poll["error"] = exc.message
        st.rerun()
    if result["status"] in ("pending", "processing"):
        st.status("Đang nhận diện…", state="running")
        return
    st.session_state.scan_result = result
    st.rerun()


scan = st.session_state.get("scan_result")
if not scan or scan.get("id") != scan_id:
    if st.session_state.scan_poll["error"]:
        st.warning(st.session_state.scan_poll["error"])
        if st.button("Kiểm tra lại", icon=":material/refresh:"):
            restart_poll()
        st.caption("Kiểm tra lại chỉ đọc trạng thái, không gửi một yêu cầu OCR mới.")
    else:
        wait_for_ocr()
    st.stop()

if scan["status"] == "failed":
    st.error(scan.get("error_message") or "Xử lý thất bại.")
    st.caption(f"Mã lỗi: {scan.get('error_code') or 'UNKNOWN'} · Đã thử lại {scan.get('retry_count', 0)}/3 lần")
    if scan.get("error_code") == "IMAGE_RECAPTURE_REQUIRED":
        st.info("Chụp rõ chữ, đủ sáng và để thẻ ngay ngắn. Ảnh này sẽ không được gửi lại OCR.")
        if st.button("Chụp hoặc tải ảnh mới"):
            st.switch_page("app_pages/capture.py")
    if scan.get("can_retry") and st.button("Thử xử lý lại", icon=":material/refresh:"):
        try:
            api.retry_scan(scan_id)
        except api.ApiError as exc:
            st.error(exc.message)
        else:
            restart_poll()

if scan.get("is_mock"):
    st.warning("Kết quả phát lại từ fixture (mock), không phải một lần OCR thật trên ảnh này.")
if scan.get("extractor") == "heuristic":
    st.info("Đang dùng regex dự phòng. Bộ này chưa trích xuất được họ tên và địa chỉ; ô trống không có nghĩa là thẻ không có thông tin.")

st.caption(f"OCR: {scan.get('ocr_provider') or '—'} · Trích xuất: {scan.get('extractor') or '—'}")
st.caption(f"Thời gian OCR: {scan.get('ms_ocr')} ms · Trích xuất: {scan.get('ms_extract')} ms")
model = (scan.get("extraction_config") or {}).get("model")
if model:
    st.text(f"Model: {model}")

grounding = scan.get("grounding_json") or scan.get("grounding") or {}
confidence = grounding.get("confidence")
for warning in grounding.get("agent_warnings", []):
    st.warning(warning)
if confidence:
    score = confidence.get("overall_score", 0.0)
    if score >= 0.8:
        st.success(f"Độ tin cậy tổng thể: {score*100:.0f}%")
    elif score >= 0.5:
        st.warning(f"Độ tin cậy tổng thể: {score*100:.0f}%")
    else:
        st.error(f"Độ tin cậy tổng thể: {score*100:.0f}% (Rất thấp)")

    if confidence.get("missing_critical"):
        st.warning(f"Cảnh báo thiếu thông tin quan trọng: {', '.join(confidence['missing_critical'])}")

AGENT_VI = {
    "image_quality_agent": "Kiểm tra chất lượng ảnh",
    "ocr_agent": "Nhận diện chữ",
    "extraction_agent": "Trích xuất trường",
    "grounding_agent": "Đối chiếu với văn bản OCR",
    "confidence_agent": "Chấm điểm tin cậy",
    "enrichment_agent": "Tra cứu doanh nghiệp",
    "pipeline": "Điều phối",
}
ACTION_VI = {
    "proceed": ("Đi tiếp", ":material/check_circle:",
                "Bước này đạt yêu cầu, hệ thống chuyển sang bước sau."),
    "retry": ("Thử lại", ":material/refresh:",
              "Hệ thống tự sửa: đọc lại ảnh đã tăng tương phản, hoặc trích "
              "xuất lại bằng prompt khác. Ngân sách thử lại có giới hạn."),
    "escalate": ("Cần người xem", ":material/pan_tool:",
                 "Hệ thống dừng và giao lại cho bạn thay vì đoán bừa."),
    "skip": ("Bỏ qua", ":material/skip_next:", "Bước này không áp dụng."),
}

agent_decisions = grounding.get("agent_decisions")
if agent_decisions:
    with st.expander("Quyết định của tầng agentic", expanded=False):
        st.caption(
            "Hệ thống ghi lại vì sao nó chọn mỗi bước — để bạn kiểm chứng "
            "được, thay vì phải tin một hộp đen."
        )
        for decision in agent_decisions:
            action = decision.get("action", "")
            label, icon, explain = ACTION_VI.get(
                action, (action or "?", ":material/info:", ""))
            agent = AGENT_VI.get(decision.get("agent"), decision.get("agent", "?"))

            with st.container(border=True):
                st.markdown(f"{icon} **{agent}** — {label}", help=explain)
                if decision.get("reason"):
                    st.caption(decision["reason"])
                if decision.get("metadata"):
                    with st.expander("Chi tiết kỹ thuật", expanded=False):
                        st.json(decision["metadata"])

image_col, data_col = st.columns([1, 1])
with image_col:
    st.subheader("Ảnh đầu vào OCR")
    try:
        st.image(api.get_image(scan_id), width="stretch")
    except Exception:
        st.caption("Chưa tải được ảnh. Văn bản và bản nháp bên cạnh vẫn được giữ.")
    with st.expander("Văn bản OCR thô"):
        st.text(scan.get("raw_text") or "—")
        if scan.get("ocr_text_for_draft") and scan["ocr_text_for_draft"] != scan.get("raw_text"):
            st.caption("Văn bản từ lần OCR bổ sung được chọn để đối chiếu bản nháp:")
            st.text(scan["ocr_text_for_draft"])

    # Phan thu hai cua ket qua quet: chu doc duoc nhung khong thuoc truong nao
    # cua de bai. Truoc day no bi bo im lang, nen nguoi dung khong biet tren
    # the con gi. Hien ra day KHONG phai de tu dong dua vao ho so - no la van
    # ban tho theo dong, chua duoc gan nhan truong.
    con_lai = scan.get("other_text") or []
    if con_lai:
        with st.expander(f"Phần quét được nhưng chưa thuộc trường nào "
                         f"({len(con_lai)} dòng)"):
            st.dataframe(
                [{"Dòng": x["line"], "Nội dung": x["text"]} for x in con_lai],
                width="stretch", hide_index=True,
            )
            st.caption("Khẩu hiệu, chi nhánh, mã số thuế, tài khoản mạng xã "
                       "hội… — những thứ đề bài không yêu cầu. Chép tay sang "
                       "ô Ghi chú nếu cần giữ lại.")

with data_col:
    st.subheader("Bản nháp từ danh thiếp")
    if st.session_state.pop(f"draft_saved:{scan_id}", False):
        st.success("Đã lưu bản nháp. Dữ liệu OCR gốc được giữ nguyên.")
    draft = scan.get("draft")
    if draft is None:
        st.info("Chưa có bản nháp hoàn tất.")
    else:
        st.caption("Xanh: khớp OCR · Vàng: cần kiểm tra · Xám: chưa đọc được. Các cờ hỗ trợ đối chiếu, không bảo đảm đúng trên ảnh.")
        st.caption("Bấm Lưu bản nháp trước khi chuyển trang. Dấu trạng thái mô tả bản đang lưu; thay đổi chỉ gửi khi bấm nút.")
        revision = scan.get("draft_revision", 0)
        nonce_key = f"editor_nonce:{scan_id}"
        buffer_key = f"draft_buffer:{scan_id}"
        buffer = st.session_state.get(buffer_key)
        form_draft = draft
        if buffer and buffer["revision"] == revision:
            form_draft = buffered_draft(draft, buffer["fields"])
            st.error(buffer["error"])
        prefix = f"draft:{scan_id}:{revision}:{st.session_state.get(nonce_key, 0)}"
        if scan["status"] == "ocr_done":
            with st.form(f"form:{prefix}", enter_to_submit=False):
                edited_fields = edit_fields(form_draft, prefix)
                submitted = st.form_submit_button("Lưu bản nháp", type="primary")
            if submitted:
                try:
                    updated = api.save_draft(scan_id, edited_fields, revision)
                except api.ApiError as exc:
                    st.session_state[buffer_key] = {"revision": revision, "fields": edited_fields, "error": exc.message}
                    st.session_state[nonce_key] = st.session_state.get(nonce_key, 0) + 1
                    st.rerun()
                else:
                    st.session_state.pop(buffer_key, None)
                    st.session_state.scan_result = updated
                    st.session_state[f"draft_saved:{scan_id}"] = True
                    st.rerun()
            if st.button("Tải lại bản nháp đã lưu", help="Bỏ thay đổi trong form và lấy bản mới nhất từ backend."):
                try:
                    st.session_state.scan_result = api.get_scan(scan_id)
                except api.ApiError as exc:
                    st.error(exc.message)
                else:
                    st.session_state.pop(buffer_key, None)
                    st.session_state[nonce_key] = st.session_state.get(nonce_key, 0) + 1
                    st.rerun()
        with st.expander("Bản đang lưu và lưu ý chuẩn hóa"):
            for field, label in FIELD_LABELS.items():
                st.markdown(f"**{label}**")
                for item in draft["fields"].get(field, []):
                    st.text(item["value"])
                    if item.get("source") == "user":
                        st.badge("Người dùng sửa", color="blue")
                    elif item.get("needs_review"):
                        st.badge("Cần kiểm tra", color="yellow")
                    else:
                        st.badge("Khớp OCR", color="green")

                    if "confidence_score" in item:
                        score = item["confidence_score"]
                        color = "green" if score >= 0.8 else "yellow" if score >= 0.5 else "red"
                        st.badge(f"Confidence: {score*100:.0f}%", color=color)

                    if item.get("extension"):
                        st.text(f"Máy lẻ: {item['extension']}")
                    for issue in item.get("issues", []):
                        st.warning(issue)
            st.caption("Bản nháp đã lưu thuộc bản quét này. Dùng Xác nhận lưu hồ sơ bên dưới để đưa vào danh sách đối tác.")

with st.expander("Kết quả đối chiếu với văn bản OCR"):
    grounding = scan.get("grounding") or {}
    st.json(grounding.get("counts", {}))
    st.caption("exact: khớp OCR; fuzzy: gần khớp; unverified: chưa đối chiếu được nên bị loại khỏi bản nháp. OCR cũng có thể đọc thiếu hoặc sai.")
    st.json(grounding.get("report", {}))

render_enrichment(scan)
render_save_contact(scan)
