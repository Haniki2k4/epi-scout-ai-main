# Lựa chọn mô hình cho EpiScout AI

Ngày kiểm tra: 03/11/2026. Người dùng chọn chạy local miễn phí trên máy hiện tại.
Đã cài Ollama CPU portable tại `D:\do-an\.local-tools\ollama`, chỉ nghe trên
`127.0.0.1:11434`. Đã kiểm định bản 2B và đang thử tiếp bản 4B; chưa chuyển
cấu hình backend sang local. Không kích hoạt dịch vụ trả phí.

## Cập nhật 04/11/2026

Hướng dẫn cài đặt có thể thực hiện trên máy khác nằm tại
[Windows + Qwen local](windows-local-qwen-setup.md), dùng `qwen3.5:4b-q4_K_M`
và alias `episcout-local`. Các đoạn bên dưới ghi lại khảo sát trước đó;
ví dụ 27B không phải cấu hình cho máy 8 GB RAM.

Bản 4B đã thử trên năm bài báo: 4/5 nhãn khớp nhãn kỳ vọng, 5/5 quyết định
công khai/loại bỏ khớp (một bài được rule loại trước LLM). Các lượt gọi model
mất khoảng 57–343 giây/bài. JSON thô vẫn có lỗi phân biệt ca mới/lũy kế,
tử vong và năm; backend kiểm tra câu nguồn, loại đại lượng, bệnh và ngày,
xóa số liệu không đủ bằng chứng. Kết quả này không bảo đảm mọi bài đều đúng.

Kiểm thử code gần nhất: **104 tests backend đạt**, TypeScript và Vite build đạt.
Tệp cấu hình mẫu local đã được đưa lên Git; `.env` chạy thực tế là cấu hình
riêng của từng máy. Việc push code không tự chuyển môi trường đang chạy
sang Qwen. Bộ thử nghiệm và kết quả trong `scratch/` là dữ liệu local,
không phải tệp có sẵn sau khi clone.

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
