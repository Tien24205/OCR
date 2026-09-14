# Chuyển hóa danh thiếp thành hồ sơ đối tác chuẩn hóa

Ứng dụng web: chụp hoặc tải ảnh danh thiếp → OCR (Anh + Nhật) → trích xuất trường có cấu trúc → chuẩn hóa → tra cứu bổ sung thông tin doanh nghiệp **có dẫn nguồn** → lưu hồ sơ tập trung, tìm kiếm và xuất dữ liệu.

Đề bài #2. Tài liệu đầy đủ: [Document/README.md](Document/README.md)

```
Streamlit (giao diện)  →  FastAPI (backend)  →  SQLite
                                ↓
                   Google Vision (OCR)  +  Gemini (trích xuất trường)
```

Cả hai tầng đều là Python và dùng chung một môi trường ảo.

---

## Yêu cầu môi trường

- Python 3.11 trở lên
- Git

Không cần Node.js, không cần Docker.

## Cài đặt

Một môi trường ảo duy nhất ở gốc dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r frontend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

Trên macOS/Linux thay `.\.venv\Scripts\python.exe` bằng `.venv/bin/python`, `Copy-Item` bằng `cp`.

Cơ sở dữ liệu tự tạo khi backend khởi động lần đầu — không cần chạy lệnh migration nào.

## Chạy

Cần **hai terminal**, cả hai chạy **từ thư mục gốc dự án**:

```powershell
# Terminal 1 — backend, cổng 8000
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000 --app-dir backend

# Terminal 2 — giao diện, cổng 8501
.\.venv\Scripts\streamlit.exe run frontend\streamlit_app.py
```

Mở http://localhost:8501 · **Tài liệu API**: http://localhost:8000/docs — mô tả đầy đủ 20 endpoint, bảng mã lỗi và lưu ý khi tích hợp

> **Phải chạy từ gốc dự án.** Streamlit đọc `.streamlit/config.toml` theo thư mục đang chạy, không theo vị trí file ứng dụng. Chạy từ chỗ khác thì giới hạn dung lượng tải lên 8 MB sẽ không được áp dụng.

## Thử ngay khi chưa có API key

Mặc định `OCR_PROVIDER=mock`, tức là phát lại kết quả OCR đã lưu theo mã băm của ảnh. **Tải một ảnh bất kỳ lên sẽ báo `FIXTURE_MISSING`** vì chưa có bản ghi cho ảnh đó.

Để có bộ ảnh dùng được ngay:

```powershell
.\.venv\Scripts\python.exe backend\scripts\make_card_sheets.py --crop
```

Lệnh này sinh 40 danh thiếp hư cấu kèm bản ghi tương ứng. Sau đó tải `datasets\_dryrun\dev\ja\001.jpg` lên là thấy trọn luồng chạy.

Ảnh đó là chữ in kỹ thuật số sắc nét tuyệt đối — **chỉ để xem luồng chạy, không dùng để đánh giá chất lượng OCR**.

---

## Biến cấu hình

Toàn bộ nằm ở `backend/.env` (đã bị `.gitignore` chặn). Xem `backend/.env.example` để biết danh sách đầy đủ.

| Biến | Ý nghĩa | Mặc định |
| --- | --- | --- |
| `OCR_PROVIDER` | `google` hoặc `mock` (phát lại bản ghi, chạy offline) | `mock` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Đường dẫn JSON service account; tương đối thì tính từ `backend/` | — |
| `EXTRACTOR` | `gemini` hoặc `heuristic` (regex, không cần mạng) | `heuristic` |
| `GEMINI_API_KEY` | Khóa từ Google AI Studio | — |
| `GEMINI_MODEL` | Tên model — **đừng đoán**, xem lệnh bên dưới | — |
| `AGENT_ENABLED` | Bật tầng agentic tự sửa lỗi | `false` |
| `DATABASE_URL` · `IMAGE_DIR` | Vị trí lưu trữ | `backend/data/` |
| `MAX_UPLOAD_BYTES` | Giới hạn dung lượng ảnh | 8 MB |
| `BATCH_WORKERS` | Số ảnh xử lý đồng thời trong một lô | 3 |
| `ENRICH_*` | Giới hạn của bước tra cứu doanh nghiệp | xem `.env.example` |

### Xuất dữ liệu

`GET /api/export?format=json|csv|vcf`, hoặc dùng nút trên trang **Hồ sơ**.

| Định dạng | Dùng khi nào |
| --- | --- |
| `json` | Sao lưu, nạp vào hệ thống khác — giữ đầy đủ dữ liệu và nguồn |
| `csv` | Mở bằng bảng tính; có BOM UTF-8 để Excel không đọc sai chữ Nhật |
| `vcf` | **vCard 3.0** — mở trên điện thoại là danh bạ tự nhận, không cần map cột |

Giao diện chỉ đọc **một** biến: `API_BASE_URL` (mặc định `http://127.0.0.1:8000`). Nó không giữ khóa nào.

### Bật OCR thật

```powershell
# 1. Xem tài khoản của bạn dùng được model Gemini nào
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py --list-models

# 2. Điền backend\.env, rồi xác nhận cấu hình — chỉ tốn 2 lời gọi dịch vụ
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py --check
```

`--check` trả lời bốn câu tách bạch: credentials đọc được không, Vision có trả về chữ Nhật không, model có tồn tại không, và model có chấp nhận schema trích xuất không.

`GET /api/health` báo trạng thái sẵn sàng của từng dịch vụ **mà không tiết lộ giá trị khóa**. Sidebar của ứng dụng hiển thị đúng thông tin này.

---

## Kiểm thử

Một lệnh chạy cả backend lẫn giao diện, từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

**402 test, không gọi mạng thật**: backend dùng `OCR_PROVIDER=mock`, giao diện dùng `AppTest` chạy headless với backend giả lập.

```powershell
# Quét rò rỉ khóa — trả mã thoát 1 nếu tìm thấy, dùng được trong CI
.\.venv\Scripts\python.exe backend\scripts\check_secrets.py --all

# Kiểm tra bộ nhãn dữ liệu mẫu
.\.venv\Scripts\python.exe backend\scripts\check_labels.py

# Đo chất lượng trích xuất theo từng trường và từng ngôn ngữ
.\.venv\Scripts\python.exe backend\scripts\evaluate.py --split dev
```

---

## Cấu trúc

```text
backend/app/          FastAPI
  ├── services/ocr/       lớp trừu tượng OCR: Google Vision + mock
  ├── services/extract/   trích xuất trường + grounding chống bịa dữ liệu
  ├── services/enrich/    tra cứu doanh nghiệp có chặn SSRF
  └── pipeline.py         điều phối; agent_runner.py khi bật chế độ agentic
backend/scripts/      công cụ chạy tay (thử OCR, sinh thẻ mẫu, đo chất lượng)
backend/tests/        unit + integration
frontend/             streamlit_app.py + app_pages/ + lib/
datasets/             ảnh mẫu (không commit) + labels.jsonl
Document/             đề bài, kế hoạch, báo cáo, kiểm chứng
```

---

## Thiết kế đáng chú ý

**Chống bịa dữ liệu.** Mô hình sinh có thể trả về một email "hợp lý" ghép từ tên người và tên miền công ty, dù thẻ không hề in email. Câu lệnh "không được bịa" làm giảm tỷ lệ chứ không triệt tiêu, và không đo lường được. Vì vậy mọi giá trị mô hình trả về đều phải **đối chiếu được với văn bản OCR gốc** — không đối chiếu được thì bị loại khỏi bản nháp, nhưng vẫn được ghi lại để báo cáo đo được tỷ lệ tự sinh.

**Bằng chứng gốc là bất biến.** Người dùng sửa dữ liệu ở bảng hồ sơ; `scans.raw_text` và `scans.extraction_json` giữ nguyên kết quả của máy. Không có điều này thì không đo được chất lượng tự động trước khi sửa tay.

**Khóa dịch vụ không bao giờ rời backend.** Streamlit chạy phía máy chủ và gọi FastAPI bằng `httpx`, nên trình duyệt không hề biết tới Google. Không có CORS, không có biến cấu hình nào gửi xuống trình duyệt.

**Thông tin tra cứu phải có nguồn.** Mỗi khẳng định kèm URL, thời điểm và đoạn trích nguyên văn; đoạn trích nào không tìm thấy trên trang nguồn thì khẳng định bị loại. Bộ tải trang chặn địa chỉ nội bộ ở **từng lần chuyển hướng**, không chỉ ở URL đầu.

---

## Giới hạn đã biết

**Chưa có lời gọi Google Vision hay Gemini nào được thực hiện trong dự án này.** Toàn bộ kiểm thử chạy trên provider giả lập. Nghĩa là chưa trả lời được câu hỏi trung tâm: hệ thống đọc đúng bao nhiêu phần trăm các trường trên một tấm danh thiếp thật. Xem [báo cáo Ngày 9](Document/3-bao-cao/ngay-9.md).

| Hạng mục | Trạng thái |
| --- | --- |
| Bộ ảnh mẫu đã chụp | 0/40 — nhãn và trang in đã sẵn sàng |
| Đo chất lượng thật | Công cụ xong, chưa có số |
| Kiểm thử camera, HTTPS trên điện thoại | Chưa — cần thiết bị thật |
| Ngôn ngữ | Mã nguồn xử lý được cả 4 (Anh, Hàn, Nhật, Trung). Hàn và Trung **chưa có thẻ mẫu**, nên ở mức "không bị chặn" chứ chưa phải "đã kiểm chứng" |
| Phạm vi ảnh | Mỗi ảnh một thẻ, một mặt, bố cục ngang |
| Chưa hỗ trợ | Nhiều thẻ trong một ảnh, dịch tự động, chữ dọc nâng cao |

Tầng agentic mặc định **tắt** (`AGENT_ENABLED=false`). Bật lên thì ảnh mờ sẽ bị chặn trước khi gọi dịch vụ, OCR điểm thấp được thử lại với ảnh tăng tương phản, và thiếu tên/công ty thì đọc lại bằng prompt khác — tất cả trong một ngân sách retry có giới hạn.
