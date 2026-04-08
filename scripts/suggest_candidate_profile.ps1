param(
    [string]$ResumePath = "",
    [string]$Output = ""
)

$args = @("candidate-profile", "suggest")
if ($ResumePath) {
    $args += @("--resume-path", $ResumePath)
}
if ($Output) {
    $args += @("--output", $Output)
}

& (Join-Path $PSScriptRoot "run_job_hunter.ps1") @args
