import easyocr
import os
from pathlib import Path
from config import EXTRACTED_DIR


def extract_text_from_receipt(image_path: str) -> tuple[str, str]:
    reader = easyocr.Reader(['en'], gpu=False)

    result = reader.readtext(image_path, detail=0, paragraph=False)
    text = "\n".join(result).strip()

    Path(EXTRACTED_DIR).mkdir(parents=True, exist_ok=True)
    base_name = Path(image_path).stem
    txt_path = os.path.join(EXTRACTED_DIR, f"{base_name}.txt")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)

    return text, txt_path