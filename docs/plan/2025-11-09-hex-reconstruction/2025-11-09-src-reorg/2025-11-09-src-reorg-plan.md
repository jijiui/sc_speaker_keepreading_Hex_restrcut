# 2025-11-09 SRC Reorg Plan

## Objectives
- Consolidate all executable/importable code into `src/` so future packaging uses a single namespace (`app`).
- Provide a deterministic migration path (move → update imports → validate → document).

## Phases
1. **Prepare `src/` Layout**
   - Create `src/app/` and move `core/`, `infra/`, `ui/`, `pv_z_时间轴播报器（python_py_qt_6_）.py` (renamed `main.py`) as well as OCR helpers.
   - Ensure each moved module has an English header comment.
   - Risk: missing files after move → Mitigation: track via `git status`.

2. **Adjust Imports & Tooling**
   - Update every module/test/script to import via `app.*` or `from app.core...`.
   - Scripts (`manual_regression_stage0.py`, `smoke_timeline.py`) prepend `src` to `sys.path`.
   - README/PowerShell helper / VS Code `.env` document `PYTHONPATH=src`.
   - Risk: stale imports → run lint/unit tests immediately after changes.

3. **Validate & Document**
   - Run unit tests + Stage 0/CLI smoke scripts inside `.venv` with `PYTHONPATH=src`.
   - Update `docs/重构任务日志.md` and Stage 0 regression doc with UTC timestamps.
   - Risk: forgetting documentation → enforce checklist before closing the stage.

## Exit Criteria
- `python -m app.bootstrap`（原 `python -m app.main`）可直接从 `src` 命名空间运行。
- All scripts/tests use the new import paths.
- `docs/plan/2025-11-09-src-reorg-*` 和 `docs/重构任务日志.md` 记录完成。
