param(
  [string]$Root = ".",
  [switch]$DoIt
)

$ErrorActionPreference = "Stop"

# Canonical archive layout
$ARCH_ROOT   = Join-Path $Root "archive"
$ARCH_ZIPS   = Join-Path $ARCH_ROOT "zips"
$ARCH_STATUS = Join-Path $ARCH_ROOT "status"
$ARCH_CODE   = Join-Path $ARCH_ROOT "code"
$ARCH_NOTES  = Join-Path $ARCH_ROOT "notes"

$targets = @($ARCH_ROOT,$ARCH_ZIPS,$ARCH_STATUS,$ARCH_CODE,$ARCH_NOTES)
foreach($d in $targets){ New-Item -ItemType Directory -Force -Path $d | Out-Null }

$whatIf = $true
if ($DoIt) { $whatIf = $false }

Write-Host "=== Consolidating archives under: $ARCH_ROOT ===" -ForegroundColor Cyan

# 1) ZIPs anywhere → archive\zips
Get-ChildItem -Path $Root -Filter *.zip -Recurse -File |
  Where-Object { $_.FullName -notlike "$ARCH_ZIPS*" } |
  ForEach-Object {
    $dest = Join-Path $ARCH_ZIPS $_.Name
    Move-Item $_.FullName $dest -Force -WhatIf:$whatIf
  }

# 2) Project status MDs → archive\status
#   (both at root and already in archive root)
$projStatus = @(
  Get-ChildItem -Path $Root -Filter "PROJECT_STATUS_v*.md" -File -ErrorAction SilentlyContinue
  Get-ChildItem -Path $ARCH_ROOT -Filter "PROJECT_STATUS_v*.md" -File -ErrorAction SilentlyContinue
) | Sort-Object -Unique

$projStatus | ForEach-Object {
  $dest = Join-Path $ARCH_STATUS $_.Name
  if ($_.FullName -ne $dest) {
    Move-Item $_.FullName $dest -Force -WhatIf:$whatIf
  }
}

# 3) Versioned code snapshots:
#    Move any archive\vNN_N → archive\code\vNN_N
Get-ChildItem -Path $ARCH_ROOT -Directory -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match '^v\d+_\d+$' } |
  ForEach-Object {
    $dest = Join-Path $ARCH_CODE $_.Name
    if ($_.FullName -ne $dest) {
      Move-Item $_.FullName $dest -Force -WhatIf:$whatIf
    }
  }

# 4) Notes change logs like notes\CHANGELOG_v*.md → archive\notes
Get-ChildItem -Path (Join-Path $Root "notes") -Filter "CHANGELOG_v*.md" -File -ErrorAction SilentlyContinue |
  ForEach-Object {
    $dest = Join-Path $ARCH_NOTES $_.Name
    Move-Item $_.FullName $dest -Force -WhatIf:$whatIf
  }

# 5) Optional: keep doc backup clones together (e.g., CHANGELOG.backup.*)
Get-ChildItem -Path (Join-Path $Root "docs") -Filter "CHANGELOG.backup.*.md" -File -ErrorAction SilentlyContinue |
  ForEach-Object {
    $dest = Join-Path $ARCH_NOTES $_.Name
    Move-Item $_.FullName $dest -Force -WhatIf:$whatIf
  }

# 6) Write a fresh filemap so we can eyeball the result
$mapPath = Join-Path $Root "PROJECT_FILEMAP.txt"
cmd /c "tree `"$Root`" /F" | Out-File -FilePath $mapPath -Encoding UTF8 -Force

Write-Host "`nPreview complete." -ForegroundColor Yellow
if ($whatIf) {
  Write-Host "Rerun with:  powershell -ExecutionPolicy Bypass -File tools\Consolidate-Archives.ps1 -DoIt" -ForegroundColor Yellow
} else {
  Write-Host "Moves applied. Updated filemap → $mapPath" -ForegroundColor Green
}
