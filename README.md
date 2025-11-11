# PvZ Timeline Speaker

This repo hosts a PyQt6-based assistant that loads timeline files (CSV/TXT/Excel) for StarCraft/PvZ strategies, pairs them with OCR/TTS, and provides countdown/announcement features. The codebase follows a hexagonal-style structure under `src/`.

## Repo Structure

```
src/
  app/
    core/       # domain models/services (TimelineService, ports.)
    infra/      # adapters: file repository, OCR agents, preference store
    ui/         # PyQt widgets/state/controller helpers
    main.py     # MainWindow entry point
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

## Setup
1. **Locate `.venv`**  
   - Check the repo root for an existing `.venv`. If it is missing, search parent directories until you reach the filesystem root.  
   - Record the `Scripts/` (Windows) or `bin/` (Unix) path once found. If `.venv` truly does not exist, stop and create/ask before proceeding.
2. **Activate the virtual environment** (run the matching command for your shell):  
   - PowerShell / pwsh: `& "<venv>/Scripts/Activate.ps1"`  
   - Windows CMD: `"<venv>\Scripts\activate.bat"`  
   - bash/zsh: `. "<venv>/bin/activate"`  
   Run every command inside an activated shell. If you are firing single-shot commands (CI, non-interactive shells, etc.), wrap activation and the command together, for example:  
   ```powershell
   & { & "..\.venv\Scripts\Activate.ps1"; $env:PYTHONPATH = "$PWD\src"; python -m unittest ... }
   ```
3. **Install deps & set PYTHONPATH** (still inside the venv):
   ```powershell
   pip install -r requirements.txt
   # Ensure PYTHONPATH points to src when running outside VS Code
   $env:PYTHONPATH = "$PWD\src"
   ```

## Running the GUI
```powershell
$env:PYTHONPATH = "$PWD\src"      # skip if VS Code already sets this
python -m app.bootstrap           # preferred entry
# legacy entry (still supported):
python -m app.main
# or use helper script (wraps bootstrap)
powershell -ExecutionPolicy Bypass -File scripts/run_app.ps1
```

## Tests & Smoke
1. Re-run the **Setup** checklist before testing: the repo `.venv` must be active and `PYTHONPATH` must point to `src/`. If your shell does not persist state, fold activation into every command.
2. Execute the following PowerShell commands in order, each wrapping “activate + command” inside one block:
   ```powershell
   & { & "..\.venv\Scripts\Activate.ps1"; $env:PYTHONPATH = "$PWD\src"; python -m unittest tests.test_timeline_service tests.test_file_repository }
   & { & "..\.venv\Scripts\Activate.ps1"; $env:PYTHONPATH = "$PWD\src"; python scripts/manual_regression_stage0.py }
   & { & "..\.venv\Scripts\Activate.ps1"; $env:PYTHONPATH = "$PWD\src"; python scripts/smoke_timeline.py --tick 2000 --lead 3000 --early }
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
| Agent Alex (2025-11-09 16:30:00-22:45:00 UTC+08:00) | Migrated codebase to `src/app` layout, added repository tests + CI workflow, updated README/run scripts, documented Stage 0 reruns, and published refactor instruction/plan/tasks for upcoming Main UI split. |
| Agent Noname (2025-11-09 22:45:00- 2025-11-10 00:00:30 UTC+08:00) | updated README, finished A1 and published. |
| Evan (2025-11-11 12:30:00 UTC+01:00) | Added encoding guards, mocked Qt dialogs in tests, and clarified Stage-0 behavior. |
