"""Uvicorn launcher for the web app.

Bind to loopback only; expose via Tailscale at the OS level rather than
opening a non-localhost port here.
"""

from __future__ import annotations

import argparse

import uvicorn

from plastiglom.apps.web_app.app import create_app
from plastiglom.packages.config import load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Plastiglom web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args(argv)

    settings = load_settings()
    app = create_app(vault_path=settings.vault_path, tz=settings.timezone)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
