# src/mock_data.py

receipt_transaction = {
    # Текстовое поле (для поиска совпадений: магазин, ИНН, адрес)
    "store_name": "Кофейня Take&Go",
    
    # Числовое поле (для проверки порогов: сумма чека)
    "total_amount": 2500.00,
    
    # Список позиций в чеке
    "items": [
        {
            "product_name": "Капучино",
            "price": 700.00,
            "quantity": 1
        },
        {
            "product_name": "Сэндвич",
            "price": 900.00,
            "quantity": 1
        },
        {
            "product_name": "Десерт",
            "price": 900.00,
            "quantity": 1
        }
    ],
    
    # Дата и время операции
    "purchase_datetime": "2026-02-11 14:32:00",
    
    # Булево поле (прошёл ли чек валидацию)
    "is_valid_receipt": True,
    
    # Данные для проверки через QR
    "qr_data": "t=20260211T1432&s=2500.00&fn=1234567890&i=11111",
    
    # Налоги
    "vat_amount": 300.00,
    
    # Способ оплаты
    "payment_method": "card"
}
