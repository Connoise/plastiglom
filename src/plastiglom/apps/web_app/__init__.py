"""Tailscale-served PWA for entry submission. Phase 1.

Responsibilities (§7.3):
  - Display pending prompt, accept a response, allow edits until `lock_at`.
  - Offline drafting via service worker + IndexedDB; first-sync counts as
    submission.
  - Host the exercise-change approval UI in Phase 4.

Concrete stack (FastAPI + htmx by default, React/Svelte if offline drafting
needs it) is deferred to implementation time per §10.
"""
