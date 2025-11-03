# Normalize-WorldForThresholds.ps1
# Ensures each school has a complete signals block for Threshold Events.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-WorldSafe {
  $path = Join-Path (Split-Path $PSScriptRoot -Parent) "data\world.json"
  if (!(Test-Path $path)) { throw "world.json missing at $path" }
  return (Get-Content $path -Raw | ConvertFrom-Json)
}

function Save-WorldSafe($world) {
  $path = Join-Path (Split-Path $PSScriptRoot -Parent) "data\world.json"
  $world | ConvertTo-Json -Depth 100 | Set-Content -Path $path -Encoding utf8
}

function Ensure-SignalsDefaults([object]$signals) {
  if (-not $signals) {
    return [pscustomobject]@{
      donor_morale     = 0.5
      board_confidence = 0.5
      ad_hotseat       = 0
      coach_hotseat    = 0
      sentiment        = 0
    }
  }
  if (-not ($signals.PSObject.Properties.Name -contains 'donor_morale'))     { $signals | Add-Member donor_morale     0.5 }
  if (-not ($signals.PSObject.Properties.Name -contains 'board_confidence')) { $signals | Add-Member board_confidence 0.5 }
  if (-not ($signals.PSObject.Properties.Name -contains 'ad_hotseat'))       { $signals | Add-Member ad_hotseat       0 }
  if (-not ($signals.PSObject.Properties.Name -contains 'coach_hotseat'))    { $signals | Add-Member coach_hotseat    0 }
  if (-not ($signals.PSObject.Properties.Name -contains 'sentiment'))        { $signals | Add-Member sentiment        0 }
  return $signals
}

$w = Get-WorldSafe

# Ensure top-level week exists (used by some flows)
if (-not ($w.PSObject.Properties.Name -contains 'week') -or $null -eq $w.week) {
  $wk = 0
  $fin = Join-Path (Split-Path $PSScriptRoot -Parent) "logs\FINANCE_LOG.csv"
  if (Test-Path $fin) {
    try {
      $wk = (Import-Csv $fin | Select-Object -Expand week | ForEach-Object {[int]$_} | Sort-Object | Select-Object -Last 1)
      if ($null -eq $wk) { $wk = 0 }
    } catch { $wk = 0 }
  }
  if ($w.PSObject.Properties.Name -contains 'week') { $w.week = $wk } else { $w | Add-Member week $wk }
}

foreach ($school in $w.schools.Keys) {
  $node = $w.schools.$school
  if ($null -eq $node) { continue }
  if (-not ($node.PSObject.Properties.Name -contains 'signals')) {
    $node | Add-Member signals ([pscustomobject]@{})
  }
  $node.signals = Ensure-SignalsDefaults $node.signals
}

Save-WorldSafe $w
Write-Host "✅ World normalized for thresholds."
