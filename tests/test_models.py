from datetime import UTC, datetime

import pytest

from streamstats.errors import InvalidEventError, InvalidTimestampError
from streamstats.models import LEVELS, Event, vremya


@pytest.mark.parametrize("level", LEVELS)
def test_all_levels(record, level):
    record["level"] = level
    assert Event(record).level == level


@pytest.mark.parametrize("field", ["timestamp", "level", "source", "message"])
def test_required_fields(record, field):
    del record[field]
    with pytest.raises(InvalidEventError, match=field):
        Event(record)


@pytest.mark.parametrize(
    ("field", "value"),
    [("level", "NOTICE"), ("level", []), ("source", "  "), ("source", 0), ("message", None)],
)
def test_invalid_fields(record, field, value):
    record[field] = value
    with pytest.raises(InvalidEventError, match=field):
        Event(record)


@pytest.mark.parametrize("value", [None, 123, "", "yesterday", "2026-01-02", "2026-02-30T00:00:00"])
def test_invalid_timestamp(value):
    with pytest.raises(InvalidTimestampError, match="timestamp") as info:
        vremya(value, filename="events", line=7)
    assert info.value.filename == "events"
    assert info.value.line == 7


@pytest.mark.parametrize(
    "value", ["2026-01-02T12:30:00Z", "2026-01-02T15:30:00+03:00", "2026-01-02T12:30:00"]
)
def test_timestamp_normalized_to_utc(value):
    assert vremya(value) == datetime(2026, 1, 2, 12, 30, tzinfo=UTC)


def test_empty_message_is_valid(record):
    record["message"] = ""
    assert Event(record).message == ""
