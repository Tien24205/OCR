"""Ngay 3: chup bang camera hoac tai anh len, xem truoc, gui toi backend."""

import streamlit as st

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

preview, actions = st.columns([2, 1])
with preview:
    st.image(data, caption="Ảnh sẽ được gửi đi", width="stretch")
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
            if exc.status == 404:
                st.warning(
                    "Backend chưa có `POST /api/scans`. Endpoint này được thêm "
                    "ở **Ngày 3** theo kế hoạch triển khai.",
                    icon=":material/construction:",
                )
            else:
                st.error(exc.message, icon=":material/error:")
        else:
            st.session_state.current_scan_id = scan["id"]
            st.switch_page("app_pages/review.py")
