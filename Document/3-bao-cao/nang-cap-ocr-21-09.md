# Báo cáo nâng cấp bằng công nghệ miễn phí — 21/09/2026

**Kế hoạch:** [2-ke-hoach/nang-cap-ocr-mien-phi.md](../2-ke-hoach/nang-cap-ocr-mien-phi.md).
**Phạm vi đo:** 40 thẻ `dev` của bộ `_dryrun` (ảnh in kỹ thuật số sắc nét). **Đây không phải số nghiệm thu** — ảnh chụp thật sẽ cho số thấp hơn.

## 1. Kết luận trước, lý lẽ sau

| Việc | Quyết định | Căn cứ |
| --- | --- | --- |
| RapidOCR làm nhà cung cấp mặc định | **Không** | Cần biết trước ngôn ngữ từng thẻ; model tiếng Nhật không đọc được `@` |
| RapidOCR làm tuỳ chọn cho kho một ngôn ngữ | **Có** | Đọc Hangul đúng, đọc trường CJK tốt hơn Tesseract rõ rệt |
| Đổi sang model Gemini mới hơn | **Không, chưa** | `3.6-flash` lỗi hẳn; `3.7`/`3.8-flash` chạm hạn mức ở 37/40 thẻ |
| CI với 5 cổng kiểm | **Đã làm** | Ba cổng đã có sẵn nhưng chưa nối vào đâu |
| Rà soát lỗ hổng phụ thuộc | **Đã làm** | Không có lỗ hổng nào đã biết |
| Linter | **Đã làm, cố ý hẹp** | 20 lỗi thật đã sửa; bỏ qua 368 cảnh báo văn phong |

## 2. RapidOCR — đọc CJK tốt hơn, nhưng không thay thế được

Thêm nhà cung cấp thứ ba [`rapid.py`](../../backend/app/services/ocr/rapid.py): PP-OCR chạy trên ONNX Runtime, giấy phép Apache-2.0, không cần tài khoản, không cần thẻ.

### Thứ nó làm được

Trên thẻ Hàn `_dryrun/dev/ko/001.jpg`:

| | Tesseract | RapidOCR |
| --- | --- | --- |
| Tên `김민준` | `Oo] xX` | **`김민준`** |
| Công ty `주식회사 한울테크놀로지` | mất hẳn | **đọc đúng** |

Đo qua đường thật (Gemini đọc ảnh + văn bản OCR) trên 10 thẻ tiếng Nhật — ngôn ngữ duy nhất có gợi ý khớp trong lần đo đó, xem mục 4:

| Trường (ja) | Tesseract | RapidOCR |
| --- | --- | --- |
| Họ tên | 80% | **100%** |
| Chức danh | 60% | **100%** |
| Phòng ban | 78% | **100%** |
| Địa chỉ | 78% | **100%** |
| **Email** | **100%** | **0%** |
| Website | 86% | 71% |
| **Tổng** | 85,9% | 85,9% |

Hai cột tổng bằng nhau, nhưng hình dạng lỗi khác hẳn nhau: RapidOCR đọc chữ Nhật gần như hoàn hảo rồi đánh mất toàn bộ email.

### Vì sao email về 0%

Cùng một ảnh, cùng bộ phát hiện, chỉ đổi bộ nhận dạng:

```
JAPAN/PPOCRV4   ->  taro.yamadagexample.co.jp     ← '@' thành 'g'
KOREAN/PPOCRV5  ->  taro.yamada@example.co.jp     ← đúng
```

Bộ ký tự của model tiếng Nhật không có `@`. **Grounding không cứu được chuyện này**: nó chỉ chặn giá trị model tự bịa, còn giá trị OCR đọc sai thì vẫn "có bằng chứng" trong văn bản OCR. Ranh giới đó đã ghi từ Ngày 9 và lần này là một ví dụ sống.

### Vì sao không làm mặc định được

RapidOCR **mỗi ngôn ngữ một model**, chọn lúc khởi tạo. Tesseract nhận `jpn+eng+kor+chi_sim` trong một lời gọi. Quét một thẻ thì chưa biết nó là ngôn ngữ gì — đó chính là thứ `languages.guess_language` đoán **sau khi** có chữ. Cấu hình sai thì không có lỗi nào được báo, chỉ có kết quả sai.

Đã ghi cảnh báo này vào [README](../../README.md) và `backend/.env.example`, và **cố ý không đưa vào `requirements.txt` hay image Docker**.

## 3. Bộ phát hiện vùng chữ quan trọng hơn bộ nhận dạng

Phát hiện ngoài dự đoán. Với bộ phát hiện mặc định (v6 small), thẻ Hàn mất hẳn dòng địa chỉ — **9 dòng chỉ thấy 7**:

```
det mặc định : 주식회사 한울테크놀로지 | 부장 | 김민준 | TEL… | 휴대폰… | email | url
det v4/SERVER: … | 김민준 | (06236) 서울특별시 강남구 테헤란로 123 한울빌딩 7층 | TEL… ✅
```

Phép đo ghi cái sót đó là **"sót"**, nên nhìn bảng số sẽ tưởng bộ nhận dạng kém, trong khi nó chưa từng được nhìn thấy dòng ấy. Lựa chọn này đã khoá bằng test.

Đánh đổi: bộ phát hiện SERVER nặng 113 MB và **chậm hơn nhiều** — thời gian OCR mỗi thẻ tăng từ ~0,8 s (Tesseract) lên ~2,9 s.

## 4. Sai sót của chính phép đo — ghi lại để không lặp

Lần đo đầu tiên **không dùng được**, và lỗi nằm ở cách tôi viết provider: nó chọn model theo gợi ý ngôn ngữ **đầu tiên khớp**, `.env` đang để `OCR_LANGUAGE_HINTS=ja,en`, nên cả 40 thẻ của bốn ngôn ngữ đều bị đọc bằng model tiếng Nhật.

Dấu vết lộ ra ở chỗ email đạt **0% ở cả bốn ngôn ngữ** — một hình dạng quá đều để là ngẫu nhiên. Chạy tay lại thì model Hàn đọc email đúng, tức là 0% kia không đến từ chất lượng OCR mà từ cấu hình.

Bài học đã thành cảnh báo trong README: **gợi ý ngôn ngữ phải khớp với thẻ**, và sai thì im lặng chứ không báo lỗi.

## 5. Model Gemini mới — có, nhưng chưa dùng được

Tài khoản này liệt kê `gemini-3.5-flash`, `3.6-flash`, `3.7-flash`, `3.8-flash`. Kiểm từng cái bằng lời gọi thật thay vì tin danh sách:

| Model | Gọi thử | Đo 40 thẻ |
| --- | --- | --- |
| `gemini-3.5-flash-lite` (đang dùng) | OK | nền so sánh: ja 85,9% |
| `gemini-3.5-flash` | OK | chưa đo |
| `gemini-3.6-flash` | **lỗi** `EXTRACT_CALL_FAILED` | — |
| `gemini-3.7-flash` | OK | **chỉ 5/40 thẻ qua**, phần còn lại lỗi tạm thời |
| `gemini-3.8-flash` | — | **chỉ 3/40 thẻ qua**; 3 thẻ đó đạt 21/21 = 100% |

Con số 100% của `3.8-flash` hấp dẫn nhưng trên 3 thẻ thì không kết luận được gì. Điều kết luận được: **hạn mức miễn phí của các model mới không đủ để chạy một lượt đánh giá**, nên `flash-lite` vẫn là lựa chọn đúng cho đến khi có tài khoản trả phí.

## 6. Cổng kiểm tự động

[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) — năm cổng, chạy trên mỗi lần đẩy code:

| Cổng | Bắt loại lỗi nào | Trạng thái hôm nay |
| --- | --- | --- |
| `ruff check` | Biến không định nghĩa, import thừa, cú pháp hỏng | sạch (sau khi sửa 20 lỗi) |
| `pytest` | Hỏng chức năng | 560+ test xanh |
| `check_docs.py` | Số liệu tài liệu lệch mã nguồn | khớp |
| `check_secrets.py` | Khoá API bị commit nhầm | sạch |
| `pip-audit` | Lỗ hổng đã biết của phụ thuộc | không có |

Ba cổng giữa đã tồn tại từ trước và **đều trả mã thoát 1 khi có vấn đề** — chúng chỉ chưa được nối vào đâu. Không cài Tesseract trên CI, cố ý: các test cần nó tự bỏ qua.

Linter cấu hình **cố ý hẹp** ([ruff.toml](../../ruff.toml)): bật hết mặc định thì ra 388 cảnh báo, gần như toàn văn phong. Chỉ giữ `E9` + `F` — 20 lỗi thật, đã sửa hết. Trong đó có hai chỗ đáng kể: một biến gán rồi bỏ trong `webhook.py` (gọi hàm chỉ để nó ném lỗi khi địa chỉ trỏ vào mạng nội bộ — nay ghi rõ bằng chú thích) và một font thừa trong `make_card_sheets.py`.

## 7. Việc còn để lại

- **Ảnh chụp thật**: mọi số trên đây đo bằng ảnh in kỹ thuật số. 0/40 ảnh chụp thật vẫn là nút thắt cũ.
- **Hợp nhất hai nguồn OCR**: RapidOCR đọc CJK tốt hơn, Tesseract đọc ASCII tốt hơn. Chạy cả hai rồi ghép theo từng trường là hướng có cơ sở — nhưng gấp đôi thời gian OCR, và phải đo trước khi tin.
- **Google Vision / Azure F0**: đều miễn phí trong hạn mức đủ cho 80 thẻ, đều cần bật tài khoản thanh toán. Việc của chủ dự án, không phải việc lập trình.
