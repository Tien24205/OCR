# Báo cáo Ngày 8 — Kiểm thử tích hợp và các trường hợp hỏng

**Ngày thực hiện:** 14/09/2026
**Phạm vi:** ma trận 13 tình huống ở mục Ngày 8 của [kế hoạch triển khai chi tiết](../2-ke-hoach/trien-khai-chi-tiet.md).

---

## 1. Kết quả

Trong 13 dòng của ma trận: **9 dòng đã tự động hóa và đang pass**, 3 dòng cần người làm tay trên trình duyệt thật (chưa làm), 1 dòng cần ảnh chụp thật (chờ Ngày 15).

| # | Tình huống | Trạng thái | Kiểm bằng |
| --- | --- | --- | --- |
| 1 | Trọn luồng, không mất dữ liệu | **Đạt** | `test_01_tron_luong_nhieu_the_khong_mat_du_lieu` |
| 2 | Từ chối quyền camera | **Chưa** | Cần trình duyệt thật — mục 4 |
| 3 | Tệp `.txt` đổi đuôi `.jpg` | **Đạt** | `test_03_*`, `test_03b_*` |
| 4 | Ảnh vượt giới hạn dung lượng | **Đạt** | `test_04_*` |
| 5 | Ảnh mờ / nghiêng / chói | **Đạt (ảnh tổng hợp)** | `test_05_*` (4 biến thể), `test_05b_*` |
| 6 | Dịch vụ OCR lỗi giữa chừng | **Đạt** | `test_06_*`, `test_06b_*` |
| 7 | Website không tồn tại / timeout | **Đạt** | Đã có từ Ngày 6 |
| 8 | Nhấn Lưu hai lần | **Đạt** | Trong `test_01_*` + Ngày 7 |
| 9 | Quét lại đúng ảnh cũ | **Đạt** | `test_09_*` |
| 10 | Quét rò rỉ khóa | **Đạt** | `check_secrets.py` + 16 test |
| 11 | DevTools → Network | **Chưa** | Cần trình duyệt thật — mục 4 |
| 12 | Camera điện thoại qua HTTPS | **Chưa** | Cần thiết bị thật — mục 4 |
| 13 | Hai phiên không lẫn dữ liệu | **Đạt (mức backend)** | `test_13_*` |

**Tổng bộ test: 309 pass.**

---

## 2. Vì sao Ngày 8 không phải là "viết thêm test"

Ngày 3–7 đã test từng bộ phận. Nếu Ngày 8 chỉ test lại những thứ đó thì không thêm giá trị gì. Ngày 8 nhắm vào hai thứ khác:

**Toàn luồng dưới điều kiện xấu.** Từng bộ phận chạy đúng không có nghĩa là ghép lại chạy đúng. `test_01` đi hết chặng ảnh → OCR → bản nháp → người sửa → hồ sơ → tìm kiếm → xuất, rồi kiểm tra ba thứ cùng lúc: sửa của người dùng còn nguyên, **bằng chứng OCR gốc còn nguyên**, và chữ Nhật không vỡ khi xuất.

**Những thứ chưa ai test.** Dòng 10 (rò rỉ khóa) và dòng 5 (ảnh xuống cấp) trước đó không có test nào.

---

## 3. Hai hạng mục đáng nói

### 3.1 Bộ quét rò rỉ khóa — vì sao không dùng `grep`

Kế hoạch ghi `grep -ri "AIza|private_key|BEGIN PRIVATE"`. Lệnh đó có hai vấn đề:

**Nó báo động giả ở chính tài liệu.** File kế hoạch chứa chuỗi `AIza` để mô tả phép kiểm tra, nên `grep` luôn tìm thấy. Người đọc sẽ quen dần với việc bỏ qua cảnh báo — đến khi có khóa thật thì cũng bỏ qua nốt. Đây là cách một biện pháp an toàn tự vô hiệu hóa.

**Nó chỉ bắt được ba dạng.** Khóa Gemini, service account JSON, token Bearer và khóa viết thẳng vào mã nguồn có hình dạng khác nhau.

[`check_secrets.py`](../../backend/scripts/check_secrets.py) khớp theo **hình dạng** của khóa chứ không theo từ khóa: nhắc `AIza` trong tài liệu thì không sao, còn `AIzaSy...` đủ 39 ký tự thì bị bắt. Có 7 mẫu, bỏ qua file nhị phân, và che bớt giá trị khi in ra để bản thân báo cáo không làm lộ khóa.

Bộ test chứng minh nó **bắt được** (6 test) và **không báo động giả** (10 test). Một bộ quét luôn báo "sạch" thì vô dụng, và nguy hiểm hơn không có gì vì tạo cảm giác an toàn giả.

**Lỗi tìm được trong lúc viết:** pattern ban đầu dùng `\b(?:api_?key|...)`. Nhưng `_` là ký tự từ, nên `\b` không khớp bên trong `GEMINI_API_KEY` — tức là bỏ sót đúng cách đặt tên phổ biến nhất. Test bắt được và đã sửa.

Chạy: `python backend/scripts/check_secrets.py --all`. Trả mã thoát 1 nếu tìm thấy gì, dùng được trong CI.

### 3.2 Ảnh xuống cấp — bảo đảm cốt lõi của dự án

`test_05b` là test quan trọng nhất của Ngày 8. Nó mô phỏng đúng tình huống nguy hiểm nhất: **ảnh mờ nên OCR chỉ đọc được một phần, nhưng mô hình vẫn trả về đầy đủ trường.**

Trong test, OCR chỉ đọc được 2 dòng (tên công ty và họ tên), còn bộ trích xuất trả thêm một email và một số điện thoại **không hề có trong văn bản OCR**. Kết quả phải là:

- Hai trường bịa ra **bị loại khỏi bản nháp**
- Nhưng bằng chứng về việc chúng bị loại **vẫn được giữ** trong `grounding_json` với verdict `unverified`

Vế thứ hai cũng quan trọng ngang vế thứ nhất: nếu trường bị loại biến mất không dấu vết thì Ngày 9 không đo được tỷ lệ mô hình tự sinh dữ liệu.

Bốn biến thể ảnh xuống cấp (mờ, nghiêng, chói đèn, mờ + nghiêng) được sinh bằng Pillow, nên phần tiếp nhận ảnh — kiểm tra định dạng, xoay theo EXIF, lưu theo SHA-256 — cũng được chạy thật.

---

## 4. Ba dòng cần làm tay — **chưa thực hiện**

Không tự động hóa được vì cần trình duyệt và thiết bị thật. Làm khi chạy demo.

### Dòng 2 — Từ chối quyền camera

1. Mở http://localhost:8501 → trang **Quét thẻ** → chọn **Chụp bằng camera**
2. Trình duyệt hỏi quyền → bấm **Chặn / Block**
3. **Kỳ vọng:** có thông báo rõ ràng, không phải màn hình trắng; chuyển sang **Tải ảnh lên** vẫn dùng được bình thường

### Dòng 11 — DevTools → Network

1. Mở DevTools (F12) → tab Network → dùng app: tải ảnh, xem bản nháp, lưu hồ sơ
2. **Kỳ vọng:** chỉ thấy WebSocket của Streamlit và tài nguyên tĩnh. **Không có request nào đi tới `googleapis.com` hay `generativelanguage.googleapis.com`**
3. Lọc theo `AIza` trong tab Network → không có kết quả

Đây là kiểm chứng trực quan cho kiến trúc: Streamlit gọi FastAPI từ phía máy chủ, nên trình duyệt không bao giờ chạm tới Google.

### Dòng 12 — Camera điện thoại qua HTTPS

1. `ngrok http 8501` (hoặc chứng chỉ tự ký)
2. Mở link HTTPS trên điện thoại → **Quét thẻ** → chụp một danh thiếp
3. **Kỳ vọng:** camera sau được dùng, ảnh gửi lên được
4. **Kiểm tra riêng:** ảnh **không bị lật gương**. Chụp một thẻ có chữ rồi đọc `raw_text` — widget hiển thị preview dạng gương như mọi ứng dụng camera, nhưng bytes trả về thì không. Đừng tin vào preview.

---

## 5. Giới hạn của kết quả này

- **Dòng 5 dùng ảnh tổng hợp**, không phải ảnh chụp thật. Ảnh sinh bằng Pillow có nhiễu đều và không có bóng tay, vân giấy hay lệch tiêu cự cục bộ. Phải chạy lại trên ảnh chụp thật ở Ngày 15.
- **Dòng 1 chạy với provider giả lập.** Nó chứng minh luồng không mất dữ liệu, không chứng minh OCR đọc đúng.
- **Dòng 13 chỉ kiểm ở mức backend.** Hai bản quét không lẫn dữ liệu sang nhau; còn việc `st.session_state` có cách ly giữa hai tab hay không thì phải mở hai tab thật để xác nhận.
- Dòng 2, 11, 12 **chưa làm**.

Theo Định nghĩa hoàn thành của kế hoạch — "13/13 dòng đạt" — **Ngày 8 chưa đạt đủ**. Nhưng điều kiện chặn quan trọng nhất thì đã thỏa: *"còn lỗi mất dữ liệu thì không được sang ngày 9"* — không tìm thấy lỗi mất dữ liệu nào.

---

## 6. Thứ tự sửa lỗi đã áp dụng

Kế hoạch quy định: mất dữ liệu → hỏng luồng chính → sai dữ liệu → khó dùng → hình thức.

Trong lượt này không phát hiện lỗi mất dữ liệu hay hỏng luồng chính. Hai lỗi đã sửa đều thuộc nhóm "sai dữ liệu":

| Lỗi | Ảnh hưởng |
| --- | --- |
| `\b` trong pattern quét khóa bỏ sót `GEMINI_API_KEY` | Khóa bị viết thẳng vào mã nguồn có thể lọt qua |
| `scan()` vỡ với đường dẫn ngoài repo | Không dùng được công cụ trên thư mục khác |

---

## 7. Cách chạy lại

```powershell
# Toàn bộ ma trận tự động
.\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_failure_matrix_day8.py -v

# Riêng phần quét rò rỉ khóa
.\.venv\Scripts\python.exe backend\scripts\check_secrets.py --all

# Toàn bộ bộ test
.\.venv\Scripts\python.exe -m pytest
```
