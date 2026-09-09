"""Ngay 7: danh sach ho so, tim kiem, trang chi tiet va xuat du lieu."""

import streamlit as st

from lib import api

query = st.text_input(
    "Tìm theo tên, công ty, email hoặc số điện thoại",
    key="contacts_query",
    placeholder="山田, Example Inc., jane@…",
)

try:
    result = api.search_contacts(query)
except api.ApiError as exc:
    if exc.status == 404:
        st.warning(
            "Backend chưa có `GET /api/contacts`. Endpoint này được thêm ở "
            "**Ngày 7** theo kế hoạch triển khai.",
            icon=":material/construction:",
        )
    else:
        st.error(exc.message, icon=":material/error:")
    st.stop()

items = result.get("items", [])
if not items:
    st.info("Chưa có hồ sơ nào khớp.", icon=":material/search_off:")
    st.stop()

st.dataframe(items, width="stretch", hide_index=True)
