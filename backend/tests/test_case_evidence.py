import pytest
from backend.app.modules.news.case_evidence import ground_disease_entries, source_date, source_location


def entry(value=2, kind='confirmed', quote='', **kwargs):
    return {'disease_name': 'não mô cầu', 'new_cases': 2, 'cumulative_cases': 2,
            'event_start_date': '2024-10-25', 'observations': [
                {'reported_value': value, 'case_type': kind, 'count_scope': 'new|cumulative', 'evidence_quote': quote, **kwargs}]}


def test_death_count_cannot_become_cases_or_an_invented_year():
    body = 'Đây là trường hợp tử vong thứ 2 do não mô cầu trong năm nay.'
    result, warnings = ground_disease_entries([entry(quote=body)], '', body)
    assert result[0]['observations'] == [] and warnings
    assert result[0]['new_cases'] == result[0]['cumulative_cases'] == 0
    assert result[0]['event_start_date'] is None


def test_wrong_citation_can_only_be_replaced_by_a_literal_matching_source_claim():
    title = 'Cà Mau ghi nhận 2 ca mắc não mô cầu, một người tử vong'
    body = 'Đây là trường hợp tử vong thứ 2 do não mô cầu trong năm nay.'
    result, _ = ground_disease_entries([entry(quote=body, location='Hà Nội')], title, body)
    observation = result[0]['observations'][0]
    assert observation['reported_value'] == 2 and observation['evidence_quote'] == title
    assert observation['count_scope'] == 'unknown' and observation['location'] == 'unknown'
    assert result[0]['new_cases'] == result[0]['cumulative_cases'] == 0


@pytest.mark.parametrize('body', [
    'Theo dõi 22 người tiếp xúc bệnh nhân não mô cầu.',
    'Bệnh nhân não mô cầu 22 tuổi đang điều trị.',
    'Chưa ghi nhận 22 ca mắc não mô cầu.',
    'Có khoảng 22 ca mắc não mô cầu.',
    'Có 22 ca nghi nhiễm não mô cầu.',
    'Có 22 ca chưa xác nhận não mô cầu.',
])
def test_age_contacts_negation_approximation_and_suspected_are_not_confirmed(body):
    result, _ = ground_disease_entries([entry(22, quote=body)], '', body)
    assert result[0]['observations'] == []


def test_explicit_new_cases_scope_and_date_are_preserved():
    body = 'Ngày 02/11/2026, Cà Mau ghi nhận 2 ca mắc não mô cầu mới.'
    raw = entry(quote=body, location='Cà Mau', report_period_start='2026-11-02', report_period_end='2026-11-02')
    result, _ = ground_disease_entries([raw], '', body)
    assert result[0]['new_cases'] == 2 and result[0]['cumulative_cases'] == 0
    assert result[0]['observations'][0]['report_period_start'] == '2026-11-02'
    assert result[0]['observations'][0]['location'] == 'Cà Mau'


def test_counts_are_not_assigned_to_the_wrong_disease():
    body = 'Có 3 ca mắc sởi và 5 ca mắc thủy đậu tại Hà Nội.'
    entries = [{'disease_name': name, 'observations': [{'reported_value': value, 'case_type': 'confirmed', 'evidence_quote': body}]} for name, value in [('sởi', 5), ('thủy đậu', 3)]]
    result, _ = ground_disease_entries(entries, '', body)
    assert all(not row['observations'] for row in result)


def test_partial_dates_and_new_provinces_are_not_invented():
    assert source_date('2026-10-25', 'Phát bệnh ngày 25-10.') is None
    assert source_date('2026-10-25', 'Ngày 25 tháng 10 năm 2026.') == '2026-10-25'
    assert source_location('Hà Nội, Cà Mau', 'Bệnh được ghi nhận tại Cà Mau.') == 'Cà Mau'


def test_patient_death_is_separate_from_ages_and_contacts():
    body = 'Một bệnh nhân mắc bệnh dại đã tử vong. Bệnh nhân 38 tuổi và có 20 người tiếp xúc.'
    raw = {'disease_name': 'bệnh dại', 'observations': [{'reported_value': 1, 'case_type': 'deaths', 'evidence_quote': body}]}
    result, _ = ground_disease_entries([raw], '', body)
    assert result[0]['observations'][0]['reported_value'] == 1
    assert result[0]['observations'][0]['case_type'] == 'deaths'
