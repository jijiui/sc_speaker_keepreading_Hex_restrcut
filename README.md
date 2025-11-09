# PvZ Timeline Speaker

## Run

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH = "$PWD\src"
python -m app.main
```

Alternatively use `scripts/run_app.ps1`, which configures `PYTHONPATH` automatically.

## Tests

```
$env:PYTHONPATH = "$PWD\src"
python -m unittest tests.test_timeline_service tests.test_file_repository
```

## Smoke Checks

```
$env:PYTHONPATH = "$PWD\src"
python scripts/manual_regression_stage0.py
python scripts/smoke_timeline.py --tick 2000 --lead 3000 --early
```
