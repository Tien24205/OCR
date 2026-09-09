"""Ngay 4-5: cho OCR chay xong, roi doi chieu anh voi form sua du lieu."""

import streamlit as st

from lib import api

scan_id = st.session_state.get("current_scan_id")

if not scan_id:
    st.info(
        "Chưa có bản quét nào. Sang trang **Quét thẻ** để chụp hoặc tải ảnh.",
        icon=":material/photo_camera:",
    )
    st.stop()

st.caption(f"Bản quét `{scan_id}`")


@st.fragment(run_every="1s")
def wait_for_ocr() -> None:
    """Poll trang thai OCR ma khong chay lai ca trang.

    `run_every` khien rieng fragment nay chay lai moi giay; phan con lai cua
    trang giu nguyen. Khi xong, `st.rerun()` chay lai toan bo trang de thoat
    khoi vong poll.
    """
    try:
        scan = api.get_scan(scan_id)
    except api.ApiError as exc:
        if exc.status == 404:
            st.warning(
                "Backend chưa có `GET /api/scans/{id}`. Endpoint này được thêm "
                "ở **Ngày 4** theo kế hoạch triển khai.",
                icon=":material/construction:",
            )
        else:
            st.error(exc.message, icon=":material/error:")
        return

    if scan["status"] in ("pending", "processing"):
        st.status("Đang nhận diện…", state="running")
        return

    st.session_state.scan_result = scan
    st.rerun()


scan = st.session_state.get("scan_result")
if not scan or scan.get("id") != scan_id:
    wait_for_ocr()
    st.stop()

if scan["status"] == "failed":
    st.error(
        scan.get("error_message") or "OCR thất bại.", icon=":material/error:"
    )
    if st.button("Thử lại", icon=":material/refresh:"):
        st.session_state.pop("scan_result", None)
        st.rerun()
    st.stop()

image_col, form_col = st.columns([1, 1])

with image_col:
    st.subheader("Ảnh gốc")
    try:
        st.image(api.get_image(scan["image_ref"]), width="stretch")
    except Exception:
        st.caption("Chưa tải được ảnh.")
    with st.expander("Văn bản OCR thô"):
        st.text(scan.get("raw_text") or "—")

with form_col:
    st.subheader("Dữ liệu trích xuất")
    st.info(
        "Ngày 4 hiển thị các trường được trích xuất; Ngày 5 thêm form sửa, "
        "cờ “cần kiểm tra” và các quy tắc chuẩn hóa.",
        icon=":material/construction:",
    )
