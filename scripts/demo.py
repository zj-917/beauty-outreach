"""End-to-end demo driver and e2e test (AC-SYS-011).

Run: python scripts/demo.py           # real clock, about 1-2 minutes
     python scripts/demo.py --fast    # fake clock, no waiting
"""

from __future__ import annotations

import argparse
import secrets
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.clock import Clock, FakeClock, SystemClock
from app.core.config import Settings
from app.engine.processor import Processor
from app.engine.worker import Worker
from app.main import create_app
from app.services.receipt_service import ReceiptService

STOP_PHONE = "+15555550101"
EXPECTED_IMPORT = {
    "total_rows": 52,
    "imported": 44,
    "duplicates": 4,
    "invalid": 4,
    "warnings": 1,
}
EXPECTED_SKIP_REASONS = {
    "NO_PHONE": 7,
    "NO_CONSENT": 1,
    "CONSENT_REVOKED": 1,
    "BLACKLISTED": 2,
    "UNSUBSCRIBED": 2,
}
EXPECTED_FAILURE_REASONS = {
    "MAX_ATTEMPTS_EXCEEDED": 1,
    "INVALID_NUMBER": 1,
    "DELIVERY_FAILED": 1,
}


class DemoFailure(AssertionError):
    """Raised when an expected demo number does not hold."""


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise DemoFailure(message)


def _settings(db_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{db_path.as_posix()}",
        admin_token="demo-token",
        phone_enc_key=Fernet.generate_key().decode(),
        phone_hash_key=secrets.token_hex(16),
        webhook_secret=secrets.token_hex(16),
        messenger_provider="mock",
        worker_enabled=False,
        tick_seconds=0.05,
        demo_mode=True,
        seed_defaults=False,
        log_level="WARNING",
    )


def _build_worker(app: FastAPI, clock: Clock) -> Worker:
    processor = Processor(
        clock,
        app.state.phone_cipher,
        app.state.messenger,
        worker_id="demo-worker",
        audit=app.state.audit_service,
    )
    receipts = ReceiptService(
        clock, messenger=app.state.messenger, session_factory=app.state.session_factory
    )
    return Worker(
        app.state.session_factory,
        clock,
        processor,
        worker_id="demo-worker",
        receipts=receipts,
    )


def _run(client: TestClient, app: FastAPI, clock: Clock, *, fast: bool) -> dict:
    reset = client.post("/demo/reset").json()
    _check(reset["counts"]["suppressions"] == 3, f"blacklist seed failed: {reset}")
    print("1/7 重置演示数据：配置与 3 条黑名单/退订已重新播种")

    batch = client.post("/api/v1/lead-batches/import", json={"source": "mock"}).json()
    for key, expected in EXPECTED_IMPORT.items():
        _check(batch[key] == expected, f"import {key}={batch[key]}, expected {expected}")
    print(f"2/7 导入 Mock 线索：{batch['imported']} 条入库，"
          f"{batch['duplicates']} 重复，{batch['invalid']} 非法，{batch['warnings']} 警告")

    screening = client.post("/api/v1/leads/screen", json={}).json()
    _check(
        (screening["processed"], screening["approved"],
         screening["pending_review"], screening["discarded"]) == (44, 20, 8, 16),
        f"screening counts unexpected: {screening}",
    )
    print("3/7 运行筛选：20 自动入池、8 待确认、16 丢弃")

    templates = client.get("/api/v1/templates").json()
    template_id = next(item["id"] for item in templates if item["name"] == "greeting")
    campaign = client.post(
        "/api/v1/campaigns",
        json={"name": "demo first round", "template_id": template_id, "selection": {}},
    ).json()
    campaign_id = campaign["id"]
    _check(campaign["total_items"] == 20, f"expected 20 targets, got {campaign}")
    print(f"4/7 创建任务 #{campaign_id}：快照 {campaign['total_items']} 条入池线索")

    _check(client.post(f"/api/v1/campaigns/{campaign_id}/start").status_code == 200,
           "start failed")
    _check(client.post(f"/api/v1/campaigns/{campaign_id}/pause").status_code == 200,
           "pause failed")
    stop = client.post("/demo/inbound-stop", json={"phone": STOP_PHONE}).json()
    _check(stop["action"] == "UNSUBSCRIBED", f"STOP not applied: {stop}")
    _check(client.post(f"/api/v1/campaigns/{campaign_id}/resume").status_code == 200,
           "resume failed")
    print("5/7 暂停 → 模拟收到 STOP → 恢复（该收件人将变为 SKIPPED/UNSUBSCRIBED）")

    worker = _build_worker(app, clock)
    status = "RUNNING"
    ticks = 0
    while ticks < 240:
        ticks += 1
        worker.tick()
        status = client.get(f"/api/v1/campaigns/{campaign_id}").json()["status"]
        if status in {"COMPLETED", "CANCELLED"}:
            break
        clock.sleep(1)
    _check(status == "COMPLETED", f"campaign ended as {status} after {ticks} ticks")
    print(f"6/7 Worker 处理完成：{ticks} 个 tick（含重试退避与频控延迟）")

    client.post("/demo/flush-receipts")
    stats = client.get(f"/api/v1/campaigns/{campaign_id}/stats").json()
    _check(stats["total"] == 20, f"total={stats['total']}")
    _check(stats["success"] == 4, f"success={stats['success']}（含 STOP 步骤应为 4）")
    _check(stats["failed"] == 3, f"failed={stats['failed']}")
    _check(stats["skipped"] == 13, f"skipped={stats['skipped']}")
    _check(stats["skip_reasons"] == EXPECTED_SKIP_REASONS,
           f"skip_reasons={stats['skip_reasons']}")
    _check(stats["failure_reasons"] == EXPECTED_FAILURE_REASONS,
           f"failure_reasons={stats['failure_reasons']}")
    print("7/7 结果统计：success=4 failed=3 skipped=13（NO_PHONE 7、NO_CONSENT 1、"
          "CONSENT_REVOKED 1、BLACKLISTED 2、UNSUBSCRIBED 2）")
    return stats


def run(*, fast: bool) -> int:
    """Drive the whole flow and return a process exit code."""
    clock: Clock = (
        FakeClock(datetime(2026, 11, 14, 9, 0, tzinfo=UTC))
        if fast
        else SystemClock()
    )
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        settings = _settings(Path(tmp) / "demo.db")
        app = create_app(settings=settings, clock=clock)
        try:
            with TestClient(
                app, headers={"X-Admin-Token": settings.admin_token}
            ) as client:
                stats = _run(client, app, clock, fast=fast)
        except DemoFailure as failure:
            print(f"DEMO FAILED: {failure}")
            return 1
        finally:
            app.state.engine.dispose()
    print(f"DEMO OK — {stats['status']}，success={stats['success']}，"
          f"failed={stats['failed']}，skipped={stats['skipped']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse flags and run the demo."""
    parser = argparse.ArgumentParser(description="End-to-end outreach demo")
    parser.add_argument(
        "--fast", action="store_true", help="use a fake clock and skip real waiting"
    )
    args = parser.parse_args(argv)
    return run(fast=args.fast)


if __name__ == "__main__":
    raise SystemExit(main())
