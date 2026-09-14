"""Ngay 3: chup bang camera hoac tai anh len, xem truoc, gui toi backend."""

from io import BytesIO

import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

from lib import api

MAX_BYTES = 8 * 1024 * 1024
BATCH_MAX = 10

st.caption(
    "Chụp hoặc tải ảnh danh thiếp. Mỗi ảnh chứa một thẻ, một mặt, bố cục ngang."
)

mode = st.segmented_control(
    "Nguồn ảnh",
    options=["Chụp bằng camera", "Tải ảnh lên", "Tải hàng loạt"],
    default="Chụp bằng camera",
    key="capture_mode",
)

# --- Che do hang loat: xu ly rieng roi dung han o day ---------------------
if mode == "Tải hàng loạt":
    st.caption(
        f"Gửi tối đa {BATCH_MAX} ảnh trong một lần. Ảnh hỏng không làm hỏng "
        "cả lô — mỗi ảnh có kết quả riêng."
    )
    files = st.file_uploader(
        "Chọn nhiều ảnh JPEG hoặc PNG",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
    )
    if not files:
        st.stop()

    if len(files) > BATCH_MAX:
        st.error(f"Chọn tối đa {BATCH_MAX} ảnh mỗi lần. Đang chọn {len(files)}.")
        st.stop()

    oversized = [f.name for f in files if len(f.getvalue()) > MAX_BYTES]
    if oversized:
        st.error("Vượt quá 8 MB: " + ", ".join(oversized))
        st.stop()

    st.caption(f"{len(files)} ảnh · "
               f"{sum(len(f.getvalue()) for f in files) / 1024:,.0f} KB")

    if st.button("Gửi cả lô", type="primary", icon=":material/send:"):
        try:
            result = api.create_batch([
                (f.name or "card.jpg", f.getvalue(), f.type or "image/jpeg")
                for f in files
            ])
        except api.ApiError as exc:
            st.error(exc.message, icon=":material/error:")
            st.stop()

        items = result.get("items", [])
        failed = [x for x in items if "error" in x]
        st.success(f"Đã nhận {result.get('queued', 0)}/{len(items)} ảnh. "
                   "Xử lý chạy nền.")
        if failed:
            st.warning("Không nhận được các ảnh sau — phần còn lại vẫn chạy:")
            for item in failed:
                st.caption(f"· **{item['filename']}** — {item['error']}")

        st.dataframe(
            [{"Tệp": x["filename"],
              "Trạng thái": x.get("error") or x.get("status", "")}
             for x in items],
            width="stretch", hide_index=True,
        )
        st.caption(
            "Xem kết quả từng thẻ ở trang **Hồ sơ** sau khi xử lý xong, hoặc "
            "theo dõi tổng quan ở trang **Tổng quan**."
        )
    st.stop()


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
