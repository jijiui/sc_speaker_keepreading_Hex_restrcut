# Run the PvZ timeline speaker GUI from Powershell.
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Join-Path $scriptRoot ".."
$env:PYTHONPATH = (Resolve-Path (Join-Path $repoRoot "src")).Path
python -m app.main
