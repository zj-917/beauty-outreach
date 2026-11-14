"""Evaluate the screening rules against the labelled mock dataset (AC-SCR-014).

Run: python scripts/eval_screening.py [--json]
"""

from __future__ import annotations

import argparse
import json
import secrets
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock, FakeClock
from app.core.config import Settings
from app.core.db import build_engine, build_session_factory
from app.core.security import PhoneCipher
from app.domain.lead import normalize_username
from app.models import Lead, create_schema
from app.services.audit_service import AuditService
from app.services.lead_service import LeadService
from app.services.screening_service import ScreeningService
from app.services.seed_service import seed_defaults

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "mock_leads.json"
TARGETS = {"precision": 0.95, "recall": 0.85, "borderline_accuracy": 0.75}
EXPECTED_STATUS = {
    "relevant": "APPROVED",
    "borderline": "PENDING_REVIEW",
    "irrelevant": "DISCARDED",
}


@dataclass
class EvalResult:
    """Metrics and error detail from one evaluation run."""

    imported: int
    approved: int
    relevant_imported: int
    precision: float
    recall: float
    borderline_accuracy: float
    confusion: dict[str, dict[str, int]] = field(default_factory=dict)
    misses: list[dict[str, Any]] = field(default_factory=list)

    def passed(self) -> bool:
        """Return whether every target metric is met."""
        return (
            self.precision >= TARGETS["precision"]
            and self.recall >= TARGETS["recall"]
            and self.borderline_accuracy >= TARGETS["borderline_accuracy"]
        )


def _build_settings(db_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{db_path.as_posix()}",
        admin_token="eval-token",
        phone_enc_key=Fernet.generate_key().decode(),
        phone_hash_key=secrets.token_hex(16),
        webhook_secret=secrets.token_hex(16),
        messenger_provider="mock",
        worker_enabled=False,
        demo_mode=True,
    )


def _labels(data_path: Path) -> dict[str, str]:
    rows = json.loads(data_path.read_text(encoding="utf-8"))
    return {
        normalize_username(row["username"]): row["expected_label"]
        for row in rows
        if row.get("username")
    }


def _import_and_screen(session: Session, clock: Clock, cipher: PhoneCipher) -> None:
    audit = AuditService(clock)
    seed_defaults(session, clock, cipher=cipher)
    LeadService(clock, cipher, audit).import_batch(
        session, LeadService.source_by_name("mock"), operator="system:eval"
    )
    ScreeningService(clock, audit).run(
        session, batch_id=None, lead_ids=None, operator="system:eval"
    )


def _evaluate_with(
    session_factory: sessionmaker[Session], labels: dict[str, str]
) -> EvalResult:
    with session_factory() as session:
        leads = session.scalars(select(Lead)).all()
    confusion: Counter[tuple[str, str]] = Counter(
        (labels.get(lead.username, "unknown"), lead.status) for lead in leads
    )
    approved = [lead for lead in leads if lead.status == "APPROVED"]
    relevant_approved = sum(
        1 for lead in approved if labels.get(lead.username) == "relevant"
    )
    relevant_total = sum(1 for lead in leads if labels.get(lead.username) == "relevant")
    borderline = [
        lead for lead in leads if labels.get(lead.username) == "borderline"
    ]
    borderline_ok = sum(
        1 for lead in borderline if lead.status == "PENDING_REVIEW"
    )
    misses = []
    for lead in leads:
        label = labels.get(lead.username, "unknown")
        if EXPECTED_STATUS.get(label) == lead.status:
            continue
        misses.append(
            {
                "username": lead.username,
                "expected_label": label,
                "status": lead.status,
                "score": lead.score,
                "reasons": lead.score_reasons,
            }
        )
    matrix: dict[str, dict[str, int]] = {}
    for (label, status), count in sorted(confusion.items()):
        matrix.setdefault(label, {})[status] = count
    return EvalResult(
        imported=len(leads),
        approved=len(approved),
        relevant_imported=relevant_total,
        precision=(
            relevant_approved / len(approved) if approved else 0.0
        ),
        recall=(
            relevant_approved / relevant_total if relevant_total else 0.0
        ),
        borderline_accuracy=(
            borderline_ok / len(borderline) if borderline else 0.0
        ),
        confusion=matrix,
        misses=misses,
    )


def evaluate(
    settings: Settings, clock: Clock, *, data_path: Path = DATA_PATH
) -> EvalResult:
    """Import the mock dataset into a fresh database, screen it and score the result."""
    cipher = PhoneCipher(settings.phone_enc_key, settings.phone_hash_key)
    engine = build_engine(settings)
    try:
        create_schema(engine)
        session_factory = build_session_factory(engine)
        with session_factory() as session:
            _import_and_screen(session, clock, cipher)
        return _evaluate_with(session_factory, _labels(data_path))
    finally:
        engine.dispose()


def _print_report(result: EvalResult) -> None:
    print(f"Screening evaluation — {result.imported} imported leads, "
          f"{result.approved} auto-approved, {result.relevant_imported} relevant")
    rows = [
        ("Precision", result.precision, TARGETS["precision"]),
        ("Recall", result.recall, TARGETS["recall"]),
        ("Borderline accuracy", result.borderline_accuracy, TARGETS["borderline_accuracy"]),
    ]
    for name, value, target in rows:
        verdict = "PASS" if value >= target else "FAIL"
        print(f"  {name:<20} {value:.3f}  target >= {target:.2f}  {verdict}")
    print("Confusion matrix (expected_label → status):")
    for label, statuses in sorted(result.confusion.items()):
        counts = ", ".join(f"{status}={count}" for status, count in sorted(statuses.items()))
        print(f"  {label:<11} {counts}")
    print(f"Misclassified: {len(result.misses)}")
    for miss in result.misses:
        reasons = ", ".join(
            f"{item.get('code')}({item.get('delta'):+d})" for item in miss["reasons"] or []
        )
        print(
            f"  - {miss['username']}: expected {miss['expected_label']}, "
            f"got {miss['status']} (score {miss['score']}); {reasons}"
        )


def main(argv: list[str] | None = None) -> int:
    """Run the evaluation and return a process exit code."""
    parser = argparse.ArgumentParser(description="Evaluate screening on mock data")
    parser.add_argument("--json", action="store_true", help="print JSON only")
    parser.add_argument("--data", type=Path, default=DATA_PATH, help="mock dataset path")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        settings = _build_settings(Path(tmp) / "eval.db")
        result = evaluate(settings, FakeClock(), data_path=args.data)

    if args.json:
        print(
            json.dumps(
                {
                    "imported": result.imported,
                    "approved": result.approved,
                    "relevant_imported": result.relevant_imported,
                    "precision": result.precision,
                    "recall": result.recall,
                    "borderline_accuracy": result.borderline_accuracy,
                    "confusion": result.confusion,
                    "misses": result.misses,
                    "passed": result.passed(),
                    "targets": TARGETS,
                },
                ensure_ascii=False,
            )
        )
    else:
        _print_report(result)
    return 0 if result.passed() else 1


if __name__ == "__main__":
    raise SystemExit(main())
