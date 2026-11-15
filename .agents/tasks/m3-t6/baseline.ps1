$root = 'C:\Users\akash\OneDrive\Pictures\Infosys-Springboard-Internship'
$out = Join-Path $root '.agents\tasks\m3-t6'
$paths = @('.env.example','config.py','models/api.py','models/schemas.py','utils/errors.py','models/chat.py','models/strategy_drafts.py','tests/test_m3_schemas.py','utils/run_store.py','utils/chat_store.py','tests/test_m3_store_migration.py','tests/test_run_store.py','agents/strategy_context.py','agents/strategy_checks.py','tests/test_m3_digest.py','tests/test_m3_checks.py','tests/test_m3_strict_schema.py','agents/base.py','agents/notices.py','utils/deadline.py','utils/groq_client.py','utils/llm_client.py','utils/run_manager.py','tests/m3_fakes.py','tests/test_m3_orchestrator.py','orchestrator.py','agents/swot_risk_agent.py','tests/test_m3_swot_agent.py')
$files = [ordered]@{}
foreach ($p in $paths) { $f = Join-Path $root $p; if (Test-Path $f) { $files[$p] = (Get-FileHash $f -Algorithm SHA256).Hash } else { $files[$p] = 'MISSING' } }
$db = Join-Path $root 'data\runs.db'
$item = Get-Item $db
$dbh = (Get-FileHash $db -Algorithm SHA256).Hash
$lw = $item.LastWriteTimeUtc.ToString('yyyy-MM-ddTHH:mm:ssZ')
$status = @(git -C $root status --porcelain)
$branch = (git -C $root rev-parse --abbrev-ref HEAD)
$head = (git -C $root rev-parse HEAD)
$mvp = Test-Path (Join-Path $root 'agents\mvp_agent.py')
$mvpt = Test-Path (Join-Path $root 'tests\test_m3_mvp_agent.py')
$match = ($dbh -eq '00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D') -and ($item.Length -eq 311296) -and ($lw -eq '2026-11-08T15:31:17Z')
$obj = [ordered]@{ files=$files; runs_db=[ordered]@{sha256=$dbh; size=$item.Length; lastWriteTimeUtc=$lw; matches_expected=$match}; branch=$branch; head=$head; git_status_porcelain=$status; mvp_agent_exists=$mvp; test_m3_mvp_agent_exists=$mvpt }
$obj | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $out 'baseline.json') -Encoding utf8
$md = @("# M3-T6 baseline","","Branch: $branch","HEAD: $head","","## runs.db","sha256: $dbh","size: $($item.Length)","lastWriteTimeUtc: $lw","matches expected: $match","","## mvp files exist","agents/mvp_agent.py: $mvp","tests/test_m3_mvp_agent.py: $mvpt","","## files")
foreach ($k in $files.Keys) { $md += "- ${k}: $($files[$k])" }
$md += ''; $md += '## git status --porcelain'; $md += ($status | ForEach-Object { "    $_" })
$md | Set-Content (Join-Path $out 'baseline.md') -Encoding utf8
"match=$match mvp=$mvp mvpt=$mvpt branch=$branch head=$head"
"db: $dbh $($item.Length) $lw"
$files.GetEnumerator() | Where-Object { $_.Value -eq 'MISSING' } | ForEach-Object { "MISSING $($_.Key)" }
$status
