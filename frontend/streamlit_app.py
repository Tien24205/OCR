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

    Presence checks do not verify account permissions, quota or model access.
    """
    try:
        data = api.health()
    except api.ApiError as exc:
        st.error(
            f"{exc.message}\n\n"
            "Kiểm tra đã chạy backend chưa:\n\n"
            "`.venv\\Scripts\\python.exe -m uvicorn app.main:app --app-dir backend --port 8000` "
            "từ gốc dự án.",
            icon=":material/cloud_off:",
        )
        return

    cfg = data["config"]
    # Theo provider dang chon, khong theo credentials Google - tesseract
    # khong dung credentials nao (D1-02).
    ocr_ok = cfg["ocr_configured"]
    ext_ok = cfg["gemini_key_present"] and cfg["gemini_model_set"]

    def mark(ok: bool) -> str:
        return "có cấu hình, chưa xác minh dịch vụ" if ok else "chưa đủ cấu hình"

    # Ket qua xac minh THAT gan nhat, neu da tung chay. Ba trang thai phai
    # phan biet cho ro (D1-02): da cau hinh / mock / da xac minh bang loi goi
    # that. Dong nhat hai cai dau voi cai thu ba la tu doi minh.
    verified = data.get("verified") or {}
    da_kiem = {c["component"]: c for c in verified.get("checks", [])}
    luc = (verified.get("checked_at") or "")[11:16]

    def dong(component: str, mac_dinh: str) -> str:
        kiem = da_kiem.get(component)
        if not kiem or kiem["state"] == "skipped":
            return mac_dinh
        dau = "✓ đã xác minh" if kiem["state"] == "verified" else "✗ lỗi"
        return f"{dau} lúc {luc} — {kiem['detail']}"

    with st.sidebar:
        st.success(f"Backend đang chạy ({data['env']})", icon=":material/cloud_done:")
        st.caption("Cấu hình xử lý")
        st.caption("Điều phối agent: " + ("bật" if cfg.get("agent_enabled") else "tắt; dùng luồng hiện tại"))
        ocr_status = "phát lại fixture, không gọi OCR thật" if cfg['ocr_provider'] == 'mock' else mark(ocr_ok)
        ext_status = "regex dự phòng, giới hạn họ tên/địa chỉ" if cfg['extractor'] == 'heuristic' else mark(ext_ok)
        st.markdown(f"- OCR — `{cfg['ocr_provider']}` — {dong('ocr', ocr_status)}")
        st.markdown(f"- Trích xuất — `{cfg['extractor']}` — {dong('extract', ext_status)}")
        enrich_mac_dinh = "bật, cần Gemini và nguồn phù hợp" if cfg["enrich_enabled"] else "tắt"
        st.markdown(f"- Tra cứu — {dong('enrich', enrich_mac_dinh)}")

        if st.button("Xác minh dịch vụ", icon=":material/verified:",
                     width="stretch"):
            with st.spinner("Đang gọi thật…"):
                try:
                    ket_qua = api.verify_readiness()
                except api.ApiError as exc:
                    st.error(exc.message, icon=":material/error:")
                else:
                    # Ba dong tren tu no da bao ket qua; chi can noi ro da tieu
                    # bao nhieu lan goi, vi day la thu nguoi dung phai tra tien.
                    st.toast(f"Đã dùng {ket_qua['service_calls']} lời gọi dịch vụ.")
                    st.rerun()
        st.caption("Nút này gọi thật nhà cung cấp đang bật — tốn tối đa hai "
                   "lời gọi. Không tự chạy.")


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
        st.Page(
            "app_pages/dashboard.py", title="Tổng quan",
            icon=":material/insights:"
        ),
    ],
    position="top",
)

st.title(page.title)
page.run()
