from datetime import UTC, datetime

from .errors import InvalidEventError, InvalidTimestampError

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
FIELDS = ("timestamp", "level", "source", "message")


def vremya(s, filename="<stream>", line=1):
    # проверяем, что есть и дата, и время
    if not isinstance(s, str) or ("T" not in s and "t" not in s and " " not in s):
        raise InvalidTimestampError("поле timestamp: нужна дата и время ISO 8601", filename, line)
    try:
        t = datetime.fromisoformat(s.replace("z", "+00:00"))
        # без часового пояса считаем время по UTC
        if t.tzinfo is None:
            t = t.replace(tzinfo=UTC)
        return t.astimezone(UTC)
    except (ValueError, OverflowError) as err:
        raise InvalidTimestampError(f"поле timestamp: неверная дата {s!r}", filename, line) from err


class Event:
    def __init__(self, data, filename="<stream>", line=1):
        # сначала проверяем поля
        if not isinstance(data, dict):
            raise InvalidEventError("событие должно быть объектом", filename, line)
        missing = []
        for name in FIELDS:
            if name not in data:
                missing.append(name)
        if missing:
            raise InvalidEventError("нет обязательных полей: " + ", ".join(missing), filename, line)

        self.timestamp = vremya(data["timestamp"], filename, line)
        self.level = data["level"]
        self.source = data["source"]
        self.message = data["message"]

        if not isinstance(self.level, str) or self.level not in LEVELS:
            raise InvalidEventError("поле level: допустимы " + ", ".join(LEVELS), filename, line)
        if not isinstance(self.source, str) or not self.source.strip():
            raise InvalidEventError("поле source: нужна непустая строка", filename, line)
        if not isinstance(self.message, str):
            raise InvalidEventError("поле message: нужна строка", filename, line)
