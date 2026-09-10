# Phiếu ghi chép nhà cung cấp OCR — Ngày 2

Mục 6 của kế hoạch Ngày 2 yêu cầu ghi lại nhà cung cấp, phiên bản, cách cấu hình, giới hạn và chi phí cần theo dõi. File này là nơi ghi.

**Trạng thái:** phần A (cài đặt) đã xong. Phần B, C, D **chưa điền** vì chưa có tài khoản dịch vụ — đây là việc phải làm khi có credentials.

---

## A. Thư viện đã cài (đã xác nhận)

| Thư viện | Phiên bản | Dùng để |
| --- | --- | --- |
| `google-cloud-vision` | 3.15.0 | OCR — feature `DOCUMENT_TEXT_DETECTION` |
| `google-genai` | 2.22.0 | Trích xuất trường có schema |
| Python | 3.11.9 | |

Cấu hình trong `backend/.env`:

```ini
OCR_PROVIDER=google
GOOGLE_APPLICATION_CREDENTIALS=./secrets/gcp-sa.json
OCR_LANGUAGE_HINTS=ja,en
OCR_TIMEOUT_S=20

EXTRACTOR=gemini
GEMINI_API_KEY=<khóa từ Google AI Studio>
GEMINI_MODEL=<xem phần B>
GEMINI_TEMPERATURE=0
```

`secrets/` đã bị `.gitignore` chặn.

---

## B. Chọn model Gemini — **cần điền**

Tên model Gemini thay đổi theo thời gian và khác nhau giữa các tài khoản. **Không đoán tên rồi hardcode** — sẽ gặp lỗi 404 khó chẩn đoán. Hỏi thẳng API:

```powershell
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py --list-models
```

Lệnh này liệt kê mọi model tài khoản bạn dùng được, kèm giới hạn token vào/ra. Chọn một model **có khả năng đọc ảnh (vision)** và điền vào `GEMINI_MODEL`.

Ghi lại kết quả tại đây:

| Mục | Giá trị |
| --- | --- |
| Model đã chọn | *(điền)* |
| Giới hạn token vào / ra | *(điền)* |
| Lý do chọn model này | *(điền — ví dụ: rẻ nhất trong nhóm đọc được ảnh)* |
| Ngày kiểm tra | *(điền)* |

---

## C. Kết quả chạy thật — **cần điền**

Chạy trên ít nhất 2 ảnh tiếng Anh và 2 ảnh tiếng Nhật:

```powershell
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py datasets\dev\ja\001.jpg datasets\dev\ja\002.jpg datasets\dev\en\001.jpg datasets\dev\en\002.jpg
```

Script tự in bảng tổng kết. Chép vào đây:

| Ảnh | Ký tự | OCR ms | Xuất ms | Khớp | Gần đúng | **Bị loại** |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | | |

**Cột "Bị loại" là chỉ số quan trọng nhất.** Đó là số trường Gemini trả về nhưng không đối chiếu được với văn bản OCR gốc — tức là dữ liệu model tự sinh. Con số này chính là cột "Tự sinh" của báo cáo Ngày 9.

Câu hỏi phải trả lời được sau khi chạy:

- [ ] Chữ Nhật hiển thị đúng trong terminal, không thành `?????` hay ô vuông?
- [ ] Vision có đọc được thẻ tiếng Nhật không? Chất lượng so với thẻ tiếng Anh?
- [ ] Gemini có bịa trường nào không? Bao nhiêu trên tổng số?
- [ ] Có trường nào bị bỏ sót dù rõ ràng có trên thẻ?
- [ ] Thời gian xử lý mỗi thẻ khoảng bao nhiêu?

---

## D. Giới hạn và chi phí cần theo dõi — **cần điền**

| Mục | Giá trị | Nguồn |
| --- | --- | --- |
| Vision — giá mỗi 1000 ảnh | *(điền)* | bảng giá Google Cloud |
| Vision — hạn mức miễn phí mỗi tháng | *(điền)* | |
| Vision — quota request/phút | *(điền)* | |
| Gemini — giá vào/ra mỗi 1M token | *(điền)* | bảng giá Gemini API |
| Gemini — hạn mức miễn phí | *(điền)* | |
| Ước tính chi phí cho 40 ảnh mẫu | *(điền)* | |
| Ngân sách tự đặt cho cả dự án | *(điền)* | |

**Vì sao phải ghi:** mỗi ảnh đi qua **hai** dịch vụ tính tiền. Bộ mẫu 40 ảnh sẽ chạy nhiều lần trong quá trình phát triển, không phải một lần. Biết trước con số giúp phát hiện sớm nếu có gì đó gọi API trong vòng lặp.

---

## E. Đường lui nếu không lấy được quyền truy cập

Đã chuẩn bị sẵn, không phải tìm phương án lúc bị kẹt:

| Tình huống | Đường lui | Hạn chế |
| --- | --- | --- |
| Không có Google Cloud project | Dùng Gemini API key đơn thuần (không cần GCP) làm cả OCR lẫn trích xuất | Mất `raw_text` độc lập, nên **grounding yếu đi đáng kể** — cả hai tầng cùng một model thì không còn bằng chứng độc lập để đối chiếu |
| Không có Gemini | `EXTRACTOR=heuristic` — bộ regex có sẵn | Bắt tốt email/điện thoại/website; kém với tên người và chức danh |
| Không có gì | `OCR_PROVIDER=mock` — chạy lại fixture đã lưu | Chỉ để phát triển giao diện, **không phải kết quả OCR** |

Đường lui đầu tiên có một cái giá cần hiểu rõ: kiến trúc hiện tại mạnh vì Vision đọc chữ (bằng chứng từ điểm ảnh) còn Gemini gán trường (mô hình sinh), rồi đối chiếu hai bên. Nếu để Gemini làm cả hai việc, nó tự chấm điểm chính mình.

---

## F. Nguồn tra cứu doanh nghiệp (mục 5 của Ngày 2) — **cần điền**

Phương án đã chốt: lấy domain từ website hoặc email trên thẻ, tải vài trang công khai, không dùng Search API trả phí.

Kiểm tra trước khi sang Ngày 6:

- [ ] Thử tải trang chủ của 2–3 công ty trong bộ mẫu bằng `httpx` — có bị chặn không?
- [ ] Các trang đó có `/about`, `/company` hoặc `/会社概要` không?
- [ ] `robots.txt` của chúng có cấm không?
- [ ] Bao nhiêu thẻ trong bộ mẫu **không có** website hay email công ty? (những thẻ này sẽ đi vào nhánh `not_found`, cần ít nhất một mẫu để kiểm thử)
