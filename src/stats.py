import json
from pathlib import Path
from collections import defaultdict
from config import PARSED_DIR, STATS_DIR

def compute_overall_statistics():
    Path(STATS_DIR).mkdir(parents=True, exist_ok=True)
    total_by_category = defaultdict(float)
    grand_total = 0.0
    receipt_count = 0

    for path in Path(PARSED_DIR).glob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            items = data.get("categorized_items", [])
            if not items:
                items = data.get("items", [])  # fallback

            for item in items:
                cat = item.get("category", "other")
                price = item.get("price", 0)
                total_by_category[cat] += price
                grand_total += price

            receipt_count += 1

        except Exception as e:
            print(f"Ошибка в {path.name}: {e}")

    stats = {
        "receipt_count": receipt_count,
        "grand_total": round(grand_total, 2),
        "by_category": {
            k: round(v, 2)
            for k, v in sorted(total_by_category.items(), key=lambda x: x[1], reverse=True)
        }
    }

    out_path = Path(STATS_DIR) / "overall_statistics.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    return stats, out_path