"""Ngay 3: chup bang camera hoac tai anh len, xem truoc, gui toi backend."""

from io import BytesIO

import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

from lib import api

st.caption(
    "Chụp hoặc tải ảnh một danh thiếp. Mỗi lần xử lý một thẻ, một mặt, "
    "bố cục ngang."
)

mode = st.segmented_control(
    "Nguồn ảnh",
    options=["Chụp bằng camera", "Tải ảnh lên"],
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
    uploaded = st.file_uploader(
        "Chọn ảnh JPEG hoặc PNG", type=["jpg", "jpeg", "png"]
    )

if uploaded is None:
    st.stop()

data = uploaded.getvalue()

if len(data) > 8 * 1024 * 1024:
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

preview, actions = st.columns([2, 1])
with preview:
    st.image(display_image, caption="Ảnh xem trước theo chiều EXIF", width="stretch")
with actions:
    st.caption(f"Dung lượng: {len(data) / 1024:,.0f} KB")
    st.caption(f"Định dạng: `{uploaded.type or 'không rõ'}`")
    st.caption(
        "Chụp lại bằng nút của widget bên trái nếu ảnh nghiêng, mờ hoặc bị chói."
    )

    if st.button(
        "Gửi để nhận diện", type="primary", icon=":material/send:", width="stretch"
    ):
        try:
            scan = api.create_scan(
                uploaded.name or "card.jpg", data, uploaded.type or "image/jpeg"
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
