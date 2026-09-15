# Kịch bản demo 5–7 phút

> **⚠ BẢN CŨ — đừng dùng để demo.**
> Viết khi dự án mới xong Ngày 10. Con số "313 test" trong tài liệu này là của
> thời điểm đó và nay đã sai. Từ Ngày 10 tới nay có thêm điều phối agentic,
> điểm tin cậy, trang tổng quan, tải hàng loạt, webhook và OCR cục bộ — demo
> theo bản này sẽ bỏ sót đúng những phần đáng xem nhất.
>
> **Bản đang dùng: [ngay-21-demo.md](ngay-21-demo.md)** (7–10 phút).
> Giữ tệp này lại chỉ để đối chiếu lịch sử.

Chuẩn bị trước, đừng làm trong lúc demo:

```powershell
# 1. Hai terminal chạy sẵn
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000 --app-dir backend
.\.venv\Scripts\streamlit.exe run frontend\streamlit_app.py

# 2. Nếu chưa có API key — sinh bộ ảnh dùng được ngay
.\.venv\Scripts\python.exe backend\scripts\make_card_sheets.py --crop

# 3. In sẵn 2 thẻ giấy (1 Anh, 1 Nhật) để demo camera
```

Mở sẵn hai tab: ứng dụng ở `localhost:8501`, tài liệu API ở `localhost:8000/docs`.

---

## 0. Mở đầu — 30 giây

> "Sau một hội thảo, người ta cầm về vài chục tấm danh thiếp. Nhập tay mất thời gian và dễ sai, tra cứu doanh nghiệp phải làm riêng, dữ liệu lưu rải rác nên không tìm lại được. Đây là hệ thống biến tấm thẻ giấy thành hồ sơ đối tác có cấu trúc, có dẫn nguồn."

## 1. Chụp thẻ tiếng Anh — 1 phút

Trang **Quét thẻ** → **Chụp bằng camera** → đưa thẻ vào khung → chụp → **Gửi để nhận diện**.

Chuyển sang trang **Kiểm tra**, chỉ vào:

- Ảnh gốc bên trái, dữ liệu bên phải — để đối chiếu được
- Cờ trạng thái từng dòng: xanh là khớp OCR, vàng là cần kiểm tra
- Nếu bật chế độ agentic: mở khối **Quyết định của Agentic Pipeline**

> "Mỗi trường đều truy về được đúng đoạn chữ trên ảnh."

## 2. Tải thẻ tiếng Nhật — 1 phút

**Quét thẻ** → **Tải ảnh lên** → chọn một thẻ tiếng Nhật.

Chỉ vào:

- Kanji hiển thị đúng, không thành ô vuông
- Họ tên giữ nguyên thứ tự bản địa — không bị đảo thành kiểu phương Tây
- Số điện thoại giữ số 0 đầu và số máy lẻ tách riêng

> "Tên tiếng Nhật giữ nguyên bản. Hệ thống không tự phiên âm hay dịch — đó là thêm thông tin không có trên thẻ."

## 3. Sửa một trường OCR đọc sai — 1 phút

Sửa một ô trong form → **Lưu bản nháp**.

Chỉ vào: dòng vừa sửa đổi nhãn thành **Người dùng sửa**.

> "Sửa của người dùng và kết quả của máy được lưu tách biệt. Bằng chứng OCR gốc không bao giờ bị ghi đè — nếu ghi đè thì sẽ không đo được chất lượng tự động nữa."

Nếu tiện, mở `/docs` → `GET /api/scans/{id}` để cho thấy `raw_text` vẫn còn nguyên.

## 4. Tra cứu doanh nghiệp — 1,5 phút

Bấm **Tra cứu doanh nghiệp**. Khi có kết quả, chỉ vào:

- Mỗi khẳng định kèm **URL nguồn bấm được** và **thời điểm tra cứu**
- Đoạn trích nguyên văn từ trang nguồn
- Nút Duyệt / Bác bỏ

Bấm vào URL, mở trang thật.

> "Mỗi thông tin bổ sung phải có đoạn trích nguyên văn từ trang nguồn. Đoạn nào không tìm thấy trên trang thì khẳng định bị loại — hệ thống không được phép nói điều nguồn không nói."

Nếu có thẻ không ghi website, demo luôn: kết quả là **chưa tìm thấy**, và dữ liệu OCR không mất gì.

## 5. Lưu và tìm lại — 1 phút

**Xác nhận lưu hồ sơ** → sang trang **Hồ sơ** → gõ một từ khóa **tiếng Nhật** vào ô tìm kiếm.

Chỉ vào: tìm được bằng chữ Nhật. Mở chi tiết. Bấm **Chuẩn bị file xuất** → tải CSV → mở bằng Excel, chữ Nhật không vỡ.

> "CSV ghi kèm BOM UTF-8. Không có nó thì Excel trên Windows đọc sai toàn bộ chữ Nhật."

## 6. Tình huống lỗi — 1 phút

Chọn **một** trong ba, tùy thời gian còn lại:

| Cách | Thao tác | Điều muốn cho thấy |
| --- | --- | --- |
| Tệp giả ảnh | Đổi tên một file `.txt` thành `.jpg` rồi tải lên | Bị từ chối với thông báo rõ ràng; hệ thống đọc magic bytes chứ không tin đuôi tệp |
| Nhấn Lưu hai lần | Bấm **Xác nhận lưu** liên tục | Chỉ một hồ sơ được tạo |
| Quét lại thẻ cũ | Tải lại đúng tấm đã quét | Cảnh báo trùng, để người dùng quyết định — không tự gộp |

> "Lỗi tra cứu không làm mất kết quả OCR. Mỗi bước hỏng được cô lập riêng."

## 7. Kết — 30 giây

Mở trang **Tổng quan**: số hồ sơ, phân bố ngôn ngữ, tỷ lệ tin cậy, quyết định của tầng agentic.

> "313 test tự động, chạy được ngoại tuyến. Còn một việc chưa làm: chưa chạy OCR thật trên ảnh chụp thật, nên chưa có số đo chất lượng. Công cụ đo đã sẵn sàng, chạy bằng một lệnh khi có API key."

---

## Nếu bị hỏi

**"Sao không dùng Azure như đề gợi ý?"**
Model `prebuilt-businessCard` đã bị ngừng phát triển từ API v4.0. Xây bài tập trên một model đã deprecated là rủi ro không cần thiết khi có lựa chọn tương đương.

**"Làm sao biết hệ thống không bịa dữ liệu?"**
Không tin vào câu lệnh prompt. Mọi giá trị mô hình trả về đều phải đối chiếu được với văn bản OCR gốc — thứ đến trực tiếp từ điểm ảnh. Không đối chiếu được thì bị loại, nhưng vẫn ghi lại để đo được tỷ lệ. Có 18 test đối kháng cho riêng phần này.

**"Độ chính xác bao nhiêu phần trăm?"**
Chưa đo được, vì chưa có OCR thật và ảnh chụp thật. Không đưa ra con số nào chưa đo. Công cụ đo đã xong và có test khóa quy tắc so sánh lại từ trước.

**"Có mở rộng sang tiếng Hàn, tiếng Trung được không?"**
Vision và Gemini vốn xử lý được. Thêm `ko`, `zh` vào `OCR_LANGUAGE_HINTS` gần như miễn phí; phần tốn công là bổ sung mẫu thử và nhãn chuẩn.

**"Xử lý được bao nhiêu thẻ một lúc?"**
Tối đa 10 ảnh một lô, chạy 3 luồng đồng thời. Không cho chạy hết song song là có chủ ý — 10 lời gọi Vision cùng lúc dễ chạm trần quota.
