$base = "http://127.0.0.1:8560"
$urls = @(
    "/mappings",
    "/datasources",
    "/training-studio",
    "/settings",
    "/tests",
    "/schema-browser",
    "/ai-assistant",
    "/tfs",
    "/agents",
    "/api/credentials",
    "/api/templates"
)

$pass = 0
$fail = 0

foreach ($url in $urls) {
    try {
        $r = Invoke-WebRequest -Uri "$base$url" -UseBasicParsing -TimeoutSec 5
        Write-Host "PASS  $url  =>  HTTP $($r.StatusCode)  ($($r.Content.Length) chars)" -ForegroundColor Green
        $pass++
    }
    catch {
        Write-Host "FAIL  $url  =>  $($_.Exception.Message)" -ForegroundColor Red
        $fail++
    }
}

Write-Host ""
Write-Host "Results: $pass passed, $fail failed" -ForegroundColor $(if ($fail -eq 0) { "Green" } else { "Red" })
