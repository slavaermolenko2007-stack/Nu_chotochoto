"""Веб-сервер: API для интерфейса + раздача страницы."""
import csv
import io
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, field_validator

from . import db
from .runner import ACTIONS, run_scenario


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Автотесты сайта", lifespan=lifespan)


# ---------- Модели данных (проверяют, что пришло из интерфейса) ----------
class Step(BaseModel):
    action: str
    target: str = ""
    value: str = ""

    @field_validator("action")
    @classmethod
    def action_must_exist(cls, v: str) -> str:
        if v not in ACTIONS:
            raise ValueError("Неизвестное действие")
        return v


class ScenarioIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    steps: list[Step] = Field(min_length=1)


# ---------- Сценарии ----------
@app.get("/api/actions")
def list_actions():
    return ACTIONS


@app.get("/api/scenarios")
def list_scenarios():
    with db.get_conn() as conn:
        return conn.execute("SELECT * FROM scenarios ORDER BY id").fetchall()


@app.post("/api/scenarios", status_code=201)
def create_scenario(data: ScenarioIn):
    steps = Jsonb([s.model_dump() for s in data.steps])
    with db.get_conn() as conn:
        return conn.execute(
            "INSERT INTO scenarios (name, description, steps) VALUES (%s, %s, %s) RETURNING *",
            (data.name, data.description, steps),
        ).fetchone()


@app.put("/api/scenarios/{scenario_id}")
def update_scenario(scenario_id: int, data: ScenarioIn):
    steps = Jsonb([s.model_dump() for s in data.steps])
    with db.get_conn() as conn:
        row = conn.execute(
            """UPDATE scenarios SET name = %s, description = %s, steps = %s, updated_at = now()
               WHERE id = %s RETURNING *""",
            (data.name, data.description, steps, scenario_id),
        ).fetchone()
    if row is None:
        raise HTTPException(404, "Сценарий не найден")
    return row


@app.delete("/api/scenarios/{scenario_id}", status_code=204)
def delete_scenario(scenario_id: int):
    with db.get_conn() as conn:
        row = conn.execute(
            "DELETE FROM scenarios WHERE id = %s RETURNING id", (scenario_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(404, "Сценарий не найден")


# ---------- Запуски и отчёты ----------
@app.post("/api/scenarios/{scenario_id}/run", status_code=202)
def start_run(scenario_id: int, background: BackgroundTasks):
    with db.get_conn() as conn:
        scenario = conn.execute(
            "SELECT * FROM scenarios WHERE id = %s", (scenario_id,)
        ).fetchone()
        if scenario is None:
            raise HTTPException(404, "Сценарий не найден")
        run = conn.execute(
            "INSERT INTO runs (scenario_id, scenario_name) VALUES (%s, %s) RETURNING id",
            (scenario_id, scenario["name"]),
        ).fetchone()
    # Тест идёт в фоне, чтобы страница не «зависала» на время выполнения
    background.add_task(run_scenario, run["id"], scenario["steps"])
    return {"run_id": run["id"]}


@app.get("/api/runs")
def list_runs():
    with db.get_conn() as conn:
        return conn.execute(
            """SELECT r.*,
                      count(s.id) AS total,
                      count(s.id) FILTER (WHERE s.status = 'passed') AS passed
               FROM runs r LEFT JOIN run_steps s ON s.run_id = r.id
               GROUP BY r.id ORDER BY r.id DESC LIMIT 100"""
        ).fetchall()


def _load_run(conn, run_id: int) -> dict:
    run = conn.execute("SELECT * FROM runs WHERE id = %s", (run_id,)).fetchone()
    if run is None:
        raise HTTPException(404, "Запуск не найден")
    run["steps"] = conn.execute(
        "SELECT * FROM run_steps WHERE run_id = %s ORDER BY position", (run_id,)
    ).fetchall()
    return run


@app.get("/api/runs/{run_id}")
def get_run(run_id: int):
    with db.get_conn() as conn:
        return _load_run(conn, run_id)


@app.get("/api/runs/{run_id}/export.csv")
def export_run(run_id: int):
    with db.get_conn() as conn:
        run = _load_run(conn, run_id)
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["№", "Действие", "Селектор", "Значение", "Статус", "Сообщение", "мс"])
    for s in run["steps"]:
        writer.writerow([s["position"], ACTIONS[s["action"]]["label"], s["target"],
                         s["value"], s["status"], s["message"], s["duration_ms"]])
    # BOM в начале, чтобы Excel правильно показал русские буквы
    return Response(
        content="\ufeff" + out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="run_{run_id}.csv"'},
    )


@app.delete("/api/runs/{run_id}", status_code=204)
def delete_run(run_id: int):
    with db.get_conn() as conn:
        conn.execute("DELETE FROM runs WHERE id = %s", (run_id,))


# Страница интерфейса. Подключаем последней, чтобы не перекрыть /api
app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "static", html=True))
