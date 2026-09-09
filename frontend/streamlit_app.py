"""Diem vao cua frontend Streamlit.

Chay:  streamlit run frontend/streamlit_app.py
"""

import streamlit as st

from lib import api

st.set_page_config(
    page_title="Danh thiếp → Hồ sơ đối tác",
    page_icon=":material/contact_mail:",
    layout="wide",
)

# --- Trang thai dung chung giua cac trang: khoi tao o DUNG MOT NOI ---
st.session_state.setdefault("current_scan_id", None)
st.session_state.setdefault("pending_image", None)


def show_backend_status() -> None:
    """Trang thai backend + cau hinh dich vu.

    Day cung la checklist Ngay 2 nhin thay duoc: khi ca hai dong OCR va
    trich xuat chuyen sang "sẵn sàng" thi phu thuoc rui ro cao nhat da xong.
    """
    try:
        data = api.health()
    except api.ApiError as exc:
        st.error(
            f"{exc.message}\n\n"
            "Kiểm tra đã chạy backend chưa:\n\n"
            "`.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload` "
            "trong thư mục `backend/`.",
            icon=":material/cloud_off:",
        )
        return

    cfg = data["config"]
    ocr_ok = cfg["ocr_credentials_present"]
    ext_ok = cfg["gemini_key_present"] and cfg["gemini_model_set"]

    def mark(ok: bool) -> str:
        return ":green[sẵn sàng]" if ok else ":orange[chưa cấu hình]"

    with st.sidebar:
        st.success(f"Backend đang chạy ({data['env']})", icon=":material/cloud_done:")
        st.caption("Trạng thái dịch vụ")
        st.markdown(f"- OCR — `{cfg['ocr_provider']}` — {mark(ocr_ok)}")
        st.markdown(f"- Trích xuất — `{cfg['extractor']}` — {mark(ext_ok)}")
        st.markdown(
            f"- Tra cứu — {'bật' if cfg['enrich_enabled'] else 'tắt'}"
        )


show_backend_status()

page = st.navigation(
    [
        st.Page(
            "app_pages/capture.py",
            title="Quét thẻ",
            icon=":material/photo_camera:",
            default=True,
        ),
        st.Page(
            "app_pages/review.py", title="Kiểm tra", icon=":material/fact_check:"
        ),
        st.Page(
            "app_pages/contacts.py", title="Hồ sơ", icon=":material/contacts:"
        ),
    ],
    position="top",
)

st.title(page.title)
page.run()
