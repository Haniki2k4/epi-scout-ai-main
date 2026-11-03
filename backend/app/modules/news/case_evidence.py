"""Conservative verification of model claims against literal source sentences."""
from datetime import date
import re

from .disease_catalog import canonical_disease, keyword_aliases, disease_names

WORDS = {1: 'một', 2: 'hai', 3: 'ba', 4: 'bốn', 5: 'năm', 6: 'sáu', 7: 'bảy', 8: 'tám', 9: 'chín', 10: 'mười'}


def source_location(value, source: str) -> str:
    normalized_source = re.sub(r'\W+', '', source.casefold())
    parts = [part.strip() for part in str(value or '').split(',') if part.strip()]
    return ', '.join(part for part in parts if re.sub(r'\W+', '', part.casefold()) in normalized_source) or 'unknown'


def source_date(value, source: str):
    try:
        parsed = date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None
    day, month, year = parsed.day, parsed.month, parsed.year
    formats = [re.escape(parsed.isoformat()), rf'0?{day}[/.-]0?{month}[/.-]{year}',
               rf'ngày\s+0?{day}\s+tháng\s+0?{month}\s+năm\s+{year}']
    return parsed.isoformat() if re.search(r'(?<!\d)(?:' + '|'.join(formats) + r')(?!\d)', source, re.I) else None


def _quantity_matches(value: int, kind: str, sentence: str):
    numbers = [re.escape(str(value))]
    if value >= 1000:
        numbers.append(re.escape(f'{value:,}').replace(',', r'[.,\s]'))
    if value in WORDS:
        numbers.append(WORDS[value])
    number = r'(?<![\w.,])(?:' + '|'.join(numbers) + r')(?![\w.,])'
    if kind == 'deaths':
        noun = r'\s+(?:(?:ca|trường hợp|người|bệnh nhân)\s+)?(?:tử vong|thiệt mạng)'
        patient_death = rf'{number}\s+(?:bệnh nhân|người)\s+(?:mắc|nhiễm)\s+(?:(?!\d|[,;]|\svà\s).){{1,60}}?\s+(?:đã\s+)?tử vong'
        pattern = rf'{number}{noun}|tử vong\s+thứ\s+{number}|{patient_death}'
    elif kind == 'suspected':
        pattern = rf'{number}\s+(?:(?:ca|trường hợp|người|bệnh nhân)\s+)?nghi\s+(?:nhiễm|mắc|ngờ)'
    else:
        pattern = rf'{number}\s+(?:ca(?:\s+(?:mắc|bệnh|nhiễm|dương tính|xác nhận))?|trường hợp\s+(?:mắc|nhiễm|dương tính)|người\s+(?:mắc|nhiễm|dương tính)|bệnh nhân)(?!\w)(?!\s+(?:tử vong|nghi|tiếp xúc|chưa|đang chờ|theo dõi))'
    for match in re.finditer(pattern, sentence, re.I):
        prefix = sentence[max(0, match.start() - 45):match.start()].casefold()
        if re.search(r'(?:không|chưa)\s+(?:(?:ghi nhận|có|xác nhận|phát hiện|phải|thêm)\s*)+$', prefix):
            continue
        if re.search(r'(?:hơn|gần|khoảng|ít nhất|trên|dưới|hàng)\s*$', prefix):
            continue  # An approximate/bounded claim is not an exact case count.
        yield match


def _bound_disease(sentence: str, match, names: list[str], current: str) -> bool:
    hits = []
    for name in names:
        for alias in keyword_aliases(name):
            for hit in re.finditer(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', sentence, re.I):
                distance = max(0, hit.start() - match.end(), match.start() - hit.end())
                hits.append((distance, -len(alias), canonical_disease(name)))
    if not hits:
        return len(names) == 1
    return min(hits)[0] <= 80 and min(hits)[2] == canonical_disease(current)


def _scope(sentence: str, match) -> str:
    cues = []
    for scope, pattern in [('cumulative', r'lũy kế|luỹ kế|từ đầu năm|tổng số|tích lũy'),
                            ('new', r'\bmới\b|trong ngày|trong 24 giờ'),
                            ('period_total', r'trong tuần|trong tháng|tuần qua|tháng qua')]:
        for hit in re.finditer(pattern, sentence, re.I):
            cues.append((max(0, hit.start() - match.end(), match.start() - hit.end()), scope))
    return min(cues)[1] if cues else 'unknown'


def ground_disease_entries(entries: list[dict], title: str, body: str, allowed_names=None) -> tuple[list[dict], list[str]]:
    source = f'{title}\n{body}'
    sentences = [part.strip() for part in re.split(r'(?<=[.!?;])\s+|\n+', source) if part.strip()]
    names = sorted(disease_names([entry['disease_name'] for entry in entries] + list(allowed_names or [])))
    results, warnings = [], []
    for entry in entries:
        normalized = dict(entry)
        observations = []
        raw = entry.get('observations')
        for observation in raw if isinstance(raw, list) else []:
            if not isinstance(observation, dict):
                continue
            value, kind = observation.get('reported_value'), observation.get('case_type')
            if type(value) is not int or value <= 0 or kind not in {'confirmed', 'suspected', 'total_unspecified', 'deaths'}:
                warnings.append('Số liệu chưa có loại hoặc giá trị hợp lệ.')
                continue
            preferred = str(observation.get('evidence_quote') or '').strip()
            candidates = ([preferred] if preferred and preferred in source and len(preferred) <= 300 else []) + sentences
            verified = None
            for sentence in dict.fromkeys(candidates):
                if len(sentence) > 300:
                    continue
                for match in _quantity_matches(value, kind, sentence):
                    if _bound_disease(sentence, match, names, entry['disease_name']):
                        verified = {**observation, 'evidence_quote': sentence, 'count_scope': _scope(sentence, match),
                                    'location': source_location(observation.get('location'), sentence),
                                    'report_period_start': source_date(observation.get('report_period_start'), source),
                                    'report_period_end': source_date(observation.get('report_period_end'), source)}
                        break
                if verified:
                    break
            if verified:
                if verified not in observations:
                    observations.append(verified)
            else:
                warnings.append('Chưa có câu nguồn gắn đúng số, loại ca và bệnh; cần thẩm định số liệu.')
        normalized['observations'] = observations
        for field, kind, scope in [('new_cases', 'confirmed', 'new'), ('cumulative_cases', 'confirmed', 'cumulative'),
                                    ('suspected_cases', 'suspected', None)]:
            claims = [row['reported_value'] for row in observations if row['case_type'] == kind and (scope is None or row['count_scope'] == scope)]
            normalized[field] = claims[0] if len(claims) == 1 else 0
        normalized['deaths'] = normalized['unspecified_cases'] = 0
        normalized['event_start_date'] = source_date(entry.get('event_start_date'), source)
        normalized['event_end_date'] = source_date(entry.get('event_end_date'), source)
        results.append(normalized)
    return results, list(dict.fromkeys(warnings))
