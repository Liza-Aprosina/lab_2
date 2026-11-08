import csv
import json
import logging

from .errors import InvalidEventError, UnsupportedFormatError
from .models import FIELDS, Event

log = logging.getLogger(__name__)


class ParseStats:
    def __init__(self):
        self.skipped_rows = 0


def bad(err, skip_invalid, stats):
    # либо останавливаемся, либо считаем пропуск
    if not skip_invalid:
        raise err
    stats.skipped_rows += 1
    log.warning("%s", err)


def read_json(stream, filename="<stream>", skip_invalid=False, stats=None):
    if stats is None:
        stats = ParseStats()
    # читаем по одной строке
    for num, line in enumerate(stream, 1):
        try:
            data = json.loads(line)
            event = Event(data, filename, num)
        except (ValueError, RecursionError) as err:
            bad(InvalidEventError(f"неверный JSON: {err}", filename, num), skip_invalid, stats)
            continue
        except InvalidEventError as err:
            bad(err, skip_invalid, stats)
            continue
        # отдаем событие, а не копим список ;)
        yield event


def read_csv(stream, filename="<stream>", skip_invalid=False, stats=None):
    if stats is None:
        stats = ParseStats()
    reader = csv.reader(stream, strict=True)
    try:
        header = next(reader)
    except StopIteration:
        return
    except csv.Error as err:
        raise InvalidEventError(f"заголовок CSV: {err}", filename, 1) from err

    # в заголовке нужны все поля без повторов
    good = len(set(header)) == len(header)
    for name in FIELDS:
        if name not in header:
            good = False
    if not good:
        raise InvalidEventError(
            "заголовок CSV: нужны уникальные столбцы timestamp, level, source, message",
            filename,
            1,
        )

    while True:
        # одна CSV-запись может занимать несколько строк
        num = reader.line_num + 1
        try:
            row = next(reader)
            if len(row) != len(header):
                raise InvalidEventError(
                    f"CSV: ожидалось {len(header)} полей, получено {len(row)}", filename, num
                )
            data = {}
            for i in range(len(header)):
                data[header[i]] = row[i]
            event = Event(data, filename, num)
        except StopIteration:
            return
        except csv.Error as err:
            bad(InvalidEventError(f"неверный CSV: {err}", filename, num), skip_invalid, stats)
            continue
        except InvalidEventError as err:
            bad(err, skip_invalid, stats)
            continue
        yield event


# имя формата -> функция чтения
PARSERS = {"csv": read_csv, "jsonl": read_json}


def reg(name, reader):
    if not isinstance(name, str) or not name.strip() or not callable(reader):
        raise ValueError("нужны имя формата и функция чтения")
    if name in PARSERS:
        raise ValueError(f"формат {name!r} уже есть")
    PARSERS[name] = reader


def get_read(name):
    if name not in PARSERS:
        raise UnsupportedFormatError(f"неподдерживаемый формат: {name}")
    return PARSERS[name]
