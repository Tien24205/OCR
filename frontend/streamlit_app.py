"""Diem vao cua frontend Streamlit.

Chay:  streamlit run frontend/streamlit_app.py
"""

from pathlib import Path

import streamlit as st

from lib import api

TEN_SAN_PHAM = "CardLens"
KHAU_HIEU = "Chụp danh thiếp, nhận hồ sơ đối tác tin được"
ASSETS = Path(__file__).parent / "assets"
TEN_COOKIE = "cardlens_phien"        # trung voi asgi_app.TEN_COOKIE

st.set_page_config(
    page_title=f"{TEN_SAN_PHAM} · {KHAU_HIEU}",
    page_icon=str(ASSETS / "icon.svg"),
    layout="wide",
)
st.logo(str(ASSETS / "logo.svg"), icon_image=str(ASSETS / "icon.svg"), size="large")

# --- Trang thai dung chung giua cac trang: khoi tao o DUNG MOT NOI ---
st.session_state.setdefault("current_scan_id", None)
st.session_state.setdefault("pending_image", None)
st.session_state.setdefault("phieu_dang_nhap", None)
st.session_state.setdefault("nguoi_dung", None)


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
        st.markdown(f"**{TEN_SAN_PHAM}**  \n:gray[{KHAU_HIEU}]")
        st.badge("Đa ngôn ngữ · Anh, Nhật, Hàn, Trung", icon=":material/translate:", color="blue")
        st.badge("Chống bịa dữ liệu bằng đối chiếu OCR", icon=":material/verified_user:", color="orange")
    # Chi tiet ky thuat cho nguoi van hanh: gap lai mac dinh de man hinh
    # chinh nhin nhu mot san pham, khong nhu bang chan doan.
    with st.sidebar.expander("Trạng thái hệ thống", icon=":material/monitor_heart:"):
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


def bat_buoc_dang_nhap() -> bool:
    """Backend co doi dang nhap khong. Hoi backend chu khong tu doan.

    Neu backend khong tra loi duoc thi coi nhu KHONG doi: `show_backend_status`
    o tren da bao ro backend dang hong roi, va chan them mot man hinh dang
    nhap len tren mot backend da chet chi lam nguoi dung tuong minh go sai
    mat khau.
    """
    try:
        return bool(api.health()["config"].get("login_required"))
    except api.ApiError:
        return False


def hien_nguoi_dang_dung() -> None:
    nguoi = st.session_state.get("nguoi_dung") or {}
    if not nguoi:
        return
    with st.sidebar:
        st.divider()
        ten = nguoi.get("display_name") or nguoi.get("email", "")
        vai = " · quản trị" if nguoi.get("role") == "admin" else ""
        st.caption(f"Đang đăng nhập: **{ten}**{vai}")
        if st.button("Đăng xuất", icon=":material/logout:", width="stretch"):
            # Xoa CA trang thai lam viec chu khong chi phieu: de lai
            # `current_scan_id` thi nguoi dang nhap sau se mo trung ban quet
            # cua nguoi truoc va nhan 404 khong ro ly do.
            for khoa in ("phieu_dang_nhap", "nguoi_dung", "current_scan_id",
                         "pending_image", "scan_result", "scan_poll"):
                st.session_state.pop(khoa, None)
            # Xoa ca cookie "ghi nho dang nhap"; va KHONG khoi phuc tu cookie
            # trong phien nay nua - cookie chi mat o lan chay SAU, nen khong
            # chan thi dang xuat xong lai tu dang nhap lai ngay.
            st.session_state.da_dang_xuat = True
            st.session_state.can_xoa_phien = True
            st.rerun()


def khoi_phuc_phien() -> None:
    """Mo lai trang ma con cookie "ghi nho dang nhap" thi vao thang.

    Hoi backend `/api/auth/me` bang phieu trong cookie: phieu het han, bi thu
    hoi hay tai khoan bi khoa thi backend tu choi, va cookie bi xoa - khong
    tin mot cookie chi vi no con nam trong trinh duyet.
    """
    ss = st.session_state
    if ss.get("phieu_dang_nhap") or ss.get("da_dang_xuat") or ss.get("phien_nho_hong"):
        return
    try:
        phieu = st.context.cookies.get(TEN_COOKIE)
    except Exception:
        return
    if not isinstance(phieu, str) or not phieu:
        return
    ss.phieu_dang_nhap = phieu
    try:
        toi = api.toi_la_ai()
    except api.ApiError:
        toi = {}
    if not toi.get("user"):
        ss.phieu_dang_nhap = None
        ss.phien_nho_hong = True        # thu MOT lan moi phien, khong lap lai
        ss.can_xoa_phien = True
        return
    ss.nguoi_dung = toi["user"]


def dong_bo_cookie() -> None:
    """Dat / xoa cookie qua route `/phien` cua `asgi_app.py`.

    Phai do trinh duyet goi: cookie HttpOnly chi dat duoc bang mot cau tra
    loi HTTP gui ve CHINH trinh duyet do, ma Streamlit noi chuyen qua
    WebSocket. Chay thang `streamlit_app.py` (khong qua asgi_app) thi route
    khong ton tai - loi goi that bai im lang, chi mat phan ghi nho.
    """
    import json

    if nho := st.session_state.pop("can_nho_phien", None):
        st.html("<script>fetch('/phien',{method:'POST',credentials:'same-origin',"
                "headers:{'Content-Type':'application/json'},body:"
                + json.dumps(json.dumps(nho)) + "})</script>",
                unsafe_allow_javascript=True)
    if st.session_state.pop("can_xoa_phien", False):
        st.html("<script>fetch('/phien',{method:'DELETE',credentials:'same-origin'})</script>",
                unsafe_allow_javascript=True)


khoi_phuc_phien()
dong_bo_cookie()
show_backend_status()

# CONG DANG NHAP.
#
# Chan bang cach dua DANH SACH TRANG cho `st.navigation`, chu khong phai
# bang `st.Page(...).run()` roi `st.stop()`: Streamlit chi cho chay dung
# trang do `st.navigation` tra ve, nen cach kia nem StreamlitAPIException.
# Lam theo cach nay con dung hon ve mat an toan - khi chua dang nhap thi
# bon trang kia KHONG CO trong thanh dieu huong, thay vi co ma bi chan.
chua_vao = bat_buoc_dang_nhap() and not st.session_state.get("phieu_dang_nhap")

if chua_vao:
    page = st.navigation([
        st.Page("app_pages/login.py", title="Đăng nhập",
                icon=":material/login:", default=True),
    ])
else:
    hien_nguoi_dang_dung()
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
                "app_pages/graph.py", title="Mạng lưới",
                icon=":material/hub:"
            ),
            st.Page(
                "app_pages/audit.py", title="Nhật ký hoạt động",
                icon=":material/history:"
            ),
        ],
        position="top",
    )

st.title(page.title)
page.run()
