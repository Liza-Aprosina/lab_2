import argparse
import logging
import os
import sys
import tempfile
from pathlib import Path

from .analysis import analyze
from .errors import CLIConfigurationError, InvalidTimestampError, StreamStatsError
from .models import LEVELS, vremya
from .parsers import get_read
from .report import write

log = logging.getLogger("streamstats")


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CLIConfigurationError(message)


def cli():
    p = Parser(description="Потоковый анализ событий CSV и JSONL")
    commands = p.add_subparsers(dest="command", required=True)
    a = commands.add_parser("analyze", help="обработать файлы")
    a.add_argument("inputs", metavar="INPUT", nargs="+")
    a.add_argument("--format", required=True, help="формат входа: csv или jsonl")
    a.add_argument("--output", type=Path, help="куда сохранить отчёт (по умолчанию stdout)")
    a.add_argument("--skip-invalid", action="store_true", help="пропускать неверные записи")
    a.add_argument("--report-format", choices=("json", "csv"), default="json")
    a.add_argument("--top", type=int, default=5, help="сколько источников ошибок вывести")
    a.add_argument("--since", help="начало интервала ISO 8601")
    a.add_argument("--until", help="конец интервала ISO 8601")
    a.add_argument("--level", action="append", choices=LEVELS, help="можно повторять")
    a.add_argument("--source", action="append", help="имя источника; можно повторять")
    return p


def check_out(output, inputs):
    # не даем затереть входной файл
    for name in inputs:
        source = Path(name)
        if output.resolve() == source.resolve():
            raise CLIConfigurationError("файл отчёта не должен совпадать с входным файлом")
        if output.exists() and source.exists() and output.samefile(source):
            raise CLIConfigurationError("файл отчёта не должен совпадать с входным файлом")


def save(output, stats, fmt, top_n):
    # сначала пишем во временный файл
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=output.parent, delete=False
        ) as stream:
            tmp = Path(stream.name)
            write(stats, stream, fmt, top_n)
        os.replace(tmp, output)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def main(argv=None):
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    try:
        args = cli().parse_args(argv)
        get_read(args.format)
        if args.top < 1:
            raise CLIConfigurationError("--top должен быть положительным целым числом")

        # разбираем границы времени, если их задали
        since = None
        until = None
        try:
            if args.since is not None:
                since = vremya(args.since)
            if args.until is not None:
                until = vremya(args.until)
        except InvalidTimestampError as err:
            raise CLIConfigurationError(f"--since/--until: {err.reason}") from err
        if since is not None and until is not None and since > until:
            raise CLIConfigurationError("--since должен быть не позже --until")

        if args.output is not None:
            check_out(args.output, args.inputs)
        stats = analyze(
            args.inputs, args.format, args.skip_invalid, since, until, args.level, args.source
        )
        if args.output is None:
            write(stats, sys.stdout, args.report_format, args.top)
        else:
            save(args.output, stats, args.report_format, args.top)
        return 0
    except (StreamStatsError, OSError, UnicodeError) as err:
        log.error("%s", err)
        return 2


if __name__ == "__main__":
    sys.exit(main())
