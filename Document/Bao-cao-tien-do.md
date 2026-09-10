# Báo cáo tiến độ — Ngày 1–2/10

**Dự án:** Chuyển hóa danh thiếp thành hồ sơ đối tác chuẩn hóa (Đề bài #2)
**Ngày lập:** 09/09/2026 · **Cập nhật:** 10/09/2026
**Giai đoạn:** Ngày 1 (khung dự án, thiết kế dữ liệu) và Ngày 2 (spike OCR)

Tài liệu liên quan: [đặc tả yêu cầu](Bai-2-business-card-yeu-cau-chuan-hoa.md) · [kế hoạch 10 ngày](Bai-2-noi-dung-va-ke-hoach-10-ngay.md) · [kế hoạch triển khai chi tiết](Bai-2-ke-hoach-trien-khai-chi-tiet.md)

---

## 1. Tóm tắt

**Ngày 1** đã xong phần kỹ thuật: khung backend, thiết kế cơ sở dữ liệu đầy đủ, khung frontend ba trang, bộ kiểm thử và công cụ quản lý dữ liệu mẫu.

**Ngày 2** đã dựng xong toàn bộ đường đi OCR — lớp trừu tượng nhà cung cấp, hai bộ trích xuất, chốt chặn chống bịa dữ liệu và script spike chạy độc lập. Đường ống chạy thông đầu-cuối trên ảnh tổng hợp.

| Chỉ số | Cuối Ngày 1 | Hiện tại |
| --- | --- | --- |
| Commit | 5 | 7 |
| File mã nguồn được theo dõi | 24 | 39 |
| Dòng Python | 1.229 | 2.654 |
| Bảng cơ sở dữ liệu | 8 | 8 |
| Test tự động | 9 | 27, tất cả pass |

*(Con số "~960 dòng" ở bản báo cáo trước đếm thiếu — lệnh PowerShell dùng khi đó bỏ qua dòng trống. Số đúng là 1.229.)*

**Hai điểm phải nói rõ:**

1. **Chưa có lời gọi OCR thật nào được thực hiện.** Chưa có tài khoản Google Cloud và Gemini. Mã nguồn đã sẵn sàng, nhưng Định nghĩa hoàn thành của Ngày 2 — bốn file kết quả OCR thật cho hai ngôn ngữ — **chưa đạt**.
2. **Chưa có ảnh danh thiếp mẫu nào.** Bộ 40 ảnh vẫn ở mức 0/40.

Cả hai đều là việc cần người thực hiện làm, không phải việc của mã nguồn.

---

## 2. Mục đích tổng thể của giai đoạn này

Ngày 1 không tạo ra tính năng người dùng nhìn thấy. Mục đích của nó là **loại bỏ các sai lầm không sửa được về sau**:

| Rủi ro nếu bỏ qua Ngày 1 | Hậu quả thực tế |
| --- | --- |
| Không có `.gitignore` trước khi tạo `.env` | Khóa dịch vụ vào lịch sử Git vĩnh viễn, xóa file sau đó không cứu được |
| Thiết kế bảng dữ liệu muộn (đến Ngày 7) | Phải sửa lại cả tầng trích xuất lẫn giao diện đã viết xong |
| Không tách bằng chứng gốc khỏi dữ liệu người dùng sửa | Ngày 9 không đo được chất lượng OCR, mất phần quan trọng nhất của bài |
| Không chuẩn bị dữ liệu mẫu từ đầu | Dồn việc gán nhãn 40 ảnh vào Ngày 9, không kịp |

Nói ngắn gọn: Ngày 1 mua sự an toàn cho 9 ngày còn lại.

---

## 3. Các quyết định kỹ thuật đã chốt

Đề gốc `De2.docx.pdf` không quy định công nghệ nào. Các lựa chọn dưới đây là quyết định của người thực hiện, kèm lý do.

| Thành phần | Lựa chọn | Vì sao chọn |
| --- | --- | --- |
| Frontend | Streamlit 1.63 | Cả dự án còn một ngôn ngữ, một môi trường ảo, một lệnh test. `st.camera_input()` giải quyết bước chụp ảnh mà không cần thư viện ngoài |
| Backend | FastAPI 0.141 + Uvicorn | Pydantic v2 dùng chung cho cả validation API và ràng buộc đầu ra của LLM |
| Cơ sở dữ liệu | SQLite + SQLAlchemy 2.0 | Đủ cho demo một máy chủ; schema viết chuẩn SQL nên chuyển PostgreSQL sau được |
| OCR | Google Cloud Vision `DOCUMENT_TEXT_DETECTION` | Hỗ trợ tiếng Nhật gồm chữ dọc; trả bounding box làm bằng chứng |
| Trích xuất trường | Gemini với structured output | Ánh xạ văn bản thô sang schema ứng dụng |
| Tra cứu doanh nghiệp | Tải trang công khai + Gemini có kiểm chứng đoạn trích | Không cần Search API trả phí |

### Vì sao không dùng Azure

Đặc tả ban đầu có xem xét Azure `prebuilt-businessCard`. Model này **đã deprecated từ API v4.0**, tài liệu chỉ còn liệt kê nó ở v3.1 (`2023-07-31`). Xây dựng bài tập trên một model đã ngừng phát triển là rủi ro không cần thiết khi có lựa chọn khác tương đương. Toàn bộ phần đối chiếu Azure ở mục 4 của đặc tả nay là tham khảo lịch sử.

### Vì sao đổi từ React sang Streamlit giữa chừng

Ban đầu khung frontend được dựng bằng React 19 + Vite, sau đó chuyển sang Streamlit. Lý do và đánh đổi ở mục 6.

---

## 4. Các hạng mục đã hoàn thành

Mỗi hạng mục trình bày theo bốn câu hỏi: **làm gì → mục đích → cách làm → vì sao làm như vậy**.

### 4.1 Kiểm soát bí mật trước tiên

**Làm gì:** Tạo `.gitignore` chặn `.env`, `secrets/`, `.streamlit/secrets.toml`, `backend/data/`, `.venv/`, `datasets/dev|eval/` — **trước khi** tạo bất kỳ file `.env` nào.

**Mục đích:** Không để khóa dịch vụ hoặc thông tin cá nhân trên danh thiếp lọt vào lịch sử Git.

**Cách làm:** Viết `.gitignore` và commit nó ở commit đầu tiên (`f937083`), rồi mới tạo `.env` từ `.env.example`.

**Vì sao theo thứ tự này:** Git lưu toàn bộ lịch sử. Một file `.env` bị commit một lần rồi xóa ở commit sau **vẫn nằm trong repo** và ai clone cũng đọc được. Cách duy nhất để gỡ là viết lại lịch sử — việc phiền phức và dễ sót. Thêm `.gitignore` sau khi đã lỡ commit là quá muộn, nên thứ tự này không thể đảo.

Ngoài ra `datasets/dev/` và `datasets/eval/` cũng bị chặn vì **ảnh danh thiếp chứa thông tin cá nhân thật** của người khác.

### 4.2 Khung backend FastAPI

**Làm gì:** `backend/app/` gồm `config.py`, `db.py`, `models.py`, `main.py`.

**Mục đích:** Có một máy chủ chạy được, đọc cấu hình từ biến môi trường, kết nối cơ sở dữ liệu.

**Cách làm:**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r frontend\requirements.txt
Copy-Item backend\.env.example backend\.env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000 --app-dir backend
```

**Vì sao dùng một môi trường ảo duy nhất ở gốc dự án:** Sau khi đổi sang Streamlit, cả hai tầng đều là Python. Hai venv riêng chỉ tạo ra câu hỏi "đang ở venv nào" mỗi lần mở terminal, và làm lệnh chạy test phức tạp hơn mà không đổi lại được gì.

**Vì sao cấu hình đi qua `pydantic-settings` thay vì `os.environ` trực tiếp:** Sai kiểu dữ liệu bị bắt ngay khi khởi động chứ không phải lúc chạy. `MAX_UPLOAD_BYTES=abc` làm ứng dụng không lên được kèm thông báo rõ ràng, thay vì gây `TypeError` khó hiểu ở giữa một lần xử lý ảnh.

### 4.3 Thiết kế cơ sở dữ liệu — hạng mục quan trọng nhất

**Làm gì:** 8 bảng trong `backend/app/models.py`: `organizations`, `contacts`, `contact_emails`, `contact_phones`, `addresses`, `scans`, `enrichments`, `idempotency_keys`.

**Mục đích:** Cấu trúc dữ liệu phải đáp ứng được mọi yêu cầu FR-01…FR-11 **trước khi** viết code trích xuất và giao diện.

**Cách làm:** Viết đặc tả DDL trong kế hoạch chi tiết trước, rồi hiện thực bằng SQLAlchemy 2.0.

**Vì sao thiết kế trước:** Đây là thành phần đắt nhất khi phải sửa. Đổi một bảng ở Ngày 7 kéo theo sửa hàm ánh xạ OCR (Ngày 4), quy tắc chuẩn hóa (Ngày 5) và toàn bộ form (Ngày 5). Đổi ở Ngày 1 thì chỉ sửa một file.

Ba quyết định thiết kế cần giải thích được khi trình bày:

#### (a) Email, điện thoại, địa chỉ nằm ở bảng riêng, không phải cột trong `contacts`

*Vì sao:* Danh thiếp thường có nhiều số điện thoại (bàn, di động, fax) và có thể nhiều email. Nếu thiết kế `contacts.phone` là một cột, khi gặp thẻ có ba số bạn buộc phải chọn: bỏ bớt, hoặc nhồi cả ba vào một chuỗi. Cả hai đều làm hỏng dữ liệu. Bảng riêng còn cho phép đánh chỉ mục để tìm kiếm và phát hiện trùng theo email/số điện thoại (FR-09, FR-10).

#### (b) Số điện thoại lưu kiểu `TEXT`, không phải số

*Vì sao:* `0312345678` đọc thành số sẽ thành `312345678` — mất số 0 đầu. Ngoài ra số điện thoại có dấu `+`, dấu gạch, dấu cách và số máy lẻ, đều không phải giá trị số học. Không ai cộng trừ số điện thoại bao giờ.

Bảng lưu hai cột: `value_raw` giữ nguyên `+81 3-1234-5678` để hiển thị, `value_digits` (`81312345678`) chỉ để so khớp trùng lặp.

#### (c) `scans.raw_text` và `scans.extraction_json` là bất biến

*Vì sao:* Đây là điều kiện để Ngày 9 đo được chất lượng. Yêu cầu là đo **kết quả tự động trước khi người dùng sửa tay**. Nếu chỉnh sửa của người dùng ghi đè lên kết quả máy, dữ liệu để đo biến mất và mọi con số báo cáo sẽ là 100% — vô nghĩa.

Vì vậy: người dùng sửa ở `contacts`/`contact_emails`/…, còn bảng `scans` giữ nguyên bằng chứng gốc. Khóa ngoại `scans.contact_id` đặt `ON DELETE SET NULL` chứ không `CASCADE`, để xóa hồ sơ không kéo theo mất bằng chứng.

#### Cặp cột `*_raw` / `*_norm`

Mọi giá trị hiển thị được lưu hai bản: bản gốc để hiện ra, và bản chuẩn hóa (`NFKC` + `casefold` + bỏ khoảng trắng) chỉ để tìm kiếm và so khớp.

*Vì sao cần NFKC:* Danh thiếp Nhật thường in bằng ký tự full-width — `ＴＥＬ：０３-１２３４`. Với máy tính đó là chuỗi hoàn toàn khác `TEL:03-1234`, nên tìm kiếm sẽ không ra kết quả. NFKC quy hai dạng về một.

*Vì sao vẫn giữ bản gốc:* Đặc tả cấm thay dữ liệu gốc bằng bản phiên âm hoặc chuẩn hóa. Người dùng phải thấy đúng những gì in trên thẻ.

### 4.4 Endpoint `GET /api/health`

**Làm gì:** Trả trạng thái ứng dụng và mức sẵn sàng của từng dịch vụ.

**Mục đích:** Biết cấu hình đã nhận chưa mà không phải đọc file `.env` hay thêm log.

**Cách làm:** Hàm `Settings.readiness()` chỉ trả `True`/`False` cho từng mục:

```json
{
  "status": "ok",
  "config": {
    "ocr_provider": "mock",
    "ocr_credentials_present": false,
    "gemini_key_present": false,
    "enrich_enabled": true
  }
}
```

**Vì sao chỉ trả `true`/`false` mà không trả giá trị khóa:** Endpoint này công khai. Trả về giá trị khóa — kể cả rút gọn kiểu `AIza...x8Q` — là làm lộ thông tin không cần thiết. Thiết kế này cũng khiến mục kiểm tra ở Ngày 8 ("grep toàn repo tìm khóa") luôn pass.

Sidebar của ứng dụng hiển thị đúng thông tin này, nên **nó đóng vai trò checklist Ngày 2 nhìn thấy được**: khi hai dòng OCR và trích xuất chuyển sang "sẵn sàng" thì phụ thuộc rủi ro cao nhất của dự án đã được gỡ bỏ.

### 4.5 Khung frontend Streamlit

**Làm gì:** `frontend/streamlit_app.py` + ba trang trong `app_pages/` (quét thẻ, kiểm tra, hồ sơ) + `lib/api.py`.

**Mục đích:** Có đủ ba màn hình theo luồng nghiệp vụ, nối được backend.

**Cách làm:**

```powershell
.\.venv\Scripts\streamlit.exe run frontend\streamlit_app.py
```

Điều hướng bằng `st.navigation` + `st.Page`. Trạng thái dùng chung giữa các trang khởi tạo tại một chỗ duy nhất trong `streamlit_app.py`.

**Vì sao đặt tên thư mục `app_pages/` chứ không phải `pages/`:** Streamlit tự động coi mọi file trong thư mục tên `pages/` là một trang, theo API đa trang đời cũ. Trộn cơ chế đó với `st.navigation` gây điều hướng trùng lặp. Đặt tên khác là cách tránh dứt điểm.

**Vì sao trạng thái phải đi qua `st.session_state`:** Streamlit chạy lại toàn bộ script từ đầu sau mỗi lần người dùng tương tác. Biến thường sẽ mất giá trị. `st.session_state` là nơi duy nhất sống sót qua các lần chạy lại.

**Vì sao trang "Kiểm tra" poll bằng `@st.fragment(run_every="1s")` thay vì gọi OCR trực tiếp:** Đây là điểm dễ gây tốn tiền nhất. Nếu gọi OCR trong thân script, mỗi lần chạy lại là một lần gọi Google — tức mỗi ký tự người dùng gõ là một hóa đơn. Kiến trúc hiện tại: OCR chạy ở tác vụ nền của backend, frontend chỉ hỏi trạng thái. `st.fragment` khiến riêng khối poll chạy lại mỗi giây, phần còn lại của trang giữ nguyên.

Trang **Quét thẻ** đã làm thật, không phải khung rỗng: chọn giữa camera và tải ảnh, xem trước, hiển thị dung lượng và định dạng, nút gửi. Đây vốn là việc của Ngày 3 nhưng `st.camera_input()` và `st.file_uploader()` có sẵn nên hoàn thành sớm.

### 4.6 Bộ kiểm thử tự động

**Làm gì:** 9 test, chạy bằng một lệnh từ gốc dự án.

**Mục đích:** Khóa lại các giả định nền tảng để chúng không bị phá vỡ âm thầm trong 9 ngày còn lại.

**Cách làm:** `python -m pytest` — `pytest.ini` ở gốc trỏ tới cả `backend/tests` và `frontend/tests`.

**Từng test bảo vệ điều gì:**

| Test | Bắt lỗi gì |
| --- | --- |
| `test_khoa_ngoai_duoc_thuc_thi` | SQLite **mặc định tắt** ràng buộc khóa ngoại. Không bật `PRAGMA foreign_keys=ON` thì mọi `ON DELETE CASCADE` chỉ là chữ trang trí, dữ liệu mồ côi tích tụ mà không báo lỗi |
| `test_tieng_nhat_di_qua_db_khong_doi` | Chữ Nhật bị hỏng khi lưu và tải lại — yêu cầu bắt buộc của đề |
| `test_norm_key_gop_full_width_va_half_width` | Tìm kiếm không ra kết quả với danh thiếp in bằng ký tự full-width |
| `test_so_dien_thoai_giu_nguyen_so_0_dau_va_dau_cong` | Mất số 0 đầu hoặc dấu `+` |
| `test_scan_giu_bang_chung_goc_khi_contact_bi_xoa` | Mất dữ liệu để đo chất lượng ở Ngày 9 |
| 4 test `AppTest` của frontend | Sai tên icon, sai tham số widget, `KeyError` trong `session_state` — loại lỗi chỉ lộ ra khi mở đúng trang đó trên trình duyệt |

**Vì sao viết test ngay từ Ngày 1 thay vì để cuối:** Năm test đầu đều bắt **lỗi im lặng** — loại lỗi không làm sập ứng dụng mà chỉ làm hỏng dữ liệu. Không có test, chúng thường chỉ bị phát hiện ở Ngày 9 khi số liệu đã sai và không còn thời gian sửa.

**Vì sao dùng `AppTest` cho frontend:** Nó chạy ứng dụng Streamlit headless ngay trong tiến trình pytest, không cần mở trình duyệt cũng không cần server. Đủ nhanh để chạy sau mỗi thay đổi. Backend được giả lập nên test không gọi mạng thật.

### 4.7 Khung dữ liệu mẫu

**Làm gì:** `datasets/README.md` (quy tắc thu thập và gán nhãn) + `labels.jsonl` + `backend/scripts/check_labels.py`.

**Mục đích:** Chuẩn bị điều kiện để Ngày 9 đo được chất lượng.

**Cách làm:** Chạy `python backend/scripts/check_labels.py` để xem tiến độ và các lỗi trong bộ nhãn.

**Vì sao tách bộ `dev/` và bộ `eval/`:** Mỗi lần nhìn một ảnh rồi sửa code cho nó chạy đúng, ảnh đó mất giá trị đánh giá. Bộ `eval/` được giữ riêng, chỉ chạy **một lần** ở Ngày 9 để lấy số liệu báo cáo.

**Vì sao gán nhãn từ ảnh chứ không từ kết quả OCR:** Nếu lấy đầu ra OCR làm đáp án chuẩn, độ chính xác đo được sẽ luôn là 100% và hoàn toàn vô nghĩa.

**Vì sao có cột `uncertain` trong nhãn:** Những trường mà chính người gán nhãn cũng không đọc nổi từ ảnh sẽ bị loại khỏi phép đo, thay vì bị tính oan là lỗi của máy.

---

## Ngày 2 — dựng đường đi OCR

### 4.8 Lớp trừu tượng nhà cung cấp OCR

**Làm gì:** `services/ocr/` gồm `base.py` (giao diện `OcrProvider` + kiểu `OcrResult`), `google_vision.py` và `mock.py`.

**Mục đích:** Phần còn lại của hệ thống chỉ biết một kiểu dữ liệu duy nhất, không biết dữ liệu đến từ nhà cung cấp nào.

**Cách làm:** `OcrProvider` là một `Protocol` với đúng một phương thức `recognize(image, mime) -> OcrResult`. Chọn nhà cung cấp bằng biến `OCR_PROVIDER=google|mock`.

**Vì sao cần lớp này:** Ngày 2 là ngày rủi ro cao nhất vì phụ thuộc dịch vụ ngoài. Nếu mã nguồn gọi thẳng `google.cloud.vision` ở khắp nơi thì đổi nhà cung cấp sẽ phải sửa cả ứng dụng. Lớp trừu tượng khiến đường lui trở thành một dòng cấu hình.

**Vì sao `recognize` là hàm đồng bộ, không phải `async`:** SDK của Google Vision là đồng bộ. Bọc nó trong `async def` mà không đẩy sang thread pool sẽ **chặn event loop** của FastAPI — cả máy chủ đứng im trong lúc chờ OCR. FastAPI tự chạy hàm đồng bộ trong thread pool, nên để đồng bộ là đúng. Kế hoạch chi tiết viết `async def`; đây là chỗ đi khác kế hoạch và lý do đi khác.

**Vì sao chọn `DOCUMENT_TEXT_DETECTION` chứ không `TEXT_DETECTION`:** Feature này dành cho ảnh chữ đặc, trả về cấu trúc trang/khối/đoạn kèm toạ độ và ngôn ngữ phát hiện được cho từng phần. `TEXT_DETECTION` chỉ trả chữ rời rạc, không có cấu trúc để đối chiếu.

**Một chi tiết dễ sai:** Vision trả về từng ký tự riêng lẻ kèm cờ `detected_break` cho biết sau ký tự đó là dấu cách hay xuống dòng. Phải tôn trọng cờ này khi ghép chữ, nếu không địa chỉ tiếng Nhật nhiều dòng sẽ bị dính liền thành một chuỗi.

**Vì sao có `MockOcrProvider`:** Bộ kiểm thử không được gọi mạng thật — vừa tốn tiền, vừa khiến test thất bại vì lý do không liên quan đến mã nguồn (mất mạng, hết quota). Mock đọc lại phản hồi đã lưu, đặt tên theo SHA-256 của ảnh. Fixture do lần gọi **thật** sinh ra, nên test vẫn chạy trên dữ liệu thực tế.

### 4.9 Grounding — chốt chặn chống bịa dữ liệu

**Làm gì:** `services/extract/grounding.py` — đối chiếu mọi giá trị mô hình trả về với văn bản OCR gốc, loại bỏ giá trị không đối chiếu được.

**Mục đích:** Đáp ứng yêu cầu "không tự điền dữ liệu không đọc được" bằng **cơ chế kỹ thuật**, không bằng lời hứa.

**Vì sao không giải quyết bằng prompt:** Gemini là mô hình sinh. Đưa nó ảnh một danh thiếp không có email, nó vẫn có thể trả về một email "hợp lý" ghép từ tên người và tên miền công ty. Câu lệnh "không được bịa" làm **giảm** tỷ lệ bịa chứ không triệt tiêu, và không đo lường được. Chốt chặn phải là một phép kiểm tra chạy được và viết được test.

**Cách làm:** `raw_text` từ Google Vision là **bằng chứng** — nó đến trực tiếp từ điểm ảnh, không qua mô hình sinh. Mọi giá trị Gemini trả về đều phải đối chiếu được với bằng chứng đó. Kết quả có ba mức:

| Mức | Nghĩa | Xử lý |
| --- | --- | --- |
| `exact` | Tìm thấy nguyên văn | Nhận |
| `fuzzy` | Lệch ít, do OCR nhầm ký tự giống nhau | Nhận nhưng gắn cờ "cần kiểm tra" |
| `unverified` | Không tìm thấy | **Loại khỏi bản nháp**, vẫn ghi lại để báo cáo |

Trường bị loại **không biến mất** khỏi báo cáo — đó chính là số liệu cột "Tự sinh" của Ngày 9.

#### Một lỗi thiết kế bị bắt bởi chính bộ test

Bản đầu tiên kiểm tra bằng phép "chuỗi con nằm trong văn bản". Test phát hiện lỗ hổng: thẻ có thật `taro.yamada@example.co.jp`; nếu mô hình bịa ra `yamada@example.co.jp` thì chuỗi bịa **nằm gọn** trong chuỗi thật nên được chấm là hợp lệ. Một email không tồn tại sẽ vào hồ sơ đối tác mà không ai biết.

**Cách sửa:** với email, URL và số điện thoại, đơn vị so sánh phải là **cả token** chứ không phải một đoạn bất kỳ. Văn bản OCR được cắt thành các token trọn vẹn bằng regex, rồi so bằng phép bằng nhau:

- Email: so cả địa chỉ.
- URL: quy về `host + path`, bỏ `https://` và `www.` vì không đổi trang; nhưng subdomain khác thật sự thì bị loại.
- Điện thoại: so bằng chuỗi chữ số, nên `03-1234-5678` và `03 1234 5678` là một.

Với tên/công ty/địa chỉ vẫn dùng phép chuỗi con, vì tên người xuất hiện hợp lệ bên trong một dòng; kèm ngưỡng độ dài tối thiểu để giá trị một ký tự không khớp bừa.

**Vì sao đáng kể lại chuyện này:** đây là loại lỗi không làm sập gì cả, chỉ âm thầm cho dữ liệu bịa lọt qua. Nó chứng minh vì sao chốt chặn phải có test — bản thân người viết cũng không tự nhìn ra.

### 4.10 Hai bộ trích xuất trường

**Làm gì:** `services/extract/gemini.py` (mô hình vision, ép schema JSON) và `heuristic.py` (regex, không cần mạng). Chọn bằng `EXTRACTOR=gemini|heuristic`.

**Vì sao đưa Gemini cả ảnh lẫn `raw_text`:** Ảnh cho mô hình thấy **bố cục** — trên danh thiếp, vị trí quyết định ý nghĩa: chữ ở góc trên trái thường là tên công ty, chữ ngay dưới tên thường là chức danh. Chỉ đưa văn bản thô thì mất toàn bộ thông tin này. Còn `raw_text` cho mô hình một bản đọc đã có, giảm việc nó phải tự đọc lại ảnh mờ và đọc sai.

**Vì sao `temperature=0`:** cùng một ảnh phải cho cùng một kết quả. Ngày 9 đo chất lượng, mà không thể đo được thứ ngẫu nhiên.

**Vì sao mọi trường trong schema đều là danh sách, không dùng `X | None`:** Về nghiệp vụ, danh thiếp Nhật thường in tên và tên công ty bằng **hai hệ chữ** (Kanji và romaji); cả hai đều là giá trị thật, không phải một đúng một sai — đặc tả yêu cầu `companyNames[]` chính vì lý do này. Về kỹ thuật, JSON Schema xử lý danh sách ổn định hơn kiểu nullable.

**Vì sao có bộ regex dự phòng:** nếu không lấy được quyền truy cập Gemini thì cả lịch trình dừng lại. Email, điện thoại và website đều có định dạng đủ chặt chẽ để bắt bằng regex.

**Giới hạn của bộ regex — đã đo, không phải phỏng đoán:** chạy thử trên thẻ tiếng Nhật tổng hợp, nó đưa `部長  山田 太郎` vào ô **chức danh** vì tên và chức danh nằm chung một dòng, và **không trích được `full_names` nào**. Đây là đường lui, không phải phương án tương đương. Báo cáo Ngày 9 bắt buộc phải ghi rõ đã dùng bộ trích xuất nào.

### 4.11 Script spike `try_ocr.py`

**Làm gì:** Công cụ chạy độc lập, không cần backend hay giao diện.

**Mục đích:** Chứng minh OCR và trích xuất hoạt động thật với cả hai ngôn ngữ **trước khi** đầu tư thời gian vào giao diện.

**Cách làm:**

```powershell
# Xem tài khoản của bạn dùng được model Gemini nào
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py --list-models

# Chạy trên ảnh thật
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py datasets\dev\ja\001.jpg datasets\dev\en\001.jpg
```

Script in văn bản OCR, bảng trường trích xuất kèm kết quả đối chiếu, thời gian xử lý, rồi lưu fixture cho bộ test.

**Vì sao có `--list-models` thay vì ghi sẵn tên model:** tên model Gemini thay đổi theo thời gian và khác nhau giữa các tài khoản. Đoán tên rồi hardcode là cách chắc chắn để gặp lỗi 404 khó chẩn đoán. Hỏi thẳng API là cách duy nhất biết chính xác — nên `GEMINI_MODEL` để trống trong `.env.example`, kèm hướng dẫn chạy lệnh này.

**Vì sao script ép UTF-8 cho stdout:** console Windows mặc định dùng cp1252 và ném `UnicodeEncodeError` khi in chữ Nhật. Không xử lý thì sẽ tưởng OCR lỗi trong khi thực ra chỉ là lỗi hiển thị của terminal. Đây là lỗi đã gặp thật trong lúc phát triển.

**Vì sao có `make_test_card.py`:** sinh ảnh danh thiếp tổng hợp để kiểm tra đường ống khi chưa có ảnh thật. Ảnh này là chữ in kỹ thuật số, sắc nét tuyệt đối — **chỉ dùng kiểm tra đường ống, không dùng đo chất lượng**. Ảnh quá đẹp sẽ cho kết quả lạc quan không phản ánh danh thiếp chụp bằng điện thoại ngoài đời. Fixture sinh ra ghi `provider: "synthetic"` để không ai nhầm là kết quả OCR thật.

---

## 5. Bằng chứng đã kiểm chứng

Phân biệt rõ giữa "đã viết code" và "đã chạy và thấy kết quả":

| Hạng mục | Cách kiểm chứng | Kết quả |
| --- | --- | --- |
| Cơ sở dữ liệu tạo được bảng | Gọi `init_db()` rồi `inspect(engine).get_table_names()` | 8 bảng đúng tên |
| Backend trả lời qua HTTP | `Invoke-WebRequest http://127.0.0.1:8000/api/health` | 200, JSON đúng cấu trúc |
| Frontend phục vụ được | `Invoke-WebRequest http://localhost:8501` | 200 |
| Ba trang Streamlit chạy không lỗi | `AppTest` chạy headless từng trang | 4/4 pass, không exception |
| Toàn bộ test | `python -m pytest` | 27/27 pass |
| Đường ống OCR đầu-cuối | `try_ocr.py` trên 2 ảnh tổng hợp (nhánh mock) | Chạy thông, chữ Nhật không lỗi mã hoá |
| Grounding loại được dữ liệu bịa | 18 test đối kháng trong `test_grounding.py` | Email/tên/điện thoại/website bịa đều bị loại |
| Đường lỗi của script spike | Chạy khi thiếu khoá và thiếu fixture | Báo lỗi rõ ràng kèm cách xử lý |
| Đường dẫn ảnh neo đúng thư mục | In `settings.image_path` khi chạy từ gốc dự án | `backend\data\images` (đúng) |
| Không rò rỉ bí mật | `git status --short` lọc `.env`, `secrets`, `.venv`, `/data/`, `.db` | Không có kết quả |

**Chưa kiểm chứng được, và vì sao:**

| Hạng mục | Lý do chưa kiểm chứng |
| --- | --- |
| **Lời gọi Google Vision thật** | Chưa có tài khoản Google Cloud. Mã nguồn đã viết xong nhưng chưa chạy lần nào |
| **Lời gọi Gemini thật** | Chưa có API key. Chưa biết mô hình có bịa dữ liệu nhiều hay ít trên thẻ thật |
| **Schema `CardExtraction` có được Gemini chấp nhận không** | Phải gọi thật mới biết. Đã thiết kế tránh kiểu nullable để giảm rủi ro |
| Chất lượng nhận diện tiếng Anh/Nhật | Chưa có OCR thật và chưa có ảnh mẫu |
| Ảnh từ `st.camera_input()` có bị lật gương không | Cần camera thật. Widget hiển thị preview dạng gương như mọi ứng dụng camera, nhưng bytes trả về thì không — phải chụp một thẻ có chữ rồi đọc lại kết quả để xác nhận, không tin vào preview |
| Xử lý xoay ảnh theo EXIF | Chưa có endpoint nhận ảnh (Ngày 3) |

---

## 6. Việc đổi frontend từ React sang Streamlit

**Đã làm gì:** Khung frontend ban đầu dựng bằng React 19 + Vite + TypeScript, sau đó thay bằng Streamlit 1.63 (commit `b128e99`).

**Vì sao đổi:** Cả stack thành Python — một ngôn ngữ, một môi trường ảo, một lệnh chạy test. `st.camera_input()` thay được `react-webcam` bằng một dòng. Thời gian tiết kiệm ở tầng giao diện được dồn cho phần thực sự tạo nên bài làm: trích xuất có kiểm chứng, chuẩn hóa và tra cứu có dẫn nguồn.

**Về hai repository webcam trong phần phân tích ban đầu:** `react-webcam` và `blazor-webcam` chỉ giải quyết **bước lấy ảnh**. `st.camera_input()` giải quyết đúng bước đó, nên vai trò tham chiếu của chúng được thay thế chứ không bị bỏ qua. Đề gốc không quy định công nghệ frontend nên lựa chọn này vẫn đúng phạm vi.

### Hệ quả kiến trúc

| Điểm | SPA (React) | Streamlit |
| --- | --- | --- |
| Ai gọi FastAPI | Trình duyệt (JavaScript) | Tiến trình Streamlit (Python, phía máy chủ) |
| CORS | Phải cấu hình | Không liên quan — không có request chéo nguồn từ trình duyệt |
| Biến cấu hình | `VITE_*` bị nhúng vào file JS gửi xuống trình duyệt | Chỉ là biến môi trường phía máy chủ |
| Ảnh danh thiếp | `<img src="/api/images/...">` → phải phơi endpoint ảnh ra Internet | Streamlit tải bytes rồi vẽ lên trang |

Ba dòng cuối đều là điểm cộng về bảo mật: bề mặt tấn công nhỏ hơn so với SPA. Đặc biệt, cái bẫy `VITE_*` — mọi biến có tiền tố này bị nhúng thẳng vào JavaScript gửi cho người dùng — không còn tồn tại.

### Cái mất, nói thẳng

- Streamlit chạy lại toàn bộ script sau mỗi tương tác. Trạng thái buộc phải đi qua `st.session_state`, và mọi lời gọi dịch vụ tốn tiền phải được đặt ngoài đường chạy lại.
- Không kiểm soát giao diện ở mức chi tiết như React.

Với phạm vi ba màn hình của bài này, đánh đổi đó có lợi.

---

## 7. Những gì chưa làm

| Ngày | Hạng mục | Trạng thái |
| --- | --- | --- |
| 1 | Thu thập 40 ảnh mẫu (20 Anh + 20 Nhật) và gán nhãn | **0/40** — chưa bắt đầu |
| 2 | Đăng ký Google Cloud + Gemini | **Chưa** — chặn Định nghĩa hoàn thành Ngày 2 |
| 2 | Chạy OCR thật trên 2 ảnh Anh + 2 ảnh Nhật | **Chưa** — chờ mục trên |
| 2 | Điền `Document/ocr-provider-notes.md` (model, quota, chi phí) | Phiếu đã có, **chưa điền** |
| 2 | Kiểm tra nguồn tra cứu doanh nghiệp truy cập được | Chưa |
| 3 | `POST /api/scans` — nhận ảnh, kiểm tra tệp thật, xoay EXIF, lưu | Chưa |
| 4 | Nối OCR vào ứng dụng, tác vụ nền, `GET /api/scans/{id}` | Chưa |
| 5 | Chuẩn hóa và form kiểm tra/chỉnh sửa | Chưa |
| 6 | Tra cứu doanh nghiệp có dẫn nguồn + chặn SSRF | Chưa |
| 7 | Lưu hồ sơ, tìm kiếm, phát hiện trùng, xuất dữ liệu | Chưa |
| 8 | Kiểm thử tích hợp 13 tình huống hỏng | Chưa |
| 9 | Đo chất lượng theo từng trường và từng ngôn ngữ | Chưa |
| 10 | Đóng gói, README, demo | README có bản đầu |

**Đi sớm hơn kế hoạch:** `grounding.py` vốn là hạng mục Ngày 4, đã làm xong ở Ngày 2. Lý do: nó là hàm thuần, kiểm thử được hoàn toàn offline, nên là việc có ích nhất để làm trong lúc chờ credentials. Nhờ vậy `try_ocr.py` báo được tỷ lệ bịa dữ liệu ngay từ lần gọi thật đầu tiên — đúng mục đích của một spike.

---

## 8. Rủi ro đang mở

| Rủi ro | Mức độ | Xử lý |
| --- | --- | --- |
| **Chưa có quyền truy cập Google Cloud / Gemini** | **Cao — đang chặn tiến độ** | Độ trễ nằm ngoài tầm kiểm soát (duyệt tài khoản, gắn thẻ thanh toán). Mọi thứ khác của Ngày 2 đã xong; chỉ còn chờ mục này. Đường lui đã ghi ở `Document/ocr-provider-notes.md` mục E |
| **Gemini bịa trường không có trên thẻ** | Cao → **đã có chốt chặn** | `grounding.py` đã viết xong và có 18 test đối kháng. Mọi giá trị không đối chiếu được với `raw_text` đều bị loại. Vẫn là rủi ro Cao vì **chưa đo được tỷ lệ bịa trên thẻ thật** |
| **Chưa có ảnh mẫu** | **Cao** (tăng từ Trung bình) | Đã sang Ngày 2 mà vẫn 0/40. Không có ảnh thì Ngày 9 không đo được gì, và cũng không kiểm chứng được OCR ở Ngày 2 |
| **Chưa biết Gemini có chấp nhận schema `CardExtraction` không** | Trung bình | Đã tránh kiểu nullable để giảm rủi ro, nhưng chỉ gọi thật mới biết chắc. Nếu lỗi thì `EXTRACTOR=heuristic` giữ luồng chính chạy |
| **Phạm vi chỉ Anh + Nhật, đề gốc nêu 4 ngôn ngữ** | Trung bình | Vision và Gemini vốn xử lý được `ko`/`zh`; thêm vào `languageHints` gần như miễn phí, chỉ cần bổ sung mẫu thử. Là việc ưu tiên nếu còn dư thời gian |
| **Chất lượng OCR thẻ Nhật chữ dọc** | Chưa rõ | Chỉ biết sau Ngày 2. Phạm vi MVP đã tuyên bố là bố cục ngang |

---

## 9. Bước tiếp theo

### Việc của người thực hiện — không có mã nguồn nào thay thế được

**1. Lấy credentials (ưu tiên cao nhất).**

- Tạo Google Cloud project, bật Cloud Vision API, tạo service account, tải JSON key về `backend/secrets/gcp-sa.json`.
- Lấy `GEMINI_API_KEY` ở Google AI Studio.
- Điền vào `backend/.env`, đổi `OCR_PROVIDER=google` và `EXTRACTOR=gemini`.

**2. Chọn model:**

```powershell
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py --list-models
```

Chọn một model đọc được ảnh, điền vào `GEMINI_MODEL`.

**3. Chụp ít nhất 2 danh thiếp tiếng Anh và 2 tiếng Nhật**, rồi:

```powershell
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py <đường dẫn 4 ảnh>
```

**4. Điền `Document/ocr-provider-notes.md`** — phần B (model), C (kết quả chạy thật), D (chi phí), F (nguồn tra cứu).

### Định nghĩa hoàn thành Ngày 2 — **chưa đạt**

Có 4 file JSON kết quả OCR thật cho cả hai ngôn ngữ, lưu trong `backend/tests/fixtures/ocr/`.

Hiện có 2 fixture nhưng chúng ghi `provider: "synthetic"` — sinh từ văn bản đã biết, **không phải kết quả OCR**. Chúng chỉ chứng minh đường ống chạy thông, không chứng minh OCR hoạt động.

**Nếu kéo dài:** được phép dùng fixture để dựng tiếp Ngày 3–5, nhưng phải ghi rõ trong README là dữ liệu mô phỏng và phải quay lại làm thật trước Ngày 8. Không che phần thiếu bằng demo giả.

### Sau khi Ngày 2 đạt — Ngày 3

`POST /api/scans`: nhận ảnh, đọc magic bytes bằng Pillow để từ chối tệp không phải ảnh dù đuôi là `.jpg`, giới hạn 8 MB, **xoay ảnh theo EXIF**, lưu vào `data/images/<sha256>`, ghi dòng `scans`.

---

## Phụ lục — Lịch sử commit

| Commit | Nội dung |
| --- | --- |
| `b38534d` | Khởi tạo repo |
| `f937083` | Kế hoạch triển khai chi tiết + `.gitignore` (trước khi tạo file `.env` nào) |
| `5b42e49` | Khung Ngày 1: backend FastAPI, schema 8 bảng, frontend React, 5 test |
| `b128e99` | Đổi frontend React → Streamlit; gộp về một venv; sửa neo đường dẫn ảnh |
| `3ecfeec` | Báo cáo tiến độ Ngày 1 |
| *(commit này)* | Ngày 2: lớp OCR, hai bộ trích xuất, grounding + 18 test, script spike |
