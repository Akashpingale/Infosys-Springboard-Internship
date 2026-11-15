$root = "c:\Users\akash\OneDrive\Pictures\Infosys-Springboard-Internship"
$dir = Join-Path $root ".agents\tasks\m3-t7"
$files = @(".env.example","config.py","models/api.py","models/schemas.py","utils/errors.py","models/chat.py","models/strategy_drafts.py","tests/test_m3_schemas.py","utils/run_store.py","utils/chat_store.py","tests/test_m3_store_migration.py","tests/test_run_store.py","agents/strategy_context.py","agents/strategy_checks.py","tests/test_m3_digest.py","tests/test_m3_checks.py","tests/test_m3_strict_schema.py","agents/base.py","agents/notices.py","utils/deadline.py","utils/groq_client.py","utils/llm_client.py","utils/run_manager.py","tests/m3_fakes.py","tests/test_m3_orchestrator.py","orchestrator.py","agents/swot_risk_agent.py","tests/test_m3_swot_agent.py","agents/mvp_agent.py","tests/test_m3_mvp_agent.py")
$h = [ordered]@{}
$lines = @()
foreach ($f in $files) {
  $p = Join-Path $root $f
  if (Test-Path $p) { $s = (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash } else { $s = "MISSING" }
  $h[$f] = $s
  $lines += "| $f | $s |"
}
$db = Join-Path $root "data\runs.db"
$dbh = (Get-FileHash -Algorithm SHA256 -LiteralPath $db).Hash
$it = Get-Item -LiteralPath $db
$lw = $it.LastWriteTimeUtc.ToString("yyyy-MM-ddTHH:mm:ssZ")
$match = ($dbh -eq "00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D") -and ($it.Length -eq 311296) -and ($lw -eq "2026-11-08T15:31:17Z")
$h["runs_db"] = [ordered]@{ sha256 = $dbh; size = $it.Length; lastWriteTimeUtc = $lw; matches_expected = $match }
$head = git -C $root rev-parse HEAD
$branch = git -C $root rev-parse --abbrev-ref HEAD
$status = (git -C $root status --porcelain) -join "`n"
$h["git"] = [ordered]@{ head = $head; branch = $branch; status_porcelain = $status }
$h | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $dir "baseline-hashes.json")
$md = @("# M3 T7 baseline","","- HEAD: $head","- Branch: $branch","","## git status --porcelain","``````",$status,"``````","","## data/runs.db","- SHA-256: $dbh","- Size: $($it.Length)","- LastWriteTimeUtc: $lw","- Matches expected: $match","","## T1-T6 file hashes","| File | SHA-256 |","|---|---|") + $lines
$md -join "`n" | Set-Content -Encoding utf8 (Join-Path $dir "baseline.md")
Write-Output "HEAD=$head BRANCH=$branch DBMATCH=$match DB=$dbh SIZE=$($it.Length) LW=$lw"
Write-Output ("MISSING: " + (($h.Keys | Where-Object { $h[$_] -eq "MISSING" }) -join ","))
Write-Output $status
