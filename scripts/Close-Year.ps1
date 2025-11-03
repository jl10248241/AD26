# scripts/Close-Year.ps1
param(
  [switch]$ResetWeek   # if set, sets globals.week = 1 for the new year
)

Set-StrictMode -Version Latest

# Load finance helpers
. .\scripts\Finance-Min.ps1

# Ensure globals for season/budget window exist
Ensure-SeasonGlobals

# Paths
$p = Get-FinancePaths
if (-not (Test-Path $p.LogPath))   { throw "Missing $($p.LogPath)" }
if (-not (Test-Path $p.WorldPath)) { throw "Missing $($p.WorldPath)" }
if (-not (Test-Path $p.StatePath)) { throw "Missing $($p.StatePath)" }

# Resolve current world
$world = Get-World
$world.schools = ConvertTo-Hashtable $world.schools

$year  = [int]$world.globals.year
$stamp = Get-Date -Format "yyyyMMdd-HHmm"
$dest  = Join-Path "archive" ("YEAR_{0}_{1}" -f $year, $stamp)

# 1) Archive snapshot (copy, don’t delete)
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Force $p.LogPath   -Destination (Join-Path $dest "FINANCE_LOG.csv")
Copy-Item -Force $p.WorldPath -Destination (Join-Path $dest "world.json")
Copy-Item -Force $p.StatePath -Destination (Join-Path $dest "finance_state.json")
Write-Host "📦 Archived finance snapshot → $dest"

# 2) Rotate finance log for the new year (fresh header)
"week,school,donor_yield,expenses,balance,prestige_change,sentiment" | Out-File $p.LogPath -Encoding utf8
Write-Host "🧾 New finance log initialized → $($p.LogPath)"

# 3) Reset per-school spend counters; keep budgets & sport levels & sponsors
foreach ($name in $world.schools.Keys) {
  $sch = $world.schools[$name]

  # reset budgets_spend if present
  if ($sch.psobject.Properties['budgets_spend']) {
    foreach ($k in $sch.budgets_spend.psobject.Properties.Name) {
      $sch.budgets_spend.$k = 0
    }
  }

  # clear weekly ops guard to allow new-year commits
  if ($sch.psobject.Properties['last_ops_week']) {
    $sch.psobject.Properties.Remove('last_ops_week') | Out-Null
  }
}

# 4) Increment year; optionally reset week; recompute budget window; keep closed
$world.globals.year = $year + 1
if ($ResetWeek) { $world.globals.week = 1 }

# Default window if missing; recompute close week from open+window length
if (-not $world.globals.psobject.Properties['budget_open_week'])    { $world.globals | Add-Member budget_open_week 31 }
if (-not $world.globals.psobject.Properties['budget_window_weeks']) { $world.globals | Add-Member budget_window_weeks 3 }
$world.globals.budget_close_week = [int]$world.globals.budget_open_week + [int]$world.globals.budget_window_weeks - 1
$world.globals.is_budget_open = $false

# 5) Reset legacy finance_state.json to clean baseline (compat)
$state = @{
  week             = [int]$world.globals.week
  balance          = 0
  last_donor_yield = 0
  last_expenses    = 0
  last_prestige    = 0
  sentiment        = 0.0
}
$state | ConvertTo-Json | Out-File $p.StatePath -Encoding utf8

# 6) Save world
Save-World $world

Write-Host ("✅ Year close complete → Rolled {0} → {1}" -f $year, $world.globals.year)
Write-Host ("   Budget window (closed): weeks {0}-{1}" -f $world.globals.budget_open_week, $world.globals.budget_close_week)
