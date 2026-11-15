$ErrorActionPreference = "Stop"
$root = "C:\Users\akash\OneDrive\Pictures\Infosys-Springboard-Internship"
Set-Location $root

"== data/runs.db =="
$db = Get-Item "data\runs.db"
$dbHash = (Get-FileHash "data\runs.db" -Algorithm SHA256).Hash
"SHA256 $dbHash"
"Size $($db.Length)"
"LastWriteTimeUtc $($db.LastWriteTimeUtc.ToString('yyyy-MM-ddTHH:mm:ssZ'))"
$dbOk = ($dbHash -eq "00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D") -and ($db.Length -eq 311296) -and ($db.LastWriteTimeUtc.ToString('yyyy-MM-ddTHH:mm:ssZ') -eq "2026-11-08T15:31:17Z")
"db unchanged: $dbOk"

"== hashes vs baseline.md =="
$lines = Get-Content ".agents\tasks\m3-t5\baseline.md" | Where-Object { $_ -match '^\| [^|]+ \| [0-9A-F]{64} \|$' }
$match = 0; $diff = @()
foreach ($line in $lines) {
    $parts = $line.Trim('|').Split('|') | ForEach-Object { $_.Trim() }
    $path = $parts[0]; $expected = $parts[1]
    $actual = (Get-FileHash $path -Algorithm SHA256).Hash
    if ($actual -eq $expected) { $match++ } else { $diff += "$path baseline=$expected now=$actual" }
}
"files checked: $($lines.Count); unchanged: $match; changed: $($diff.Count)"
$diff
"baseline copy orchestrator.py: $((Get-FileHash '.agents\tasks\m3-t5\baseline\orchestrator.py' -Algorithm SHA256).Hash)"

"== new files =="
foreach ($p in "agents\swot_risk_agent.py", "tests\test_m3_swot_agent.py") {
    $lc = (Get-Content $p).Count
    "$p lines=$lc sha256=$((Get-FileHash $p -Algorithm SHA256).Hash)"
}

"== secret scan =="
$files = "orchestrator.py", "agents\swot_risk_agent.py", "tests\test_m3_swot_agent.py", "tests\test_m3_orchestrator.py"
$patterns = @('AIza[0-9A-Za-z_\-]{20,}', 'gsk_[0-9A-Za-z]{10,}', 'tvly-[0-9A-Za-z]{10,}', 'sk-[0-9A-Za-z_\-]{16,}', 'Bearer\s+[0-9A-Za-z._\-]{16,}', 'PRIVATE KEY')
$hits = 0
foreach ($f in $files) {
    foreach ($pat in $patterns) {
        $found = Select-String -Path $f -Pattern $pat -CaseSensitive
        foreach ($h in $found) { $hits++; "HIT $f`:$($h.LineNumber) pattern=$pat" }
    }
}
"secret hits: $hits"
