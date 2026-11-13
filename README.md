# Автоматизированная система тестирования сайтов

Python 3.14 · FastAPI · Selenium 4 · PostgreSQL 16.6 · Vue 3

## Запуск
1. Нужны: Python 3.14, Docker, браузер Google Chrome.
2. База данных:  `docker compose up -d`
3. Зависимости:
   ```
   python -m venv .venv
   .venv\Scripts\activate        (Linux/macOS: source .venv/bin/activate)
   pip install -r requirements.txt
   ```
4. Сервер:  `uvicorn app.main:app --reload`
5. Открыть в браузере: http://localhost:8000

Таблицы и два демо-сценария создаются автоматически при первом запуске.

## Настройки (переменные окружения, необязательно)
- `DATABASE_URL` — адрес БД (по умолчанию `postgresql://tester:tester@localhost:5432/tester`)
- `HEADLESS=0` — показывать окно браузера во время теста
- `STEP_TIMEOUT=10` — сколько секунд ждать элемент

## Структура
- `app/schema.sql` — таблицы БД
- `app/db.py` — подключение к БД, стартовые данные
- `app/runner.py` — выполнение шагов через Selenium
- `app/main.py` — API (сценарии, запуск, отчёты, CSV)
- `static/index.html` — интерфейс на Vue
