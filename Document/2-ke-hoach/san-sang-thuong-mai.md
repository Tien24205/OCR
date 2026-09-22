# Kế hoạch đưa sản phẩm tới trạng thái bán được

**Ngày lập:** 21/09/2026. **Trạng thái:** chờ quyết định của chủ dự án ở mục 6.

**Điều kiện bắt đầu đã có:** 27 endpoint, 579 test, bốn trang giao diện, lớp grounding chống bịa dữ liệu, CI năm cổng, bộ 80 thẻ mẫu bốn ngôn ngữ kèm nhãn chuẩn.

**Câu hỏi kế hoạch này trả lời:** còn thiếu gì giữa "chạy được trên máy tôi" và "bán được cho khách hàng thứ hai".

---

## 1. Ba thứ chặn, xếp theo mức chặn

### C1 — Dữ liệu không thuộc về ai

`models.py` có 10 bảng, **không bảng nào có chủ sở hữu**. `API_KEYS` là một danh sách khoá phẳng: mọi khoá nhìn thấy toàn bộ hồ sơ.

Khách hàng thứ hai xuất hiện là dữ liệu hai khách nằm chung một rổ. Đây không phải tính năng gắn thêm ở rìa — mọi truy vấn trong `contact_routes.py` và `main.py` phải lọc theo chủ sở hữu.

**Một lỗ hổng cụ thể đã thấy — đã sửa:** `GET /api/images/{image_ref}` tra ảnh theo mã băm nội dung, nên bất kỳ ai có `image_ref` hợp lệ đều tải được ảnh mà không cần liên quan gì tới bản quét. Nay ảnh chỉ tải được qua `GET /api/scans/{scan_id}/image`; phép kiểm quyền theo `owner_id` sẽ có đúng một chỗ để đặt. Phần còn lại của C1 vẫn nguyên.

### C2 — Danh thiếp là dữ liệu cá nhân, mà không có đường xoá

Trong 27 endpoint, `DELETE` duy nhất dành cho webhook. Không có cách nào xoá một hồ sơ, một bản quét, hay ảnh gốc. Ảnh nằm vô thời hạn trong volume `ocr-data`.

Nghị định 13/2023/NĐ-CP (Việt Nam) và GDPR đều đòi quyền xoá, quyền truy cập và thời hạn lưu trữ. Đây là rủi ro pháp lý, không phải thiếu tiện ích.

### C3 — Chưa có số đo trên ảnh chụp thật

Vẫn 0/40 ảnh thật. Câu hỏi đầu tiên của mọi khách hàng là *"đọc đúng bao nhiêu phần trăm?"*. Không có số thì không định giá được, không viết được SLA, không chọn được thị trường mục tiêu.

---

## 2. Lộ trình

Bốn giai đoạn, xếp theo *mở khoá được nhiều thứ nhất trên mỗi đơn vị công sức*.

### Giai đoạn 1 — Có số thật (rẻ nhất, mở khoá mọi quyết định còn lại)

| Việc | Ghi chú |
| --- | --- |
| In 8 trang `datasets/print/`, **cắt rời từng thẻ**, chụp 80 thẻ | Không phải việc lập trình |
| `import_photos.py --split dev --lang ja --from <thư mục>` | Cổng kiểm ảnh trước khi vào bộ đo |
| `check_labels.py` rồi `evaluate.py --split eval` | Bộ `eval` chỉ chạy **một lần** |
| Ghi số vào `Document/3-bao-cao/` | Kể cả khi số xấu |

**Hoàn thành khi:** có bảng chất lượng theo từng ngôn ngữ và từng trường, đo trên ảnh chụp thật, kèm thời gian xử lý trung bình mỗi thẻ.

**Tình trạng 22/09 — đang chờ ảnh.** Lô 18 tấm đầu tiên bị loại, và lý do đáng ghi lại: đó là thẻ của **một bộ khác** (`Marcus Feld / Halbrook Logistics` — không tên nào có trong `labels.jsonl`, cũng không có trong lịch sử kho này), và tất cả đều chụp **cả trang chưa cắt** nên một ảnh có chữ của hai ba thẻ. Không cổng kiểm nào bắt được: cả hai lỗi chỉ lộ ra ở báo cáo, dưới dạng một con số xấu không ai giải thích được.

Đã xử lý hai việc:

- [`import_photos.py`](../../backend/scripts/import_photos.py) đối chiếu tên người/công ty đọc được với nhãn đang chờ, chặn ảnh còn nhìn thấy mã thẻ (tức là trang chưa cắt), chặn ảnh nhỏ hoặc mờ, và đặt tên `001..010` theo **thời điểm bấm máy**.
- Xác minh bộ sheet trên đĩa đúng là bản khớp nhãn: chạy lại `make_card_sheets.py` cho ra `labels.jsonl` không đổi một byte.

**Vì sao đứng đầu:** nó quyết định ba thứ mà mọi giai đoạn sau đều phụ thuộc — giá bán, thị trường nào (Nhật hay Việt), và có cần đổi nhà cung cấp OCR không.

### Giai đoạn 2 — Nhiều khách hàng dùng chung một hệ thống (C1 + C2)

Hai việc này phải đi cùng nhau: xoá dữ liệu mà chưa biết dữ liệu thuộc về ai thì không xoá đúng được.

| Việc | Chạm vào |
| --- | --- |
| Bảng `Tenant` + `owner_id` trên Contact, Scan, Organization, Enrichment, EnrichmentJob, ContactProfile | `models.py`, migration |
| Ánh xạ khoá API → tenant (thay danh sách khoá phẳng) | `auth.py`, `config.py` |
| Lọc theo `owner_id` ở **mọi** truy vấn | `contact_routes.py`, `main.py`, `stats.py`, `export` |
| ~~`GET /api/images/{ref}` phải kiểm quyền qua bản quét~~ **đã làm trước** | `main.py` — nay là `GET /api/scans/{scan_id}/image` |
| `DELETE /api/contacts/{id}` và `DELETE /api/scans/{id}` | Xoá lan theo email/phone/address/profile |
| Xoá ảnh gốc khi không còn bản quét nào dùng | **Bẫy:** ảnh lưu theo SHA-256 nên hai bản quét có thể dùng chung một tệp. Xoá mù là mất ảnh của bản quét khác |
| Thời hạn lưu trữ cấu hình được + tác vụ dọn | Cấu hình mới `RETENTION_DAYS` |
| Alembic | Đổi schema trên dữ liệu thật mà không có migration là không quay lại được |

**Hoàn thành khi:** một test chứng minh tenant A không đọc được bất kỳ dữ liệu nào của tenant B — gồm cả ảnh; và một test chứng minh xoá hồ sơ thì ảnh dùng chung của bản quét khác **vẫn còn**.

**Đây là giai đoạn dài nhất và đắt nhất nếu làm muộn.** Mỗi hồ sơ, mỗi bản quét tạo ra trước khi có `owner_id` đều là dữ liệu phải sửa tay sau này.

### Giai đoạn 3 — Đưa dữ liệu ra nơi khách thật sự dùng

Khách mua phần mềm quét danh thiếp để **đổ vào CRM**, không phải để tải file về.

| Việc | Vì sao |
| --- | --- |
| Đồng bộ Google Contacts (People API, OAuth) | Rẻ nhất, hạn mức miễn phí rộng, ai cũng có tài khoản Google |
| Quét hai mặt thẻ | Thẻ Nhật hay in tiếng Anh ở mặt sau; hiện README ghi rõ "một ảnh, một thẻ, một mặt" |
| Tag + ghi chú + ngày gặp | Giá trị thật của việc lưu danh thiếp là nhớ gặp ai ở đâu |

**Hoàn thành khi:** một hồ sơ đi từ ảnh chụp tới danh bạ Google mà không phải tải file nào.

**Cố ý chỉ làm MỘT tích hợp.** HubSpot và Salesforce đắt gấp nhiều lần và chỉ đáng làm khi có khách hàng cụ thể đòi.

### Giai đoạn 4 — Vận hành được khi có khách trả tiền

| Việc | Hiện trạng |
| --- | --- |
| Sao lưu và khôi phục có kiểm chứng | Chưa có. SQLite một tệp trong volume |
| Log có cấu trúc + cảnh báo | 10 chỗ ghi log trong toàn bộ `app/` |
| Chuyển SQLite → PostgreSQL | Chỉ khi cần chạy nhiều instance; SQLite dùng tốt tới hàng chục nghìn hồ sơ |
| Trang điều khoản + chính sách dữ liệu | Bắt buộc nếu bán ra thị trường |

**Hoàn thành khi:** khôi phục được toàn bộ dữ liệu từ bản sao lưu trên một máy trắng, và có bằng chứng đã làm thử.

---

## 3. Việc KHÔNG làm trong lộ trình này

| Không làm | Vì sao |
| --- | --- |
| Ứng dụng di động riêng | Đắt gấp nhiều lần một PWA. Chỉ làm khi số đo Giai đoạn 1 cho thấy ảnh chụp điện thoại là nguồn chính |
| Nhiều thẻ trong một ảnh | Cần tách vùng ảnh — một bài toán riêng. Chờ có khách hỏi |
| HubSpot / Salesforce | Xem Giai đoạn 3 |
| Đổi sang RapidOCR làm mặc định | [Báo cáo 21/09](../3-bao-cao/nang-cap-ocr-21-09.md) đã kết luận bằng số: không |
| SQLite FTS5 | Hiện 0 hồ sơ. Tối ưu tìm kiếm khi chưa có gì để tìm là tối ưu tưởng tượng |

---

## 4. Thứ đáng bán mà đối thủ không có

Lớp **grounding**: hệ thống không bao giờ trả về giá trị nó không đọc được từ ảnh, và điều đó chứng minh được bằng số (`rejected`, `rejected_but_correct`, cột "Sai" tách khỏi cột "Tự sinh").

Phần mềm quét danh thiếp khác bịa cho đầy trường rồi để người dùng tự phát hiện. Đây là điểm bán hàng mạnh nhất của dự án và nên nằm ở đầu trang giới thiệu, không phải nằm trong tài liệu kỹ thuật.

---

## 5. Rủi ro

| Rủi ro | Xử lý |
| --- | --- |
| Số đo Giai đoạn 1 quá thấp để bán | Biết sớm vẫn hơn biết sau khi đã bán. Khi đó chuyển hướng: Google Vision (miễn phí 1 000 đơn vị/tháng) hoặc thu hẹp thị trường về một ngôn ngữ |
| Làm C1 muộn | Mọi dữ liệu tạo trước đó phải sửa tay. Làm trước khách hàng đầu tiên |
| Giữ ảnh danh thiếp vô thời hạn | Vi phạm NĐ13/GDPR. Giai đoạn 2 xử lý |
| Hạn mức Gemini miễn phí | 1 000 lượt/ngày. Một khách quét 200 thẻ/ngày là chạm trần — phải có tài khoản trả phí trước khi bán |

---

## 6. Ba câu chủ dự án phải trả lời trước khi bắt đầu Giai đoạn 2

1. **Bán cho ai:** cá nhân (một người, một danh bạ) hay doanh nghiệp (một nhóm dùng chung)? Câu trả lời đổi hẳn thiết kế của `Tenant`.
2. **Thị trường nào trước:** Nhật, Hàn, Trung hay Việt? Quyết định nhà cung cấp OCR và mức đầu tư vào từng ngôn ngữ.
3. **Chạy ở đâu:** khách tự cài trong mạng nội bộ, hay bạn vận hành dịch vụ? Tự cài thì C1 nhẹ đi rất nhiều; vận hành dịch vụ thì Giai đoạn 4 thành bắt buộc.

Chưa trả lời ba câu này thì Giai đoạn 2 có nguy cơ làm sai hướng — nên Giai đoạn 1 vẫn là việc đúng để bắt đầu ngay hôm nay.
