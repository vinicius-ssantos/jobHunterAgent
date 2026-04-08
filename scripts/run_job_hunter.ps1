param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$JobHunterArgs
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$pythonExecutable = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExecutable)) {
    $pythonExecutable = "python"
}

$ollamaBin = "C:\Users\vinicius\AppData\Local\Programs\Ollama"
if ((Test-Path $ollamaBin) -and -not ($env:Path -like "*$ollamaBin*")) {
    $env:Path = "$ollamaBin;$env:Path"
}

if (-not $env:PLAYWRIGHT_BROWSERS_PATH) {
    $env:PLAYWRIGHT_BROWSERS_PATH = ".playwright-browsers"
}

& $pythonExecutable "main.py" @JobHunterArgs
