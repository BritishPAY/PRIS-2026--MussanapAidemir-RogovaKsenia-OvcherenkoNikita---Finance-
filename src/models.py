from dataclasses import dataclass, field
from typing import List


@dataclass
class Receipt:
    """
    Строгая модель чека (транзакции).
    Заменяет неструктурированные словари.
    """
    store_name: str                 # Название магазина (уникальный id чека)
    tags_list: List[str]            # Категории товаров (coffee, food, dessert и т.д.)
    total_amount: float = 0.0       # Итоговая сумма чека
    is_valid_receipt: bool = False  # Прошёл ли чек верификацию (QR/ФН)

    def __str__(self):
        return f"{self.store_name} | {self.total_amount} | {', '.join(self.tags_list)}"
