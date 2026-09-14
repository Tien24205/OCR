# Báo cáo Ngày 3 — Tiếp nhận ảnh danh thiếp

**Ngày thực hiện:** 11/09/2026.
**Phạm vi:** Ngày 3 trong kế hoạch 10 ngày và kế hoạch triển khai chi tiết. Tiếp tục theo yêu cầu người dùng dù Ngày 2 còn chờ kiểm chứng dịch vụ thật.

## 1. Kết quả

Đã triển khai phần mềm nhận ảnh từ hai nhánh camera/upload, kiểm tra tệp, xử lý EXIF, lưu ảnh theo SHA-256 và tạo bản ghi `scans` trạng thái `pending`. **46 test pass** (27 test trước + 19 trường hợp mới); không gọi dịch vụ OCR.

**Chưa đóng toàn bộ nghiệm thu Ngày 3:** camera/trình duyệt thật chưa được kiểm tra trên thiết bị. Hai nhánh giao diện được chạy bằng AppTest với bytes giả lập; backend được kiểm tra bằng multipart TestClient với SQLite và thư mục ảnh tạm thật. Không gọi kết quả này là đã xác nhận camera vật lý không lật chữ.

## 2. Đã làm gì và vì sao?

| Thành phần | Thay đổi | Vì sao |
| --- | --- | --- |
| `backend/app/services/images.py` | Kiểm tra JPEG/PNG bằng Pillow, verify rồi mở lại/decode đầy đủ | Không tin đuôi tệp hoặc MIME trình duyệt; bắt cả tệp giả và ảnh bị cắt/hỏng |
| Giới hạn đầu vào | Tối đa 8 MiB (8 × 1024 × 1024 byte theo cấu hình), cạnh tối đa 6000px; ảnh tĩnh một khung | Theo hợp đồng Ngày 3; tránh giải mã ảnh ngoài giới hạn |
| EXIF | Áp dụng hướng EXIF cho JPEG/PNG trước khi lưu | Ảnh điện thoại có thể lưu pixel và hướng hiển thị khác nhau |
| Kho ảnh | Ghi tệp tạm rồi công bố bằng tên SHA-256; tên upload không tham gia đường dẫn | Tránh tệp dở dang, đường dẫn tùy ý và lưu lặp cùng nội dung ảnh |
| `POST /api/scans` | Multipart `file`; trả `201 {id, status: "pending"}` sau khi lưu và commit DB | Có đầu vào bền vững cho bước OCR Ngày 4 |
| Lỗi | 400 cho ảnh sai/hỏng/ngoài kích thước, 413 quá dung lượng, 500 lưu thất bại | Người dùng nhận thông báo phù hợp; không báo thành công khi DB lỗi |
| `capture.py` | Xem trước theo EXIF, báo lỗi ảnh, nút “Lưu ảnh”, xác nhận scan đã lưu | Phản ánh đúng chức năng hiện có; chưa chuyển sang màn hình polling chưa có API |
| `.streamlit/config.toml` | Chuyển từ `frontend/.streamlit` về gốc repo | Khớp cách khởi chạy README; đã xác nhận cấu hình hiệu lực là 8 MB |

Không nối OCR, không sửa grounding/credentials, không làm GET scan, retry OCR, tra cứu hoặc hồ sơ. Các hạng mục đó giữ nguyên trạng thái trong báo cáo Ngày 1–2 và kế hoạch ngày tiếp theo.

## 3. Quy ước ảnh lưu

- Tên tệp là SHA-256 của **bytes thực lưu sau xử lý EXIF**; `image_bytes` và `image_mime` mô tả chính tệp đó.
- Không có EXIF cần chuyển hướng: giữ nguyên bytes để không tái nén ảnh đã đúng chiều.
- Có orientation 2–8: chuyển hướng theo EXIF, mã hóa lại đúng JPEG/PNG và bỏ orientation đã áp dụng; tránh xoay lần thứ hai ở bước đọc tiếp.
- Không lật ảnh ngang tùy tiện. Với EXIF có chỉ dẫn phản chiếu, tuân theo chỉ dẫn đó.
- Ảnh sau chuyển hướng cũng phải nằm trong giới hạn dung lượng. JPEG cần xoay được mã hóa lại quality 95; đây không phải phép xoay JPEG không mất dữ liệu.
- Tải lại cùng ảnh có thể tạo scan mới nhưng dùng chung tệp hash. Chống tạo hồ sơ trùng/idempotency thuộc kế hoạch sau.
- Nếu ảnh đã ghi xong nhưng DB commit thất bại: rollback DB, báo lỗi; tệp hash hoàn chỉnh có thể còn lại để tái sử dụng. Không xóa tệp có thể đang được scan khác sử dụng. Chưa xây cơ chế dọn ảnh mồ côi trong phạm vi Ngày 3.

## 4. Kiểm thử đã chạy

Lệnh từ gốc repo:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Kết quả: **46 passed**, 2 cảnh báo deprecation từ thư viện test; không có test thất bại. `git diff --check` không có lỗi whitespace.

| Nhóm | Bằng chứng |
| --- | --- |
| JPEG/PNG hợp lệ | HTTP 201, scan pending, DB lưu MIME thật/hash/dung lượng đúng; tệp không cần xoay giữ nguyên bytes |
| MIME/tên tệp giả | Header text/plain và filename tùy ý không quyết định loại hoặc đường dẫn ảnh |
| Đầu vào không hợp lệ | Tệp rỗng, text đổi đuôi jpg, GIF, PNG bị cắt, cạnh 6001px đều bị chặn; không tạo scan/ảnh |
| Dung lượng | Quá 8 MiB trả 413; đúng ranh giới byte cấu hình được nhận |
| EXIF PNG | Orientation 6 cho đúng kích thước và vị trí pixel, bỏ orientation; gửi ảnh đã xoay lần nữa không xoay tiếp |
| EXIF JPEG | Orientation 8 cho đúng chiều/kích thước và MIME |
| Lưu trùng nội dung | Hai scan, một tệp ảnh |
| Lỗi lưu | Lỗi đĩa/DB không trả thành công, không lộ thông tin lỗi nội bộ, không để scan chưa commit |
| Camera/upload qua AppTest | Cả hai nguồn chuyển đúng bytes cho lớp API sau click; rerun thông thường không gửi lại |
| Lỗi giao diện | Ảnh không đọc được hiện thông báo; API thất bại không hiện thành công |

Test mới nằm ở `backend/tests/integration/test_upload_day3.py` (15 trường hợp) và `frontend/tests/test_capture_day3.py` (4 trường hợp). Không bổ sung dependency.

## 5. Checklist kiểm tra thủ công còn lại

Chạy backend và frontend từ `C:\Users\dotie\OneDrive\Desktop\OCR\OCR` ở hai terminal:

```powershell
# Terminal 1
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000 --app-dir backend

# Terminal 2
.\.venv\Scripts\python.exe -m streamlit run frontend\streamlit_app.py
```

Mở `http://localhost:8501`:

- [ ] Chọn camera, cấp quyền, chụp thẻ có chữ dễ phân biệt trái/phải; kiểm tra bản ảnh lưu trên đĩa không bị lật chữ so với thẻ (không chỉ nhìn live preview).
- [ ] Bấm “Lưu ảnh”, ghi mã scan; kiểm tra DB có trạng thái pending và tệp hash tồn tại trong `backend/data/images`.
- [ ] Từ chối camera hoặc không có camera, chuyển sang upload và lưu được JPEG/PNG.
- [ ] Thử ảnh điện thoại có EXIF, xác nhận bản lưu đúng chiều.
- [ ] Nếu thử camera qua điện thoại truy cập máy chủ khác, dùng HTTPS và kiểm tra quyền trình duyệt thực tế.

Chưa có GET image ở Ngày 3. Có thể tìm tệp hash bằng DB Browser for SQLite hoặc Python dựa trên mã scan, mở ảnh bằng trình xem ảnh. OCR để đối chiếu `raw_text` cần đợi Ngày 4 và dịch vụ thật; Ngày 3 chỉ xác nhận hướng ảnh bằng mắt.

## 6. Câu báo cáo ngắn

> Ngày 3 đã hoàn thành phần mềm tiếp nhận ảnh: camera/upload, kiểm tra JPEG/PNG, giới hạn dung lượng/kích thước, xử lý EXIF, lưu ảnh theo SHA-256 và tạo scan pending. Bộ test tăng từ 27 lên 46 và đều pass. Chưa triển khai OCR của Ngày 4. Kiểm tra camera vật lý và luồng trình duyệt thật còn chờ thực hiện nên chưa đánh dấu toàn bộ DoD Ngày 3 đạt.

Tham khảo kỹ thuật: [FastAPI UploadFile](https://fastapi.tiangolo.com/tutorial/request-files/), [Pillow EXIF transpose](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html#PIL.ImageOps.exif_transpose).
