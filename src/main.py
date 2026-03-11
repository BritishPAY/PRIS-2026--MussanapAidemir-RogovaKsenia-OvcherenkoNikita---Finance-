from tqdm import tqdm
import os
from config import (
    DATA_DIR, RECEIPT_START, RECEIPT_END, RECEIPT_SUFFIX
)
from ocr import extract_text_from_receipt
from parser import parse_receipt_text, save_parsed_data
from categorizer import categorize_items, update_json_with_categories
from stats import compute_overall_statistics


def main():
    processed = 0
    errors = 0

    for num in tqdm(range(RECEIPT_START, RECEIPT_END + 1)):
        filename = f"{num}{RECEIPT_SUFFIX}"
        image_path = os.path.join(DATA_DIR, filename)

        if not os.path.exists(image_path):
            continue

        try:
            # 1. OCR
            text, txt_path = extract_text_from_receipt(image_path)

            # 2. Парсинг
            items, total = parse_receipt_text(text)
            json_path = save_parsed_data(items, total, txt_path)

            # 3. Категоризация
            categorized = categorize_items(items)
            update_json_with_categories(json_path, categorized)

            processed += 1

        except Exception as e:
            print(f"Ошибка {filename}: {e}")
            errors += 1

    print(f"\nОбработано успешно: {processed} чеков")
    if errors:
        print(f"С ошибками: {errors}")

    print("\nСчитаем итоговую статистику...")
    stats, path = compute_overall_statistics()
    print(f"Сохранено → {path}")
    print(stats)


if __name__ == "__main__":
    main()