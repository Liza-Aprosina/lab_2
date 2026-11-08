import csv
import json

from .errors import UnsupportedFormatError


def write(stats, stream, fmt="json", top_n=5):
    data = stats.report(top_n)
    if fmt == "json":
        # ensure_ascii=False оставляет кириллицу
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    elif fmt == "csv":
        out = csv.writer(stream)
        out.writerow(["section", "key", "value"])
        for key in ("total_events", "skipped_rows", "first_timestamp", "last_timestamp"):
            out.writerow(["summary", key, data[key]])
        for level, count in data["by_level"].items():
            out.writerow(["by_level", level, count])
        for source, count in data["by_source"].items():
            out.writerow(["by_source", source, count])
        for row in data["top_error_sources"]:
            out.writerow(["top_error_sources", row["source"], row["count"]])
    else:
        raise UnsupportedFormatError(f"неподдерживаемый формат отчёта: {fmt}")
