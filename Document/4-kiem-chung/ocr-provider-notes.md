# Phiếu ghi chép nhà cung cấp OCR — Ngày 2

> **Cập nhật 14/09/2026:** Đã có `--check` để kiểm tra credentials bằng 2 lời gọi (mục A2), và 17 test dựng lại cấu trúc phản hồi thật của Vision để kiểm chứng phần đọc dữ liệu trước khi tốn tiền gọi API. Bộ mẫu 40 nhãn chuẩn và 4 trang A4 để in đã sẵn sàng — xem `backend/scripts/make_card_sheets.py`. Vẫn **chưa có lời gọi thật nào**.

> **Cập nhật Ngày 4, 11/09/2026:** Đã sửa đường dẫn credentials tương đối và truyền trực tiếp cho Vision SDK, dùng chung factory giữa app và spike; đã nối pipeline, timeout, retry và lưu bằng chứng vào DB. Xem [báo cáo Ngày 4](../3-bao-cao/ngay-4.md). Chưa có lời gọi thật. Các lỗi `--no-extract` và ghi đè fixture của script nêu trong đính chính bên dưới vẫn còn; việc lưu DB không thay thế bốn fixture OCR thật của Ngày 2.

> **Cập nhật 14/09/2026 — ba lỗi nêu bên dưới đã sửa xong:**
> `--no-extract` nay lưu kết quả OCR và trả mã thoát 0 khi OCR thành công;
> chạy ở chế độ mock không còn ghi đè được fixture (kết quả mock bị từ chối
> ghi, kèm thông báo giải thích); đường truyền credentials hỗ trợ đầy đủ cả
> file service account lẫn ADC. Mục B/C/D/F vẫn chờ bằng chứng thực tế.

> **Đính chính 11/09/2026:** Xem [rà soát Ngày 1–2](ra-soat-ngay-1-2.md). Trước khi chạy thật cần sửa đường truyền credentials và cách lưu kết quả; mock replay hiện có thể ghi đè fixture. `--no-extract` hiện không lưu OCR và trả exit 1 dù OCR thành công.

Mục 6 của kế hoạch Ngày 2 yêu cầu ghi lại nhà cung cấp, phiên bản, cách cấu hình, giới hạn và chi phí cần theo dõi. File này là nơi ghi.

**Trạng thái:** phần A (cài đặt) đã xong. Phần B, C, D **chưa điền** vì chưa có tài khoản dịch vụ — đây là việc phải làm khi có credentials.

---

## A. Thư viện đã cài (đã xác nhận)

| Thư viện | Phiên bản | Dùng để |
| --- | --- | --- |
| `google-cloud-vision` | 3.15.0 | OCR — feature `DOCUMENT_TEXT_DETECTION` |
| `google-genai` | 2.22.0 | Trích xuất trường có schema |
| Python | 3.11.9 | |

Cấu hình trong `backend/.env`:

```ini
OCR_PROVIDER=google
GOOGLE_APPLICATION_CREDENTIALS=./secrets/gcp-sa.json
OCR_LANGUAGE_HINTS=ja,en
OCR_TIMEOUT_S=20

EXTRACTOR=gemini
GEMINI_API_KEY=<khóa từ Google AI Studio>
GEMINI_MODEL=<xem phần B>
GEMINI_TEMPERATURE=0
```

`secrets/` đã bị `.gitignore` chặn.

---

## A2. Kiểm tra sẵn sàng trước khi chạy cả bộ

Sau khi điền `backend/.env`, chạy:

```powershell
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py --check
```

Lệnh này dùng **đúng hai lời gọi dịch vụ** để trả lời bốn câu hỏi riêng biệt:

1. Credentials của Vision có đọc được không?
2. Vision có thật sự trả về chữ tiếng Nhật không?
3. `GEMINI_MODEL` có tồn tại với tài khoản này không?
4. Model có **chấp nhận schema `CardExtraction`** không?

Câu 4 là ẩn số lớn nhất của cả dự án — schema đó chưa từng được model nào chấp nhận lần nào.

**Vì sao không chạy thẳng 40 ảnh:** cấu hình sai sẽ cho 40 lỗi giống nhau, khó biết lỗi nằm ở đâu, mà những lần gọi thành công vẫn bị tính tiền.

---

## B. Chọn model Gemini — **đã xác minh 14/09/2026**

Tên model Gemini thay đổi theo thời gian và khác nhau giữa các tài khoản. **Không đoán tên rồi hardcode** — sẽ gặp lỗi 404 khó chẩn đoán. Hỏi thẳng API:

```powershell
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py --list-models
```

Lệnh này liệt kê mọi model tài khoản bạn dùng được, kèm giới hạn token vào/ra. Chọn một model **có khả năng đọc ảnh (vision)** và điền vào `GEMINI_MODEL`.

Ghi lại kết quả tại đây:

| Mục | Giá trị |
| --- | --- |
| **Model đang dùng** | **`gemini-3.5-flash-lite`** — chốt ngày 15/09 |
| Giới hạn token vào / ra | 1 048 576 / 65 536 |
| Lý do chọn | Bản chính thức (không phải `preview`), trả lời ổn định, đọc đúng chữ Nhật, chấp nhận schema `CardExtraction` |
| Ngày kiểm tra | 15/09/2026 |

### Đã thử những model nào — 15/09/2026

Mỗi model đúng một lời gọi thật, trên cùng một ảnh tiếng Nhật:

| Model | Kết quả |
| --- | --- |
| `gemini-2.5-flash` | **404 NOT_FOUND** — có trong `--list-models` nhưng gọi không được |
| `gemini-2.5-flash-lite` | **404 NOT_FOUND** — như trên |
| `gemini-3.5-flash-lite` | ✅ đọc đúng `山田 太郎` và `株式会社青葉テクノロジー` |
| `gemini-3-flash-preview` | ✅ đúng, nhưng là bản `preview` nên không chọn |
| `gemini-3.5-flash` | **503** liên tục hai ngày — "experiencing high demand" |

**Bài học đáng ghi:** `--list-models` liệt kê model mà tài khoản *nhìn thấy*,
không phải model *gọi được*. Hai model bậc 2.5 nằm trong danh sách nhưng trả
404. Chỉ có gọi thật mới biết — đúng lý do `--check` tồn tại.

`gemini-3.5-flash` bị bỏ vì hai lý do cộng lại: hạn mức 20 lượt/ngày (xem
dưới) và 503 lặp lại. Một model đúng về lý thuyết mà không gọi được thì
không dùng được.

> ### ⚠ Model này KHÔNG đủ để đo 40 thẻ
>
> Phát hiện ngày 14/09 khi chạy thử đường đo: bậc miễn phí của
> `gemini-3.5-flash` giới hạn **20 lượt gọi mỗi ngày mỗi model**. Nguyên văn
> phản hồi của Google:
>
> ```
> Quota exceeded for metric: generate_content_free_tier_requests,
> limit: 20, model: gemini-3.5-flash
> quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier
> ```
>
> Đo 40 thẻ cần tối thiểu 40 lượt — **gấp đôi hạn mức**. Ba đường đi:
>
> | Cách | Đánh đổi |
> | --- | --- |
> | Đổi sang model có hạn mức lớn hơn (bậc `flash-lite`) | Chất lượng thấp hơn một chút, nhưng đo được trong một ngày |
> | Chia làm hai ngày, mỗi ngày 20 thẻ | Miễn phí, nhưng hai nửa bộ mẫu đo ở hai thời điểm khác nhau |
> | Bật thanh toán trên Google AI Studio | Hết giới hạn, nhưng phải gắn thẻ |
>
> **Kiểm hạn mức thật của tài khoản bạn tại <https://ai.dev/rate-limit>** —
> con số ở đây là của một tài khoản cụ thể vào một ngày cụ thể, đừng chép lại
> làm sự thật chung.
>
> Lựa chọn model ở bảng trên được chốt trước khi biết ràng buộc này. Nó vẫn
> đúng về mặt chất lượng và tính ổn định, nhưng **chưa tính tới hạn mức** —
> và hạn mức mới là thứ đang chặn việc đo.

**Vì sao không chọn `gemini-flash-latest`:** đó là bí danh trôi — Google trỏ nó
sang model khác bất cứ lúc nào. Dự án này công bố số đo chất lượng, mà số đo chỉ
có nghĩa khi nói rõ đo trên cái gì. Một cái tên trôi khiến kết quả hôm nay không
lặp lại được vào tháng sau, và tệ hơn: chất lượng tụt mà không ai biết vì sao.
Tên cố định thì khi đổi model là một thay đổi có chủ ý, có commit, đo lại được.

**Vì sao không chọn bản `preview`:** Google có thể rút bản preview mà không báo
trước, và không cam kết hành vi ổn định giữa các lần cập nhật.

### Câu hỏi 4 đã có lời đáp

Ẩn số lớn nhất của dự án — *model có chấp nhận schema `CardExtraction` không* —
đã được trả lời bằng một lời gọi dịch vụ thật:

```
[2/2] Gemini - trich xuat truong co schema
      OK   - model 'gemini-3.5-flash' chap nhan schema CardExtraction
      Ho ten doc duoc : 山田 太郎
      Email doc duoc  : taro@example.co.jp
```

Schema được chấp nhận nguyên vẹn, và chữ Nhật đi qua toàn tuyến không hỏng.
Trước đây điều này chỉ được kiểm bằng `t_schema()` cục bộ — tức mới chứng minh
schema *hợp lệ về hình thức*, chưa chứng minh máy chủ *nhận*. Nay đã có cả hai.

**Phần còn thiếu:** Google Cloud Vision vẫn chưa cấu hình (`OCR_PROVIDER=mock`,
chưa có `backend/secrets/gcp-sa.json`), nên câu 1 và 2 còn bỏ ngỏ và `--check`
vẫn kết luận *chưa sẵn sàng*. Đó là việc duy nhất chắn giữa dự án và số đo thật.

---

## B2. Đường đo đã chạy trọn vẹn — 15/09/2026

Chạy khô trên `datasets/_dryrun` (ảnh số sắc nét, **không phải ảnh chụp**):

```
Ảnh có   : 10   ·   thiếu ảnh: 0
NGÔN NGỮ    CÓ THẬT   ĐÚNG   SAI   SÓT  TỰ SINH   TỶ LỆ
ja               78     78     0     0        0  100.0%
```

**Con số 100% này không nói gì về chất lượng hệ thống.** OCR đang là `mock`,
tức phát lại văn bản tổng hợp hoàn hảo — không có nhiễu OCR nào để mà sai.
Nó chỉ đo được một việc: Gemini có chép đúng các trường từ một đoạn văn bản
sạch hay không.

Cái nó **thật sự chứng minh** là công cụ đo chạy được từ đầu tới cuối: đọc
nhãn chuẩn, gọi hai tầng, so sánh theo quy tắc đã chốt, sinh đủ ba tệp
`.md` / `.csv` / `.json`. Trước hôm nay điều đó chưa từng được kiểm.

Bản thân báo cáo sinh ra đã tự in hai cảnh báo "CHẠY KHÔ — số liệu này vô
nghĩa để nghiệm thu" ngay đầu tệp, nên không ai đọc nhầm được.

---

## C. Kết quả chạy thật — **cần điền**

Chạy trên ít nhất 2 ảnh tiếng Anh và 2 ảnh tiếng Nhật:

```powershell
.\.venv\Scripts\python.exe backend\scripts\try_ocr.py datasets\dev\ja\001.jpg datasets\dev\ja\002.jpg datasets\dev\en\001.jpg datasets\dev\en\002.jpg
```

Script tự in bảng tổng kết. Chép vào đây:

| Ảnh | Ký tự | OCR ms | Xuất ms | Khớp | Gần đúng | **Bị loại** |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | | |

**Cột "Bị loại" đếm giá trị không đối chiếu được với văn bản OCR.** Không được đồng nhất với dữ liệu model tự sinh: OCR có thể bỏ sót chữ, hoặc grounding loại nhầm. Cột "Tự sinh/không có trên ảnh" của Ngày 9 phải dựa vào ảnh và nhãn chuẩn. Báo riêng số bị grounding loại, số bị loại nhầm, số gán sai trường và số không có trên ảnh; giữ đầu ra trước/sau lọc.

Câu hỏi phải trả lời được sau khi chạy:

- [ ] Chữ Nhật hiển thị đúng trong terminal, không thành `?????` hay ô vuông?
- [ ] Vision có đọc được thẻ tiếng Nhật không? Chất lượng so với thẻ tiếng Anh?
- [ ] Gemini có bịa trường nào không? Bao nhiêu trên tổng số?
- [ ] Có trường nào bị bỏ sót dù rõ ràng có trên thẻ?
- [ ] Thời gian xử lý mỗi thẻ khoảng bao nhiêu?

---

## D. Giới hạn và chi phí cần theo dõi — **cần điền**

| Mục | Giá trị | Nguồn |
| --- | --- | --- |
| Vision — giá mỗi 1000 ảnh | *(điền)* | bảng giá Google Cloud |
| Vision — hạn mức miễn phí mỗi tháng | *(điền)* | |
| Vision — quota request/phút | *(điền)* | |
| Gemini — giá vào/ra mỗi 1M token | *(điền)* | bảng giá Gemini API |
| Gemini — hạn mức miễn phí | *(điền)* | |
| Ước tính chi phí cho 40 ảnh mẫu | *(điền)* | |
| Ngân sách tự đặt cho cả dự án | *(điền)* | |

**Vì sao phải ghi:** mỗi ảnh đi qua **hai** dịch vụ tính tiền. Bộ mẫu 40 ảnh sẽ chạy nhiều lần trong quá trình phát triển, không phải một lần. Biết trước con số giúp phát hiện sớm nếu có gì đó gọi API trong vòng lặp.

---

## E. Đường lui nếu không lấy được quyền truy cập

Các phương án dự phòng: mock và heuristic đã có mã; phương án Gemini làm cả OCR lẫn trích xuất **chưa được triển khai**, cần adapter mới và kiểm thử, không chỉ đổi biến cấu hình.

| Tình huống | Đường lui | Hạn chế |
| --- | --- | --- |
| Không có Google Cloud project | Dùng Gemini API key đơn thuần (không cần GCP) làm cả OCR lẫn trích xuất | Mất `raw_text` độc lập, nên **grounding yếu đi đáng kể** — cả hai tầng cùng một model thì không còn bằng chứng độc lập để đối chiếu |
| Không có Gemini | `EXTRACTOR=heuristic` — bộ regex có sẵn | Bắt tốt email/điện thoại/website; kém với tên người và chức danh |
| Không có gì | `OCR_PROVIDER=mock` — chạy lại fixture đã lưu | Chỉ để phát triển giao diện, **không phải kết quả OCR** |

Đường lui đầu tiên có một cái giá cần hiểu rõ: kiến trúc hiện tại mạnh vì Vision đọc chữ (bằng chứng từ điểm ảnh) còn Gemini gán trường (mô hình sinh), rồi đối chiếu hai bên. Nếu để Gemini làm cả hai việc, nó tự chấm điểm chính mình.

---

## F. Nguồn tra cứu doanh nghiệp (mục 5 của Ngày 2) — **cần điền**

Phương án đã chốt: lấy domain từ website hoặc email trên thẻ, tải vài trang công khai, không dùng Search API trả phí.

Kiểm tra trước khi sang Ngày 6:

- [ ] Thử tải trang chủ của 2–3 công ty trong bộ mẫu bằng `httpx` — có bị chặn không?
- [ ] Các trang đó có `/about`, `/company` hoặc `/会社概要` không?
- [ ] `robots.txt` của chúng có cấm không?
- [ ] Bao nhiêu thẻ trong bộ mẫu **không có** website hay email công ty? (những thẻ này sẽ đi vào nhánh `not_found`, cần ít nhất một mẫu để kiểm thử)
