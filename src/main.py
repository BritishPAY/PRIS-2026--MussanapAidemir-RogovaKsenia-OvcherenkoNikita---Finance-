import os
import json
from PIL import Image

import torch
from torch.utils.data import Dataset

from transformers import (
    LayoutLMv3Processor,
    LayoutLMv3ForTokenClassification,
    Trainer,
    TrainingArguments
)

# ========================
# 1. НАСТРОЙКИ
# =========================

DATASET_DIR = "C:/Users/Админ/PycharmProjects/PRIS-2026--MussanapAidemir-RogovaKsenia-OvcherenkoNikita---Finance-/SROIE2019/train"
MODEL_NAME = "microsoft/layoutlmv3-base"

EPOCHS = 1          # вместо 10
BATCH_SIZE = 1      # CPU реально так быстрее
MAX_LENGTH = 512    # вместо 512
LR = 2e-5

# =========================
# 2. МЕТКИ
# =========================

LABELS = [
    "O",
    "B-COMPANY", "I-COMPANY",
    "B-DATE", "I-DATE",
    "B-ADDRESS", "I-ADDRESS",
    "B-TOTAL", "I-TOTAL"
]

label2id = {l: i for i, l in enumerate(LABELS)}
id2label = {i: l for l, i in label2id.items()}

# =========================
# 3. ЧТЕНИЕ ФАЙЛОВ
# =========================

def read_box_file(path):
    words = []
    boxes = []

    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(",")

            if len(parts) < 9:
                continue

            x1, y1, x2, y2 = map(int, parts[1:5])
            text = parts[-1].strip()

            if text == "":
                continue

            words.append(text)
            boxes.append([x1, y1, x2, y2])

    return words, boxes


def read_entities(path):
    with open(path, encoding="utf-8") as f:
        content = f.read().strip()

    if content.startswith("text"):
        content = content[len("text"):].strip()

    return json.loads(content)

# =========================
# 4. НОРМАЛИЗАЦИЯ BBOX
# =========================

def normalize_bbox(box, width, height):
    x0, y0, x1, y1 = box

    x0 = int(1000 * x0 / width)
    x1 = int(1000 * x1 / width)
    y0 = int(1000 * y0 / height)
    y1 = int(1000 * y1 / height)

    def clamp(v):
        return max(0, min(1000, v))

    return [clamp(x0), clamp(y0), clamp(x1), clamp(y1)]

# =========================
# 5. НАЗНАЧЕНИЕ МЕТОК
# =========================

def assign_labels(words, entities):
    labels = ["O"] * len(words)

    for i, word in enumerate(words):
        w = word.lower()
        for key, value in entities.items():
            if value and w in value.lower():
                labels[i] = f"B-{key.upper()}"
                break

    return labels

# =========================
# 6. DATASET
# =========================

class ReceiptDataset(Dataset):
    def __init__(self, root_dir, processor):
        self.processor = processor
        self.samples = []

        box_dir = os.path.join(root_dir, "box")
        ent_dir = os.path.join(root_dir, "entities")
        img_dir = os.path.join(root_dir, "img")

        for file in os.listdir(box_dir):
            if not file.endswith(".txt"):
                continue

            base = file.replace(".txt", "")

            box_path = os.path.join(box_dir, file)
            ent_path = os.path.join(ent_dir, base + ".txt")
            img_path = os.path.join(img_dir, base + ".jpg")

            if not os.path.exists(ent_path) or not os.path.exists(img_path):
                continue

            words, boxes = read_box_file(box_path)
            entities = read_entities(ent_path)
            labels = assign_labels(words, entities)

            image = Image.open(img_path).convert("RGB")
            width, height = image.size

            boxes = [normalize_bbox(b, width, height) for b in boxes]

            self.samples.append((image, words, boxes, labels))

        print(f"Загружено чеков: {len(self.samples)}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        image, words, boxes, labels = self.samples[idx]

        encoding = self.processor(
            image,
            words,
            boxes=boxes,
            word_labels=[label2id[l] for l in labels],
            padding="max_length",
            truncation=True,
            max_length=MAX_LENGTH,
            return_tensors="pt"
        )

        return {k: v.squeeze(0) for k, v in encoding.items()}

# =========================
# 7. ЗАГРУЗКА МОДЕЛИ
# =========================

processor = LayoutLMv3Processor.from_pretrained(
    MODEL_NAME,
    apply_ocr=False
)

model = LayoutLMv3ForTokenClassification.from_pretrained(
    MODEL_NAME,
    num_labels=len(LABELS),
    id2label=id2label,
    label2id=label2id
)

# =========================
# 8. DATASET
# =========================

dataset = ReceiptDataset(DATASET_DIR, processor)

# =========================
# 9. ОБУЧЕНИЕ
# =========================

training_args = TrainingArguments(
    output_dir="./receipt_model",
    learning_rate=LR,
    per_device_train_batch_size=BATCH_SIZE,
    num_train_epochs=EPOCHS,
    logging_steps=50,
    save_strategy="epoch",
    eval_strategy="no",
    report_to="none"
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset
)

trainer.train()

# =========================
# 10. СОХРАНЕНИЕ
# =========================

model.save_pretrained("./receipt_model")
processor.save_pretrained("./receipt_model")

print("Обучение завершено ✔")

