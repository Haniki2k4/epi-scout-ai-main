# Feature: Crawl Data Expansion

## Mục tiêu

Tiếp tục mở rộng kiến trúc nguồn crawl để hệ thống có thể hỗ trợ nhiều loại website hơn, không chỉ RSS, và có khả năng quan sát vận hành tốt hơn.

Phần nền tảng đã có sẵn:

- danh sách nguồn crawl đã được đưa ra khỏi constant hardcode
- crawler hiện đọc nguồn active từ bảng `rss_sources`
- admin đã có CRUD và bật/tắt RSS source trên UI
- startup đã seed default RSS source vào DB nếu bảng còn trống

Tài liệu này chỉ giữ lại phần chưa làm hoặc mới làm một phần.

## Bài toán hiện tại

Sau khi bỏ hardcode `RSS_FEEDS`, các giới hạn còn lại là:

- mô hình nguồn hiện vẫn xoay quanh `rss_sources`, chưa phải source registry tổng quát
- chưa có `source_type` để phân biệt `rss`, `google_news`, `sitemap`, `html_list`, `custom`
- truy vấn Google News hiện vẫn nằm trực tiếp trong `scan_news()`
- logic discovery và logic filtering/persistence vẫn nằm chung trong crawler
- chưa có `crawl_runs` hoặc `source_health` để theo dõi nguồn nào lỗi, stale hoặc chất lượng thấp
- chưa hỗ trợ tốt các site không có RSS hoặc RSS không đi đúng chuyên mục

## Mục tiêu thiết kế

Hệ thống tiếp theo nên cho phép:

- thêm nguồn mới mà không cần sửa logic lõi của crawler
- hỗ trợ nhiều loại nguồn khác nhau, không chỉ RSS
- cấu hình nguồn bằng database theo mô hình mở rộng được
- bật/tắt nguồn linh hoạt theo môi trường và nhu cầu vận hành
- theo dõi trạng thái, lỗi và lịch sử quét của từng nguồn
- tái sử dụng cùng một tầng filter keyword cho mọi loại nguồn

## Hướng tiếp cận đề xuất

### 1. Tổng quát hóa `rss_sources`

Thay vì dừng ở bảng `rss_sources`, nên mở rộng thành mô hình nguồn chung, ví dụ `news_sources`.

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
- `google_news`
- `sitemap`
- `html_list`
- `custom`

Nếu chưa muốn đổi tên bảng ngay, có thể mở rộng trực tiếp `rss_sources` rồi migrate dần sang abstraction mới.

## Kiến trúc crawler nên tách thành 2 lớp

### A. Discovery layer

Nhiệm vụ:

- đọc source config
- chọn adapter đúng theo `source_type`
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
- đánh giá trusted domain
- gọi LLM re-check nếu bật
- resolve event
- lưu article, disease case, event

Điểm quan trọng là tầng filter keyword không nên biết nguồn là RSS, Google News hay HTML listing. Nó chỉ nên nhận dữ liệu đã chuẩn hóa.

## Nên dùng adapter theo loại nguồn

Thay vì để `scan_news()` ôm toàn bộ logic phát hiện nguồn, nên có adapter riêng cho từng loại source.

Ví dụ:

- `RssSourceAdapter`
- `GoogleNewsSourceAdapter`
- `SitemapSourceAdapter`
- `HtmlListingSourceAdapter`
- `CustomSourceAdapter`

Mỗi adapter chỉ cần implement một interface kiểu:

```python
class BaseSourceAdapter:
    def fetch_entries(self, source) -> list[dict]:
        ...
```

## Vì sao vẫn cần Google News / nguồn tổng hợp

Hiện tại crawler đã có nhánh tạo Google News RSS khi người dùng quét theo khoảng ngày. Tuy nhiên phần này mới là logic cài trong crawler, chưa phải source type chính thức.

Google News vẫn có giá trị vì:

- nhiều bài về dịch bệnh không nằm trong chuyên mục `sức khỏe`
- có thể phủ tốt hơn cho keyword hiếm hoặc nguồn quốc tế
- phù hợp với các ca cần quét hồi cứu theo khoảng thời gian

Việc còn thiếu là đưa nó thành adapter riêng và quản lý như một loại nguồn cấu hình được.

## Đề xuất mô hình dữ liệu bổ sung

### Bảng `crawl_runs`

Lưu mỗi lần quét:

- source nào được quét
- thời gian bắt đầu / kết thúc
- số bài lấy được
- số bài match keyword
- số bài lưu thành công
- lỗi nếu có

### Trạng thái `source_health`

Có thể để ngay trên `news_sources` trước, sau đó tách bảng riêng nếu cần lịch sử dài hạn.

Thông tin nên có:

- `last_success_at`
- `last_error`
- `consecutive_failures`
- `stale_since`
- `avg_items_per_run`

## Luồng chạy đề xuất

1. Load danh sách source đang active.
2. Với mỗi source, chọn adapter theo `source_type`.
3. Adapter trả ra list bài viết đã chuẩn hóa.
4. Chạy tầng filter/persistence hiện có.
5. Ghi log kết quả vào `crawl_runs`.
6. Cập nhật trạng thái health của source.

## Lộ trình triển khai thực tế

### Phase 1

Mục tiêu: chuẩn hóa abstraction nguồn trên nền hiện có.

Việc cần làm:

- mở rộng `rss_sources` để có thêm `source_type`, `parser_name`, `config_json`
- tách phần load/feed parsing ra khỏi `scan_news()`
- tạo `BaseSourceAdapter` và `RssSourceAdapter`

### Phase 2

Mục tiêu: thêm các loại nguồn ngoài RSS.

Việc cần làm:

- tách logic Google News hiện tại thành `GoogleNewsSourceAdapter`
- thêm hỗ trợ `sitemap` hoặc `html_list` cho các site không có RSS phù hợp
- chuẩn hóa cấu hình parser theo từng source

### Phase 3

Mục tiêu: quan sát và vận hành tốt hơn.

Việc cần làm:

- thêm `crawl_runs`
- thêm `source_health`
- retry / backoff theo source
- admin UI cho source observability

## Tối thiểu nên làm ngay

Nếu muốn đạt hiệu quả nhanh với effort vừa phải, nên làm theo thứ tự:

1. thêm `source_type` và `config_json` vào nguồn hiện có
2. tách `RssSourceAdapter` khỏi `scan_news()`
3. chuyển Google News sang adapter riêng
4. lưu lịch sử crawl và lỗi gần nhất của từng nguồn

4 bước này sẽ đưa hệ thống từ `RSS config in DB` sang `source architecture có thể mở rộng`.

## Các rủi ro cần lưu ý

- một số site chặn request hoặc thay đổi HTML thường xuyên
- RSS có thể chậm, thiếu summary hoặc trả link trung gian
- nguồn tổng hợp có thể sinh nhiều bản tin trùng nhau
- cần canonicalization link tốt hơn để tránh duplicate
- số lượng source tăng sẽ làm rõ nhu cầu rate limit, retry và observability

## Kết luận

Phần “đưa nguồn RSS ra khỏi code” đã hoàn thành ở mức cơ bản. Vấn đề còn lại bây giờ không còn là hardcode feed nữa, mà là:

- nguồn vẫn chưa được mô hình hóa đủ tổng quát
- crawler vẫn chưa tách discovery khỏi filtering
- hệ thống chưa có lớp adapter và quan sát vận hành theo source

Muốn mở rộng bền vững, bước tiếp theo là chuẩn hóa source thành abstraction chung, rồi bổ sung adapter và telemetry cho từng nguồn.