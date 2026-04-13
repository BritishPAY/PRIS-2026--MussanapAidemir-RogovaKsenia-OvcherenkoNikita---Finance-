"""
app.py  — Flask-сервер для Receipt Analytics Dashboard
Запуск:  python app.py
Открыть: http://localhost:5000
"""

import os, json, base64, hashlib
from pathlib import Path
from flask import Flask, render_template, request, jsonify

# ── Пытаемся импортировать парсер и категоризатор ──────────────────
try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from parser import parse_receipt_text
    from categorizer import categorize_items
    PARSER_AVAILABLE = True
except Exception as e:
    PARSER_AVAILABLE = False
    print(f"[WARN] parser/categorizer не найден: {e}")
    print("[WARN] Режим демо — данные будут смоделированы")

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

UPLOAD_DIR = Path(__file__).parent / "uploads_ui"
UPLOAD_DIR.mkdir(exist_ok=True)

CATEGORY_LABELS = {
    "meat":            "🥩 Мясо",
    "fish":            "🐟 Рыба и морепродукты",
    "vegetables":      "🥦 Овощи",
    "fruits":          "🍎 Фрукты",
    "dairy":           "🥛 Молочные продукты",
    "bakery":          "🥐 Выпечка",
    "beverages":       "☕ Напитки",
    "alcohol":         "🍷 Алкоголь",
    "snacks":          "🍿 Снеки",
    "sweets":          "🍰 Сладости",
    "restaurant_food": "🍽️ Блюда из ресторана",
    "household":       "🧹 Хозтовары",
    "personal_care":   "🧴 Личная гигиена",
    "tobacco":         "🚬 Табак",
    "other":           "📦 Прочее",
}

MANUAL_CATEGORIES = [
    ("groceries",   "🛒 Продукты питания"),
    ("taxi",        "🚕 Такси / Uber"),
    ("transport",   "🚌 Транспорт"),
    ("medical",     "💊 Медицина и здоровье"),
    ("leisure",     "🎭 Развлечения и отдых"),
    ("clothing",    "👗 Одежда и обувь"),
    ("beauty",      "💅 Красота / Косметика"),
    ("gym",         "🏋️ Фитнес / Спорт"),
    ("education",   "📚 Образование"),
    ("pets",        "🐾 Питомцы"),
    ("subscriptions","📱 Подписки (Netflix и др.)"),
    ("housing",     "🏠 Аренда / Коммуналка"),
    ("gifts",       "🎁 Подарки"),
    ("other_manual","📋 Прочие расходы"),
]


# ═══════════════════════════════════════════════════
#  API
# ═══════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html",
                           categories=CATEGORY_LABELS,
                           manual_cats=MANUAL_CATEGORIES,
                           parser_ok=PARSER_AVAILABLE)


@app.route("/api/upload", methods=["POST"])
def upload():
    """Принимает изображения/txt чеков, возвращает распознанные позиции."""
    files = request.files.getlist("receipts")
    if not files:
        return jsonify({"error": "Нет файлов"}), 400

    results = []
    for f in files:
        if not f.filename:
            continue
        ext = Path(f.filename).suffix.lower()
        content = f.read()
        fid = hashlib.md5(content).hexdigest()[:8]

        if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            # Сохраняем изображение, возвращаем base64 для превью
            img_path = UPLOAD_DIR / f"{fid}{ext}"
            img_path.write_bytes(content)
            b64 = base64.b64encode(content).decode()
            # OCR здесь не делаем — нужен pytesseract или внешний сервис
            # Парсим только если есть соответствующий .txt
            txt_path = UPLOAD_DIR / f"{fid}.txt"
            if txt_path.exists() and PARSER_AVAILABLE:
                items, total = parse_receipt_text(txt_path.read_text(errors="replace"))
                cat_items = categorize_items(items)
            else:
                items, total, cat_items = [], 0.0, []
            results.append({
                "id": fid,
                "name": f.filename,
                "type": "image",
                "preview": f"data:image/{ext.lstrip('.')};base64,{b64[:200]}...",
                "items": cat_items,
                "total": total,
                "status": "ok" if cat_items else "no_text",
            })

        elif ext == ".txt":
            txt = content.decode("utf-8", errors="replace")
            txt_path = UPLOAD_DIR / f"{fid}.txt"
            txt_path.write_text(txt, encoding="utf-8")
            if PARSER_AVAILABLE:
                items, total = parse_receipt_text(txt)
                cat_items = categorize_items(items)
            else:
                # Демо-данные
                cat_items = [{"name": "Demo Item", "qty": 1, "unit_price": 9.99,
                               "price": 9.99, "category": "restaurant_food",
                               "category_score": 1.0}]
                total = 9.99
            results.append({
                "id": fid,
                "name": f.filename,
                "type": "txt",
                "items": cat_items,
                "total": round(total, 2),
                "status": "ok" if cat_items else "empty",
            })
        else:
            results.append({"id": fid, "name": f.filename,
                            "type": "unknown", "status": "unsupported"})

    return jsonify({"receipts": results})


@app.route("/api/stats", methods=["POST"])
def stats():
    """
    Принимает:
      - receipts: [{items: [{category, price}], total}]
      - manual:   {taxi: 50, medical: 30, ...}
    Возвращает полную статистику.
    """
    data = request.get_json(force=True)
    receipts = data.get("receipts", [])
    manual = data.get("manual", {})

    # Агрегируем по категориям из чеков
    receipt_by_cat = {}
    receipt_total = 0.0
    item_count = 0

    for r in receipts:
        receipt_total += r.get("total", 0)
        for it in r.get("items", []):
            cat = it.get("category", "other")
            receipt_by_cat[cat] = receipt_by_cat.get(cat, 0) + it.get("price", 0)
            item_count += 1

    # Ручные расходы
    manual_total = sum(float(v) for v in manual.values() if v)
    manual_clean = {k: float(v) for k, v in manual.items() if v and float(v) > 0}

    # Продукты: если заполнено вручную — берём вручную, иначе из чеков
    groceries_from_receipts = sum(
        receipt_by_cat.get(c, 0) for c in
        ["meat", "fish", "vegetables", "fruits", "dairy", "bakery",
         "beverages", "snacks", "sweets", "restaurant_food", "other"]
    )

    grand_total = receipt_total + manual_total

    return jsonify({
        "receipt_total": round(receipt_total, 2),
        "manual_total": round(manual_total, 2),
        "grand_total": round(grand_total, 2),
        "item_count": item_count,
        "receipt_count": len(receipts),
        "receipt_by_category": {k: round(v, 2) for k, v in receipt_by_cat.items()},
        "manual": manual_clean,
        "groceries_from_receipts": round(groceries_from_receipts, 2),
    })


if __name__ == "__main__":
    print("=" * 50)
    print("  Receipt Analytics Dashboard")
    print(f"  Парсер: {'✓ подключён' if PARSER_AVAILABLE else '✗ демо-режим'}")
    print("  Открыть:  http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
