# Epi Scout AI

Hệ thống giám sát tin tức dịch bệnh từ RSS, gồm:

- `frontend/`: React + Vite + shadcn/ui
- `backend/`: FastAPI + crawler + MySQL
- `docker-compose.yml`: dịch vụ database local

Project hiện đã hoàn thiện đầy đủ các tính năng của một hệ thống giám sát dịch tễ chuyên nghiệp:

- **Quản trị người dùng & Xác thực**: Hệ thống phân quyền RBAC (Admin/User), JWT Auth.
- **Quản lý linh hoạt**: Keyword, Whitelist và **RSS Sources** đều được quản lý động qua UI Admin.
- **Lọc đa tầng nâng cao**: Regex context + Local Embedding Similarity + LLM re-check (GPT-4o/Qwen).
- **Phân tích & Dự báo**:
  - Phát hiện đột biến bằng thuật toán **Z-Score**.
  - Dự báo xu hướng bằng **Meta Prophet**.
  - Trực quan hóa qua Heatmap, WordCloud và Stacked Trend Charts.
- **Chống trùng bài (Deduplication)**: Heuristic chấm điểm similarity dựa trên title, location, case count và date.
- **Kiến trúc Crawler module**: Dễ dàng mở rộng nguồn crawl (RSS, Sitemap, Google News).

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

## 3. Kiến trúc hệ thống

### 3.1. Luồng hoạt động chính (Pipeline)

1. **Thu thập (Collect)**: Đọc danh sách Website/RSS từ Database -> Multi-threaded Crawler.
2. **Tiền xử lý (Pre-process)**: Strip HTML bẩn, chuẩn hóa Unicode, bóc tách Sapo.
3. **Lọc (Filter)**: 
   - Stage 1: Regex/Context scoring để lọc tin rác.
   - Stage 2: Similarity matching với dữ liệu 48h gần nhất để tránh trùng lặp Article.
   - Stage 3: LLM Re-check (nếu bật) để bóc tách số ca (`case_count`), địa điểm (`location`) và độ nghiêm trọng.
4. **Phân tích (Analytics)**:
   - Gom nhóm Article vào các **NewsEvent**.
   - Chạy mô hình Prophet để dự báo và Z-Score để cảnh báo bất thường.
5. **Phân phối (Distribution)**: API cho Frontend React hiển thị Dashboard và Admin Panel.

### 3.2. Chế độ phân quyền (RBAC)

- **Admin**: Quản lý toàn bộ hệ thống (User, RSS Sources, Keywords, Whitelist).
- **User (Operator)**: Chạy Scan, duyệt bài viết chưa xác thực, xem báo cáo phân tích.

## 4. Cấu trúc thư mục

```text
.
├── backend
│   ├── alembic/            # Database migrations
│   ├── app
│   │   ├── core/           # Security, Code base, Logger
│   │   ├── modules
│   │   │   ├── admin/      # Quản lý User, RSS Sources
│   │   │   ├── auth/       # JWT, Security logic
│   │   │   └── news/       # Crawler, Stats, Models, CRUD
│   │   └── main.py         # FastAPI routes & entry point
│   ├── requirements.txt
│   └── scripts/            # Debug tools
├── frontend
│   ├── src
│   │   ├── components/     # UI Components (shadcn/ui)
│   │   ├── contexts/       # AuthContext, ThemeContext
│   │   ├── pages/          # Dashboard, Analytics, Admin
│   │   └── services/       # API calling (Axios hooks)
├── docker-compose.yml
└── .env
```

## 5. Các thành phần quan trọng

### 5.1. `backend/app/modules/news/crawler.py`
Core logic của hệ thống:
- Sử dụng `SentenceTransformer` (MiniLM-L12-v2) để tính tương đồng văn bản.
- Tự động bóc tách Sapo từ các báo VN (VnExpress, Tuổi Trẻ, Thanh Niên...).
- Quản lý cooldown khi gọi LLM bị rate limit hoặc timeout.

### 5.2. `backend/app/modules/news/stats.py`
Nơi thực hiện các phân tích nâng cao:
- **Z-Score Spike Detection**: Tìm các ngày có số bài viết tăng đột biến so với trung bình 14 ngày trước đó.
- **Prophet Forecast**: Sử dụng thư viện Prophet của Meta để dự báo số ca mắc trong 7-30 ngày tới.
- **Heatmap Logic**: Tính toán mật độ dịch bệnh theo địa phương và thời gian.

### 5.3. `backend/app/modules/auth/security.py`
Xử lý bảo mật:
- Băm mật khẩu bằng `passlib` (bcrypt).
- Tạo và xác thực JWT token.
- Middleware kiểm tra quyền hạn (Admin/User).

## 6. API chính của hệ thống

### Xác thực & Người dùng
- `POST /api/auth/login`: Đăng nhập nhận token.
- `GET /api/admin/users`: (Admin) Danh sách tài khoản.

### Giám sát & Bài viết
- `POST /api/scan`: Chạy tiến trình crawl tin tức.
- `GET /api/articles`: Danh sách bài viết toàn hệ thống (phân trang).
- `GET /api/events`: Danh sách các sự kiện dịch tễ đã được gom nhóm.

### Phân tích (Analytics)
- `GET /api/stats/overview`: Chỉ số tổng hợp (Top bệnh, số ca, lượt cảnh báo).
- `GET /api/stats/zscore`: Dữ liệu phát hiện đột biến.
- `GET /api/stats/forecast`: Dữ liệu dự báo AI.
- `GET /api/stats/heatmap`: Mật độ địa bàn.

### Quản trị (Admin)
- `GET /api/rss-sources`: Quản lý danh sách nguồn tin.
- `POST /api/keywords`: Quản lý bộ từ khóa giám sát.
- `POST /api/whitelist`: Quản lý domain tin cậy.

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

## 9. Tính năng UI nổi bật

### 9.1. Tab Giám sát bài viết
- Chạy Scan đa tầng với tùy chọn **Quét nguồn chưa xác thực**.
- Quản lý bộ từ khóa động (Batch create/delete).
- Dashboard bài viết: lọc theo bệnh, nguồn, thời gian, trạng thái (Manual/Auto).
- Xem chi tiết **Sự kiện (Event)**: Biết được một sự kiện dịch bệnh được đưa tin bởi những báo nào, số lượng ca mắc cộng dồn thế nào.

### 9.2. Tab Phân tích nâng cao
- **Phát hiện đột biến**: Biểu đồ Z-Score trực quan, tự động đánh dấu các ngày có số bài tăng vọt (Danger/Alert).
- **Dự báo xu hướng**: Sử dụng AI dự báo ngưỡng lây lan trong tương lai.
- **Bản đồ địa bàn**: Heatmap hiển thị ổ dịch theo tỉnh thành.

### 9.3. Tab Quản trị hệ thống
- Quản trị người dùng: Tạo tài khoản, đổi mật khẩu, phân quyền.
- Quản trị nguồn tin: Bật/tắt các RSS feeds, thêm nguồn mới vào hệ thống mà không cần sửa code.
- Quản trị Whitelist: Định nghĩa các domain tin cậy để tự động lưu bài.

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

- Schema migration đang trong quá trình chuẩn hóa toàn bộ qua Alembic (vẫn còn một số bảng cũ chưa migrate hết).
- Dự báo AI yêu cầu lượng dữ liệu lịch sử tối thiểu 90 ngày để đạt độ chính xác cao.
- Crawler chưa hỗ trợ JavaScript Rendering (không crawl được bài viết ở các trang SPA).
- Hệ thống thông báo (Notification) chưa được triển khai qua Email/Zalo.

## 13. Hướng phát triển tiếp theo

1. **Crawler Support**: Thêm adapter cho Google News API và Sitemap.
2. **Notification Module**: Gửi cảnh báo ngay khi Z-Score phát hiện đột biến nguy hiểm.
3. **Multi-language Support**: Hỗ trợ giám sát các báo quốc tế (tiếng Anh).
4. **Export Report**: Xuất báo cáo dịch tễ định kỳ (PDF/Excel) tự động.
5. **Mobile View**: Tối ưu hóa UI Dashboard cho thiết bị di động.

## 14. Tài liệu liên quan

- thiết kế mở rộng nguồn crawl: [`docs/feature-crawl-data-expansion.md`](/home/suno/Github/epi-scout-ai-main/docs/feature-crawl-data-expansion.md)

## 15. Lệnh hay dùng

Chạy DB:

```bash
docker compose up -d
```

Chạy backend:

```bash
linux: backend/venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
windows: .\backend\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
venv: .\backend\venv\Scripts\Activate.ps1
      uvicorn backend.main:app --host 127.0.0.1 --port 8000
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
Linux: backend/venv/bin/python backend/scripts/debug_rss.py
Windows: backend\venv\Scripts\python.exe backend/scripts/debug_rss.py
```

Compile nhanh backend:

```bash
python3 -m py_compile backend/app/main.py backend/app/modules/news/models.py backend/app/modules/news/crud.py backend/app/modules/news/crawler.py backend/app/modules/news/schemas.py
```