# Feature: Crawl Data Expansion

## Mục tiêu

Thiết kế lại cách quản lý nguồn crawl để hệ thống có thể mở rộng sang nhiều website khác mà không phải sửa code mỗi lần thêm nguồn mới.

## Bài toán hiện tại

Hiện tại crawler đang dùng danh sách hardcode:

- `RSS_FEEDS` trong [crawler.py](/home/suno/Github/epi-scout-ai-main/backend/app/modules/news/crawler.py)

Vấn đề của cách này:

- thêm nguồn mới phải sửa code
- phải deploy lại backend mỗi lần đổi danh sách feed
- khó bật/tắt nguồn theo môi trường
- phụ thuộc nặng vào việc website có RSS phù hợp hay không
- không hỗ trợ tốt các site không có RSS hoặc RSS không nằm đúng chuyên mục
- khó theo dõi nguồn nào đang lỗi, nguồn nào stale, nguồn nào chất lượng thấp

## Mục tiêu thiết kế

Hệ thống mới nên cho phép:

- thêm nguồn mới mà không cần sửa code
- hỗ trợ nhiều loại nguồn khác nhau, không chỉ RSS
- cấu hình nguồn bằng database hoặc file config
- bật/tắt nguồn linh hoạt
- theo dõi trạng thái từng nguồn
- mở rộng parser theo từng loại website

## Hướng tiếp cận đề xuất

### 1. Đưa source ra khỏi code

Thay vì hardcode `RSS_FEEDS`, tạo bảng cấu hình nguồn dữ liệu, ví dụ `news_sources`.

Gợi ý schema:

- `id`
- `name`
- `base_url`
- `source_type`
- `feed_url`
- `category`
- `is_active`
- `is_trusted`
- `parser_name`
- `crawl_interval_minutes`
- `last_crawled_at`
- `last_success_at`
- `last_error`
- `config_json`

`source_type` có thể là:

- `rss`
- `sitemap`
- `html_list`
- `google_news`
- `custom`

## Kiến trúc crawler nên tách thành 2 lớp

### A. Discovery layer

Nhiệm vụ:

- đọc source config
- lấy danh sách bài viết thô từ từng nguồn
- chuẩn hóa về một format chung

Output chuẩn hóa ví dụ:

```python
{
    "title": "...",
    "link": "...",
    "summary": "...",
    "published_date": ...,
    "source": "...",
}
```

### B. Filtering and persistence layer

Nhiệm vụ:

- chuẩn hóa text
- match keyword
- kiểm tra recency
- kiểm tra whitelist
- lưu bài vào database
- ghi log và thống kê

Điểm quan trọng là logic lọc keyword không nên biết nguồn là RSS hay HTML. Nó chỉ nên nhận dữ liệu đã chuẩn hóa.

## Nên dùng adapter theo loại nguồn

Thay vì một hàm `scan_news()` làm tất cả, nên có adapter theo source type.

Ví dụ:

- `RssSourceAdapter`
- `SitemapSourceAdapter`
- `HtmlListingSourceAdapter`
- `GoogleNewsSourceAdapter`
- `CustomSourceAdapter`

Mỗi adapter chỉ cần implement một interface kiểu:

```python
class BaseSourceAdapter:
    def fetch_entries(self, source) -> list[dict]:
        ...
```

## Vì sao nên thêm Google News / nguồn tổng hợp

Nhiều bài về dịch bệnh không nằm ở chuyên mục `sức khỏe`. Chúng có thể xuất hiện ở:

- `thời sự`
- `thế giới`
- `đời sống`
- `breaking news`

Nếu chỉ bám RSS chuyên mục sức khỏe thì sẽ bỏ sót nhiều bài.

Nguồn tổng hợp theo keyword như Google News RSS có lợi thế:

- coverage rộng hơn
- không cần tự thêm từng site nhỏ
- phù hợp với keyword hiếm như `H5N1`, `Bird Flu`, `Ebola`

## Đề xuất mô hình dữ liệu

### Bảng `news_sources`

Quản lý nguồn crawl.

### Bảng `crawl_runs`

Lưu mỗi lần quét:

- source nào được quét
- thời gian bắt đầu/kết thúc
- số bài lấy được
- số bài match keyword
- số bài lưu thành công
- lỗi nếu có

### Bảng `source_health`

Có thể gộp vào `news_sources`, nhưng nếu cần theo dõi lịch sử thì nên tách.

## Luồng chạy đề xuất

1. Load danh sách source đang active.
2. Với mỗi source, chọn adapter theo `source_type`.
3. Adapter trả ra list bài viết đã chuẩn hóa.
4. Chạy logic filter keyword hiện có.
5. Lưu bài phù hợp.
6. Cập nhật trạng thái crawl của source.

## Lộ trình triển khai thực tế

### Phase 1

Mục tiêu: bỏ hardcode `RSS_FEEDS`.

Việc cần làm:

- tạo model `NewsSource`
- tạo bảng `news_sources`
- seed dữ liệu từ danh sách RSS hiện tại
- sửa `scan_news()` để đọc source từ DB thay vì từ constant

### Phase 2

Mục tiêu: hỗ trợ nhiều loại source.

Việc cần làm:

- tạo adapter base class
- implement `rss` adapter
- implement `google_news` adapter

### Phase 3

Mục tiêu: quan sát và vận hành tốt hơn.

Việc cần làm:

- lưu log crawl
- tracking source health
- retry/backoff
- admin UI cho source management

## Tối thiểu nên làm ngay

Nếu muốn đạt hiệu quả nhanh mà effort thấp, nên làm theo thứ tự:

1. chuyển `RSS_FEEDS` sang DB
2. thêm `news_sources` CRUD
3. hỗ trợ `source_type = rss`
4. thêm `google_news` adapter

Chỉ 4 bước này đã giải quyết phần lớn bài toán scale nguồn dữ liệu.

## Các rủi ro cần lưu ý

- một số site chặn request hoặc thay đổi HTML thường xuyên
- RSS có thể chậm hoặc không chứa đủ summary
- nguồn tổng hợp có thể sinh trùng bài
- cần canonicalization link tốt hơn để tránh lưu duplicate
- cần cơ chế rate limit khi số lượng source tăng

## Kết luận

Vấn đề gốc không phải chỉ là danh sách `RSS_FEEDS` dài hay ngắn. Vấn đề là source config đang nằm trong code.

Muốn mở rộng bền vững, cần:

- biến source thành dữ liệu cấu hình
- tách crawler thành adapter theo loại nguồn
- chuẩn hóa output trước khi filter keyword

Khi đó hệ thống sẽ dễ mở rộng hơn nhiều và không còn phụ thuộc vào việc mỗi website có RSS phù hợp hay không.
