$root = "C:\Users\akash\OneDrive\Pictures\Infosys-Springboard-Internship"
Set-Location $root
$db = Get-Item "data/runs.db"
"runs.db sha=" + (Get-FileHash "data/runs.db" -Algorithm SHA256).Hash + " size=" + $db.Length + " utc=" + $db.LastWriteTimeUtc.ToString("yyyy-MM-ddTHH:mm:ssZ")
$baseline = Get-Content ".agents/tasks/m3-t5/baseline.md"
$mismatch = 0
foreach ($line in $baseline) {
    if ($line -match '^\| ([^|]+) \| ([0-9A-F]{64}) \|$') {
        $path = $Matches[1].Trim(); $want = $Matches[2]
        $have = (Get-FileHash $path -Algorithm SHA256).Hash
        if ($have -ne $want) { $mismatch++; "CHANGED $path" }
    }
}
"hash mismatches: $mismatch"
"--- git status"
git status --porcelain
"--- secret scan"
$files = @("agents/swot_risk_agent.py", "tests/test_m3_swot_agent.py", "orchestrator.py", "tests/test_m3_orchestrator.py")
$pattern = 'AIza[0-9A-Za-z_\-]{10,}|gsk_[0-9A-Za-z]{10,}|tvly-[0-9A-Za-z_\-]{6,}|sk-[0-9A-Za-z_\-]{10,}|Bearer [0-9A-Za-z._\-]{8,}|PRIVATE KEY'
$hits = Select-String -Path $files -Pattern $pattern
"secret hits: " + @($hits).Count
$hits | ForEach-Object { $_.ToString() }
"--- orchestrator diff"
git diff --no-index --ignore-cr-at-eol ".agents/tasks/m3-t5/baseline/orchestrator.py" "orchestrator.py"
