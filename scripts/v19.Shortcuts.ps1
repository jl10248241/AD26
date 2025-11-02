<# v19.Shortcuts.ps1 — tiny helpers that feel like v18 #>

Set-StrictMode -Version Latest

# Depend on v19.Addons.ps1 being loaded first (for rel+/rel-, rep.calc, v19.stat)
function Praise-Coach {
  [CmdletBinding()]
  param([string]$Target = "Coach.HeadCoach", [int]$Intensity = 12)
  rel+ -Target $Target -Intensity $Intensity
  rep.calc
  v19.stat
}

function Discipline-Coach {
  [CmdletBinding()]
  param([string]$Target = "Coach.HeadCoach", [int]$Intensity = 10)
  rel- -Target $Target -Intensity $Intensity
  rep.calc
  v19.stat
}

function Daily-Brief {
  [CmdletBinding()] param()
  Write-Host "==== DAILY BRIEF — v19 ====" -ForegroundColor Cyan
  v19.stat
  $root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
  $docs = Join-Path $root 'docs'
  if (Test-Path $docs) {
    $out = Join-Path $docs 'DAILY_BRIEF_v19.md'
    $now = Get-Date -Format s
    $rep = Get-Content (Join-Path $root 'data\reputation.json') -Raw | ConvertFrom-Json
    $lines = @(
      "# Daily Brief — v19",
      "**Generated:** $now  ",
      "",
      "| Metric | Value |",
      "|---|---:|",
      "| Reputation | $($rep.score) ($($rep.label)) |",
      "| Relationships Avg | $( [double]$rep.components.relationships ) |",
      ""
    )
    Set-Content -Encoding UTF8 -Path $out -Value ($lines -join "`r`n")
    Write-Host "Saved brief: $out" -ForegroundColor Green
  } else {
    Write-Host "Tip: create docs\ to auto-write a brief md file." -ForegroundColor DarkGray
  }
}

# comfy aliases
Set-Alias praise Praise-Coach
Set-Alias discipline Discipline-Coach
Set-Alias brief Daily-Brief
