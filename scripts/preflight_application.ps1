param(
    [Parameter(Mandatory = $true, Position = 0)]
    [int]$Id,
    [switch]$ComTelegram
)

$args = @()
if (-not $ComTelegram) {
    $args += "--sem-telegram"
}
$args += @("applications", "preflight", "--id", "$Id")

& (Join-Path $PSScriptRoot "run_job_hunter.ps1") @args
