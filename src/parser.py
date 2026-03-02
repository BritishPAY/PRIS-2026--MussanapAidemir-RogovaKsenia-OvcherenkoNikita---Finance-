import re
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from config import PARSED_DIR


# ─────────────────────────────────────────────
#  Вспомогательные функции
# ─────────────────────────────────────────────

def extract_price_from_end(line: str) -> Optional[float]:
    """
    Ищет цену в формате XX.XX (или XX,XX) строго в конце строки.
    Возвращает float или None.
    """
    m = re.search(r'(\d+)[.,](\d{2})\s*$', line)
    if m:
        try:
            return float(f"{m.group(1)}.{m.group(2)}")
        except ValueError:
            return None
    return None


def extract_price_anywhere(s: str) -> Optional[float]:
    """
    Безопасное извлечение цены из строки (для fallback).
    """
    if not s:
        return None
    cleaned = re.sub(r'[^0-9.,]', '', s.strip()).replace(',', '.')
    m = re.search(r'(\d+\.\d{2})$', cleaned)
    if not m:
        m = re.search(r'(\d+(?:\.\d{1,2})?)$', cleaned)
    if not m:
        return None
    try:
        val = float(m.group(1))
        return val if val > 0 else None
    except ValueError:
        return None


# ─────────────────────────────────────────────
#  Паттерны для фильтрации
# ─────────────────────────────────────────────

# Служебные строки, которые не являются товарами
SKIP_RE = re.compile(
    r'(?i)\b('
    r'cashier|server|clerk|station|terminal|'
    r'order\s*[#№]?|check\s*[#№]|table|guest|'
    r'dine\s+in|take[\s-]?out|'
    r'thank\s+you|come\s+again|pleasure|dining|'
    r'visa|mastercard|amex|discover|card\s*[#№]|acct|approval|auth|'
    r'sub[\s-]?total|subtotal|tax|total|'
    r'gratuity|suggested\s+gratuity|'
    r'cash\s+tender|cash\s+pay|balance|amount\s+due|'
    r'drive[\s-]?thru|mobile|download\s+the|survey|'
    r'for\s+a\s+chance|see\s+back|receipt'
    r')\b'
    r'|={3,}|-{3,}|[*]{3,}|#{3,}'           # разделители
    r'|\bXX{3,}\b'                            # маскированные номера карт
)

# Строки, состоящие только из цены (без названия товара)
PRICE_ONLY_RE = re.compile(r'^\s*\$?\s*\d+[.,]\d{2}\s*$')

# Телефонные номера — пропускаем строки, которые СОСТОЯТ только из номера
PHONE_ONLY_RE = re.compile(r'^\s*\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\s*$')

# Строки только из цифр (коды заказов, номера столиков и т.п.)
DIGITS_ONLY_RE = re.compile(r'^\s*[\d\s]{1,8}\s*$')

# Дата/время
DATETIME_RE = re.compile(
    r'^\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}'   # дата
    r'|\d{1,2}:\d{2}(:\d{2})?\s*(AM|PM)?$',      # время
    re.IGNORECASE
)

# OCR-исправления (паттерн → замена)
OCR_FIXES = [
    (r'(?i)Co\s*f\s*fee',     'Coffee'),
    (r'(?i)Coffe{2,}',        'Coffee'),
    (r'(?i)Cok\s*e\b',        'Coke'),
    (r'(?i)Lunc\s*h\b',       'Lunch'),
    (r'(?i)Chicke\s*n\b',     'Chicken'),
    (r'(?i)Burge\s*r\b',      'Burger'),
    (r'(?i)Parmes\s*an\b',    'Parmesan'),
    (r'(?i)Sirlo\s*in\b',     'Sirloin'),
]


def clean_name(name: str) -> str:
    name = re.sub(r'\s{2,}', ' ', name).strip()
    for pattern, replacement in OCR_FIXES:
        name = re.sub(pattern, replacement, name)
    return name


def is_valid_name(name: str) -> bool:
    """Название должно содержать хотя бы одну букву и не быть мусором."""
    if not name or len(name.strip()) < 2:
        return False
    if not re.search(r'[A-Za-zА-Яа-я]', name):
        return False
    # Отклоняем строки вида ".90", "':42", "#38" и т.п.
    if re.match(r'^[\W\d]+$', name):
        return False
    return True


# ─────────────────────────────────────────────
#  Поиск итоговой суммы
# ─────────────────────────────────────────────

def find_total(lines: List[str]) -> float:
    """
    Приоритеты:
    1. Строка "TOTAL" (не SUB TOTAL) + цена на той же или следующей строке.
       Особый случай: цена разбита OCR на две строки ("69\n25" → 69.25).
    2. Строка SUB TOTAL + цена.
    3. Последняя разумная цена в чеке.
    """
    # Стратегия 1 и 2
    for priority, keyword_re in enumerate([
        re.compile(r'(?i)(?<!\w)total(?!\s*(not|:?\s*\d+\s*$))', re.IGNORECASE),
        re.compile(r'(?i)\b(sub[\s-]?total|subtotal)\b', re.IGNORECASE),
    ]):
        for idx, line in enumerate(lines):
            if not keyword_re.search(line):
                continue

            # Цена в той же строке
            p = extract_price_from_end(line)
            if p and 0.5 < p < 50_000:
                return p

            # Цена в следующей строке
            if idx + 1 < len(lines):
                p = extract_price_from_end(lines[idx + 1])
                if p and 0.5 < p < 50_000:
                    return p

                # OCR-сплит: "69\n25" → 69.25
                part1 = lines[idx + 1].strip()
                if re.match(r'^\d+$', part1) and idx + 2 < len(lines):
                    part2 = lines[idx + 2].strip()
                    if re.match(r'^\d+$', part2):
                        try:
                            combined = float(f"{part1}.{part2}")
                            if 0.5 < combined < 50_000:
                                return combined
                        except ValueError:
                            pass

    # Стратегия 3: последняя разумная цена
    candidates = []
    for line in lines:
        p = extract_price_from_end(line)
        if p and 0.5 < p < 50_000:
            candidates.append(p)
    if candidates:
        return candidates[-1]

    return 0.0


# ─────────────────────────────────────────────
#  Основной парсер
# ─────────────────────────────────────────────

def parse_receipt_text(text: str) -> Tuple[List[Dict], float]:
    items: List[Dict] = []
    raw_lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in raw_lines if len(ln) >= 2]

    total = find_total(lines)

    i = 0
    while i < len(lines):
        line = lines[i]

        # ── Фильтры пропуска ──────────────────────────────────────────────
        if (SKIP_RE.search(line)
                or PRICE_ONLY_RE.match(line)
                or PHONE_ONLY_RE.match(line)
                or DIGITS_ONLY_RE.match(line)
                or DATETIME_RE.search(line)):
            i += 1
            continue

        # ── Попытка извлечь количество ───────────────────────────────────
        # Паттерн: цифра(ы) в начале, затем ОБЯЗАТЕЛЬНО буква
        qty = 1
        working_line = line
        qty_m = re.match(r'^(\d{1,3})\s+([A-Za-zА-Яа-я].*)$', line)
        if qty_m:
            potential_qty = int(qty_m.group(1))
            if 1 <= potential_qty <= 99:
                qty = potential_qty
                working_line = qty_m.group(2)

        # ── Цена: сначала из текущей строки ──────────────────────────────
        line_price = extract_price_from_end(working_line)

        # Если нет — проверяем следующую строку (OCR разнёс название и цену)
        if line_price is None and i + 1 < len(lines):
            nxt = lines[i + 1]
            if PRICE_ONLY_RE.match(nxt):
                line_price = extract_price_from_end(nxt)
                if line_price is not None:
                    i += 1   # поглощаем строку с ценой

        if line_price is None:
            i += 1
            continue

        # Слишком дешёвое или нереально дорогое — пропускаем
        if not (0.25 < line_price < 500):
            i += 1
            continue

        # ── Формируем название ───────────────────────────────────────────
        # Убираем цену с конца строки, чтобы получить чистое название
        name = re.sub(r'\s*\$?\s*\d+[.,]\d{2}\s*$', '', working_line).strip()
        if not name:
            name = working_line
        name = clean_name(name)

        if not is_valid_name(name):
            i += 1
            continue

        # ── Добавляем позицию ────────────────────────────────────────────
        unit_price = round(line_price / qty, 2) if qty > 1 else round(line_price, 2)
        items.append({
            "name": name,
            "qty": qty,
            "unit_price": unit_price,
            "price": round(line_price, 2),
        })

        i += 1

    # Страховка: если total нет или явно неправдоподобен — считаем из позиций.
    # Допускаем расхождение до 25% (налог, обслуживание); если больше — OCR-ошибка.
    sum_items = round(sum(it["price"] for it in items), 2)
    if total <= 0:
        total = sum_items
    elif sum_items > 0 and abs(total - sum_items) / sum_items > 0.25:
        total = sum_items

    return items, round(total, 2)


# ─────────────────────────────────────────────
#  Сохранение результата
# ─────────────────────────────────────────────

def save_parsed_data(items: List[Dict], total: float, txt_path) -> str:
    txt_path = Path(txt_path)
    Path(PARSED_DIR).mkdir(parents=True, exist_ok=True)
    json_path = Path(PARSED_DIR) / f"{txt_path.stem}.json"

    data = {
        "items": items,
        "total": round(total, 2),
        "source_txt": str(txt_path),
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return str(json_path)