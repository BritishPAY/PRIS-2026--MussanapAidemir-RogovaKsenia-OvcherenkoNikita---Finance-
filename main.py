import sys
import os

# Добавляем текущую директорию в путь, чтобы пакеты src и ui были видны
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ui.app import app

if __name__ == "__main__":
    print("=" * 50)
    print("  FINANCE PROJECT: MAIN ENTRY POINT")
    print("  Запуск Flask-сервера из корня...")
    print("  Открыть: http://localhost:5000")
    print("=" * 50)

    # Запускаем приложение, импортированное из папки ui
    app.run(debug=True, port=5000)