from contextlib import asynccontextmanager
from datetime import date
from enum import Enum
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, model_validator

from . import db, logic

BASE = Path(__file__).parent


class SortBy(str, Enum):
    id = "id"
    title = "title"
    tag = "tag"
    due_date = "due_date"
    done = "done"


class Order(str, Enum):
    asc = "asc"
    desc = "desc"


class Frequency(str, Enum):
    once = "once"
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"


class TemplateIn(BaseModel):
    title: str
    frequency: Frequency
    tag: str = ""
    start_date: date
    end_date: date | None = None

    @model_validator(mode="after")
    def check_dates(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.pool.open(wait=True)
    db.init_schema()
    db.seed()
    logic.sync()
    yield
    db.pool.close()


app = FastAPI(title="Task API", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE / "static" / "index.html")


@app.get("/health")
def health():
    try:
        db.ping()
    except Exception:
        raise HTTPException(503, "Database unreachable")
    return {"status": "ok"}


@app.get("/tasks")
def get_tasks(
    tag: str | None = None,
    done: bool | None = None,
    title: str | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    sort_by: SortBy = SortBy.due_date,
    order: Order = Order.asc,
):
    return logic.list_tasks(tag, done, title, due_from, due_to,
                            sort_by.value, order.value)


@app.patch("/tasks/{task_id}/done")
def done(task_id: int):
    try:
        return logic.mark_done(task_id)
    except KeyError:
        raise HTTPException(404, "Task not found")


@app.post("/sync")
def sync():
    return {"created": logic.sync()}


@app.get("/templates")
def get_templates():
    return logic.list_templates()


@app.post("/templates", status_code=201)
def create_template(body: TemplateIn):
    return logic.add_template(body.title, body.frequency.value, body.tag,
                              body.start_date, body.end_date)
