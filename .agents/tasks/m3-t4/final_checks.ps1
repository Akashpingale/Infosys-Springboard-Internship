$root = "C:\Users\akash\OneDrive\Pictures\Infosys-Springboard-Internship"
Set-Location $root
$base = ".agents/tasks/m3-t4/baseline"
$pairs = "agents/base.py","orchestrator.py","utils/deadline.py","utils/run_manager.py","agents/notices.py","utils/llm_client.py","utils/structured.py","utils/groq_client.py","config.py",".env.example"
foreach ($f in $pairs) {
  $cur = (Get-FileHash -Algorithm SHA256 $f).Hash
  $old = (Get-FileHash -Algorithm SHA256 "$base/$f").Hash
  $stat = git diff --no-index --numstat --ignore-cr-at-eol -- "$base/$f" $f
  if (-not $stat) { $stat = "0`t0`t(identical)" }
  Write-Output ("{0} same={1} numstat={2}" -f $f, ($cur -eq $old), ($stat -join ' '))
}
foreach ($f in "tests/m3_fakes.py","tests/test_m3_orchestrator.py") {
  $n = (Get-Content $f).Count
  Write-Output "$f new lines=$n"
}
$files = "agents/base.py","agents/notices.py","orchestrator.py","utils/deadline.py","utils/groq_client.py","utils/llm_client.py","utils/run_manager.py","tests/m3_fakes.py","tests/test_m3_orchestrator.py"
$loose = 'AIza|gsk_|tvly-|sk-[0-9A-Za-z]|Bearer\s|PRIVATE KEY'
$hits = Select-String -Path $files -Pattern $loose
Write-Output "loose prefix hits: $(@($hits).Count)"
$hits | ForEach-Object { Write-Output ("LOOSE {0}:{1}: {2}" -f $_.Path.Replace($root,''), $_.LineNumber, $_.Line.Trim()) }
$outside = git status --porcelain -- routes frontend web docs MILESTONE_3_MASTER_IMPLEMENTATION_PLAN.md "KIRO_*.md"
Write-Output "changes in routes/frontend/web/docs/plan/KIRO: $(@($outside | Where-Object { $_ }).Count)"
