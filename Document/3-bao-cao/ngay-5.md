# Báo cáo Ngày 5 — Chuẩn hóa và màn hình duyệt

**Ngày thực hiện:** 11/09/2026.  
**Phạm vi:** mục Ngày 5 và bảng 5.4 trong [kế hoạch triển khai](../2-ke-hoach/trien-khai-chi-tiet.md).

## 1. Kết quả

Đã triển khai chuẩn hóa theo từng trường và form sửa bản nháp đa giá trị. Người dùng có thể sửa/thêm/xóa họ tên, tên công ty, chức danh, phòng ban, email, điện thoại, website và địa chỉ; bấm **Lưu bản nháp** để lưu vào DB của bản quét.

**116 test pass**: 73 ca trước + 43 ca Ngày 5. DoD Ngày 5 đã được xác nhận bằng kiểm thử tự động: sửa tên sang tiếng Nhật qua form, lưu và đọc lại đúng Unicode, trong khi `raw_text`, `extraction_json` và bằng chứng grounding ban đầu không thay đổi.

Kiểm thử giao diện dùng Streamlit AppTest với trạng thái ô dữ liệu được cung cấp trong test; API/SQLite chạy thật trong môi trường test. Chưa thực hiện kiểm tra thao tác bàn phím/chuột trên trình duyệt vật lý hoặc OCR dịch vụ thật trong lượt Ngày 5. Việc này không thay thế bằng chứng ảnh thật còn thiếu ở Ngày 2–4.

## 2. Đã làm gì và tại sao?

| Thành phần | Thay đổi | Vì sao |
| --- | --- | --- |
| `backend/app/services/normalize.py` | Quy tắc cho từng trường, dữ liệu gốc, chuỗi so khớp, cảnh báo cấu trúc | Chuẩn hóa cách biểu diễn, không tự đoán thông tin thiếu |
| `backend/app/services/drafts.py` | Schema nhận bản sửa, nhận diện dòng và xác định nguồn thay đổi ở backend | Không tin nhãn `source` do trình duyệt gửi; phân biệt sửa một dòng với giữ nguyên dòng khác |
| `PATCH /api/scans/{id}/draft` | Lưu bản người dùng sửa riêng; kiểm tra trạng thái và phiên bản bản nháp | Không thay đổi bằng chứng OCR; tránh ghi đè thao tác từ một cửa sổ khác |
| `GET /api/scans/{id}` | Trả bản đã sửa nếu có, phiên bản và thời điểm lưu; scan Ngày 4 chưa sửa được chuẩn hóa bằng quy tắc mới khi đọc | Hiển thị dữ liệu mới nhất mà không phải gọi OCR lại |
| `frontend/lib/fields.py` | Tám bảng `st.data_editor(num_rows="dynamic")`, loại số/máy lẻ riêng, cờ trạng thái | Một danh thiếp có thể có nhiều tên theo hệ chữ, email, số liên hệ và địa chỉ |
| `frontend/app_pages/review.py` | Ảnh bên trái, form bên phải; chỉ gửi khi bấm nút; xem bản đang lưu và cảnh báo chuẩn hóa | Người dùng đối chiếu ảnh trước khi xác nhận thay đổi |
| Bộ đệm khi lưu lỗi | Giữ nội dung đã gửi trong Session State và dựng lại form từ nội dung đó | Test phát hiện thử lưu lại có thể quay về giá trị cũ; không bắt người dùng nhập lại |

Không thêm dependency, bảng hoặc cột DB. Lưu bản nháp là phần của Ngày 5; tạo `Contact`/`Organization`, tìm kiếm và xuất hồ sơ vẫn thuộc Ngày 7.

## 3. Các quy tắc chuẩn hóa đã áp dụng

| Trường | Ví dụ / kết quả | Giới hạn |
| --- | --- | --- |
| Họ tên, công ty, chức danh, phòng ban | `  山田　 太郎 ` → `山田 太郎`; gộp khoảng trắng liên tiếp | Không đảo thứ tự tên, không dịch/phiên âm; giữ các tên đa giá trị |
| Email | ` Jane.Doe+sales@EXAMPLE.COM ` → `Jane.Doe+sales@example.com` | Chỉ hạ domain; không sửa chính tả. Regex kiểm tra cấu trúc phổ biến, không xác minh hộp thư tồn tại |
| Điện thoại | `03-1234-5678 (内線 １０２)` → số hiển thị `03-1234-5678`, `value_digits=0312345678`, máy lẻ `102` | `value_raw` giữ nguyên; không thêm +81 hoặc ép E.164 |
| Máy lẻ mâu thuẫn | Trong số ghi `ext. 102` nhưng ô máy lẻ là `204` | Giữ thông tin đã nhập, gắn cảnh báo; không chọn hộ một giá trị |
| URL | `EXAMPLE.COM/Team?ID=A#Top` → `https://example.com/Team?ID=A#Top` | Hạ host, giữ case/path/query/fragment. Chỉ bỏ dấu `/` ở đường dẫn gốc; không xóa `/` ở đường dẫn con vì có thể đổi nghĩa |
| Website domain | Lấy hostname, không lấy path/query/port | Gmail, Yahoo, Outlook và các domain trong danh sách free-mail không được dùng làm domain công ty; không suy website từ email |
| Địa chỉ | Trim đầu/cuối, giữ `〒`, chữ Nhật, khoảng trắng và xuống dòng bên trong | Không dịch hoặc đổi thứ tự tỉnh/quận/số nhà |
| Chuỗi so khớp | NFKC + casefold + bỏ khoảng trắng: `ＡＢＣ　山田` → `abc山田` | Dùng cho đối sánh; tên hiển thị vẫn giữ hệ chữ gốc |

Giá trị sai cấu trúc vẫn được giữ trong bản nháp và đánh dấu **cần kiểm tra**, để người dùng sửa theo ảnh; không tự xóa hoặc tự sinh giá trị thay thế. Giới hạn 7–15 chữ số là cảnh báo sơ bộ về độ dài điện thoại, không phải xác thực số theo từng quốc gia. Bộ kiểm tra email chưa bao phủ toàn bộ các dạng địa chỉ hợp lệ theo tiêu chuẩn quốc tế; danh sách free-mail cũng không đầy đủ mọi nhà cung cấp.

## 4. Bản sửa được lưu ở đâu?

- `scans.raw_text`: văn bản OCR gốc, không bị form ghi đè.
- `scans.extraction_json`: đầu ra trích xuất gốc, không bị form ghi đè.
- `scans.grounding_json.fields/report/counts`: bằng chứng đối chiếu ban đầu, giữ nguyên.
- `scans.grounding_json.reviewed_draft`: bản người dùng đã sửa và chuẩn hóa.
- `draft_revision`, `draft_saved_at`: phiên bản và thời điểm lưu bản nháp.

Dòng giữ nguyên giá trị và metadata giữ nguồn cũ. Dòng thêm hoặc sửa đặt `source="user"`; dòng OCR ban đầu giữ `source="ocr"`. Xóa một dòng chỉ bỏ nó khỏi bản đang duyệt, không xóa dữ liệu gốc trong extraction/grounding. `value_raw` trong dòng người dùng sửa là nội dung người dùng vừa nhập trước chuẩn hóa; giá trị OCR trước sửa vẫn nằm trong bằng chứng gốc.

API nhận toàn bộ tám nhóm trường; bỏ trống một nhóm bằng `[]` là xóa các dòng trong nhóm đó. Backend từ chối nhóm bị thiếu, trường không được phép như `source`, ID không thuộc dòng hiện có hoặc bị lặp, quá 100 dòng/nhóm, quá 4096 ký tự/giá trị. Chỉ sửa scan `ocr_done`; các trạng thái khác trả 409. Scan không có trả 404. Lưu DB lỗi trả thông báo phù hợp và rollback.

Mỗi lần lưu hợp lệ tăng phiên bản. Gửi lại phiên bản cũ trả `DRAFT_CONFLICT` (409). Backend còn kiểm tra bằng cập nhật có điều kiện để chặn thay đổi chen giữa bước đọc và ghi. Nút **Tải lại bản nháp đã lưu** bỏ thay đổi trong form và lấy phiên bản mới nhất; không tự gộp hai bản sửa.

## 5. Cách sử dụng

1. Từ trang **Quét thẻ**, gửi ảnh và chờ scan chuyển sang `ocr_done`; hoặc mở trang **Kiểm tra** của scan đã xử lý trong phiên hiện tại.
2. Đối chiếu ảnh bên trái với các nhóm trường bên phải. Sửa ô; thêm dòng bằng dòng trống ở cuối; chọn dòng để xóa bằng công cụ của bảng.
3. Điện thoại có ô loại số (`tel`, `mobile`, `fax`) và ô máy lẻ riêng. Giữ nhiều tên nếu thẻ có cả Kanji và Latin.
4. Bấm **Lưu bản nháp**. Giá trị được backend chuẩn hóa; thông báo xác nhận xuất hiện sau khi DB commit thành công.
5. Mở **Bản đang lưu và lưu ý chuẩn hóa** để xem kết quả, nguồn người dùng sửa và cảnh báo. Có thể tiếp tục sửa rồi lưu lần nữa.
6. Nếu lưu lỗi, nội dung đã gửi vẫn nằm trong form để thử lại. Nếu báo xung đột, ghi nhận nội dung cần giữ rồi bấm **Tải lại bản nháp đã lưu**, đối chiếu và sửa lại trên bản mới.

**Cờ trạng thái:** xanh = khớp OCR; vàng = cần kiểm tra; xám = chưa đọc được; nhãn người dùng sửa phân biệt với OCR. Cờ và cột trạng thái mô tả bản đang lưu, không tự cập nhật theo mỗi phím gõ trong form. `exact` không bảo đảm đúng trên ảnh, `unverified` cũng không tự chứng minh AI bịa.

**Chuyển trang:** bấm Lưu bản nháp trước khi chuyển. Bản đã lưu được giữ trong DB; nội dung chưa bấm gửi vẫn ở phía trình duyệt nên có thể mất khi chuyển trang/đóng tab. Streamlit 1.63 không có tham số `persist_state` cho `st.data_editor`; không áp dụng máy móc ví dụ `persist_state="session"` trong kế hoạch cho widget này. Bộ đệm lỗi chỉ bảo vệ nội dung đã gửi trong phiên hiện tại, không sống qua việc đóng phiên.

## 6. Kiểm thử và số liệu

Chạy từ gốc repo:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

**Kết quả cuối: 116 passed, 4 warnings.** Warnings vẫn là deprecation của bộ công cụ TestClient/AnyIO và tham số timeout trong test. Không có lời gọi OCR/Gemini thật. `git diff --check` không có lỗi whitespace.

| Bộ test mới | Số ca | Nội dung |
| --- | ---: | --- |
| `backend/tests/unit/test_normalize_day5.py` | 27 | Tên Anh/Nhật, whitespace, email, máy lẻ/full-width, URL sai/free-mail, địa chỉ nhiều dòng, chuỗi so khớp, không biến đổi bằng chứng, không điền trường vắng |
| `backend/tests/integration/test_draft_day5.py` | 16 | Lưu/sửa/thêm/xóa qua API, Unicode, nguồn dữ liệu, bản gốc bất biến, revision cũ, đầu vào sai, rollback khi DB lỗi, trạng thái không được sửa và hai luồng form xuyên API |

Hai luồng form dùng AppTest với `DataEditorState` được cung cấp vào widget thật, không thay `st.data_editor` bằng hàm giả. Test kiểm tra sửa tên Nhật rồi sửa lần thứ hai, chuyển trang rồi quay lại, thêm/xóa email, lưu lỗi rồi thử lại đúng nội dung, không gửi PATCH khi chỉ rerun. Việc mô phỏng này chưa xác nhận thao tác ô bằng chuột/bàn phím trên trình duyệt thật.

## 7. Kiến thức cần học và nắm rõ

| Kiến thức | Cần giải thích được |
| --- | --- |
| Chuẩn hóa và suy đoán | Bỏ khoảng trắng khác với sửa một ký tự tên/email; thiếu quốc gia thì không tự thêm mã điện thoại |
| Unicode/NFKC | Chuỗi so khớp có thể chuyển full-width/case, nhưng không dùng kết quả đó thay tên hiển thị |
| Biểu diễn dữ liệu | Phân biệt `value_raw`, `value`, `value_digits`, `value_norm`, domain và máy lẻ; giữ danh sách đa giá trị |
| Nguồn dữ liệu | Backend xác định `source=user` từ thay đổi, không nhận lời khẳng định nguồn do client tự gửi |
| Pydantic và transaction | Validation cấu trúc trước ghi; commit thành công mới báo đã lưu; rollback giữ bản trước |
| Phiên bản bản nháp | Hai cửa sổ sửa cùng scan có thể gây mất thay đổi; revision và cập nhật có điều kiện ngăn ghi đè im lặng |
| Streamlit form/data editor | Form gửi theo đợt; input nền phải ổn định, không gán đầu ra editor ngược vào input mỗi rerun; sau lưu thành công thay key theo revision |
| Session State và lưu DB | Session giữ thao tác trong phiên, DB giữ bản đã xác nhận; dữ liệu chưa gửi từ trình duyệt không tự có ở backend |
| Kiểm thử | Test định dạng là pure unit test; bất biến bằng chứng cần test DB/API; chuỗi thao tác sửa/lưu/thất bại cần test giao diện |

## 8. Kiểm tra thủ công còn lại và phạm vi sau Ngày 5

- [ ] Trên trình duyệt thật, sửa một lỗi OCR trong thẻ Anh và một thẻ Nhật; kiểm tra nhập Kanji/Kana và chỉnh địa chỉ nhiều dòng.
- [ ] Thêm/xóa dòng email, sửa loại số/máy lẻ, lưu rồi chuyển trang và quay lại; đối chiếu bản đang lưu.
- [ ] Kiểm tra các cờ xanh/vàng/xám và cảnh báo định dạng có dễ hiểu trên màn hình đang dùng không.
- [ ] Tiếp tục bổ sung bằng chứng ảnh/OCR thật theo [báo cáo Ngày 4](ngay-4.md); các test Ngày 5 không thay thế dữ liệu đánh giá OCR.

Chưa triển khai tra cứu doanh nghiệp Ngày 6 hoặc lưu/tìm kiếm/xuất hồ sơ Ngày 7. Hạn chế worker bị gián đoạn khi backend tắt/crash từ Ngày 4 vẫn giữ nguyên. Lưu bản nháp không gọi OCR lại và không tạo hồ sơ đối tác.

## 9. Đoạn báo cáo có thể sử dụng

> Ngày 5 đã hoàn thành phần chuẩn hóa dữ liệu và form duyệt/sửa bản nháp đa giá trị. Người dùng sửa được chữ Nhật, thêm/xóa trường và lưu bản nháp vào scan; mọi dòng thay đổi có nguồn user, còn raw_text và extraction_json gốc giữ nguyên. Đã thêm cảnh báo định dạng, giữ nội dung sau lỗi lưu và chặn ghi đè phiên bản cũ. Tổng 116 test pass, trong đó 43 ca mới xác nhận quy tắc chuẩn hóa, lưu DB và thao tác form xuyên API. Phần kiểm tra trình duyệt vật lý và OCR dịch vụ thật vẫn cần nghiệm thu riêng.
