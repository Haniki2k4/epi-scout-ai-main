# Epi Scout AI

Hệ thống giám sát tin tức dịch bệnh từ RSS, gồm:

- `frontend/`: React + Vite + shadcn/ui
- `backend/`: FastAPI + crawler + MySQL
- `docker-compose.yml`: dịch vụ database local

Project hiện đã vượt mức demo crawl RSS đơn giản. Ngoài luồng quét theo keyword, hệ thống đã có:

- quản lý keyword và whitelist trên UI
- lọc nhiều tầng: regex context + LLM re-check
- chống lỗi rate limit/timeout của LLM bằng cooldown
- lưu bài viết thủ công từ nguồn chưa xác thực
- phân trang, filter, sort cho danh sách bài viết đã lưu
- soft dedupe theo `event`
- similarity score và `dedupe_reason`
- API/UI xem một event gồm những article nào

## 1. Bài toán đặt ra

Mục tiêu ban đầu:

- quản lý danh sách từ khóa giám sát như `H5N1`, `sốt xuất huyết`, `não mô cầu`
- quét nhiều nguồn RSS để phát hiện bài viết liên quan dịch tễ
- tự động lưu bài từ nguồn tin tin cậy
- cho phép người dùng duyệt bài từ nguồn chưa có trong whitelist
- hiển thị danh sách bài viết, thống kê, xu hướng

Trong quá trình làm, project phát sinh thêm các bài toán thực tế:

- RSS feed chứa nhiều bài tư vấn/lifestyle gây false positive
- summary RSS có HTML bẩn như `href`, `img`
- LLM classifier có thể timeout hoặc bị `429`
- cùng một sự kiện có thể được nhiều báo đưa thành nhiều bài khác nhau
- modal danh sách nguồn chưa xác thực dài nhưng không scroll
- endpoint lưu bài thủ công nhận sai payload khi gửi nhiều bài một lúc

## 2. Cách giải quyết các bài toán

### 2.1. Lọc bài viết

Luồng lọc hiện tại:

1. Crawl RSS
2. Chuẩn hóa text
3. Stage-1 regex/context filter
4. Stage-2 LLM re-check
5. Chuẩn hóa metadata: keyword, location, case count, severity
6. Lưu article, disease case và event

Những điểm đã xử lý:

- `normalize_text()` strip HTML tags để tránh hiện nguyên `href`/`img`
- stage-1 chỉ match khi keyword thực sự xuất hiện trong title/summary
- hard exclude các title tư vấn/lifestyle rõ ràng
- LLM disabled thì thực sự bypass API call
- output LLM bị lệch schema không còn làm văng cả feed

### 2.2. LLM timeout / rate limit

Đã bổ sung:

- preflight kiểm tra model/key/base URL
- cooldown khi gặp `429`
- cooldown ngắn khi gặp timeout
- skip LLM trong thời gian cooldown thay vì tiếp tục spam request lỗi

Biến môi trường liên quan:

```env
LLM_RECHECK_ENABLED=false
LLM_RECHECK_MODEL=
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_RECHECK_TIMEOUT_SECONDS=20
LLM_RECHECK_RATE_LIMIT_COOLDOWN_SECONDS=300
LLM_RECHECK_TIMEOUT_COOLDOWN_SECONDS=60
```

### 2.3. Nguồn chưa xác thực

Luồng hiện tại:

- bài từ source không nằm trong whitelist sẽ đi vào modal `Phát hiện nguồn chưa xác thực`
- người dùng có thể:
  - lưu bài đã chọn
  - thêm domain vào whitelist

Đã xử lý thêm:

- `POST /api/whitelist` hiện idempotent, thêm trùng không còn `400`
- frontend lưu từng article thay vì gửi cả mảng vào endpoint single-item
- modal có scroll đúng khi danh sách dài

### 2.4. Trùng bài giữa nhiều nguồn

Hệ thống hiện dùng `soft dedupe theo event`, không hard dedupe theo article.

Tư duy:

- `2 article`
- `1 event`

Nghĩa là nếu nhiều báo cùng đưa một sự kiện:

- vẫn giữ toàn bộ article để giữ nguồn và chi tiết bổ sung
- nhưng gom chúng về cùng một `NewsEvent`

### 2.5. Similarity score

Event matching hiện không còn là rule `or` đơn giản.

Hệ thống chấm điểm theo:

- `title`
- `location`
- `date`
- `case_count`

Nếu tổng điểm vượt ngưỡng, article sẽ gắn vào event cũ. Nếu không, tạo event mới.

Mỗi article hiện lưu thêm:

- `event_match_score`
- `dedupe_reason`

để truy vết vì sao bài đó được gom vào event nào.

## 3. Kiến trúc hiện tại

## 3.1. Luồng backend

1. Người dùng thêm keyword trên UI
2. Frontend gọi `POST /api/keywords`
3. Người dùng bấm quét
4. Frontend gọi `POST /api/scan`
5. Backend:
   - đọc keyword từ DB
   - quét RSS feeds
   - lọc bằng regex/context
   - LLM re-check
   - tính case count/location/tags
   - xác định trusted hay unknown
   - trusted: lưu article + disease case + event
   - unknown: trả về modal để người dùng quyết định
6. Frontend reload articles, events, stats

## 3.2. Luồng frontend

Tab `Quét từ khóa` hiện có:

- quản lý keyword
- điều khiển scan
- danh sách bài viết đã lưu
- card `Sự kiện đã gom`
- dialog xem article theo từng event

## 4. Cấu trúc thư mục

```text
.
├── backend
│   ├── app
│   │   ├── core
│   │   │   └── database.py
│   │   ├── modules
│   │   │   └── news
│   │   │       ├── crawler.py
│   │   │       ├── crud.py
│   │   │       ├── models.py
│   │   │       ├── schemas.py
│   │   │       └── stats.py
│   │   └── main.py
│   ├── requirements.txt
│   └── scripts
├── frontend
│   ├── src
│   ├── package.json
│   └── vite.config.ts
├── docs
│   └── feature-crawl-data-expansion.md
├── docker-compose.yml
└── .env
```

## 5. Các thành phần quan trọng

### 5.1. `backend/app/modules/news/crawler.py`

Chứa logic chính:

- RSS feed list
- text normalization
- keyword/context scoring
- LLM re-check
- cooldown khi provider lỗi
- event similarity scoring
- resolve article -> event
- scan RSS và lưu dữ liệu

### 5.2. `backend/app/modules/news/models.py`

Các model hiện có:

- `ArticleIdentity`
- `ArticleDetails`
- `DiseaseCase`
- `WhitelistDomain`
- `Keyword`
- `NewsEvent`

Lưu ý:

- project chưa dùng migration framework chuẩn
- hiện dùng `ensure_news_schema()` để vá schema cũ lúc startup cho các cột/bảng mới

### 5.3. `frontend/src/components/KeywordMonitoring.tsx`

Đây là màn hình backend operator chính, gồm:

- CRUD keyword
- bật/tắt scan mở rộng
- xem danh sách article đã lưu
- filter/sort/pagination
- xem grouped events
- xem score/reason dedupe của từng article

## 6. API hiện có

### Keywords

- `GET /api/keywords`
- `POST /api/keywords`
- `DELETE /api/keywords/{keyword_id}`

### Articles

- `GET /api/articles`
- `POST /api/articles/save`

### Scan

- `POST /api/scan`

### Whitelist

- `GET /api/whitelist`
- `POST /api/whitelist`

### Events

- `GET /api/events`
- `GET /api/events/{event_id}`

### Stats

- `GET /api/stats/overview`
- `GET /api/stats/trends?days=7`

## 7. Model dữ liệu nghiệp vụ

### 7.1. Article

Một bài báo cụ thể từ một link cụ thể.

Thông tin nổi bật:

- `title`
- `link`
- `source`
- `published_date`
- `keywords_matched`
- `event_id`
- `event_match_score`
- `dedupe_reason`

### 7.2. DiseaseCase

Thông tin ca bệnh được trích từ bài viết:

- `disease_name`
- `case_count`
- `location`
- `report_date`

### 7.3. NewsEvent

Một sự kiện dịch tễ được gom từ nhiều article.

Thông tin nổi bật:

- `canonical_title`
- `disease_name`
- `location`
- `event_date`
- `case_count`
- `severity`
- `fingerprint`

## 8. Quyết định kỹ thuật quan trọng

### 8.1. Vì sao không hard dedupe article

Nếu nhiều báo cùng đưa tin:

- có thể là cùng event
- nhưng khác góc nhìn
- khác số liệu cập nhật
- khác mức xác nhận

Nên hiện tại:

- article vẫn được giữ riêng
- thống kê nghiệp vụ nên dựa vào event

### 8.2. Vì sao similarity score chưa quá phức tạp

Project đang ở mức pragmatic:

- chưa dùng embedding/vector search
- chưa crawl full-content một cách ổn định
- chưa có ranking pipeline riêng

Nên scoring hiện tại ưu tiên:

- dễ hiểu
- dễ debug
- dễ tune threshold

### 8.3. Vì sao chưa dùng migration framework

Hiện project đang chạy theo hướng dev/demo nhanh:

- `Base.metadata.create_all()`
- cộng với `ensure_news_schema()` để vá schema cũ

Đây không phải cách nên dùng lâu dài ở production, nhưng phù hợp để tiếp tục phát triển nhanh trong giai đoạn hiện tại.

## 9. Tính năng UI đã làm

Trong tab `Quét từ khóa`, hiện đã có:

- thêm nhiều keyword một lần
- lọc keyword
- chọn nhiều keyword và xóa hàng loạt
- scan bài viết
- scan mở rộng với unknown source
- modal duyệt unknown source
- thêm whitelist trực tiếp từ modal
- danh sách bài viết đã lưu
- search/filter/sort article
- filter theo trusted/manual
- phân trang article
- card `Sự kiện đã gom`
- dialog xem chi tiết event
- hiển thị `event_match_score` và `dedupe_reason`

## 10. Cách chạy local

## 10.1. Yêu cầu

- Python 3.12+
- Node.js 18+
- Docker + Docker Compose

## 10.2. Biến môi trường

Project đọc `.env` ở root repo.

Ví dụ tối thiểu:

```env
DB_SERVER=localhost
DB_PORT=3306
DB_NAME=EpiScoutDB
DB_USER=epi_scout
DB_PASSWORD=epi_scout_dev_pw
```

## 10.3. Chạy database

```bash
docker compose up -d
docker compose ps
```

## 10.4. Chạy backend

```bash
cd backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cd /path/to/epi-scout-ai-main
backend/venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Backend mặc định:

- `http://127.0.0.1:8000`

## 10.5. Chạy frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend mặc định:

- `http://localhost:8080`

Trong dev mode, request `/api` được proxy về backend.

## 11. Các lỗi đã gặp và đã xử lý

### 11.1. Quét xong nhưng lưu bài thủ công bị `422`

Nguyên nhân:

- frontend từng gửi cả mảng article vào endpoint chỉ nhận một article

Đã xử lý:

- frontend giờ lưu từng bài riêng lẻ

### 11.2. Add whitelist bị `400 Bad Request`

Nguyên nhân:

- backend reject domain đã tồn tại

Đã xử lý:

- endpoint whitelist giờ idempotent

### 11.3. Modal unknown source không scroll

Nguyên nhân:

- thiếu `overflow/min-h` đúng trong flex layout

Đã xử lý:

- sửa layout `DialogContent` + `ScrollArea`

### 11.4. Summary hiện nguyên HTML

Nguyên nhân:

- RSS summary chứa HTML nhưng trước đó chưa strip tag

Đã xử lý:

- strip HTML tag ở `normalize_text()`

### 11.5. LLM bị timeout / `429`

Đã xử lý:

- cooldown theo timeout/rate limit
- skip tạm LLM thay vì spam request lỗi

## 12. Hạn chế hiện tại

- chưa có Alembic hoặc migration chuẩn
- schema patch hiện chỉ đủ cho dev flow
- event matching vẫn là heuristic, chưa dùng embedding
- chưa crawl full article content ổn định
- chưa có auth/permission
- chưa có test tự động đủ mạnh
- chưa có backfill dữ liệu cũ sang event/score/reason
- chưa có dashboard thống kê theo event

## 13. Hướng phát triển tiếp theo

Ưu tiên hợp lý:

1. backfill dữ liệu cũ vào `NewsEvent`
2. chuyển source RSS hardcode sang DB
3. thêm `news_sources` + adapter architecture
4. thêm event-based stats
5. thêm Alembic
6. thêm integration test cho:
   - scan flow
   - whitelist flow
   - save unknown article
   - event matching
7. thêm giao diện theo dõi source health

## 14. Tài liệu liên quan

- thiết kế mở rộng nguồn crawl: [`docs/feature-crawl-data-expansion.md`](/home/suno/Github/epi-scout-ai-main/docs/feature-crawl-data-expansion.md)

## 15. Lệnh hay dùng

Chạy DB:

```bash
docker compose up -d
```

Chạy backend:

```bash
backend/venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Chạy frontend:

```bash
cd frontend
npm run dev
```

Build frontend:

```bash
cd frontend
npm run build
```

Kiểm tra RSS:

```bash
backend/venv/bin/python backend/scripts/debug_rss.py
```

Compile nhanh backend:

```bash
python3 -m py_compile backend/app/main.py backend/app/modules/news/models.py backend/app/modules/news/crud.py backend/app/modules/news/crawler.py backend/app/modules/news/schemas.py
```

H