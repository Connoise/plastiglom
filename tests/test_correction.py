"""Tests for the analyzer correction channel.

We can't talk to a real LLM in unit tests, so we drive `Analyzer` with a
minimal fake router that returns canned responses. The point of these tests
is to verify the *bookkeeping* around corrections, not the LLM output.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from plastiglom.apps.analyzer import (
    AnalysisRequest,
    Analyzer,
    Cadence,
    correction_request,
)
from plastiglom.packages.llm.types import LLMResponse
from plastiglom.packages.vault.markdown import read_markdown_file


@dataclass
class FakeRouter:
    text: str = "FAKE REPORT BODY"

    def invoke(self, _task, _call) -> LLMResponse:
        return LLMResponse(
            text=self.text,
            model="fake",
            input_tokens=0,
            output_tokens=0,
        )


def _write_first_report(vault: Path) -> Path:
    analyzer = Analyzer(vault_path=vault, router=FakeRouter(text="ORIGINAL"))
    request = AnalysisRequest(
        cadence=Cadence.WEEKLY,
        window_start=datetime(2026, 5, 11, tzinfo=UTC),
        window_end=datetime(2026, 5, 18, tzinfo=UTC),
    )
    return analyzer.run(request)


def test_correction_writes_new_report_alongside_prior(tmp_path):
    prior = _write_first_report(tmp_path)
    assert prior.exists()
    original_text = prior.read_text(encoding="utf-8")

    analyzer = Analyzer(vault_path=tmp_path, router=FakeRouter(text="CORRECTED"))
    new_path = analyzer.run(correction_request(prior, "you missed the X pattern"))

    # Prior is untouched.
    assert prior.read_text(encoding="utf-8") == original_text
    # Corrected report is a sibling, not a replacement.
    assert new_path != prior
    assert new_path.parent == prior.parent
    assert "-corrected-" in new_path.stem
    assert "CORRECTED" in new_path.read_text(encoding="utf-8")


def test_correction_logs_history_pointer(tmp_path):
    prior = _write_first_report(tmp_path)
    analyzer = Analyzer(vault_path=tmp_path, router=FakeRouter())
    new_path = analyzer.run(correction_request(prior, "the second observation was wrong"))

    history_dir = tmp_path / "analysis_history"
    history_files = list(history_dir.glob("*.md"))
    assert len(history_files) == 1

    pointer = read_markdown_file(history_files[0])
    assert pointer.metadata["supersedes"] == str(prior)
    assert pointer.metadata["superseded_by"] == str(new_path)
    assert pointer.metadata["note"] == "the second observation was wrong"


def test_correction_request_carries_window_from_prior(tmp_path):
    prior = _write_first_report(tmp_path)
    request = correction_request(prior, "note")
    assert request.cadence is Cadence.WEEKLY
    assert request.window_start == datetime(2026, 5, 11, tzinfo=UTC)
    assert request.window_end == datetime(2026, 5, 18, tzinfo=UTC)
    assert request.correction_of == prior
    assert request.correction_note == "note"
