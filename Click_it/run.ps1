$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$env:PYTHONPATH = (Join-Path $root "src")
python -m task_repeat
