from datetime import time, timedelta

import pytest

from apps.reservations.rules import ReservationError, slot_times, validate_start
from apps.reservations.tests.factories import future_slot


def test_slot_grid():
    slots = slot_times()

    assert slots[0] == time(10, 0)
    assert slots[-1] == time(21, 0)  # 21:00 + 2 часа = закрытие в 23:00
    assert len(slots) == 23


def test_valid_slot_passes():
    validate_start(future_slot())


@pytest.mark.parametrize(
    ("hour", "minute"),
    [(19, 15), (9, 30), (21, 30), (22, 0)],
)
def test_outside_grid(hour, minute):
    with pytest.raises(ReservationError) as exc:
        validate_start(future_slot(hour=hour, minute=minute))

    assert exc.value.code == "invalid_slot"


def test_seconds_are_not_allowed():
    with pytest.raises(ReservationError) as exc:
        validate_start(future_slot() + timedelta(seconds=30))

    assert exc.value.code == "invalid_slot"


def test_too_soon():
    start = future_slot()

    with pytest.raises(ReservationError) as exc:
        validate_start(start, now=start - timedelta(minutes=10))

    assert exc.value.code == "too_soon"


def test_exactly_min_lead_time_is_ok():
    start = future_slot()

    validate_start(start, now=start - timedelta(minutes=30))


def test_too_far():
    start = future_slot()

    with pytest.raises(ReservationError) as exc:
        validate_start(start, now=start - timedelta(days=31))

    assert exc.value.code == "too_far"
