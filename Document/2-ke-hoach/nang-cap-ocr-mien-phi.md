# Kế hoạch nâng cấp bằng công nghệ miễn phí — RapidOCR và CI

**Ngày lập:** 21/09/2026. **Trạng thái:** đang thực hiện.
**Điều kiện bắt đầu:** đã có bộ 80 thẻ bốn ngôn ngữ kèm nhãn chuẩn và `evaluate.py` chạy được. Không có hai thứ đó thì mọi so sánh dưới đây chỉ là cảm tính.

## 1. Vì sao nâng cấp, và nâng cấp cái gì

Ba số đo thật đang có, không phải phỏng đoán:

| Điểm đau | Số đo | Nguồn |
| --- | --- | --- |
| Tesseract đọc Hangul hỏng | `김민준` → `Oo] xX`, tên công ty mất hẳn | chạy thật 21/09 trên `_dryrun/dev/ko/001.jpg` |
| Gemini chiếm phần lớn thời gian chờ | 5,3–10,0 s mỗi thẻ, bằng 70–85% tổng | 7 bản quét ảnh chụp thật trong DB |
| Chưa có cổng kiểm tự động | 560 test + 2 script trả mã thoát 1, chưa nối vào đâu | không có thư mục `.github/` |

Nâng cấp đúng ba việc, xếp theo tỷ lệ *giá trị / công sức*:

1. **Thêm nhà cung cấp OCR RapidOCR** (Apache-2.0, ONNX, chạy CPU, không cần mạng khi đã có model).
2. **Đo Tesseract với RapidOCR trên cùng bộ 80 thẻ** rồi mới kết luận cái nào hơn.
3. **Dựng CI GitHub Actions** từ ba cổng kiểm đã có sẵn.

## 2. Việc KHÔNG làm trong đợt này, và vì sao

| Không làm | Lý do |
| --- | --- |
| Google Cloud Vision (1.000 đơn vị/tháng miễn phí) | Code đã viết xong và có test, nhưng vẫn phải bật tài khoản thanh toán. Đó là việc của chủ dự án, không phải việc lập trình. |
| Azure Document Intelligence F0 (500 trang/tháng) | Cùng lý do, cộng thêm phải viết một adapter mới. Để dành làm **mốc đối chứng** cho báo cáo, không phải nhà cung cấp chính. |
| PaddleOCR-VL (0.9B) | Mạnh hơn nhưng nặng hơn hẳn. Chỉ xét đến nếu RapidOCR đo ra vẫn chưa đủ. |
| SQLite FTS5 cho tìm kiếm | Hiện có **0 hồ sơ**. Tối ưu tìm kiếm khi chưa có gì để tìm là tối ưu tưởng tượng. |
| Alembic | Chỉ cần khi đổi schema trên dữ liệu thật. Chưa có dữ liệu thật. |
| Đưa RapidOCR vào image Docker | Đo trên máy trước. Chưa biết nó có hơn không mà đã làm image nặng thêm ~200 MB là làm ngược thứ tự. |

## 3. Kết quả thăm dò trước khi viết code

Đã cài thật (`rapidocr` 3.9.2 + `onnxruntime` 1.30.0) và chạy thử, **không** viết kế hoạch trên giả định.

Tổ hợp hợp lệ của `(ngôn ngữ, phiên bản, cỡ model)` — thư viện báo lỗi với mọi tổ hợp ngoài danh sách này:

```
JAPAN  : PPOCRV4/MOBILE
KOREAN : PPOCRV4/MOBILE, PPOCRV5/MOBILE
CH     : PPOCRV4|PPOCRV5 × MOBILE|SERVER
EN     : PPOCRV4|PPOCRV5 × MOBILE
```

Kết quả đọc thử (ảnh chạy khô, chữ in sắc nét — **không** phải số đo chất lượng):

| Thẻ | Model | Thời gian | Nhận xét |
| --- | --- | --- | --- |
| Hàn | KOREAN/v5 | 618 ms | `김민준`, `주식회사 한울테크놀로지` **đúng** — Tesseract đọc thành `Oo] xX`. Sót dòng phòng ban và địa chỉ. |
| Nhật | mặc định (v6/CH) | 809 ms | Email và URL đúng, nhưng ra `携带` (giản thể) thay vì `携帯`. |
| Nhật | JAPAN/v4 | 1.127 ms | `携帯` và `山田 太郎` đúng, nhưng email hỏng (`@`→`g`) và URL hỏng. |
| Trung | mặc định (v6/CH) | 566 ms | Đúng toàn bộ. |

**Phát hiện quan trọng:** không có model nào thắng mọi mặt. Model tiếng Nhật đọc Kanji tốt hơn nhưng đọc chữ Latin (email, URL) tệ hơn model mặc định. Đây chính là thứ phải **đo** chứ không chọn bằng cảm tính, và cũng là lý do bước 2 tồn tại.

**Lưu ý về grounding:** lỗi kiểu `@`→`g` là lỗi của OCR, **không** bị grounding chặn — grounding chỉ chặn model bịa giá trị không có trong văn bản OCR. OCR đọc sai thì giá trị sai vẫn "có bằng chứng". Ranh giới này đã được ghi nhận từ Ngày 9 và không thay đổi.

## 4. Thiết kế

**Nhà cung cấp mới** `backend/app/services/ocr/rapidocr.py`, cài đặt đúng `OcrProvider` Protocol đã có. Lớp trừu tượng này chính là thứ làm việc thêm nhà cung cấp trở nên rẻ: một file, cộng một nhánh trong `providers.py`.

- Chọn model **theo gợi ý ngôn ngữ** (`OCR_LANGUAGE_HINTS`): `ko` → KOREAN/v5, `ja` → JAPAN/v4, còn lại → mặc định.
- Trả `OcrResult` với `blocks` kèm toạ độ thật (RapidOCR trả về hộp bốn điểm) — Ngày 5 cần toạ độ để tô sáng vùng chữ trên ảnh.
- `confidence` lấy từ điểm số của từng dòng.
- Thiếu thư viện thì ném `OcrError("OCR_NOT_CONFIGURED", …)` kèm lệnh cài — giống hệt cách `tesseract.py` xử lý, không được để lỗi ImportError thô đi ra ngoài.
- Model tải về lần chạy đầu và nằm trong `site-packages`. Máy không có mạng ở lần chạy đầu sẽ hỏng — phải nói rõ trong README.

**CI** `.github/workflows/ci.yml`: `pytest`, `check_docs.py`, `check_secrets.py`. Cả ba đã trả mã thoát khác 0 khi có vấn đề nên không phải viết thêm gì. Test cần Tesseract sẽ tự bỏ qua trên máy CI không cài.

## 5. Định nghĩa hoàn thành

- [ ] `OCR_PROVIDER=rapidocr` chạy được đầy đủ luồng, có test không cần cài RapidOCR (giả lập, như `test_ocr_tesseract.py` làm với Tesseract).
- [ ] Chạy `evaluate.py` trên cùng bộ ảnh với hai nhà cung cấp, có bảng đối chiếu theo từng ngôn ngữ.
- [ ] Kết luận ghi bằng **số**, kể cả khi số nói RapidOCR thua.
- [ ] CI chạy được ba cổng kiểm.
- [ ] `check_docs.py` sạch, `check_secrets.py` sạch, toàn bộ test xanh.

## 6. Rủi ro đã biết

| Rủi ro | Xử lý |
| --- | --- |
| Model tải lúc chạy đầu, máy offline thì hỏng | Ghi rõ trong README; lỗi ném ra phải nói đúng nguyên nhân |
| Ảnh chạy khô quá sắc nét, số đo lạc quan | Số đo vẫn ghi là của `_dryrun`, **không** dùng làm số nghiệm thu |
| Thêm ~200 MB phụ thuộc | Chưa đưa vào image Docker; để tuỳ chọn cho tới khi có số |
| Model tiếng Nhật đọc Latin kém | Đo theo từng trường, không chỉ theo tổng |
