# scripts\dayplay.ps1 — run one playable week and take a golden snapshot
param()
$ErrorActionPreference = "Stop"

# Run DayPlay
python -m engine.src.ui_dayplay_cli play

# Golden snapshot (suffix to avoid validator dupes)
$stamp = (Get-Date -Format "yyyyMMdd_HHmmss")
$gold  = ".\docs\_golden\v17_9_2_$stamp"
New-Item -ItemType Directory -Force -Path $gold | Out-Null
$files = @("MEDIA_FEED.md","SCHEDULE.md","MEDIA_REACH_MAP.md")
foreach ($f in $files) {
  $src = Join-Path ".\docs" $f
  if (Test-Path $src) {
    $dst = Join-Path $gold ($f -replace '\.md$',"__golden__$stamp.md")
    Copy-Item $src $dst -Force
  }
}
Write-Host "`nGolden snapshot -> $gold" -ForegroundColor Cyan
