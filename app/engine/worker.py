"""Claim leased task items and drive the processor."""

from __future__ import annotations

import logging
import threading
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.engine.processor import Processor
from app.engine.runtime import load_runtime_settings
from app.repositories import campaign_repo

logger = logging.getLogger(__name__)


class Worker:
    """Single-process worker: claim, process, repeat. Driven by ``tick()``."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        clock: Clock,
        processor: Processor,
        *,
        worker_id: str = "worker-1",
        tick_seconds: float = 1.0,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self._processor = processor
        self.worker_id = worker_id
        self._tick_seconds = tick_seconds
        self._stop = threading.Event()

    def tick(self) -> int:
        """Claim each running task's share and process every claimed item."""
        processed = 0
        with self._session_factory() as session:
            task_ids = campaign_repo.list_running_task_ids(session)
        for task_id in task_ids:
            for item_id in self.claim(task_id):
                with self._session_factory() as session:
                    try:
                        self._processor.process(session, item_id)
                    except Exception:
                        session.rollback()
                        logger.exception(
                            "worker item processing failed item_id=%s", item_id
                        )
                        continue
                    processed += 1
        return processed

    def claim(self, task_id: int) -> list[int]:
        """Lease up to ``sending.claim_batch_size`` claimable items of one task."""
        with self._session_factory() as session:
            settings: dict[str, Any] = load_runtime_settings(session)
            claimed = campaign_repo.claim_items(
                session,
                task_id=task_id,
                worker_id=self.worker_id,
                now=self._clock.now(),
                lease_seconds=int(settings["sending.lease_seconds"]),
                limit=int(settings["sending.claim_batch_size"]),
            )
            session.commit()
            return claimed

    def run_forever(self) -> None:
        """Loop ticks until ``stop()`` is called; used by the app lifespan."""
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                logger.exception("worker tick failed")
            self._stop.wait(self._tick_seconds)

    def stop(self) -> None:
        """Ask the loop to exit after the current tick."""
        self._stop.set()
