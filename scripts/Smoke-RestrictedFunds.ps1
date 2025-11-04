param(
  [string]$School = 'State U',
  [string]$SportKey = 'Basketball_M',
  [double]$PoolAmount = 250000.0,
  [double]$SpendAmount = 50000.0
)

$ErrorActionPreference = 'Stop'
Write-Host '--- Smoke: Loading core ---'

# Use $PSScriptRoot to reliably locate sibling files in the 'scripts' directory
$scriptsPath = $PSScriptRoot
# Added robust fallback: if $PSScriptRoot is null (e.g., when running via .\script.ps1), 
# use the path of the currently executing command instead.
if (-not $scriptsPath) { $scriptsPath = Split-Path $MyInvocation.MyCommand.Path -Parent }

# Load necessary modules if they haven't been loaded (should be skipped if Session-Load was run)
if (-not (Get-Command Get-World -ErrorAction SilentlyContinue)) { . (Join-Path $scriptsPath 'Finance-Min.ps1') }
if (-not (Get-Command Ensure-RestrictedSchema -ErrorAction SilentlyContinue)) { . (Join-Path $scriptsPath 'Donor-Pools.ps1') }
if (-not (Get-Command Advance-Week -ErrorAction SilentlyContinue) -and (Test-Path (Join-Path $scriptsPath 'Threshold-Events.ps1'))) { . (Join-Path $scriptsPath 'Threshold-Events.ps1') }
if (Get-Command Advance-Week -ErrorAction SilentlyContinue) { Set-Alias close-week Advance-Week -ErrorAction SilentlyContinue }

# 1) Schema sanity
Write-Host '--- Smoke: schema sanity ---'
# Ensure-RestrictedSchema handles world loading internally if Get-World is missing
[void](Ensure-RestrictedSchema)
$w = Get-World
if (-not $w.schools.$School) { throw "School '$School' not found." }
$bal = $w.schools.$School.restricted.balances
if ($bal.sport   -isnot [hashtable]) { throw 'restricted.balances.sport is not a hashtable' }
if ($bal.project -isnot [hashtable]) { throw 'restricted.balances.project is not a hashtable' }
Write-Host 'OK: restricted balance maps are hashtables.'

# 2) Reset or create a test pool (ALWAYS release this run)
Write-Host '--- Smoke: ensure test pool ---'
$donor = 'SMOKE_TEST_DONOR'
$pool = $w.schools.$School.restricted.pools | Where-Object { $_.donor -eq $donor -and $_.restriction.key -eq $SportKey } | Select-Object -First 1

# Ensure PoolAmount is available if we are resetting an existing pool
if ($pool) {
  $pool.status = 'pending'
  $pool.remaining = [double]$pool.amount
  Save-World $w
  Write-Host "Reset existing test pool (ID=$($pool.id))."
} else {
  Add-DonorPool -School $School -Donor $donor -Amount $PoolAmount `
    -Restriction @{ scope='Sport'; key=$SportKey; allowed_uses=@('recruiting') } `
    -Condition   @{ type='always' } `
    -AvailabilityPolicy 'always_release' -WeekCreated 1 | Out-Null
  Write-Host 'Added new test pool.'
}

# 3) Realize pools this week
Write-Host '--- Smoke: realize pools ---'
# Find the project root (one level up from 'scripts') for reliable log access
$projectRoot = Split-Path $scriptsPath -Parent
$fin = Join-Path $projectRoot 'logs\FINANCE_LOG.csv'

# Determine the next week number for the transaction
$wk  = (Import-Csv $fin -ea SilentlyContinue | ForEach-Object week | ForEach-Object {[int]$_} | Sort-Object | Select-Object -Last 1)
if (-not $wk) { $wk = 1 } else { $wk++ }

[void](Realize-DonorPoolsForWeek -World (Get-World) -Week $wk)

$w = Get-World
$initial = ($w.schools.$School.restricted.balances.sport[$SportKey] ?? 0.0)
Write-Host ('Initial restricted Sport:{0} = {1}' -f $SportKey,[math]::Round($initial,2))
if ($initial -lt 1) { throw 'Expected restricted balance > 0 after release.' }

# 4) Spend from restricted (recruiting) first
Write-Host ('--- Smoke: spending {0} against Sport:{1} ---' -f [math]::Round($SpendAmount,2), $SportKey)
$spend = Commit-Expense -School $School -Amount $SpendAmount -UseTag 'recruiting' -Sport $SportKey -Week $wk
Write-Host ('Spend result: covered={0} remainder={1}' -f [math]::Round($spend.covered,2), [math]::Round($spend.remainder,2))

if ([math]::Round($spend.covered,2) -ne [math]::Round($SpendAmount,2)) { throw 'Expected full amount covered from restricted.' }
if ([math]::Round($spend.remainder,2) -ne 0) { throw 'Expected remainder=0 (no cash hit).' }

$after = (Get-World).schools.$School.restricted.balances.sport[$SportKey]
Write-Host ('Remaining restricted Sport:{0} = {1}' -f $SportKey, [math]::Round($after,2))
if ([math]::Round($initial - $after,2) -ne [math]::Round($SpendAmount,2)) { throw 'Restricted balance did not decrease by SpendAmount.' }

# 5) Optional: make sure close-week still runs
if (Get-Command close-week -ErrorAction SilentlyContinue) {
  Write-Host '--- Smoke: close-week compatibility ---'
  close-week -Week $wk -Sport $SportKey -AutoBank | Out-Null
  Write-Host 'close-week executed.'
}

Write-Host '✅ SMOKE TEST PASSED.'
