from backend.app.modules.news.html_utils import trim_feed_related_titles


def test_vnanet_related_headlines_are_removed():
    text = (
        "Trong tổng số 50 ca bệnh có 6 trẻ đang phải thở máy."
        "Bộ Y tế yêu cầu tăng cường phòng chống bệnh tay chân miệng"
        "Đi trước một bước trong phòng dịch"
    )

    assert trim_feed_related_titles(
        text, "https://vnanet.vn/vi/rss/suc-khoe-7.rss"
    ) == "Trong tổng số 50 ca bệnh có 6 trẻ đang phải thở máy."


def test_other_feeds_keep_multiple_sentences():
    text = "Câu thứ nhất. Câu thứ hai vẫn thuộc mô tả chính."

    assert trim_feed_related_titles(
        text, "https://example.com/health.rss"
    ) == text


def test_vnanet_normal_sentence_spacing_is_not_a_boundary():
    text = "TP. Hồ Chí Minh ghi nhận ca bệnh mới."

    assert trim_feed_related_titles(
        text, "https://vnanet.vn/vi/rss/suc-khoe-7.rss"
    ) == text
