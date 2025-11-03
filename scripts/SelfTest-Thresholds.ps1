# SelfTest-Thresholds.ps1 — v19.3 smoke test
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$finance = Join-Path $PSScriptRoot "Finance-Min.ps1"
if (Test-Path $finance) { . $finance }

. (Join-Path $PSScriptRoot "Threshold-Events.ps1")

$w = if (Get-Command Get-World -ErrorAction SilentlyContinue) { Get-World } else { Get-Content (Join-Path (Split-Path $PSScriptRoot -Parent) "data\world.json") -Raw | ConvertFrom-Json }
$wk = if ($w.week) { [int]$w.week } else { 0 }
$school = ($w.schools.Keys | Select-Object -First 1)
$w.schools.$school.signals.ad_hotseat = 95
$w.schools.$school.signals.coach_hotseat = 82
$w.schools.$school.signals.board_confidence = 0.28
$w.schools.$school.signals.donor_morale = 0.20

$hits = Apply-ThresholdEvents -World $w -Week $wk
"Hits: $($hits.Count)"
$hits | Format-Table -AutoSize

$log = Join-Path (Join-Path (Split-Path $PSScriptRoot -Parent) "logs") "THRESHOLD_EVENTS.csv"
if (Test-Path $log) {
  "---- tail THRESHOLD_EVENTS.csv ----"
  Get-Content $log | Select-Object -Last 10
} else { "THRESHOLD_EVENTS.csv not found." }
