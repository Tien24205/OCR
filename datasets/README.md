# Bộ dữ liệu mẫu và nhãn chuẩn

## Cấu trúc

```text
datasets/
├── dev/en/    10 ảnh tiếng Anh   — dùng khi phát triển, được nhìn thoải mái
├── dev/ja/    10 ảnh tiếng Nhật  — dùng khi phát triển
├── eval/en/   10 ảnh tiếng Anh   — GIỮ RIÊNG, chỉ chạy ở Ngày 9
├── eval/ja/   10 ảnh tiếng Nhật  — GIỮ RIÊNG
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

Phân bổ 40 ảnh sao cho phủ được các tình huống kiểm thử ở Ngày 8:

| Đặc điểm | Số ảnh tối thiểu |
| --- | --- |
| Rõ nét, chụp thẳng, đủ sáng | 20 |
| Nghiêng hoặc chụp bằng điện thoại cầm tay | 8 |
| Mờ hoặc chói/lóa | 4 |
| Thiếu email | 4 |
| Thiếu số điện thoại | 3 |
| Có nhiều hơn một số điện thoại (tel + fax + mobile) | 6 |
| Có số máy lẻ (`内線`, `ext.`) | 3 |
| Tên công ty dài | 3 |
| Song ngữ Nhật–Anh trên cùng một mặt | 4 |
| Không có website trên thẻ (để thử nhánh `not_found` ở Ngày 6) | 4 |

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
