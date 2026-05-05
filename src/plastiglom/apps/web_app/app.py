"""FastAPI factory for the Plastiglom web app.

Routes:
  - GET  /                 : the current open prompt, editable until lock.
  - GET  /entry/{id}       : view an individual entry (read-only once locked).
  - POST /entry/{id}       : submit or update a response.
  - GET  /day/{iso-date}   : list entries for that day.
  - GET  /analysis         : index of weekly / monthly / ad-hoc reports.
  - GET  /analysis/view    : render one report.
  - POST /analysis/correct : flag a report wrong; runs analyzer if provided.

The route handlers are thin; persistence goes through `Archiver.on_submit`
which enforces `lock_at`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from fastapi import Body, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from plastiglom.apps.analyzer import AnalysisRequest, correction_request
from plastiglom.apps.archiver.archiver import Archiver, SubmitRequest
from plastiglom.apps.meta_engine import (
    ProposalStatus,
    apply_proposal,
    decide,
    list_proposals,
    load_proposal,
)
from plastiglom.apps.web_app.analysis_view import (
    list_analysis,
    resolve_analysis_path,
)
from plastiglom.apps.web_app.lookup import (
    iter_entries_for_day,
    latest_open_entry,
    load_entry,
)
from plastiglom.apps.web_app.templates import build_env
from plastiglom.packages.vault.markdown import read_markdown_file
from plastiglom.packages.vault.serializers import exercise_to_document


class AnalyzerLike(Protocol):
    def run(self, request: AnalysisRequest) -> Path: ...


def create_app(
    vault_path: Path,
    tz: ZoneInfo,
    *,
    now: Callable[[], datetime] | None = None,
    analyzer: AnalyzerLike | None = None,
    on_change: Callable[[Path], None] | None = None,
) -> FastAPI:
    """Build the FastAPI app.

    `now` is injectable for tests. `analyzer` is optional: when omitted, the
    correction route returns 503 instead of trying to call the LLM.
    `on_change` lets a caller pass an indexer reindex hook.
    """
    app = FastAPI(title="Plastiglom", version="0.0.1")
    env = build_env()
    archiver = Archiver(vault_path, on_change=on_change)
    clock: Callable[[], datetime] = now or (lambda: datetime.now(tz=tz))

    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

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

    @app.get("/analysis", response_class=HTMLResponse)
    def analysis_index() -> HTMLResponse:
        items = list_analysis(vault_path)
        grouped: dict[str, list] = defaultdict(list)
        for item in items:
            grouped[item.cadence].append(item)
        ordered = sorted(grouped.items(), key=lambda kv: kv[0])
        return render("analysis_index.html", items=ordered, title="Plastiglom — Analysis")

    @app.get("/analysis/view", response_class=HTMLResponse)
    def analysis_view(path: str) -> HTMLResponse:
        try:
            resolved = resolve_analysis_path(vault_path, path)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        doc = read_markdown_file(resolved)
        return render(
            "analysis_view.html",
            relative_path=path,
            meta=doc.metadata,
            rendered_body=_naive_markdown_to_html(doc.content),
            title=f"Plastiglom — {resolved.stem}",
        )

    @app.post("/analysis/correct")
    def analysis_correct(path: str = Form(...), note: str = Form(...)) -> RedirectResponse:
        if analyzer is None:
            raise HTTPException(status_code=503, detail="analyzer is not configured")
        try:
            prior = resolve_analysis_path(vault_path, path)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        request = correction_request(prior, note)
        new_path = analyzer.run(request)
        relative = new_path.relative_to(vault_path / "analysis").as_posix()
        return RedirectResponse(
            url=f"/analysis/view?path={relative}",
            status_code=303,
        )

    @app.get("/proposals", response_class=HTMLResponse)
    def proposals_index() -> HTMLResponse:
        all_records = list_proposals(vault_path)
        pending = [r for r in all_records if r.status is ProposalStatus.PENDING]
        decided = [r for r in all_records if r.status is not ProposalStatus.PENDING]
        return render(
            "proposals_index.html",
            pending=pending,
            decided=decided,
            title="Plastiglom — Proposals",
        )

    @app.get("/proposals/{proposal_id}", response_class=HTMLResponse)
    def proposal_view(proposal_id: str) -> HTMLResponse:
        try:
            record = load_proposal(vault_path, proposal_id)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        proposed_yaml = _exercise_metadata_yaml(record.proposal.exercise)
        return render(
            "proposal_view.html",
            record=record,
            proposed_yaml=proposed_yaml,
            title=f"Plastiglom — proposal {proposal_id}",
        )

    @app.post("/proposals/{proposal_id}/approve")
    def proposal_approve(proposal_id: str) -> RedirectResponse:
        try:
            record = load_proposal(vault_path, proposal_id)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if record.status is not ProposalStatus.PENDING:
            raise HTTPException(status_code=409, detail="proposal is not pending")
        apply_proposal(vault_path, record.proposal, approved_by="user")
        decide(
            vault_path,
            proposal_id,
            status=ProposalStatus.APPROVED,
            decided_by="user",
        )
        return RedirectResponse(url=f"/proposals/{proposal_id}", status_code=303)

    @app.post("/proposals/{proposal_id}/reject")
    def proposal_reject(
        proposal_id: str, note: str = Form(default="")
    ) -> RedirectResponse:
        try:
            record = load_proposal(vault_path, proposal_id)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if record.status is not ProposalStatus.PENDING:
            raise HTTPException(status_code=409, detail="proposal is not pending")
        decide(
            vault_path,
            proposal_id,
            status=ProposalStatus.REJECTED,
            decided_by="user",
            note=note or None,
        )
        return RedirectResponse(url=f"/proposals/{proposal_id}", status_code=303)

    # ─── Mobile UI ──────────────────────────────────────────────────
    mobile_index = static_dir / "mobile" / "index.html"

    @app.get("/mobile", response_model=None)
    def mobile_shell() -> FileResponse:
        if not mobile_index.is_file():
            raise HTTPException(status_code=404, detail="mobile UI not bundled")
        return FileResponse(mobile_index, media_type="text/html")

    @app.get("/api/today")
    def api_today() -> JSONResponse:
        entry = latest_open_entry(vault_path, clock())
        return JSONResponse({"entry": _entry_payload(entry, clock()) if entry else None})

    @app.get("/api/entry/{entry_id}")
    def api_entry(entry_id: str) -> JSONResponse:
        try:
            entry = load_entry(vault_path, entry_id)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return JSONResponse({"entry": _entry_payload(entry, clock())})

    @app.post("/api/entry/{entry_id}")
    def api_submit_entry(
        entry_id: str,
        payload: dict = Body(default_factory=dict),  # noqa: B008
    ) -> JSONResponse:
        try:
            existing = load_entry(vault_path, entry_id)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        now_ = clock()
        if existing.is_locked(now_):
            raise HTTPException(status_code=409, detail="entry is locked")
        response_text = str(payload.get("response", ""))
        try:
            archiver.on_submit(
                SubmitRequest(
                    entry_id=existing.id,
                    exercise_id=existing.exercise_id,
                    fired_at=existing.timestamp_fired,
                    response=response_text,
                    submitted_at=now_,
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        updated = load_entry(vault_path, entry_id)
        return JSONResponse({"entry": _entry_payload(updated, now_)})

    @app.get("/api/archive")
    def api_archive(limit: int = 30) -> JSONResponse:
        entries_root = vault_path / "entries"
        if not entries_root.exists():
            return JSONResponse({"entries": []})
        from plastiglom.packages.vault.markdown import read_markdown_file
        from plastiglom.packages.vault.serializers import parse_entry as _parse

        gathered = []
        for md in entries_root.rglob("*.md"):
            try:
                gathered.append(_parse(read_markdown_file(md)))
            except Exception:
                continue
        gathered.sort(key=lambda e: e.timestamp_fired, reverse=True)
        now_ = clock()
        items = [_entry_summary(e, now_) for e in gathered[: max(1, min(limit, 200))]]
        return JSONResponse({"entries": items})

    @app.get("/api/analysis")
    def api_analysis() -> JSONResponse:
        items = list_analysis(vault_path)
        grouped: dict[str, list] = defaultdict(list)
        for item in items:
            grouped[item.cadence].append(
                {
                    "relative_path": item.relative_path,
                    "title": item.title,
                    "has_correction": item.has_correction,
                }
            )
        groups = [
            {"cadence": cadence, "items": grouped[cadence]}
            for cadence in sorted(grouped)
        ]
        return JSONResponse({"groups": groups})

    return app


def _entry_payload(entry, now: datetime) -> dict:
    return {
        "id": entry.id,
        "title": entry.title,
        "exercise_id": entry.exercise_id,
        "status": entry.status.value,
        "tags": list(entry.tags),
        "prompt_snapshot": list(entry.prompt_snapshot),
        "response": entry.response,
        "timestamp_fired": entry.timestamp_fired.isoformat(),
        "lock_at": entry.lock_at.isoformat(),
        "is_locked": entry.is_locked(now),
    }


def _entry_summary(entry, now: datetime) -> dict:
    return {
        "id": entry.id,
        "title": entry.title,
        "status": entry.status.value,
        "tags": list(entry.tags),
        "timestamp_fired": entry.timestamp_fired.isoformat(),
        "lock_at": entry.lock_at.isoformat(),
        "is_locked": entry.is_locked(now),
    }


def _exercise_metadata_yaml(exercise) -> str:
    import yaml as _yaml

    return _yaml.safe_dump(
        exercise_to_document(exercise).metadata,
        sort_keys=False,
        default_flow_style=False,
    ).rstrip()


def _naive_markdown_to_html(text: str) -> str:
    """Minimal markdown -> HTML.

    The vault stores plain markdown; we don't pull in a heavyweight
    markdown library here. Newlines become paragraph breaks; everything
    else is escaped by Jinja2 (we set autoescape=True). Only the body
    we return is marked safe at the call site.
    """
    from html import escape

    parts = [
        f"<p>{escape(block).replace(chr(10), '<br>')}</p>"
        for block in text.split("\n\n")
        if block.strip()
    ]
    return "\n".join(parts)
