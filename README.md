# ЛР 2. Анализ файлов с событиями

Апросина Елизавета Денисовна
## Как запустить

В папке проекта:

```bash
./run.sh analyze examples/events.jsonl --format jsonl
./run.sh analyze examples/events.csv --format csv --output report.json
```

Несколько файлов передаются подряд:

```bash
./run.sh analyze first.jsonl second.jsonl --format jsonl --output report.json
```
## Дополнительные возможности

Фильтры: начало и конец интервала включаются, `--level` и `--source` можно повторять.
Разные фильтры работают одновременно. Неверные записи проверяются до фильтров.

```bash
./run.sh analyze examples/events.jsonl --format jsonl \
  --since 2026-01-02T10:00:00Z --until 2026-01-02T10:02:00Z \
  --level ERROR --level CRITICAL --source 'база данных' --top 3
```
## Проверки

Установка для тестов:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
ruff check .
python -m streamstats --help
```
