from transformers import pipeline
import json
from pathlib import Path
from config import CATEGORIES, LLM_MODEL, PARSED_DIR

def categorize_items(items: list[dict]) -> list[dict]:
    if not items:
        return []

    classifier = pipeline(
        "zero-shot-classification",
        model=LLM_MODEL,
        device=-1,               # -1 = CPU
        batch_size=8
    )

    texts = [item["name"] for item in items]
    results = classifier(texts, candidate_labels=CATEGORIES, multi_label=False)

    categorized = []
    for item, res in zip(items, results):
        best_cat = res["labels"][0]
        categorized.append({
            **item,
            "category": best_cat,
            "category_score": round(res["scores"][0], 4)
        })

    return categorized


def update_json_with_categories(json_path: str, categorized: list):
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    data["categorized_items"] = categorized

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)