$root = "C:\Users\akash\OneDrive\Pictures\Infosys-Springboard-Internship"
Set-Location $root
$expected = @{
  ".env.example" = "0EE7C4BF150AC001EE42C04E7CAA0463A548DD7B464481430C65E512D6047C53"
  "config.py" = "0E5BD22FD2CD8BD5F562228EB4EFB00C5AC8F3AE553A2F2CBC7EF7EFCAB58A6E"
  "models/api.py" = "C0B2D6E76C41A9BC089F910C32A7364F74B7E1FE96DBAC070C1B3DCED70E3F8A"
  "models/schemas.py" = "46C02616B345E0B11E5EFFF56B6247771FFB110C78E921DD6F4ED813FCE41BCF"
  "utils/errors.py" = "D931AF3B70510EBA924467852B1392510AD5CFEFBFD9AC22EE94704F7AEE105A"
  "models/chat.py" = "60F45CD64D7204CF0FE694A6BA1D99F9C9C024D94ED77B60DB0F8C5D39910BEA"
  "models/strategy_drafts.py" = "01E7BBBF762864CCC21250E0407989137190EB007BC2B38F762898F70FDFE8D0"
  "tests/test_m3_schemas.py" = "1BAB66868D468410891653819765FF5EB2325F54932B3EA33AEF4AC1A1ED7026"
  "utils/run_store.py" = "E7F32AF4FC5F9CD88817BB26C397D943AAF2ADA275FAAF4950527ADCA28E1018"
  "utils/chat_store.py" = "C1C54B9A96BF5B262BBD06FCD9C92322E70FB4B0075810F9FEB28AB174D7BFC0"
  "tests/test_m3_store_migration.py" = "4DA142C0C908ABFF234A25AE7A075135B829A3C6C7F4B5F0ED19873EA30E3B09"
  "tests/test_run_store.py" = "86C54A839A8D7C3A6C68FCEA2300B432B1D4F6A313D75DFC79717A4E2300B665"
  "agents/strategy_context.py" = "1A33D80E85FF14EED2A7C1112FDFEE4840E489129647B7DA9CF869C520CE16E1"
  "agents/strategy_checks.py" = "8808D072F4DE8F223027C6C3AAC12FEC18A1A97276C91E552F277B24C79B555E"
  "tests/test_m3_digest.py" = "B2C39005C3D5749336AF60C663439CCCFF005E9878823E10B228652CDC967242"
  "tests/test_m3_checks.py" = "6311503F6AA117C050B65B32CDC49F1C3D4AAA9A6FBE9D8F8E1732F70B601CB9"
  "tests/test_m3_strict_schema.py" = "CB984106F2680762428CAA6029F1A11C45EBF6A5C3D94384D12580D7772D9378"
}
$bad = 0
foreach ($k in $expected.Keys) {
  $h = (Get-FileHash -Algorithm SHA256 $k).Hash
  if ($h -ne $expected[$k]) { $bad++; Write-Output "MISMATCH $k $h" }
}
Write-Output "T1-T3 mismatches: $bad of $($expected.Count)"
$db = Get-Item "data/runs.db"
$dbh = (Get-FileHash -Algorithm SHA256 "data/runs.db").Hash
Write-Output ("runs.db " + $dbh + " " + $db.Length + " " + $db.LastWriteTimeUtc.ToString("yyyy-MM-ddTHH:mm:ssZ"))
$files = "agents/base.py","agents/notices.py","orchestrator.py","utils/deadline.py","utils/groq_client.py","utils/llm_client.py","utils/run_manager.py","tests/m3_fakes.py","tests/test_m3_orchestrator.py"
$pattern = 'AIza[0-9A-Za-z_\-]{20,}|gsk_[0-9A-Za-z]{20,}|tvly-[0-9A-Za-z]{10,}|sk-[0-9A-Za-z]{20,}|Bearer\s+[0-9A-Za-z\-_\.]{20,}|PRIVATE KEY'
$hits = Select-String -Path $files -Pattern $pattern
Write-Output "secret hits: $(@($hits).Count)"
$hits | ForEach-Object { Write-Output "HIT $($_.Path):$($_.LineNumber)" }
foreach ($f in $files) {
  $t = [IO.File]::ReadAllText((Join-Path $root $f))
  $crlf = ([regex]::Matches($t, "`r`n")).Count
  $lf = ([regex]::Matches($t, "(?<!`r)`n")).Count
  Write-Output "$f crlf=$crlf lone_lf=$lf"
}
