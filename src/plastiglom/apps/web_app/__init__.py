"""Tailscale-served PWA for entry submission. See §7.3 of DESIGN.md.

Minimal FastAPI + Jinja2 surface. The JavaScript footprint is htmx-only, to
keep the mobile page fast over Tailscale. Service-worker + IndexedDB offline
drafting is still deferred (§10 open choice); the server-side endpoints here
are already shaped to accept a first-sync-as-submission pattern.
"""

from plastiglom.apps.web_app.app import create_app

__all__ = ["create_app"]
