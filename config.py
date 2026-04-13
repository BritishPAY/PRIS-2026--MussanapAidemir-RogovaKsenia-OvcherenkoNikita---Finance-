import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data", "receipts")
EXTRACTED_DIR = os.path.join(BASE_DIR, "processed", "extracted_text")
PARSED_DIR = os.path.join(BASE_DIR, "processed", "parsed_data")
STATS_DIR = os.path.join(BASE_DIR, "processed", "stats")

# Твои чеки
RECEIPT_PREFIX = ""
RECEIPT_START = 1000
RECEIPT_END = 1199
RECEIPT_SUFFIX = "-receipt.jpg"

CATEGORIES = [
    "fruits", "vegetables", "dairy", "meat", "fish",
    "bakery", "beverages", "snacks", "sweets", "household",
    "personal_care", "restaurant_food", "alcohol", "tobacco",
    "other"
]

LLM_MODEL = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"