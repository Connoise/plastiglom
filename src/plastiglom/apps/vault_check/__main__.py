"""CLI for the vault integrity validator.

  plastiglom-vault check                 # human report; exits 1 on any error
  plastiglom-vault check --json          # machine-readable
  plastiglom-vault check --warnings-as-errors

Exit codes:
  0 — no errors (warnings may still be present unless --warnings-as-errors)
  1 — at least one error
  2 — bad invocation
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from plastiglom.apps.vault_check.checks import Finding, ValidationReport, run_checks
from plastiglom.packages.config import load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plastiglom vault integrity check.")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check")
    check.add_argument("--json", action="store_true")
    check.add_argument("--warnings-as-errors", action="store_true")

    args = parser.parse_args(argv)
    settings = load_settings()
    report = run_checks(settings.vault_path)

    if args.command != "check":
        parser.error(f"unknown command {args.command!r}")
        return 2

    if args.json:
        print(json.dumps(_report_to_dict(report), indent=2))
    else:
        _print_human(report)

    fail = bool(report.errors) or (args.warnings_as_errors and bool(report.warnings))
    return 1 if fail else 0


def _print_human(report: ValidationReport) -> None:
    print(
        f"scanned: {report.exercise_files_scanned} exercise file(s), "
        f"{report.entry_files_scanned} entry file(s)"
    )
    print(f"findings: {len(report.errors)} error(s), {len(report.warnings)} warning(s)")
    if not report.findings:
        print("ok.")
        return
    for finding in report.findings:
        path = f" [{finding.path}]" if finding.path else ""
        print(f"  {finding.severity.value.upper():<5} {finding.code}: {finding.message}{path}")


def _report_to_dict(report: ValidationReport) -> dict:
    return {
        "exercise_files_scanned": report.exercise_files_scanned,
        "entry_files_scanned": report.entry_files_scanned,
        "errors": len(report.errors),
        "warnings": len(report.warnings),
        "findings": [_finding_to_dict(f) for f in report.findings],
    }


def _finding_to_dict(f: Finding) -> dict:
    d = asdict(f)
    d["severity"] = f.severity.value
    d["path"] = str(f.path) if f.path else None
    return d


if __name__ == "__main__":
    sys.exit(main())
