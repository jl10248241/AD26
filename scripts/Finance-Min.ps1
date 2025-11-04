# Finance-Min.ps1 — v19.6 minimal + restricted spend integration
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-ProjectRoot { Split-Path -Parent $PSScriptRoot }
function Ensure-Dir([string]$path) { if (!(Test-Path $path)) { New-Item -ItemType Directory -Path $path | Out-Null }; $path }
function Ensure-Logs { Ensure-Dir (Join-Path (Get-ProjectRoot) "logs") }
function Get-WorldPath { Join-Path (Get-ProjectRoot) "data\world.json" }

function Save-World([object]$World) { $World | ConvertTo-Json -Depth 100 | Set-Content (Get-WorldPath) -Encoding utf8 }

function Get-World {
  $wp = Get-WorldPath
  $w  = $null
  if (Test-Path $wp) {
    try { $raw = Get-Content $wp -Raw; if ($raw -and $raw.Trim().Length -gt 0) { $w = $raw | ConvertFrom-Json } } catch { Write-Warning ("world.json unreadable — rebuilding default. ({0})" -f $_.Exception.Message) }
  }
  if (-not $w -or -not $w.schools) {
    $w = [pscustomobject]@{
      week    = 0
      schools = [pscustomobject]@{
        'State U' = [pscustomobject]@{
          name='State U'; cash=0; bank=0
          signals=[pscustomobject]@{ donor_morale=0.5; board_confidence=0.5; ad_hotseat=0; coach_hotseat=0; sentiment=0 }
        }
        'Tech U'  = [pscustomobject]@{
          name='Tech U'; cash=0; bank=0
          signals=[pscustomobject]@{ donor_morale=0.5; board_confidence=0.5; ad_hotseat=0; coach_hotseat=0; sentiment=0 }
        }
      }
    }
    Ensure-Dir (Split-Path $wp -Parent) | Out-Null
    $w | ConvertTo-Json -Depth 100 | Set-Content $wp -Encoding utf8
  }
  if ($w.schools -isnot [pscustomobject]) {
    $obj = New-Object PSObject
    if ($w.schools -is [System.Collections.IEnumerable]) {
      $i=0; foreach($s in $w.schools){ $i++; $n = if($s.name){[string]$s.name}else{"School$i"}; $obj | Add-Member -NotePropertyName $n -NotePropertyValue $s }
    } else { $obj | Add-Member -NotePropertyName 'State U' -NotePropertyValue ([pscustomobject]@{ name='State U' }) }
    $w.schools = $obj
  }
  foreach($name in $w.schools.PSObject.Properties.Name){
    $node = $w.schools.$name
    if (-not ($node.PSObject.Properties.Name -contains 'cash')) { $node | Add-Member cash 0 }
    if (-not ($node.PSObject.Properties.Name -contains 'bank')) { $node | Add-Member bank 0 }
    if (-not $node.signals) { $node | Add-Member signals ([pscustomobject]@{}) }
    foreach($k in 'donor_morale','board_confidence','ad_hotseat','coach_hotseat','sentiment'){
      if (-not ($node.signals.PSObject.Properties.Name -contains $k)) {
        $node.signals | Add-Member -NotePropertyName $k -NotePropertyValue ( ($k -match 'morale|confidence') ? 0.5 : 0 )
      }
    }
    if (-not $node.restricted) { $node | Add-Member restricted ([pscustomobject]@{ ops=0; recruiting=0; facilities=0; NIL=0; capex=0 }) }
    foreach($rk in 'ops','recruiting','facilities','NIL','capex'){ if (-not ($node.restricted.PSObject.Properties.Name -contains $rk)) { $node.restricted | Add-Member -NotePropertyName $rk -NotePropertyValue 0 } }
    if (-not $node.restricted_projects) { $node | Add-Member restricted_projects ([pscustomobject]@{}) }
  }
  Save-World $w
  return $w
}

function Ensure-FinanceLog {
  $fin = Join-Path (Ensure-Logs) "FINANCE_LOG.csv"
  if(!(Test-Path $fin)){ "week,school,donor_yield,expenses,balance,prestige_change,sentiment" | Out-File $fin -Encoding utf8 }
  $fin
}

# --- Revenue & governance (simple) ---
function Process-DonorsForWeek {
  [CmdletBinding()]
  param([Parameter(Mandatory=$true)][string]$School,
        [Parameter(Mandatory=$true)][string]$Sport,
        [Parameter(Mandatory=$true)][int]$Week)
  $w = Get-World
  $sent = $w.schools.$School.signals.sentiment
  $base = 1000000 + (Get-Random -Minimum 250000 -Maximum 750000)
  $scale = 1.0 + [math]::Round(($sent * 0.2),3)
  [math]::Round($base * $scale, 2)
}
function Apply-EventWeekEffects { param([string]$School,[int]$Week) }
function Apply-MatchingGifts { param([string]$School,[int]$Week) return 0 }
function Apply-DonorDecayToWeek { param([string]$School,[string]$Sport,[int]$Week) }
function Update-GovernanceSignals {
  param([string]$School,[string]$Sport,[int]$Week)
  $w = Get-World
  $s = $w.schools.$School.signals
  $s.donor_morale     = [math]::Min(1,[math]::Max(0, $s.donor_morale))
  $s.board_confidence = [math]::Min(1,[math]::Max(0, $s.board_confidence))
  $s.sentiment        = [math]::Min(1,[math]::Max(-1,$s.sentiment))
  Save-World $w
  [pscustomobject]@{
    school=$School; loss_trend_5=0; donor_decay_pct=0; donor_morale=$s.donor_morale
    board_conf=$s.board_confidence; ad_hotseat=$s.ad_hotseat; coach_hotseat=$s.coach_hotseat
  }
}
function Bank-SettleNow { param([string]$School,[int]$Week) }

# --- Restricted-aware spend helper ---
# NOTE: Spend-Tagged is now defined in Donor-Pools.ps1 and has been removed from here to prevent conflicts.

# --- Commit entries ---
function Commit-TicketRevenue {
  [CmdletBinding()]
  param([Parameter(Mandatory=$true)][string]$School,
        [Parameter(Mandatory=$true)][string]$Sport,
        [Parameter(Mandatory=$true)][int]$Week)
  $w = Get-World
  $yield = Process-DonorsForWeek -School $School -Sport $Sport -Week $Week
  $w.schools.$School.cash = ($w.schools.$School.cash + 0) + $yield
  Save-World $w
  $fin = Ensure-FinanceLog
  $sent = $w.schools.$School.signals.sentiment
  "$Week,$School,$yield,0,$($w.schools.$School.cash),0,$sent" | Out-File $fin -Append -Encoding utf8
  return $yield
}
function Commit-Expense {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory)][string]$School,
    [Parameter(Mandatory)][double]$Amount,
    [Parameter(Mandatory)][int]$Week,
    [string]$UseTag,
    [string]$Sport,
    [string]$ProjectKey
  )
  $w = Get-World
  [double]$covered = 0
  if ($UseTag -and (Get-Command Spend-Tagged -ErrorAction SilentlyContinue)) {
    $covered = Spend-Tagged -School $School -Amount $Amount -UseTag $UseTag -Sport $Sport -ProjectKey $ProjectKey
  }
  $remainder = [math]::Max(0, [double]$Amount - $covered)

  if ($remainder -gt 0) {
    $w.schools.$School.cash = ($w.schools.$School.cash + 0.0) - $remainder
    Save-World $w
  }

  $fin = Ensure-FinanceLog
  $sent = $w.schools.$School.signals.sentiment
  "$Week,$School,0,$remainder,$($w.schools.$School.cash),0,$sent" | Out-File $fin -Append -Encoding utf8
  return [pscustomobject]@{ covered=$covered; remainder=$remainder }
}
function Commit-SportsOps {
  [CmdletBinding()]
  param([Parameter(Mandatory=$true)][string]$School,
        [Parameter(Mandatory=$true)][int]$Week)
  # Example: spend 150k ops per week from restricted->cash
  [void](Commit-Expense -School $School -Amount 150000 -UseTag ops -Week $Week)
  return 150000
}

# --- Advance-Week integrates donor pool realization + thresholds ---
function Advance-Week {
  [CmdletBinding()]
  param([Parameter(Mandatory=$true)][int]$Week,
        [Parameter(Mandatory=$true)][string]$Sport,
        [switch]$AutoBank)

  $w = Get-World
  if (-not $w.week -or $w.week -lt $Week) { $w.week = $Week }

  foreach ($s in $w.schools.PSObject.Properties.Name) {
    Apply-EventWeekEffects -School $s -Week $Week
    [void](Commit-TicketRevenue -School $s -Sport $Sport -Week $Week)
    [void](Apply-MatchingGifts -School $s -Week $Week)
    Apply-DonorDecayToWeek -School $s -Sport $Sport -Week $Week
    [void](Update-GovernanceSignals -School $s -Sport $Sport -Week $Week)
    [void](Commit-SportsOps -School $s -Week $Week)
    if ($AutoBank) { Bank-SettleNow -School $s -Week $Week }
  }
  Save-World $w

  # Donor Pools → post into restricted when released
  if (Get-Command Realize-DonorPoolsForWeek -ErrorAction SilentlyContinue) {
    try {
      $hits = Realize-DonorPoolsForWeek -World $w -Week $Week
      if ($hits.Count -gt 0) { Write-Host ("Donor pools released: {0}" -f ($hits.Count)) }
    } catch { Write-Warning ("Advance-Week: DonorPools failed ({0})" -f $_.Exception.Message) }
  }

  # Optional: Threshold Events
  $thrPath = Join-Path $PSScriptRoot "Threshold-Events.ps1"
  if (-not (Get-Command Apply-ThresholdEvents -ErrorAction SilentlyContinue) -and (Test-Path $thrPath)) { . $thrPath }
  if (Get-Command Apply-ThresholdEvents -ErrorAction SilentlyContinue) {
    try {
      $thresholds = Apply-ThresholdEvents -World $w -Week $Week
      if ($thresholds.Count -gt 0) {
        $events = $thresholds | Select-Object -ExpandProperty event -Unique | Sort-Object
        Write-Host ("⚠ Threshold events: {0}" -f ($events -join ', '))
      }
    } catch { Write-Warning ("Advance-Week: ThresholdEvents failed ({0})" -f $_.Exception.Message) }
  }

  return $Week
}

Set-Alias close-week Advance-Week -ErrorAction SilentlyContinue