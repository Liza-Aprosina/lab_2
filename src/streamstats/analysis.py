from pathlib import Path

from .models import LEVELS
from .parsers import ParseStats, get_read


class Stats:
    def __init__(self):
        self.total = 0
        self.skipped_rows = 0
        self.levels = {}
        for level in LEVELS:
            self.levels[level] = 0
        self.sources = {}
        self.errors = {}
        self.first = None
        self.last = None

    def add(self, event):
        # обновляем счетчики
        self.total += 1
        self.levels[event.level] += 1
        name = event.source
        if name not in self.sources:
            self.sources[name] = 0
        self.sources[name] += 1
        if event.level in ("ERROR", "CRITICAL"):
            if name not in self.errors:
                self.errors[name] = 0
            self.errors[name] += 1
        if self.first is None or event.timestamp < self.first:
            self.first = event.timestamp
        if self.last is None or event.timestamp > self.last:
            self.last = event.timestamp

    def merge(self, other):
        # объединяем две готовые статистики
        self.total += other.total
        self.skipped_rows += other.skipped_rows
        for level in LEVELS:
            self.levels[level] += other.levels[level]
        for name, count in other.sources.items():
            if name not in self.sources:
                self.sources[name] = 0
            self.sources[name] += count
        for name, count in other.errors.items():
            if name not in self.errors:
                self.errors[name] = 0
            self.errors[name] += count
        if other.first is not None:
            if self.first is None or other.first < self.first:
                self.first = other.first
        if other.last is not None:
            if self.last is None or other.last > self.last:
                self.last = other.last

    def report(self, top_n=5):
        if top_n < 1:
            raise ValueError("top_n должен быть положительным")
        # минус нужен, чтобы большие счетчики шли первыми
        top = []
        for name, count in self.errors.items():
            top.append((-count, name))
        top.sort()
        top_errors = []
        for count, name in top[:top_n]:
            top_errors.append({"source": name, "count": -count})

        # источники выводим по алфавиту
        sources = {}
        for name in sorted(self.sources):
            sources[name] = self.sources[name]
        first = None
        last = None
        if self.first is not None:
            first = self.first.isoformat()
        if self.last is not None:
            last = self.last.isoformat()
        return {
            "total_events": self.total,
            "by_level": self.levels.copy(),
            "by_source": sources,
            "top_error_sources": top_errors,
            "first_timestamp": first,
            "last_timestamp": last,
            "skipped_rows": self.skipped_rows,
        }


def filtr(events, since=None, until=None, levels=None, sources=None):
    # границы времени тоже включаем
    for event in events:
        if since is not None and event.timestamp < since:
            continue
        if until is not None and event.timestamp > until:
            continue
        if levels is not None and event.level not in levels:
            continue
        if sources is not None and event.source not in sources:
            continue
        yield event


def analyze(inputs, fmt, skip_invalid=False, since=None, until=None, levels=None, sources=None):
    reader = get_read(fmt)
    result = Stats()
    for filename in inputs:
        path = Path(filename)
        skips = ParseStats()
        # utf-8-sig умеет читать и обычный UTF-8, и файл с BOM
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            events = reader(stream, filename=str(path), skip_invalid=skip_invalid, stats=skips)
            for event in filtr(events, since, until, levels, sources):
                result.add(event)
        result.skipped_rows += skips.skipped_rows
    return result
