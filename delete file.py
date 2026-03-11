import os
import shutil

# Укажи свои пути
paths = [
    r"C:\PycharmProjects\PRIS-2026--MussanapAidemir-RogovaKsenia-OvcherenkoNikita---Finance-\processed\extracted_text",
    r"C:\PycharmProjects\PRIS-2026--MussanapAidemir-RogovaKsenia-OvcherenkoNikita---Finance-\processed\parsed_data",
    r"C:\PycharmProjects\PRIS-2026--MussanapAidemir-RogovaKsenia-OvcherenkoNikita---Finance-\processed\stats"
]

def clear_folder(folder_path):
    if not os.path.exists(folder_path):
        print(f"Папка не существует: {folder_path}")
        return

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)  # удаляет файл или ссылку
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)  # удаляет папку и всё внутри
        except Exception as e:
            print(f"Ошибка при удалении {file_path}: {e}")

    print(f"Папка очищена: {folder_path}")


for path in paths:
    clear_folder(path)

print("Очистка завершена.")