from __future__ import annotations

from datetime import date, datetime

from events_service.app.schemas.event import EventFilters
from events_service.app.services.event_service import _effective_window


def test_filters_prioritize_explicit_range() -> None:
    filters = EventFilters(
        **{"from": datetime(2026, 3, 1, 10, 0, 0)},
        **{"to": datetime(2026, 3, 2, 10, 0, 0)},
        month="2026-03",
    )
    start, end = _effective_window(filters)

    assert start is not None and end is not None
    assert start.year == 2026 and start.month == 3 and start.day == 1
    assert end.year == 2026 and end.month == 3 and end.day == 2


def test_filters_support_month_shortcut() -> None:
    filters = EventFilters(month="2026-03")
    start, end = _effective_window(filters)

    assert start is not None and end is not None
    assert start.month == 3
    assert end.month == 4


def test_filters_support_week_shortcut() -> None:
    filters = EventFilters(week_start=date(2026, 3, 23))
    start, end = _effective_window(filters)

    assert start is not None and end is not None
    assert end.toordinal() - start.toordinal() == 7

