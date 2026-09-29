"""Nhat ky hoat dong (audit log): ai lam gi, voi cai gi, luc nao.

Thay cho trang Tong quan cu. Nguoi dung thuong thay hoat dong cua chinh minh
- ke ca nhung lan dang nhap SAI vao tai khoan cua minh; quan tri thay cua
moi nguoi. Loc duoc theo khoang ngay, loai hanh dong va nguoi thuc hien, va
tai ve CSV de nop cho kiem toan.
"""

import csv
import io
from datetime import date, datetime, timedelta, timezone

import streamlit as st

from lib import api

HANH_DONG_VI = {
    "dang_nhap": ("Đăng nhập", ":material/login:"),
    "dang_nhap_that_bai": ("Đăng nhập thất bại", ":material/gpp_bad:"),
    "tao_tai_khoan": ("Tạo tài khoản", ":material/person_add:"),
    "quet_the": ("Quét thẻ", ":material/photo_camera:"),
    "sua_ban_nhap": ("Sửa bản nháp", ":material/edit_note:"),
    "luu_ho_so": ("Lưu hồ sơ", ":material/save:"),
    "sua_ho_so": ("Sửa hồ sơ", ":material/edit:"),
    "xoa_ho_so": ("Xoá hồ sơ", ":material/delete:"),
    "xoa_ban_quet": ("Xoá bản quét", ":material/delete_sweep:"),
    "xuat_du_lieu": ("Xuất dữ liệu", ":material/download:"),
}
LOAI_VI = {"ho_so": "Hồ sơ", "ban_quet": "Bản quét", "tai_khoan": "Tài khoản"}
KHOANG = {"7 ngày": 7, "30 ngày": 30, "90 ngày": 90, "Tất cả": None}


def _ten(ma: str) -> str:
    return HANH_DONG_VI.get(ma, (ma, ""))[0]


TRUONG_VI = {"full_names": "họ tên", "company_names": "công ty", "job_titles": "chức danh",
             "departments": "phòng ban", "emails": "email", "phones": "điện thoại",
             "websites": "website", "addresses": "địa chỉ"}
LY_DO_VI = {"sai_mat_khau": "sai mật khẩu", "khong_co_tai_khoan": "email chưa có tài khoản",
            "tai_khoan_bi_khoa": "tài khoản bị khoá"}
TRANG_THAI_VI = {"pending": "đang chờ", "processing": "đang nhận diện", "ocr_done": "chờ kiểm tra",
                 "committed": "đã lưu hồ sơ", "failed": "lỗi"}


def _truong(ds) -> str:
    return ", ".join(TRUONG_VI.get(t, t) for t in ds or [])


def _cac_dong(x: dict) -> list[str]:
    """Chi tiet doc duoc, tung y mot. Nhat ky khong giu du lieu ca nhan cua
    doi tac - chi ten truong, so luong, so thu tu."""
    c = x.get("chi_tiet") or {}
    h = x["hanh_dong"]
    phan: list[str] = []
    if h == "quet_the":
        phan.append(f"{c.get('so_anh', 1)} ảnh" + (" · tải hàng loạt" if c.get("hang_loat") else ""))
        if c.get("so_thu_tu"):
            phan.append("bản quét " + ", ".join(f"#{s}" for s in c["so_thu_tu"] if s))
        if c.get("anh_loi"):
            phan.append(f"{c['anh_loi']} ảnh lỗi bị bỏ qua")
        if c.get("dung_luong_kb"):
            phan.append(f"{c['dung_luong_kb']:,.0f} KB")
    elif h == "sua_ban_nhap":
        if c.get("so_thu_tu"):
            phan.append(f"bản quét #{c['so_thu_tu']}")
        phan.append(f"lưu bản nháp lần {c.get('ban', '?')}")
        phan.append(("sửa: " + _truong(c["truong_sua"])) if c.get("truong_sua") else "không đổi trường nào")
    elif h == "luu_ho_so":
        phan.append({"gop": "gộp vào hồ sơ có sẵn", "cap_nhat": "ghi đè hồ sơ có sẵn"}
                    .get(c.get("kieu"), "tạo hồ sơ mới"))
        if c.get("ban_quet"):
            phan.append(f"từ bản quét #{c['ban_quet']}")
        if c.get("kieu") == "gop":
            phan.append(("bổ sung: " + _truong(c["truong_bo_sung"])) if c.get("truong_bo_sung")
                        else "không có thông tin mới")
        if c.get("so_gia_tri"):
            phan.append(f"{c['so_gia_tri']} giá trị")
        if c.get("co_ghi_chu"):
            phan.append("có ghi chú")
    elif h == "sua_ho_so":
        phan.append(f"lên phiên bản {c.get('phien_ban', '?')}")
        if c.get("truong_sua"):
            phan.append("sửa: " + _truong(c["truong_sua"]))
        if c.get("sua_ghi_chu"):
            phan.append("sửa ghi chú")
        if c.get("doi_doanh_nghiep"):
            phan.append("đổi doanh nghiệp liên kết")
    elif h == "xoa_ho_so":
        if "so_ban_quet_xoa_theo" in c:
            phan.append(f"xoá kèm {c['so_ban_quet_xoa_theo']} bản quét và ảnh gốc")
    elif h == "xoa_ban_quet":
        if c.get("so_thu_tu"):
            phan.append(f"bản quét #{c['so_thu_tu']}")
        if c.get("trang_thai"):
            phan.append(f"lúc xoá đang: {TRANG_THAI_VI.get(c['trang_thai'], c['trang_thai'])}")
    elif h == "xuat_du_lieu":
        phan.append(f"{str(c.get('dinh_dang', '')).upper()} · {c.get('so_ho_so', 0)} hồ sơ")
        if c.get("dung_luong_kb") is not None:
            phan.append(f"{c['dung_luong_kb']:,.1f} KB")
    elif h == "dang_nhap_that_bai" and c.get("ly_do"):
        phan.append(LY_DO_VI.get(c["ly_do"], c["ly_do"]))
    elif h == "tao_tai_khoan" and "vai_tro" in c:
        phan.append("vai trò: " + ("quản trị" if c["vai_tro"] == "admin" else "người dùng"))
    return phan


def _mo_ta(x: dict) -> str:
    return " · ".join(_cac_dong(x))


def _thiet_bi(ua: str | None) -> str:
    """"Chrome · Windows" tu chuoi User-Agent. Doan theo tu khoa, du de doc."""
    if not ua:
        return ""
    trinh = next((ten for khoa, ten in (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"),
                                         ("Chrome/", "Chrome"), ("Safari/", "Safari"),
                                         ("python-httpx", "API / script"), ("curl/", "curl"))
                  if khoa in ua), "Khác")
    may = next((ten for khoa, ten in (("Android", "Android"), ("iPhone", "iPhone"), ("iPad", "iPad"),
                                       ("Windows", "Windows"), ("Mac OS", "macOS"), ("Linux", "Linux"))
                if khoa in ua), "")
    return f"{trinh} · {may}" if may else trinh


def _doi_tuong(x: dict) -> str:
    dt = x.get("doi_tuong")
    loai = LOAI_VI.get(x.get("loai"), x.get("loai") or "")
    if x.get("loai") == "tai_khoan":
        return f"Tài khoản {x.get('ai') or ''}".strip()
    if not dt:
        return loai
    return f"{loai}: {dt['ten']}"


def _gio_dia_phuong(luc: str) -> datetime | None:
    try:
        return datetime.fromisoformat(luc).astimezone()
    except (TypeError, ValueError):
        return None


la_quan_tri = (st.session_state.get("nguoi_dung") or {}).get("role") == "admin"
st.caption(
    "Mọi thao tác quan trọng đều để lại một dòng: đăng nhập, quét, lưu, sửa, xoá, xuất. "
    + ("Bạn là **quản trị** nên thấy hoạt động của **toàn hệ thống**. " if la_quan_tri
       else "Bạn chỉ thấy hoạt động của chính mình. ")
    + "Nhật ký chỉ ghi thêm — không ai sửa hay xoá được."
)

# --- Bo loc ----------------------------------------------------------------
with st.container(horizontal=True, vertical_alignment="bottom"):
    khoang = st.segmented_control("Khoảng thời gian", list(KHOANG), default="30 ngày",
                                  key="audit_khoang")
    tu_khoa = st.text_input("Tìm theo người thực hiện hoặc mã đối tượng",
                            key="audit_tim", placeholder="vd. an@congty.vn")

so_ngay = KHOANG.get(khoang or "30 ngày")
tu_ngay = (datetime.now(timezone.utc) - timedelta(days=so_ngay)).isoformat() if so_ngay else None

try:
    items = api.nhat_ky_kiem_toan(limit=1000, since=tu_ngay)["items"]
except api.ApiError as exc:
    st.error(exc.message, icon=":material/error:")
    st.stop()

if not items:
    st.info("Chưa có hoạt động nào trong khoảng thời gian này.", icon=":material/history:")
    st.stop()

co_mat = [k for k in HANH_DONG_VI if any(x["hanh_dong"] == k for x in items)]
chon = st.pills("Loại hoạt động", co_mat, selection_mode="multi", default=co_mat,
                format_func=lambda k: f"{HANH_DONG_VI[k][1]} {HANH_DONG_VI[k][0]}",
                key="audit_loai")
nguoi_co = sorted({x["ai"] or "(không rõ)" for x in items})
chon_nguoi = (st.multiselect("Người thực hiện", nguoi_co, key="audit_nguoi",
                             placeholder="Tất cả mọi người")
              if la_quan_tri and len(nguoi_co) > 1 else [])

tim = (tu_khoa or "").strip().casefold()
loc = [x for x in items
       if x["hanh_dong"] in (chon or [])
       and (not chon_nguoi or (x["ai"] or "(không rõ)") in chon_nguoi)
       and (not tim or tim in (x["ai"] or "").casefold() or tim in (x["ma"] or "").casefold())]

# --- So lieu nhanh -------------------------------------------------------
def _dem(*ma: str) -> int:
    return sum(1 for x in loc if x["hanh_dong"] in ma)


with st.container(horizontal=True):
    st.metric("Hoạt động", len(loc), border=True)
    st.metric("Thẻ đã quét", sum((x.get("chi_tiet") or {}).get("so_anh", 0)
                                 for x in loc if x["hanh_dong"] == "quet_the"), border=True)
    st.metric("Hồ sơ lưu / sửa", _dem("luu_ho_so", "sua_ho_so"), border=True)
    st.metric("Lần xuất dữ liệu", _dem("xuat_du_lieu"), border=True)
    st.metric("Đăng nhập thất bại", _dem("dang_nhap_that_bai"), border=True,
              help="Nhiều lần liên tiếp vào cùng một tài khoản là dấu hiệu dò mật khẩu.")

if _dem("dang_nhap_that_bai") >= 5:
    st.warning("Có từ 5 lần đăng nhập thất bại trở lên trong khoảng này. "
               "Kiểm tra cột **Người thực hiện** để xem tài khoản nào bị nhắm tới.",
               icon=":material/shield:")

if not loc:
    st.info("Không có hoạt động nào khớp bộ lọc.", icon=":material/filter_alt_off:")
    st.stop()

# --- Hoat dong theo ngay -------------------------------------------------
dem_ngay: dict[tuple[str, str], int] = {}
for x in loc:
    luc = _gio_dia_phuong(x["luc"])
    if luc:
        khoa = (luc.date().isoformat(), _ten(x["hanh_dong"]))
        dem_ngay[khoa] = dem_ngay.get(khoa, 0) + 1
if dem_ngay:
    st.subheader("Hoạt động theo ngày")
    st.bar_chart([{"Ngày": n, "Hoạt động": h, "Số lần": c} for (n, h), c in sorted(dem_ngay.items())],
                 x="Ngày", y="Số lần", color="Hoạt động", height=260)

# --- Bang chi tiet -------------------------------------------------------
st.subheader("Chi tiết")
st.caption("Bấm vào một dòng để xem đầy đủ.")
dong = []
for x in loc:
    luc = _gio_dia_phuong(x["luc"])
    dong.append({
        "Thời gian": luc.strftime("%d/%m/%Y %H:%M:%S") if luc else x["luc"],
        "Người thực hiện": x["ai"] or "(không rõ)",
        "Hoạt động": _ten(x["hanh_dong"]),
        "Đối tượng": _doi_tuong(x),
        "Chi tiết": _mo_ta(x),
        "IP": x.get("ip") or "",
        "Thiết bị": _thiet_bi(x.get("thiet_bi")),
    })
chon = st.dataframe(dong, hide_index=True, width="stretch", on_select="rerun",
                    selection_mode="single-row", key=f"audit-bang:{len(dong)}:{loc[0]['luc']}",
                    column_config={"Chi tiết": st.column_config.TextColumn(width="large")})

if chon.selection.rows:
    x = loc[chon.selection.rows[0]]
    luc = _gio_dia_phuong(x["luc"])
    icon = HANH_DONG_VI.get(x["hanh_dong"], ("", ":material/info:"))[1]
    with st.container(border=True):
        st.markdown(f"#### {icon} {_ten(x['hanh_dong'])}")
        bang = [
            ("Thời gian", luc.strftime("%H:%M:%S, %d/%m/%Y") + f" ({luc.tzname() or 'giờ máy'})" if luc else x["luc"]),
            ("Người thực hiện", x["ai"] or "(không rõ)"),
            ("Đối tượng", _doi_tuong(x) or "—"),
            ("Mã đối tượng", x.get("ma") or "—"),
            ("Địa chỉ IP", x.get("ip") or "(không ghi nhận)"),
            ("Thiết bị", _thiet_bi(x.get("thiet_bi")) or "(không ghi nhận)"),
        ]
        bang += [("Chi tiết", y) for y in _cac_dong(x)] or [("Chi tiết", "—")]
        st.table({"Mục": [a for a, _ in bang], "Nội dung": [b for _, b in bang]})
        if x.get("thiet_bi"):
            st.caption(f"Trình duyệt đầy đủ: `{x['thiet_bi']}`")
        dt = x.get("doi_tuong") or {}
        if dt.get("con") and x.get("loai") == "ho_so":
            if st.button("Mở hồ sơ", icon=":material/contacts:", key="audit-mo-hs"):
                st.session_state.selected_contact_id = x["ma"]
                st.switch_page("app_pages/contacts.py")
        elif dt.get("con") and x.get("loai") == "ban_quet":
            if st.button("Mở bản quét", icon=":material/fact_check:", key="audit-mo-bq"):
                st.session_state.current_scan_id = x["ma"]
                st.session_state.pop("scan_result", None)
                st.session_state.pop("scan_poll", None)
                st.switch_page("app_pages/review.py")
        elif dt and not dt.get("con"):
            st.caption("Đối tượng này đã bị xoá. Nhật ký vẫn giữ dòng này, nhưng không giữ "
                       "dữ liệu cá nhân của đối tượng.")
        with st.expander("Dữ liệu gốc của dòng nhật ký"):
            st.json(x)


def _csv(rows: list[dict]) -> bytes:
    ra = io.StringIO(newline="")
    viet = csv.DictWriter(ra, fieldnames=list(rows[0]))
    viet.writeheader()
    viet.writerows(rows)
    return ra.getvalue().encode("utf-8-sig")   # BOM de Excel doc dung tieng Viet


st.download_button("Tải nhật ký (CSV)", _csv(dong), file_name=f"nhat-ky-{date.today()}.csv",
                   mime="text/csv", icon=":material/download:")


# --------------------------------------------------------------------------
# Cap tai khoan (chi quan tri, Ngay 31) - chuyen tu trang Tong quan cu.
# --------------------------------------------------------------------------
#
# Khi `REGISTRATION_OPEN=false` thi trang dang nhap khong con o "Tao tai
# khoan"; quan tri van phai cap duoc tai khoan tren giao dien. Dung lai
# `/api/auth/register`: backend cho quan tri di qua cong da dong.
if la_quan_tri:
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
                    # khoan VUA TAO; nhan no se dang xuat quan tri.
                    st.success(f"Đã tạo tài khoản cho {email_moi}.",
                               icon=":material/check:")
        st.caption("Người được cấp nên đổi mật khẩu sau lần đăng nhập đầu. "
                   "Tài khoản tạo ở đây luôn là quyền thường, không phải quản trị.")
