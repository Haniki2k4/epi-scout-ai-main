"""Disease identities shared by detection and analytics. Never rewrites stored data."""
import re
import unicodedata


def _key(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value).casefold()).strip()


# Canonical name -> aliases. Subtypes are deliberately separate identities.
ALIASES = {
    "não mô cầu": ("viêm não mô cầu", "viêm màng não mô cầu", "bệnh do não mô cầu", "Neisseria meningitidis"),
    "bệnh dại": ("virus dại", "rabies"),
    "sốt rét": ("malaria",),
    "whitmore": ("bệnh Whitmore", "melioidosis", "Burkholderia pseudomallei"),
    "liên cầu lợn": ("liên cầu khuẩn lợn", "Streptococcus suis"),
    "quai bị": ("mumps",),
    "uốn ván": ("tetanus",),
    "thương hàn": ("typhoid fever", "Salmonella Typhi"),
    "rubella": ("sởi Đức",),
    "bệnh than": ("anthrax", "Bacillus anthracis"),
    "xoắn khuẩn vàng da": ("leptospirosis", "Leptospira", "nhiễm leptospira"),
    "adenovirus": ("virus adeno", "vi rút adeno", "vi rút adenovirus"),
    "nhiễm rsv": ("RSV", "virus hợp bào hô hấp", "vi rút hợp bào hô hấp", "respiratory syncytial virus"),
    "chikungunya": ("sốt chikungunya",),
    "ngộ độc botulinum": ("botulism", "Clostridium botulinum"),
    "listeria": ("nhiễm Listeria", "listeriosis", "Listeria monocytogenes"),
    "legionella": ("bệnh Legionnaire", "legionellosis", "Legionella pneumophila"),
    "viêm gan d": ("viêm gan vi rút D", "hepatitis D"),
    "viêm gan e": ("viêm gan vi rút E", "hepatitis E"),
    "marburg": ("virus Marburg", "Marburg virus"),
    "nipah": ("virus Nipah", "Nipah virus"),
    "lassa": ("sốt Lassa", "Lassa fever", "virus Lassa"),
    "sốt vàng": ("yellow fever",),
    "sốt tây sông nin": ("virus Tây sông Nile", "West Nile virus", "sốt Tây sông Nile"),
    "mers-cov": ("hội chứng hô hấp Trung Đông", "MERS"),
    "cúm a/h5n1": ("H5N1", "A(H5N1)", "cúm A(H5N1)", "cúm A H5N1"),
    "cúm a/h5n6": ("H5N6", "A(H5N6)", "cúm A(H5N6)", "cúm A H5N6"),
    "cúm a/h7n9": ("H7N9", "A(H7N9)", "cúm A(H7N9)", "cúm A H7N9"),
    "cúm a/h9n2": ("H9N2", "A(H9N2)", "cúm A(H9N2)", "cúm A H9N2"),
    "nhiễm rickettsia": ("Rickettsia", "bệnh do Rickettsia"),
    "sốt mò": ("scrub typhus", "Orientia tsutsugamushi"),
    "sán lá gan": ("bệnh sán lá gan",),
    "sán lá phổi": ("bệnh sán lá phổi",),
    "bại liệt": ("bệnh bại liệt", "polio", "poliomyelitis"),
    "bệnh lao": ("lao phổi", "tuberculosis"),
    "bệnh lậu": ("gonorrhea",),
    "covid-19": ("covid", "SARS-CoV-2"),
    "đậu mùa khỉ": ("mpox", "monkeypox"),
    "ebola": ("virus Ebola",),
    "hanta": ("hantavirus", "virus Hanta"),
    "zika": ("virus Zika",),
    "sốt xuất huyết": ("dengue", "sốt xuất huyết dengue"),
    "viêm gan a": ("viêm gan vi rút A", "hepatitis A"),
    "viêm gan b": ("viêm gan vi rút B", "hepatitis B"),
    "viêm gan c": ("viêm gan vi rút C", "hepatitis C"),
    "viêm não nhật bản": ("Japanese encephalitis",),
    "viêm não vi rút": ("viêm não virus",),
    "nhiễm rotavirus": ("rotavirus", "tiêu chảy do rotavirus"),
    "sởi": ("measles",),
    "thủy đậu": ("varicella", "chickenpox"),
    "tay chân miệng": ("tay-chân-miệng", "HFMD"),
    "virus chưa xác định": ("virus", "vi rút", "vi-rút", "nhiễm virus chưa rõ loại"),
    "sốt chưa rõ nguyên nhân": ("sốt", "sốt không rõ nguyên nhân"),
    "sốt do virus chưa xác định": ("sốt virus", "sốt siêu vi", "sốt do virus"),
}
_CANONICAL = {_key(alias): name for name, aliases in ALIASES.items() for alias in (name, *aliases)}

# All additions from the reviewed list, plus explicit unresolved viral fever.
ADDITIONAL_KEYWORDS = (
    "bệnh dại", "sốt rét", "Whitmore", "liên cầu lợn", "quai bị", "uốn ván",
    "thương hàn", "rubella", "bệnh than", "xoắn khuẩn vàng da", "adenovirus",
    "virus hợp bào hô hấp", "chikungunya", "ngộ độc botulinum", "nhiễm Listeria",
    "bệnh Legionnaire", "viêm gan D", "viêm gan E", "virus Marburg", "virus Nipah",
    "sốt Lassa", "sốt vàng", "virus Tây sông Nile", "MERS-CoV", "cúm A/H5N6",
    "cúm A/H7N9", "cúm A/H9N2", "nhiễm Rickettsia", "sán lá gan", "sán lá phổi",
    "sốt do virus",
)

# Preserve the supplied legacy vocabulary on fresh installations as well.
LEGACY_KEYWORDS = (
    "đậu mùa khỉ", "Ebola", "viêm phổi", "bệnh lậu", "zika", "lỵ", "cúm",
    "giang mai", "virus", "hanta", "sốt", "bệnh tả", "cúm A/H5N1", "Bệnh bại liệt",
    "h5n1", "bệnh lao", "viêm gan A", "nhiễm rotavirus", "viêm gan C", "viêm gan B",
    "HIV/AIDS", "thủy đậu", "viêm não vi rút", "sởi", "sốt phát ban", "đậu mùa",
    "dịch hạch", "cúm gia cầm", "Bại liệt", "tay chân miệng", "sốt xuất huyết",
    "covid-19", "viêm não nhật bản", "ho gà", "bạch hầu", "não mô cầu", "cúm mùa",
    "cúm B", "cúm A",
)

VIRAL_DISEASES = frozenset({
    "cúm", "cúm a", "cúm b", "cúm mùa", "cúm gia cầm", "cúm a/h5n1",
    "cúm a/h5n6", "cúm a/h7n9", "cúm a/h9n2", "covid-19", "sởi", "rubella",
    "quai bị", "thủy đậu", "tay chân miệng", "sốt xuất huyết", "zika", "hanta",
    "đậu mùa", "đậu mùa khỉ", "ebola", "marburg", "lassa", "nipah", "sốt vàng",
    "sốt tây sông nin", "mers-cov", "bại liệt", "bệnh dại", "adenovirus",
    "nhiễm rsv", "chikungunya", "viêm gan a", "viêm gan b", "viêm gan c",
    "viêm gan d", "viêm gan e", "viêm não nhật bản", "viêm não vi rút",
    "nhiễm rotavirus", "hiv/aids", "nhiễm hpv", "sốt do virus chưa xác định",
})
# Membership here is a surveillance category, not an inference that every case has fever.
FEVER_DISEASES = frozenset({
    "sốt rét", "sốt xuất huyết", "sốt mò", "sốt vàng", "sốt tây sông nin",
    "lassa", "ebola", "marburg", "chikungunya", "thương hàn", "phó thương hàn",
    "nhiễm rickettsia", "sốt phát ban", "sốt do virus chưa xác định",
})


def canonical_disease(value: str) -> str:
    key = _key(value)
    return _CANONICAL.get(key, key)


def keyword_aliases(value: str) -> tuple[str, ...]:
    name = canonical_disease(value)
    return tuple(dict.fromkeys((value, name, *ALIASES.get(name, ()))))


def disease_names(values) -> set[str]:
    """Canonical detail labels, with broad labels used only when unresolved."""
    values = [v for v in values if isinstance(v, str) and v.strip()]
    explicit = {_key(v) for v in values}
    names = {canonical_disease(v) for v in values}
    if names & VIRAL_DISEASES and "virus chưa xác định" not in explicit:
        names.discard("virus chưa xác định")
    if names & FEVER_DISEASES and "sốt chưa rõ nguyên nhân" not in explicit:
        names.discard("sốt chưa rõ nguyên nhân")
    # Do not count the same flu observation both as a parent and a subtype.
    if any(n.startswith("cúm a/") for n in names):
        names.discard("cúm a")
        names.discard("cúm gia cầm")
    if any(n.startswith("cúm ") for n in names):
        names.discard("cúm")
    return names


def belongs_to_category(name: str, category: str) -> bool:
    if category == "virus":
        return name in VIRAL_DISEASES or name == "virus chưa xác định"
    if category == "sốt":
        return name in FEVER_DISEASES or name == "sốt chưa rõ nguyên nhân"
    raise ValueError("Unknown disease category")


def matches_disease_filter(names: set[str], requested: str | None) -> bool:
    if not requested:
        return True
    # Legacy broad filters request a union, never a sum of subtype counts.
    if _key(requested) in {"virus", "sốt"}:
        return any(belongs_to_category(name, _key(requested)) for name in names)
    return canonical_disease(requested) in names


LLM_DISEASE_RULES = """
## Phân loại nguyên nhân và tên bệnh
- Giữ riêng từng bệnh/tác nhân và từng phân týp cúm; không gộp thành 'virus' hoặc 'sốt'.
- Chỉ định danh nguyên nhân khi bài nêu rõ bằng chứng; không đoán từ triệu chứng.
- Nếu chỉ có 'virus' hoặc 'sốt', chọn keyword rộng đó và giải thích chưa rõ nguyên nhân trong reason.
- 'Sốt do virus' chỉ được chọn khi nguồn nêu rõ nguyên nhân virus nhưng chưa rõ loại.
- Biến thể/tên khoa học trong ngoặc là tên đồng nghĩa, không phải bệnh mới.
- Không ghi cùng một số ca cho cả tên bệnh cụ thể và nhãn rộng bao trùm nó.
- Không tự phân bổ số ca tổng giữa nhiều bệnh. Giữ số chưa rõ nguyên nhân ở mục riêng.
"""


def normalize_disease_entries(entries, allowed_keywords=None) -> list[dict]:
    """Validate LLM names without merging or inventing numeric observations."""
    if not isinstance(entries, list):
        return []
    allowed = ({canonical_disease(k) for k in allowed_keywords}
               if allowed_keywords is not None else None)
    result = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("disease_name"), str):
            continue
        name = canonical_disease(entry["disease_name"])
        if not name or (allowed is not None and name not in allowed):
            continue
        # Exact duplicate observations from aliases must not duplicate counts.
        import json
        normalized = {**entry, "disease_name": name}
        signature = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
        if signature not in seen:
            seen.add(signature)
            result.append(normalized)
    return result
