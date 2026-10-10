# Nightly collection. SerpAPI is the licensed multi-carrier sweep; Akasa is
# the direct, RBD-level PRISM panel. The current 20-route x 5-window SerpAPI
# sweep requires 100 searches. All raw evidence is sealed after both adapters.
$repo = "D:\Engineering Resources\SIH 26\project\air-sankhyiki"
Set-Location $repo
$logDir = Join-Path $repo "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("collect_" + (Get-Date -Format "yyyy-MM-dd") + ".log")

function Log($msg) { $msg | Tee-Object -FilePath $log -Append }

Log "=== nightly run started $(Get-Date -Format o) ==="
$failedSteps = [System.Collections.Generic.List[string]]::new()
$requiredSerpSearches = 100

# The helper checks every authorized configured credential and prints only the
# combined remaining quota. It never prints key values.
$left = python -m uv run --project services/collectors serpapi-quota 2>> $log
$quotaExit = $LASTEXITCODE
if ($quotaExit -eq 0 -and [int]$left -ge $requiredSerpSearches) {
    Log "serpapi daily sweep (authorized quota available: $left)"
    python -m uv run --project services/collectors collect --adapter serpapi 2>&1 |
        Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        $failedSteps.Add("serpapi-collection")
        Log "serpapi result: PARTIAL/FAILED (exit $LASTEXITCODE)"
    } else {
        Log "serpapi result: COMPLETE"
    }
} else {
    $available = if ($quotaExit -eq 0) { $left } else { "unknown" }
    Log "serpapi SKIPPED: $available searches available ($requiredSerpSearches required)"
    $failedSteps.Add("serpapi-preflight")
}

python -m uv run --project services/collectors collect --adapter akasa 2>&1 |
    Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) {
    $failedSteps.Add("akasa-collection")
    Log "akasa result: PARTIAL/FAILED (exit $LASTEXITCODE)"
} else {
    Log "akasa result: COMPLETE"
}

python -m uv run --project services/collectors ledger seal 2>&1 |
    Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) {
    $failedSteps.Add("ledger-seal-or-verification")
    Log "ledger result: FAILED (exit $LASTEXITCODE)"
} else {
    Log "ledger result: COMPLETE"
}

if ($failedSteps.Count -gt 0) {
    Log "=== nightly run finished PARTIAL/FAILED $(Get-Date -Format o); steps: $($failedSteps -join ', ') ==="
    exit 1
}

Log "=== nightly run finished COMPLETE $(Get-Date -Format o) ==="
exit 0
