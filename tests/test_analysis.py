import csv
import io
import json

import pytest
from conftest import encode

from streamstats.analysis import Stats, analyze, filtr
from streamstats.models import LEVELS, Event, vremya
from streamstats.report import write


@pytest.mark.parametrize("format", ["csv", "jsonl"])
def test_empty_report(tmp_path, format):
    path = tmp_path / "empty"
    path.touch()
    report = analyze([path], format).report()
    assert report == {
        "total_events": 0,
        "by_level": dict.fromkeys(LEVELS, 0),
        "by_source": {},
        "top_error_sources": [],
        "first_timestamp": None,
        "last_timestamp": None,
        "skipped_rows": 0,
    }


def test_equivalent_formats_multiple_files_and_unchanged_inputs(tmp_path, record):
    records = [
        record,
        {**record, "level": "ERROR", "timestamp": "2025-12-31T23:00:00-03:00"},
        {**record, "level": "CRITICAL", "source": "другой"},
    ]
    reports = []
    for format in ("csv", "jsonl"):
        paths = [tmp_path / f"a.{format}", tmp_path / f"b.{format}"]
        paths[0].write_text(encode(records[:2], format), encoding="utf-8")
        paths[1].write_text(encode(records[2:], format), encoding="utf-8")
        original = [p.read_bytes() for p in paths]
        reports.append(analyze(paths, format).report())
        assert [p.read_bytes() for p in paths] == original
    assert reports[0] == reports[1]
    data = reports[0]
    assert data["total_events"] == 3
    assert data["by_source"] == {"сервис": 2, "другой": 1}
    assert data["by_level"]["ERROR"] == 1
    assert data["by_level"]["CRITICAL"] == 1
    assert data["first_timestamp"] == "2026-01-01T02:00:00+00:00"
    assert data["last_timestamp"] == "2026-01-02T12:30:00+00:00"


def test_top_five_deterministic_and_top_n(record):
    stats = Stats()
    for source in "gfedcba":
        stats.add(Event({**record, "level": "ERROR", "source": source}))
    stats.add(Event({**record, "level": "CRITICAL", "source": "g"}))
    # INFO не увеличивает число ошибок.
    stats.add(Event({**record, "source": "f"}))
    assert stats.report()["top_error_sources"] == [
        {"source": "g", "count": 2},
        *[{"source": name, "count": 1} for name in "abcd"],
    ]
    assert len(stats.report(2)["top_error_sources"]) == 2
    with pytest.raises(ValueError):
        stats.report(0)


def test_merge(record):
    first, second, combined = Stats(), Stats(), Stats()
    for index, stats in enumerate((first, second)):
        event = Event({**record, "level": "ERROR", "source": str(index)})
        stats.add(event)
        combined.add(event)
    second.skipped_rows = 2
    combined.skipped_rows = 2
    first.merge(second)
    first.merge(Stats())
    assert first.report() == combined.report()


def test_filters_are_lazy_and_inclusive(record):
    def events():
        yield Event(record)
        raise RuntimeError("следующее событие пока не запрашивали")

    instant = vremya(record["timestamp"])
    filtered = filtr(
        events(),
        since=instant,
        until=instant,
        levels=["INFO"],
        sources=["сервис"],
    )
    assert next(filtered).source == "сервис"
    with pytest.raises(RuntimeError):
        next(filtered)


def test_skips_counted_even_when_filtered(tmp_path, record):
    path = tmp_path / "events.jsonl"
    path.write_text(encode([record, {**record, "level": "BAD"}], "jsonl"), encoding="utf-8")
    stats = analyze([path], "jsonl", skip_invalid=True, levels=["ERROR"])
    assert stats.total == 0
    assert stats.skipped_rows == 1


def test_reports_share_calculations(record):
    stats = Stats()
    stats.add(Event({**record, "level": "ERROR"}))
    json_output, csv_output = io.StringIO(), io.StringIO()
    write(stats, json_output)
    write(stats, csv_output, fmt="csv")
    assert "сервис" in json_output.getvalue()
    data = json.loads(json_output.getvalue())
    rows = list(csv.DictReader(io.StringIO(csv_output.getvalue())))
    assert {"section": "summary", "key": "total_events", "value": str(data["total_events"])} in rows
    assert {"section": "by_source", "key": "сервис", "value": "1"} in rows


def test_bom_input(tmp_path, record):
    for format in ("csv", "jsonl"):
        path = tmp_path / format
        path.write_text(encode([record], format), encoding="utf-8-sig")
        assert analyze([path], format).total == 1
