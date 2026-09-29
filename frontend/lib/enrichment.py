"""Research is separate from the saved card draft and never triggers OCR."""
import time
import streamlit as st
from lib import api

LABELS = {"industry": "Lĩnh vực", "company_size": "Quy mô", "products_services": "Sản phẩm / dịch vụ",
          "founded": "Thành lập", "headcount_asof": "Mốc thống kê nhân sự"}
STATUSES = {"verified": "Đã đối chiếu nguồn", "unverified": "Chưa xác minh đầy đủ",
            "conflicting": "Nguồn mâu thuẫn", "not_found": "Chưa tìm thấy"}
REASONS = {
    "NO_DOMAIN_ON_CARD": "Không tìm được website của doanh nghiệp. Kiểm tra lại tên, hoặc nhập website nếu bạn biết.",
    "SUMMARIZER_NOT_CONFIGURED": "Chưa cấu hình Gemini để trích xuất thông tin từ các trang đã tải.",
    "SUMMARY_FAILED": "Chưa trích xuất được thông tin từ website. Kiểm tra model, quyền và quota Gemini.",
    "IDENTITY_UNVERIFIED": "Chưa đối chiếu được danh tính doanh nghiệp với danh thiếp.",
    "NO_VERIFIABLE_CLAIMS": "Chưa có thông tin đáp ứng điều kiện dẫn nguồn.",
    "BLOCKED_ADDRESS": "Địa chỉ website không phải địa chỉ Internet công khai được phép truy cập.",
    "ROBOTS_DISALLOWED": "Website không cho phép ứng dụng tải trang này theo robots.txt.",
    "FETCH_FAILED": "Không tải được website trong thời gian cho phép.",
    "DNS_FAILED": "Không phân giải được tên miền website.",
}


@st.fragment(run_every="1s")
def poll_research(key: str):
    state = st.session_state[key]
    if time.monotonic() - state["started"] >= 60:
        state["poll_error"] = "Đã chờ 60 giây. Tác vụ có thể vẫn chạy; bấm Kiểm tra trạng thái để xem tiếp."
        st.rerun()
    try:
        job = api.get_research(state["job"]["organization_id"])
    except api.ApiError as exc:
        state["poll_error"] = exc.message
        st.rerun()
    state["job"] = job
    if job["status"] == "done":
        st.rerun()
    st.status("Đang tải và đối chiếu nguồn doanh nghiệp…", state="running")


def _o_nhap(scan: dict, key: str, nhan_nut: str) -> None:
    """O nhap ten / website doanh nghiep, dien san tu the."""
    fields = (scan.get("draft") or {}).get("fields") or {}
    ten_the = ((fields.get("company_names") or [{}])[0]).get("value", "")
    web_the = ((fields.get("websites") or [{}])[0]).get("value", "")
    with st.form(f"form:{key}:{nhan_nut}", border=False, enter_to_submit=True):
        with st.container(horizontal=True):
            ten = st.text_input("Tên doanh nghiệp", value=ten_the, max_chars=300,
                                placeholder="vd. Công ty TNHH ABC Logistics")
            web = st.text_input("Website (không bắt buộc)", value=web_the, max_chars=500,
                                placeholder="vd. abclogistics.vn")
        gui = st.form_submit_button(nhan_nut, type="primary", icon=":material/travel_explore:")
    st.caption("Không có website thì hệ thống tự tìm website chính thức theo tên. Mọi thông tin tìm được "
               "đều kèm nguồn và đoạn trích nguyên văn. Tên nhập ở đây chỉ dùng để tra cứu, không sửa dữ liệu trên thẻ.")
    if not gui:
        return
    if not ten.strip() and not web.strip():
        st.error("Nhập tên doanh nghiệp hoặc website để tra cứu.", icon=":material/error:")
        return
    try:
        job = api.start_enrichment(scan["id"], scan.get("draft_revision", 0), ten.strip(), web.strip())
    except api.ApiError as exc:
        st.error(exc.message, icon=":material/error:")
        return
    st.session_state[key] = {"job": job, "started": time.monotonic(), "poll_error": None}
    st.rerun()


def render_enrichment(scan: dict):
    if scan.get("status") not in {"ocr_done", "committed"}:
        return
    st.subheader("Thông tin doanh nghiệp từ website")
    st.caption("Kết quả web được giữ riêng với dữ liệu trên thẻ.")
    revision = scan.get("draft_revision", 0)
    key = f"research:{scan['id']}:{revision}"
    if key not in st.session_state and scan.get("enrichment"):
        st.session_state[key] = {"job": scan["enrichment"], "started": time.monotonic(), "poll_error": None}
    state = st.session_state.get(key)
    if not state:
        _o_nhap(scan, key, "Tra cứu doanh nghiệp")
        return
    job = state["job"]
    if job["status"] != "done":
        if state.get("poll_error"):
            st.warning(state["poll_error"])
            if st.button("Kiểm tra trạng thái", key=f"check:{key}"):
                state.update(started=time.monotonic(), poll_error=None)
                st.rerun()
        else:
            poll_research(key)
        return
    if job.get("reason"):
        st.info(REASONS.get(job["reason"], "Tra cứu chưa hoàn tất đầy đủ. Xem chi tiết lượt tra cứu bên dưới."))
        query = job.get("metadata", {}).get("manual_search_query")
        if query:
            st.caption("Gợi ý từ khóa để tự tìm và kiểm tra đúng doanh nghiệp:")
            st.text(query)
    st.caption("Đối chiếu nguồn xác nhận đoạn trích và giá trị có trong trang đã tải; vẫn cần kiểm tra đúng doanh nghiệp và ngữ nghĩa.")
    for item in job.get("enrichments", []):
        with st.container(border=True):
            st.markdown(f"**{LABELS.get(item['attribute'], item['attribute'])}**")
            st.caption(STATUSES[item["status"]])
            if item["status"] == "conflicting":
                st.caption("Chọn thông tin phù hợp; duyệt mục này sẽ bác bỏ lựa chọn mâu thuẫn đã duyệt cùng thuộc tính.")
            if item["attribute"] == "company_size":
                st.caption("Quy mô cần có đơn vị và mốc thời gian thống kê.")
            if item["value"] is None:
                st.text("Chưa tìm thấy thông tin có nguồn phù hợp.")
                continue
            st.text(item["value"])
            if item.get("source_url"):
                st.link_button("Mở nguồn", item["source_url"])
                st.text(item["source_url"])
                st.caption(item.get("source_title") or "")
            st.caption(f"Thời điểm tải: {item.get('fetched_at') or '—'}")
            st.text(item["evidence_snippet"])
            decision = item.get("decision", "pending")
            st.caption({"pending": "Chờ người dùng duyệt", "accepted": "Đã duyệt", "rejected": "Đã bác bỏ"}[decision])
            with st.container(horizontal=True):
                accept = st.button("Duyệt", key=f"accept:{item['id']}", disabled=decision == "accepted")
                reject = st.button("Bác bỏ", key=f"reject:{item['id']}", disabled=decision == "rejected")
            if accept or reject:
                try:
                    state["job"] = api.review_enrichment(item["id"], "accepted" if accept else "rejected")
                except api.ApiError as exc:
                    st.error(exc.message)
                else:
                    st.rerun()
    if job.get("attempts", 1) < 3 and st.button("Thử tra cứu lại", key=f"retry:{key}"):
        try:
            state["job"] = api.retry_enrichment(job["organization_id"])
        except api.ApiError as exc:
            st.error(exc.message)
        else:
            state.update(started=time.monotonic(), poll_error=None)
            st.rerun()
    if job.get("attempts", 1) < 3:
        with st.expander("Tra cứu với tên hoặc website khác", icon=":material/edit:"):
            _o_nhap(scan, key, "Tra cứu lại")
    with st.expander("Chi tiết lượt tra cứu"):
        st.caption(f"Lượt {job.get('attempts', 1)}/3 · Phiên bản bản nháp {job['draft_revision']}")
        st.json({"reason": job.get("reason"), "pages": job.get("pages", []), "metadata": job.get("metadata", {})})
