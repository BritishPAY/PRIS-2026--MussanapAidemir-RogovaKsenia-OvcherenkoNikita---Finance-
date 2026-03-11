"""
parser.py  ·  v7
────────────────
OCR-артефакты, которые обрабатываем:
  $  → S, s                                  (буква)
  $  → 8, 3, 4  перед двузначным: 813.95 → $13.95
  $  → 5        перед однозначным: 54.00  → $4.00
  Пробелы внутри числа: "16 . 00", "16 , 00", "152, 00"
  Буква в дробной части: "12.C0" → 12.00
  total-split: "128\n33" → 128.33
  Total-keyword OCR: Tcta], Tota|, Tota", totl, txtl …
  Taxable/Settled/med-rare/of sale — новые SKIP-паттерны
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from config import PARSED_DIR


# ═══════════════════════════════════════════════════════════════
#  НОРМАЛИЗАЦИЯ ЦЕН
# ═══════════════════════════════════════════════════════════════

_DOLLAR_OCR = re.compile(r'^[Ss\$](?=\d)')


def _normalize_price_str(s: str) -> str:
    s = s.strip()
    s = re.sub(r'[€£¥]', '', s)
    s = _DOLLAR_OCR.sub('', s)                            # S7.99 → 7.99
    s = re.sub(                                            # "16 . (0" → "16.00"
        r'(\d)\s+[.,]\s*(?:[€({\[Cc])?(\d)',
        lambda m: m.group(1) + '.' + m.group(2), s)
    s = re.sub(r'^(\d+),(\d{2})\s*$', r'\1.\2', s)        # 17,00 → 17.00
    s = re.sub(r'(\d),\s+(\d{2})\s*$', r'\1.\2', s)       # "152, 00" → 152.00
    s = re.sub(r'(\d),\.(\d)', r'\1.\2', s)               # 7,.99 → 7.99
    s = re.sub(r'(\.\d?)[CcOoQq](\d)', r'\g<1>0\2', s)   # .C0 → .00
    return s.strip()


def _parse_float(s: str) -> Optional[float]:
    try:
        return float(s.replace(',', '.'))
    except (ValueError, AttributeError):
        return None


def is_price_only_line(line: str) -> bool:
    norm = _normalize_price_str(line.strip())
    norm_clean = re.sub(r'[^\d.]', '', norm)
    return bool(re.match(r'^\d+(\.\d{1,2})?\s*$', norm_clean)) and len(norm_clean) >= 2


# Максимум для OCR prefix-замены ($ → 3/4/5/8).
# Цены > этого порога считаются "реальными" (не OCR-артефактом).
_OCR_PREFIX_MAX = 200.0


def extract_price_from_end(line: str) -> Optional[float]:
    """
    Ищет цену в конце строки.

    ВАЖНО: для строк, которые целиком являются числом (standalone price),
    сначала проверяем OCR-prefix паттерны. Это позволяет правильно
    раскодировать "814.36" → $14.36 и "425.76" → $25.76.
    """
    stripped = line.strip()
    norm = _normalize_price_str(stripped)

    # Если строка — чистое число (standalone), проверяем OCR-prefix ПЕРВЫМИ
    if re.match(r'^\d+[.,]\d{2}\s*$', stripped):
        # $ → 8/3/4 перед РОВНО двузначным: "813.95" → $13.95, "425.76" → $25.76
        for prefix in ('3', '4', '8'):
            m2 = re.match(rf'^{prefix}(\d{{2}}[.,]\d{{2}})\s*$', stripped)
            if m2:
                val = _parse_float(m2.group(1))
                if val and 0.5 < val < _OCR_PREFIX_MAX:
                    return val
        # $ → 5 перед однозначным: "54.00" → $4.00  (только до $9.99)
        m1 = re.match(r'^5(\d[.,]\d{2})\s*$', stripped)
        if m1:
            val = _parse_float(m1.group(1))
            if val and 0.25 < val < 10:
                return val

    # Общий паттерн: NN.NN в конце (после нормализации)
    m = re.search(r'(\d+[.,]\d{2})\s*$', norm)
    if m:
        val = _parse_float(m.group(1))
        if val and val > 0:
            return val

    return None


def extract_price_spaced(line: str) -> Optional[float]:
    """Расширенное: "1 5 4" → 154 (для поиска total)."""
    p = extract_price_from_end(line)
    if p:
        return p
    digits_only = re.sub(r'\s+', '', line.strip())
    if re.match(r'^\d{2,5}$', digits_only):
        val = _parse_float(digits_only)
        if val and 0.5 < val < 50_000:
            return val
    return None


# ═══════════════════════════════════════════════════════════════
#  ФИЛЬТРЫ ПРОПУСКА
# ═══════════════════════════════════════════════════════════════

# Модификаторы размера/степени прожарки (стоят между именем и ценой)
SIZE_MODIFIER_RE = re.compile(
    r'^('
    r'SMALL|MEDIUM|LARGE|SM\b|LG\b|MD\b|XL\b|REG(?:ULAR)?|MINI'
    r'|med-rare|medium.?rare|well.?done|over.?easy|sunny.?side'
    r'|extra\s+spicy|mild|spicy'
    r')\s*$',
    re.IGNORECASE
)

SKIP_RE = re.compile(
    r'(?i)\b('
    # Персонал / заголовки
    r'cashier|server|clerk|station|terminal|'
    r'order\s*[#№]?|check\s*[#№]|table\b|guests?\b|seat\b|'
    r'dine[\s-]+in|take[\s-]?out|pickup\b|settled\b|'
    r'thank\s+you|come\s+again|pleasure|dining\s+with|'
    r'tel\b|phone\b|'
    # Карты / оплата
    r'visa|mastercard|amex|discover|card\s*[#№]|acct|approval|auth|'
    r'cash\b|change\b|chng\b|'
    # Total / subtotal (все OCR-варианты)
    r'sub[\s-]?total|subtotal|subtctal|subtota|subioia|sbt|'
    r'sales?\s+tax|tax\b|taxes\b|iaxes|'
    r'grand\s+total|total\b|tctal|tcta|tota[l\|]|'
    r'totl\b|txtl\b|'
    # Чаевые и процентные строки
    r'gratuity|gratulty|gratultles|suggested|'
    r'tip\b|'
    # Прочие служебные
    r'amount\s+due|amt\s+due|amt\b|balance\b|'
    r'service\s+fee|service\s+fees|service\s+charge|credit\s+card|resort\s+tax|'
    r'regular\s+price|'
    r'add[\s-]?on|'
    r'drive[\s-]?thru|mobile\s+order|download\s+the|'
    r'survey|for\s+a\s+chance|see\s+back|receipt|'
    r'void\b|discount\b|taxable\b|'
    r'complimentar|item\s+comps|'
    r'open\s+time|closed\b|'
    r'beverages?\b|^food\b'            # итоговые метки-резюме в конце чека
    r')\b'
    r'|of\s+sa\w*\s*l?e?[;:]?'            # "% of sale:" / "OOK_of sa le;" (tips)
    r'|\(axable'                       # "(axable:" = OCR "Taxable:"
    r'|\bitem\s*\(s\)'
    r'|\btota\s*[\]\|l;:"\'`]'        # "Tcta]", "Tota|", "Tota\"", "Tota'"
    r'|={3,}|-{3,}|[*]{3,}|#{3,}|[k]{4,}'
    r'|\bXX{3,}\b'
    r'|^[rk]+\s+ToGo'
    r'|scontrino|contante|totale\b'
    ,
    re.IGNORECASE
)

PHONE_ONLY_RE  = re.compile(r'^\s*\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\s*$')
DIGITS_ONLY_RE = re.compile(r'^\s*[\d\s]{1,10}\s*$')
DATETIME_RE    = re.compile(
    r'^\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}'
    r'|\d{1,2}:\d{2}(:\d{2})?\s*(AM|PM)?'
    r'|\d{1,2}-[A-Za-z]{3}-\d{4}'
    r'|\d{2}-\d{4}\s+\d{2}:\d{2}',
    re.IGNORECASE
)

OCR_NAME_FIXES = [
    (r'(?i)Co\s*f\s*fee|Coffe{2,}',    'Coffee'),
    (r'(?i)Cok\s*e\b',                 'Coke'),
    (r'(?i)Lunc\s*h\b',                'Lunch'),
    (r'(?i)Chicke\s*n\b',              'Chicken'),
    (r'(?i)Ensa\s*lada',               'Ensalada'),
    (r'(?i)Sparklingg\b',              'Sparkling'),
    (r'(?i)Burge\s*r\b',               'Burger'),
    (r'(?i)Parmes\s*an\b',             'Parmesan'),
    (r'(?i)Sirlo\s*in\b',              'Sirloin'),
    (r'(?i)Asparaq\w*\b',              'Asparagus'),
    (r'(?i)Chees\w*urger\b',           'Cheeseburger'),
    (r'(?i)Cal[sz]c?[ao]?ne?\b',       'Calzone'),
    (r'(?i)Margherit\w+\b',            'Margherita'),
    (r'(?i)ReB\s+MEAL\b',              'R&B MEAL'),
    (r'(?i)MACRCHZ\b',                 'MAC&CHZ'),
    (r'(?i)COLL\s*GRN\b',              'COLL GRN'),
    (r'(?i)SPCY\s*FR[IY]\w*',          'SPICY FRY'),
    (r'(?i)Coctai[l|]\s*Sn?[rn]iop?',  'Cocktail Shrimp'),
    (r'(?i)Eourguigonne?',              'Escargot Bourguignon'),
    (r'(?i)cappucin\w*',               'Cappuccino'),
    (r'(?i)Dririk\b',                  'Drink'),
    (r'(?i)Dft\s+',                    'Draft '),   # "Dft Guiness" → "Draft Guiness"
]


def clean_name(name: str) -> str:
    name = re.sub(r'\s{2,}', ' ', name).strip()
    name = re.sub(r'^\$\s+', '', name)           # "$ ADD FRIES" → "ADD FRIES"
    name = re.sub(r'^[Ss\$]+(?=\d)', '', name)
    # Убираем OCR-модификаторы в начале ("Med SO.0o ", "MILD PLEASE ")
    name = re.sub(
        r'^(?:Med|MILD|MAKE\s+IT\s+MILD|MAKE\s+IT|ADD|EXTRA)\s+(?:PLEASE\s+)?'
        r'(?:[A-Z]{1,4}[.,]\d+[a-z]\s+)?',
        '', name, flags=re.IGNORECASE
    )
    for pat, rep in OCR_NAME_FIXES:
        name = re.sub(pat, rep, name)
    return name.strip()


def is_valid_name(name: str) -> bool:
    if not name or len(name.strip()) < 2:
        return False
    if not re.search(r'[A-Za-zА-ЯÀ-ÿа-я]', name):
        return False
    if re.match(r'^[\W\d]+$', name):
        return False
    if re.search(r'(.)\1{4,}', name):
        return False
    return True


# ═══════════════════════════════════════════════════════════════
#  ПОИСК ИТОГОВОЙ СУММЫ
# ═══════════════════════════════════════════════════════════════

_TOTAL_KW = re.compile(
    r'(?i)\b(amt\s+due|amount\s+due|balance\s+due|total\s+due'
    r'|grand\s+total|totale?|totl)\b'
    r'|\btota\s*[\]\|l;:"\'`]'
)
_SUBTOTAL_KW = re.compile(
    r'(?i)\b(sub[\s-]?total|subtotal|subtctal|subtota|subioia|sbt[l]?'
    r'|txtl)\b'
)
_MIN_TOTAL = 2.50


def find_total(lines: List[str]) -> float:
    reversed_enum = list(enumerate(lines))[::-1]

    for kw_re in [_TOTAL_KW, _SUBTOTAL_KW]:
        for idx, line in reversed_enum:
            if not kw_re.search(line):
                continue
            p = extract_price_spaced(line)
            if p and p >= _MIN_TOTAL:
                return p

            found_part1 = None
            for offset in range(1, 6):
                if idx + offset >= len(lines):
                    break
                nxt = lines[idx + offset]

                if SKIP_RE.search(nxt) and not re.search(r'\d', nxt):
                    continue

                p = extract_price_spaced(nxt)
                if p:
                    if p >= _MIN_TOTAL:
                        if p == int(p) and idx + offset + 1 < len(lines):
                            part2 = re.sub(r'[^\d]', '', lines[idx + offset + 1])
                            if re.match(r'^\d{2}$', part2):
                                combined = _parse_float(f"{int(p)}.{part2}")
                                if combined and combined >= _MIN_TOTAL:
                                    return combined
                        return p
                    continue

                part1 = re.sub(r'[^\d]', '', _normalize_price_str(nxt))
                if re.match(r'^\d{1,4}$', part1) and part1:
                    found_part1 = part1
                    if idx + offset + 1 < len(lines):
                        part2 = re.sub(r'[^\d]', '', lines[idx + offset + 1])
                        if re.match(r'^\d{2}$', part2):
                            combined = _parse_float(f"{found_part1}.{part2}")
                            if combined and combined >= _MIN_TOTAL:
                                return combined

            if found_part1:
                val = _parse_float(found_part1)
                if val and val >= _MIN_TOTAL:
                    return val

    candidates = []
    for line in lines:
        p = extract_price_from_end(line)
        if p and p >= _MIN_TOTAL:
            candidates.append(p)
    return candidates[-1] if candidates else 0.0


# ═══════════════════════════════════════════════════════════════
#  ОСНОВНОЙ ПАРСЕР
# ═══════════════════════════════════════════════════════════════

def _should_skip(line: str) -> bool:
    return (SKIP_RE.search(line) is not None
            or is_price_only_line(line)
            or PHONE_ONLY_RE.match(line) is not None
            or DIGITS_ONLY_RE.match(line) is not None
            or DATETIME_RE.search(line) is not None)


def parse_receipt_text(text: str) -> Tuple[List[Dict], float]:
    items: List[Dict] = []
    raw_lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in raw_lines if len(ln) >= 2]

    total = find_total(lines)

    i = 0
    while i < len(lines):
        line = lines[i]

        if _should_skip(line) or SIZE_MODIFIER_RE.match(line):
            i += 1
            continue

        qty = 1
        working_line = line
        qty_m = re.match(r'^(\d{1,3})\s+([A-Za-zА-ЯÀ-ÿа-я].*)$', line)
        if qty_m:
            potential = int(qty_m.group(1))
            if 1 <= potential <= 99:
                qty = potential
                working_line = qty_m.group(2)

        line_price: Optional[float] = extract_price_from_end(working_line)
        advance = 0

        if line_price is None and i + 1 < len(lines):
            nxt1 = lines[i + 1]

            # Случай 1: NAME / PRICE
            if is_price_only_line(nxt1):
                candidate = extract_price_from_end(nxt1)
                if candidate is not None:
                    line_price = candidate
                    advance = 1

            # Случай 2: NAME / SIZE_OR_MODIFIER / PRICE
            elif SIZE_MODIFIER_RE.match(nxt1) and i + 2 < len(lines):
                nxt2 = lines[i + 2]
                if is_price_only_line(nxt2):
                    candidate = extract_price_from_end(nxt2)
                    if candidate is not None:
                        line_price = candidate
                        advance = 2

            # Случай 3: NAME1 / NAME2 / PRICE (двухстрочное имя)
            elif (not _should_skip(nxt1)
                  and SIZE_MODIFIER_RE.match(nxt1) is None
                  and is_valid_name(nxt1)
                  and i + 2 < len(lines)):
                nxt2 = lines[i + 2]
                if is_price_only_line(nxt2):
                    candidate = extract_price_from_end(nxt2)
                    if candidate is not None:
                        working_line = working_line + ' ' + nxt1
                        line_price = candidate
                        advance = 2

        if line_price is None or not (0.25 < line_price < 500):
            i += 1
            continue

        name = re.sub(r'\s*[Ss\$38]?\s*\d[\d\s]*[,.][\d\s]{1,3}\s*[#]?\s*$',
                      '', working_line).strip()
        if not name:
            name = working_line
        name = clean_name(name)

        if not is_valid_name(name):
            i += 1 + advance
            continue

        unit_price = round(line_price / qty, 2) if qty > 1 else round(line_price, 2)
        items.append({
            "name": name,
            "qty": qty,
            "unit_price": unit_price,
            "price": round(line_price, 2),
        })

        i += 1 + advance

    sum_items = round(sum(it["price"] for it in items), 2)
    if total <= 0:
        total = sum_items
    elif sum_items > 0 and (total > sum_items * 5 or total < sum_items * 0.1):
        total = sum_items

    return items, round(total, 2)


def save_parsed_data(items: List[Dict], total: float, txt_path) -> str:
    txt_path = Path(txt_path)
    Path(PARSED_DIR).mkdir(parents=True, exist_ok=True)
    json_path = Path(PARSED_DIR) / f"{txt_path.stem}.json"
    data = {"items": items, "total": round(total, 2), "source_txt": str(txt_path)}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(json_path)