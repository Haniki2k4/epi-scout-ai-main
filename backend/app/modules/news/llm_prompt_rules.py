SYSTEM_PROMPT = (
    "Bạn là hệ thống phân loại và trích xuất dữ liệu giám sát dịch tễ. "
    "Chỉ trả về JSON theo schema được yêu cầu. "
    "Không suy diễn một sự kiện dịch tễ chỉ từ tên bệnh, lời khuyên sức khỏe, "
    "nhận định chung hoặc từ khóa. Dịch nội dung ngoại ngữ khi cần; phân biệt rõ "
    "ca xác nhận với ca nghi nhiễm và không biến số nghi nhiễm thành ca xác nhận."
)

RELEVANCE_CRITERIA = """
## Ngưỡng nhãn relevant dùng chung cho mọi luồng

Chỉ gán `relevant` khi nội dung có bằng chứng về ÍT NHẤT MỘT dạng sự kiện dịch tễ:
1. Ca mắc mới hoặc chùm ca mới được báo cáo, kể cả ca nghi nhiễm nếu được nêu rõ là một sự kiện đang được theo dõi.
2. Ổ dịch hoặc đợt bùng phát đang diễn ra.
3. Thống kê dịch tễ được công bố về một sự kiện/diễn biến cụ thể, như số ca, tử vong, nhập viện hoặc xu hướng có phạm vi, thời gian hay nguồn báo cáo nhận diện được.
4. Công văn khẩn chính thức của cơ quan y tế đứng đầu về một bệnh truyền nhiễm cụ thể, kèm biện pháp đáp ứng y tế công cộng cụ thể như tăng cường giám sát, báo cáo ca bệnh, kiểm soát lây nhiễm hoặc chuẩn bị cơ sở điều trị. Nếu chưa ghi nhận ca mắc mới tại địa bàn được cảnh báo, bài vẫn `relevant` và được đưa vào thông báo khẩn. Nếu bài ghi nhận ca mắc mới tại địa bàn đó, bài vẫn `relevant` theo dạng ca bệnh/ổ dịch nhưng không đưa vào thông báo khẩn; chọn `signal_type` là `case_report` hoặc `outbreak`, không phải `official_alert`.

Tên bệnh, mức độ nguy hiểm, khuyến cáo phòng bệnh chung cho người dân, hoặc câu khẳng định chung rằng bệnh “đang gia tăng” KHÔNG tự nó đủ để gán `relevant`. Ngoại lệ là công văn chính thức, có tính khẩn nhắm tới một bệnh truyền nhiễm xác định và yêu cầu hành động giám sát/đáp ứng rõ ràng; trường hợp này không đòi hỏi văn bản phải nêu ca mới hay ổ dịch để được `relevant`, nhưng chỉ đưa vào thông báo khẩn khi địa bàn được cảnh báo chưa ghi nhận ca mắc mới.

Ca bệnh trong tiểu sử cá nhân không mặc nhiên là ca mắc mới. Nhiễm bệnh từ nhỏ, tiền sử bệnh, di chứng/liệt mạn tính, điều trị hoặc phẫu thuật hậu quả của bệnh cũ KHÔNG phải sự kiện dịch tễ hiện tại. Chỉ gán `relevant` nếu bài xác nhận rõ ca bệnh mới, ổ dịch/thống kê dịch tễ hiện tại, hoặc có cảnh báo/công văn khẩn chính thức đáp ứng điều kiện ở mục 4; không suy ra sự kiện từ việc người bệnh đang khám hay điều trị tại bệnh viện.

Nếu ví dụ hoặc nhãn tham khảo mâu thuẫn với ngưỡng này, ưu tiên ngưỡng này và chỉ gán `relevant` khi chính bài đang xét có bằng chứng phù hợp.

Ví dụ: nếu toàn bộ nội dung chỉ khẳng định “bệnh X đang gia tăng” và khuyên người dân phòng bệnh, nhưng không nêu ca mới, địa bàn/thời gian, ổ dịch, số liệu báo cáo hoặc cảnh báo ứng phó chính thức, thì gán `noise`. Ngược lại, công văn hỏa tốc của cơ quan y tế về bệnh X yêu cầu cơ sở y tế tăng cường giám sát và sàng lọc là `relevant`, kể cả khi chưa có ca bệnh được báo cáo. Nếu bài đồng thời ghi nhận ca mới tại địa bàn được cảnh báo, vẫn gán `relevant` nhưng phân loại là tin ca bệnh/ổ dịch, không phải thông báo khẩn. Phải xét toàn bộ nội dung bài; không kết luận chỉ từ tiêu đề hoặc đoạn trích.

Nếu bài chỉ tư vấn, giải thích bệnh/triệu chứng, nêu nguy cơ chung hoặc nhận định xu hướng không kèm dữ kiện dịch tễ cụ thể: gán `noise` khi có nhắc bệnh; gán `irrelevant` khi không thực sự nói về bệnh/dịch tễ.

Chỉ dùng `unsure` khi có dấu hiệu cụ thể về ca mới, ổ dịch/bùng phát, thống kê dịch tễ hoặc cảnh báo ứng phó chính thức nhưng nội dung hiện có chưa đủ xác định. Không dùng `unsure` cho bài tư vấn hay nhận định chung không có sự kiện.
""".strip()

KEYWORD_ROUTE_CRITERIA = f"""
{RELEVANCE_CRITERIA}

Với tuyến từ khóa, tên bệnh chính phải khớp một keyword được phép. Từ khóa ứng viên chỉ giúp tìm bài, không phải bằng chứng để gán relevant.
""".strip()

CONTEXT_ROUTE_CRITERIA = f"""
{RELEVANCE_CRITERIA}

Với tuyến ngữ cảnh không có keyword bệnh, chỉ chấp nhận tín hiệu thực địa cụ thể có khả năng biểu hiện ca mới/chùm ca/bùng phát, thống kê dịch tễ, hoặc cảnh báo/công văn khẩn chính thức về bệnh truyền nhiễm kèm biện pháp ứng phó rõ ràng; không suy đoán tên bệnh.
""".strip()
