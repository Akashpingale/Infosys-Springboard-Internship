param([string]$Label = "baseline")
$root = "c:\Users\akash\OneDrive\Pictures\Infosys-Springboard-Internship"
$dir = Join-Path $root ".agents\tasks\m3-t8"
$listed = git -C $root status --porcelain | ForEach-Object { $_.Substring(3).Trim('"') } | Where-Object { $_ -notlike ".agents/*" }
$pinned = @("routes/run_routes.py","routes/meta_routes.py","models/api.py","app.py","utils/run_manager.py","orchestrator.py","tests/test_runs_api.py","tests/test_meta_route.py")
$files = @($listed + $pinned) | Select-Object -Unique
$h = [ordered]@{}
foreach ($f in $files) {
  $p = Join-Path $root $f
  if (Test-Path -LiteralPath $p -PathType Leaf) { $h[$f] = (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash } else { $h[$f] = "MISSING" }
}
$db = Join-Path $root "data\runs.db"
$dbh = (Get-FileHash -Algorithm SHA256 -LiteralPath $db).Hash
$it = Get-Item -LiteralPath $db
$lw = $it.LastWriteTimeUtc.ToString("yyyy-MM-ddTHH:mm:ssZ")
$match = ($dbh -eq "00A4F85940CEA543823EC25AC4C5FF35B002FD10E1BCAD356D84EF44FEA8337D") -and ($it.Length -eq 311296) -and ($lw -eq "2026-11-08T15:31:17Z")
$out = [ordered]@{
  git = [ordered]@{ head = (git -C $root rev-parse HEAD); branch = (git -C $root rev-parse --abbrev-ref HEAD) }
  files = $h
  runs_db = [ordered]@{ sha256 = $dbh; size = $it.Length; lastWriteTimeUtc = $lw; matches_expected = $match }
}
$out | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $dir "$Label-hashes.json")
Write-Output "FILES=$($h.Count) MISSING=$((@($h.Keys | Where-Object { $h[$_] -eq 'MISSING' })) -join ',') DBMATCH=$match DB=$dbh SIZE=$($it.Length) LW=$lw"
