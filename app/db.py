"""Работа с базой данных PostgreSQL."""
import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

DSN = os.getenv("DATABASE_URL", "postgresql://tester:tester@localhost:5432/tester")

# Стартовые сценарии, чтобы сразу было что запускать
SEED_SCENARIOS = [
    {
        "name": "Открытие главной страницы",
        "description": "Сайт открывается и страница отображается",
        "steps": [
            {"action": "open", "target": "", "value": "https://shop.3-test.mts.by"},
            {"action": "assert_visible", "target": "body", "value": ""},
            {"action": "assert_url", "target": "", "value": "mts.by"},
        ],
    },
    {
        "name": "Демо: тест с ошибкой",
        "description": "Специально падает, чтобы показать, как выглядит отчёт об ошибке",
        "steps": [
            {"action": "open", "target": "", "value": "https://shop.3-test.mts.by"},
            {"action": "assert_visible", "target": "#element-which-does-not-exist", "value": ""},
            {"action": "assert_title", "target": "", "value": "этот шаг будет пропущен"},
        ],
    },
]


@contextmanager
def get_conn():
    """Соединение с БД: по выходу из блока with изменения сохраняются, соединение закрывается."""
    with psycopg.connect(DSN, row_factory=dict_row) as conn:
        yield conn


def init_db() -> None:
    """Создаёт таблицы и стартовые данные при запуске приложения."""
    schema = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    with get_conn() as conn:
        conn.execute(schema)
        # Если сервер выключили во время теста, запуск навсегда остался бы «выполняется»
        conn.execute(
            "UPDATE runs SET status = 'failed', finished_at = now() WHERE status = 'running'"
        )
        count = conn.execute("SELECT count(*) AS n FROM scenarios").fetchone()["n"]
        if count == 0:
            for sc in SEED_SCENARIOS:
                conn.execute(
                    "INSERT INTO scenarios (name, description, steps) VALUES (%s, %s, %s)",
                    (sc["name"], sc["description"], Jsonb(sc["steps"])),
                )
