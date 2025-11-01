$ErrorActionPreference="Stop"
Set-Location $PSScriptRoot\..
& .\tools\verify_guard.ps1
$pre = (Get-Content .\engine\state\clock.json -Raw | ConvertFrom-Json).week
python -m engine.src.run_tick
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass | Out-Null
& .\docs\SMOKE_v17.9.ps1
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$gold  = ".\docs\_golden\v17_9_1_$stamp"
New-Item -ItemType Directory -Force -Path $gold | Out-Null
"MEDIA_FEED.md","SCHEDULE.md","MEDIA_REACH_MAP.md" | %{
  Copy-Item ".\docs\$_" (Join-Path $gold ($_ -replace '\.md$','__golden__'+$stamp+'.md')) -Force
}
$now = (Get-Content .\engine\state\clock.json -Raw | ConvertFrom-Json).week
Write-Host "Play-Week ✅ ($pre -> $now)  Snapshot: $gold" -ForegroundColor Green
