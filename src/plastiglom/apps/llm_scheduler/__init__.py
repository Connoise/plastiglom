"""Scheduled execution of LLM-driven jobs (digest, analyzer, proposals).

See `runner.py` for the cadence rules and job registry. The cron-facing
entrypoint is `__main__.py` (`python -m plastiglom.apps.llm_scheduler`).
"""
