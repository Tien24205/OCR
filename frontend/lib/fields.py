"""Multi-value form widgets; provenance is determined by the backend."""
import pandas as pd
import streamlit as st
from copy import deepcopy

FIELD_LABELS = {
    "full_names": "Họ tên", "company_names": "Công ty",
    "job_titles": "Chức danh", "departments": "Phòng ban",
    "emails": "Email", "phones": "Điện thoại", "websites": "Website", "addresses": "Địa chỉ",
}


def status_label(item: dict) -> str:
    """Nhãn trạng thái cho một dòng dữ liệu.

    Điểm tin cậy được gắn thêm khi backend có chấm điểm. Nó là **tín hiệu hỗ
    trợ** để người dùng biết nên soi kỹ dòng nào trước, không phải kết luận
    đúng/sai.
    """
    if item.get("source") == "user":
        return "Người dùng sửa"

    base = "🟡 Cần kiểm tra" if item.get("needs_review") else "🟢 Khớp OCR"
    score = item.get("confidence_score")
    if isinstance(score, (int, float)):
        return f"{base} · {score * 100:.0f}%"
    return base


def buffered_draft(draft: dict, fields: dict) -> dict:
    """Rebase widgets on a failed submission without changing the saved draft."""
    result = deepcopy(draft)
    for field in FIELD_LABELS:
        originals = {item.get("id", ""): item for item in draft["fields"].get(field, [])}
        result["fields"][field] = [{**originals.get(row.get("id", ""), {}), **row}
                                   for row in fields[field]]
    return result


def edit_fields(draft: dict, key_prefix: str) -> dict:
    fields = {}
    for field, label in FIELD_LABELS.items():
        st.markdown(f"**{label}**")
        items = draft["fields"].get(field, [])
        columns = ["id", "value", "status"]
        if field == "phones":
            columns += ["label", "extension"]
        rows = [{**{column: item.get(column, "") for column in columns},
                 "status": status_label(item)} for item in items]
        data = pd.DataFrame(rows, columns=columns, dtype=object)
        config = {"id": None, "value": st.column_config.TextColumn("Giá trị", max_chars=4096),
                  "status": "Bản đang lưu", "extension": st.column_config.TextColumn("Máy lẻ", max_chars=32),
                  "label": st.column_config.SelectboxColumn("Loại số", options=["", "tel", "fax", "mobile"])}
        edited = st.data_editor(data, key=f"{key_prefix}:{field}", num_rows="dynamic",
                                hide_index=True, disabled=["id", "status"], column_config=config,
                                width="stretch")
        if not items:
            st.badge("Chưa đọc được", color="gray")
            st.caption("Có thể thêm dòng nếu đọc được trên ảnh.")
        fields[field] = [{column: str(row.get(column) or "") for column in columns if column != "status"}
                         for row in edited.fillna("").to_dict("records")]
    return fields
