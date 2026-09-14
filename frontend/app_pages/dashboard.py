"""Bảng điều khiển: tổng quan số liệu của kho hồ sơ."""

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


try:
    data = api.stats()
except api.ApiError as exc:
    st.error(exc.message, icon=":material/error:")
    st.stop()

totals = data["totals"]

with st.container(horizontal=True):
    st.metric("Bản quét", totals["scans"])
    st.metric("Hồ sơ đối tác", totals["contacts"])
    st.metric("Doanh nghiệp", totals["organizations"])
    st.metric("Thông tin tra cứu", totals["enrichments"])

if not totals["scans"]:
    st.info(
        "Chưa có bản quét nào. Sang trang **Quét thẻ** để bắt đầu.",
        icon=":material/photo_camera:",
    )
    st.stop()

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
