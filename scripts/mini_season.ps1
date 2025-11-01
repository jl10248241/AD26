param([int]$Weeks = 4)
$ErrorActionPreference = "Stop"

for ($i=1; $i -le $Weeks; $i++) {
  Write-Host "`n=== MINI-SEASON: Week $i/$Weeks ===" -ForegroundColor Cyan
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dayplay.ps1 | Write-Host
}
