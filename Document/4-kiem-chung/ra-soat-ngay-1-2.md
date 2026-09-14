# Rà soát tiến độ Ngày 1–2 và việc cần làm tiếp

**Ngày kiểm tra:** 11/09/2026. **Mốc mã nguồn:** `7ae5ef6`, 6 commit.
**Thư mục dự án:** `C:\Users\dotie\OneDrive\Desktop\OCR\OCR` (hai cấp OCR).

Đối chiếu mã nguồn backend/frontend, scripts, tests, dữ liệu mẫu và toàn bộ tài liệu trong `Document`. Bản này đính chính báo cáo trước, phân biệt phần đã viết, phần đã kiểm thử và phần chưa hoàn thành. Các lỗi mã nguồn dưới đây **chưa được sửa trong lần rà soát này**; chỉ cập nhật tài liệu và lưu kết quả kiểm tra.

## 1. Kết luận để báo cáo

**Ngày 1 đã hoàn thành phần lớn nền tảng kỹ thuật, chưa hoàn tất checklist dữ liệu mẫu.** Có FastAPI, Streamlit ba trang, schema 8 bảng, cấu hình, Git và bộ test. Hiện có 0 ảnh trong `datasets`, hai nhãn minh họa không có ảnh tương ứng; chưa đạt ít nhất 5 nhãn thật đầu tiên theo kế hoạch chi tiết.

**Ngày 2 có bản thử nghiệm chạy với mock, chưa đạt định nghĩa hoàn thành.** Có adapter Google Vision, Gemini, regex, grounding và script thử độc lập. Chưa có bằng chứng OCR/trích xuất thật. Ngoài credentials và ảnh mẫu, còn các lỗi tích hợp và kiểm chứng dữ liệu; không nên báo “mọi thứ khác đã xong, chỉ chờ tài khoản”.

**Chưa có luồng ứng dụng hoàn chỉnh.** API nghiệp vụ hiện chỉ có `GET /api/health`. Nhận ảnh, worker OCR, tra cứu, lưu hồ sơ, tìm kiếm và xuất dữ liệu chưa được nối vào backend. Đây phần lớn là công việc Ngày 3–7 đúng kế hoạch, không phải tất cả đều là phần trễ của Ngày 1–2.

## 2. Số liệu đã kiểm chứng lại

| Chỉ số | Cuối Ngày 1 (`3ecfeec`) | Mốc kiểm tra (`7ae5ef6`) |
| --- | --- | --- |
| Commit | 5 | **6**, không phải 7 |
| Tổng file Git theo dõi | 29 | 45 |
| File ngoài `Document` | 24 | 39 |
| File Python | 14 | 27 |
| Dòng Python gồm dòng trống/chú thích | 1.229 | 2.654 |
| Bảng ORM | 8 | 8 |
| Test | 9 theo cấu trúc Ngày 1 | **27/27 pass**, chạy lại 2,42 giây |
| Ảnh thực trong `datasets` | Không suy ra được từ Git vì ảnh bị ignore | **0/40** |
| Nhãn hiện có | — | 2 dòng minh họa, thiếu cả hai ảnh |
| Fixture OCR hiện có | — | 2 file, `provider: "mock:synthetic"` |

24/39 là số file ngoài `Document`, gồm README, cấu hình và fixture; không nên gọi tất cả là “file mã nguồn”. Số dòng Python cũ đã đính chính đúng, nhưng không phải số dòng logic hay phần trăm hoàn thành. Không cộng trước commit báo cáo chưa được tạo. Hai fixture có nguồn gốc tổng hợp, không phải OCR thật; provider thực tế trên đĩa là `mock:synthetic`.

Phiên bản đang cài: Streamlit 1.63.0, FastAPI 0.141.1, SQLAlchemy 2.0.52, google-cloud-vision 3.15.0, google-genai 2.22.0. Requirements dùng cận dưới `>=`, chưa khóa phiên bản để tái lập môi trường này.

## 3. Ngày 1: đã làm, ý nghĩa và phần cần cải thiện

| Hạng mục | Bằng chứng đã có | Vì sao cần | Chưa hoàn tất |
| --- | --- | --- | --- |
| Khung dự án | Git, `.gitignore`, README, requirements, một venv | Quản lý và chạy thống nhất | Khóa phiên bản, đồng bộ hướng dẫn thư mục chạy |
| Backend | Config, DB, models, main; health 200 qua TestClient | Nền cho API và dịch vụ | Readiness chưa phải xác nhận dịch vụ thật |
| Schema | 8 bảng; test Unicode, khóa ngoại, điện thoại, giữ scan khi xóa contact pass | Bảo toàn dữ liệu và quan hệ | Quy tắc giữ nhiều tên/website, thiếu tên, chống sửa bằng chứng |
| Frontend | Camera/upload/xem trước; ba trang; lớp API; khung poll | Chuẩn bị tương tác | Gửi ảnh chưa tới API thực; camera chưa thử thiết bị thật |
| Test | 5 DB + 4 AppTest | Bảo vệ nền tảng | Chưa kiểm tra submit/retry; DB test tự bật PRAGMA nên chưa bảo vệ trực tiếp cấu hình DB ứng dụng |
| Dữ liệu mẫu | README, labels minh họa, script kiểm tra | Nền cho đánh giá | 0 ảnh, chưa có 5 cặp ảnh–nhãn thật |

### D1-01 — P1: Giới hạn upload 8 MB chưa được nạp

File cấu hình nằm trong `frontend/.streamlit/config.toml`, nhưng README chạy Streamlit từ gốc repo. Probe cấu hình hiệu lực tại gốc trả **200 MB**, không phải 8 MB. Cần chuyển cấu hình về `.streamlit/config.toml` tại thư mục chạy hoặc truyền tùy chọn CLI và kiểm tra lại. Backend vẫn phải chặn dung lượng độc lập ở Ngày 3.

### D1-02 — P2: Trạng thái “sẵn sàng” đang gây hiểu nhầm

`config.py:72` chỉ kiểm tra tệp có tồn tại/key có giá trị; không kiểm tra quyền, quota hay model. Đường credentials tương đối còn được kiểm tra theo thư mục đang chạy, không neo vào backend. Sidebar áp điều kiện key Gemini cho cả `heuristic` và credentials Google cho cả `mock`.

Cần phân biệt “đã cấu hình”, “mock/offline” và “đã xác nhận bằng lời gọi thật”; xử lý riêng từng provider. Không dùng đèn xanh này làm DoD Ngày 2.

### D1-03 — P2: Schema DB chưa giữ được đầy đủ đầu ra đa giá trị

`CardExtraction` có `full_names[]`, `company_names[]`, `websites[]`; DB chỉ có một tên chính cho contact, một website cho organization và cặp tên công ty gốc/Latin. Cần quy định chọn giá trị chính và giữ các biến thể còn lại. `Contact.full_name_original` là NOT NULL: phải xác định cách lưu bản nháp thiếu tên mà không bắt người dùng bịa tên.

`Scan.raw_text` và `extraction_json` được chú thích là bất biến nhưng chưa có chốt chặn cập nhật. Test hiện kiểm tra giữ scan khi xóa contact, chưa kiểm tra chống ghi đè bằng sửa tay. Chốt các quy tắc này trước khi làm mapping và form Ngày 4–5.

### D1-04 — P2: Script kiểm tra nhãn chưa phải cổng nghiệm thu

`check_labels.py` đọc 2 nhãn, cảnh báo thiếu ảnh nhưng vẫn in “Không có lỗi” và exit **0**. Số 1/10 đếm dòng nhãn, không phải cặp ảnh–nhãn hợp lệ.

Thêm chế độ strict, xác thực kiểu dữ liệu/cấu trúc, file ảnh tồn tại, thư mục khớp `lang`, đủ số lượng. Báo riêng nhãn/ảnh hợp lệ. Kiểm tra trùng nội dung giữa dev/eval; nhiều ảnh chụp cùng danh thiếp phải ở cùng một tập để tránh rò rỉ dữ liệu đánh giá.

## 4. Ngày 2: đã có những thành phần nào?

| Thành phần | Đã có | Giới hạn bằng chứng |
| --- | --- | --- |
| OCR base | Protocol, OcrResult/OcrBlock, lỗi có mã | Hợp đồng nội bộ đã viết |
| Google Vision | Request OCR, text/bbox/ngôn ngữ, một số nhánh lỗi | Chưa gọi dịch vụ thật |
| Mock | Fixture theo SHA-256 ảnh | Hai fixture đều tổng hợp |
| Gemini | Schema Pydantic, ảnh + raw text, system instruction | Chưa xác nhận ảnh/schema/model thật |
| Heuristic | Regex email/phone/URL, từ khóa công ty/chức danh/phòng ban | Không phải extractor đủ mọi trường |
| Grounding | exact/fuzzy/unverified, 18 test pass | Còn nhận sai/loại nhầm, xem mục 5 |
| Script spike | Liệt kê model, chạy độc lập, lưu kết quả | Có lỗi OCR-only và ghi đè fixture |
| Phiếu nhà cung cấp | Khung ghi chép | B/C/D/F chưa có kết quả thật |

Chạy lại spike với `--no-save` trên hai ảnh tổng hợp trong `tmp/test-cards` thành công qua mock + heuristic: mẫu Anh có 6 giá trị được giữ, mẫu Nhật có 8. Đây không phải điểm chất lượng OCR; cả hai vẫn không trích tên người/địa chỉ. Không thực hiện lời gọi Vision/Gemini trong đợt kiểm tra này.

## 5. Lỗi Ngày 2 đã tái hiện

### D2-01 — P1: Credentials trong `.env` chưa được truyền sang Google SDK

**Vị trí:** `backend/app/services/ocr/google_vision.py:62`, `backend/app/config.py:72`, `backend/scripts/try_ocr.py` hàm `build_ocr`.

Settings đọc đường dẫn nhưng `ImageAnnotatorClient()` không nhận credentials và môi trường tiến trình không được cập nhật. Probe mock SDK xác nhận constructor không có kwargs và biến môi trường chưa được đặt. Nếu máy không có ADC ngoài ứng dụng, chỉ điền `.env` như hướng dẫn vẫn có thể thất bại.

**Sửa:** Resolve đường dẫn theo `BACKEND_DIR`, truyền credentials tường minh vào client hoặc thiết lập ADC nhất quán; kiểm tra chạy từ cả gốc repo và backend. [Tài liệu ADC của Google](https://docs.cloud.google.com/docs/authentication/application-default-credentials) xác nhận SDK tìm biến môi trường, ADC cục bộ hoặc tài khoản gắn với môi trường; không tự đọc đối tượng Settings.

### D2-02 — P1: Số máy lẻ/nhãn điện thoại chưa được kiểm chứng

**Vị trí:** `grounding.py:235–254`.

OCR chỉ có `TEL: 03-1234-5678`; đầu ra thử thêm `extension="999"`, `label="fax"`, `source_text="invented"`. Grounding vẫn giữ cả ba với `needs_review=false`. Chỉ `item.value` được so khớp; metadata được sao chép thẳng.

**Sửa:** Kiểm chứng máy lẻ và nhãn trong cùng đoạn nguồn với số chính; giới hạn nhãn bằng enum; kiểm tra source_text hoặc ghi rõ chưa xác minh. Thêm test “số đúng nhưng máy lẻ bịa”, “TEL bị gắn FAX”, “nguồn trích không tồn tại”.

### D2-03 — P1: So cả token vẫn chưa loại hết trường hợp nhận sai/loại nhầm

**Vị trí:** `grounding.py:36`, `:40–45`, `:116–118`, `:154–181`.

| Dữ liệu thử | Kết quả hiện tại | Vấn đề |
| --- | --- | --- |
| OCR `taro.yamada@example.co.jp`, giá trị `taroyamada@example.co.jp` | fuzzy, accepted=true | Xóa dấu chấm trong `_collapse` khiến email khác được giữ |
| OCR hai dòng số `03-1234-5678` và `090-8765-4321`; đối chiếu số đầu | unverified | `\s` trong regex gộp hai dòng thành một token |
| OCR URL `/Profile`, giá trị `/profile` | exact | Hạ chữ cả URL làm mất phân biệt path |
| OCR và giá trị đều `https://example.com?a=1` | unverified | Query không được giữ khi không có `/` sau host |

**Sửa:** Tách token theo ranh giới phù hợp; dùng parser URL và chuẩn hóa host riêng; không coi thay dấu email là tương đương. Trường fuzzy phải chờ duyệt trước khi được coi là xác minh hoặc tự lưu/xuất. Lỗi lấy đuôi email bằng chuỗi con cũ đã được chặn, nhưng chưa thể kết luận cả cơ chế đã an toàn.

### D2-04 — P1: `--no-extract` trả thất bại và không lưu OCR thành công

**Vị trí:** `try_ocr.py:172–173` và phần tổng kết `main()`.

Probe OCR giả lập thành công rồi chạy `--no-extract` cho exit **1**, **0 fixture**. `process()` trả `None` trước bước lưu. Nếu OCR thành công nhưng extraction lỗi, dữ liệu OCR cũng chưa được lưu.

**Sửa:** Lưu OCR ngay khi thành công; tách trạng thái OCR/extraction. OCR-only phải exit 0 khi OCR thành công; extraction lỗi vẫn giữ đầu ra OCR để tránh gọi OCR lại và mất bằng chứng.

### D2-05 — P1: Mock replay có thể ghi đè kết quả thật

**Vị trí:** `try_ocr.py:120–146`, `mock.py`.

Probe ghi fixture `google_vision`, sau đó ghi cùng hash từ `mock:google_vision`: file gốc bị thay. Hiện hai fixture đã có provider `mock:synthetic`. File lưu thiếu extractor/model/thời điểm chạy nên khó tái lập phép đo.

**Sửa:** Không cho mock ghi lại kho bằng chứng gốc; tách replay/raw runs hoặc dùng run ID. Lưu hash ảnh, timestamp, provider/model, tham số và kết quả từng bước. Kết quả thật có thông tin liên hệ cần thư mục riêng được ignore; hash tên file không ẩn danh nội dung JSON. Tạm dùng `--no-save` khi chạy mock.

### D2-06 — P1: Chỉ số “bị loại” bị diễn giải sai thành “AI bịa”

Một giá trị thật trên ảnh có thể không nằm trong OCR do OCR bỏ sót hoặc bộ so khớp sai. Ngược lại `ground("Example", "Example Solutions Inc.", "name")` trả exact nhưng không chứng minh đó là tên người.

**Sửa cách đo:** `unverified` = “không đối chiếu được với OCR”. Chỉ kết luận “không có trên ảnh/tự sinh” sau khi kiểm tra ảnh và nhãn chuẩn. Đo riêng sai OCR, sai gán trường, grounding loại nhầm và thông tin không có trên ảnh. Giữ đầu ra trước/sau lọc để đo bộ lọc. Điểm 0.95 trong grounding là điểm quy tắc, không phải xác suất đúng đã hiệu chỉnh.

Đây là sửa đổi bắt buộc của báo cáo, phiếu nhà cung cấp và kế hoạch Ngày 9; nếu không, số liệu chất lượng sẽ sai ngay từ định nghĩa.

### D2-07 — P2: Regex không chỉ “kém với tên Nhật”

`HeuristicExtractor.extract()` không có nhánh điền `full_names` và `addresses`, nên luôn bỏ trống hai trường ở cả Anh/Nhật. Mẫu `部長  山田 太郎` bị gán nguyên dòng vào chức danh. Với TEL và FAX cùng dòng, cả hai số nhận nhãn fax và cùng máy lẻ 102.

**Sửa:** Ghi đúng giới hạn; xét nhãn/máy lẻ quanh từng số; thêm test nhiều số cùng dòng. Nếu bổ sung tên/địa chỉ, cần đánh giá riêng, không coi heuristic tương đương Gemini.

### D2-08 — P2: Còn thiếu test adapter và đường lỗi

27 test hiện tại = **5 DB + 18 grounding + 4 frontend**; chưa có test trực tiếp Google adapter, Gemini adapter, CLI hoặc checker nhãn. Gemini bắt mọi ngoại lệ thành retryable=true, chưa phân biệt sai quyền/model với lỗi tạm thời; chưa đặt timeout riêng ở tầng ứng dụng. `--list-models` chỉ lọc `generateContent`, không chứng minh model nhận ảnh/schema hoặc tài khoản còn quota.

**Sửa:** Test bằng response giả cho quyền sai, 429, timeout, JSON lỗi/rỗng, OCR trống, nhiều ảnh có một ảnh lỗi. Sau đó kiểm tra thật model trên bốn ảnh. Structured output ràng buộc cấu trúc, không tự bảo đảm nội dung đúng. [Tài liệu Gemini](https://ai.google.dev/gemini-api/docs/structured-output).

## 6. Rà soát các tài liệu

| File | Điểm cần đồng bộ |
| --- | --- |
| `De2.docx.pdf` | Giữ nguyên đề gốc: chụp → OCR → tra cứu công khai → hồ sơ tập trung. Không bắt buộc framework, SLA hoặc tỷ lệ chính xác cụ thể |
| `Bai-2-business-card-yeu-cau-chuan-hoa.md` | React/Blazor/Azure là phương án tham khảo ban đầu; triển khai hiện tại dùng Python/Google |
| `Bai-2-noi-dung-va-ke-hoach-10-ngay.md` | Thay nội dung học frontend theo Streamlit/session_state/form/fragment và backend FastAPI/Pydantic/SQLAlchemy/httpx; giữ mục tiêu nghiệp vụ |
| `Bai-2-ke-hoach-trien-khai-chi-tiet.md` | Code mẫu async OCR khác hàm đồng bộ; `full_name` khác `full_names[]`; thuật toán grounding cũ; CORS còn 5173; cần đồng bộ trước Ngày 4 |
| Kế hoạch chi tiết | DoD Ngày 2 ghi **4 OCR + 4 extraction thật**, báo cáo cũ chỉ ghi 4 OCR; phải có đủ hai loại kết quả cho 4 mẫu. Có thể gộp file nếu ghi rõ, không bỏ bước extraction |
| Kế hoạch chi tiết | Ma trận Ngày 8 có 13 dòng nhưng DoD 12/12; bảng repo trống và “việc hôm nay” là trạng thái lịch sử |
| `ocr-provider-notes.md` | B/C/D/F chưa điền; đổi định nghĩa “bị loại”; Gemini-only là phương án chưa triển khai, không phải đường lui đã sẵn sàng |
| README/báo cáo cũ | Không dùng `git status` chứng minh không lộ bí mật; không coi key có mặt là dịch vụ dùng được; không khẳng định temperature=0 bảo đảm kết quả giống tuyệt đối |

Kế hoạch chi tiết thu hẹp tra cứu vào website/domain trên thẻ, không có domain thì `not_found`; kế hoạch ban đầu còn tìm theo tên. Cần ghi đây là giới hạn MVP. Không ưu tiên thêm Hàn/Trung trước khi Anh/Nhật được kiểm chứng.

Streamlit không tự làm ảnh riêng tư: nội dung hiển thị vẫn gửi tới trình duyệt người xem; vẫn cần phân quyền. Khung `review.py` có polling nhưng chưa giới hạn thời gian; nút “Thử lại” chỉ xóa session cache, chưa gọi API retry. Hoàn thiện các phần này ở Ngày 3–4, không báo đã có worker/retry thật.

## 7. Những việc bạn cần làm tiếp

### Bạn chuẩn bị

1. **Quyền dịch vụ:** Google Cloud có Vision API/quyền sử dụng phù hợp; credentials cục bộ; Gemini API key và model nhận ảnh + structured output. Không cần gửi key vào chat. Hiện có `.env`, nhưng không thấy tệp credential tại đường backend đã cấu hình, Gemini key/model trống; không đủ căn cứ kết luận bạn chưa có tài khoản ở nơi khác.
2. **Bốn ảnh đầu tiên:** 2 Anh + 2 Nhật trong `datasets/dev/en/` và `datasets/dev/ja/`, có quyền sử dụng và nhãn đọc từ ảnh. Thẻ hư cấu có thể in rồi chụp lại; PNG sinh trực tiếp chỉ dùng kiểm thử kỹ thuật.
3. **Bổ sung dữ liệu Ngày 1:** ít nhất 5 cặp ảnh–nhãn thật, rồi tiến tới 20 Anh + 20 Nhật, tách dev/eval theo danh thiếp gốc.
4. **Nguồn tra cứu:** chọn 2–3 website doanh nghiệp thật và ghi kiểm tra vào phần F. Domain minh họa của thẻ hư cấu không chứng minh tra cứu doanh nghiệp thật.
5. **Ngân sách/quota:** ghi giới hạn tài khoản và ngân sách vào phiếu; giá kiểm tra tại thời điểm dùng, không ghi số chưa xác minh.

### Phần thuộc lập trình, không phải việc chờ bạn cấp tài khoản

1. Sửa credentials, OCR-only và giữ bằng chứng: D2-01, D2-04, D2-05.
2. Sửa kiểm chứng máy lẻ/token: D2-02, D2-03; đổi cách diễn giải số liệu: D2-06.
3. Sửa cấu hình upload/readiness, bổ sung kiểm tra nhãn và test adapter/CLI.
4. Chạy lại test, rồi chạy Vision + Gemini thật trên bốn ảnh.
5. Điền B/C/D/F, đối chiếu với nhãn chuẩn trước sửa tay và ghi kết luận.

Trong lúc chờ quyền/ảnh có thể làm backend nhận ảnh Ngày 3 bằng mock ghi nhãn rõ; bắt đầu Ngày 3 không có nghĩa Ngày 2 đã đạt.

### Cách chạy tạm thời sau khi bạn đã có credentials

Với code hiện tại chưa sửa D2-01, nếu dùng JSON service account, đặt đường dẫn tuyệt đối trong terminal chạy script. Lệnh dưới không in khóa:

```powershell
Set-Location 'C:\Users\dotie\OneDrive\Desktop\OCR\OCR'
$env:GOOGLE_APPLICATION_CREDENTIALS = (Resolve-Path 'backend\secrets\gcp-sa.json').Path
$env:OCR_PROVIDER = 'google'
$env:EXTRACTOR = 'gemini'
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py --list-models
```

Đặt Gemini key và model lựa chọn vào `backend/.env`. List models không thay thế thử ảnh/schema. Sau khi sửa cơ chế lưu bằng chứng:

```powershell
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py datasets\dev\en\001.jpg datasets\dev\en\002.jpg datasets\dev\ja\001.jpg datasets\dev\ja\002.jpg
```

Raw JSON hiện lưu vào fixture được Git theo dõi. Trước khi chia sẻ/commit, tách dữ liệu riêng hoặc chỉ dùng fixture được phép công bố.

## 8. Điều kiện hoàn tất Ngày 1–2

**Ngày 1:** khung chạy, DB/test đạt, cấu hình đúng thư mục, trạng thái frontend rõ; ít nhất 5 cặp ảnh–nhãn hợp lệ và lịch thu đủ 40 mẫu. Chưa nên ghi hoàn thành toàn bộ khi 0 ảnh.

**Ngày 2:** 4 mẫu (2 Anh/2 Nhật), mỗi mẫu có OCR thật và extraction thật trước sửa tay; lưu provider/model/thời điểm/hash; kiểm tra bằng ảnh và nhãn chuẩn; phiếu B/C/D/F có dữ liệu; lỗi P1 có test hồi quy. Bốn mẫu chỉ chứng minh tích hợp ban đầu, không đủ khẳng định chất lượng mọi danh thiếp.

## 9. Phạm vi và giới hạn kiểm tra

- `python -m pytest`: 27 pass; `check_labels.py`: 2 nhãn không ảnh, exit 0.
- FastAPI TestClient với DB tạm: health 200, 8 bảng; POST scans và GET contacts trả 404. Không thay thế kiểm tra camera/trình duyệt và server triển khai thật.
- Spike mock hai ảnh chạy bằng `--no-save`. Probe offline tái hiện các lỗi ghi ở trên; [JSON kết quả](ket-qua-ngay-1-2.json) giữ đầu vào giả và đầu ra để đối chiếu.
- Chỉ kiểm tra sự hiện diện cấu hình, không in giá trị key. `git check-ignore` xác nhận `.env`, service account, DB, ảnh mẫu bị ignore; chưa kiểm toán bí mật toàn bộ lịch sử Git.
- Không gọi Vision/Gemini, không đo chất lượng ảnh chụp, không sửa logic ứng dụng hoặc tạo commit.

## 10. Đoạn tóm tắt dùng khi trình bày

> Trong hai ngày đầu, dự án đã xây nền tảng Streamlit–FastAPI–SQLite với 8 bảng, lớp OCR/trích xuất và 27 test đang pass. Luồng thử nghiệm chạy được bằng fixture tổng hợp; chưa xác nhận Google Vision/Gemini bằng ảnh thật. Dữ liệu mẫu hiện 0/40 nên checklist dữ liệu Ngày 1 và DoD Ngày 2 chưa hoàn tất. Rà soát bổ sung phát hiện lỗi nối credentials, lưu bằng chứng và grounding nhận sai/loại nhầm. Ưu tiên tiếp theo là sửa các lỗi này, chuẩn bị bốn ảnh Anh/Nhật để kiểm chứng thật, bổ sung nhãn và hoàn thiện phiếu nhà cung cấp trước khi đánh dấu Ngày 2 hoàn thành.
