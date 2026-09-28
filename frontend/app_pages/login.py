"""Trang dang nhap / dang ky (Ngay 23).

Trang nay la trang DUY NHAT hien ra khi backend bat buoc dang nhap ma phien
hien tai chua co phieu - xem `streamlit_app.py`.
"""

import streamlit as st

from lib import api

MAT_KHAU_TOI_THIEU = 10


def _nhan_phieu(ket_qua: dict) -> None:
    """Luu phieu vao PHIEN cua trinh duyet nay, roi ve lai trang.

    `st.session_state` rieng cho tung phien trinh duyet, nen hai nguoi dung
    hai may khong bao gio thay phieu cua nhau - khac han `@st.cache_resource`
    von dung chung ca tien trinh.
    """
    st.session_state.phieu_dang_nhap = ket_qua["token"]
    st.session_state.nguoi_dung = ket_qua["user"]
    # Bo sach trang thai cua nguoi truoc: khong lam thi ban quet dang mo cua
    # nguoi vua dang xuat con nam lai, va nguoi moi vao se thay mot ma ban
    # quet ma ho khong co quyen doc - roi nhan 404 ma khong hieu vi sao.
    for khoa in ("current_scan_id", "pending_image", "scan_result", "scan_poll"):
        st.session_state.pop(khoa, None)
    st.rerun()


st.caption("Ứng dụng đang bật đăng nhập. Mỗi người chỉ thấy bản quét và hồ sơ "
           "của chính mình; quản trị thấy tất cả.")

# Hoi backend chu khong tu doan: luat "chua co ai thi van cho dang ky" nam o
# backend, va viet lai no o day la tao ban sao thu hai cua mot luat.
cua_mo = api.cua_dang_ky_mo()

if not cua_mo:
    # KHONG hien o "Tao tai khoan" nua. De no lai thi nguoi ta dien xong ca
    # bieu mau roi moi nhan 403 - va ho se tuong minh go sai chu khong phai
    # trang nay khong nhan nguoi moi.
    st.info("Trang này không mở đăng ký. Liên hệ quản trị viên để được cấp "
            "tài khoản.", icon=":material/lock:")

vao, *con_lai = st.tabs(["Đăng nhập", "Tạo tài khoản"] if cua_mo
                        else ["Đăng nhập"])

with vao:
    with st.form("dang_nhap"):
        email = st.text_input("Email", key="vao_email",
                              autocomplete="username")
        mat_khau = st.text_input("Mật khẩu", type="password", key="vao_mk",
                                 autocomplete="current-password")
        gui = st.form_submit_button("Đăng nhập", width="stretch")
    if gui:
        if not email or not mat_khau:
            st.error("Nhập cả email và mật khẩu.", icon=":material/error:")
        else:
            try:
                _nhan_phieu(api.dang_nhap(email, mat_khau))
            except api.ApiError as exc:
                st.error(exc.message, icon=":material/lock:")

for moi in con_lai:
    with moi:
        with st.form("dang_ky"):
            ten = st.text_input("Tên hiển thị (không bắt buộc)", key="moi_ten")
            email_moi = st.text_input("Email", key="moi_email",
                                      autocomplete="username")
            mk1 = st.text_input(f"Mật khẩu (ít nhất {MAT_KHAU_TOI_THIEU} ký tự)",
                                type="password", key="moi_mk",
                                autocomplete="new-password")
            mk2 = st.text_input("Nhập lại mật khẩu", type="password", key="moi_mk2",
                                autocomplete="new-password")
            tao = st.form_submit_button("Tạo tài khoản", width="stretch")
        if tao:
            # Kiem o day truoc khi goi API: bao loi ngay canh o nhap thi de sua
            # hon la doi mot ma loi 422 tu may chu.
            if mk1 != mk2:
                st.error("Hai ô mật khẩu chưa khớp.", icon=":material/error:")
            elif len(mk1) < MAT_KHAU_TOI_THIEU:
                st.error(f"Mật khẩu cần ít nhất {MAT_KHAU_TOI_THIEU} ký tự.",
                         icon=":material/error:")
            elif "@" not in email_moi:
                st.error("Email chưa đúng định dạng.", icon=":material/error:")
            else:
                try:
                    _nhan_phieu(api.dang_ky(email_moi, mk1, ten))
                except api.ApiError as exc:
                    st.error(exc.message, icon=":material/error:")

        st.caption("Người tạo tài khoản đầu tiên trên hệ thống này sẽ là quản trị.")
