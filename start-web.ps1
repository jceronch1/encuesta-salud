$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw 'No existe .venv. Ejecute primero: uv venv .venv --python 3.12'
}

Set-Location -LiteralPath $projectRoot
& $pythonExe 'run.py'
