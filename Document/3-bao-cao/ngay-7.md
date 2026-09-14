# Báo cáo Ngày 7 — Lưu, tìm kiếm và xuất hồ sơ

Cập nhật: 11/09/2026. Phạm vi theo [kế hoạch chi tiết](../2-ke-hoach/trien-khai-chi-tiet.md): lưu bản nháp đã duyệt, quyết định trùng, danh sách/chi tiết/cập nhật, JSON/CSV và kiểm tra lưu bền vững. Báo cáo này cũng ghi kết quả rà soát theo yêu cầu “kiểm tra lại những gì đã làm”.

## 1. Kết luận

Đã triển khai luồng Ngày 7. Có thể đưa bản nháp vào kho hồ sơ, tìm lại bằng tên Nhật hoặc tên Latin, xem nguồn và bản quét gốc, sửa hồ sơ rồi xuất dữ liệu. Đã kiểm chứng việc tắt backend và khởi động tiến trình mới trên cùng SQLite bằng HTTP thật, trong môi trường dữ liệu thử riêng.

**Chưa đóng đầy đủ DoD trên dữ liệu thật:** chưa mở CSV để kiểm tra trực quan trong Excel; các phép thử OCR vẫn dùng provider giả lập. Không dùng kết quả này để tuyên bố đã đo độ chính xác OCR Anh/Nhật hay đã nghiệm thu Gemini thật của Ngày 6.

## 2. Những gì đã làm và lý do

| Thành phần | Kết quả | Vì sao cần |
| --- | --- | --- |
| `backend/app/contact_routes.py` | API lưu, cập nhật, danh sách, chi tiết, ứng viên trùng, xuất JSON/CSV | Đưa bản nháp thành dữ liệu dùng lại được |
| `services/contacts.py` | Ghi hồ sơ và các bảng email, điện thoại, địa chỉ cùng transaction; liên kết scan đã committed | Lỗi ở một bước phải trả toàn bộ DB về trạng thái trước khi lưu |
| `services/dedupe.py` | Chấm điểm theo email, số di động, tên/doanh nghiệp, domain và ảnh | Cảnh báo có giải thích, tránh tự gộp hai người cùng tên |
| `models.ContactProfile` | Giữ toàn bộ bản đã duyệt, nguồn từng giá trị, các tên Anh/Nhật, nhiều website và số phiên bản | Cột tên chính trong schema ban đầu không đủ lưu các biến thể đa ngôn ngữ |
| `frontend/lib/contacts.py` | Xác nhận lưu, ba lựa chọn khi trùng, chi tiết và form cập nhật | Người dùng kiểm soát dữ liệu trước khi đưa vào kho |
| `frontend/app_pages/contacts.py` | Tìm kiếm, phân trang, chọn dòng mở chi tiết và tải file | Kiểm chứng dữ liệu có thể tìm lại và tái sử dụng |
| `scripts/check_day7_restart.py` | Chạy hai tiến trình Uvicorn lần lượt, kiểm tra hồ sơ và idempotency sau khởi động lại | Session hoặc cache không phải bằng chứng lưu bền vững |

Schema hiện có **10 bảng**. `contact_profiles` là bảng bổ sung, được tạo qua `init_db()` khi backend khởi động. Không xóa bảng hay thay cột dữ liệu cũ. Hồ sơ Contact có sẵn nhưng không có ContactProfile chưa được tự chuyển đổi; cần chuyển dữ liệu riêng nếu có dữ liệu cũ ngoài luồng ứng dụng này.

## 3. Quy tắc lưu và cập nhật

1. **Nguồn ghi hồ sơ là bản nháp đã lưu ở backend.** POST gửi `scan_id` và `revision`, không gửi lại các trường tùy ý từ client. Điều này giữ nguyên nguồn OCR/user do backend xác định ở Ngày 5.
2. Một transaction chứa khóa idempotency, tạo hoặc chọn doanh nghiệp, ghi Contact/ContactProfile và các bảng con, rồi cập nhật `scans.status='committed'` và `scans.contact_id`. Test cố tình gây lỗi sau khi ghi bảng con để kiểm tra rollback.
3. `Idempotency-Key` bắt buộc. Cùng khóa/cùng nội dung trả cùng ID; cùng khóa/nội dung khác trả 409. Bảng khóa lưu dấu băm của thao tác và payload trong cột `endpoint` hiện có. Không chỉ kiểm tra khóa trong bộ nhớ.
4. Một scan chỉ được commit một lần. Dùng khóa khác cho scan đã commit cũng không tạo thêm hồ sơ.
5. Sửa hồ sơ dùng `version` để chống ghi đè từ phiên cũ. Giá trị thay đổi có `source=user`; giá trị không đổi giữ nguồn cũ. Bằng chứng `raw_text`, `extraction_json` và bản nháp của scan đã commit không bị sửa theo hồ sơ.
6. **Cập nhật ứng viên trùng là thay toàn bộ dữ liệu liên hệ bằng bản nháp đang chọn, kể cả ô trống và ghi chú.** Giao diện cảnh báo và yêu cầu xác nhận trước khi thực hiện. Đây không phải thuật toán gộp từng trường. Các scan cũ vẫn liên kết tới hồ sơ để đối chiếu.
7. Liên kết doanh nghiệp không ghi đè tên/website của doanh nghiệp đã tồn tại. Các tên công ty trên danh thiếp vẫn giữ trong ContactProfile. Nếu chọn tạo mới và scan có lượt tra cứu Ngày 6 cùng revision, dùng doanh nghiệp của lượt tra cứu đó.
8. Thông tin bổ sung giữ URL, thời gian, trích đoạn, trạng thái máy và quyết định người duyệt. Phần tóm tắt và CSV chỉ lấy khẳng định được duyệt của doanh nghiệp hiện đang liên kết; tra cứu của các scan/doanh nghiệp trước vẫn nằm trong chi tiết và JSON lịch sử.

## 4. Cảnh báo trùng

Điểm là **tín hiệu mạnh nhất**, không cộng dồn để đẩy một đối sánh yếu vượt ngưỡng.

| Tín hiệu | Điểm |
| --- | --- |
| Email khớp sau chuẩn hóa | 100 |
| Cùng mã băm ảnh với scan đã lưu thành hồ sơ | 100 |
| Hai số có nhãn mobile, đều dài ít nhất 9 chữ số, khớp 9 số cuối | 80 |
| Cùng tên và cùng doanh nghiệp đã liên kết | 70 |
| Cùng tên và domain website | 60 |
| Chỉ cùng tên | 25 |

Từ 60 điểm, hiển thị **Xem hồ sơ cũ / Cập nhật hồ sơ này / Tạo hồ sơ mới**. Mặc định xem hồ sơ cũ, chưa ghi gì. API cũng kiểm tra lại ứng viên và phiên bản đích trước khi cập nhật; không chỉ tin lựa chọn từ giao diện.

## 5. Hợp đồng API hiện thực

| API | Nội dung |
| --- | --- |
| `POST /api/contacts` | `{scan_id, revision, organization:{mode:"new" hoặc "link", id?}, duplicate_action:"check" hoặc "new" hoặc "update", target_contact_id?, target_version?, note?}`; header `Idempotency-Key`; trả `{id}` |
| `GET /api/scans/{id}/duplicates` | Ứng viên từ bản nháp đã lưu; có thể truyền `organization_id` |
| `GET /api/contacts?q=&page=&size=` | Tên chính/tên phụ, công ty, email, điện thoại; size tối đa 100 |
| `GET /api/contacts/{id}` | Bản đầy đủ, version, doanh nghiệp, các scan gốc và kết quả tra cứu |
| `PATCH /api/contacts/{id}` | `{version, fields, organization, note}`; kiểm tra nguồn và version tại backend |
| `GET /api/contacts/{id}/duplicates` | Ứng viên khác, loại chính hồ sơ đang xem |
| `GET /api/organizations` | Danh sách doanh nghiệp để chọn liên kết |
| `GET /api/export?format=json` | Toàn bộ hồ sơ, giá trị đa ngôn ngữ và nguồn/lịch sử tra cứu |
| `GET /api/export?format=csv` | BOM UTF-8; trường đa giá trị biểu diễn bằng mảng JSON trong từng ô |

Tên/alias tìm bằng NFKC + casefold + bỏ khoảng trắng, nhưng hiển thị giá trị đã duyệt. LIKE xử lý `%` và `_` như ký tự tìm kiếm, không thành wildcard tùy ý. Điện thoại so bằng chuỗi chữ số; không đổi số điện thoại thành kiểu số.

CSV ưu tiên bảo toàn ranh giới các giá trị: ví dụ ô họ tên là `["山田 太郎", "Taro Yamada"]`, ô điện thoại giữ số 0 đầu và máy lẻ. JSON là bản đầy đủ có metadata nguồn, nhãn và giá trị thô. Ô ghi chú có thể bắt đầu bằng công thức được thêm dấu nháy đơn; không dùng công thức Excel để ép kiểu điện thoại.

## 6. Rà soát và lỗi đã sửa

Trong lúc rà soát, workspace có thêm mã điều phối, chất lượng ảnh, confidence và tải ảnh hàng loạt. Đây không phải các hạng mục được bổ sung cho Ngày 7 ở trên. Không xóa các phần đó; kiểm tra hồi quy cho thấy:

| Phát hiện | Ảnh hưởng | Sửa và bằng chứng |
| --- | --- | --- |
| `get_scan` thiếu decorator route | GET scan trả 404, UI không lấy được kết quả OCR | Khôi phục `@app.get("/api/scans/{scan_id}")`; test luồng và HTTP restart đi qua endpoint này |
| Orchestrator thử lại bao ngoài `_recognize` | Lỗi OCR không retryable bị gọi 2 lần; 4 lượt người dùng thành 8 lần gọi | Bỏ lớp retry OCR bên ngoài, giữ `_recognize` làm nơi quản lý retry; test hồi quy trở lại 4 lần |
| Exception thô được ghi vào decision log | Có thể lộ nội dung request hoặc dữ liệu riêng qua API và log | Chỉ ghi thông điệp cố định và loại exception; test canary không còn xuất hiện trong response |
| Form sửa hồ sơ đọc baseline mới ở mỗi rerun | Có nguy cơ thay baseline trong lúc người dùng còn sửa phiên cũ | Giữ snapshot/version của form đến khi lưu hoặc tải lại; test hai phiên không ghi đè và giữ nội dung bị từ chối |
| Test cũ đòi cảnh báo “endpoint Ngày 7 chưa có” | Không còn đúng sau khi đã hiện thực endpoint | Đổi thành kiểm tra lỗi API được hiển thị mà trang không sập |

**Cần cải thiện nhưng chưa coi là hoàn tất:** nhãn “Độ tin cậy …%” trong phần mở rộng confidence hiện là điểm heuristic, không phải xác suất đúng đã hiệu chuẩn trên dữ liệu thực. Không đưa con số này vào báo cáo như độ chính xác OCR. Phần kiểm tra ảnh ghi nhận vấn đề nhưng vẫn cho pipeline tiếp tục; đây là cảnh báo, chưa phải cơ chế tự sửa ảnh. API batch và các phần mở rộng cần nghiệm thu riêng nếu giữ trong phạm vi bài tập.

## 7. Kiểm tra đã thực hiện

**Kết quả cuối: 201 passed, 5 warnings trong 43,66 giây.** Có 24 ca mới cho Ngày 7; workspace có thêm 3 ca orchestrator ngoài bộ 174 ca ở mốc Ngày 6. Warning còn lại thuộc TestClient/AnyIO và tham số timeout; không có test thất bại. `git diff --check` đã sạch lỗi whitespace.

- 20 ca backend Ngày 7: transaction/rollback, khóa lặp và hai yêu cầu đồng thời, trùng/cập nhật/tạo mới, stale version, liên kết doanh nghiệp, nguồn bổ sung, Unicode và JSON/CSV, dữ liệu không hợp lệ.
- 4 ca giao diện Ngày 7 qua API/SQLite thật trong test: mất phản hồi sau khi commit, lựa chọn trùng, tìm/xuất/sửa tên Nhật, không ghi đè phiên mới và giữ nội dung sửa thất bại.
- Kiểm tra HTTP riêng bằng hai tiến trình Uvicorn: lưu → tắt backend → khởi động lại → đọc nguyên hồ sơ → tìm tiếng Nhật → replay khóa lưu → xuất JSON/CSV. Xem [bằng chứng khởi động lại](../4-kiem-chung/ket-qua-khoi-dong-lai-ngay-7.json).
- Các nguồn OCR và trích xuất trong test là giả lập; không gọi Google/Gemini để đo chất lượng.

Chạy lại từ gốc repo:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -X utf8 backend\scripts\check_day7_restart.py
```

Script thứ hai dùng DB và thư mục ảnh tạm, không chạm dữ liệu hồ sơ hiện có; tự tắt các tiến trình do nó tạo.

## 8. Cách dùng và việc nghiệm thu còn lại

1. Khởi động lại backend để nhận bảng mới; mở app Streamlit theo README.
2. Quét/tải ảnh → đối chiếu dữ liệu → **Lưu bản nháp**. Thay đổi chưa bấm lưu không được đưa vào hồ sơ.
3. Nếu dùng tra cứu, duyệt/bác bỏ từng thông tin ở phần Ngày 6.
4. Chọn doanh nghiệp liên kết hoặc tạo từ danh thiếp. Nếu có ứng viên trùng, xem hồ sơ cũ rồi chủ động chọn cập nhật/tạo mới.
5. Xác nhận đã kiểm tra → **Xác nhận lưu hồ sơ** → mở trang Hồ sơ, tìm bằng `山田` hoặc tên Latin.
6. Chọn dòng để xem chi tiết; bật Chỉnh sửa khi cần. Nếu báo hồ sơ đã thay đổi, giữ lại nội dung cần dùng và bấm Tải lại hồ sơ để đối chiếu bản mới trước khi gửi tiếp.
7. Bấm Chuẩn bị file xuất → tải JSON/CSV. File tải là snapshot tại lần chuẩn bị gần nhất, bấm lại nếu đã sửa dữ liệu.
8. **Còn nghiệm thu:** mở CSV trên Excel Windows, xác nhận hai tên Anh/Nhật, dấu `〒`, số `03…`, `+81…` và máy lẻ hiển thị nguyên. Đã kiểm tra BOM/giá trị bằng parser, chưa kiểm tra bằng giao diện Excel.
9. Chạy lại luồng trên ảnh thực và dịch vụ OCR/Gemini đã cấu hình. Việc hoàn tất phần lưu không đóng các tồn đọng dịch vụ thật của Ngày 2/4/6.

## 9. Kiến thức cần nắm

| Kiến thức | Cần giải thích được trong báo cáo |
| --- | --- |
| Transaction và rollback | Vì sao Contact, bảng con, scan và khóa gửi trùng phải cùng thành công hoặc cùng thất bại |
| Idempotency | Phân biệt gửi lại một yêu cầu với quét lại một ảnh; vì sao key phải tồn tại trong DB sau restart |
| Optimistic locking | Vì sao gửi version cũ phải bị từ chối, không tự lấy version mới để ghi đè |
| Mô hình quan hệ và JSON | Bảng con phục vụ tìm kiếm; snapshot giữ đa giá trị/provenance; hai phần được cập nhật cùng transaction |
| Unicode | NFKC dùng cho đối sánh, giá trị hiển thị giữ nguyên hệ chữ; số điện thoại là chuỗi |
| Đối sánh trùng | Điểm là quy tắc cảnh báo, không phải xác suất hai hồ sơ cùng người; con người quyết định |
| Kiểm thử | Mock chứng minh hành vi phần mềm; restart chứng minh lưu bền vững; cả hai không chứng minh OCR đúng trên ảnh thật |

Giới hạn MVP: tìm ứng viên trùng còn duyệt các hồ sơ trong DB, danh sách doanh nghiệp và xuất toàn bộ chưa streaming; phù hợp bộ dữ liệu nhỏ của bài tập. Bảng mới không cung cấp migration cho Contact cũ được tạo ngoài luồng. Tác vụ OCR/tra cứu đang chạy vẫn dùng BackgroundTasks, chưa có cơ chế phục hồi sau khi tiến trình bị tắt; phép thử restart ở đây thực hiện sau khi hồ sơ đã commit.
