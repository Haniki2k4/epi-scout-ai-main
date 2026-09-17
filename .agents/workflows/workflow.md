---
description: 
---

Bạn là kỹ sư phụ trách Epi Scout AI. Hãy đọc AGENTS.md, README.md, báo cáo đồ án và mã nguồn hiện tại trước khi sửa. Mục tiêu là xây dựng workflow giám sát tín hiệu bệnh truyền nhiễm từ nguồn tin mở, có bước xác minh của con người. Scout chỉ hỗ trợ sàng lọc và ưu tiên xử lý; không tự xác nhận ổ dịch hoặc phát cảnh báo dịch chính thức.

Nguyên tắc làm việc
- Kiểm tra lại mọi đường dẫn, schema và hành vi trong code; số dòng trong plan cũ có thể đã thay đổi.
- Sửa đúng phạm vi. Tái sử dụng cấu trúc hiện có, tránh thêm dịch vụ hoặc dependency khi chưa cần.
- Bảo toàn dữ liệu lịch sử. Không TRUNCATE, xóa hàng loạt hoặc tự động ghi đè số ca cũ.
- Với thay đổi schema/API dùng chung, trình bày hợp đồng mới và tác động tương thích trước khi thực hiện.
- Mỗi giai đoạn phải có kiểm thử, tiêu chí nghiệm thu và bản tóm tắt thay đổi. Không chuyển giai đoạn khi lỗi dữ liệu của giai đoạn trước chưa được giải quyết.
- Phân biệt rõ dữ liệu từ báo chí, dữ liệu đã xác minh và dữ liệu giám sát chính thức.

WORKFLOW NGHIỆP VỤ ĐÍCH

1. Thu thập
   - Đọc nguồn đang bật; lưu URL gốc, nguồn, thời điểm đăng, thời điểm thu, kết quả lấy nội dung.
   - Kiểm tra URL trùng trước khi tải nội dung bổ sung hoặc gọi LLM.
   - Theo dõi số entry, lỗi và độ mới theo từng nguồn.

2. Sàng lọc bài
   - Stage 1 lọc keyword và ngữ cảnh, có lý do giữ/loại.
   - Stage 2 dùng LLM khi được bật để phân loại relevant, noise, irrelevant, unsure.
   - unsure không bị coi là relevant hoặc bị bỏ mất; đưa vào hàng đợi xem xét.
   - Lưu mẫu bài bị Stage 1 loại để đánh giá recall của toàn pipeline về sau.

3. Trích xuất
   - Với mỗi thông tin bệnh, địa điểm, ngày, số ca: lưu giá trị, loại giá trị, bài nguồn và đoạn văn làm bằng chứng khi có thể.
   - Tách ca xác nhận, ca nghi nhiễm, ca mới và ca lũy kế.
   - Xác định rõ số nghi nhiễm có bao gồm ca đã xác nhận hay không. Nếu nguồn không nói rõ, đánh dấu chưa rõ; không tự cộng hai số.
   - Tách ngày đăng bài khỏi ngày/kỳ xảy ra sự kiện.
   - Nếu bài chỉ nêu tổng cho nhiều ngày hoặc nhiều địa điểm, lưu tổng và phạm vi gốc. Không tự chia đều thành số ca theo ngày hoặc địa phương.

4. Gom bài thành event ứng viên
   - Tìm bài cùng bệnh, địa bàn và thời gian rồi so độ tương đồng.
   - Chỉ tạo event ứng viên, chưa gắn nghĩa “sự kiện đã xác minh”.
   - Lưu điểm và lý do ghép. Cho người có quyền gộp hoặc tách event, có nhật ký.
   - Hiệu chỉnh ngưỡng ghép trên bộ dữ liệu cặp bài có nhãn; không mặc định 0.75 là tối ưu.

5. Xác minh
   - Có hàng đợi event ứng viên và bài unsure.
   - Trạng thái tối thiểu: pending_review, under_verification, monitoring, verified_event, rejected. Định nghĩa chuyển trạng thái hợp lệ.
   - Mỗi quyết định lưu người xử lý, thời điểm, lý do, nguồn đối chiếu và lịch sử thay đổi.
   - Tách quyền quản trị kỹ thuật khỏi quyền xác minh nghiệp vụ. Không mặc định mọi admin đều là chuyên viên y tế.
   - “verified_event” chỉ có nghĩa dấu hiệu đã được xác minh là sự kiện liên quan; không tự đồng nghĩa với “đã công bố có dịch”.

6. Đánh giá và thông báo
   - Điểm liên quan bài báo chỉ dùng ưu tiên đọc.
   - Điểm ghép event chỉ dùng quyết định gom bài.
   - Mức nguy cơ dịch tễ là đánh giá khác, cần dữ liệu và người chịu trách nhiệm.
   - Thông báo từ Scout phải ghi “tín hiệu từ nguồn mở/chờ xác minh” hoặc trạng thái tương ứng.
   - Không áp dụng ngưỡng cảnh báo dịch theo Thông tư 15/2026/TT-BYT bằng số lượt nhắc báo chí. Nếu thiếu dữ liệu ca xác nhận và đường cơ sở theo địa bàn, hiển thị “chưa đủ dữ liệu để đánh giá theo tiêu chí này”.

7. Báo cáo và phản hồi
   - Tách báo cáo tín hiệu chờ xác minh và báo cáo event đã xác minh.
   - Hiển thị rõ nguồn, trạng thái, ngày đăng, kỳ sự kiện và loại số ca.
   - Quyết định của người xác minh được đưa vào dữ liệu đánh giá cho các phiên bản sau.

TIÊU CHÍ HOÀN THÀNH
- Không còn đường ghi ca nghi vào số ca xác nhận.
- Không còn số ca được phân bổ theo ngày/địa phương khi nguồn không nêu phân bố.
- Scan tiếp tục xử lý bài khác khi một bài lỗi; dữ liệu bài lỗi không ở trạng thái lưu dở.
- Mọi event mới có trạng thái chưa xác minh; chỉ người có quyền nghiệp vụ xác minh được.
- Dashboard và report ghi đúng đơn vị đo, nguồn và trạng thái xác minh.
- Dữ liệu cũ còn nguyên, có cách phân biệt với dữ liệu theo schema mới.
- Có kiểm thử cho các tình huống trên và báo cáo kết quả chạy.
- Báo cáo cuối cùng nêu: đã sửa gì, file/migration/API nào thay đổi, kiểm thử nào chạy, rủi ro còn lại và mục nào chưa làm.
