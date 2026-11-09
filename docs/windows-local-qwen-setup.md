# Cài môi trường Windows và chạy Qwen local

Hướng dẫn cho nhánh `nann-bi`, cập nhật 04/11/2026. Chạy PowerShell tại thư mục gốc repository. Không cần activate venv: các lệnh gọi trực tiếp Python trong venv.

## 1. Công cụ cần cài

- Git: https://git-scm.com/downloads/win
- Python **3.12 x64**: https://www.python.org/downloads/ (bật Python Launcher).
- Node.js **22 LTS** và npm: https://nodejs.org/
- MySQL **8.x** cùng MySQL CLI hoặc Workbench: https://dev.mysql.com/downloads/installer/
- Ollama portable theo bước 5. Lần cài đầu cần Internet để tải thư viện và model.

Máy đã thử: i5-1135G7, khoảng 8 GB RAM, không GPU rời. Qwen 4B chạy chậm, có bài mất vài phút. Model khoảng 3.32 GB gồm trọng số và projector; cần thêm RAM cho context và các dịch vụ. Nên có ít nhất 15 GB đĩa trống, nhiều hơn nếu tải embedding `BAAI/bge-m3` và cache Python. RAM 16 GB trở lên thuận tiện hơn; 8 GB có thể phải dùng bộ nhớ ảo.

```powershell
git clone --branch nann-bi https://github.com/Haniki2k4/epi-scout-ai-main.git
Set-Location .\epi-scout-ai-main
py -3.12 --version
node --version
npm.cmd --version
py -3.12 -m venv backend\venv
.\backend\venv\Scripts\python.exe -m pip install --upgrade pip
.\backend\venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\backend\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Push-Location frontend
npm.cmd ci
Pop-Location
```

Nếu đã có repository, dùng `git switch nann-bi` rồi `git pull --ff-only` sau khi lưu các chỉnh sửa của bạn. Không clone đè hoặc reset bản đang làm.

## 2. Cấu hình backend

Chỉ khi chưa có `.env`, tạo từ mẫu:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.qwen.example .env }
.\backend\venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Mở `.env`, đặt `DB_SERVER`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` theo MySQL của máy, thay `SECRET_KEY` bằng chuỗi vừa tạo. Mẫu dùng database mới `EpiScoutDB`; nếu đã có dữ liệu, giữ tên DB và thông tin kết nối đang dùng. Không thay toàn bộ `.env` đang hoạt động. Không commit `.env` thật.

Mẫu Qwen dùng `episcout-local`, timeout 600 giây, không fallback cloud. `OPENAI_API_KEY=ollama` chỉ là giá trị giả cho API local. SMTP là tùy chọn cho gửi thư; muốn dùng cần cấu hình SMTP riêng.

## 3. Database

Khởi động MySQL. Với **cài mới**, tạo database rỗng trong MySQL CLI hoặc Workbench:

```sql
CREATE DATABASE EpiScoutDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Dùng tài khoản có quyền trên database này trong `.env`. Với database hoàn toàn rỗng, tạo schema hiện hành từ các model rồi đánh dấu phiên bản migration:

```powershell
.\backend\venv\Scripts\python.exe -c "from sqlalchemy import inspect; from backend.app.core.database import Base,engine; from backend.app.modules.news import models; from backend.app.modules.auth import models as auth_models; from backend.app.modules.evaluation import models as evaluation_models; assert not inspect(engine).get_table_names(), 'Database must be empty'; Base.metadata.create_all(engine)"
.\backend\venv\Scripts\python.exe -m alembic -c backend/alembic.ini stamp head
.\backend\venv\Scripts\python.exe -m backend.scripts.add_monitoring_keywords
.\backend\venv\Scripts\python.exe -m backend.scripts.add_monitoring_keywords --apply
```

Lệnh đầu từ chối DB đã có bảng. `stamp head` chỉ dùng sau khi vừa tạo schema mới thành công; nó không nâng cấp schema cũ. Migration gốc của dự án không tạo bảng, vì vậy DB rỗng cần bước `create_all` này trước. Script từ khóa cho xem trước, sau đó chỉ thêm mục thiếu, giữ nguyên mục cũ và lưu backup. Có thể thêm, sửa, bỏ từ khóa trên trang quản trị Tài nguyên sau khi đăng nhập.

Với **database đã có dữ liệu**, sao lưu trước rồi dùng lịch sử migration hiện có:

```powershell
.\backend\venv\Scripts\python.exe -m alembic -c backend/alembic.ini current
.\backend\venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
```

Nếu database có bảng nhưng chưa có lịch sử Alembic, cần đối chiếu schema trước khi gắn revision. Không chạy `reset_db.py`, không import SQL đè DB, không stamp tùy ý. Git không chứa dữ liệu bài báo hoặc tài khoản trên máy hiện tại. Cài mới cần đăng ký tài khoản qua giao diện; tài khoản quản trị của DB cũ không được chuyển qua Git.

## 4. Cấu hình frontend

```powershell
if (-not (Test-Path frontend\.env.local)) {
    Copy-Item frontend\.env.development.example frontend\.env.local
}
```

Nội dung cần có trong `frontend/.env.local`:

```dotenv
EPISCOUT_API_PROXY_TARGET=http://127.0.0.1:8001
VITE_API_BASE_URL=
```

Vite chuyển `/api` từ cổng 8080 sang backend 8001. `.env.production` dành cho triển khai riêng, không quyết định proxy development này.

## 5. Cài Ollama portable và Qwen 4B

Tải ZIP Windows chính thức từ https://github.com/ollama/ollama/releases (bản đã thử: **v0.40.13**). Giải nén **đầy đủ runtime**, giữ nguyên thư mục DLL đi kèm, vào `.local-tools/ollama` ở thư mục cha repository. Ví dụ repo `D:\do-an\epi-scout-ai-main` thì executable là `D:\do-an\.local-tools\ollama\ollama.exe`. Không chỉ chép mỗi executable.

Có thể tải/giải nén bằng PowerShell bên dưới khi runtime chưa tồn tại. ZIP Windows có thể lớn vì kèm thư viện GPU; có thể tải qua trình duyệt từ trang release và giải nén cùng vị trí.

```powershell
$runtimeRoot = Join-Path (Split-Path (Get-Location).Path -Parent) '.local-tools\ollama'
$runtimeZip = Join-Path $env:TEMP 'episcout-ollama-windows-amd64.zip'
if (Test-Path $runtimeRoot) { throw 'Runtime da ton tai; giu nguyen, khong giai nen de.' }
Invoke-WebRequest 'https://github.com/ollama/ollama/releases/download/v0.40.13/ollama-windows-amd64.zip' -OutFile $runtimeZip
Expand-Archive -LiteralPath $runtimeZip -DestinationPath $runtimeRoot
$runtimeSignature = Get-AuthenticodeSignature (Join-Path $runtimeRoot 'ollama.exe')
if ($runtimeSignature.Status -ne 'Valid') { throw 'Chu ky Ollama khong hop le; kiem tra lai file tai ve.' }
$runtimeSignature.SignerCertificate.Subject
.\start-local-model.ps1
& (Join-Path $runtimeRoot 'ollama.exe') pull qwen3.5:4b-q4_K_M
& (Join-Path $runtimeRoot 'ollama.exe') create episcout-local -f .\Modelfile.local
& (Join-Path $runtimeRoot 'ollama.exe') list
Invoke-RestMethod 'http://127.0.0.1:11434/v1/models/episcout-local'
```

Kiểm tra chữ ký executable hợp lệ của Ollama trước khi chạy. Script chỉ bind `127.0.0.1:11434`, tắt cloud, giới hạn một model và một yêu cầu đồng thời; log ở `scratch/ollama.*.log`. Nếu đã cài Ollama bằng installer, có thể dùng server đó và chạy `ollama pull ...`, `ollama create ...`; server đang chạy phải có alias trong chính kho model của nó. Script gặp API đang hoạt động sẽ dùng lại, không thay cấu hình server đó.

`Modelfile.local` dùng Qwen3.5 4B Q4_K_M, context 65536, 4 luồng CPU, nhiệt độ 0, tối đa 4096 token đầu ra. Byte budget trong backend không tương đương token budget. Bài vượt ngưỡng hoặc thiếu bằng chứng giữ trạng thái cần duyệt, không tự cắt bài và coi đã đọc đủ. Có thể giảm context khi thiếu RAM, nhưng phải kiểm định lại khả năng đọc bài dài.

## 6. Khởi động mỗi lần sử dụng

Mở hai PowerShell tại gốc repository:

```powershell
# Terminal 1: tự khởi động Ollama nếu .env dùng local
.\start-backend.ps1
```

```powershell
# Terminal 2
.\start-frontend.ps1
```

Nếu PowerShell chặn script, cho phép trong phiên hiện tại rồi chạy lại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

- Giao diện: http://127.0.0.1:8080
- Phân tích: http://127.0.0.1:8080/analytics
- API health qua proxy: http://127.0.0.1:8080/api/health
- Swagger backend: http://127.0.0.1:8001/docs
- Ollama: http://127.0.0.1:11434/api/version

Backend có scheduler; quét bài và tạo báo cáo có thể gọi model. Lần dùng embedding đầu sẽ tải thêm `BAAI/bge-m3` từ Hugging Face, độc lập với Qwen. Model không nằm trong Git. Tắt backend/frontend bằng Ctrl+C ở terminal tương ứng. Ollama portable chạy nền có PID được in lúc khởi động.

## 7. Kiểm tra và xử lý lỗi

```powershell
Invoke-RestMethod 'http://127.0.0.1:8080/api/health'
.\backend\venv\Scripts\python.exe -m pip install pytest
$env:PYTHONPATH = "$((Get-Location).Path);$((Get-Location).Path)\backend"
.\backend\venv\Scripts\python.exe -m pytest backend/tests -q --disable-warnings
Push-Location frontend
npx.cmd tsc --noEmit -p tsconfig.app.json
npm.cmd run build
Pop-Location
```

Kiểm tra code ngày 03/11/2026: **104 tests backend đạt**, TypeScript và Vite build đạt. Đây không phải đánh giá độ chính xác tuyệt đối của mô hình hay xác nhận cài mới trên mọi máy.

- Không thấy `Activate.ps1`: kiểm tra đang ở đúng repo và đã tạo `backend/venv`; script khởi động không yêu cầu activate.
- Lỗi MySQL: kiểm tra service, cổng, tên DB, mật khẩu và bảng; `DB_PORT` không được để trống.
- Model not found: kiểm tra `ollama list`, tạo alias `episcout-local` trong server đang dùng.
- Timeout/thiếu RAM: giữ một yêu cầu, đóng bớt ứng dụng; không tăng số yêu cầu song song. JSON hợp lệ vẫn có thể sai số liệu, cần kiểm tra bằng chứng nguồn.
- 8080 báo lỗi proxy: backend phải nghe 8001; kiểm tra `.env.local`, khởi động lại Vite sau khi sửa env.
- Báo cáo 24–72 giờ hoặc Prophet rỗng: có thể thiếu dữ liệu trong kỳ hoặc thiếu lịch sử hợp lệ; không tự điền số 0 hay dựng dự báo.

Xem thêm [lựa chọn và kiểm định model](llm-model-selection.md), [phân loại nguyên nhân bệnh](disease-cause-monitoring.md).
