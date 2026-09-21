# Kịch bản demo 7–10 phút

Bản này thay cho [ngay-10-demo.md](ngay-10-demo.md). Bản cũ viết khi dự án
mới xong Ngày 10; từ đó có thêm điều phối agentic, điểm tin cậy, trang tổng
quan, tải hàng loạt, webhook, và OCR cục bộ.

> **Nguyên tắc duy nhất khi demo:** không nói một câu nào mà bạn không chứng
> minh được ngay tại chỗ. Phần 4 ghi rõ những gì **chưa** đo được — đọc trước,
> để nếu bị hỏi thì bạn trả lời được thay vì lúng túng.

---

## Chuẩn bị trước — làm xong trước khi vào phòng

```powershell
# 1. Hai terminal chạy sẵn
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000 --app-dir backend
.\.venv\Scripts\streamlit.exe run frontend\streamlit_app.py

# 2. Sinh sẵn ảnh dùng được ngay, không cần credentials
.\.venv\Scripts\python.exe backend\scripts\make_card_sheets.py --crop

# 3. Kiểm cấu hình - tốn đúng 2 lời gọi dịch vụ
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py --check
```

Mở sẵn bốn tab: ứng dụng `localhost:8501`, tài liệu API `localhost:8000/docs`,
[kien-truc-agentic.md](../2-ke-hoach/kien-truc-agentic.md), và `reports/evaluation.md`.

**In sẵn 2 thẻ giấy** (1 Anh, 1 Nhật) để demo camera. Nếu không in kịp, dùng
đường tải ảnh — đừng để phần này làm hỏng nhịp.

---

## 1. Mở đầu — 1 phút

> "Sau một hội thảo, người ta cầm về vài chục tấm danh thiếp. Nhập tay mất
> thời gian và dễ sai. Nhưng vấn đề lớn hơn nằm ở chỗ khác: nếu dùng AI để
> đọc, **model có thể bịa ra dữ liệu trông rất thật** — một địa chỉ email
> không hề có trên tấm thẻ. Một email bịa trông y hệt một email thật, nên
> người duyệt không có cách nào phát hiện."

> "Hệ thống này giải quyết đúng vấn đề đó. Mọi giá trị model trả về đều phải
> tìm được trong văn bản OCR — thứ đến thẳng từ pixel. Không tìm được thì bị
> loại, nhưng vẫn được ghi lại để đếm."

Đừng nói "dùng Agentic AI" ở câu mở đầu. Nói **vấn đề** trước; kiến trúc để
dành phần 3.

---

## 2. Demo trực tiếp — 4 phút

### 2.1 Thẻ tiếng Anh (1 phút)

Trang **Quét thẻ** → **Chụp bằng camera** → chụp → **Gửi để nhận diện**.

Sang trang **Kiểm tra**, chỉ vào ba thứ:

- Ảnh gốc bên trái, dữ liệu bên phải — đối chiếu được ngay
- **Điểm tin cậy từng trường**, không phải một điểm cho cả thẻ
- Trường nào có nhiều giá trị thì hiện cả, không tự chọn hộ

> "Chấm theo từng trường vì một tấm thẻ có thể đọc đúng tên mà sai số điện
> thoại. Một điểm chung cho cả thẻ sẽ giấu mất điều đó."

### 2.2 Thẻ tiếng Nhật — phần quan trọng nhất (1,5 phút)

Tải ảnh thẻ Nhật. Đợi xử lý, rồi mở phần **giá trị bị loại**.

> "Đây là chỗ đáng xem nhất. Model trả về giá trị này, nhưng nó không có trong
> văn bản OCR — nên hệ thống **loại đi**, và vẫn ghi lại để đếm được model bịa
> nhiều hay ít. Một hệ thống âm thầm vứt dữ liệu là hệ thống không ai kiểm
> toán được."

Nếu lần chạy này không có giá trị nào bị loại, **đừng cố dựng** — nói thẳng:

> "Lần này không có giá trị nào bị loại. Cơ chế nằm ở `grounding.py` và có
> test riêng; tôi chỉ được luôn nếu cần."

### 2.3 Sửa một trường và lưu (45 giây)

Sửa một trường OCR đọc sai → **Lưu hồ sơ**. Chỉ vào phát hiện trùng nếu có.

> "Bản ghi OCR gốc **không bị ghi đè** khi người dùng sửa. Nếu ghi đè, sau này
> sẽ không còn cách nào trả lời câu hỏi *hệ thống đọc sai bao nhiêu phần trăm*
> — dữ liệu để so sánh đã bị chính mình xóa mất."

### 2.4 Tra cứu doanh nghiệp (45 giây)

Bấm tra cứu → chỉ vào **nguồn kèm URL** của từng thông tin.

> "Mỗi thông tin bổ sung đều kèm nguồn. Không có nguồn thì không hiển thị."

Nếu bị hỏi về bảo mật: hệ thống kiểm tra địa chỉ ở **mọi lần chuyển hướng**,
không chỉ lần đầu — vì DNS có thể đổi giữa chừng (tấn công DNS rebinding).

### 2.5 Tổng quan và tải hàng loạt (30 giây)

Trang **Tổng quan**: số bản quét, phân bố ngôn ngữ, **quyết định của agent**
(proceed / retry / escalate), điểm tin cậy trung bình.

Trang **Quét thẻ** → **Tải hàng loạt**: chọn nhiều ảnh cùng lúc.

---

## 3. Kiến trúc — 2 phút

Mở [kien-truc-agentic.md](../2-ke-hoach/kien-truc-agentic.md), chiếu **sơ đồ
Mermaid** ở phần 2.

Nói đúng ba ý, không hơn:

**(a) Vì sao agentic, không phải chạy thẳng một lượt.**
> "Ba thứ có thể hỏng độc lập: ảnh mờ, OCR đọc sót, model bịa dữ liệu. Mỗi thứ
> cần một phản ứng khác nhau — dừng trước khi tốn tiền, đọc lại với ảnh tăng
> tương phản, hoặc loại giá trị không có chứng cứ. Một đường ống chạy thẳng
> chỉ làm được một việc: đi tiếp."

**(b) Ba hành động, ngân sách cứng.**
> "Mỗi tác tử chỉ được chọn PROCEED, RETRY hoặc ESCALATE. Tối đa hai lượt thử
> lại cho cả bản quét — và lượt thử được **ghi sổ trước khi gọi**, nên tiến
> trình chết giữa chừng cũng không thử lại vô hạn."

**(c) Grounding là lớp an toàn, không phải bước hậu xử lý.**
> "Hai nguồn phải độc lập: OCR đọc pixel, model suy diễn. Nếu để model sinh ra
> cả hai thì thành lấy lời khai của một người ra kiểm chứng chính lời khai đó."

Nếu còn thời gian, kể **lỗi chuỗi con** — nó cho thấy dự án tự bắt được lỗi
của mình:

> "Ban đầu chúng tôi so khớp bằng phép kiểm tra chuỗi con. Văn bản thật là
> `taro.yamada@example.co.jp`. Model trả về `yamada@example.co.jp` — một địa
> chỉ không có trên thẻ. Phép kiểm tra chuỗi con cho qua, vì chuỗi bịa đúng là
> phần đuôi của chuỗi thật. Test của chính dự án bắt được, và cách sửa là cắt
> văn bản thành token trọn vẹn rồi so cả token."

---

## 4. Kết quả kiểm thử — 1 phút

Chiếu `reports/evaluation.md`.

**Nói chính xác thế này, đừng nói khác:**

> "579 test tự động, không gọi mạng thật. Nhưng test xanh chỉ chứng minh **mã
> nguồn tự nhất quán** — nó không chứng minh hệ thống đọc được danh thiếp
> thật. Hai điều đó khác nhau."

> "Công cụ đo đã chạy trọn đường, sinh đủ báo cáo. Nhưng số liệu hiện tại là
> **chạy khô** trên ảnh số sắc nét, không phải ảnh chụp — nên chưa dùng để
> nghiệm thu được. Bản thân báo cáo tự in cảnh báo đó ở ngay đầu tệp."

Chỉ vào bốn cột của bảng đo:

> "Cột đáng chú ý là **Tự sinh** — đếm giá trị hệ thống trả về trong khi thẻ
> không hề có trường đó. Nó được tách riêng khỏi cột **Sai**, vì bịa ra dữ
> liệu và đọc nhầm là hai loại lỗi khác hẳn nhau về mức nguy hiểm."

**Điều gì còn thiếu, nói thẳng:**

| Chưa có | Vì sao |
| --- | --- |
| Số đo trên ảnh chụp thật | Chưa in và chụp 40 thẻ |
| Ngưỡng fuzzy hiệu chỉnh theo Kanji thật | Con số 0.90 chọn theo suy luận |
| Nghiệm thu tiếng Hàn, tiếng Trung | Mã nguồn hỗ trợ, chưa có bộ mẫu |

---

## 5. Roadmap — 1 phút

Mở [roadmap.md](../2-ke-hoach/roadmap.md). Nói một ý duy nhất:

> "Lộ trình này không xếp theo độ khó lập trình, mà theo **điều kiện để bắt
> đầu**. Mốc kế tiếp không phải thêm tính năng — mà là đo được tính năng hiện
> có. Thêm tác tử khi chưa biết tác tử hiện tại chạy tốt đến đâu là xây thêm
> tầng trên một nền chưa đo."

Nếu bị hỏi "bao giờ xong v1.0": **hai việc, cả hai không phải lập trình** —
in và chụp 40 thẻ, rồi chạy `evaluate.py`.

---

## Nếu bị hỏi

| Câu hỏi | Trả lời |
| --- | --- |
| "Làm sao biết model không bịa?" | Không biết trước được — nên mới không tin nó. Mọi giá trị phải khớp với văn bản OCR, không khớp thì loại. Số lần loại được đếm và có trong báo cáo. |
| "Sao không để AI làm hết cho gọn?" | Sẽ mất cơ chế kiểm chứng. OCR và model phải là hai nguồn độc lập, nếu không thì lấy lời khai của một người ra kiểm chứng chính lời khai đó. |
| "Chạy được không nếu không có API key?" | Được. Có OCR cục bộ bằng Tesseract, miễn phí, không cần mạng. Chất lượng Kanji thấp hơn nhưng grounding vẫn đúng nguyên vẹn. |
| "Số đo chất lượng đâu?" | Chưa có trên ảnh thật. Công cụ đo xong và đã chạy trọn đường; còn thiếu bước in, cắt, chụp 40 thẻ. Tôi không đưa con số mà mình chưa đo. |
| "Vì sao bảng nhãn chuẩn đáng tin?" | Nhãn sinh ra từ chính dữ liệu dùng để vẽ thẻ, nên không thể lệch nhau. |
| "Bao nhiêu test?" | 460, chạy trong khoảng 53 giây, không gọi mạng thật. |
| "Bảo mật thế nào?" | API hiện **chưa có xác thực** — nên webhook mặc định tắt. Đó là lý do xác thực đứng đầu mốc v1.5. |

**Câu trả lời tệ nhất bạn có thể đưa ra là một con số bạn chưa đo.** Nếu không
biết, nói "chưa đo" — điều đó mạnh hơn một con số đoán bừa, và người chấm sẽ
nhận ra ngay nếu bạn đoán.

---

## Nếu có sự cố khi demo

| Hỏng | Làm gì |
| --- | --- |
| Gemini trả 503 / 429 | Nói thẳng "dịch vụ đang quá tải"; chuyển sang `EXTRACTOR=heuristic` đã chuẩn bị sẵn |
| Camera không lên | Dùng đường **Tải ảnh lên** — đã có sẵn ảnh từ `--crop` |
| Backend chết | Sidebar báo đỏ ngay; khởi động lại terminal 1, dữ liệu không mất |
| Hết hạn mức Gemini trong ngày | Đổi `EXTRACTOR=heuristic`, nói rõ đang chạy chế độ không cần mạng |

### Biết trước đường lui `heuristic` làm được gì — đo ngày 15/09

Đổi một dòng trong `backend/.env` và khởi động lại, không cần mạng, không cần
khóa. **Nhưng đừng dùng nó mà không biết trước nó hỏng ở đâu:**

| Trường | Heuristic đọc được? |
| --- | --- |
| Công ty, chức danh, phòng ban | ✅ 100% |
| Email, điện thoại, website | ✅ 100% |
| **Họ tên** | ❌ **0%** |
| **Địa chỉ** | ❌ **0%** |

Lý do: regex bắt được email, số điện thoại, URL, và tên công ty Nhật nhờ dấu
hiệu `株式会社`. Nhưng **tên người Nhật không có dấu hiệu nào để nhận ra** —
`山田 太郎` trông y hệt mọi cụm Kanji khác trên thẻ. Địa chỉ cũng vậy.

Nghĩa là nếu bạn chuyển sang heuristic giữa buổi demo, **ô họ tên sẽ trống** —
đúng cái trường người xem nhìn vào đầu tiên. Nói trước một câu sẽ tốt hơn là
để họ tự nhận ra:

> "Tôi đang chuyển sang bộ trích xuất không cần mạng. Nó dùng regex nên đọc
> được email, điện thoại và tên công ty, nhưng **không đọc được tên người** —
> tên người không có dấu hiệu nào để một biểu thức chính quy nhận ra. Đó
> chính là lý do hệ thống cần một model cho việc này."

Một tính chất đáng khen của nó: **tự sinh 0**. Nó bỏ sót chứ không bịa. Với
một đường lui thì đó đúng là thứ mình muốn — thà trống còn hơn sai.

*(Số đo trên 4 thẻ tiếng Nhật của bộ chạy khô, văn bản OCR sạch tuyệt đối.
Trên ảnh chụp thật con số sẽ thấp hơn.)*
