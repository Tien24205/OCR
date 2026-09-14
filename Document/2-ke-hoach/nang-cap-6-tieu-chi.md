# Kế Hoạch Nâng Cấp Dự Án OCR Danh Thiếp — Hướng Đến 6 Tiêu Chí Đánh Giá

**Dự án**: Chuyển hóa danh thiếp thành hồ sơ đối tác chuẩn hóa  
**Workspace**: `c:\Users\dotie\OneDrive\Desktop\OCR`  
**Ngày lập**: 11/09/2026  
**Hạn chót**: 29/09/2026 (còn **18 ngày**)

---

## Bối Cảnh Hiện Tại

Dự án đã hoàn thành **Ngày 1–6/10** của kế hoạch gốc:
- ✅ Khung dự án FastAPI + Streamlit + SQLite (9 bảng)
- ✅ OCR Engine (Google Vision + Mock), Extraction (Gemini + Heuristic Regex)
- ✅ Grounding Engine chống bịa dữ liệu (18 test đối kháng)
- ✅ Chuẩn hóa theo trường, form đa giá trị, lưu bản nháp có revision
- ✅ Tra cứu doanh nghiệp (SSRF Safe Fetcher + Gemini Summarizer + Evidence Validator)
- ✅ Ngày 7: Lưu hồ sơ, tìm kiếm, phát hiện trùng, xuất JSON/CSV
- ✅ **174+ test** pass
- ⚠️ **Chưa nghiệm thu Vision/Gemini thật** — vẫn dùng mock fixtures
- ⚠️ **Chưa có ảnh mẫu** (0/40)
- ⚠️ Chưa đo chất lượng (Ngày 8–9–10 chưa làm)

---

## 6 Tiêu Chí Đánh Giá & Gap Analysis

| # | Tiêu Chí | Hiện Trạng | Gap Cần Bổ Sung |
|---|----------|-----------|-----------------|
| 1 | **Tính sáng tạo** — AI/Agentic AI | Có Gemini extraction + grounding chống hallucination | Cần thêm: **Agentic AI pipeline** (multi-agent xử lý thẻ), **intelligent routing**, **self-correcting pipeline**, batch processing thông minh |
| 2 | **Khả năng triển khai** — Demo chạy được | Có prototype nhưng chỉ chạy mock | Cần: **cấu hình OCR thật**, **demo video/recording**, **deploy instructions rõ ràng** |
| 3 | **Giá trị thực tiễn** — Giải quyết vấn đề thật | Luồng đầy đủ từ ảnh → hồ sơ | Cần: **batch scan** nhiều thẻ, **dashboard thống kê**, **tích hợp vCard/CRM export** |
| 4 | **Đóng góp chuyển đổi số** — Giá trị kinh tế/xã hội | Số hóa danh thiếp giấy → kho dữ liệu | Cần: **API mở cho hệ thống khác**, **multi-user**, **analytics & insight** |
| 5 | **Năng lực AI** — GenAI, Agentic AI | Gemini extraction + enrichment | Cần: **Agentic AI architecture** rõ ràng, **multi-step reasoning**, **confidence scoring**, **self-healing pipeline** |
| 6 | **Khả năng phát triển tiếp** — Tiềm năng sản phẩm | Kiến trúc clean nhưng chưa mở rộng | Cần: **plugin architecture**, **API docs**, **roadmap**, **thêm ngôn ngữ**, **mobile-ready** |

---

## User Review Required

> [!IMPORTANT]
> **Về credentials Google Cloud / Gemini**: Kế hoạch giả định bạn sẽ lấy được API key trước ngày 13/09 để chạy OCR thật. Nếu chưa có, cần cho biết để điều chỉnh kế hoạch (dùng mock + tài liệu giải thích).

> [!IMPORTANT]
> **Về scope Agentic AI**: Kế hoạch đề xuất xây dựng một **Agentic Pipeline** có khả năng tự quyết định bước tiếp theo (OCR → Extraction → Grounding → Enrichment) dựa trên kết quả từng bước. Đây là điểm sáng tạo chính. Bạn có muốn tập trung vào hướng này không, hay muốn ưu tiên feature khác?

> [!WARNING]
> **Thời gian dự án**: Kế hoạch ban đầu là 11 ngày (đến 22/09), nay được mở rộng thêm 1 tuần (đến 29/09). Kế hoạch chia thành 4 giai đoạn ưu tiên: **Must-Have** (ngày 12–16), **Should-Have** (ngày 17–19), **Nice-to-Have** (ngày 20–22), và **Advanced / Scaling** (ngày 23-29). Cắt giảm từ giai đoạn sau nếu bị chậm tiến độ.

---

## Open Questions

> [!IMPORTANT]
> 1. **Google Cloud credentials**: Bạn đã có tài khoản Google Cloud và Gemini API key chưa? Nếu chưa, khi nào dự kiến có?
> 2. **Ảnh mẫu**: Bạn có sẵn danh thiếp thật (Anh/Nhật) để chụp làm bộ test không? Hay cần dùng ảnh tổng hợp?
> 3. **Phạm vi mở rộng (23-29/09)**: Giai đoạn 4 sẽ tập trung vào Multi-user (Phân quyền) và Relationship Graph. Bạn có muốn ưu tiên phát triển bản Mobile (PWA) hơn không?

---

## Proposed Changes

Kế hoạch chia thành **4 giai đoạn**, từ nền tảng cốt lõi đến mở rộng quy mô:

---

### 🔴 Giai Đoạn 1: Must-Have (Ngày 12–16/09)
*Mục tiêu: Demo chạy được thật + Agentic AI Architecture*

---

#### Ngày 12/09 — Agentic AI Pipeline Architecture

**Mục tiêu**: Xây dựng **Agentic Pipeline** — hệ thống AI tự quyết định và tự điều chỉnh.

##### [NEW] [agent_orchestrator.py](../../backend/app/services/agent_orchestrator.py)

**Agent Orchestrator** — bộ điều phối agentic:
- Mỗi bước xử lý (OCR → Extract → Ground → Normalize → Enrich) là một **Agent** độc lập
- Orchestrator quyết định:
  - Ảnh mờ → yêu cầu re-capture thay vì ép OCR
  - OCR confidence thấp → thử OCR lại với preprocessing khác (contrast enhancement, rotation)
  - Extraction thiếu trường quan trọng → thử prompt khác hoặc bổ sung context
  - Grounding loại quá nhiều → cảnh báo người dùng thay vì im lặng
  - Enrichment không tìm thấy → đề xuất tìm kiếm thủ công với gợi ý query
- Ghi log mọi quyết định vào `agent_decisions` để giải thích (explainability)
- **Self-correcting**: nếu bước sau phát hiện bước trước sai, trigger retry có điều kiện

```python
# Kiến trúc:
class AgentDecision:
    agent: str          # "ocr_agent", "extract_agent", ...
    action: str         # "proceed", "retry", "escalate", "skip"  
    reason: str         # Giải thích tại sao quyết định như vậy
    confidence: float   # 0.0–1.0
    metadata: dict

class AgentOrchestrator:
    def run(scan_id, config) -> list[AgentDecision]:
        # 1. Image Quality Agent: đánh giá chất lượng ảnh
        # 2. OCR Agent: chọn provider phù hợp, retry nếu cần
        # 3. Extraction Agent: chọn extractor, validate output
        # 4. Grounding Agent: verify và quyết định threshold
        # 5. Enrichment Agent: tìm nguồn, cross-validate
```

##### [NEW] [image_quality.py](../../backend/app/services/image_quality.py)

**Image Quality Agent** — đánh giá chất lượng ảnh trước OCR:
- Kiểm tra độ sáng, contrast, blur (Laplacian variance)
- Phát hiện ảnh bị xoay/lật bất thường
- Đề xuất: chấp nhận / cảnh báo + tiếp tục / yêu cầu chụp lại
- Dùng Pillow (đã có) + thuật toán cơ bản, **không cần thêm dependency nặng**

##### [MODIFY] [pipeline.py](../../backend/app/pipeline.py)

Tích hợp Agent Orchestrator vào pipeline hiện tại:
- Thay `run_scan()` tuần tự bằng `AgentOrchestrator.run()` 
- Giữ backward compatibility (nếu không có agent config, chạy như cũ)
- Lưu `agent_decisions` vào `scan.grounding_json`

##### [NEW] [test_agent_orchestrator.py](../../backend/tests/unit/test_agent_orchestrator.py)

Test cho agent orchestrator: quyết định đúng khi ảnh mờ, OCR fail, extraction thiếu trường.

---

#### Ngày 13/09 — Confidence Scoring & Smart Retry

**Mục tiêu**: Hệ thống tự tin cậy và tự sửa lỗi.

##### [NEW] [confidence.py](../../backend/app/services/confidence.py)

**Multi-signal Confidence Scoring**:
- Tổng hợp nhiều tín hiệu để tính điểm tin cậy cho mỗi trường:
  - OCR confidence (nếu Vision API cung cấp)
  - Grounding verdict (exact=1.0, fuzzy=0.7, unverified=0.0)
  - Cross-field consistency (email domain khớp company website?)
  - Language detection consistency
- Output: mỗi trường có `confidence_score` và `confidence_reasons[]`
- Hiển thị trên UI bằng màu gradient thay vì chỉ 3 trạng thái

##### [MODIFY] [pipeline.py](../../backend/app/pipeline.py)

Thêm **Smart Retry Logic**:
- OCR fail → retry với image preprocessing (auto-rotate, contrast adjust)
- Extraction miss critical fields (name, company) → retry với alternative prompt
- Tối đa 2 retry tự động, ghi log lý do retry

##### [MODIFY] [review.py](../../frontend/app_pages/review.py)

Hiển thị confidence score và agent decisions trên trang Kiểm tra.

---

#### Ngày 14/09 — Batch Processing & Dashboard

**Mục tiêu**: Xử lý hàng loạt + bảng điều khiển tổng quan.

##### [MODIFY] [main.py](../../backend/app/main.py)

Thêm endpoint `POST /api/scans/batch`:
- Nhận nhiều ảnh trong một request (tối đa 10)
- Tạo scan cho từng ảnh, chạy song song trong background
- Trả về danh sách scan_id và trạng thái

##### [NEW] [dashboard.py](../../frontend/app_pages/dashboard.py)

**Dashboard** — trang tổng quan:
- Số lượng hồ sơ theo thời gian (chart)
- Phân bố ngôn ngữ (Anh/Nhật/khác)
- Tỷ lệ confidence trung bình
- Agent decisions breakdown (bao nhiêu retry, bao nhiêu escalate)
- Top doanh nghiệp có nhiều liên hệ nhất
- Dùng `st.metric`, `st.bar_chart` — không cần thêm thư viện

##### [MODIFY] [streamlit_app.py](../../frontend/streamlit_app.py)

Thêm trang Dashboard vào navigation.

---

#### Ngày 15/09 — OCR Thật & Ảnh Mẫu

**Mục tiêu**: Chạy pipeline thật, không còn mock.

##### Cấu hình Google Cloud + Gemini

1. Đăng ký / kích hoạt Google Cloud Vision API
2. Tạo service account, tải JSON key
3. Lấy Gemini API key từ Google AI Studio
4. Cấu hình `backend/.env`:
   ```
   OCR_PROVIDER=google
   EXTRACTOR=gemini
   GOOGLE_APPLICATION_CREDENTIALS=secrets/gcp-sa.json
   GEMINI_API_KEY=...
   GEMINI_MODEL=...
   ```

##### Thu thập ảnh mẫu

- Tối thiểu 10 ảnh tiếng Anh + 10 ảnh tiếng Nhật (giảm từ 20+20 do thời gian)
- Chia: 6 dev + 4 eval mỗi ngôn ngữ
- Gán nhãn trong `datasets/labels.jsonl`

##### [MODIFY] [ocr-provider-notes.md](../4-kiem-chung/ocr-provider-notes.md)

Điền kết quả chạy thật: model, kết quả, chi phí, giới hạn.

---

#### Ngày 16/09 — Kiểm Thử Tích Hợp & Fix Bugs

**Mục tiêu**: Luồng chính ổn định end-to-end.

##### Chạy pipeline thật trên ảnh mẫu dev

- Chạy `try_ocr.py` trên 12 ảnh dev (6 Anh + 6 Nhật)
- Fix các lỗi phát sinh khi chạy Vision/Gemini thật
- Lưu fixture thật cho test

##### [NEW] [test_integration_e2e.py](../../backend/tests/integration/test_integration_e2e.py)

End-to-end test: upload → OCR → extract → ground → draft → save contact.

##### Fix bugs & edge cases

- Camera permission denied → fallback UI
- Ảnh mờ/nghiêng → agent cảnh báo
- Unicode encoding issues trên Windows terminal
- Concurrent scan processing

---

### 🟡 Giai Đoạn 2: Should-Have (Ngày 17–19/09)
*Mục tiêu: Giá trị thực tiễn + Chuyển đổi số*

---

#### Ngày 17/09 — API Mở & Tích Hợp CRM

**Mục tiêu**: Mở API cho hệ thống bên ngoài, xuất vCard.

##### [NEW] [api_docs.py](../../backend/app/api_docs.py)

Bổ sung OpenAPI documentation:
- Mô tả chi tiết từng endpoint
- Request/Response examples
- Error codes reference
- Authentication notes (cho tương lai)

##### [MODIFY] [contact_routes.py](../../backend/app/contact_routes.py)

Thêm export formats:
- **vCard 3.0** export (`.vcf`) — import trực tiếp vào điện thoại/Outlook
- **Excel** export (`.xlsx`) — nếu openpyxl đã có, hoặc giữ CSV

##### [NEW] [webhook.py](../../backend/app/webhook.py)

**Webhook** — thông báo khi hoàn tất scan:
- Đăng ký URL callback
- POST kết quả khi scan hoàn tất → tích hợp CRM/ERP bên ngoài
- Retry logic cho webhook delivery

---

#### Ngày 18/09 — Đo Chất Lượng & Báo Cáo

**Mục tiêu**: Bằng chứng chất lượng AI.

##### [NEW] [evaluate.py](../../backend/scripts/evaluate.py)

Script đo chất lượng tự động:
- Chạy pipeline trên bộ eval (4 Anh + 4 Nhật)
- So sánh từng trường với nhãn chuẩn
- Tạo báo cáo:
  - Precision / Recall / F1 theo trường
  - Theo ngôn ngữ
  - Tỷ lệ hallucination (grounding loại)
  - Thời gian xử lý trung bình

##### [NEW] [Bao-cao-chat-luong.md](../../Document/3-bao-cao/chat-luong.md)

Báo cáo chất lượng:
- Kết quả đo trên bộ eval
- So sánh Gemini vs Heuristic
- Phân tích lỗi thường gặp
- Đề xuất cải thiện

---

#### Ngày 19/09 — Multi-Language & UX Polish

**Mục tiêu**: Mở rộng ngôn ngữ + UI chuyên nghiệp.

##### [MODIFY] [gemini.py](../../backend/app/services/extract/gemini.py)

Thêm hỗ trợ tiếng Hàn (`ko`) và tiếng Trung (`zh`):
- Bổ sung language hints cho Vision API
- Mở rộng extraction prompt cho 4 ngôn ngữ
- Cập nhật grounding rules cho CJK characters

##### UI Polish cho Streamlit

- Thêm emoji/icon cho các trạng thái
- Cải thiện responsive layout
- Thêm tooltips giải thích agent decisions
- Loading states mượt hơn
- Dark mode friendly

---

### 🟢 Giai Đoạn 3: Nice-to-Have (Ngày 20–22/09)
*Mục tiêu: Hoàn thiện tài liệu + Demo ấn tượng*

---

#### Ngày 20/09 — Tài Liệu Agentic AI & Kiến Trúc

##### [NEW] [AGENTIC_AI_ARCHITECTURE.md](../../Document/kien-truc-agentic.md)

Tài liệu chuyên đề về kiến trúc Agentic AI:
- Giải thích Multi-Agent Pipeline
- Mô hình quyết định (Decision Model) của từng Agent
- Self-correcting mechanisms
- Grounding as Safety Layer
- So sánh với single-pass pipeline truyền thống
- Diagram kiến trúc (Mermaid)
- Hướng phát triển: thêm Agent cho translation, duplicate resolution

##### [NEW] [ROADMAP.md](../../Document/roadmap.md)

Roadmap phát triển sản phẩm:
- **v1.0** (hiện tại): MVP Anh/Nhật, single user
- **v1.5**: +Hàn/Trung, batch processing, API mở
- **v2.0**: Multi-user, authentication, cloud deployment
- **v3.0**: Mobile app (React Native), real-time translation
- **v4.0**: Full CRM integration, AI-powered relationship mapping

---

#### Ngày 21/09 — Demo Preparation & Recording

##### Chuẩn bị demo 7–10 phút

1. **Mở đầu** (1 phút): Vấn đề thực tế + Giải pháp Agentic AI
2. **Live demo** (4 phút):
   - Chụp/tải thẻ tiếng Anh → xem agent quyết định → kết quả
   - Tải thẻ tiếng Nhật → grounding loại dữ liệu bịa → sửa + lưu
   - Tra cứu doanh nghiệp có nguồn → duyệt
   - Dashboard tổng quan
   - Xuất vCard / JSON
3. **Kiến trúc** (2 phút): Giải thích Agentic Pipeline, Grounding, Confidence
4. **Kết quả kiểm thử** (1 phút): Bảng đo chất lượng, số test pass
5. **Roadmap** (1 phút): Hướng phát triển tiếp

##### Quay recording demo (browser recording)

- Quay video demo trọn luồng
- Screenshot các màn hình chính
- Lưu vào `Document/demo/`

---

#### Ngày 22/09 — Đóng Gói & Bàn Giao

##### [MODIFY] [README.md](../../README.md)

Cập nhật README hoàn chỉnh:
- Tổng quan dự án và Agentic AI approach
- Hướng dẫn cài đặt chi tiết
- Cấu hình và chạy
- Kiểm thử
- Kết quả đo chất lượng
- Kiến trúc và Roadmap
- Screenshots

##### Final verification

1. Clone repo mới → cài đặt → chạy → verify
2. Chạy toàn bộ test suite → tất cả pass
3. Demo trọn luồng trên môi trường sạch
4. Kiểm tra không rò rỉ credentials

---

### 🟣 Giai Đoạn 4: Advanced & Scaling (Ngày 23–29/09)
*Mục tiêu: Đưa dự án từ Prototype lên cấp độ Enterprise (Chuyển đổi số thực sự)*

---

#### Ngày 23–24/09 — Authentication & Multi-user (RBAC)

**Mục tiêu**: Hỗ trợ nhiều người dùng trong doanh nghiệp.

##### [NEW] [auth.py](../../backend/app/auth.py)
- Thêm JWT Authentication
- Role-based Access Control (Admin, User)
- Cập nhật database: bảng `users`, link `scans` và `contacts` tới người tạo.
- Hỗ trợ User A chỉ xem được contact của User A (hoặc share toàn công ty).

##### [MODIFY] Streamlit App
- Thêm trang Login / Đăng ký.
- Yêu cầu đăng nhập trước khi dùng ứng dụng.

#### Ngày 25/09 — Cloud Storage & Scale

**Mục tiêu**: Không phụ thuộc vào local filesystem, chuẩn bị cho deploy thật.

##### [NEW] [storage.py](../../backend/app/services/storage.py)
- Tích hợp Cloud Storage (Google Cloud Storage hoặc AWS S3) để lưu trữ ảnh bản quét.
- Cập nhật luồng upload và phục vụ ảnh tĩnh qua presigned URL thay vì đọc file local.

#### Ngày 26–27/09 — Tối Ưu UX: Mobile PWA & Camera Native

**Mục tiêu**: Trải nghiệm quét danh thiếp trên điện thoại như một app Native.

##### [MODIFY] [app_pages/capture.py](../../frontend/app_pages/capture.py)
- Refactor giao diện Capture bằng HTML/JS custom component (nếu Streamlit webcam không đủ mượt) hoặc PWA manifest để cài đặt lên Home Screen điện thoại (iOS/Android).
- Tích hợp auto-crop (tự động nhận diện khung danh thiếp trên UI).

#### Ngày 28/09 — Trí tuệ mạng lưới (Relationship Graph)

**Mục tiêu**: Sáng tạo & Năng lực AI (Khả năng phát triển tiếp).

##### [NEW] [graph.py](../../frontend/app_pages/graph.py)
- Vẽ biểu đồ mạng lưới (Network Graph) thể hiện quan hệ:
  - User <-> Contacts
  - Contact <-> Organizations (nhiều liên hệ cùng một công ty)
  - Sử dụng thư viện `streamlit-agraph` hoặc `pyvis`.

#### Ngày 29/09 — End-to-End Re-Test & Final Handover

**Mục tiêu**: Chốt sổ toàn bộ dự án.

- Kiểm thử hồi quy toàn bộ hệ thống (Regression Test).
- Cập nhật demo video bao gồm tính năng đăng nhập và đồ thị.
- Đóng gói Docker image (`docker-compose.yml`) cho backend và frontend.

---

## Tóm Tắt: Mapping Tiêu Chí → Deliverables

| Tiêu Chí | Deliverables Chính | Ngày |
|----------|-------------------|------|
| 1. **Sáng tạo** | Agent Orchestrator, Relationship Graph | 12–13, 28 |
| 2. **Triển khai thực tế** | OCR thật, Docker Compose, Cloud Storage | 15, 25, 29 |
| 3. **Giá trị thực tiễn** | Batch processing, Mobile PWA UX, vCard export | 14, 17, 26-27 |
| 4. **Chuyển đổi số** | Multi-user & RBAC, Webhook | 17, 23-24 |
| 5. **Năng lực AI** | Confidence Scoring, Multi-signal, Multi-language | 13, 19 |
| 6. **Phát triển tiếp** | AGENTIC_AI_ARCHITECTURE.md, API mở | 17, 20 |

---

## Verification Plan

### Automated Tests
```powershell
# Chạy toàn bộ test suite
.\.venv\Scripts\python.exe -m pytest -v

# Chạy riêng agent orchestrator tests
.\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_agent_orchestrator.py -v

# Chạy evaluation script
.\.venv\Scripts\python.exe backend/scripts/evaluate.py
```

### Manual Verification
- Demo trọn luồng: ảnh Anh → hồ sơ + ảnh Nhật → hồ sơ
- Verify agent decisions hiển thị trên UI
- Verify batch upload hoạt động
- Verify dashboard số liệu đúng
- Verify vCard export mở được trên Outlook/iPhone
- Verify không rò rỉ credentials trong repo/logs
