"""Ngay 28: mang luoi quan he giua nguoi dung, ho so va doanh nghiep.

VI SAO DUNG `st.graphviz_chart` CHU KHONG PHAI `streamlit-agraph`/`pyvis`:
ca hai goi kia deu la phu thuoc moi, con `st.graphviz_chart` co san trong
Streamlit va tu dat vi tri cac dinh o phia trinh duyet. Doi lai la do thi
khong bam vao duoc - o day khong mat gi, vi cau hoi ma trang nay tra loi
("cong ty nao co nhieu dau moi") doc duoc ngay tren hinh.
"""

import html

import streamlit as st

from lib import api

# Chan tren so ho so dua vao hinh. Tren muc nay thi hinh thanh mot dam chi
# roi: khong doc duoc gi, ma trinh duyet thi phai dat vi tri cho hang tram
# dinh moi lan chay lai script.
TOI_DA = 120

MAU_NGUOI_DUNG = "#ff4b4b"
MAU_CONG_TY = "#2b6cb0"
MAU_HO_SO = "#4a5568"
MAU_CHU = "#1a202c"


def _lay_ho_so() -> tuple[list[dict], int]:
    """Ho so cua nguoi dang dang nhap. Backend da loc theo chu so huu."""
    items, trang, tong = [], 1, 0
    while len(items) < TOI_DA:
        goi = api.search_contacts(q="", page=trang, size=100)
        tong = goi.get("total", 0)
        moi = goi.get("items", [])
        items.extend(moi)
        if len(moi) < 100:
            break
        trang += 1
    return items[:TOI_DA], tong


def _dinh(ma: str, nhan: str, mau: str, hinh: str = "box") -> str:
    """Mot dong DOT.

    HAI CHO PHAI CAN THAN, va chung khac nhau:

    `ma` la DINH DANH trong chuoi DOT. No PHAI do chinh trang nay sinh ra
    (`cty0`, `hs3`...), khong bao gio duoc ghep tu du lieu. Ten cong ty doc
    tu tam the bang OCR co the chua dau nhay kep; ghep thang vao thi no
    thoat ra khoi chuoi dinh danh va phan con lai bi doc nhu ma DOT - ca
    hinh hong, hoac te hon la ve ra nhung canh khong ai khai. Do la ly do
    `_ma_dinh()` ton tai.

    `nhan` la phan nguoi doc nhin thay, va no DUOC phep chua du lieu -
    nhung phai thoat: `html.escape` cho cac ky tu danh dau, roi doi not dau
    nhay kep con lai thanh nhay don, vi DOT dung nhay kep de bao chuoi.
    """
    an_toan = html.escape(nhan or "(không tên)", quote=True).replace('"', "'")
    return (f'  "{ma}" [label="{an_toan}", shape={hinh}, style="filled,rounded", '
            f'fillcolor="{mau}", fontcolor="{MAU_CHU}", fontname="Helvetica"];')


def _ma_dinh(tien_to: str, khoa: str, da_cap: dict[str, str]) -> str:
    """Dinh danh on dinh cho mot dinh, chi gom chu va so. Xem `_dinh()`."""
    if khoa not in da_cap:
        da_cap[khoa] = f"{tien_to}{len(da_cap)}"
    return da_cap[khoa]


st.caption("Mạng lưới đối tác: ai thuộc công ty nào, và công ty nào bạn đã có "
           "nhiều hơn một đầu mối.")

try:
    ho_so, tong = _lay_ho_so()
except api.ApiError as exc:
    st.error(exc.message, icon=":material/error:")
    st.stop()

if not ho_so:
    st.info("Chưa có hồ sơ nào. Quét một tấm thẻ rồi lưu, đồ thị sẽ hiện ở đây.",
            icon=":material/hub:")
    st.stop()

# --- Gom theo cong ty ------------------------------------------------------
theo_cong_ty: dict[str, list[dict]] = {}
for c in ho_so:
    theo_cong_ty.setdefault((c.get("company") or "").strip(), []).append(c)

nhieu_dau_moi = {ten: ds for ten, ds in theo_cong_ty.items()
                 if ten and len(ds) > 1}

# --- Bo loc ----------------------------------------------------------------
chi_nhieu = False
if nhieu_dau_moi:
    chi_nhieu = st.toggle(
        f"Chỉ hiện {len(nhieu_dau_moi)} công ty có nhiều đầu mối",
        value=len(ho_so) > 25,
        help="Đây thường là phần đáng nhìn: nhiều người cùng một công ty.")

hien = ({ten: ds for ten, ds in theo_cong_ty.items() if ten in nhieu_dau_moi}
        if chi_nhieu else theo_cong_ty)

# --- Dung chuoi DOT --------------------------------------------------------
nguoi = st.session_state.get("nguoi_dung") or {}
ten_toi = nguoi.get("display_name") or nguoi.get("email") or "Kho hồ sơ"

dong = [
    "digraph mang_luoi {",
    "  rankdir=LR;",
    "  bgcolor=transparent;",
    '  node [fontsize=11, margin="0.12,0.06"];',
    '  edge [color="#a0aec0", arrowsize=0.6];',
    _dinh("__toi__", ten_toi, MAU_NGUOI_DUNG, hinh="ellipse"),
]

ma_cty_theo_ten: dict[str, str] = {}
ma_hs_theo_id: dict[str, str] = {}

for ten_cty, ds in hien.items():
    ma_cty = _ma_dinh("cty", ten_cty, ma_cty_theo_ten)
    nhan_cty = ten_cty or "(chưa rõ công ty)"
    if len(ds) > 1:
        nhan_cty = f"{nhan_cty}\\n{len(ds)} đầu mối"
    dong.append(_dinh(ma_cty, nhan_cty, MAU_CONG_TY))
    dong.append(f'  "__toi__" -> "{ma_cty}";')
    for c in ds:
        ma_hs = _ma_dinh("hs", str(c.get("id")), ma_hs_theo_id)
        dong.append(_dinh(ma_hs, c.get("name") or "(không tên)", MAU_HO_SO))
        dong.append(f'  "{ma_cty}" -> "{ma_hs}";')

dong.append("}")
st.graphviz_chart("\n".join(dong), width="stretch")

# --- Doc gi tren hinh ------------------------------------------------------
a, b, c = st.columns(3)
a.metric("Hồ sơ trên đồ thị", len(ho_so))
b.metric("Công ty", len([t for t in theo_cong_ty if t]))
c.metric("Công ty nhiều đầu mối", len(nhieu_dau_moi))

if tong > len(ho_so):
    st.caption(f"Đang vẽ {len(ho_so)} hồ sơ mới nhất trên tổng số {tong}. "
               "Nhiều hơn thế thì hình thành một đám chỉ rối.")

if nhieu_dau_moi:
    with st.expander(f"{len(nhieu_dau_moi)} công ty có nhiều hơn một đầu mối"):
        for ten_cty, ds in sorted(nhieu_dau_moi.items(),
                                  key=lambda x: -len(x[1])):
            st.markdown(f"**{ten_cty}** — " +
                        ", ".join(x.get("name") or "(không tên)" for x in ds))
else:
    st.caption("Chưa có công ty nào xuất hiện hai lần. Khi có, chúng sẽ được "
               "gom lại ở đây.")
