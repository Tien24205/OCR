"""Ngay 3: chup bang camera hoac tai anh len, xem truoc, gui toi backend."""

from io import BytesIO

import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

from lib import api
from lib import autocrop

MAX_BYTES = 8 * 1024 * 1024
BATCH_MAX = 10

TRANG_THAI_VI = {
    "pending": "đang chờ",
    "processing": "đang nhận diện",
    "ocr_done": "xong — mở để kiểm tra",
    "committed": "đã lưu thành hồ sơ",
    "failed": "lỗi",
}


XONG = ("ocr_done", "failed", "committed")


@st.fragment(run_every="2s")
def _bang_trang_thai(items: list[dict]) -> None:
    """Trang thai tung anh, tu lam moi cho den khi ca lo xu ly xong.

    MOT loi goi cho ca lo, va chi hoi nhung ban quet CHUA xong.

    LOI DA SUA: ban dau ham nay goi `get_scan` cho TUNG anh, moi 2 giay. Ba
    anh la 90 loi goi mot phut, trong khi gioi han la 60 - nen chinh cai bang
    theo doi lam nguoi dung bi chan, va bang hien "Vuot qua 60 loi goi moi
    phut" thay cho trang thai. Mot lo 10 anh con te hon: 300 loi goi mot phut.

    Trang thai ket thuc thi khong quay lai duoc nua, nen nho lai la du - lo da
    xong hoan toan thi ham nay khong goi mang lan nao nua.
    """
    da_biet = st.session_state.setdefault("batch_status", {})
    can_hoi = [x["id"] for x in items
               if not x.get("error") and da_biet.get(x["id"]) not in XONG]
    loi_goi = None
    if can_hoi:
        try:
            for row in api.scans_status(can_hoi)["items"]:
                da_biet[row["id"]] = row["status"]
        except api.ApiError as exc:
            loi_goi = exc.message

    rows, con_chay = [], False
    for item in items:
        if item.get("error"):
            rows.append({"Tệp": item["filename"], "Trạng thái": item["error"]})
            continue
        trang_thai = da_biet.get(item["id"])
        con_chay = con_chay or trang_thai not in XONG
        rows.append({
            "Tệp": item["filename"],
            "Trạng thái": TRANG_THAI_VI.get(trang_thai, trang_thai or "đang chờ"),
        })
    st.dataframe(rows, width="stretch", hide_index=True)
    if loi_goi:
        st.caption(f"Chưa đọc được trạng thái: {loi_goi} Bảng sẽ thử lại.")
    if con_chay:
        st.caption("Bảng này tự làm mới. Nhận diện mỗi thẻ mất khoảng 7–20 giây; "
                   "bạn có thể sang trang khác, xử lý vẫn chạy ở backend.")


def render_batch() -> None:
    """Lo anh gan nhat - song qua moi lan chay lai va moi lan chuyen trang."""
    items = st.session_state.get("batch_items")
    if not items:
        return
    mo_duoc = [x for x in items if not x.get("error")]
    st.success(f"Đã nhận {len(mo_duoc)}/{len(items)} ảnh. Xử lý chạy nền.")
    _bang_trang_thai(items)

    if mo_duoc:
        ten = {x["filename"]: x["id"] for x in mo_duoc}
        with st.container(horizontal=True):
            chon = st.selectbox("Mở một bản quét", list(ten), key="batch_chon")
            if st.button("Mở trong trang Kiểm tra", icon=":material/fact_check:"):
                st.session_state.current_scan_id = ten[chon]
                st.session_state.pop("scan_result", None)
                st.session_state.pop("scan_poll", None)
                st.switch_page("app_pages/review.py")
        st.caption("Trang **Kiểm tra** tự chờ nếu thẻ chưa nhận diện xong. "
                   "Thẻ chỉ xuất hiện ở trang **Hồ sơ** sau khi bạn lưu.")
    if st.button("Xoá danh sách này", icon=":material/close:"):
        st.session_state.pop("batch_items", None)
        st.session_state.pop("batch_status", None)
        st.rerun()

st.caption(
    "Chụp hoặc tải ảnh danh thiếp. Mỗi ảnh chứa một thẻ, một mặt, bố cục ngang."
)

NGUON = ["Chụp bằng camera", "Tải ảnh lên"]
# Phien cu con nho che do "Tai hang loat" da bi gop: dua ve "Tai anh len"
# thay vi de segmented_control nhan mot gia tri khong con trong danh sach.
if st.session_state.get("capture_mode") not in (None, *NGUON):
    st.session_state.capture_mode = "Tải ảnh lên"

mode = st.segmented_control(
    "Nguồn ảnh",
    options=NGUON,
    default="Chụp bằng camera",
    key="capture_mode",
)

uploaded = None
if mode == "Chụp bằng camera":
    uploaded = st.camera_input("Đưa danh thiếp vào khung hình")
    st.caption(
        "Trình duyệt sẽ hỏi quyền dùng camera. Nếu bạn từ chối hoặc máy không "
        "có camera, chuyển sang **Tải ảnh lên**."
    )
else:
    st.caption(
        f"Gửi tối đa {BATCH_MAX} ảnh trong một lần. Ảnh hỏng không làm hỏng "
        "cả lô — mỗi ảnh có kết quả riêng."
    )
    files = st.file_uploader(
        "Chọn một hoặc nhiều ảnh JPEG/PNG",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
    ) or []
    # MOT anh: di duong xem truoc + cat vien ben duoi, roi mo trang Kiem tra.
    # NHIEU anh: gui ca lo va theo doi ngay tai day.
    if len(files) == 1:
        uploaded = files[0]

if mode != "Chụp bằng camera" and uploaded is None:
    # Cac phep kiem duoi day KHONG dung `st.stop()` truoc `render_batch()`:
    # dung som thi lo dang chay bien mat khoi man hinh dung luc can theo doi.
    oversized = [f.name for f in files if len(f.getvalue()) > MAX_BYTES]
    if len(files) > BATCH_MAX:
        st.error(f"Chọn tối đa {BATCH_MAX} ảnh mỗi lần. Đang chọn {len(files)}.")
    if oversized:
        st.error("Vượt quá 8 MB: " + ", ".join(oversized))
    if files:
        st.caption(f"{len(files)} ảnh · "
                   f"{sum(len(f.getvalue()) for f in files) / 1024:,.0f} KB")

    gui_duoc = bool(files) and len(files) <= BATCH_MAX and not oversized
    if gui_duoc and st.button(f"Gửi {len(files)} ảnh", type="primary", icon=":material/send:"):
        try:
            result = api.create_batch([
                (f.name or "card.jpg", f.getvalue(), f.type or "image/jpeg")
                for f in files
            ])
        except api.ApiError as exc:
            st.error(exc.message, icon=":material/error:")
        else:
            # LOI DA SUA: bang ket qua truoc day duoc ve NGAY TRONG khoi `if`
            # cua nut. Nut chi True o dung lan chay xu ly cu bam, nen chi can
            # doi sang trang khac - hay bat ky thao tac nao gay chay lai - la
            # ca lo bien mat khoi man hinh. Backend van xu ly xong va van luu,
            # nhung nguoi dung khong con duong nao mo lai nhung ban quet do,
            # nen tuong la mat het va phai quet lai tu dau. Giu danh sach trong
            # session_state thi no song qua moi lan chay lai va moi lan doi trang.
            st.session_state.batch_items = result.get("items", [])
            # Lo moi thi quen trang thai cua lo cu, khong thi anh dau
            # tien cua lo moi co the an theo trang thai mot ma trung.
            st.session_state.pop("batch_status", None)
            st.rerun()

    render_batch()
    st.stop()

if uploaded is None:
    st.stop()

data = uploaded.getvalue()

if len(data) > MAX_BYTES:
    st.error("Ảnh vượt quá 8 MB. Vui lòng chọn ảnh nhỏ hơn.")
    st.stop()

try:
    with Image.open(BytesIO(data)) as source:
        if source.format not in {"JPEG", "PNG"} or max(source.size) > 6000:
            st.error("Chọn ảnh JPEG/PNG có cạnh không vượt quá 6000 pixel.")
            st.stop()
        display_image = ImageOps.exif_transpose(source)
        display_image.load()
except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
    st.error("Không đọc được ảnh. Vui lòng chọn lại tệp JPEG hoặc PNG hợp lệ.")
    st.stop()

# --- Goi y cat vien (Ngay 27) --------------------------------------------
#
# `cache_data` khoa theo chinh bytes cua anh: Streamlit chay lai ca script
# sau MOI thao tac, va do vien la viec ton vai chuc mili giay tren anh lon.
# Khong nho lai thi moi lan go phim la mot lan do lai cung mot tam anh.
@st.cache_data(show_spinner=False, max_entries=8)
def _khung_cat(anh_bytes: bytes):
    return autocrop.goi_y_cat(anh_bytes)


khung = _khung_cat(data)
cat_vien = False
if khung:
    cat_vien = st.toggle(
        "Cắt viền tự động", value=True, key="capture_autocrop",
        help="Bỏ phần nền quanh thẻ để chữ chiếm nhiều điểm ảnh hơn. "
             "Tắt nếu khung cắt ăn vào thẻ.")

gui_data, gui_mime = data, uploaded.type or "image/jpeg"
if khung and cat_vien:
    da_cat, mime_cat = autocrop.cat(data, khung)
    # Anh cat ra ma van vuot han muc thi gui ban goc: 8 MB la gioi han cua
    # backend, va mot buoc lam dep khong duoc lam hong duong gui.
    if len(da_cat) <= MAX_BYTES:
        gui_data, gui_mime = da_cat, mime_cat
        with Image.open(BytesIO(gui_data)) as anh_cat:
            anh_cat.load()
            display_image = anh_cat.copy()
    else:
        cat_vien = False
        st.caption("Ảnh sau khi cắt vẫn vượt 8 MB nên giữ ảnh gốc.")

preview, actions = st.columns([2, 1])
with preview:
    chu_thich = ("Ảnh sẽ gửi — đã cắt viền" if khung and cat_vien
                 else "Ảnh xem trước theo chiều EXIF")
    st.image(display_image, caption=chu_thich, width="stretch")
with actions:
    st.caption(f"Dung lượng: {len(gui_data) / 1024:,.0f} KB")
    st.caption(f"Định dạng: `{gui_mime}`")
    if khung and cat_vien:
        st.caption("Đã bỏ phần nền quanh thẻ. Ảnh **gửi đi** chính là ảnh "
                   "bạn đang xem — không có bước sửa nào sau lưng bạn.")
    elif not khung:
        st.caption("Không tìm được viền thẻ rõ ràng nên gửi nguyên ảnh.")
    st.caption(
        "Chụp lại bằng nút của widget bên trái nếu ảnh nghiêng, mờ hoặc bị chói."
    )

    if st.button(
        "Gửi để nhận diện", type="primary", icon=":material/send:", width="stretch"
    ):
        try:
            scan = api.create_scan(
                uploaded.name or "card.jpg", gui_data, gui_mime
            )
        except api.ApiError as exc:
            st.error(exc.message, icon=":material/error:")
        else:
            st.session_state.current_scan_id = scan["id"]
            st.session_state.pop("scan_result", None)
            st.session_state.pop("scan_poll", None)
            st.success("Đã lưu ảnh. Bản quét đang chờ xử lý.")
            st.caption(f"Mã bản quét: {scan['id']}")
            st.switch_page("app_pages/review.py")
