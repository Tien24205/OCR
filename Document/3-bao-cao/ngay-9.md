# Báo cáo Ngày 9 — Đo chất lượng

**Ngày thực hiện:** 14/09/2026
**Phạm vi:** mục Ngày 9 của [kế hoạch triển khai chi tiết](../2-ke-hoach/trien-khai-chi-tiet.md).

---

## 1. Kết luận — **Ngày 9 chưa đạt**

Định nghĩa hoàn thành của Ngày 9 là: *"`reports/evaluation.md` có số thật"* và *"không ghi con số nào chưa đo"*.

**Chưa có số thật, vì hai lý do nằm ngoài mã nguồn:**

| Điều kiện | Trạng thái |
| --- | --- |
| Tài khoản Google Vision + Gemini | Chưa có |
| 40 ảnh danh thiếp đã chụp | 0/40 — nhãn và trang in đã sẵn sàng, chưa in |

Không có hai thứ đó thì mọi con số sinh ra đều là số của bộ regex chạy trên ảnh số sắc nét — **không phản ánh hệ thống thật**, và đưa vào báo cáo sẽ là gây hiểu nhầm.

**Cái đã hoàn thành:** toàn bộ công cụ đo, đã chạy thông đầu-cuối và có test. Khi có credentials và ảnh, Ngày 9 là **một lệnh**.

---

## 2. Đối chiếu từng mục của Ngày 9

| Mục trong kế hoạch | Trạng thái |
| --- | --- |
| `datasets/labels.jsonl` cho 10 mẫu eval Anh + 10 Nhật | **Xong** — 40 nhãn, sinh từ chính dữ liệu vẽ thẻ nên không thể sai |
| `scripts/evaluate.py` đọc kết quả **trước khi sửa tay** | **Xong** |
| Xuất `reports/evaluation.md` + `evaluation.csv` | **Xong** |
| Quy tắc so sánh chốt trước khi nhìn kết quả | **Xong** — trong mã nguồn, có 22 test khóa lại |
| Bảng 4 cột Đúng / Sai / Bỏ sót / **Tự sinh** cho mỗi (trường × ngôn ngữ) | **Xong** |
| Ghi `ms_ocr`, `ms_extract` | **Xong** |
| Thời gian tra cứu, thời gian sửa tay | **Chưa** — xem mục 5 |
| Kiểm tra thông tin bổ sung đúng doanh nghiệp và có URL hỗ trợ | **Chưa** — cần tra cứu thật |
| 2 ví dụ thành công + 2 ví dụ thất bại | Công cụ **đã có**; chưa có số thật để điền |
| Ghi rõ nếu bộ eval bị "nhiễm" | **Xong** — báo cáo tự dán cảnh báo |

---

## 3. Quy tắc so sánh — chốt trước khi đo

Nằm trong [`evaluation.py`](../../backend/app/services/evaluation.py), không phải quyết định tùy hứng lúc viết báo cáo.

| Trường | Quy tắc |
| --- | --- |
| Email | bỏ khoảng trắng, hạ thấp toàn bộ |
| Điện thoại | chỉ giữ chữ số |
| Website | bỏ scheme, bỏ `www.`, bỏ `/` cuối |
| Tên, công ty, chức danh, phòng ban | NFKC + casefold + bỏ khoảng trắng, **khớp chính xác** |
| Địa chỉ | như trên, chấp nhận khớp ≥ 90% ký tự |

**Vì sao đặt trong mã nguồn có test:** kế hoạch cấm nới lỏng quy tắc sau khi thấy điểm thấp. Để quy tắc trong đầu thì không có gì ngăn việc đó. Để trong test thì muốn nới lỏng phải sửa test, và việc sửa nằm trong lịch sử Git.

### Vì sao "Sai" và "Tự sinh" là hai cột riêng

Đây là điểm phân biệt quan trọng nhất của cả phép đo:

- **Sai** — thẻ *có* trường đó, máy đọc nhầm. Lỗi của OCR hoặc trích xuất.
- **Tự sinh** — thẻ *không hề có* trường đó, máy vẫn trả về. **Dữ liệu bịa ra.**

Gộp hai cột này lại sẽ che mất chỉ số quan trọng nhất của bài. Một hệ thống đọc sai 20% email vẫn dùng được; một hệ thống bịa ra 5% email thì không, vì người dùng không có cách nào biết cái nào thật.

### Đo chính chốt chặn grounding

Báo cáo còn đo: trong số giá trị grounding loại bỏ, bao nhiêu là **loại nhầm** giá trị có thật trên thẻ. Không có con số này thì không biết ngưỡng `_FUZZY_THRESHOLD = 0.90` đặt đúng hay quá chặt — và một ngưỡng quá chặt sẽ âm thầm vứt đi dữ liệu đúng.

---

## 4. Kiểm chứng công cụ — chạy khô

Chưa có ảnh chụp, nên đã chạy toàn bộ đường đo trên ảnh cắt từ trang A4 (`datasets/_dryrun/`) để chứng minh công cụ hoạt động.

```
NGÔN NGỮ    CÓ THẬT   ĐÚNG   SAI   SÓT  TỰ SINH   TỶ LỆ
en               78     40     1    38        0   51.3%
ja               78     52     0    26        0   66.7%
```

> **Những con số này KHÔNG phải kết quả nghiệm thu.** Chúng là của bộ trích xuất regex chạy trên ảnh số sắc nét tuyệt đối. Báo cáo sinh ra tự dán hai cảnh báo về điều này.

Dù vậy chúng nói được ba điều có ích:

**Công cụ đo chạy đúng.** Hồ sơ lỗi khớp chính xác với giới hạn đã ghi của bộ regex: email 100%, điện thoại 100%, website 100% — còn họ tên 0% và địa chỉ 0%, vì regex không tách được tên người khỏi chức danh trên cùng một dòng.

**Cột "Tự sinh" bằng 0.** Chuỗi grounding không bịa gì cả — đúng như thiết kế.

**Chênh lệch Anh/Nhật có lý do.** Tiếng Nhật cao hơn (66.7% so với 51.3%) vì tên công ty tiếng Nhật có dấu hiệu rõ (`株式会社`, `有限会社`) mà regex bắt được; tên công ty tiếng Anh thì không có dấu hiệu tương đương.

---

## 5. Hai mục chưa làm được và vì sao

### Thời gian tra cứu và thời gian sửa tay

`evaluate.py` đo `ms_ocr` và `ms_extract`. Hai thời gian còn lại chưa đo:

- **Thời gian tra cứu doanh nghiệp** cần gọi mạng thật tới website thật. Đo trên fixture sẽ ra con số vô nghĩa.
- **Thời gian sửa tay** cần người ngồi sửa 40 thẻ và bấm giờ. Không tự động hóa được; đây là phép đo về con người, không phải về hệ thống.

### Thông tin bổ sung có đúng doanh nghiệp không

Kế hoạch yêu cầu kiểm tra thông tin tra cứu *"thực sự được URL nguồn hỗ trợ hay không"*. Hệ thống đã ép mỗi khẳng định phải kèm đoạn trích nguyên văn từ trang nguồn, và validator loại bỏ khẳng định nào không có. Nhưng việc **đoạn trích đó có thực sự chứng minh điều được khẳng định hay không** thì cần người đọc — máy chỉ kiểm được là đoạn trích có tồn tại trên trang.

Làm khi có tra cứu thật: mở 5 hồ sơ, bấm vào từng URL nguồn, xác nhận trang đó đúng là của doanh nghiệp trên thẻ và có nói điều được ghi.

---

## 6. Cách chạy khi có ảnh và credentials

```powershell
# 1. Xác nhận cấu hình - chỉ tốn 2 lời gọi dịch vụ
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py --check

# 2. Trong lúc phát triển, đo trên bộ dev
.\.venv\Scripts\python.exe backend\scripts\evaluate.py --split dev

# 3. So sánh Gemini với bộ regex (dùng chung một lần gọi OCR)
.\.venv\Scripts\python.exe backend\scripts\evaluate.py --split dev --compare

# 4. Số liệu báo cáo - CHỈ CHẠY MỘT LẦN
.\.venv\Scripts\python.exe backend\scripts\evaluate.py --split eval
```

### Kỷ luật đo lường

Bộ `eval/` chỉ giữ giá trị nếu **chưa từng được dùng để sửa mã nguồn**. Mỗi lần nhìn kết quả trên một ảnh eval rồi chỉnh code cho nó chạy đúng, ảnh đó mất giá trị đánh giá — và nếu làm với cả bộ thì con số cuối cùng chỉ đo được khả năng ghi nhớ, không đo được khả năng đọc thẻ mới.

Trong quá trình phát triển dùng `--split dev`. Nếu lỡ sửa code dựa trên bộ eval, phải ghi rõ trong báo cáo là bộ đó đã bị "nhiễm".

---

## 7. Điều cần nói thẳng

Dự án hiện có 313 test xanh, 18 endpoint, luồng nghiệp vụ đầy đủ và một tầng agentic có nhánh rẽ thật. Nhưng **chưa có một lời gọi Google Vision hay Gemini nào trong toàn bộ dự án**.

Nghĩa là câu hỏi trung tâm của đề bài — *hệ thống đọc đúng bao nhiêu phần trăm các trường trên một tấm danh thiếp tiếng Nhật* — vẫn chưa có câu trả lời.

Ngày 9 là ngày trả lời câu hỏi đó. Công cụ đã xong; còn thiếu đúng hai thứ mà chỉ người thực hiện làm được: **lấy API key** và **in, cắt, chụp 40 tấm thẻ**.
