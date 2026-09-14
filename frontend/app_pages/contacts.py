"""Searchable persistent contacts and portable exports."""
import hashlib
import streamlit as st
from lib import api
from lib.contacts import render_contact_detail

if st.session_state.pop("contact_saved_notice", False):
    st.success("Đã lưu thay đổi hồ sơ.")
query = st.text_input("Tìm theo tên, công ty, email hoặc số điện thoại",
                      key="contacts_query", placeholder="山田, Example Inc., jane@…", max_chars=500)
if st.session_state.get("contacts_previous_query") != query:
    st.session_state.contacts_previous_query = query
    st.session_state.contacts_page = 1
page = st.session_state.get("contacts_page", 1)
try:
    result = api.search_contacts(query, page=page)
except api.ApiError as exc:
    st.error(exc.message)
    st.stop()
items = result["items"]
st.caption(f"{result['total']} hồ sơ · Trang {page}")
if items:
    data = [{"Họ tên": x["name"], "Công ty": x["company"], "Email": x["emails"],
             "Điện thoại": x["phones"]} for x in items]
    identity = hashlib.sha256((query + str(page) + str([x["id"] for x in items])).encode()).hexdigest()[:16]
    selected = st.dataframe(data, width="stretch", hide_index=True, on_select="rerun",
                            selection_mode="single-row", key=f"contacts-table:{identity}")
    if selected.selection.rows:
        st.session_state.selected_contact_id = items[selected.selection.rows[0]]["id"]
else:
    st.info("Chưa có hồ sơ nào khớp.")
with st.container(horizontal=True):
    if st.button("Trang trước", disabled=page <= 1):
        st.session_state.contacts_page = page - 1
        st.rerun()
    if st.button("Trang sau", disabled=page * result["size"] >= result["total"]):
        st.session_state.contacts_page = page + 1
        st.rerun()
with st.expander("Xuất toàn bộ hồ sơ"):
    st.caption("JSON giữ đầy đủ dữ liệu và nguồn. CSV có BOM UTF-8; mỗi ô đa giá trị là một mảng JSON để giữ chữ Nhật và số 0 đầu số điện thoại. vCard mở trên điện thoại là danh bạ tự nhận.")
    if st.button("Chuẩn bị file xuất"):
        try:
            st.session_state.contact_exports = {fmt: api.export_contacts(fmt) for fmt in ("json", "csv", "vcf")}
        except api.ApiError as exc:
            st.error(exc.message)
    exports = st.session_state.get("contact_exports")
    if exports:
        st.caption("File là dữ liệu tại lần bấm Chuẩn bị gần nhất; bấm lại sau khi sửa hồ sơ.")
        st.download_button("Tải JSON", exports["json"], "contacts.json", "application/json", on_click="ignore")
        st.download_button("Tải CSV", exports["csv"], "contacts.csv", "text/csv", on_click="ignore")
        st.download_button("Tải vCard", exports["vcf"], "contacts.vcf", "text/vcard", on_click="ignore")
if contact_id := st.session_state.get("selected_contact_id"):
    render_contact_detail(contact_id)
