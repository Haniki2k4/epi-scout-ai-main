# Lọc lại lần hai theo tiêu chí hiện hành — 09/11/2026

Đã kiểm tra lại **145 bài đang được AI cho qua**: giữ **138**, chuyển **3** sang `noise`, **4** sang `unsure`. 209 bài có nhãn duyệt con người giữ nguyên lịch sử. Tổng bài công khai sau lọc: **347**, trong đó **125** bài có ngày đăng từ 01/06/2026.

## Tiêu chí được phép qua

Áp dụng đúng `RELEVANCE_CRITERIA` trong `backend/app/modules/news/llm_prompt_rules.py`, không sửa ngưỡng trong mã nguồn. Một bài cần có bằng chứng trong thân bài cho ít nhất một loại sau:

1. Ca/chùm ca mới được báo cáo; có thể là nghi nhiễm nếu nguồn ghi rõ đang theo dõi.
2. Ổ dịch hoặc đợt bùng phát đang diễn ra.
3. Thống kê hoặc diễn biến dịch tễ cụ thể có phạm vi, thời gian hay nguồn báo cáo nhận diện được.
4. Công văn khẩn chính thức về bệnh truyền nhiễm xác định, yêu cầu hành động đáp ứng cụ thể như giám sát, báo cáo, kiểm soát lây hoặc chuẩn bị điều trị.

Nguồn uy tín, tên bệnh và lời khuyên sức khỏe không tự tạo điều kiện được duyệt. Dự thảo, quy định thường quy, gánh nặng bệnh chung và giới thiệu vaccine không tự đáp ứng mục 4. Nếu chưa rõ sự kiện hiện tại hoặc kỳ số liệu thì giữ `unsure`.

Phải đọc toàn bộ thân bài: một bài tư vấn vẫn có thể đạt nếu chứa ca mới hoặc số liệu giám sát độc lập đủ bằng chứng. Hộp nội dung do tác giả chèn trong bài không mặc nhiên là tin liên quan; tuy vậy, ca minh họa trong hộp vẫn cần mốc sự kiện hoặc thông tin cho biết đó là ca mới.

Ngoại lệ thông báo khẩn: nếu công văn đồng thời nêu ca mới tại địa bàn được cảnh báo, phân loại theo ca/ổ dịch thay vì gắn thành thông báo khẩn chưa có ca. Ca nghi, ca xác nhận, người phơi nhiễm và tử vong nghi liên quan luôn giữ riêng.

## Các quyết định thay đổi

| Bài | Nhãn mới | Lý do |
|---|---|---|
| [#1482 — Hoàn thiện quy định về giám sát dịch tễ học HIV/AIDS phù hợp mô hình chính quyền địa phương 2 cấp](https://nhandan.vn/hoan-thien-quy-dinh-ve-giam-sat-dich-te-hoc-hivaids-phu-hop-mo-hinh-chinh-quyen-dia-phuong-2-cap-post999928.html) | noise | Dự thảo phân công giám sát HIV, không nêu ca mới, ổ dịch hoặc thống kê diễn biến cụ thể; không phải công văn khẩn. Thay đổi chính sách thường quy không đạt mục 4. |
| [#1433 — 12 tuần điều trị, rào cản 15 triệu đồng và bài toán khó cho quỹ BHYT](https://vietnamnet.vn/12-tuan-dieu-tri-rao-can-15-trieu-dong-va-bai-toan-kho-cho-quy-bhyt-2562301.html) | unsure | Có người được phát hiện viêm gan C nhưng không có mốc phát hiện; bài chính bàn chi trả BHYT và ước tính gánh nặng mạn. Chưa đủ xác định ca mới hay diễn biến dịch tễ hiện tại. |
| [#1330 — Khoảng trống miễn dịch khiến thanh thiếu niên dễ mắc não mô cầu](https://vnexpress.net/khoang-trong-mien-dich-khien-thanh-thieu-nien-de-mac-nao-mo-cau-5121533.html) | unsure | Số 53 ca đến 30/07 không ghi rõ năm; đoạn tiếp theo nói mẫu năm 2025 trong hội nghị năm 2026. Không tự coi số này là cập nhật năm 2026; cần báo cáo gốc xác định kỳ số liệu. |
| [#1271 — Đau mỏi người khi bị cảm, cúm: Ai dễ gặp triệu chứng nặng hơn?](https://suckhoedoisong.vn/dau-moi-nguoi-khi-bi-cam-cum-ai-de-gap-trieu-chung-nang-hon-169260914203722379.htm) | unsure | Có ca cúm A trong hộp minh họa cuối bài, nhưng không nêu ngày hoặc cho biết đây là ca mới được báo cáo. Chưa đủ chứng minh sự kiện hiện tại; cần nguồn ca gốc, không lấy ngày bài tư vấn làm ngày ca. |
| [#1274 — Trẻ bị sốt khi nào cần nhập viện?](https://suckhoedoisong.vn/tre-bi-sot-khi-nao-can-nhap-vien-169260910170058653.htm) | unsure | Có bệnh nhi Adenovirus trong hộp minh họa, nhưng không nêu mốc sự kiện hoặc xác nhận đây là ca mới. Giữ chờ nguồn ca gốc thay vì duyệt nhờ phần tư vấn nhập viện. |
| [#1292 — Căn bệnh khiến khoảng 2,2 triệu trẻ nhập viện hằng năm](https://tienphong.vn/can-benh-khien-khoang-22-trieu-tre-nhap-vien-hang-nam-post1870018.tpo) | noise | Bài dự phòng RSV dùng gánh nặng toàn cầu chung; thay đổi danh mục giám sát từ 01/07 là quy định thường quy, không phải công văn khẩn và không có số liệu giám sát hiện tại. |
| [#1320 — Gia tăng trẻ em mắc virus Adeno khi đi bơi, Bộ Y tế khuyến cáo](https://vietnamnet.vn/gia-tang-tre-em-mac-virus-adeno-khi-di-boi-bo-y-te-khuyen-cao-2537700.html) | noise | Thân bài chỉ giải thích Adenovirus và khuyến cáo vệ sinh cho người dân; không có ca mới/thống kê cụ thể hay công văn khẩn yêu cầu cơ sở y tế đáp ứng. Tiêu đề gia tăng không thay cho bằng chứng. |

## Những bài được giữ dù tiêu đề là tư vấn/quảng bá

- Bài #1392 và #1359: thân bài có số liệu HCDC về một tuần giữa tháng 10, với 34.664 ca viêm hô hấp cấp và tỷ lệ H1N1 trong mẫu cúm. Không quy toàn bộ thành ca cúm xác nhận.
- Bài #1273: hộp nội dung nêu Nhi Trung ương “vừa tiếp nhận” bệnh nhi 4 tuổi dương tính cúm A; có tín hiệu ca mới, khác các hộp minh họa không nêu thời điểm ở #1271 và #1274.
- Bài #1213: dùng ca 7 tuổi được Nhi đồng 2 báo cáo trong tháng 5 làm bằng chứng; không xem ca kể từ tháng 1/3 là ca mới tháng 6.
- Bài #1340: có chẩn đoán mới lao gan thể u bằng giải phẫu bệnh; giữ như báo cáo phát hiện bệnh, không suy thành nhiễm lao mới hoặc tự thêm số ca.
- Bài #1445, #1446, #1534: giữ theo dõi ca viêm phổi chưa rõ nguyên nhân; không xác nhận dịch hạch và không tính cập nhật theo dõi là một ca mới khác.

## Kiểm tra sau áp dụng

- Backend 8001 và proxy giao diện 8081 đều hiển thị đủ 138 bài được giữ và 209 bài đã có nhãn con người; 7 bài bị loại/chờ không xuất hiện công khai.
- Các nhóm hết bài hợp lệ không còn trong danh sách sự kiện công khai. Nhóm dự thảo HIV được đánh dấu không đạt tiêu chí; nhóm chờ thêm bằng chứng giữ chờ rà soát.
- Bộ lọc bệnh không làm lọt lại 7 bài đã xử lý. Nhóm trợ lý tạo trong đợt trước còn 24 nhóm có bài hợp lệ.
- Không xóa hàng, không thay nhãn con người, không thay số ca cũ, không thay nhật ký xác minh hoặc tự xác minh sự kiện.
- Các bài đã bị loại trước đợt này giữ nguyên trạng thái; đợt này rà soát lại các bài đang được cho qua, không khẳng định đã đọc lại toàn bộ kho tin bị loại.

Sao lưu trước thay đổi: `D:\do-an\epi-scout-ai-main\backups\refilter-before-20261109T030915Z.json`. JSON cùng tên chứa quyết định, đoạn nguồn, mã băm nội dung và mục tiêu chí cho từng bài.
