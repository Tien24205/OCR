# Báo cáo Ngày 6 — Tra cứu doanh nghiệp có dẫn nguồn

**Ngày thực hiện:** 11/09/2026.  
**Phạm vi:** Ngày 6 và mục 5.6 trong [kế hoạch triển khai](../2-ke-hoach/trien-khai-chi-tiet.md).

## 1. Kết quả và giới hạn nghiệm thu

Đã triển khai luồng **bản nháp đã lưu → chọn website ứng viên → tải trang → trích xuất thông tin bằng Gemini → đối chiếu nguồn → lưu kết quả → người dùng duyệt/bác bỏ**. Kết quả website nằm riêng với dữ liệu trên danh thiếp. Lỗi tra cứu không đổi trạng thái scan và không ghi đè OCR hoặc bản nháp.

**174 test pass**, gồm 58 ca mới Ngày 6. Các ca giao diện/API/DB dùng nguồn web và câu trả lời Gemini giả lập. Bộ tải của ứng dụng đã chạy một phép thử Internet thật thành công với `https://www.python.org/`: lấy được tiêu đề `Welcome to Python.org` và 7.134 ký tự text sau bỏ tag. Kết quả và thời điểm được lưu tại [bằng chứng tải web](../4-kiem-chung/ket-qua-tai-web-ngay-6.json).

**Chưa đóng đầy đủ DoD Ngày 6:** chưa có ảnh chụp màn hình một doanh nghiệp thật với lĩnh vực và sản phẩm/dịch vụ do Gemini trích từ website thật. Kiểm tra cấu hình hiện tại chỉ đọc cờ hiện diện: `ENRICH_ENABLED=true`, nhưng chưa có Gemini key/model. Phép thử tải Python.org xác nhận bộ tải HTTPS/robots/giải nén, không xác nhận việc nhận diện doanh nghiệp hoặc trích xuất bằng LLM.

## 2. Những phần đã triển khai

| Thành phần | Làm gì | Vì sao |
| --- | --- | --- |
| `services/enrich/discover.py` | Ưu tiên website trên bản nháp; sau đó domain email công ty, loại free-mail; không có thì trả `NO_DOMAIN_ON_CARD` | Không dùng LLM đoán website từ tên công ty; domain email chỉ là ứng viên để kiểm chứng |
| Đối chiếu doanh nghiệp | So tên công ty, địa chỉ hoặc token điện thoại với trang chủ | Hạn chế nhầm doanh nghiệp; không dùng tên người liên hệ làm bằng chứng xác định công ty |
| `services/enrich/fetcher.py` | HTTP(S), kiểm tra URL/IP/DNS, ghim IP, TLS, redirect, robots, rate limit, giới hạn kích thước | Website từ danh thiếp là đầu vào không đáng tin; mọi kết nối phải qua cùng bộ kiểm tra |
| Chọn trang con | Ưu tiên link cùng host có nội dung about/company/products/services và các đường dẫn dự phòng | Thu thập nguồn theo phạm vi nhỏ, không biến thành bộ quét web diện rộng |
| `services/enrich/summarize.py` | Gemini có schema, không có tool; yêu cầu sao chép giá trị và đoạn trích nguyên văn | Nội dung trang là dữ liệu, không được điều khiển công cụ hoặc thay đổi quy trình |
| Validator | URL phải thuộc trang đã tải, snippet có trong text trang, value có trong snippet | Chặn cả nguồn tự sinh, đoạn trích tự sinh và giá trị không được đoạn trích hỗ trợ |
| `services/enrich/worker.py` | Tác vụ nền riêng, lưu nguồn/thời điểm/trạng thái; thiếu thông tin tạo dòng `not_found` | Kết quả không tìm thấy vẫn có trạng thái rõ ràng; OCR và bản nháp tiếp tục dùng được |
| `frontend/lib/enrichment.py` | Khối nguồn có giá trị, URL bấm được, tiêu đề, thời điểm, trích dẫn, nút Duyệt/Bác bỏ | Người dùng nhìn thấy bằng chứng trước khi chấp nhận thông tin bổ sung |

## 3. Cách nối với Ngày 5 và Ngày 7

Kế hoạch Ngày 6 dùng `organization_id`, nhưng chức năng tạo hồ sơ đối tác nằm ở Ngày 7. Để bước tra cứu dùng được ngay từ bản nháp, đã bổ sung:

- `POST /api/scans/{id}/enrich`: nhận revision bản nháp đang xem, tạo **bản ghi doanh nghiệp phục vụ tra cứu** và tác vụ gắn với bản quét.
- Bảng mới `enrichment_jobs`: lưu scan ID, organization ID, revision, ảnh chụp dữ liệu đầu vào tại thời điểm tra cứu, trạng thái, số lượt chạy, kết quả, quyết định duyệt và thông tin nguồn.
- Dùng bảng `organizations` và `enrichments` đã có để lưu tên đích tra cứu và từng khẳng định có nguồn.

Schema có **9 bảng thay vì 8**. `init_db()` tạo thêm bảng khi backend khởi động; không đổi/xóa cột hoặc dữ liệu của các bảng cũ. Không cần cài thêm dependency.

Doanh nghiệp phục vụ tra cứu chỉ lấy tên có trong bản nháp; không có tên thì giữ chuỗi rỗng. Không tự điền website suy từ email vào trường website của doanh nghiệp. Các tên đa giá trị vẫn nằm đầy đủ trong snapshot. Chưa tạo Contact, chưa đổi scan sang `committed`, chưa làm tìm kiếm hoặc xuất hồ sơ.

Mỗi cặp **scan ID + draft revision** có một tác vụ duy nhất. Bấm Tra cứu lặp lại trả tác vụ cũ, không gọi lại web/Gemini. Sửa và lưu bản nháp tạo revision mới; kết quả cũ vẫn ở DB nhưng không được gán sang bản mới. Ngày 7 cần dùng/liên kết doanh nghiệp phù hợp khi lưu hồ sơ, không tự tạo bản trùng với doanh nghiệp phục vụ tra cứu này.

## 4. Giới hạn tải web và chặn SSRF

| Kiểm tra | Cách thực hiện |
| --- | --- |
| Scheme, host, port | Chỉ HTTP/HTTPS, cổng 80/443; không nhận user/password trong URL, ký tự điều khiển, backslash hoặc địa chỉ không hợp lệ |
| IP | Chặn loopback, private, link-local, metadata, multicast, reserved và các dạng IPv6 chuyển tiếp được loại trừ trong bộ kiểm tra |
| DNS | Kiểm tra toàn bộ địa chỉ DNS trả về; có một địa chỉ không công khai thì từ chối. Giới hạn thời gian chờ DNS và tối đa 4 công việc DNS đồng thời |
| Kết nối | Dùng IP đã kiểm tra cho kết nối; giữ host ban đầu ở HTTP Host và TLS SNI; xác minh chứng chỉ TLS. Client mới cho mỗi request tránh dùng chung kết nối TLS giữa các tên miền cùng IP |
| Proxy môi trường | `trust_env=False`; không âm thầm đi qua proxy từ môi trường |
| Redirect | Tự xử lý tối đa 3 lần; kiểm tra URL/DNS/IP lại ở mỗi lần, kể cả request robots.txt |
| robots.txt | Đọc trước trang, tôn trọng Disallow. 404/410 coi là không có quy tắc; lỗi truy cập/đọc robots khác thì không tải trang tiếp |
| Tần suất | Ít nhất 1 giây giữa các request cùng host trong một process; xét cả Crawl-delay/Request-rate khi parser đọc được |
| Dung lượng | Tối đa 2 MiB cả trên đường truyền và sau giải nén; robots tối đa 256 KiB; từ chối vượt giới hạn, MIME không phù hợp, nén hỏng hoặc kiểu nén chưa hỗ trợ |
| Timeout | Timeout mạng tối đa 8 giây mỗi giai đoạn request; có kiểm tra thời gian trong vòng đọc. DNS, redirect, robots và nhiều trang có thể làm tổng lượt tra cứu lâu hơn 8 giây |
| Ngân sách trang | Tối đa 5 ứng viên trang nội dung gồm trang chủ; robots và redirect là request bổ sung |

Giới hạn robots: test hồi quy cho thấy parser chuẩn của Python 3.11 bỏ qua ký tự đại diện trong `Disallow`. Đã bổ sung kiểm tra `*` và dấu kết thúc `$`. Bộ kiểm tra chọn cách từ chối khi một quy tắc Disallow áp dụng khớp đường dẫn, nên có thể chặn cả trang có ngoại lệ Allow; đây chưa phải triển khai đầy đủ thứ tự ưu tiên và gộp nhóm của [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html).

Phép thử Internet thật phát hiện máy chủ có thể trả nội dung nén dù đã gửi `Accept-Encoding: identity`. Đã bổ sung giải nén gzip/deflate với giới hạn đầu ra và test dữ liệu nén nhỏ nhưng bung ra lớn. Không dùng giải nén không giới hạn. Brotli và các chuỗi nhiều lớp nén chưa được hỗ trợ.

HTML được bỏ script/style/noscript/template trước khi lấy text; hỗ trợ đọc trang tiếng Nhật theo charset, gồm test Shift-JIS. Không chạy JavaScript của website. Mỗi trang gửi vào Gemini tối đa 16.000 ký tự, nên nội dung nằm sau giới hạn này có thể chưa được trích xuất.

Thiết kế kiểm tra SSRF tham chiếu [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html); kết nối dựa trên [HTTPX transports](https://www.python-httpx.org/advanced/transports/) và [HTTPCore SNI extension](https://www.encode.io/httpcore/extensions/). Đây là lớp bảo vệ ở ứng dụng, không thay thế kiểm soát mạng nếu triển khai ra môi trường nhiều người dùng.

## 5. Quy tắc kiểm chứng và duyệt

- `verified`: có đối chiếu doanh nghiệp và thỏa điều kiện kiểm tra nguồn; **không phải bảo đảm thông tin đúng về ngữ nghĩa hoặc luôn còn hiệu lực**.
- `unverified`: chưa đối chiếu được doanh nghiệp, hoặc quy mô thiếu đơn vị/mốc thời gian theo bộ kiểm tra.
- `conflicting`: hai trang cho giá trị khác nhau ở cùng thuộc tính; giữ cả hai để người dùng lựa chọn.
- `not_found`: không có khẳng định đủ điều kiện; giá trị null, không cho bấm duyệt một giá trị không tồn tại.

Quy mô cần đơn vị như employees/人/名 và năm thống kê trong giá trị. Không tự suy nhân sự từ vốn hoặc doanh thu. Bộ kiểm tra hiện nhận năm kiểu Gregorian; mốc niên hiệu Nhật có thể vẫn bị đánh dấu cần kiểm tra.

Khẳng định vi phạm điều kiện snippet/value/source bị loại trước khi lưu vào bảng enrichment. Metadata có số khẳng định bị loại. Text các trang của **lượt hiện tại** được lưu để đối chiếu lại validator; quote, URL và thời điểm của từng khẳng định được lưu riêng.

Quyết định người dùng (`accepted`/`rejected`) độc lập với trạng thái đối chiếu máy. Bác bỏ không xóa bằng chứng. Khi duyệt một giá trị mâu thuẫn, lựa chọn đã duyệt khác cùng thuộc tính được đổi sang bác bỏ trong cùng transaction. Cách phát hiện mâu thuẫn hiện bảo thủ: số liệu ở hai năm khác nhau hoặc mô tả bổ sung nhau cũng có thể bị đánh dấu để người dùng kiểm tra, không tự chọn số mới hơn.

Không tự sửa tên, email, số điện thoại hay bất kỳ dữ liệu danh thiếp nào bằng nội dung website. Nội dung prompt có trong trang cũng chỉ là dữ liệu; Gemini bước này không được cấp tool.

## 6. API và cách sử dụng

| API | Mục đích |
| --- | --- |
| `POST /api/scans/{id}/enrich` | Khởi tạo tra cứu từ bản nháp đúng revision; trả 202 và tác vụ |
| `GET /api/scans/{id}` | Có thêm kết quả tra cứu tương ứng revision hiện tại |
| `GET /api/organizations/{id}` | Lấy doanh nghiệp và trạng thái/kết quả `research` |
| `POST /api/organizations/{id}/enrich` | Chạy lại tác vụ có snapshot; đang chạy thì trả tác vụ hiện tại; tối đa 3 lượt tổng cộng |
| `PATCH /api/enrichments/{id}` | Body `{"decision":"accepted"}` hoặc `{"decision":"rejected"}`; giữ giá trị/quote gốc |

Chạy lại tra cứu giữ các dòng khẳng định cũ trong DB và tạo các dòng mới; giao diện hiển thị lượt hiện tại. Không duyệt được một dòng đã thuộc lượt cũ. Text toàn trang của lượt cũ chưa có cơ chế lưu lịch sử riêng qua các lần chạy lại; quote/URL/thời điểm của dòng khẳng định cũ vẫn còn.

Trong ứng dụng:

1. Đợi OCR xong, sửa và **Lưu bản nháp**. Tra cứu chỉ dùng dữ liệu đã lưu; thay đổi chưa gửi trong form không được dùng.
2. Bấm **Tra cứu doanh nghiệp** dưới phần đối chiếu OCR.
3. Chờ kết quả. Poll mỗi giây, dừng tự động sau mốc 60 giây hoặc lỗi API. **Kiểm tra trạng thái** chỉ đọc lại, không khởi chạy tác vụ mới.
4. Đọc giá trị, mở URL nguồn, xem thời điểm và đoạn trích trước khi bấm **Duyệt** hoặc **Bác bỏ**.
5. Khi cần chạy lại nguồn, dùng **Thử tra cứu lại**; có giới hạn 3 lượt cho mỗi snapshot.

`BackgroundTasks` vẫn chạy trong process backend. Tắt/crash/reload giữa lúc xử lý có thể để tác vụ ở pending/processing; chưa có queue bền vững hoặc tự phục hồi. Tránh reload khi nghiệm thu. Hạn chế này được giữ trong phạm vi 10 ngày, không triển khai hạ tầng queue ở Ngày 6.

## 7. Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest
```

**Kết quả cuối: 174 passed, 5 warnings.** Warnings từ TestClient/AnyIO và timeout trong test; không có test thất bại. `git diff --check` không phát hiện lỗi whitespace.

| Bộ test mới | Số ca | Kiểm tra chính |
| --- | ---: | --- |
| `backend/tests/unit/test_fetcher_day6.py` | 34 | Địa chỉ nguy hiểm, DNS có IP private, ghim IP/Host/SNI, redirect nội bộ và robots của host mới, MIME, dung lượng, gzip, timeout, rate limit, DNS rebinding, Shift-JIS |
| `backend/tests/unit/test_enrichment_claims_day6.py` | 7 | Nguồn/snippet/value phải khớp, danh tính, quy mô có ngày, mâu thuẫn, chọn domain và giới hạn trang |
| `backend/tests/unit/test_summarizer_day6.py` | 4 | Schema Gemini, không có tool, dữ liệu web không làm system instruction, cấu hình thiếu và lỗi JSON được xử lý |
| `backend/tests/integration/test_enrichment_day6.py` | 11 | Thành công, thiếu domain, lỗi web, thiếu summarizer, gửi lặp, retry, snapshot revision, duyệt mâu thuẫn, giữ scan và luồng UI/API |
| `frontend/tests/test_enrichment_ui_day6.py` | 2 | Hết thời gian chờ và mất mạng: dừng poll, giữ OCR, không tự tạo lượt mới |

**58 ca mới + 116 ca trước = 174.** Hai kịch bản có website và không có nguồn đã được kiểm tra bằng nguồn giả lập. Phép thử tải web thật được ghi riêng, không trộn vào phép đo chất lượng của dữ liệu giả lập.

## 8. Việc cần làm để đóng DoD thật

1. Điền `GEMINI_API_KEY` và `GEMINI_MODEL` trong `backend/.env`; model phải gọi được structured output. Giữ `ENRICH_ENABLED=true`.
2. Khởi động lại backend để nhận cấu hình và tạo bảng mới. Chạy từ gốc repo, hai terminal:

```powershell
# Backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --app-dir backend

# Frontend
.\.venv\Scripts\python.exe -m streamlit run frontend\streamlit_app.py
```

3. Với một bản quét đã xử lý, lưu tên công ty và website/email công ty đúng theo thẻ. Dùng danh thiếp thật và kiểm chứng OCR thật nếu muốn đóng đồng thời các tồn đọng Ngày 2–4.
4. Tra cứu một doanh nghiệp có website công khai, có thông tin lĩnh vực và sản phẩm/dịch vụ. Kiểm tra từng giá trị có đoạn trích thực sự hỗ trợ và đúng doanh nghiệp.
5. Chụp màn hình phần kết quả có **lĩnh vực + sản phẩm/dịch vụ + URL + thời điểm + đoạn trích**, ghi scan ID/revision/model và các lỗi quan sát được.
6. Thử thẻ không có website hoặc email công ty: phải hiện chưa tìm thấy; OCR và bản nháp vẫn nguyên. Nếu robots hoặc website không cho tải, ghi đúng giới hạn, không bỏ kiểm tra để lấy cho đủ dữ liệu.

| Bằng chứng | Hiện tại |
| --- | --- |
| Tải HTTPS/robots bằng code thực tế | Đã có với Python.org; xem JSON kèm báo cáo |
| Gemini trích từ website doanh nghiệp thật | Chưa có |
| Ảnh màn hình doanh nghiệp thật có đủ trường và dẫn nguồn | Chưa có |
| Không có domain vẫn giữ OCR | Đã có test tự động, cần thêm thao tác nghiệm thu trên giao diện thật |

## 9. Kiến thức cần học và nắm rõ

| Kiến thức | Cần giải thích được |
| --- | --- |
| SSRF | Vì sao URL từ danh thiếp không được fetch tùy ý; tại sao redirect và DNS phải được kiểm tra |
| DNS, IP và TLS | Kiểm tra DNS rồi gọi lại theo hostname vẫn có rủi ro đổi địa chỉ; ghim IP nhưng giữ Host/SNI giúp kết nối đúng nơi và xác minh chứng chỉ đúng tên |
| HTTP streaming | Không đọc toàn bộ response không giới hạn; phân biệt kích thước tải và kích thước sau giải nén |
| robots/rate limit | robots.txt là chính sách của website, không phải biện pháp thay thế SSRF; request phải có User-Agent và giới hạn tần suất |
| Nguồn và định danh | Website/email domain chỉ gợi ý nơi tra cứu; cần đối chiếu doanh nghiệp, không tìm theo tên người |
| Structured output và grounding | Schema đúng chưa có nghĩa nội dung đúng; URL/snippet/value phải đối chiếu được với dữ liệu đã tải |
| Bằng chứng và mâu thuẫn | Giữ thời điểm và đơn vị quy mô; không tự gộp hai nguồn khác nhau hoặc ghi đè danh thiếp |
| Trạng thái và lưu dữ liệu | Scan và research job độc lập; snapshot gắn revision; quyết định người dùng tách khỏi trạng thái xác minh máy |
| Kiểm thử | Mock giúp tái hiện trường hợp lỗi và nội dung nguy hiểm; phép thử mạng và nghiệm thu doanh nghiệp thật là các bằng chứng khác nhau |

## 10. Đoạn báo cáo có thể sử dụng

> Ngày 6 đã triển khai tra cứu doanh nghiệp từ website hoặc domain email công ty, tải nguồn qua bộ kiểm tra SSRF/robots/giới hạn dung lượng và dùng Gemini có schema để trích xuất khẳng định. Mỗi thông tin phải có URL, thời điểm và đoạn trích đối chiếu được; kết quả được lưu riêng và cho người dùng duyệt/bác bỏ. Lỗi tra cứu không đổi OCR hoặc bản nháp. Tổng 174 test pass; bộ tải đã thử HTTPS thật thành công với Python.org. Chưa có Gemini key/model và ảnh màn hình doanh nghiệp thật đủ lĩnh vực/sản phẩm có nguồn nên DoD thực tế Ngày 6 vẫn còn chờ nghiệm thu.
