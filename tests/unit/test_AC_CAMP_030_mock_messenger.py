"""MockMessenger deterministic matrix and idempotency tests."""

from __future__ import annotations

from app.core.clock import FakeClock
from app.providers.messenger import MockMessenger, ResultKind, SendRequest


def _request(key: str, phone: str) -> SendRequest:
    return SendRequest(
        idempotency_key=key,
        to_phone=phone,
        body="Hi {{name}}",
        template_name="greeting",
        language="en",
    )


def test_AC_CAMP_030_9001_retries_twice_then_accepts(clock: FakeClock) -> None:
    """Given the 9001 suffix, when sent repeatedly, then two timeouts precede acceptance."""
    mock = MockMessenger(clock)
    request = _request("key-9001", "+15555559001")

    first = mock.send(request)
    second = mock.send(request)
    third = mock.send(request)

    assert (first.kind, first.code) == (ResultKind.RETRYABLE, "TIMEOUT")
    assert (second.kind, second.code) == (ResultKind.RETRYABLE, "TIMEOUT")
    assert third.kind == ResultKind.ACCEPTED
    assert third.provider_message_id is not None
    assert mock.calls == 3
    assert mock.unique_messages == 1

    repeat = mock.send(request)
    assert repeat.kind == ResultKind.ACCEPTED
    assert repeat.provider_message_id == third.provider_message_id
    assert mock.calls == 4
    assert mock.unique_messages == 1


def test_AC_CAMP_030_9002_always_retryable(clock: FakeClock) -> None:
    """Given the 9002 suffix, when sent repeatedly, then every call is retryable."""
    mock = MockMessenger(clock)
    request = _request("key-9002", "+15555559002")

    for _ in range(3):
        result = mock.send(request)
        assert (result.kind, result.code) == (
            ResultKind.RETRYABLE,
            "SERVER_ERROR",
        )
        assert result.provider_message_id is None

    assert mock.unique_messages == 0


def test_AC_CAMP_030_9003_is_permanently_invalid(clock: FakeClock) -> None:
    """Given the 9003 suffix, when sent, then the result is a permanent failure."""
    result = MockMessenger(clock).send(_request("key-9003", "+15555559003"))

    assert (result.kind, result.code) == (
        ResultKind.PERMANENT,
        "INVALID_NUMBER",
    )
    assert result.provider_message_id is None


def test_AC_CAMP_030_9004_rate_limited_then_accepts(clock: FakeClock) -> None:
    """Given the 9004 suffix, when sent twice, then the first is rate-limited with retry_after."""
    mock = MockMessenger(clock)
    request = _request("key-9004", "+15555559004")

    first = mock.send(request)
    second = mock.send(request)

    assert (first.kind, first.code) == (ResultKind.RETRYABLE, "RATE_LIMITED")
    assert first.retry_after_seconds == 3.0
    assert second.kind == ResultKind.ACCEPTED


def test_AC_CAMP_030_9005_fails_by_receipt(clock: FakeClock) -> None:
    """Given the 9005 suffix, when accepted, then a failed receipt is produced later."""
    mock = MockMessenger(clock)
    result = mock.send(_request("key-9005", "+15555559005"))
    assert result.kind == ResultKind.ACCEPTED

    clock.advance(2)
    receipts = mock.poll_receipts()

    assert [receipt.status for receipt in receipts] == ["failed"]
    assert receipts[0].error_code == "DELIVERY_FAILED"
    assert receipts[0].provider_message_id == result.provider_message_id
    assert receipts[0].timestamp == clock.now()


def test_AC_CAMP_030_generic_accepted_receipts_delivered_then_read(
    clock: FakeClock,
) -> None:
    """Given an even last digit, when accepted, then delivered and read receipts arrive on time."""
    mock = MockMessenger(clock)
    result = mock.send(_request("key-even", "+15555550100"))
    assert result.kind == ResultKind.ACCEPTED
    assert mock.poll_receipts() == []

    clock.advance(2)
    delivered = mock.poll_receipts()
    assert [receipt.status for receipt in delivered] == ["delivered"]
    assert delivered[0].timestamp == clock.now()
    assert mock.poll_receipts() == []

    clock.advance(3)
    read = mock.poll_receipts()
    assert [receipt.status for receipt in read] == ["read"]
    assert read[0].timestamp == clock.now()
    assert mock.poll_receipts() == []


def test_AC_CAMP_030_odd_last_digit_has_no_read_receipt(
    clock: FakeClock,
) -> None:
    """Given an odd last digit, when accepted, then only the delivered receipt arrives."""
    mock = MockMessenger(clock)
    mock.send(_request("key-odd", "+15555550101"))

    clock.advance(5)

    assert [receipt.status for receipt in mock.poll_receipts()] == ["delivered"]


def test_AC_CAMP_030_idempotent_acceptance_does_not_duplicate_receipts(
    clock: FakeClock,
) -> None:
    """Given an accepted key, when repeated, then no duplicate receipts are queued."""
    mock = MockMessenger(clock)
    request = _request("key-repeat", "+15555550100")

    first = mock.send(request)
    second = mock.send(request)
    assert first.provider_message_id == second.provider_message_id

    clock.advance(5)
    receipts = mock.poll_receipts()

    assert [receipt.status for receipt in receipts] == ["delivered", "read"]
    assert mock.unique_messages == 1


def test_AC_CAMP_030_message_ids_are_deterministic_and_unique(
    clock: FakeClock,
) -> None:
    """Given the same key, when sent from a new instance, then the message id is stable."""
    first = MockMessenger(clock).send(_request("same-key", "+15555550100"))
    second = MockMessenger(clock).send(_request("same-key", "+15555550100"))
    other = MockMessenger(clock).send(_request("other-key", "+15555550100"))

    assert first.provider_message_id == second.provider_message_id
    assert first.provider_message_id != other.provider_message_id


def test_AC_CAMP_030_errors_do_not_contain_the_full_phone(
    clock: FakeClock,
) -> None:
    """Given provider errors, when returned, then no message contains the full phone."""
    mock = MockMessenger(clock)

    for key, phone in (
        ("k1", "+15555559001"),
        ("k2", "+15555559002"),
        ("k3", "+15555559003"),
    ):
        result = mock.send(_request(key, phone))
        assert phone not in (result.message or "")


def test_flush_receipts_returns_everything_immediately(
    clock: FakeClock,
) -> None:
    """Given queued receipts, when flushed, then all are returned and the queue is empty."""
    mock = MockMessenger(clock)
    mock.send(_request("flush-key", "+15555550100"))

    assert [receipt.status for receipt in mock.flush_receipts()] == [
        "delivered",
        "read",
    ]
    assert mock.poll_receipts() == []
