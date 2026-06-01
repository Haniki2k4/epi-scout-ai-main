# Epi Scout AI- 0.3.48

Hệ thống giám sát tin tức dịch bệnh đa người dùng, gồm:

- `frontend/`: React + Vite + shadcn/ui
- `backend/`: FastAPI + crawler + analytics + reporting
- `docker-compose.yml`: hạ tầng local cho MySQL và Qdrant

Project hiện tại đã vượt mức demo crawl RSS đơn giản. Ngoài luồng quét theo keyword, hệ thống đã có:

- xác thực người dùng và phân quyền `user` / `admin`
- quản trị keyword và RSS source trên admin panel
- auto scan bằng APScheduler
- lọc nhiều tầng: regex/context + LLM re-check tùy chọn
- gom nhiều article về cùng một `NewsEvent`
- lưu `DiseaseCase` để phục vụ thống kê theo bệnh, thời gian và địa bàn
- dashboard heatmap, top disease, trend, z-score, forecast
- bookmark bài viết, alert cá nhân và feed theo bộ lọc riêng
- xuất báo cáo Word/Excel và gửi email qua Mailtrap

## 1. Bài toán đặt ra

Mục tiêu hiện tại của hệ thống:

- theo dõi các từ khóa dịch tễ như `H5N1`, `sốt xuất huyết`, `sởi`, `bạch hầu`
- quét nhiều nguồn RSS để phát hiện bài viết liên quan dịch tễ
- giảm false positive từ các bài tư vấn/lifestyle hoặc tin không phải ổ dịch
- gom nhiều bài báo về cùng một sự kiện để tránh nhìn dữ liệu rời rạc
- cung cấp dashboard, cảnh báo cá nhân và báo cáo cho vận hành

Trong quá trình làm, hệ thống phát sinh thêm các nhu cầu thực tế:

- nguồn tin cần quản lý động thay vì hardcode trong code
- bài RSS thường chứa HTML bẩn hoặc summary quá nghèo
- LLM classifier có thể timeout hoặc bị rate limit
- cùng một sự kiện có thể xuất hiện trên nhiều nguồn với wording khác nhau
- người dùng nghiệp vụ cần theo dõi bài theo bộ lọc riêng và nhận báo cáo định kỳ
- admin cần cấu hình lịch quét, tài khoản, email và dữ liệu nguồn ngay trên UI

## 2. Cách giải quyết các bài toán

### 2.1. Luồng crawl và lọc bài viết

Luồng backend hiện tại:

1. Load keyword đang active từ DB
2. Load RSS source đang active từ bảng `rss_sources`
3. Parse feed, chuẩn hóa title/summary, cố gắng lấy thêm `sapo`
4. Stage-1 regex/context filter
5. Stage-2 LLM re-check nếu được bật
6. Trích xuất disease, location, case count, severity
7. Gom article vào `NewsEvent`
8. Lưu `ArticleIdentity`, `ArticleDetails` và `DiseaseCase`

Những điểm đã xử lý:

- `normalize_text()` strip HTML tag trong title/summary
- stage-1 chỉ giữ các bài có tín hiệu keyword + context đủ mạnh
- hard exclude các title tư vấn/lifestyle/video rõ ràng
- có thể bypass hoàn toàn LLM khi `LLM_RECHECK_ENABLED=false`
- nếu có quét theo khoảng ngày, crawler bổ sung truy vấn Google News RSS cho tập domain trusted
- domain trusted được suy ra từ các RSS source đang active, không còn hardcode trong luồng chính

### 2.2. LLM timeout / rate limit

Đã bổ sung:

- preflight kiểm tra model/key/base URL
- cooldown khi gặp `429`
- cooldown ngắn khi gặp timeout
- skip tạm LLM trong thời gian cooldown thay vì spam request lỗi

Biến môi trường liên quan:

```env
LLM_RECHECK_ENABLED=false
LLM_RECHECK_MODEL=gemini-2.5-flash
OPENAI_API_KEY=
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_RECHECK_TIMEOUT_SECONDS=20
LLM_RECHECK_RATE_LIMIT_COOLDOWN_SECONDS=300
LLM_RECHECK_TIMEOUT_COOLDOWN_SECONDS=60
```

### 2.3. Quản lý nguồn crawl

Luồng hiện tại:

- danh sách nguồn nằm trong bảng `rss_sources`
- startup sẽ seed default RSS sources nếu bảng còn trống
- admin có thể:
  - thêm nguồn RSS mới
  - bật/tắt nguồn
  - xóa nguồn không dùng nữa

Điểm cần lưu ý:

- mô hình hiện tại vẫn là `RSS-first`
- chưa có abstraction chung cho `sitemap`, `html_list`, `google_news`, `custom`

### 2.4. Gom bài theo sự kiện

Hệ thống hiện dùng `event-level dedupe`, không hard dedupe article.

Tư duy:

- `n article`
- `1 event`

Nghĩa là nếu nhiều báo cùng đưa một sự kiện:

- vẫn giữ toàn bộ article để bảo toàn nguồn
- nhưng gom chúng về cùng một `NewsEvent`

Mỗi article hiện lưu thêm:

- `event_id`
- `event_match_score`
- `dedupe_reason`

để truy vết lý do vì sao bài được gắn vào event nào.

### 2.5. Dashboard, phân tích và báo cáo

Hệ thống hiện đã có:

- `overview stats`
- top disease theo mốc thời gian
- heatmap địa danh trên bản đồ Việt Nam
- stacked trend và interest trend theo bệnh
- z-score spike detection
- forecast xu hướng bằng Prophet
- keyword diversity / keyword z-score
- xuất Word report
- xuất Excel theo biểu mẫu EBS
- gửi email báo cáo qua Mailtrap

### 2.6. Alert cá nhân và lịch gửi báo cáo

Người dùng hiện có thể:

- tạo nhiều `UserAlert` theo keyword và địa bàn
- xem feed bài viết khớp với từng alert
- bookmark bài viết để xem lại
- cấu hình email cá nhân
- chọn lịch gửi `hourly`, `daily`, `weekly`
- chọn nhận báo cáo toàn hệ thống hoặc theo một alert cụ thể

## 3. Kiến trúc hiện tại

### 3.1. Luồng backend

1. Người dùng đăng nhập để lấy JWT
2. Admin quản trị keyword, RSS source, user, scheduler
3. Khi scan chạy:
   - load keyword active
   - load RSS source active
   - parse feed
   - filter bằng regex/context
   - LLM re-check nếu bật
   - trích xuất disease/location/case count
   - resolve article -> event
   - lưu article, event, disease case
4. Module stats đọc dữ liệu đã lưu để trả dashboard
5. Module report dựng file Word/Excel và gửi email

### 3.2. Luồng frontend

Màn hình chính hiện có các tab:

- `Tổng quan`
- `Tin tức`
- `Phân tích`
- `Báo cáo tự động`
- `Cảnh báo`
- `Bookmark` (đi từ menu người dùng)

Admin panel hiện có:

- quản lý tài khoản
- quản lý article
- quản lý keyword và RSS source
- cấu hình scheduler / manual scan
- cấu hình email gửi báo cáo

### 3.3. Luồng scheduler

1. FastAPI startup -> khởi động APScheduler
2. Scheduler đọc `scheduler_config`
3. Theo chu kỳ cấu hình, hệ thống auto scan từ `last_run_at` đến `now`
4. Kết quả scan cập nhật:
   - `last_run_at`
   - `next_run_at`
   - `last_run_saved_count`
5. Nếu user có lịch email, scheduler đăng ký thêm job gửi báo cáo cá nhân

## 4. Cấu trúc thư mục

```text
.
├── backend
│   ├── alembic
│   ├── app
│   │   ├── core
│   │   │   ├── database.py
│   │   │   └── logger.py
│   │   ├── modules
│   │   │   ├── admin
│   │   │   ├── auth
│   │   │   ├── news
│   │   │   └── report
│   │   ├── main.py
│   │   └── scheduler.py
│   ├── requirements.txt
│   └── scripts
├── frontend
│   ├── public
│   ├── src
│   │   ├── components
│   │   ├── contexts
│   │   └── pages
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

- parse RSS feeds
- chuẩn hóa text
- regex/context scoring
- LLM re-check
- cooldown khi provider lỗi
- similarity scoring để ghép event
- resolve article -> event
- scan và lưu dữ liệu

### 5.2. `backend/app/modules/news/stats.py`

Chứa logic thống kê phục vụ dashboard:

- overview stats
- top disease
- heatmap theo địa danh
- stacked trends / interest trends
- z-score spikes
- forecast

### 5.3. `backend/app/scheduler.py`

Chứa logic vận hành nền:

- APScheduler bootstrap
- auto scan theo chu kỳ
- manual run từ admin panel
- đăng ký lịch gửi email cá nhân

### 5.4. `backend/app/modules/report`

Chứa pipeline báo cáo:

- `generator.py`: gom dữ liệu báo cáo
- `docx_builder.py`: dựng file Word
- `excel_builder.py`: dựng file Excel EBS
- `email_sender.py`: gửi email qua Mailtrap

### 5.5. `frontend/src/components`

Các màn hình vận hành chính:

- `DashboardOverview.tsx`
- `KeywordMonitoring.tsx`
- `DataAnalysis.tsx`
- `AlertsPage.tsx`
- `admin/ResourceManagement.tsx`
- `admin/SchedulerConfig.tsx`

## 6. API hiện có

### Auth

- `POST /api/auth/login`
- `GET /api/auth/me`
- `PUT /api/auth/me`
- `POST /api/auth/me/send-report-now`

### Keywords

- `GET /api/keywords`
- `POST /api/keywords`
- `PUT /api/keywords/{keyword_id}`
- `PATCH /api/keywords/{keyword_id}/toggle`
- `DELETE /api/keywords/{keyword_id}`

### RSS Sources

- `GET /api/rss-sources`
- `POST /api/rss-sources`
- `PATCH /api/rss-sources/{source_id}/toggle`
- `DELETE /api/rss-sources/{source_id}`

### Scan / Scheduler

- `POST /api/scan`
- `GET /api/scan-status`
- `GET /api/scheduler/status`
- `PUT /api/scheduler/config`
- `POST /api/scheduler/run-now`

### Articles / Events / Bookmarks

- `GET /api/articles`
- `POST /api/articles/save`
- `DELETE /api/articles/{article_id}`
- `GET /api/events`
- `GET /api/events/{event_id}`
- `POST /api/bookmarks/{article_id}`
- `DELETE /api/bookmarks/{article_id}`
- `GET /api/bookmarks`

### Stats

- `GET /api/stats/overview`
- `GET /api/stats/trends`
- `GET /api/stats/top-diseases`
- `GET /api/stats/heatmap`
- `GET /api/stats/interest-trends`
- `GET /api/stats/stacked-trends`
- `GET /api/stats/zscore`
- `GET /api/stats/keyword-timeseries`
- `GET /api/stats/keyword-zscore`
- `GET /api/stats/forecast`

### Alerts

- `GET /api/alerts`
- `POST /api/alerts`
- `PUT /api/alerts/{alert_id}`
- `DELETE /api/alerts/{alert_id}`
- `GET /api/alerts/{alert_id}/feed`

### Reports

- `POST /api/report/generate`
- `POST /api/report/export-excel`
- `POST /api/report/send-email`

### Admin Users

- `GET /api/admin/users`
- `POST /api/admin/users`
- `PUT /api/admin/users/{user_id}`
- `PUT /api/admin/users/{user_id}/status`
- `DELETE /api/admin/users/{user_id}`

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

### 7.4. Tài nguyên và vận hành

Các bảng vận hành chính:

- `Keyword`
- `RssSource`
- `SchedulerConfig`
- `User`
- `UserAlert`
- `UserBookmark`

## 8. Quyết định kỹ thuật quan trọng

### 8.1. Vì sao vẫn giữ article riêng, nhưng thống kê theo event

Nếu nhiều báo cùng đưa tin:

- mỗi article vẫn có giá trị nguồn riêng
- thông tin case/location có thể cập nhật khác nhau
- nhưng thống kê vận hành nên nhìn theo event để giảm nhiễu

### 8.2. Vì sao trusted source dựa trên `rss_sources`

Trusted domain hiện được suy ra từ danh sách RSS source đang active.

Ưu điểm:

- admin quản lý nguồn ngay trên UI
- crawler không còn phụ thuộc constant hardcode
- thay đổi nguồn không cần sửa code

Giới hạn:

- hiện mới bao phủ tốt cho mô hình RSS
- chưa phải source registry tổng quát cho nhiều adapter

### 8.3. Vì sao LLM re-check vẫn là tùy chọn

Project đang cần giữ scan ổn định trong môi trường dev/demo:

- regex/context filter xử lý phần lớn false positive
- LLM chỉ là lớp tăng độ chính xác
- có thể tắt hoàn toàn khi không có key/model hoặc khi cần chạy rẻ/nhanh

### 8.4. Trạng thái migration

Project hiện đã có `alembic` trong `backend/alembic`.

Thực tế triển khai hiện nay:

- dùng migration để cập nhật schema
- startup sẽ seed default keywords và RSS sources nếu chưa có dữ liệu

## 9. Tính năng UI đã làm

### 9.1. Giao diện người dùng

Trong app chính, hiện đã có:

- dashboard tổng quan với biểu đồ và bản đồ
- danh sách bài viết đã lưu
- search/filter/sort/pagination cho article
- xem danh sách event và article trong từng event
- bookmark bài viết
- alert cá nhân
- phân tích z-score / forecast / keyword diversity
- tab báo cáo tự động
- cấu hình email cá nhân và lịch nhận báo cáo

### 9.2. Giao diện quản trị

Trong admin panel, hiện đã có:

- quản lý tài khoản
- thêm/sửa/xóa/bật/tắt keyword
- thêm/xóa/bật/tắt RSS source
- xem và xóa article
- bật/tắt auto scan
- đổi chu kỳ scheduler
- chạy manual scan theo khoảng ngày
- cấu hình Mailtrap cho báo cáo

## 10. Cách chạy local

### 10.1. Yêu cầu

- Python 3.12+
- Node.js 18+
- Docker + Docker Compose

### 10.2. Biến môi trường

Project đọc `.env` ở root repo.

Ví dụ tối thiểu:

```env
DB_SERVER=localhost
DB_PORT=3306
DB_NAME=EpiScoutDB
DB_USER=epi_scout
DB_PASSWORD=epi_scout_dev_pw
SECRET_KEY=change-me-in-production
SCHEDULER_WAKE_SECRET=change-me-in-production
```

Có thể dùng `DATABASE_URL` thay cho bộ biến DB rời.

### 10.3. Chạy hạ tầng local

```bash
docker compose up -d
docker compose ps
```

Services mặc định:

- MySQL: `localhost:3306`
- Qdrant: `localhost:6333`

### 10.4. Cài backend

```bash
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 10.5. Chạy migration

```bash
cd backend
alembic upgrade head
cd ..
```

### 10.6. Chạy backend

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend mặc định:

- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/docs`

### 10.7. Chạy frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend mặc định:

- `http://localhost:8080`

Trong dev mode, request `/api` được proxy về backend.

## 11. Các cấu hình đáng chú ý

### 11.1. Database

- hỗ trợ `DATABASE_URL`
- nếu không có, backend tự build kết nối MySQL từ `DB_SERVER`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`

### 11.2. Auth

- `SECRET_KEY`
- JWT expiry mặc định 7 ngày

### 11.3. Scheduler wake-up

- Set `SCHEDULER_WAKE_SECRET` on the Hugging Face Space.
- Add GitHub repository secret `SCHEDULER_WAKE_SECRET` with the same value.
- Add GitHub repository secret `BACKEND_WAKE_URL`, for example `https://your-space.hf.space`.
- `.github/workflows/wake-backend.yml` calls `/api/scheduler/wake` every 30 minutes so the Space wakes periodically and overdue scans are queued.

### 11.4. LLM Re-check

- `LLM_RECHECK_ENABLED`
- `LLM_RECHECK_MODEL`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `LLM_RECHECK_TIMEOUT_SECONDS`
- `LLM_RECHECK_RATE_LIMIT_COOLDOWN_SECONDS`
- `LLM_RECHECK_TIMEOUT_COOLDOWN_SECONDS`

### 11.4. Email report

Cấu hình Mailtrap hiện lưu trong DB qua admin UI, không nằm trong `.env` mặc định.

## 12. Tài liệu liên quan

- thiết kế mở rộng nguồn crawl: [`docs/feature-crawl-data-expansion.md`](docs/feature-crawl-data-expansion.md)

## 13. Lệnh hay dùng

Chạy hạ tầng:

```bash
docker compose up -d
```

Chạy migration:

```bash
cd backend
alembic upgrade head
```

Chạy backend:

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
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
python backend/scripts/debug_rss.py
```
