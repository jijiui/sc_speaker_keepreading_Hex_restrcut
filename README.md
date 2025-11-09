# PvZ Timeline Speaker

This repo hosts a PyQt6-based assistant that loads timeline files (CSV/TXT/Excel) for StarCraft/PvZ strategies, pairs them with OCR/TTS, and provides countdown/announcement features. The codebase follows a hexagonal-style structure under `src/`.

## Repo Structure

```
src/
  app/
    core/       # domain models/services (TimelineService, ports…)
    infra/      # adapters: file repository, OCR agents, preference store
    ui/         # Qt components, bindings, state controller
    controllers/# (planned) controllers for timeline/OCR logic
    main.py     # MainWindow definition
    bootstrap.py (planned) # DI/entry wiring
docs/
  plan/         # instruction/plan/tasks triplets (per agent rules)
scripts/
  manual_regression_stage0.py # UC-01~07 smoke harness
  smoke_timeline.py           # CLI check for announcement logic
  run_app.ps1                 # PowerShell helper (sets PYTHONPATH)
tests/
  test_timeline_service.py
  test_file_repository.py
```

## Prerequisites
- Python 3.9+ (Windows focus; OCR uses OpenCV)
- Recommended: create a project-specific virtual environment (`python -m venv .venv`)
- If running inside VS Code, `.env` already sets `PYTHONPATH=${workspaceFolder}\src`

## Setup
```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Ensure PYTHONPATH points to src when running outside VS Code
$env:PYTHONPATH = "$PWD\src"
```

## Running the GUI
```powershell
$env:PYTHONPATH = "$PWD\src"  # skip if using VS Code with .env
python -m app.main            # current entry
# or use helper script
powershell -ExecutionPolicy Bypass -File scripts/run_app.ps1
```
> Upcoming refactors will introduce `python -m app.bootstrap` as the unified entry point—watch the plan docs for updates.

## Tests & Smoke
```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest tests.test_timeline_service tests.test_file_repository
python scripts/manual_regression_stage0.py
python scripts/smoke_timeline.py --tick 2000 --lead 3000 --early
```

CI (`.github/workflows/ci.yml`) runs the same suite on Windows: install deps → unit tests → smoke CLI.

## Documentation & Plans
- `docs/重构任务日志.md` – append-only log with UTC timestamps (`UTC±HH:MM`).
- Proposal/plan/tasks must follow agent rules: `docs/plan/<date>-<name>/{instruction|plan|tasks}.md`.
- Stage‑0 regression results maintained in `docs/阶段0-用例回归记录.md`.

## Contribution Workflow
1. Activate `.venv`, set `PYTHONPATH=src`.
2. Follow agent instructions (English comments, commit per task, update docs/logs).
3. For new refactors, add instruction/plan/tasks triplet under `docs/plan/`.
4. Run unit tests + smoke scripts before every commit/push.
5. Update `docs/重构任务日志.md` with UTC timestamp describing the change.

Need orientation? Start by reading:
- `docs/plan/2025-11-09-main-ui/{instruction,plan,tasks}.md`
- `docs/plan/2025-11-09-src-reorg/{instruction,plan,tasks}.md`

## Agent Timeline

| Agent (Name & Period) | Summary |
| --- | --- |
| Agent Alex (2025-11-09 16:30:00–22:45:00 UTC+08:00) | Migrated codebase to `src/app` layout, added repository tests + CI workflow, updated README/run scripts, documented Stage 0 reruns, and published refactor instruction/plan/tasks for upcoming Main UI split. |
