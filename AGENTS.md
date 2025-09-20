# Repository Guidelines

## Project Structure & Module Organization
- `yt_dlp/` — core Python package. Extractors live in `yt_dlp/extractor/`; entrypoint is `yt_dlp/__main__.py`.
- `test/` — pytest-based tests and testdata.
- `devscripts/` — helper scripts for building docs, completions, and lazy extractors.
- `completions/`, `yt-dlp.1`, `README*.md/txt` — generated assets.
- `Makefile`, `pyproject.toml` — build, lint, and test configuration.

## Build, Test, and Development Commands
- `make yt-dlp` — build the standalone zipapp `yt-dlp`.
- `make test` — run pytest (with warnings as errors) and style checks.
- `make ot` or `make offlinetest` — run tests excluding network-marked tests.
- `make codetest` — run fast linters only (ruff + autopep8 diff).
- `make completions` — regenerate shell completions; `make doc` — docs/manpage/issue templates.
- Hatch (optional): `hatch run hatch-test:run` and `hatch run hatch-static-analysis:lint-check`.

## Coding Style & Naming Conventions
- Language: Python 3.9+; 4-space indentation; max line length 120.
- Quotes: single quotes for code, double quotes for docstrings (ruff config).
- Prefer explicit imports; follow first-party import grouping (configured in ruff isort).
- Run `make codetest` before committing. Avoid banned compat helpers; use standard library or `yt_dlp.utils` where noted in `pyproject.toml`.
- Extractors: place under `yt_dlp/extractor/`, name `*_extractor.py` when adding groups; class names in `CamelCase` ending with `IE`.

## Testing Guidelines
- Framework: pytest. Mark networked tests with `@pytest.mark.download`.
- Quick runs: `pytest -m "not download"` or `make ot`.
- Add tests in `test/` mirroring module paths; name files `test_*.py` and functions `test_*`.
- Keep tests deterministic; use fixtures/testdata instead of live network where possible.

## Commit & Pull Request Guidelines
- Commits: imperative mood, concise scope prefixes when helpful (e.g., `extractor(twitch): fix clip parsing`).
- Before PR: run `make test` and update generated assets if affected (`make completions`, `make doc`).
- PRs should include: clear description, rationale, reproduction steps, and tests for behavior changes. Link related issues.

## Security & Configuration Tips
- Do not hardcode credentials or tokens. Place secrets outside repo and mock in tests.
- Use `make offlinetest` for CI-like runs without network.

## Web UI Runbook (Local)
- Prereqs: Python 3.9+, `ffmpeg` in PATH.
- Build CLI once: `make yt-dlp` (creates `./yt-dlp`).
- Virtualenv: `python3 -m venv .venv && .venv/bin/pip install -U pip Flask gunicorn`.
- Start (single worker only):
  - `.venv/bin/gunicorn -w 1 -b 127.0.0.1:8080 webui.app:app --pid webui/.webui.pid --access-logfile webui/webui.log --error-logfile webui/webui.log --daemon`
- Reason for `-w 1`: the Web UI stores task state in-process (`_tasks` dict). Multiple workers will not share state and cause `/api/status/<id>` to return 404 intermittently.
- Environment vars:
  - `YTDLP_WEBUI_DOWNLOAD_DIR` (default `./webui_downloads`)
  - `YTDLP_WEBUI_HOST` (default `127.0.0.1`)
  - `YTDLP_WEBUI_PORT` (default `8080`)
- Manage:
  - Stop: `kill $(cat webui/.webui.pid)`
  - Restart: `kill -HUP $(cat webui/.webui.pid)`
  - Check: `ps -p $(cat webui/.webui.pid) -o pid,comm,etime` and `lsof -nP -iTCP:8080 -sTCP:LISTEN`
  - Logs: `tail -f webui/webui.log`
- Troubleshooting:
  - Status 404 after creating a task → ensure single worker (`-w 1`).
  - Audio extraction fails → install/verify `ffmpeg`.
  - Cannot download files from `/files/...` → path is sanitized; only files inside `YTDLP_WEBUI_DOWNLOAD_DIR` are served.
