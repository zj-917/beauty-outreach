"""Demo-only operations kept out of the API layer."""

from __future__ import annotations

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.core.security import PhoneCipher
from app.repositories import schema_repo
from app.services.seed_service import seed_defaults


class DemoService:
    """Clear the database and reseed the defaults for a fresh demo."""

    def __init__(self, clock: Clock, cipher: PhoneCipher) -> None:
        self._clock = clock
        self._cipher = cipher

    def reset(
        self, engine: Engine, session_factory: sessionmaker[Session]
    ) -> dict[str, int]:
        """Drop every table, recreate the schema and seed, returning row counts."""
        schema_repo.reset_schema(engine)
        with session_factory() as session:
            return seed_defaults(session, self._clock, cipher=self._cipher)
