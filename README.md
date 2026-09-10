# Chuyển hóa danh thiếp thành hồ sơ đối tác chuẩn hóa

Ứng dụng web: chụp/tải ảnh danh thiếp → OCR (Anh + Nhật) → trích xuất trường có cấu trúc → chuẩn hóa → tra cứu bổ sung thông tin doanh nghiệp có dẫn nguồn → lưu hồ sơ tập trung, tìm kiếm và xuất dữ liệu.

Tài liệu: [đặc tả yêu cầu](Document/Bai-2-business-card-yeu-cau-chuan-hoa.md) · [kế hoạch 10 ngày](Document/Bai-2-noi-dung-va-ke-hoach-10-ngay.md) · [kế hoạch triển khai chi tiết](Document/Bai-2-ke-hoach-trien-khai-chi-tiet.md) · [báo cáo tiến độ](Document/Bao-cao-tien-do.md)

Kiến trúc: **Streamlit** (frontend) → **FastAPI** (backend) → **SQLite** + Google Vision/Gemini. Cả hai tầng đều là Python, dùng chung một môi trường ảo.

## Yêu cầu môi trường

- Python 3.11+
- Git

## Cài đặt

Một môi trường ảo duy nhất ở gốc dự án, dùng cho cả backend và frontend:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r frontend\requirements.txt
Copy-Item backend\.env.example backend\.env    # rồi điền giá trị thật, xem bảng bên dưới
```

Trên macOS/Linux thay `.\.venv\Scripts\python.exe` bằng `.venv/bin/python` và `Copy-Item` bằng `cp`.

## Chạy

Cần **hai terminal**, chạy từ thư mục gốc dự án:

```powershell
# Terminal 1 — backend, cổng 8000
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000 --app-dir backend

# Terminal 2 — frontend, cổng 8501
.\.venv\Scripts\streamlit.exe run frontend\streamlit_app.py
```

Mở http://localhost:8501. Tài liệu API tự sinh: http://localhost:8000/docs

Streamlit chạy phía máy chủ và gọi FastAPI bằng `httpx`, nên trình duyệt không bao giờ gọi thẳng backend — không có CORS, và không có biến cấu hình nào bị gửi xuống trình duyệt.

## Biến cấu hình

Toàn bộ nằm ở `backend/.env` (đã bị `.gitignore` chặn). Xem `backend/.env.example` để biết danh sách đầy đủ.

| Biến | Ý nghĩa | Mặc định |
| --- | --- | --- |
| `DATABASE_URL` | Đường dẫn SQLite | `sqlite:///./data/app.db` |
| `IMAGE_DIR` | Thư mục lưu ảnh danh thiếp | `./data/images` |
| `MAX_UPLOAD_BYTES` | Giới hạn dung lượng ảnh tải lên | 8 MB |
| `OCR_PROVIDER` | `google` hoặc `mock` (chạy offline bằng fixture) | `mock` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Đường dẫn tới JSON service account của Google Cloud | — |
| `EXTRACTOR` | `gemini` hoặc `heuristic` (regex, không cần mạng) | `heuristic` |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Cấu hình trích xuất trường | — |
| `ENRICH_*` | Giới hạn của bước tra cứu doanh nghiệp | xem `.env.example` |

Frontend chỉ đọc **một** biến: `API_BASE_URL` (mặc định `http://127.0.0.1:8000`). Nó không giữ khóa nào, nên không cần `.streamlit/secrets.toml`.

Kiểm tra cấu hình đã nhận chưa: `GET /api/health` trả về trạng thái sẵn sàng của từng dịch vụ mà không tiết lộ giá trị khóa. Sidebar của app hiển thị đúng thông tin này.

## Cơ sở dữ liệu

Bảng được tạo tự động khi backend khởi động. Muốn làm lại từ đầu: xóa `backend/data/app.db` rồi chạy lại.

## Kiểm thử

Một lệnh chạy cả backend lẫn frontend, từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Test không gọi mạng thật: backend dùng `OCR_PROVIDER=mock`, frontend dùng `AppTest` chạy app headless với backend được giả lập.

Kiểm tra bộ nhãn dữ liệu mẫu: `.\.venv\Scripts\python.exe backend\scripts\check_labels.py` (xem [datasets/README.md](datasets/README.md)).

## Cấu trúc

```text
backend/app/        FastAPI: config, models, db, api/, services/
backend/scripts/    công cụ chạy tay (thử OCR, kiểm tra nhãn, đo chất lượng)
frontend/           streamlit_app.py + app_pages/ + lib/
datasets/           ảnh mẫu (không commit) + labels.jsonl
Document/           đặc tả và kế hoạch
```

## Tình trạng hiện tại

**Ngày 1/10 xong:** khung dự án, schema 8 bảng, `/api/health`, frontend Streamlit 3 trang, bộ khung dữ liệu mẫu.

**Ngày 2/10 xong phần mã nguồn:** lớp trừu tượng OCR (Google Vision + mock), hai bộ trích xuất trường (Gemini có schema + regex dự phòng), chốt chặn grounding chống bịa dữ liệu, script spike `try_ocr.py`.

**Ngày 2 chưa đạt Định nghĩa hoàn thành:** chưa có tài khoản Google Cloud/Gemini nên **chưa chạy lời gọi OCR thật nào**. Hai fixture đang có ghi `provider: "synthetic"` — sinh từ văn bản đã biết, không phải kết quả OCR.

**Chưa làm:** nhận ảnh ở backend (Ngày 3), nối OCR vào ứng dụng (Ngày 4), chuẩn hóa và màn hình duyệt (Ngày 5), tra cứu doanh nghiệp (Ngày 6), lưu/tìm kiếm/xuất (Ngày 7).

### Chạy thử OCR

```powershell
# Xem model Gemini nào tài khoản của bạn dùng được
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py --list-models

# Chạy OCR + trích xuất trên ảnh thật, lưu fixture cho bộ test
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py datasets\dev\ja\001.jpg

# Sinh ảnh danh thiếp tổng hợp để thử đường ống khi chưa có ảnh thật
.\.venv\Scripts\python.exe backend\scripts\make_test_card.py
```

Xem [Document/ocr-provider-notes.md](Document/ocr-provider-notes.md) để biết cách chọn model và các giới hạn cần theo dõi.

## Giới hạn đã biết

- Phạm vi MVP: tiếng Anh và tiếng Nhật. Đề gốc còn nêu tiếng Hàn và tiếng Trung.
- Mỗi ảnh xử lý một danh thiếp, một mặt, bố cục ngang.
- Chưa hỗ trợ: nhiều thẻ trong một ảnh, xử lý hàng loạt, dịch tự động, chữ dọc nâng cao.
