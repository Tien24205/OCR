# Báo cáo Ngày 4 — Nối OCR vào ứng dụng

**Ngày thực hiện:** 11/09/2026.  
**Phạm vi:** Ngày 4 trong [kế hoạch triển khai chi tiết](../2-ke-hoach/trien-khai-chi-tiet.md): OCR → trích xuất → grounding → chuẩn hóa sơ bộ → lưu bản quét → xem bản nháp.

## 1. Kết quả và trạng thái nghiệm thu

Đã nối luồng xử lý vào ứng dụng. Sau khi bấm **Gửi để nhận diện**, backend lưu ảnh và tạo scan, chạy tác vụ nền, frontend chuyển sang **Kiểm tra** để đợi và hiển thị kết quả. Bộ test tăng từ **46 lên 73**, tất cả pass.

**Hoàn thành phần triển khai Ngày 4; chưa đạt đầy đủ DoD với dịch vụ thật.** Hai ca Anh/Nhật đã chạy xuyên suốt bằng Streamlit AppTest → lớp API frontend → FastAPI TestClient → SQLite/tệp ảnh → worker → trang kết quả. Camera và nhà cung cấp được giả lập; các ca này xác nhận luồng phần mềm, không đo khả năng đọc ảnh của Vision/Gemini.

Kiểm tra cấu hình hiện tại chỉ đọc cờ hiện diện, không đọc/in giá trị khóa: `OCR_PROVIDER=mock`, `EXTRACTOR=heuristic`, chưa có file credentials Vision hợp lệ tại đường dẫn cấu hình, chưa có Gemini key/model. Chưa thực hiện lời gọi dịch vụ thật. Bộ ảnh trong `datasets` vẫn chưa có JPEG/PNG; hai fixture hiện có mang nguồn `mock:synthetic`.

## 2. Đã làm những gì và vì sao?

| Thành phần | Đã thực hiện | Lý do |
| --- | --- | --- |
| `backend/app/pipeline.py` | Tác vụ `BackgroundTasks`, mỗi tác vụ dùng DB session riêng; chỉ nhận scan `pending` bằng một lệnh cập nhật có điều kiện | Request upload trả về trước khi gọi OCR; tránh dùng session đã đóng và tránh chạy lại scan đã được nhận xử lý |
| Các bước xử lý | OCR → extract → ground → normalize → `ocr_done`; lỗi thành `failed` | Trạng thái có ý nghĩa thống nhất cho API và giao diện |
| Lưu bằng chứng | Commit `raw_text`, payload OCR, bbox, ngôn ngữ, thời điểm ngay sau OCR; commit `extraction_json` trước grounding | Lỗi bước sau không làm mất kết quả đã có; bản gốc vẫn chứa cả giá trị bị grounding loại |
| Thời gian | Lưu `ms_ocr`, `ms_extract` | Có số đo thời gian từng giai đoạn; thời gian OCR gồm các lần thử tạm thời nếu có |
| Khởi tạo provider | `services/providers.py` dùng chung cho pipeline và script spike; từ chối tên cấu hình sai | Không âm thầm chuyển sang mock khi cấu hình nhầm |
| Credentials Vision | Đường dẫn tương đối neo vào `backend`; truyền trực tiếp cho SDK | Đọc `.env` bằng Pydantic không đồng nghĩa SDK nhận được biến môi trường; cách chạy từ gốc repo và từ backend phải thống nhất |
| Giới hạn lời gọi | Vision timeout 20 giây/lần, tối đa 2 lần thử thêm cho lỗi tạm thời; Gemini timeout 30 giây, một lần gọi mỗi lượt xử lý | Có giới hạn chờ và tránh nhân số lần thử giữa SDK với worker |
| Lỗi provider | Thông báo xử lý phù hợp; không đưa nguyên văn lỗi SDK hoặc JSON sai ra API/log | Lỗi SDK có thể chứa nội dung yêu cầu; người dùng vẫn có mã lỗi để kiểm tra cấu hình |
| Chuẩn hóa sơ bộ | `services/normalize.py`: giữ mọi giá trị dạng danh sách, thêm `value_raw`, chỉ trim khoảng trắng đầu/cuối; `source=ocr` | Tạo bản nháp có cấu trúc mà vẫn giữ chữ Nhật, thứ tự tên và dữ liệu trước chuẩn hóa |
| Trang Kiểm tra | Ảnh đầu vào OCR, text thô, 8 nhóm trường, số đo và báo cáo grounding | Người dùng có thể đối chiếu kết quả với ảnh, thấy rõ trường trống hoặc cần kiểm tra |
| Giao diện trạng thái | Cảnh báo mock/regex; sidebar chỉ nói có cấu hình, chưa xác minh dịch vụ | Tránh nhầm phát lại fixture với OCR thật, hoặc có khóa với chắc chắn gọi được API |

Không bổ sung dependency hoặc bảng dữ liệu. `grounding_json` lưu kết quả đối chiếu và `draft`; chưa tạo `Contact`/`Organization` từ bản quét.

## 3. Hợp đồng API hiện có

| API | Hành vi |
| --- | --- |
| `POST /api/scans` | Multipart `file`; trả `201 {id, status: "pending"}` sau khi lưu; lập lịch worker |
| `GET /api/scans/{id}` | Trả trạng thái, ảnh tham chiếu, `raw_text`, `draft`, `grounding`, provider/model, thời gian, lỗi, số lần thử lại; không tìm thấy trả 404 |
| `POST /api/scans/{id}/retry` | Chỉ nhận scan `failed`, tối đa 3 lần do người dùng yêu cầu; trả 202; trạng thái không hợp lệ/hết lượt trả 409 |
| `GET /api/images/{image_ref}` | Chỉ nhận SHA-256 64 ký tự hex thường, yêu cầu ảnh đã thuộc một scan; trả đúng MIME và `private, no-store`; không tồn tại trả 404 |

Retry giữ nguyên kết quả OCR/trích xuất đã thành công và chạy tiếp bước còn thiếu. Nếu muốn nhận diện lại toàn bộ bằng provider/model khác, gửi ảnh thành scan mới; không ghi đè bằng chứng của scan cũ.

Frontend hỏi trạng thái mỗi giây bằng `st.fragment`. Khi hoàn tất hoặc lỗi API, dừng polling. Sau mốc 60 giây không tiếp tục lập yêu cầu tự động; một request GET đang chờ có timeout riêng 5 giây. **Kiểm tra lại** chỉ đọc trạng thái; **Thử xử lý lại** mới gửi POST retry. Hết thời gian chờ ở frontend không hủy worker.

## 4. Các lỗi đối chiếu Ngày 2 đã sửa trong phạm vi nối luồng

Các test hồi quy được thêm trước khi sửa grounding. Chúng tái hiện các lỗi sau:

| Trường hợp | Trước | Sau |
| --- | --- | --- |
| `taroyamada@example.com` so với `taro.yamada@example.com` | Dấu chấm bị xóa khi so khớp fuzzy; email khác có thể lọt | Giữ dấu câu khi so khớp email |
| Hai số ở hai dòng hoặc ngăn bởi `/` | Regex có thể ghép thành một token dài | Tách token, không ghép qua dòng hoặc dấu phân cách này |
| URL `/Team` và `/team`, URL có query/fragment | Chuẩn hóa có thể làm mất khác biệt ở đuôi URL | Giữ case của path, giữ query/fragment; không fuzzy URL |
| TEL/FAX và máy lẻ của hai số cùng dòng | Sao chép metadata từ model mà chưa kiểm tra gắn với số nào | Chỉ giữ nhãn gần số và máy lẻ ngay sau số khi đối chiếu được; phần không đạt để trống và gắn `needs_review` |
| `source_text` tự sinh | Có thể xuất hiện như bằng chứng dù không có trong OCR | Chỉ đưa sang bản nháp nếu là đoạn nguyên văn trong OCR; nếu không, bỏ và đánh dấu kiểm tra |

**Giới hạn còn lại:** `exact` chỉ là khớp với OCR, không bảo đảm đúng trên ảnh. `fuzzy` vẫn cần người kiểm tra. `unverified` là chưa đối chiếu được với OCR, không tự động kết luận “AI bịa”; muốn đo phải so với ảnh/nhãn chuẩn. Quy ước so khớp URL vẫn coi biến thể scheme/`www` tương đương theo thiết kế cũ, không xác minh chúng dẫn đến cùng website. Regex dự phòng vẫn chưa trích xuất được họ tên/địa chỉ và có thể nhầm chức danh với tên trên thẻ Nhật.

## 5. Kiểm thử và bằng chứng

Chạy từ gốc repo:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Kết quả cuối: **73 passed, 4 warnings**. Warnings là deprecation của bộ công cụ test, gồm httpx/TestClient, AnyIO và timeout khi dùng TestClient; không phải lỗi gọi Vision/Gemini. `git diff --check` không phát hiện lỗi whitespace. Không thay đổi dependency để xử lý các cảnh báo này trong Ngày 4.

| File test mới | Số ca | Kiểm tra |
| --- | ---: | --- |
| `backend/tests/unit/test_grounding_day4.py` | 5 | Email, điện thoại, URL, metadata và bằng chứng nguồn |
| `backend/tests/unit/test_providers_day4.py` | 5 | Đường dẫn credentials, truyền cấu hình SDK, timeout/schema Gemini, lỗi đầu ra, cấu hình sai; SDK được giả lập |
| `backend/tests/integration/test_pipeline_day4.py` | 11 | API/DB/worker, Anh/Nhật, giữ bằng chứng khi lỗi, retry, OCR rỗng, không lộ lỗi nội bộ, ảnh/scan không tồn tại; gồm 2 ca nối UI xuyên suốt |
| `frontend/tests/test_review_day4.py` | 6 | Hiển thị Anh/Nhật, dừng poll khi xong, đang chờ, timeout, mất mạng, retry |

Tổng **27 ca mới + 46 ca cũ = 73**. Test Ngày 3 được cập nhật để cô lập xử lý upload với worker và xác nhận chuyển trang sau gửi ảnh. Kiểm tra xuyên suốt dùng một ảnh PNG tạo trong test và câu trả lời provider có kiểm soát; không sử dụng ảnh đó để tính độ chính xác OCR.

## 6. Việc cần làm để đóng DoD Ngày 4

1. Chuẩn bị ít nhất **1 ảnh danh thiếp tiếng Anh và 1 ảnh tiếng Nhật thực tế**, đủ rõ để tự đối chiếu tên/công ty/email/điện thoại. Có thêm mẫu thiếu email/website để kiểm tra giữ trường trống. Bộ 40 ảnh của kế hoạch tổng vẫn cần tiếp tục thu thập.
2. Cấu hình `backend/.env`: `OCR_PROVIDER=google`, `GOOGLE_APPLICATION_CREDENTIALS=./secrets/gcp-sa.json`, `EXTRACTOR=gemini`, `GEMINI_API_KEY` và `GEMINI_MODEL`. Không gửi khóa vào báo cáo hoặc commit Git.
3. Chạy lệnh liệt kê model bằng tài khoản của mình; chọn model hỗ trợ ảnh và structured output, xác minh bằng một lời gọi thực tế. Danh sách model không tự chứng minh tài khoản gọi thành công mọi model trong danh sách.

```powershell
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py --list-models
```

4. Khởi động lại backend sau khi đổi `.env`. Để nghiệm thu, chạy một process backend và tránh sửa code/reload giữa lúc scan đang xử lý. Mở hai terminal tại gốc repo:

```powershell
# Terminal 1
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --app-dir backend

# Terminal 2
.\.venv\Scripts\python.exe -m streamlit run frontend\streamlit_app.py
```

5. Mở `http://localhost:8501`, lần lượt gửi hai ảnh; ở trang Kiểm tra xác nhận có tên/công ty/email/điện thoại đúng theo ảnh, chữ Nhật giữ nguyên, trường không có không tự điền. Thử cả thẻ thiếu trường. Chụp màn hình và ghi scan ID, provider/model, thời gian, các lỗi đọc thực tế vào bảng dưới.
6. Nếu lấy ảnh qua camera, kiểm tra chữ trong ảnh đầu vào OCR không bị lật; đây cũng là phần kiểm tra thiết bị còn lại của Ngày 3.

| Mẫu | Scan ID | Provider/model thật | Kết quả các trường / thời gian | Bằng chứng ảnh màn hình |
| --- | --- | --- | --- | --- |
| Tiếng Anh | Chưa chạy | Chưa có | Chưa đo | Chưa có |
| Tiếng Nhật | Chưa chạy | Chưa có | Chưa đo | Chưa có |
| Thẻ thiếu trường | Chưa chạy | Chưa có | Chưa đo | Chưa có |

Việc lưu scan thật trong ứng dụng không tự tạo bốn fixture OCR của DoD Ngày 2. Phần đó vẫn theo [phiếu nhà cung cấp](../4-kiem-chung/ocr-provider-notes.md); lỗi `--no-extract` và khả năng ghi đè fixture của script còn tồn đọng, chưa được sửa trong Ngày 4. Không dùng mock replay để thay cho bằng chứng OCR thật.

## 7. Kiến thức cần nắm để giải thích bài làm

| Kiến thức | Cần hiểu và giải thích được |
| --- | --- |
| FastAPI `BackgroundTasks` | Vì sao commit scan trước, trả HTTP rồi mới làm tác vụ; đây là tác vụ trong process, không phải hàng đợi bền vững |
| SQLAlchemy session/transaction | Vì sao worker có session riêng; vì sao lưu checkpoint sau OCR và extraction; đọc trạng thái không được gọi OCR lại |
| OCR và trích xuất có cấu trúc | Vision đọc chữ; Gemini gán vào trường theo schema; regex chỉ là phương án giới hạn |
| Grounding | So cả token email/điện thoại, giữ khác biệt URL; phân biệt “khớp OCR” với “đúng trên ảnh” |
| Unicode và dữ liệu gốc | Giữ Kanji/Kana, tên đa giá trị, thứ tự tên; `value_raw` khác bản hiển thị đã trim; không tự thêm +81 hoặc phiên âm |
| Streamlit | `session_state` giữ scan/result, `fragment` chỉ poll; `st.rerun()` chuyển sang màn hình kết quả; nút kiểm tra trạng thái khác nút retry |
| Kiểm thử | Test double giúp kiểm tra logic và tình huống lỗi; ảnh thật + nhãn chuẩn mới giúp đo chất lượng nhận diện |

## 8. Giới hạn và việc để đúng ngày sau

- `BackgroundTasks` không sống qua việc process bị tắt/crash. Chưa có hàng đợi bền vững hoặc tự phục hồi scan `pending/processing` bị gián đoạn. Sau sự cố đó, gửi ảnh thành scan mới để xử lý; không coi scan cũ đã hoàn tất. Không triển khai hạ tầng queue trong Ngày 4.
- Chuẩn hóa hiện chỉ phục vụ bản nháp: chưa đủ quy tắc điện thoại/email/URL/địa chỉ của Ngày 5. Form sửa và lưu thay đổi của người dùng chưa được triển khai.
- Tra cứu nguồn công khai thuộc Ngày 6; lưu/tìm kiếm/xuất hồ sơ và xử lý trùng thuộc Ngày 7.
- Bằng chứng từ Ngày 1–2 còn thiếu và kiểm tra camera vật lý Ngày 3 vẫn chưa được thay thế bằng các test Ngày 4.

## 9. Đoạn báo cáo có thể sử dụng

> Ngày 4 đã nối luồng OCR, trích xuất, grounding và bản nháp vào ứng dụng qua tác vụ nền. Kết quả OCR/trích xuất gốc được lưu riêng để giữ bằng chứng khi bước sau lỗi; giao diện xem ảnh, text và các trường có cấu trúc, có giới hạn polling và chức năng thử lại. Đã sửa các lỗi đối chiếu email, số điện thoại, URL và metadata ảnh hưởng trực tiếp đến bản nháp. Tổng cộng 73 test pass, gồm luồng giao diện tới backend với mẫu Anh/Nhật mô phỏng. Do chưa cấu hình Vision/Gemini và chưa có ảnh thực tế, chưa xác nhận đầy đủ DoD Ngày 4 trên dịch vụ thật.

Tham khảo: [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/), [Google Gen AI SDK](https://googleapis.github.io/python-genai/). Hành vi Streamlit đã đối chiếu tài liệu đi kèm phiên bản cài đặt 1.63.0.
