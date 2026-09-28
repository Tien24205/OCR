"""Trang chu cua nguoi dang dang nhap: loi chao, tom tat rieng, va so lieu.

VI SAO KHONG TAO MOT TRANG "Trang chu" RIENG: dat mot trang nua truoc trang
Quet the nghia la them mot cu bam vao viec ma nguoi ta mo ung dung len de
lam. Trang nay von da la trang so lieu, va tu Ngay 29 thi so lieu do da
duoc loc theo chu so huu - nen no DA LA trang chu ca nhan, chi la chua noi
ra dieu do.
"""

import streamlit as st

from lib import api

STATUS_VI = {
    "pending": "Chờ xử lý",
    "processing": "Đang xử lý",
    "ocr_done": "Đã nhận diện",
    "failed": "Lỗi",
    "committed": "Đã lưu hồ sơ",
}
LANG_VI = {"ja": "Tiếng Nhật", "en": "Tiếng Anh", "ko": "Tiếng Hàn",
           "zh": "Tiếng Trung", "mixed": "Song ngữ",
           # Chữ Hán nhưng không đủ dấu hiệu để phân biệt Nhật với Trung.
           "han": "Chữ Hán (chưa rõ)",
           "other": "Khác", "khong ro": "Không rõ"}
ACTION_VI = {"proceed": "Đi tiếp", "retry": "Thử lại", "escalate": "Cần người xem",
             "skip": "Bỏ qua"}
ENRICH_VI = {"verified": "Đã xác minh", "unverified": "Chưa xác minh",
             "conflicting": "Nguồn mâu thuẫn", "not_found": "Không tìm thấy"}


def bars(mapping: dict, names: dict, label: str) -> None:
    """Biểu đồ cột từ một dict đếm. Không vẽ gì nếu chưa có dữ liệu."""
    if not mapping:
        st.caption("Chưa có dữ liệu.")
        return
    rows = [{label: names.get(k, k), "Số lượng": v} for k, v in mapping.items()]
    st.bar_chart(rows, x=label, y="Số lượng", horizontal=True)


def _ten_goi() -> str | None:
    """Ten de chao. Khong co ten hien thi thi lay phan truoc dau @ cua email.

    Chao bang ca dia chi email day du nghe nhu mot thu tu dong; lay phan
    truoc @ thi gan voi cach nguoi ta tu goi minh hon.
    """
    nguoi = st.session_state.get("nguoi_dung") or {}
    ten = (nguoi.get("display_name") or "").strip()
    if ten:
        return ten
    email = (nguoi.get("email") or "").strip()
    return email.split("@")[0] if email else None


def _la_quan_tri() -> bool:
    return (st.session_state.get("nguoi_dung") or {}).get("role") == "admin"


try:
    data = api.stats()
except api.ApiError as exc:
    st.error(exc.message, icon=":material/error:")
    st.stop()

totals = data["totals"]

# --- Loi chao ------------------------------------------------------------
ten_toi = _ten_goi()
if ten_toi:
    st.subheader(f"Chào {ten_toi}")

# NOI RO SO LIEU NAY LA CUA AI. Voi nguoi dung thuong, backend da loc theo
# chu so huu; voi quan tri thi khong loc. Hai con so do khac nhau ve ban
# chat, va khong noi ra thi quan tri se tuong 40 ban quet kia la cua minh.
if _la_quan_tri():
    st.caption("Bạn đang là **quản trị**, nên số liệu dưới đây là của **toàn "
               "hệ thống**, không riêng bạn.")
elif ten_toi:
    st.caption("Số liệu dưới đây chỉ tính phần của bạn. Người khác không thấy "
               "bản quét hay hồ sơ của bạn, và ngược lại.")

with st.container(horizontal=True):
    st.metric("Bản quét", totals["scans"])
    st.metric("Hồ sơ đối tác", totals["contacts"])
    st.metric("Doanh nghiệp", totals["organizations"])
    st.metric("Thông tin tra cứu", totals["enrichments"])

TRANG_THAI_VI = {"pending": "đang chờ", "processing": "đang nhận diện",
                 "ocr_done": "chờ bạn kiểm tra", "committed": "đã lưu hồ sơ",
                 "failed": "lỗi"}


def _ban_quet_gan_nhat() -> dict | None:
    """Ban quet moi nhat cua nguoi nay, de mo lai bang mot cu bam.

    Nuot loi co y: day la mot tien ich o dau trang, no khong duoc lam ca
    trang so lieu hong chi vi mot loi goi phu that bai.
    """
    try:
        items = api.list_scans(limit=1)["items"]
    except api.ApiError:
        return None
    return items[0] if items else None


if not totals["scans"]:
    st.info(
        (f"{ten_toi} ơi, bạn chưa quét tấm thẻ nào. " if ten_toi
         else "Chưa có bản quét nào. ")
        + "Sang trang **Quét thẻ** để bắt đầu.",
        icon=":material/photo_camera:",
    )
    if st.button("Quét tấm thẻ đầu tiên", type="primary",
                 icon=":material/photo_camera:"):
        st.switch_page("app_pages/capture.py")
    st.stop()

# --- Tom tat rieng, va duong quay lai viec dang lam do ------------------
gan_nhat = _ban_quet_gan_nhat()
if gan_nhat:
    trang_thai = TRANG_THAI_VI.get(gan_nhat["status"], gan_nhat["status"])
    nhan = gan_nhat.get("full_name") or gan_nhat.get("company_name") or "chưa rõ tên"
    luc = (gan_nhat.get("created_at") or "")[11:16]
    with st.container(horizontal=True, vertical_alignment="center"):
        st.markdown(f"Gần nhất: **{nhan}** · {trang_thai}"
                    + (f" · lúc {luc}" if luc else ""))
        if st.button("Mở lại", icon=":material/fact_check:"):
            # Dat lai ca ba khoa: giu `scan_result` cu thi trang Kiem tra
            # hien ban quet truoc do trong mot nhip roi moi doi.
            st.session_state.current_scan_id = gan_nhat["id"]
            st.session_state.pop("scan_result", None)
            st.session_state.pop("scan_poll", None)
            st.switch_page("app_pages/review.py")

# --- Hồ sơ tạo mới theo ngày ---
per_day = data.get("contacts_per_day") or []
if any(row["contacts"] for row in per_day):
    st.subheader("Hồ sơ tạo mới theo ngày")
    st.line_chart(
        [{"Ngày": r["date"], "Hồ sơ": r["contacts"]} for r in per_day],
        x="Ngày", y="Hồ sơ",
    )

left, right = st.columns(2)

with left:
    st.subheader("Ngôn ngữ thẻ")
    bars(data.get("languages", {}), LANG_VI, "Ngôn ngữ")

with right:
    st.subheader("Trạng thái bản quét")
    bars(data.get("scans_by_status", {}), STATUS_VI, "Trạng thái")

# --- Độ tin cậy ---
confidence = data.get("confidence") or {}
st.subheader("Độ tin cậy")
if confidence.get("average") is None:
    st.caption(
        "Chưa có bản quét nào được chấm điểm. Điểm tin cậy chỉ được tính khi "
        "chạy với chế độ agent (`AGENT_ENABLED=true`)."
    )
else:
    with st.container(horizontal=True):
        st.metric("Điểm trung bình", f"{confidence['average'] * 100:.0f}%")
        st.metric("Số thẻ đã chấm", confidence["measured_scans"])
        st.metric(
            "Thẻ dưới 50%", confidence["below_half"],
            help="Những thẻ này gần như chắc chắn cần người kiểm tra lại.",
        )
    missing = data.get("missing_critical") or {}
    if missing:
        names = {"missing_name": "thiếu họ tên", "missing_company": "thiếu công ty"}
        st.caption(
            "Cảnh báo thiếu trường quan trọng: "
            + " · ".join(f"{names.get(k, k)}: {v}" for k, v in missing.items())
        )

# --- Quyết định của tầng agentic ---
actions = data.get("agent_actions") or {}
st.subheader("Quyết định của tầng agentic")
if not actions:
    st.caption(
        "Chưa có quyết định nào được ghi. Tầng agentic đang tắt — bật bằng "
        "`AGENT_ENABLED=true` trong `backend/.env`."
    )
else:
    bars(actions, ACTION_VI, "Quyết định")
    st.caption(
        "“Thử lại” là số lần hệ thống tự sửa: đọc lại ảnh đã tăng tương phản, "
        "hoặc trích xuất lại bằng prompt khác."
    )

# --- Tra cứu doanh nghiệp ---
enrich = data.get("enrichments_by_status") or {}
if enrich:
    st.subheader("Kết quả tra cứu doanh nghiệp")
    bars(enrich, ENRICH_VI, "Trạng thái")

# --- Doanh nghiệp nhiều liên hệ nhất ---
top = data.get("top_organizations") or []
if top:
    st.subheader("Doanh nghiệp có nhiều liên hệ nhất")
    st.dataframe(
        [{"Doanh nghiệp": r["organization"], "Số liên hệ": r["contacts"]} for r in top],
        width="stretch", hide_index=True,
    )


# --------------------------------------------------------------------------
# Cap tai khoan (chi quan tri, Ngay 31)
# --------------------------------------------------------------------------
#
# VI SAO O DAY: khi `REGISTRATION_OPEN=false` thi trang dang nhap khong con o
# "Tao tai khoan" nua - do la ca muc dich. Nhung quan tri VAN phai cap duoc
# tai khoan cho dong nghiep, va neu khong co cho nao lam viec do tren giao
# dien thi ho se phai go `curl`, hoac se mo lai cua dang ky va quen dong.
#
# Dung lai `/api/auth/register`: backend cho quan tri di qua cong da dong.
# Khong them endpoint rieng - cung phep kiem dinh dang, cung cach bam mat
# khau, mot duong de kiem.

if _la_quan_tri():
    st.divider()
    with st.expander("Cấp tài khoản cho người khác", icon=":material/person_add:"):
        with st.form("cap_tai_khoan"):
            ten_moi = st.text_input("Tên hiển thị (không bắt buộc)")
            email_moi = st.text_input("Email", autocomplete="off")
            mk_moi = st.text_input("Mật khẩu tạm (ít nhất 10 ký tự)",
                                   type="password", autocomplete="new-password")
            cap = st.form_submit_button("Tạo tài khoản", width="stretch")
        if cap:
            if len(mk_moi) < 10:
                st.error("Mật khẩu cần ít nhất 10 ký tự.", icon=":material/error:")
            elif "@" not in email_moi:
                st.error("Email chưa đúng định dạng.", icon=":material/error:")
            else:
                try:
                    api.dang_ky(email_moi, mk_moi, ten_moi)
                except api.ApiError as exc:
                    st.error(exc.message, icon=":material/error:")
                else:
                    # KHONG doi phien hien tai: `dang_ky` tra ve phieu cua tai
                    # khoan VUA TAO, va nhan no vao day se dang xuat quan tri
                    # roi dang nhap thanh nguoi moi. Chi bao da xong.
                    st.success(f"Đã tạo tài khoản cho {email_moi}.",
                               icon=":material/check:")
        st.caption("Người được cấp nên đổi mật khẩu sau lần đăng nhập đầu. "
                   "Tài khoản tạo ở đây luôn là quyền thường, không phải quản trị.")
