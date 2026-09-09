# Chuyển hóa danh thiếp thành hồ sơ đối tác chuẩn hóa

Ứng dụng web: chụp/tải ảnh danh thiếp → OCR (Anh + Nhật) → trích xuất trường có cấu trúc → chuẩn hóa → tra cứu bổ sung thông tin doanh nghiệp có dẫn nguồn → lưu hồ sơ tập trung, tìm kiếm và xuất dữ liệu.

Tài liệu: [đặc tả yêu cầu](Document/Bai-2-business-card-yeu-cau-chuan-hoa.md) · [kế hoạch 10 ngày](Document/Bai-2-noi-dung-va-ke-hoach-10-ngay.md) · [kế hoạch triển khai chi tiết](Document/Bai-2-ke-hoach-trien-khai-chi-tiet.md)

## Yêu cầu môi trường

- Python 3.11+
- Node.js 20+
- Git

## Cài đặt

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env      # rồi điền giá trị thật, xem bảng bên dưới

# Frontend
cd ..\frontend
npm install
Copy-Item .env.example .env      # để trống VITE_API_BASE_URL khi chạy dev
```

Trên macOS/Linux thay `.\.venv\Scripts\python.exe` bằng `.venv/bin/python` và `Copy-Item` bằng `cp`.

## Chạy

Cần **hai terminal**:

```powershell
# Terminal 1 — backend, cổng 8000
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend, cổng 5173
cd frontend
npm run dev
```

Mở http://localhost:5173. Vite proxy `/api` sang `http://127.0.0.1:8000`, nên frontend không cần biết URL backend và không dính CORS khi chạy dev.

Tài liệu API tự sinh: http://localhost:8000/docs

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

**`frontend/.env` chỉ được phép có `VITE_API_BASE_URL`.** Mọi biến `VITE_*` đều bị nhúng thẳng vào file JS gửi xuống trình duyệt — đặt API key ở đó là làm lộ khóa.

Kiểm tra cấu hình đã nhận chưa: `GET /api/health` trả về trạng thái sẵn sàng của từng dịch vụ mà không tiết lộ giá trị khóa. Banner đầu trang cũng hiển thị đúng thông tin này.

## Cơ sở dữ liệu

Bảng được tạo tự động khi backend khởi động. Muốn làm lại từ đầu: xóa `backend/data/app.db` rồi chạy lại.

## Kiểm thử

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

Test không gọi mạng thật — đặt `OCR_PROVIDER=mock` để dùng fixture.

Kiểm tra bộ nhãn dữ liệu mẫu: `python backend/scripts/check_labels.py` (xem [datasets/README.md](datasets/README.md)).

## Cấu trúc

```text
backend/app/       FastAPI: config, models, db, api/, services/
backend/tests/     pytest
backend/scripts/   công cụ chạy tay (thử OCR, kiểm tra nhãn, đo chất lượng)
frontend/src/      React: api/, components/, pages/
datasets/          ảnh mẫu (không commit) + labels.jsonl
Document/          đặc tả và kế hoạch
```

## Tình trạng hiện tại

Ngày 1/10 đã xong: khung dự án, schema dữ liệu đầy đủ, `/api/health`, frontend nối được backend, bộ khung dữ liệu mẫu.

Chưa làm: OCR thật (Ngày 2), chụp/tải ảnh (Ngày 3), trích xuất trường (Ngày 4), chuẩn hóa và màn hình duyệt (Ngày 5), tra cứu doanh nghiệp (Ngày 6), lưu/tìm kiếm/xuất (Ngày 7).

## Giới hạn đã biết

- Phạm vi MVP: tiếng Anh và tiếng Nhật. Đề gốc còn nêu tiếng Hàn và tiếng Trung.
- Mỗi ảnh xử lý một danh thiếp, một mặt, bố cục ngang.
- Chưa hỗ trợ: nhiều thẻ trong một ảnh, xử lý hàng loạt, dịch tự động, chữ dọc nâng cao.
