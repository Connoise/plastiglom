"""Tests for the analysis browse + correction routes."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from plastiglom.apps.analyzer import AnalysisRequest
from plastiglom.apps.web_app.app import create_app
from plastiglom.packages.vault.markdown import FrontmatterDocument, write_markdown_file


@dataclass
class FakeAnalyzer:
    captured: list[AnalysisRequest] = field(default_factory=list)
    output_path: Path | None = None

    def run(self, request: AnalysisRequest) -> Path:
        self.captured.append(request)
        # Simulate the corrected report living next to the prior one.
        prior = request.correction_of
        assert prior is not None
        out = prior.with_name(prior.stem + "-corrected-1" + prior.suffix)
        write_markdown_file(
            out,
            FrontmatterDocument(
                metadata={
                    "cadence": request.cadence.value,
                    "window_start": request.window_start,
                    "window_end": request.window_end,
                    "correction_of": str(prior),
                },
                content="corrected body\n",
            ),
        )
        self.output_path = out
        return out


def _write_report(vault: Path, relative: str, **meta) -> Path:
    path = vault / "analysis" / relative
    write_markdown_file(
        path,
        FrontmatterDocument(
            metadata={
                "cadence": meta.get("cadence", "weekly"),
                "window_start": meta.get(
                    "window_start", datetime(2026, 5, 11, tzinfo=UTC)
                ),
                "window_end": meta.get(
                    "window_end", datetime(2026, 5, 18, tzinfo=UTC)
                ),
                "query": meta.get("query"),
                "slug": meta.get("slug"),
            },
            content=meta.get("body", "Some report body.\n"),
        ),
    )
    return path


def _client(vault: Path, *, analyzer=None) -> TestClient:
    app = create_app(
        vault_path=vault,
        tz=ZoneInfo("UTC"),
        now=lambda: datetime(2026, 5, 20, tzinfo=UTC),
        analyzer=analyzer,
    )
    return TestClient(app)


def test_analysis_index_groups_by_cadence(vault):
    _write_report(vault, "weekly/2026-W19.md")
    _write_report(vault, "monthly/2026-04.md", cadence="monthly")
    _write_report(vault, "queries/2026-05-15-ad.md", cadence="adhoc", query="why?")
    client = _client(vault)
    r = client.get("/analysis")
    assert r.status_code == 200
    text = r.text
    assert "weekly" in text
    assert "monthly" in text
    assert "queries" in text
    assert "2026-W19" in text
    assert "why?" in text


def test_analysis_view_renders_report(vault):
    _write_report(vault, "weekly/2026-W19.md", body="A blunt observation.\n")
    client = _client(vault)
    r = client.get("/analysis/view", params={"path": "weekly/2026-W19.md"})
    assert r.status_code == 200
    assert "A blunt observation." in r.text
    assert "Flag a correction" in r.text


def test_analysis_view_rejects_path_traversal(vault):
    client = _client(vault)
    r = client.get("/analysis/view", params={"path": "../../etc/passwd"})
    assert r.status_code == 404


def test_correction_503_when_analyzer_missing(vault):
    _write_report(vault, "weekly/2026-W19.md")
    client = _client(vault, analyzer=None)
    r = client.post(
        "/analysis/correct",
        data={"path": "weekly/2026-W19.md", "note": "wrong"},
        follow_redirects=False,
    )
    assert r.status_code == 503


def test_correction_runs_analyzer_and_redirects(vault):
    prior = _write_report(vault, "weekly/2026-W19.md")
    analyzer = FakeAnalyzer()
    client = _client(vault, analyzer=analyzer)
    r = client.post(
        "/analysis/correct",
        data={"path": "weekly/2026-W19.md", "note": "second observation was wrong"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert len(analyzer.captured) == 1
    captured = analyzer.captured[0]
    assert captured.correction_of == prior
    assert captured.correction_note == "second observation was wrong"
    # Redirect points at the new corrected report under /analysis/.
    location = r.headers["location"]
    assert location.startswith("/analysis/view?path=weekly/2026-W19-corrected-1.md")
