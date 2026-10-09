# Cài đặt và kiến trúc kỹ thuật EpiScout AI

Tài liệu này dành cho người phát triển và vận hành. Giới thiệu sản phẩm và workflow nghiệp vụ nằm tại [README](../README.md).

## Công nghệ

| Phần | Công nghệ chính |
| --- | --- |
| Frontend | React 18, TypeScript, Vite 5, Tailwind CSS, shadcn/ui, TanStack Query |
| Biểu đồ và bản đồ | Recharts, MapLibre, deck.gl |
| Backend | FastAPI, Uvicorn, SQLAlchemy, PyMySQL, Alembic |
| Thu thập | feedparser, Requests, Beautiful Soup |
| Phân tích | LLM qua API tương thích OpenAI, Sentence Transformers, RapidFuzz, Prophet |
| Vận hành | APScheduler, Docker, GitHub Actions |
| Dữ liệu | MySQL 8.4; Qdrant có trong Docker Compose |
| Production | Vercel frontend, Hugging Face Spaces backend |

## Cấu trúc thư mục

```text
.
├── backend
│   ├── alembic/versions     # migration
│   ├── app
│   │   ├── core             # database, logging
│   │   ├── modules          # auth, admin, news, evaluation, report
│   │   ├── main.py
│   │   └── scheduler.py
│   ├── scripts
│   ├── tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend
│   ├── src/components
│   ├── src/contexts
│   ├── src/pages
│   └── package.json
├── docs
├── docker-compose.yml
└── .env.example
```

## Mô hình dữ liệu chính

| Nhóm | Thành phần | Vai trò |
| --- | --- | --- |
| Tin bài | `ArticleIdentity`, `ArticleDetails` | URL và nội dung/phân tích của bài báo |
| Sự kiện | `NewsEvent` | Gom nhiều bài về cùng sự kiện dịch tễ |
| Ca bệnh | `DiseaseCase` | Số liệu nguồn báo nêu và bằng chứng |
| Nguồn | `RssSource`, `Keyword` | Nguồn RSS và từ khóa hoạt động |
| Chất lượng | `RssEntrySample`, `CrawlRun`, `ScanRun` | Mẫu nhãn và số liệu mỗi lần quét |
| Cửa B | `ContextSignalReview` | Quyết định của nhân viên y tế |
| Người dùng | `User`, `UserAlert`, `UserBookmark` | Tài khoản và chức năng cá nhân |
| Vận hành | `SchedulerConfig` | Lịch crawler và trạng thái chạy |

Schema được cập nhật bằng Alembic. Backend không tự chạy migration khi khởi động.

## Nhóm API

Chi tiết tương tác có tại Swagger `/docs`. Các nhóm chính:

- `/api/auth`: xác thực và hồ sơ;
- `/api/articles`, `/api/events`, `/api/signals`: bài và sự kiện;
- `/api/keywords`, `/api/rss-sources`: nguồn thu thập;
- `/api/scan`, `/api/scan-status`, `/api/scheduler`: quét và lịch;
- `/api/context-signals`: hàng đợi Cửa B;
- `/api/quality`: mẫu và chỉ số chất lượng;
- `/api/stats`: dashboard và phân tích;
- `/api/alerts`, `/api/bookmarks`: chức năng cá nhân;
- `/api/report`: báo cáo;
- `/api/admin`: quản trị;
- `/api/health`: health check.

Endpoint quản trị và đánh giá yêu cầu JWT phù hợp với vai trò.

## Yêu cầu local

- Python tương thích với `backend/requirements.txt`
- Node.js 18 trở lên
- Docker và Docker Compose nếu chạy MySQL/Qdrant bằng container

Docker image production hiện dùng Python 3.11. Nếu local dùng Python 3.12 hoặc 3.13, phải tạo venv mới và cài dependency trong đúng interpreter; không sao chép venv giữa các phiên bản.

## Biến môi trường

Sao chép `.env.example` thành `.env` tại thư mục gốc. Không commit secret.

### Database

Dùng một URL:

```env
DATABASE_URL=mysql+pymysql://user:password@host:3306/EpiScoutDB
```

Hoặc các biến rời:

```env
DB_SERVER=localhost
DB_PORT=3306
DB_NAME=EpiScoutDB
DB_USER=epi_scout
DB_PASSWORD=change-me
```

### Xác thực và CORS

```env
SECRET_KEY=replace-with-a-long-random-secret
CORS_ORIGINS=http://localhost:8080
```

`SECRET_KEY` ký và kiểm tra JWT. Đổi khóa làm token cũ mất hiệu lực. Production cần khóa riêng, mạnh và ổn định.

`CORS_ORIGINS` là danh sách URL frontend, phân cách bằng dấu phẩy và gồm scheme, ví dụ `https://epi-scout-ai-main.vercel.app`.

### LLM và Gate B

```env
LLM_RECHECK_ENABLED=true
LLM_RECHECK_MODEL=google/gemma-4-31b-it:free
LLM_FALLBACK_MODEL=openai/gpt-oss-120b:free
OPENAI_API_KEY=
OPENAI_BASE_URL=
LLM_RECHECK_TIMEOUT_SECONDS=20

GATE_B_ENABLED=true
GATE_B_LLM_ENABLED=false
GATE_B_LLM_FEED_ALLOWLIST=
```

Allowlist rỗng không cấp phép feed nào. `*` cấp phép mọi feed và chỉ nên dùng sau khi đo chế độ shadow.

### Scheduler và frontend

```env
SCHEDULER_WAKE_SECRET=replace-with-another-random-secret
VITE_API_BASE_URL=https://your-space.hf.space
```

GitHub Actions cần repository secrets `SCHEDULER_WAKE_SECRET` và `BACKEND_WAKE_URL`. Frontend local có thể để trống `VITE_API_BASE_URL` để Vite proxy `/api`.

## Chạy local

### 1. Khởi động database

```powershell
docker compose up -d
docker compose ps
```

MySQL dùng cổng `3306`; Qdrant dùng `6333`.

### 2. Tạo môi trường backend

```powershell
py -3.13 -m venv backend\venv
.\backend\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
```

Có thể thay `-3.13` bằng phiên bản Python đang dùng, nhưng phải tạo venv cho đúng phiên bản đó.

### 3. Chạy migration

Sao lưu đúng database đích trước migration:

```powershell
Set-Location backend
.\venv\Scripts\python.exe -m alembic current
.\venv\Scripts\python.exe -m alembic upgrade head
Set-Location ..
```

Xem [Rollout Signal Evidence](signal-evidence-rollout.md) và [Rollout Gate B](gate-b-rollout.md).

### 4. Chạy backend

```powershell
.\backend\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend
```

- API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/api/health`

Dùng `--reload-dir backend` để thay đổi frontend không restart backend giữa lúc crawler đang chạy.

### 5. Chạy frontend

```powershell
Set-Location frontend
npm install
npm run dev
```

Frontend local mặc định ở `http://localhost:8080`.

## Kiểm tra và build

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend\tests

Set-Location frontend
npm run lint
npm run build
```

Một số test tích hợp cần database hoặc dependency native đúng với Python đang chạy.

## Triển khai

### Frontend trên Vercel

1. Chọn đúng thư mục frontend trong project Vercel.
2. Đặt `VITE_API_BASE_URL` thành URL Hugging Face backend.
3. Build bằng `npm run build`.
4. Thêm URL Vercel đầy đủ vào `CORS_ORIGINS` của backend.

### Backend trên Hugging Face Spaces

Backend dùng [Dockerfile](../backend/Dockerfile) và lắng nghe cổng từ `PORT`. Đặt cấu hình database, JWT, CORS, LLM và scheduler trong Secrets/Variables của Space.

Dockerfile chỉ khởi động Uvicorn. Migration production phải chạy riêng sau khi backup và kiểm tra revision.

### Database production

- Xác nhận chính xác database backend đang dùng.
- Tạo và kiểm tra backup trước migration.
- Chạy `alembic current` rồi `alembic upgrade head`.
- Không thử downgrade có thể mất dữ liệu trên production.

## Tài liệu liên quan

- [README sản phẩm](../README.md)
- [Thiết kế mở rộng nguồn crawl](feature-crawl-data-expansion.md)
