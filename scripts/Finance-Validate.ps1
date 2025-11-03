param(
  [switch]$Strict,
  [switch]$FixWorld
)

Set-StrictMode -Version Latest

$logPath   = "logs\FINANCE_LOG.csv"
$worldPath = "data\world.json"

# 1) CSV header check
if (-not (Test-Path $logPath)) { throw "Missing $logPath" }
$header = (Get-Content $logPath -First 1).Trim()
$expected = "week,school,donor_yield,expenses,balance,prestige_change,sentiment"
if ($header -ne $expected) {
  throw "CSV header mismatch. Found: '$header' Expected: '$expected'"
}

# 2) Load rows
$rows = Import-Csv $logPath
if (-not $rows) { Write-Host "⚠️ CSV has header but no data rows."; return }

# 3) Duplicate (week,school) check
$dups = $rows | Group-Object week,school | Where-Object { $_.Count -gt 1 }
if ($dups) {
  Write-Host "🟥 Duplicate (week,school) rows found:" -ForegroundColor Red
  $dups | ForEach-Object { Write-Host ("  - {0}" -f $_.Name) }
  throw "Duplicate keys exist. Run your dedup routine."
}

# 4) Sentiment bounds + numeric sanity
$badSent = @()
$badNums = @()
foreach ($r in $rows) {
  $ok = ($r.week -as [int]) -ne $null -and
        ($r.donor_yield -as [double]) -ne $null -and
        ($r.expenses -as [double]) -ne $null -and
        ($r.balance -as [double]) -ne $null -and
        ($r.prestige_change -as [double]) -ne $null -and
        ($r.sentiment -as [double]) -ne $null
  if (-not $ok) { $badNums += $r }
  $s = [double]$r.sentiment
  if ($s -lt -1.0 -or $s -gt 1.0) { $badSent += $r }
}
if ($badNums.Count -gt 0) {
  Write-Host "🟥 Non-numeric fields detected in CSV rows:" -ForegroundColor Red
  $badNums | Select-Object week,school,donor_yield,expenses,balance,prestige_change,sentiment | Format-Table
  throw "Numeric validation failed."
}
if ($badSent.Count -gt 0) {
  Write-Host "🟥 Sentiment out of bounds (must be [-1,1]) in rows:" -ForegroundColor Red
  $badSent | Select-Object week,school,sentiment | Format-Table
  if ($Strict) { throw "Sentiment bound violation(s)." }
}

# 5) world.json parity against latest CSV per school
if (-not (Test-Path $worldPath)) { throw "Missing $worldPath" }
$world = Get-Content $worldPath | ConvertFrom-Json

# Build latest-by-school map
$latest = $rows | Group-Object school | ForEach-Object {
  $_.Group | Sort-Object {[int]$_.week} | Select-Object -Last 1
}

$mismatches = @()
foreach ($r in $latest) {
  $school = $r.school
  if ($null -eq $world.schools.$school) {
    $mismatches += [pscustomobject]@{ school=$school; issue="missing_in_world"; want_balance=[double]$r.balance; want_sent=[double]$r.sentiment }
    continue
  }
  $wb = [double]$world.schools.$school.balance
  $ws = [double]$world.schools.$school.sentiment
  $rb = [double]$r.balance
  $rs = [double]$r.sentiment
  if ([math]::Abs($wb - $rb) -gt 0.001 -or [math]::Abs($ws - $rs) -gt 0.001) {
    $mismatches += [pscustomobject]@{ school=$school; issue="value_differs"; world_balance=$wb; csv_balance=$rb; world_sent=$ws; csv_sent=$rs }
  }
}

if ($mismatches.Count -gt 0) {
  Write-Host "🟨 world.json mismatches with latest CSV:" -ForegroundColor Yellow
  $mismatches | Format-Table -AutoSize

  if ($FixWorld) {
    # Fix: align world.json with latest csv values
    # Re-load world as hashtable-like via JSON again (simple assignment)
    $world = Get-Content $worldPath | ConvertFrom-Json
    foreach ($r in $latest) {
      $s = $r.school
      if ($null -eq $world.schools.$s) {
        # add if missing
        $world.schools | Add-Member -NotePropertyName $s -NotePropertyValue ([pscustomobject]@{ balance = 0; sentiment = 0.0 })
      }
      $world.schools.$s.balance   = [math]::Round([double]$r.balance,2)
      $world.schools.$s.sentiment = [math]::Round([double]$r.sentiment,2)
      if ([int]$r.week -gt [int]$world.globals.week) { $world.globals.week = [int]$r.week }
    }
    $world | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -Path $worldPath
    Write-Host "✅ world.json updated to match latest CSV."
    $mismatches = @()
  } elseif ($Strict) {
    throw "world.json is out of sync with CSV (run with -FixWorld to align)."
  }
}

if ($mismatches.Count -eq 0) {
  Write-Host "✅ Finance validation passed."
}
