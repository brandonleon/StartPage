# Repository Guidelines

## Project Structure & Module Organization
`main.py` bootstraps the FastAPI app, loads config, and wires Jinja templates. Domain logic lives in `services/` (`db_utils.py` for SQLite access, `app_config.py` for metadata, `io_utils.py` helpers, `tags.py` for tag bookkeeping); keep new helpers module-scoped there. HTML resides in `templates/` (Jinja fragments such as `index.html`, `dashboard.html`, `tags.html`, `stats.html`), while static assets (favicon, CSS, theme/search JS) belong under `static/`. The standalone administrator guide sits in `docs/index.html` and shares the same styles. SQL migrations stay in `sql_scripts/` and the runtime database is stored under `data/links.db`—treat it as disposable state, not source. Low-level service tests live alongside their modules (e.g., `services/test_db_utils.py`), and higher-level FastAPI tests belong at the repo root when added.

## Build, Test, and Development Commands
- `uv sync`: install Python 3.10 dependencies defined in `pyproject.toml`.
- `make develop` (or `uv run uvicorn main:app --reload`): start the API with autoreload for local work.
- `make run`: daemonize the server via `screen`, handy for longer manual testing.
- `make dockerbuild`: build and run the production container, binding `~/.config/startpage` as persistent storage.
- `uv run pytest`: execute the unit suite; pass paths (e.g., `uv run pytest services/test_db_utils.py`) to target modules.

## Coding Style & Naming Conventions
Use 4-space indentation and type hints where feasible (matching existing `services/*.py`). Modules, files, and functions follow `snake_case`; classes keep `PascalCase`. Favor FastAPI path handlers grouped by feature, returning template responses as shown in `main.py`. Keep SQL in multiline strings with uppercase keywords. Before pushing, run `uv run mypy services` if you touch typed modules to keep static checks healthy.

## Testing Guidelines
Unit and integration tests run through `pytest`; mock the database rather than referencing production data. There are no browser-based smoke tests in the tree right now, so HTTP or template-level coverage should be added with conventional test clients (e.g., httpx + FastAPI’s TestClient) when needed. Name new tests `test_<feature>` and colocate FastAPI route tests in repo-root while service-level tests stay under `services/`. Aim to cover new database queries and any Jinja context-building logic.

## Commit & Pull Request Guidelines
Recent history shows short, imperative summaries (`Bootstrap 5.2.2`, `Updating uv.lock`). Follow that style, keep to ~50 characters, and add details in the body if needed. PRs should describe the feature or fix, list test evidence (`uv run pytest`, manual browser checks), and reference any related issue or ticket. Include screenshots or GIFs for UI changes (dashboard, add-link form) so reviewers can validate layout adjustments quickly.
