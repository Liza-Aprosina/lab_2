import csv
import io
import json

import pytest


@pytest.fixture
def record():
    return {
        "timestamp": "2026-01-02T12:30:00Z",
        "level": "INFO",
        "source": "сервис",
        "message": "Привет, мир!",
    }


def encode(records, format):
    if format == "jsonl":
        return "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=["timestamp", "level", "source", "message"])
    writer.writeheader()
    writer.writerows(records)
    return stream.getvalue()
