# --- guard sanity (import + call + compile) ---
& powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\verify_guard.ps1
if ($LASTEXITCODE -ne 0) { throw "Guard verification failed." }
# docs\SMOKE_v17.9.ps1
param()

# UTF-8 nicety
chcp 65001 > $null
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING='utf-8'

# Rebuild reports
python -m engine.src.media_desk report
python -m engine.src.ui_schedule_cli report
python -m engine.src.ui_media_map_cli render
python -m engine.src.ui_recruiting_influence_cli compute

# Show heads
Get-Content .\docs\MEDIA_FEED.md | Select-Object -First 8
Get-Content .\docs\SCHEDULE.md    | Select-Object -First 8
Get-Content .\engine\config\MEDIA_REACH.json | Select-Object -First 12
Get-Content .\docs\RECRUITING_READOUT.md | Select-Object -First 12

Write-Host "`nSMOKE_v17.9 ✅" -ForegroundColor Green


