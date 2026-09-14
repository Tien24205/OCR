# Đối chiếu implementation_plan với code thực tế

> **Đính chính 14/09/2026 — mục IP-01 đã lỗi thời.**
> Tài liệu này viết lúc 20:35 ngày 11/09 và kết luận `AgenticOrchestrator` "chưa có `run()`".
> Nhưng `agent_orchestrator.py` được sửa lúc 20:51 và `agent_runner.py` được tạo lúc 21:00 cùng ngày.
> Kiểm chứng lại: `run()` có thật, được `pipeline.run_scan()` gọi khi `agent_enabled=true`, và
> `agent_runner.py` có nhánh rẽ thật (ảnh mờ thì dừng trước khi gọi provider, OCR điểm thấp thì thử
> lại với ảnh tăng tương phản, thiếu tên/công ty thì đọc lại bằng prompt khác, ngân sách retry có
> giới hạn toàn cục). **Mốc 12/09 đã đạt.** Các mục IP-02 trở đi chưa kiểm chứng lại.


Ngày kiểm tra: 11/09/2026. Kế hoạch tham chiếu: [implementation_plan.md](../2-ke-hoach/nang-cap-6-tieu-chi.md).

## 1. Kết luận về tiến độ

**Theo kế hoạch 10 ngày cũ:** đã triển khai chức năng tới Ngày 7, còn nghiệm thu camera/Excel và dịch vụ OCR/Gemini thật.

**Theo implementation_plan mới (12–29/09):** đang triển khai một phần Giai đoạn 1. Có mã thuộc các mốc 12, 13 và 14/09, nhưng **chưa mốc nào trong ba mốc đó đáp ứng đầy đủ yêu cầu**. Mốc chưa hoàn tất đầu tiên là 12/09 — điều phối có khả năng thay đổi luồng và tự sửa lỗi. Không thể kết luận đã xong Giai đoạn 1 hay đã làm xong ngày 14 chỉ dựa vào tên file.

Phần lõi đáp ứng khá đầy đủ chức năng danh thiếp → bản nháp → hồ sơ → tìm kiếm/xuất. Phần nâng cấp hiện chủ yếu bổ sung ghi log, điểm heuristic và endpoint batch; mức độ điều phối thông minh thấp hơn mô tả trong kế hoạch.

Lần kiểm tra này chỉ đối chiếu và ghi báo cáo, không hiện thực thêm các tính năng được đề xuất trong kế hoạch. Các mục “User Review Required/Open Questions” trong tài liệu được xem là nội dung đề xuất, không phải chỉ thị tự động triển khai.

## 2. Bằng chứng đã chạy

- Chạy lại toàn bộ suite: **201 passed, 5 warnings, 42,56 giây**. Warning thuộc TestClient/AnyIO và tham số timeout.
- Chạy probe riêng trên SQLite và ảnh trắng tổng hợp trong thư mục tạm; provider được giả lập, không gọi dịch vụ bên ngoài. Kết quả nằm tại [Ket-qua-doi-chieu-implementation-plan.json](ket-qua-doi-chieu-ke-hoach-nang-cap.json).
- Kiểm tra cấu hình chỉ đọc trạng thái hiện diện, không đọc/in giá trị khóa: OCR=`mock`, extractor=`heuristic`; chưa có OCR credentials, Gemini key hoặc model.
- Schema thực tế có **10 bảng**. Bộ dữ liệu có **0 ảnh**, hai fixture OCR mang nhãn `mock:synthetic`. Hai dòng labels tham chiếu ảnh chưa tồn tại, không tính thành hai ảnh mẫu đã thu thập.
- Bằng chứng restart đã có từ Ngày 7: [Kiem-tra-khoi-dong-lai-ngay-7.json](ket-qua-khoi-dong-lai-ngay-7.json). Không chạy lại phép thử restart trong lần đối chiếu này.

201 test đạt không chứng minh đã đáp ứng toàn bộ kế hoạch mới. Các probe dưới đây thể hiện yêu cầu chưa đạt dù suite hiện có vẫn xanh.

## 3. Những điểm chưa phù hợp cần xử lý trước

### IP-01 — Điều phối chưa thay đổi luồng theo chất lượng/kết quả (ưu tiên cao)

**Kế hoạch:** ảnh quá mờ thì yêu cầu chụp lại; extraction thiếu tên/công ty thì đổi prompt/context; bước sau có thể yêu cầu sửa bước trước. `AgentOrchestrator.run()` điều phối toàn bộ luồng.

**Code:** `AgenticOrchestrator` chỉ có ghi log và `execute_with_retry`; chưa có `run()`. `pipeline.run_scan()` vẫn tuần tự. Ảnh không đạt chỉ ghi `ESCALATE`, rồi đi tiếp OCR. Thiếu trường quan trọng chỉ làm giảm điểm và ghi quyết định, không kích hoạt lần extraction khác. Enrichment vẫn là luồng riêng do người dùng khởi chạy, chưa nằm trong điều phối. Chưa có cấu hình bật/tắt chế độ agent theo đề xuất backward compatibility.

**Probe:** ảnh trắng bị ghi `quality_action=escalate`, nhưng OCR vẫn được gọi 1 lần. Extraction thiếu cả `full_names` và `company_names` chỉ gọi 1 lần; scan kết thúc `ocr_done`.

**Vị trí:** `backend/app/services/agent_orchestrator.py:31`, `backend/app/pipeline.py:52`, `backend/app/pipeline.py:97`, `backend/app/pipeline.py:120`.

**Cần làm:** quy định rõ khi nào cảnh báo và tiếp tục, khi nào yêu cầu chụp lại, khi nào retry; điều khiển luồng thật theo quyết định đó. Không chỉ đổi tên class thành Agent hoặc thêm log.

### IP-02 — Smart retry hiện lặp cùng đầu vào (ưu tiên cao)

**Kế hoạch:** retry OCR với chỉnh contrast/rotation; retry extraction bằng prompt khác; ghi lý do từng lần, tối đa hai retry tự động.

**Code:** `_recognize` có tối đa 3 lần gọi cho lỗi transient, nhưng sử dụng cùng provider, ảnh và MIME. Retry extraction chỉ xảy ra khi ném `ExtractionError(retryable=True)`, gọi lại cùng hàm và cùng đầu vào. Không có nhánh retry dựa trên kết quả thiếu trường, confidence thấp hoặc số trường grounding loại. Log orchestrator bao ngoài `_recognize` cũng không ghi riêng từng lần retry OCR bên trong.

**Probe:** gây hai lỗi OCR transient rồi thành công: có 3 lần gọi, **bytes ảnh giống nhau ở cả ba lần**.

**Vị trí:** `backend/app/pipeline.py:23`, `backend/app/pipeline.py:65`, `backend/app/pipeline.py:97`.

**Cần làm:** retry phải có thay đổi đầu vào hoặc chiến lược cụ thể, ghi log từng lần và giữ bằng chứng từng lần thử. Giữ nguyên chốt chặn không tự retry lỗi cấu hình/quyền truy cập.

### IP-03 — Confidence từng trường bị mất trước khi tới UI (ưu tiên cao)

**Kế hoạch:** mỗi trường có `confidence_score`, `confidence_reasons[]` và được hiển thị trên trang Kiểm tra.

**Code:** pipeline tính điểm vào `grounding_json['draft']`. Nhưng `GET /api/scans/{id}` gọi `current_draft()`, hàm này dựng lại từ `grounding['fields']` hoặc lấy `reviewed_draft`, không đọc bản `draft` đã chấm điểm. UI kiểm tra `confidence_score` trên các item của bản nháp trả về nên nhánh hiển thị điểm từng trường không chạy với bản mới qua luồng này.

**Probe:** cùng một scan, trường email trong bản draft lưu ở DB **có score**, nhưng email trong `API response['draft']` **không có score**. Điểm tổng thể vẫn có trong `response['grounding']['confidence']`.

**Vị trí:** `backend/app/pipeline.py:112`, `backend/app/services/confidence.py:59`, `backend/app/services/drafts.py:40`, `backend/app/main.py:185`, `frontend/app_pages/review.py:169`.

**Cần làm:** thống nhất nguồn bản nháp đưa ra API và cách gắn điểm. Phân biệt điểm của kết quả máy gốc với giá trị người dùng đã sửa; không giữ điểm cũ cho một giá trị mới mà không giải thích.

### IP-04 — Điểm confidence chưa tổng hợp nhiều tín hiệu như kế hoạch (ưu tiên vừa)

**Đã có:** exact/fuzzy, kiểm tra sơ bộ email/độ dài số, trừ điểm khi thiếu tên/công ty.

**Chưa có:** sử dụng OCR confidence của Vision, đối chiếu email domain với website, consistency ngôn ngữ. `scan_langs` được truyền vào nhưng không được dùng để quyết định điểm. Điểm thành công của orchestrator đặt cứng 1.0, không phải độ tin cậy nội dung.

**Sai khác cụ thể:** tài liệu yêu cầu `unverified=0.0`; `evaluate_field()` hiện cho tên unverified **0.2**. Đây là sai khác của bộ tính điểm; không có nghĩa grounding hiện cho phép lưu mọi trường unverified, vì chốt grounding riêng vẫn loại dữ liệu không được kiểm chứng.

**Vị trí:** `backend/app/services/confidence.py:16`, `backend/app/services/agent_orchestrator.py:56`.

**Cần làm:** thống nhất công thức và bổ sung các tín hiệu đã cam kết; ghi rõ điểm heuristic chưa được hiệu chuẩn, không trình bày như xác suất OCR đúng.

### IP-05 — Batch có API nhưng chạy tuần tự; chưa có UI batch/Dashboard (ưu tiên vừa)

**Đã có:** `POST /api/scans/batch`, tối đa 10 ảnh, lưu scan từng ảnh và trả danh sách ID/lỗi. `GET /api/stats` trả tổng scans/contacts/organizations.

**Chưa đạt:** các scan trong một batch được đưa vào cùng `BackgroundTasks`; implementation đang `for task: await task()`, nên xử lý tuần tự trong batch. Chưa có giới hạn concurrency/worker song song theo đề xuất. `capture.py` vẫn tải một ảnh, gọi `create_scan`; chưa có frontend API wrapper/bộ theo dõi batch. Chưa có `dashboard.py`; navigation vẫn chỉ Quét thẻ, Kiểm tra, Hồ sơ. Stats chưa có biểu đồ theo thời gian, ngôn ngữ, confidence, decisions hoặc top công ty.

**Probe:** gửi trực tiếp hai ảnh qua handler với worker giả lập: tạo 2 scan, đăng ký 2 task và thực thi theo thứ tự gửi; đã đối chiếu vòng lặp của BackgroundTasks trong thư viện cài trên máy. Điều này chỉ kết luận tuần tự trong một batch, không kết luận các HTTP request khác nhau không thể chạy đồng thời.

**Vị trí:** `backend/app/main.py:137`, `backend/app/main.py:163`, `backend/app/main.py:81`, `frontend/app_pages/capture.py:30`, `frontend/streamlit_app.py:59`.

### IP-06 — Test của phần nâng cấp chưa phủ tiêu chí nghiệm thu (ưu tiên cao)

`test_agent_orchestrator.py` có 3 ca: thành công, lỗi rồi thành công, hết số lần retry. Các ca này kiểm tra wrapper gọi hàm, chưa kiểm tra ảnh mờ dẫn tới yêu cầu chụp lại, OCR preprocessing, extraction thiếu trường đổi prompt, confidence đi qua API/UI hoặc batch concurrency.

Các test E2E của phần lõi đã có trong `test_pipeline_day4.py`, `test_contacts_day7.py`, `test_contacts_ui_day7.py` và script restart; không đánh dấu “chưa có E2E” chỉ vì thiếu đúng tên `test_integration_e2e.py`. Tuy nhiên chưa có bằng chứng E2E dịch vụ thật trên 12 ảnh dev theo mốc 16/09.

## 4. Ma trận tiến độ theo từng mốc kế hoạch mới

| Mốc | Trạng thái thực tế | Đã có / còn thiếu |
| --- | --- | --- |
| 12/09 — Agentic architecture | **Một phần** | Có decision log, wrapper retry, đánh giá ảnh; chưa có điều phối theo kết quả, `run()` tổng hoặc self-correction |
| 13/09 — Confidence/smart retry | **Một phần** | Có điểm heuristic và UI tổng/log; thiếu multi-signal, đổi ảnh/prompt; điểm từng trường rơi khỏi API |
| 14/09 — Batch/Dashboard | **Một phần** | Có endpoint batch và 3 bộ đếm; chưa song song trong batch, UI batch và Dashboard |
| 15/09 — OCR thật/dữ liệu | **Chưa đạt** | Adapter SDK có sẵn; cấu hình còn mock/heuristic, chưa credentials; **0/20 ảnh theo kế hoạch mới** |
| 16/09 — E2E thật/fix | **Một phần nền tảng** | E2E giả lập và test lỗi đã có; chưa chạy Vision/Gemini trên 12 ảnh dev và lưu fixture thật |
| 17/09 — API/CRM/vCard | **Một phần nền tảng** | FastAPI có OpenAPI mặc định, JSON/CSV; chưa docs/example chuyên biệt, vCard, webhook. XLSX là tùy chọn vì kế hoạch cho phép giữ CSV |
| 18/09 — Đo chất lượng | **Chưa triển khai** | Chưa `evaluate.py`, chưa bộ 8 ảnh eval, chưa báo cáo precision/recall/F1/latency thật |
| 19/09 — Hàn/Trung, UX | **Một phần UX nền** | Có trạng thái tải, icon, form; cấu hình hints vẫn `ja,en`, chưa chứng cứ hỗ trợ/kiểm thử ko/zh theo kế hoạch |
| 20/09 — Kiến trúc/Roadmap | **Chưa có deliverable mới** | Chưa `AGENTIC_AI_ARCHITECTURE.md`, `ROADMAP.md`; tài liệu MVP cũ vẫn có |
| 21/09 — Demo/recording | **Chưa có bằng chứng bàn giao** | Chưa thấy video/screenshot trong `Document/demo/` theo yêu cầu |
| 22/09 — Đóng gói | **Một phần tài liệu nền** | Có README và suite; chưa bằng chứng clone sạch/demo thật và bộ tài liệu nâng cấp hoàn chỉnh |
| 23–24/09 — Auth/RBAC | **Chưa triển khai** | Chưa auth/JWT/users/ownership/login; phiên Streamlit riêng không thay thế phân quyền backend |
| 25/09 — Cloud storage | **Chưa triển khai** | Ảnh vẫn lưu local; chưa adapter cloud/presigned URL |
| 26–27/09 — PWA/auto-crop | **Chưa triển khai phần mới** | Có camera Streamlit/EXIF; chưa PWA hoặc auto-crop danh thiếp |
| 28/09 — Relationship graph | **Chưa triển khai** | Chưa trang graph hoặc thư viện tích hợp tương ứng |
| 29/09 — Re-test/Docker/handover | **Chưa có deliverable cuối** | Chưa Docker Compose và demo đầy đủ tính năng nâng cấp |

Chất lượng ảnh hiện dùng Pillow `FIND_EDGES` làm proxy, không phải Laplacian variance đúng như tên thuật toán trong kế hoạch. Chưa phát hiện nội dung xoay/lật; xử lý EXIF đã tồn tại ở bước nhận ảnh, là chức năng khác. Đây là phần triển khai cần ghi rõ giới hạn, không nên tính là đã hoàn tất phát hiện orientation.

## 5. Những chỗ bản kế hoạch cần cập nhật

1. Bối cảnh ghi “Ngày 1–6” nhưng đồng thời tick Ngày 7. Nên ghi: chức năng MVP tới Ngày 7, các mốc nghiệm thu thực tế còn chờ.
2. Schema “9 bảng” đã cũ: thực tế **10 bảng** do có ContactProfile.
3. “174+ test” không sai về bất đẳng thức nhưng chưa chính xác để báo cáo: lần này **201 pass**; cần ghi rõ test không chứng minh chất lượng AI thật.
4. Mốc 15/09 giảm dữ liệu từ 40 xuống **20 ảnh: 10 Anh + 10 Nhật; 6 dev + 4 eval mỗi ngôn ngữ**. Vì vậy đối chiếu kế hoạch này phải ghi **0/20**, không tiếp tục lấy 0/40 làm chỉ tiêu duy nhất. Giảm cỡ mẫu cũng làm kết luận chất lượng kém chắc chắn hơn.
5. Credentials được giả định có trước 13/09 nhưng lịch triển khai đặt cấu hình thật vào 15/09. Cần phân biệt hạn có credentials với ngày tích hợp/nghiệm thu, tránh coi là đã có khóa khi đến lịch chạy.
6. Kế hoạch ghi 22/09 bàn giao rồi 23–29/09 mở rộng: nên gọi 22/09 là bản ứng viên demo, 29/09 là bàn giao cuối để báo cáo không mâu thuẫn.
7. Các phần multi-user/graph/PWA đang được đặt trong mục đề xuất và câu hỏi ưu tiên. Lần kiểm tra này không suy diễn rằng toàn bộ phạm vi đó đã được chốt để triển khai.

## 6. Thứ tự công việc tiếp theo để bám kế hoạch

1. **Khép mốc 12–13/09:** chốt bảng quyết định; sửa luồng confidence API/UI; bổ sung đúng tín hiệu, đầu vào retry và test theo hành vi yêu cầu. Giữ bất biến bằng chứng OCR gốc khi có nhiều lần thử.
2. **Làm song song phần chuẩn bị 15/09:** credentials và 20 ảnh thật có nhãn, chia dev/eval trước khi điều chỉnh thuật toán. Đây là điều kiện để kiểm chứng, không thể thay bằng tăng số unit test.
3. **Khép 14/09:** batch có concurrency giới hạn, chọn nhiều ảnh/theo dõi trạng thái trên UI, Dashboard đủ dữ liệu và test.
4. **Nghiệm thu 15–16/09:** chạy dịch vụ thật trên 12 ảnh dev, ghi model/chi phí/lỗi, lưu fixture thật, đối chiếu Anh/Nhật và camera/Excel.
5. Sau đó mới chuyển tiếp API/vCard, đo chất lượng và các giai đoạn sau theo ưu tiên đã chốt. Không dùng nhãn “Agentic AI hoàn chỉnh”, “self-healing” hay “Enterprise” để thay cho bằng chứng chạy được.

**Câu mô tả tiến độ có thể dùng trong báo cáo:** “Dự án đã có MVP danh thiếp đến lưu/tìm kiếm/xuất hồ sơ, kiểm thử 201 ca đạt. Kế hoạch nâng cấp 12–29/09 đang ở Giai đoạn 1: mới triển khai một phần điều phối, chấm điểm và batch; còn thiếu self-correction, multi-signal confidence, batch UI/Dashboard và nghiệm thu OCR thật. Bộ dữ liệu hiện 0/20 theo mục tiêu đã giảm trong kế hoạch mới.”
