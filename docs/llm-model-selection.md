# Lựa chọn mô hình cho EpiScout AI

## Cấu hình đang sử dụng từ 09/11/2026

Đã cập nhật checkout `D:\do-an\epi-scout-ai-main` từ `origin/main`, commit
`758f94f`, rồi chuyển các thiết lập LLM trong `.env` sang API Ollama nội bộ.
Giữ nguyên database/JWT/SMTP, keyword, quy tắc lọc, schema và bước kiểm tra
bằng chứng. `.env` cũ đã được sao lưu trong
`D:\do-an\.local-tools\workspace-backups`.

Model `episcout-local` là alias của `qwen3.5:4b-q4_K_M` đã có trên máy,
context 65.536 token, tối đa 4.096 token đầu ra, bốn luồng CPU. Profile
có thể sao chép từ [`.env.local.example`](../.env.local.example):

```dotenv
LLM_RECHECK_ENABLED=true
LLM_RECHECK_MODEL=episcout-local
LLM_SUMMARY_MODEL=episcout-local
LLM_FALLBACK_MODEL=
OPENAI_BASE_URL=http://127.0.0.1:11434/v1
OPENAI_API_KEY=ollama
LLM_REASONING_EFFORT=none
LLM_MAX_INPUT_BYTES=57344
LLM_RECHECK_TIMEOUT_SECONDS=600
LLM_SUMMARY_TIMEOUT_SECONDS=600
LLM_MAX_RETRIES=1
```

`ollama` chỉ là placeholder cho giao thức tương thích OpenAI. Bóc tách,
chạy lại đánh giá và tóm tắt đều dùng cấu hình local; không có model fallback
cloud. Không phát sinh phí API hay phụ thuộc quota miễn phí của bên thứ ba.
Windows và model vẫn dùng CPU, RAM và điện; website tin tức vẫn có thể giới
hạn lượt tải. Model không tự thu thập tin: pipeline RSS/đọc thân bài hiện có
tiếp tục đảm nhiệm phần này.

Khởi chạy từ PowerShell:

```powershell
Set-Location 'D:\do-an\epi-scout-ai-main'
.\start-local-model.ps1
.\start-backend.ps1
```

Script backend tự khởi động Ollama khi `.env` dùng endpoint local; script
Ollama kiểm tra alias `episcout-local` và tạo từ `Modelfile.local` nếu chưa
có. Runtime portable vẫn ở `D:\do-an\.local-tools\ollama`.

Bản 4B được ưu tiên thay cho 2B vì kiểm định trước đây phát hiện lỗi bóc tách
ở bản 2B. Bản 4B cũng có thể nhầm; kiểm tra bằng chứng và thẩm định của con
người vẫn bắt buộc theo quy trình hiện có. Máy 8 GB RAM xử lý từng bài và có
thể cần vài phút/bài. Không diễn giải kết quả thử nhỏ thành độ chính xác trên
toàn bộ nguồn tin. Nội dung vượt ngân sách byte bị từ chối, không âm thầm cắt
rồi coi là đã đọc đủ bài.

Kiểm thử hồi quy sau tích hợp: **104 passed**. Các mock cũ của ba tệp test
được cập nhật theo hợp đồng trả về `(parsed, requested_model, actual_model)`
đã có trên `main`; không thay đổi điều kiện kiểm tra hoặc tiêu chí nghiệp vụ.

Kiểm định model thật sau tích hợp dùng hai bài giả lập có sẵn, ví dụ built-in
của dự án và bước kiểm tra bằng chứng thật. Tắt ví dụ bổ sung từ workbook
trong lần đo này để tránh trộn dữ liệu tham khảo với dữ liệu kiểm định;
cấu hình chạy ứng dụng vẫn giữ nguyên lựa chọn few-shot hiện có.
Không ghi dữ liệu kiểm định vào bảng bài báo/sự kiện.

| Bài giả lập | Kết quả | Thời gian |
| --- | --- | --- |
| CDC Thanh Hóa ghi nhận sốt xuất huyết | `relevant`; giữ riêng 8 ca mới, 120 ca lũy kế, 2 ca nghi nhiễm trong `diseases`; có observation và câu nguồn | 305,6 giây |
| Bài viêm mao mạch dị ứng, phủ định thủy đậu/tay chân miệng | Bị loại đúng; model trả `noise` thay vì nhãn chuẩn `irrelevant`, không giữ số ca/bệnh | 162,3 giây |

Đúng quyết định giữ/loại: **2/2**, đúng nhãn chính xác: **1/2**. Đây chỉ là
hai mẫu kiểm tra kết nối và hành vi, không phải ước lượng chất lượng trên
nguồn tin thực tế. Kết quả chi tiết nằm trong
`scratch/local-integration-20261109.jsonl`. Model vẫn bỏ trống ngày sự kiện
ở bài đầu; không tự bổ sung ngày chưa bóc tách được. Không thể coi bản 4B là
bộ bóc tách đã đạt độ chính xác production chỉ dựa trên lần kiểm tra này.

API model được kiểm tra theo URL cấu hình và trả HTTP 200. Lần kiểm tra ban
đầu database báo `OperationalError`. Kiểm tra lại ngày 09/11/2026 sau khi
MySQL Docker sẵn sàng: `SELECT 1` thành công, dùng cấu hình database local
`EpiScoutDB_latest_20261103` hiện có, không thay mật khẩu hay nhập lại dữ liệu.
Backend main chạy tại `127.0.0.1:8001`, frontend main tại `127.0.0.1:8081`.
Health check, trang frontend và API đọc bài qua proxy frontend đều trả HTTP
200; đọc được 225 bài công khai và 76 keyword đang bật tại thời điểm kiểm tra.
Startup xác nhận preflight `episcout-local` OK. Chưa kích hoạt lượt quét mới
để kiểm thử ghi dữ liệu. Theo yêu cầu người dùng, đã dừng backend/frontend
bản cũ tại 8000/8080 cùng lượt quét đang chạy; hai cổng này không còn dịch vụ
lắng nghe. Bản cũ dùng database `EpiScoutDB` khác với bản main; không xóa hay
nhập lại dữ liệu của database đó. Bản main tại 8001/8081 đã kiểm tra lại health
và API đọc bài thành công sau chuyển đổi.

## Hồ sơ kiểm định trước lần tích hợp này

Ngày kiểm tra: 03/11/2026. Người dùng chọn chạy local miễn phí trên máy hiện tại.
Đã cài Ollama CPU portable tại `D:\do-an\.local-tools\ollama`, chỉ nghe trên
`127.0.0.1:11434`. Đã kiểm định bản 2B và đang thử tiếp bản 4B; chưa chuyển
cấu hình backend sang local. Không kích hoạt dịch vụ trả phí.

## Kết luận

Muốn không chịu quota lượt gọi của một API bên ngoài thì tự triển khai mô hình
open-weight trên máy của mình hoặc máy chủ riêng. Vẫn có giới hạn RAM/VRAM,
tốc độ sinh token, số tác vụ đồng thời và độ dài ngữ cảnh; không có mô hình nào
bảo đảm bóc tách đúng tuyệt đối. Dịch vụ API trả phí cũng không đồng nghĩa vô hạn.
Quota của API và khả năng đọc trang báo là hai giới hạn khác nhau: website nguồn
vẫn có thể chặn truy cập, đổi HTML hoặc không cung cấp toàn bộ nội dung.

## Ứng viên đã xác minh từ nguồn chính thức

| Phương án | Nơi chạy | Đánh giá cho dự án |
| --- | --- | --- |
| Qwen3.8-27B qua Ollama | Máy chủ riêng đủ bộ nhớ | Ứng viên ưu tiên để kiểm định nếu cần tự chủ quota. Bản Ollama hiện khoảng 18 GB trọng số; bộ nhớ chạy cần thêm cho context và runtime. Chưa benchmark trên dữ liệu dự án, chưa thể kết luận tốt hơn mô hình hiện tại. |
| Qwen3.5-2B Q4_K_M qua Ollama | Máy hiện tại, đang kiểm định | Tag cụ thể `qwen3.5:2b-q4_K_M`: khoảng 1.85 GiB gồm trọng số và projector. Dung lượng tải không phải RAM chạy. Model nhỏ có nguy cơ sai ngữ nghĩa và số liệu; phải kiểm định trước khi dùng. |
| API online trả phí | Nhà cung cấp | Tránh nhiều hạn chế của tầng miễn phí, giảm nhu cầu phần cứng local; vẫn phải kiểm tra quota, khả dụng, giá và ngân sách. Chưa chọn hoặc kích hoạt dịch vụ. |

Phần cứng đã đọc từ Windows: Intel Core i5-1135G7, 4 nhân/8 luồng, khoảng
7.8 GB RAM, Intel Iris Xe; không phát hiện GPU rời. Chạy đồng thời Windows,
MySQL, backend, trình duyệt và mô hình lớn sẽ thiếu bộ nhớ. Không khuyến nghị
cài bản 27B lên máy này. Với máy chủ riêng, nên lập kế hoạch từ 32 GB RAM trở
lên; nếu dùng GPU, lựa chọn VRAM phải dựa trên lượng tử hóa và context thực tế.
Đây là ước lượng triển khai, không phải yêu cầu tối thiểu được benchmark.

## Giữ cấu trúc và quy trình hiện có

Giữ nguyên các module và đường dẫn hiện có, gồm `crawler.py`, `stage1_context.py`,
`article_content.py`, bộ kiểm tra bằng chứng, thống kê và các model database.
Không thay pipeline bằng việc chỉ dò từ khóa hoặc tự duyệt mọi bài.

Giữ các nhãn `relevant`, `noise`, `irrelevant`, `unsure` và các trường JSON:
`normalized_title`, `matched_keywords`, `location`, `diseases`, `severity`,
`reason`, cùng `relevance_evidence` hiện có. Trong `diseases`, giữ riêng
`cumulative_cases`, `new_cases`, `suspected_cases`, `case_status`, ngày sự kiện
và `observations`. Không đổi ý nghĩa hoặc gộp số liệu khi thay model.

Luồng vẫn là RSS → lọc từ khóa/ngữ cảnh → đọc thân bài → LLM → kiểm tra bằng
chứng và trường dữ liệu → duyệt Cửa B nếu thuộc luồng này → công khai/thống kê.
Bài không đọc được, câu trích không khớp hoặc nhà cung cấp lỗi tiếp tục bị ẩn.

Ollama có giao diện `/v1/chat/completions`, `/v1/models/{model}` và JSON output,
phù hợp giao tiếp hiện có. JSON hợp lệ chỉ bảo đảm hình thức, không chứng minh
các số liệu hoặc kết luận y tế là đúng. Cần chạy thử endpoint thật trước khi đổi.

Ví dụ các giá trị LLM trong `.env` khi một máy phù hợp đã cài model này:

```dotenv
LLM_RECHECK_ENABLED=true
LLM_RECHECK_MODEL=qwen3.8:27b
LLM_FALLBACK_MODEL=
OPENAI_BASE_URL=http://127.0.0.1:11434/v1
OPENAI_API_KEY=ollama
LLM_RECHECK_TIMEOUT_SECONDS=180
```

Đây chỉ là các giá trị cần ghép vào file cấu hình hiện có, không thay thế toàn bộ
`.env` hoặc các thiết lập database/JWT. `ollama` là giá trị giả dùng cho server
local, không phải khóa cloud. Nếu chạy trên máy chủ khác, dùng địa chỉ máy chủ
và cơ chế bảo vệ truy cập tương ứng. Model/tag phải được tải trước.

Ollama dùng context của model triển khai; không được cho rằng context mặc định
đủ chứa mọi bài dài và toàn bộ prompt. Nếu cần, tạo model với `num_ctx` phù hợp
bộ nhớ theo tài liệu Ollama, đo độ dài đầu vào, không cắt nội dung rồi coi đã đọc hết.

## Kiểm định trước khi chuyển

### Cấu hình local cho máy hiện tại

Runtime portable dùng kho model `D:\do-an\.local-tools\ollama\models`.
`start-local-model.ps1` khởi động dịch vụ ẩn, giới hạn một model và một yêu cầu
đồng thời. `start-backend.ps1` tự gọi script này nếu `.env` trỏ tới Ollama local.
Không cần kích hoạt venv thủ công khi dùng script khởi động backend.

Sau khi tải xong tag chính thức, tạo alias bằng:

```powershell
& D:\do-an\.local-tools\ollama\ollama.exe create episcout-local -f .\Modelfile.local
```

`Modelfile.local` giữ context 65536, bốn luồng CPU, nhiệt độ 0, tối đa 4096
token đầu ra. Cấu hình backend local dự kiến dùng `LLM_REASONING_EFFORT=none`,
`LLM_MAX_INPUT_BYTES=57344`, timeout 600 giây và không có fallback cloud.
Ngân sách byte tính cả system prompt và user prompt; nội dung vượt ngưỡng
phải chờ thẩm định, không được âm thầm cắt bài. Khả năng nạp context này còn
phụ thuộc RAM trống thực tế; sẽ ghi kết quả kiểm định sau khi chạy.

Kiểm thử hồi quy backend: **86 passed**. Kiểm định mô hình thật dùng
`scratch/test_local_model.py`, chỉ đọc năm thân bài báo đã lưu và ghi kết quả
vào `scratch/local-model-test-results.jsonl`, không ghi bảng bài báo/sự kiện.

Kết quả 2B với thinking tắt: 3/5 nhãn đúng (bao gồm một bài tư vấn bị loại
bởi rule trước LLM). Bài não mô cầu bị đưa sang `unsure` do tên bệnh ngoài
keyword; JSON thô còn nhầm số tử vong thành số ca và tự thêm năm không có
trong bài. Bài viêm mao mạch dị ứng bị nhận sai là bệnh dịch, nhưng bộ kiểm
tra keyword đã chặn công khai. Thời gian gọi LLM khoảng 22–93 giây/bài.
Thinking bật trên bài não mô cầu mất 371 giây và hết ngân sách 4096 token,
không có JSON hợp lệ. **Không chọn bản 2B làm cấu hình production.**

### Tiêu chí

1. Chạy cùng bộ bài cố định với cấu hình hiện tại và ứng viên, không ghi kết quả
   thử nghiệm vào dữ liệu công khai. Tách bộ dùng chọn model khỏi bộ đánh giá cuối.
2. Bao phủ hỏi đáp cá nhân, tin thương mại, nghĩa bóng của “sốt/lao”, bệnh không
   truyền nhiễm, báo cáo một ca thực tế, chùm ca, cảnh báo chính thức, nhiều bệnh,
   số ca nghi nhiễm và số ca lũy kế.
3. Đo độ đúng nhãn, số ca, loại ca, bệnh, địa điểm, thời gian, độ khớp câu bằng
   chứng; ghi riêng lỗi JSON, thiếu trường, timeout và tốc độ xử lý.
4. Kiểm tra bài dài, ngữ cảnh phủ định, số tuổi/giá tiền và trường hợp chỉ dẫn
   nằm trong nội dung bài. Không tự hiểu số tuổi là số ca hoặc ví dụ là ca thực tế.
5. Chỉ chuyển cấu hình sau khi có kết quả đo đáp ứng nhu cầu. Giữ cấu hình cũ
   để khôi phục và kiểm tra cổng 8080 sau chuyển đổi.

## Nguồn chính thức

- Qwen model card: https://huggingface.co/Qwen/Qwen3.8-27B
- Ollama Qwen3.8: https://ollama.com/library/qwen3.8
- Ollama Qwen3.5: https://ollama.com/library/qwen3.5
- Giao tiếp API và context: https://docs.ollama.com/api/openai-compatibility
- Structured outputs: https://docs.ollama.com/capabilities/structured-outputs
- Quota OpenRouter: https://openrouter.ai/docs/api_reference/limits
- Tầng dịch vụ OpenRouter: https://openrouter.ai/pricing
