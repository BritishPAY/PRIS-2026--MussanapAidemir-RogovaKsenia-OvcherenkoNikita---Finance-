import json
import os

# Автоматическое определение пути к файлу
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(BASE_DIR, 'data', 'raw', 'rules.json')


def load_rules():
    with open(RULES_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_rules(receipt):
    """
    Принимает словарь чека (receipt), возвращает строковый вердикт.
    """
    rules = load_rules()

    # --- 1. HARD FILTERS (Критические проверки) ---
    # Чек должен быть верифицирован
    if rules["critical_rules"]["must_be_verified"] and not receipt["is_valid_receipt"]:
        return "⛔ Критическая ошибка: Чек не прошёл верификацию"

    # --- 2. БИЗНЕС-ЛОГИКА ---

    # Проверка категорий товаров
    for tag in receipt["tags_list"]:
        if tag in rules["lists"]["blacklist"]:
            return f"⚠️ Предупреждение: В чеке найден запрещённый товар ({tag})"

    # Проверка: есть ли хотя бы одна разрешённая категория
    allowed_found = any(
        tag in rules["lists"]["whitelist"]
        for tag in receipt["tags_list"]
    )

    if not allowed_found:
        return "❌ Отказ: В чеке нет допустимых категорий товаров"

    # --- 3. УСПЕХ ---
    return f"✅ Успех: Чек соответствует сценарию '{rules['scenario_name']}'"
