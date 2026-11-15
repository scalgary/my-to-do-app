"""Task rules. Every function runs in one transaction."""
from calendar import monthrange
from datetime import date, timedelta

from . import db

SORT_COLUMNS = {
    "id": "id",
    "title": "lower(title)",
    "tag": "lower(tag)",
    "due_date": "due_date",
    "done": "done",
}


def _clamp(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, monthrange(year, month)[1]))


def add_interval(d: date, freq: str, anchor_day: int) -> date | None:
    """Next occurrence after d. None for 'once'."""
    if freq == "daily":
        return d + timedelta(days=1)
    if freq == "weekly":
        return d + timedelta(days=7)
    if freq == "monthly":
        year = d.year + d.month // 12
        month = d.month % 12 + 1
        return _clamp(year, month, anchor_day)
    if freq == "yearly":
        return _clamp(d.year + 1, d.month, anchor_day)
    return None


def _sync(conn) -> int:
    """Create a task_used row for each unsynced task_db row."""
    todo = conn.execute(
        "SELECT id, title, tag, start_date, end_date, next_date "
        "FROM task_db WHERE NOT synced ORDER BY id FOR UPDATE"
    ).fetchall()
    created = 0
    for t in todo:
        due = t["next_date"] or t["start_date"]
        if t["end_date"] is None or due <= t["end_date"]:
            conn.execute(
                "INSERT INTO task_used (task_id, title, tag, due_date) "
                "VALUES (%s, %s, %s, %s)",
                (t["id"], t["title"], t["tag"], due))
            created += 1
        conn.execute("UPDATE task_db SET synced = TRUE WHERE id = %s", (t["id"],))
    return created


def sync() -> int:
    with db.pool.connection() as conn:
        return _sync(conn)


def mark_done(used_id: int) -> dict:
    """Mark done, compute next_date in task_db, then sync. One transaction."""
    with db.pool.connection() as conn:
        row = conn.execute(
            "SELECT u.id, u.task_id, u.title, u.tag, u.due_date, u.done, "
            "       t.frequency, t.start_date, t.end_date "
            "FROM task_used u JOIN task_db t ON t.id = u.task_id "
            "WHERE u.id = %s FOR UPDATE OF u, t", (used_id,)
        ).fetchone()
        if row is None:
            raise KeyError(used_id)
        if not row["done"]:
            conn.execute("UPDATE task_used SET done = TRUE WHERE id = %s", (used_id,))
            nxt = add_interval(row["due_date"], row["frequency"], row["start_date"].day)
            if nxt and (row["end_date"] is None or nxt <= row["end_date"]):
                conn.execute(
                    "UPDATE task_db SET next_date = %s, synced = FALSE WHERE id = %s",
                    (nxt, row["task_id"]))
            else:  # 'once', or the series is finished
                conn.execute(
                    "UPDATE task_db SET next_date = NULL WHERE id = %s", (row["task_id"],))
            _sync(conn)
        return {
            "id": row["id"], "task_id": row["task_id"], "title": row["title"],
            "tag": row["tag"], "due_date": row["due_date"], "done": True,
        }


def list_tasks(tag=None, done=None, title=None, due_from=None, due_to=None,
               sort_by="due_date", order="asc") -> list[dict]:
    where, params = [], []
    if tag:
        where.append("lower(tag) = lower(%s)")
        params.append(tag)
    if done is not None:
        where.append("done = %s")
        params.append(done)
    if title:
        where.append("title ILIKE %s")
        params.append(f"%{title}%")
    if due_from:
        where.append("due_date >= %s")
        params.append(due_from)
    if due_to:
        where.append("due_date <= %s")
        params.append(due_to)

    # Column and direction come from fixed whitelists, never from raw input.
    column = SORT_COLUMNS[sort_by]
    direction = "DESC" if order == "desc" else "ASC"
    sql = "SELECT id, task_id, title, tag, due_date, done FROM task_used"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {column} {direction}, id"

    with db.pool.connection() as conn:
        return conn.execute(sql, params).fetchall()


def list_templates() -> list[dict]:
    with db.pool.connection() as conn:
        return conn.execute("SELECT * FROM task_db ORDER BY id").fetchall()


def add_template(title, frequency, tag, start_date, end_date) -> dict:
    with db.pool.connection() as conn:
        row = conn.execute(
            "INSERT INTO task_db (title, frequency, tag, start_date, end_date) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING *",
            (title, frequency, tag, start_date, end_date)).fetchone()
        _sync(conn)
        return row
