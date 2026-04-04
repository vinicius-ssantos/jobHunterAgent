param(
    [string]$BrowsersPath = ".playwright-browsers"
)

$ErrorActionPreference = "Stop"

Write-Host "Configurando Playwright com browsers locais em: $BrowsersPath"
$env:PLAYWRIGHT_BROWSERS_PATH = $BrowsersPath

python -m playwright install chromium

Write-Host "Playwright Chromium instalado com sucesso."
Write-Host "Mantenha PLAYWRIGHT_BROWSERS_PATH=$BrowsersPath ao executar o projeto."
