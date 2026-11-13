"""Seed default configuration and the greeting template."""

from __future__ import annotations

import argparse

from app.core.clock import SystemClock
from app.core.config import load_settings
from app.core.db import build_engine, build_session_factory
from app.models import Base, create_schema
from app.services.seed_service import seed_defaults


def main() -> int:
    """Seed the configured database and print created row counts."""
    parser = argparse.ArgumentParser(description="Seed default configuration")
    parser.add_argument("--reset", action="store_true", help="drop all tables first")
    args = parser.parse_args()

    settings = load_settings()
    engine = build_engine(settings)
    if args.reset:
        Base.metadata.drop_all(engine)
    create_schema(engine)
    with build_session_factory(engine)() as session:
        counts = seed_defaults(session, SystemClock())
    engine.dispose()
    summary = ", ".join(f"{name}={count}" for name, count in counts.items())
    print(f"seed complete: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
