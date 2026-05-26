import re
from typing import List

CANONICAL_PROVINCES: dict[str, list[str]] = {
    # Municipalities (thành phố trực thuộc trung ương)
    "Hà Nội": ["hn", "ha noi", "thành phố hà nội", "tp hà nội", "hà nội", "hanoi", "thu do ha noi", "thủ đô hà nội", "nội thành hà nội", "hà-nội"],
    "Hồ Chí Minh": ["hcm", "tphcm", "tp hcm", "tp. hcm", "thành phố hồ chí minh", "tp hồ chí minh", "sài gòn", "saigon", "sai gon", "hồ chí minh", "ho chi minh", "hochiminh", "tphan ho chi minh", "tpho ho chi minh"],
    "Đà Nẵng": ["da nang", "danang", "thành phố đà nẵng", "tp đà nẵng", "đà nẵng", "da-nang"],
    "Cần Thơ": ["can tho", "cantho", "thành phố cần thơ", "tp cần thơ", "cần thơ", "tay do", "tây đô"],
    "Hải Phòng": ["hai phong", "haiphong", "thành phố hải phòng", "tp hải phòng", "hải phòng", "hai-phong"],

    # Northern provinces
    "Bắc Ninh": ["bac ninh", "bacninh", "tỉnh bắc ninh", "bắc ninh"],
    "Bắc Giang": ["bac giang", "bacgiang", "tỉnh bắc giang", "bắc giang"],
    "Bắc Kạn": ["bac kan", "backan", "tỉnh bắc kạn", "bắc kạn", "bac can"],
    "Cao Bằng": ["cao bang", "caobang", "tỉnh cao bằng", "cao bằng"],
    "Hà Giang": ["ha giang", "hagiang", "tỉnh hà giang", "hà giang"],
    "Lạng Sơn": ["lang son", "langson", "tỉnh lạng sơn", "lạng sơn"],
    "Phú Thọ": ["phu tho", "phutho", "tỉnh phú thọ", "phú thọ"],
    "Quảng Ninh": ["quang ninh", "quangninh", "tỉnh quảng ninh", "quảng ninh", "ha long", "hạ long"],
    "Thái Nguyên": ["thai nguyen", "thainguyen", "tỉnh thái nguyên", "thái nguyên"],
    "Tuyên Quang": ["tuyen quang", "tuyenquang", "tỉnh tuyên quang", "tuyên quang"],
    "Lào Cai": ["lao cai", "laocai", "tỉnh lào cai", "lào cai", "sa pa"],
    "Yên Bái": ["yen bai", "yenbai", "tỉnh yên bái", "yên bái"],
    "Điện Biên": ["dien bien", "dienbien", "tỉnh điện biên", "điện biên", "dien bien phu", "điện biên phủ"],
    "Hoà Bình": ["hoa binh", "hoabinh", "tỉnh hoà bình", "hoà bình", "hòa bình"],
    "Lai Châu": ["lai chau", "laichau", "tỉnh lai châu", "lai châu"],
    "Sơn La": ["son la", "sonla", "tỉnh sơn la", "sơn la"],
    "Hưng Yên": ["hung yen", "hungyen", "tỉnh hưng yên", "hưng yên"],
    "Hải Dương": ["hai duong", "haiduong", "tỉnh hải dương", "hải dương"],
    "Hà Nam": ["ha nam", "hanam", "tỉnh hà nam", "hà nam"],
    "Nam Định": ["nam dinh", "namdinh", "tỉnh nam định", "nam định"],
    "Ninh Bình": ["ninh binh", "ninhbinh", "tỉnh ninh bình", "ninh bình"],
    "Thái Bình": ["thai binh", "thaibinh", "tỉnh thái bình", "thái bình"],
    "Vĩnh Phúc": ["vinh phuc", "vinhphuc", "tỉnh vĩnh phúc", "vĩnh phúc"],

    # North Central provinces (Bắc Trung Bộ)
    "Thanh Hóa": ["thanh hoa", "thanhhoa", "tỉnh thanh hóa", "thanh hóa"],
    "Nghệ An": ["nghe an", "nghean", "tỉnh nghệ an", "nghệ an", "vinh", "vinh city"],
    "Hà Tĩnh": ["ha tinh", "hatinh", "tỉnh hà tĩnh", "hà tĩnh"],
    "Quảng Bình": ["quang binh", "quangbinh", "tỉnh quảng bình", "quảng bình", "dong hoi", "đồng hới"],
    "Quảng Trị": ["quang tri", "quangtri", "tỉnh quảng trị", "quảng trị", "dong ha", "đông hà"],
    "Thừa Thiên Huế": ["thua thien hue", "hue", "tỉnh thừa thiên huế", "thừa thiên huế", "tt hue", "huế", "thua thien", "tp huế", "thành phố huế", "thừa thiên–huế"],

    # South Central provinces (Nam Trung Bộ)
    "Quảng Nam": ["quang nam", "quangnam", "tỉnh quảng nam", "quảng nam", "hoi an", "hội an", "tam ky", "tam kỳ"],
    "Quảng Ngãi": ["quang ngai", "quangngai", "tỉnh quảng ngãi", "quảng ngãi"],
    "Bình Định": ["binh dinh", "binhdinh", "tỉnh bình định", "bình định", "quy nhon", "quy nhơn"],
    "Phú Yên": ["phu yen", "phuyen", "tỉnh phú yên", "phú yên", "tuy hoa", "tuy hòa"],
    "Khánh Hòa": ["khanh hoa", "khanhhoa", "tỉnh khánh hòa", "khánh hòa", "nha trang", "cam ranh", "cam ranh"],
    "Ninh Thuận": ["ninh thuan", "ninhthuan", "tỉnh ninh thuận", "ninh thuận", "phan rang", "phan rang - tháp chàm", "phan rang tháp chàm"],
    "Bình Thuận": ["binh thuan", "binhthuan", "tỉnh bình thuận", "bình thuận", "phan thiet", "phan thiết", "mui ne", "mũi né"],

    # Central Highlands (Tây Nguyên)
    "Kon Tum": ["kon tum", "kontum", "tỉnh kon tum", "kon tum"],
    "Gia Lai": ["gia lai", "gialai", "tỉnh gia lai", "gia lai", "pleiku", "playku"],
    "Đắk Lắk": ["dak lak", "daklak", "tỉnh đắk lắk", "đắk lắk", "dak lak", "daklak", "buon ma thuot", "buôn ma thuột"],
    "Đắk Nông": ["dak nong", "daknong", "tỉnh đắk nông", "đắk nông", "dak nong", "daknong", "gia nghia", "gia nghĩa"],
    "Lâm Đồng": ["lam dong", "lamdong", "tỉnh lâm đồng", "lâm đồng", "da lat", "đà lạt", "bao loc", "bảo lộc", "dalat"],

    # Southern provinces (Miền Nam)
    "Bình Phước": ["binh phuoc", "binhphuoc", "tỉnh bình phước", "bình phước"],
    "Bình Dương": ["binh duong", "binhduong", "tỉnh bình dương", "bình dương", "thu dau mot", "thủ dầu một", "di an", "dĩ an"],
    "Đồng Nai": ["dong nai", "dongnai", "tỉnh đồng nai", "đồng nai", "bien hoa", "biên hòa"],
    "Tây Ninh": ["tay ninh", "tayninh", "tỉnh tây ninh", "tây ninh"],
    "Bà Rịa - Vũng Tàu": ["ba ria vung tau", "vung tau", "bà rịa vũng tàu", "bà rịa - vũng tàu", "tỉnh bà rịa - vũng tàu", "ba ria", "vũng tàu", "vungtau", "brvt"],
    "Long An": ["long an", "longan", "tỉnh long an"],
    "Tiền Giang": ["tien giang", "tiengiang", "tỉnh tiền giang", "tiền giang", "my tho", "mỹ tho"],
    "Bến Tre": ["ben tre", "bentre", "tỉnh bến tre", "bến tre"],
    "Đồng Tháp": ["dong thap", "dongthap", "tỉnh đồng tháp", "đồng tháp", "cao lanh", "cao lãnh", "sa dec", "sa đéc"],
    "Vĩnh Long": ["vinh long", "vinhlong", "tỉnh vĩnh long", "vĩnh long"],
    "Trà Vinh": ["tra vinh", "travinh", "tỉnh trà vinh", "trà vinh"],
    "An Giang": ["an giang", "angiang", "tỉnh an giang", "an giang", "long xuyen", "long xuyên", "chau doc", "châu đốc"],
    "Kiên Giang": ["kien giang", "kiengiang", "tỉnh kiên giang", "kiên giang", "rach gia", "rạch giá", "ha tien", "hà tiên", "phu quoc", "phú quốc"],
    "Cà Mau": ["ca mau", "camau", "tỉnh cà mau", "cà mau"],
    "Bạc Liêu": ["bac lieu", "baclieu", "tỉnh bạc liêu", "bạc liêu"],
    "Hậu Giang": ["hau giang", "haugiang", "tỉnh hậu giang", "hậu giang", "vi thanh", "vị thanh"],
    "Sóc Trăng": ["soc trang", "soctrang", "tỉnh sóc trăng", "sóc trăng"],
}

NON_PROVINCE_PATTERNS = [
    r"^miền\s+(bắc|trung|nam|bắc bộ|trung bộ|nam bộ)$",
    r"^các\s+tỉnh\s+(phía\s+)?(bắc|trung|nam)",
    r"^tây\s+nguyên$",
    r"^đồng\s+bằng\s+sông\s+cửu\s+long$",
    r"^đồng\s+bằng\s+bắc\s+bộ$",
    r"^việt\s+nam$",
    r"^nước\s+ngoài$",
    r"^quốc\s+tế$",
]


def build_reverse_map() -> dict[str, str]:
    """Build a case-insensitive alias → canonical mapping."""
    mapping: dict[str, str] = {}
    for canonical, aliases in CANONICAL_PROVINCES.items():
        canonical_lower = canonical.lower()
        for alias in aliases:
            mapping[alias] = canonical
        mapping[canonical_lower] = canonical
    return mapping


_REVERSE_MAP = build_reverse_map()
_COMPILED_NON_PROVINCE = [re.compile(p, re.IGNORECASE) for p in NON_PROVINCE_PATTERNS]


def normalize_location(raw: str) -> str:
    """
    Normalize a raw location string to the canonical province name.
    Returns 'unknown' if no match is found or if it's a non-province pattern.
    """
    if not raw or not raw.strip():
        return "unknown"

    cleaned = raw.strip().lower()
    cleaned = re.sub(r"^(tỉnh|tp\.?\s*|thành phố|tx\.?\s*|thị xã|huyện|quận|phường|xã|thị trấn)\s+", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"[‘’'\"“”«»]", "", cleaned).strip()

    for pattern in _COMPILED_NON_PROVINCE:
        if pattern.match(cleaned):
            return "unknown"

    if cleaned in _REVERSE_MAP:
        return _REVERSE_MAP[cleaned]

    if cleaned.replace(" ", "") in _REVERSE_MAP:
        return _REVERSE_MAP[cleaned.replace(" ", "")]

    return "unknown"


def parse_location_list(raw: str) -> list[str]:
    """
    Parse comma-separated locations, normalize each, filter unknowns.
    Returns a deduplicated, ordered list of canonical province names.
    """
    if not raw or not raw.strip():
        return ["unknown"]

    raw_locations = [loc.strip() for loc in raw.split(",") if loc.strip()]
    if not raw_locations:
        return ["unknown"]

    normalized: list[str] = []
    seen: set[str] = set()
    for loc in raw_locations:
        norm = normalize_location(loc)
        if norm != "unknown" and norm not in seen:
            normalized.append(norm)
            seen.add(norm)

    return normalized if normalized else ["unknown"]


def extract_locations_from_text(text: str) -> list[str]:
    """
    Regex-based fallback: scan text for known province names.
    Returns deduplicated list of canonical province names.
    """
    if not text:
        return ["unknown"]

    text_lower = text.lower()
    found: list[str] = []
    seen: set[str] = set()

    for canonical, aliases in CANONICAL_PROVINCES.items():
        for alias in aliases:
            if alias in text_lower:
                if canonical not in seen:
                    found.append(canonical)
                    seen.add(canonical)
                break

    return found if found else ["unknown"]
