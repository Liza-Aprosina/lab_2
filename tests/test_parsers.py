import io
import json

import pytest
from conftest import encode

from streamstats.errors import InvalidEventError, InvalidTimestampError, UnsupportedFormatError
from streamstats.parsers import ParseStats, get_read, read_csv, read_json, reg


@pytest.mark.parametrize("format", ["csv", "jsonl"])
def test_parser_unicode_and_empty_message(record, format):
    records = [record, {**record, "message": ""}]
    events = list(get_read(format)(io.StringIO(encode(records, format))))
    assert len(events) == 2
    assert events[0].message == "Привет, мир!"
    assert events[0].source == "сервис"
    assert events[1].message == ""


@pytest.mark.parametrize("format", ["csv", "jsonl"])
def test_empty_file(format):
    assert list(get_read(format)(io.StringIO(""))) == []


@pytest.mark.parametrize("format", ["csv", "jsonl"])
def test_stop_on_invalid_event(record, format):
    text = encode([record, {**record, "level": "BAD"}, record], format)
    events = get_read(format)(io.StringIO(text), filename="input.log")
    next(events)
    with pytest.raises(InvalidEventError, match="input.log") as info:
        next(events)
    assert info.value.line == (3 if format == "csv" else 2)


@pytest.mark.parametrize("format", ["csv", "jsonl"])
def test_skip_invalid_event(record, format, caplog):
    text = encode([record, {**record, "timestamp": "bad"}, record], format)
    stats = ParseStats()
    result = list(
        get_read(format)(io.StringIO(text), skip_invalid=True, stats=stats, filename="input")
    )
    assert len(result) == 2
    assert stats.skipped_rows == 1
    assert "timestamp" in caplog.text
    assert caplog.records[0].levelname == "WARNING"


def test_json_error_at_line_seven(record):
    stream = io.StringIO(encode([record] * 6, "jsonl") + "broken\n")
    with pytest.raises(InvalidEventError) as info:
        list(read_json(stream, filename="seven.jsonl"))
    assert info.value.line == 7


@pytest.mark.parametrize("bad_line", ["{", "[]", "null", "42", '"string"', "", " "])
def test_bad_json_lines_recover(record, bad_line):
    text = bad_line + "\n" + json.dumps(record) + "\n"
    stats = ParseStats()
    assert len(list(read_json(io.StringIO(text), skip_invalid=True, stats=stats))) == 1
    assert stats.skipped_rows == 1


def test_csv_multiline_and_line_numbers(record):
    record["message"] = 'строка 1\nстрока 2, "кавычки"'
    text = encode([record, {**record, "timestamp": "bad"}], "csv")
    events = read_csv(io.StringIO(text, newline=""))
    assert next(events).message == record["message"]
    with pytest.raises(InvalidTimestampError) as info:
        next(events)
    assert info.value.line == 4


@pytest.mark.parametrize(
    "header", ["timestamp,level,source\n", "timestamp,level,source,message,message\n", '"bad\n']
)
def test_csv_invalid_header_is_fatal(header):
    with pytest.raises(InvalidEventError, match="заголовок CSV"):
        list(read_csv(io.StringIO(header), skip_invalid=True))


@pytest.mark.parametrize("bad_row", ["1,2\n", '"unterminated\n'])
def test_csv_syntax_and_field_count(bad_row):
    text = "timestamp,level,source,message\n" + bad_row
    with pytest.raises(InvalidEventError):
        list(read_csv(io.StringIO(text)))
    stats = ParseStats()
    assert list(read_csv(io.StringIO(text), skip_invalid=True, stats=stats)) == []
    assert stats.skipped_rows == 1


class StreamingOnly(io.StringIO):
    """Запрещаем чтение всего файла."""

    def read(self, size=-1):
        if size < 0:
            raise AssertionError("unbounded read")
        return super().read(size)

    def readlines(self, hint=-1):
        raise AssertionError("readlines")


@pytest.mark.parametrize("format", ["csv", "jsonl"])
def test_parsers_are_lazy_and_streaming(record, format):
    text = encode([record, {**record, "timestamp": "bad"}], format)
    stream = StreamingOnly(text)
    events = get_read(format)(stream)
    assert iter(events) is events
    assert stream.tell() == 0
    assert next(events).source == "сервис"
    assert stream.tell() < len(text)
    with pytest.raises(InvalidTimestampError):
        next(events)


def test_registry(monkeypatch):
    from streamstats import parsers

    monkeypatch.setattr(parsers, "PARSERS", dict(parsers.PARSERS))
    reg("custom", read_json)
    assert get_read("custom") is read_json
    with pytest.raises(ValueError):
        reg("custom", read_json)
    with pytest.raises(ValueError):
        reg("", read_json)
    with pytest.raises(UnsupportedFormatError):
        get_read("missing")
