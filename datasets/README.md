# Bộ dữ liệu mẫu và nhãn chuẩn

## Cấu trúc

```text
datasets/
├── dev/en/    10 ảnh tiếng Anh   — dùng khi phát triển, được nhìn thoải mái
├── dev/ja/    10 ảnh tiếng Nhật  — dùng khi phát triển
├── dev/ko/    10 ảnh tiếng Hàn   — dùng khi phát triển
├── dev/zh/    10 ảnh tiếng Trung — dùng khi phát triển
├── eval/en/   10 ảnh tiếng Anh   — GIỮ RIÊNG, chỉ chạy ở Ngày 9
├── eval/ja/   10 ảnh tiếng Nhật  — GIỮ RIÊNG
├── eval/ko/   10 ảnh tiếng Hàn   — GIỮ RIÊNG
├── eval/zh/   10 ảnh tiếng Trung — GIỮ RIÊNG
└── labels.jsonl                  — nhãn chuẩn, mỗi dòng một ảnh
```

**Quy tắc quan trọng nhất:** không debug trên bộ `eval/`. Mỗi lần bạn nhìn một ảnh eval rồi sửa code cho nó chạy đúng, bộ đó mất giá trị đánh giá. Ngày 9 chỉ chạy bộ eval **một lần** để lấy số liệu báo cáo.

## Nguồn ảnh được phép dùng

Danh thiếp chứa thông tin cá nhân thật. Chọn theo thứ tự ưu tiên:

1. Danh thiếp của chính bạn và đồng nghiệp đã đồng ý.
2. Danh thiếp mẫu/template công khai của các nhà in (tìm "business card template", "名刺 サンプル").
3. Danh thiếp bạn tự tạo bằng Canva/Figma với tên và công ty hư cấu — hợp pháp và kiểm soát được nội dung, nhưng **phải in ra rồi chụp lại**, không dùng file PNG gốc sắc nét, vì ảnh quá đẹp sẽ cho kết quả OCR lạc quan không đúng thực tế.

Thư mục ảnh đã bị `.gitignore` chặn. Chỉ commit `labels.jsonl` nếu nội dung là dữ liệu hư cấu.

## Độ đa dạng cần có

Phân bổ 80 ảnh (bốn ngôn ngữ của đề gốc) sao cho phủ được các tình huống
kiểm thử ở Ngày 8:

| Đặc điểm | Số ảnh tối thiểu |
| --- | --- |
| Rõ nét, chụp thẳng, đủ sáng | 40 |
| Nghiêng hoặc chụp bằng điện thoại cầm tay | 16 |
| Mờ hoặc chói/lóa | 8 |
| Thiếu email | 8 |
| Thiếu số điện thoại | 6 |
| Có nhiều hơn một số điện thoại (tel + fax + mobile) | 12 |
| Có số máy lẻ (`内線`, `내선`, `分机`, `ext.`) | 6 |
| Tên công ty dài | 6 |
| Song ngữ bản địa–Anh trên cùng một mặt | 8 |
| Không có website trên thẻ (để thử nhánh `not_found` ở Ngày 6) | 8 |

`make_card_sheets.py` đã sinh sẵn đúng phân bổ này: mỗi ngôn ngữ 10 thẻ dev +
10 thẻ eval, lặp lại cùng một bộ 10 tình huống. Việc còn lại là in, cắt và
chụp — phần xuống cấp ảnh (nghiêng, mờ, chói) chỉ có thể tạo ra khi chụp.

## In, cắt, chụp và đưa ảnh vào

1. In **8 trang** trong `datasets/print/` ở tỷ lệ 100% (Actual size), **không**
   dùng Fit to page. Mã thẻ (`EN-D-01`…) nằm ngoài viền, ở lề trang.
2. **Cắt rời từng thẻ theo viền.** Mã thẻ bị cắt mất là đúng — nó ở đó để bạn
   giữ thứ tự, không phải để OCR đọc. Chụp cả trang chưa cắt thì một ảnh có
   chữ của hai ba thẻ, và cả đường ống được viết theo giao ước *một ảnh, một
   thẻ, một mặt*.
3. Chụp **một thẻ một ảnh**, đi lần lượt từ thẻ 01 đến thẻ 10 của từng trang.
   Giữ khoảng cách đủ để máy lấy nét — thẻ chiếm gần hết khung là vừa, sát quá
   thì ống kính điện thoại không nét được.
4. Đổ ảnh của **một ngôn ngữ, một split** vào một thư mục rồi chạy:

```
python backend/scripts/import_photos.py --split dev --lang ja --from <thư mục>
python backend/scripts/import_photos.py --split dev --lang ja --from <thư mục> --apply
```

Lần chạy đầu chỉ in kế hoạch và các lỗi; `--apply` mới thực sự chép vào
`datasets/dev/ja/001.jpg`… theo đúng thứ tự bấm máy. Script chặn ba lỗi không
lộ ra lúc chạy mà chỉ lộ ra ở báo cáo dưới dạng một con số xấu khó giải thích:
ảnh quá nhỏ hoặc quá mờ, ảnh còn nhìn thấy mã thẻ (tức là trang chưa cắt), và
ảnh không phải thẻ mà nhãn đang mô tả — chẳng hạn khi in nhầm bộ thẻ cũ.

## Cách gán nhãn

**Gán nhãn từ ảnh, không phải từ đầu ra OCR.** Nếu bạn copy kết quả OCR làm đáp án, số đo Ngày 9 sẽ luôn là 100% và hoàn toàn vô nghĩa.

Với các trường tiếng Nhật bạn không chắc, nhờ người đọc được tiếng Nhật kiểm tra. Ghi vào `uncertain` những trường mà chính bạn cũng không đọc được từ ảnh — chúng bị loại khỏi phép đo thay vì bị tính là lỗi của máy.

Mỗi dòng trong `labels.jsonl` là một JSON:

```json
{"image": "dev/ja/001.jpg", "lang": "ja", "full_name": "山田 太郎", "company_name": "株式会社サンプル", "job_titles": ["営業部長"], "departments": ["営業部"], "emails": ["taro.yamada@example.co.jp"], "phones": [{"value": "03-1234-5678", "label": "tel", "extension": "102"}, {"value": "090-1234-5678", "label": "mobile"}], "websites": ["https://www.example.co.jp"], "addresses": ["〒100-0001 東京都千代田区千代田1-1-1"], "uncertain": []}
```

Quy ước:

- Trường **không có trên thẻ** → bỏ hẳn khỏi JSON hoặc để mảng rỗng. Đừng ghi `null` cho trường có thật nhưng khó đọc.
- Trường **có trên thẻ nhưng chính bạn không đọc nổi** → thêm tên trường vào `uncertain`.
- Sao chép **nguyên văn**, giữ đúng khoảng trắng, dấu gạch, ký tự 〒 và chữ full-width.
- Số điện thoại chép đúng như in trên thẻ, kể cả dấu cách và ngoặc.

Kiểm tra nhãn bằng: `python backend/scripts/check_labels.py`
