import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import encode

from streamstats.__main__ import main

SRC = str(Path(__file__).resolve().parents[1] / "src")


def run_cli(tmp_path, *args):
    environment = {**os.environ, "PYTHONPATH": SRC}
    return subprocess.run(
        [sys.executable, "-m", "streamstats", *map(str, args)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


@pytest.mark.parametrize("format", ["csv", "jsonl"])
def test_cli_integration_files_and_report(tmp_path, record, format):
    first, second, output = (tmp_path / name for name in ("first", "second", "report.json"))
    first.write_text(encode([record], format), encoding="utf-8")
    second.write_text(encode([{**record, "level": "ERROR"}], format), encoding="utf-8")
    result = run_cli(tmp_path, "analyze", first, second, "--format", format, "--output", output)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["total_events"] == 2
    assert report["by_source"] == {"сервис": 2}


@pytest.mark.parametrize("skip", [False, True])
@pytest.mark.parametrize("format", ["csv", "jsonl"])
def test_cli_error_modes(tmp_path, record, format, skip):
    path, report = tmp_path / f"events.{format}", tmp_path / "report.json"
    path.write_text(
        encode([record, {**record, "timestamp": "bad"}, record], format), encoding="utf-8"
    )
    report.write_text("старый отчёт", encoding="utf-8")
    args = ["analyze", path, "--format", format, "--output", report]
    result = run_cli(tmp_path, *args, *(["--skip-invalid"] if skip else []))
    assert "timestamp" in result.stderr
    assert str(path) in result.stderr
    assert f"строка {3 if format == 'csv' else 2}" in result.stderr
    if skip:
        assert result.returncode == 0
        assert "WARNING" in result.stderr
        assert json.loads(report.read_text(encoding="utf-8"))["skipped_rows"] == 1
        assert json.loads(report.read_text(encoding="utf-8"))["total_events"] == 2
    else:
        assert result.returncode == 2
        assert report.read_text(encoding="utf-8") == "старый отчёт"


def test_cli_json_stdout_and_warning_stderr(tmp_path, record):
    path = tmp_path / "input"
    path.write_text("bad\n" + encode([record], "jsonl"), encoding="utf-8")
    result = run_cli(tmp_path, "analyze", path, "--format", "jsonl", "--skip-invalid")
    assert result.returncode == 0
    assert json.loads(result.stdout)["total_events"] == 1
    assert "WARNING" in result.stderr


def test_help(tmp_path):
    assert run_cli(tmp_path, "--help").returncode == 0
    assert "--skip-invalid" in run_cli(tmp_path, "analyze", "--help").stdout


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["analyze"],
        ["analyze", "file"],
        ["analyze", "file", "--format", "xml"],
        ["analyze", "file", "--format", "jsonl", "--top", "0"],
        ["analyze", "file", "--format", "jsonl", "--top", "abc"],
        ["analyze", "file", "--format", "jsonl", "--since", "bad"],
        [
            "analyze",
            "file",
            "--format",
            "jsonl",
            "--since",
            "2026-01-03T00:00:00Z",
            "--until",
            "2026-01-01T00:00:00Z",
        ],
        ["analyze", "file", "--format", "jsonl", "--level", "NOTICE"],
    ],
)
def test_configuration_errors_return_two_without_traceback(tmp_path, args):
    result = run_cli(tmp_path, *args)
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_missing_file_returns_two(tmp_path):
    result = run_cli(tmp_path, "analyze", "missing", "--format", "jsonl")
    assert result.returncode == 2
    assert "missing" in result.stderr


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_output_cannot_overwrite_input(tmp_path, record, alias):
    path, output = tmp_path / "input", tmp_path / "output"
    path.write_text(encode([record], "jsonl"), encoding="utf-8")
    original = path.read_bytes()
    if alias == "same":
        output = path
    elif alias == "symlink":
        output.symlink_to(path)
    else:
        output.hardlink_to(path)
    assert main(["analyze", str(path), "--format", "jsonl", "--output", str(output)]) == 2
    assert path.read_bytes() == original


def test_csv_output_and_filters(tmp_path, record):
    path = tmp_path / "input"
    path.write_text(encode([record, {**record, "level": "ERROR"}], "jsonl"), encoding="utf-8")
    result = run_cli(
        tmp_path,
        "analyze",
        path,
        "--format",
        "jsonl",
        "--level",
        "ERROR",
        "--source",
        "сервис",
        "--since",
        record["timestamp"],
        "--until",
        record["timestamp"],
        "--report-format",
        "csv",
    )
    assert result.returncode == 0, result.stderr
    assert "summary,total_events,1" in result.stdout


def test_invalid_utf8_returns_two(tmp_path):
    path = tmp_path / "invalid"
    path.write_bytes(b"\xff\n")
    result = run_cli(tmp_path, "analyze", path, "--format", "jsonl")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
