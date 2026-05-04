"""FastAPI factory for the Plastiglom web app.

Routes:
  - GET  /                 : the current open prompt, editable until lock.
  - GET  /entry/{id}       : view an individual entry (read-only once locked).
  - POST /entry/{id}       : submit or update a response.
  - GET  /day/{iso-date}   : list entries for that day.

The route handlers are thin; persistence goes through `Archiver.on_submit`
which enforces `lock_at`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from plastiglom.apps.archiver.archiver import Archiver, SubmitRequest
from plastiglom.apps.web_app.lookup import (
    iter_entries_for_day,
    latest_open_entry,
    load_entry,
)
from plastiglom.apps.web_app.templates import build_env


def create_app(
    vault_path: Path,
    tz: ZoneInfo,
    *,
    now: Callable[[], datetime] | None = None,
) -> FastAPI:
    """Build the FastAPI app. `now` is injectable for tests."""
    app = FastAPI(title="Plastiglom", version="0.0.1")
    env = build_env()
    archiver = Archiver(vault_path)
    clock: Callable[[], datetime] = now or (lambda: datetime.now(tz=tz))

    def render(template: str, **ctx: object) -> HTMLResponse:
        ctx.setdefault("today", clock().date())
        return HTMLResponse(env.get_template(template).render(**ctx))

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        _ = request
        entry = latest_open_entry(vault_path, clock())
        return render("home.html", entry=entry, title="Plastiglom")

    @app.get("/entry/{entry_id}", response_class=HTMLResponse)
    def view_entry(entry_id: str) -> HTMLResponse:
        try:
            entry = load_entry(vault_path, entry_id)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        locked = entry.is_locked(clock())
        return render("entry.html", entry=entry, locked=locked, title=entry.title)

    @app.post("/entry/{entry_id}")
    def submit_entry(entry_id: str, response: str = Form(default="")) -> RedirectResponse:
        try:
            existing = load_entry(vault_path, entry_id)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        now_ = clock()
        if existing.is_locked(now_):
            raise HTTPException(status_code=409, detail="entry is locked")
        try:
            archiver.on_submit(
                SubmitRequest(
                    entry_id=existing.id,
                    exercise_id=existing.exercise_id,
                    fired_at=existing.timestamp_fired,
                    response=response,
                    submitted_at=now_,
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return RedirectResponse(url=f"/entry/{entry_id}", status_code=303)

    @app.get("/day/{iso_date}", response_class=HTMLResponse)
    def view_day(iso_date: str) -> HTMLResponse:
        try:
            day = date.fromisoformat(iso_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid date") from exc
        entries = iter_entries_for_day(vault_path, day)
        return render("day.html", day=day, entries=entries, title=f"Plastiglom — {day}")

    return app
