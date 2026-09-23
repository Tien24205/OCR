# Roadmap sản phẩm

Lộ trình phát triển từ bản hiện tại trở đi. Mỗi mốc ghi kèm **điều kiện để
bắt đầu** — vì phần lớn việc phía sau không chặn ở công sức lập trình mà chặn
ở chỗ khác.

> **Nguyên tắc xuyên suốt:** không thêm tính năng khi chưa đo được tính năng
> hiện có. Xây tầng mới trên một nền chưa đo là cách chắc chắn để sau này
> không biết chỗ nào hỏng.

---

## v1.0 — Bản hiện tại

**Trạng thái: mã nguồn xong, chưa nghiệm thu.**

Đã chạy được:

- Chụp/tải ảnh danh thiếp, một thẻ một mặt, kèm tải hàng loạt tối đa 10 ảnh
- OCR qua Google Vision **hoặc** Tesseract cục bộ, trích xuất trường bằng
  Gemini có schema
- Grounding loại bỏ giá trị model bịa ra, có ghi lại để đếm
- Điểm tin cậy theo từng trường với bốn tín hiệu
- Điều phối agentic có nhánh rẽ thật, ngân sách 2 lượt thử lại mỗi bản quét
- Tra cứu doanh nghiệp có dẫn nguồn, chặn SSRF ở mọi lần chuyển hướng
- Lưu hồ sơ, tìm kiếm, phát hiện trùng, xuất JSON/CSV/vCard
- Trang tổng quan, màn hình duyệt, 32 endpoint có mô tả OpenAPI
- 632 test tự động

**Còn thiếu để gọi là v1.0 thật:**

| Việc | Chặn ở đâu |
| --- | --- |
| Số đo chất lượng trên ảnh chụp thật | Cần in, cắt, chụp 40 thẻ — 0/40 |
| `Document/3-bao-cao/chat-luong.md` | Viết được sau khi có số đo |
| 3 dòng kiểm thử thủ công của Ngày 8 | Cần thiết bị thật: quyền camera, DevTools, HTTPS trên điện thoại |

Ghi chú thành thật: kế hoạch gốc xếp *"+Hàn/Trung"* và *"batch processing"*
vào v1.5. Thực tế cả hai **đã nằm trong mã nguồn v1.0** — bốn ngôn ngữ được hỗ
trợ và tải hàng loạt đã có giao diện. Nhưng tiếng Hàn và tiếng Trung **chưa
từng được đo**, nên chúng được tính là *chưa nghiệm thu*, không phải *đã xong*.

---

## v1.1 — Nghiệm thu bốn ngôn ngữ

**Điều kiện bắt đầu:** có số đo tiếng Anh và tiếng Nhật trước.

- Sinh và chụp bộ mẫu tiếng Hàn, tiếng Trung (hiện `make_card_sheets.py` mới
  sinh Anh + Nhật)
- Đo riêng từng ngôn ngữ — gộp chung sẽ giấu mất ngôn ngữ nào yếu
- Hiệu chỉnh `_FUZZY_THRESHOLD` theo dữ liệu thật thay vì theo suy luận.
  Ngưỡng 0.90 hiện nay chưa từng được kiểm trên chữ Kanji thật
- Hiệu chỉnh ngưỡng của tác tử chất lượng ảnh — mã nguồn tự ghi *"thresholds
  are uncalibrated rules"*

**Vì sao đây là mốc riêng, không gộp vào v1.0:** mỗi ngôn ngữ thêm vào là một
bộ nhãn chuẩn mới phải làm tay. Gộp vào sẽ khiến v1.0 không bao giờ đóng được.

---

## v1.5 — Mở cho hệ thống khác dùng

**Điều kiện bắt đầu:** chất lượng đã đo và chấp nhận được.

- ~~Xác thực API bằng khóa~~ — **đã làm 15/09**, sớm hơn mốc này
- ~~Giới hạn tần suất theo từng khóa~~ — **đã làm 15/09**
- Webhook bật mặc định sau khi đã có xác thực
- Nhập hàng loạt từ thư mục, không chỉ qua giao diện
- Xuất thẳng sang định dạng danh bạ phổ biến

**Vì sao xác thực đứng trước mọi thứ khác ở mốc này:** mở API mà không có xác
thực nghĩa là ai biết địa chỉ cũng đọc được toàn bộ hồ sơ đối tác.

> **Đã kéo lên làm sớm (15/09).** Lộ trình này đặt xác thực sau khi đo xong
> chất lượng, và xét thuần kỹ thuật thì thứ tự đó đúng. Nhưng nó được kéo lên
> vì một lý do khác: xác thực không đụng gì tới tầng AI, nên làm sớm không
> làm hỏng số đo sau này — trong khi để API mở thì mọi câu nói về "mở cho hệ
> thống khác dùng" đều không đứng vững.
>
> Hai phần còn lại của mốc này (băm khóa khi lưu, bộ đếm tần suất dùng chung
> giữa nhiều bản sao) vẫn chờ, và vẫn nên chờ.

---

## v2.0 — Nhiều người dùng

**Điều kiện bắt đầu:** v1.5 xong, và có nhu cầu thật từ nhiều người dùng.

- Bảng `users`, gắn `scans` và `contacts` với người tạo
- Phân quyền theo vai trò: quản trị / người dùng
- ~~Đóng gói bằng Docker~~ — **đã làm 15/09**: `docker compose up --build`
- Triển khai lên máy chủ, chuyển từ SQLite sang PostgreSQL
- Nhật ký thao tác: ai sửa trường nào, lúc nào

**Điểm cần cân nhắc khi tới đây:** bảng `scans` đang giữ ảnh gốc và văn bản
OCR bất biến. Nhiều người dùng nghĩa là dữ liệu cá nhân của người khác — phải
trả lời được câu hỏi lưu bao lâu và ai xóa được, **trước khi** viết dòng mã
đầu tiên của mốc này.

---

## v3.0 — Di động và dịch thuật

**Điều kiện bắt đầu:** v2.0 chạy ổn định với người dùng thật.

- Ứng dụng di động — chụp danh thiếp tại chỗ ở hội chợ, hội thảo
- Tác tử dịch chức danh Nhật ↔ Anh cho hồ sơ song ngữ
- Làm việc ngoại tuyến, đồng bộ khi có mạng

**Vì sao dịch thuật chưa làm sớm hơn:** chức danh doanh nghiệp Nhật không dịch
theo từ điển được — `部長` là "trưởng phòng" hay "giám đốc" tùy quy mô công ty.
Cần thuật ngữ chuẩn theo ngành, mà nguồn đó chưa có.

---

## v4.0 — Nối vào quy trình kinh doanh

**Điều kiện bắt đầu:** có khách hàng thật đang dùng v3.0.

- Đồng bộ hai chiều với CRM
- Tác tử gộp trùng: quyết định hai hồ sơ có phải một người không
- Bản đồ quan hệ: ai giới thiệu ai, gặp ở sự kiện nào

**Cảnh báo:** tác tử gộp trùng là thứ dễ gây hại nhất trong toàn bộ lộ trình.
Gộp nhầm hai người khác nhau thành một hồ sơ là mất dữ liệu **không khôi phục
được**, và sai lầm đó lan ra mọi hệ thống đã đồng bộ. Nó phải đo được tỷ lệ
nhận nhầm trên dữ liệu thật trước, và phải luôn có bước người xác nhận.

---

## Việc không nằm trong lộ trình

Ghi ra để khỏi ai hỏi lại:

| Không làm | Vì sao |
| --- | --- |
| Để Gemini làm luôn OCR cho gọn | Phá vỡ tính độc lập hai nguồn, grounding mất sạch ý nghĩa — xem [kien-truc-agentic.md](kien-truc-agentic.md) phần 4 |
| Đọc thẻ hai mặt trong một ảnh | Đề bài chốt một thẻ một mặt; mở rộng cần đổi cả bộ nhãn chuẩn |
| Tự động sửa chính tả tên người | Tên người không có "đúng chính tả"; sửa tự động là bịa có hệ thống |
| Đoán ngôn ngữ khi chữ Hán không phân biệt được | Đã chọn trả về nhãn `han` trung thực thay vì đoán bừa giữa Nhật và Trung |

---

**Đọc tiếp:** [kien-truc-agentic.md](kien-truc-agentic.md) ·
[nang-cap-6-tieu-chi.md](nang-cap-6-tieu-chi.md)
