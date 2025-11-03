# scripts/Finance-Min.ps1
# v19.2 — Minimal Finance (clean rebuild)

Set-StrictMode -Version Latest

function Get-FinancePaths {
    [pscustomobject]@{
        StatePath = "data\finance_state.json"
        LogPath   = "logs\FINANCE_LOG.csv"
        WorldPath = "data\world.json"
    }
}

function Initialize-Finance {
    $p = Get-FinancePaths

    if (-not (Test-Path $p.LogPath)) {
        "week,school,donor_yield,expenses,balance,prestige_change,sentiment" | Out-File $p.LogPath -Encoding utf8
    }

    $state = @{
        week             = 0
        balance          = 0
        last_donor_yield = 0
        last_expenses    = 0
        last_prestige    = 0
        sentiment        = 0.0
    }
    $state | ConvertTo-Json | Out-File $p.StatePath -Encoding utf8

    # seed world.json minimally
    $world = Get-World
    Ensure-School -world $world -School "State U"
    Save-World $world

    Write-Host "✅ Minimal finance initialized."
    Write-Host " - State : $($p.StatePath)"
    Write-Host " - Log   : $($p.LogPath)"
    Write-Host " - World : $($p.WorldPath)"
}

# ---------- world.json helpers ----------
function ConvertTo-Hashtable($obj) {
    if ($null -eq $obj) { return @{} }
    if ($obj -is [hashtable]) { return $obj }
    $ht = @{}
    $obj.PSObject.Properties | ForEach-Object { $ht[$_.Name] = $_.Value }
    return $ht
}

function Get-World {
    $p = Get-FinancePaths
    if (Test-Path $p.WorldPath) {
        $w = Get-Content $p.WorldPath | ConvertFrom-Json
        if ($null -eq $w.globals) { $w | Add-Member -Force NoteProperty globals ([pscustomobject]@{ week = 0; sentiment_min = -1.0; sentiment_max = 1.0 }) }
        $w | Add-Member -Force NoteProperty schools (ConvertTo-Hashtable $w.schools)
        return $w
    }
    return [pscustomobject]@{
        globals = [pscustomobject]@{ week = 0; sentiment_min = -1.0; sentiment_max = 1.0 }
        schools = @{}
    }
}

function Ensure-School {
    param(
        [Parameter(Mandatory)] $world,
        [Parameter(Mandatory)][string] $School
    )
    $world.schools = ConvertTo-Hashtable $world.schools
    if (-not $world.schools.ContainsKey($School)) {
        $world.schools[$School] = [pscustomobject]@{ balance = 0; sentiment = 0.0 }
    }
}

function Save-World($world) {
    if ($world.schools -is [hashtable]) {
        $world.schools = [pscustomobject]$world.schools
    }
    $p = Get-FinancePaths
    $world | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -Path $p.WorldPath
}

# ---------- main commands ----------
function Add-FinanceTick {
    param(
        [Parameter(Mandatory=$true)][int]$Week,
        [Parameter(Mandatory=$false)][string]$School = "State U",
        [Parameter(Mandatory=$false)][double]$DonorYield = 0,
        [Parameter(Mandatory=$false)][double]$Expenses = 0,
        [Parameter(Mandatory=$false)][double]$PrestigeChange = 0.0
    )

    # input guards
    if ([string]::IsNullOrWhiteSpace($School)) { throw "School cannot be empty." }
    if ($Week -lt 0)                            { throw "Week must be >= 0." }
    if ([double]::IsNaN($DonorYield) -or [double]::IsInfinity($DonorYield)) { throw "DonorYield must be a finite number." }
    if ([double]::IsNaN($Expenses)    -or [double]::IsInfinity($Expenses))  { throw "Expenses must be a finite number." }
    if ([double]::IsNaN($PrestigeChange) -or [double]::IsInfinity($PrestigeChange)) { throw "PrestigeChange must be a finite number." }
    if ($Expenses -lt 0) { throw "Expenses cannot be negative." }
    if ($PrestigeChange -lt -5 -or $PrestigeChange -gt 5) { throw "PrestigeChange must be in [-5, 5]." }

    $p = Get-FinancePaths
    if (-not (Test-Path $p.StatePath)) { throw "Finance state not found. Run Initialize-Finance first." }

    # world snapshot for per-school math
    $world = Get-World
    Ensure-School -world $world -School $School
    $prevBalance   = [double]$world.schools[$School].balance
    $prevSentiment = [double]$world.schools[$School].sentiment

    $balanceNew = [math]::Round(($prevBalance + $DonorYield - $Expenses), 2)
    $sentNext   = [double]([math]::Round(($prevSentiment + (0.1 * $PrestigeChange)), 2))
    if ($sentNext -gt 1) { $sentNext = 1 }
    if ($sentNext -lt -1) { $sentNext = -1 }
    $prestOut   = [math]::Round($PrestigeChange, 2)

    # ensure header
    if (-not (Test-Path $p.LogPath)) {
        "week,school,donor_yield,expenses,balance,prestige_change,sentiment" | Out-File $p.LogPath -Encoding utf8
    }

    # replace existing (Week,School) row; then append new
    $all = Get-Content $p.LogPath
    $headerOk = ($all.Count -gt 0 -and $all[0] -eq "week,school,donor_yield,expenses,balance,prestige_change,sentiment")
    if ($headerOk) {
        $header = $all[0]
        $rows   = @($all | Select-Object -Skip 1 | Where-Object { $_ -notmatch "^\s*$" })
        # remove any existing row that starts with "Week,School,"
        $rows   = $rows | Where-Object { $_ -notmatch ("^{0},{1}," -f [regex]::Escape([string]$Week), [regex]::Escape($School)) }
        $newRow = ("{0},{1},{2},{3},{4},{5},{6}" -f $Week,$School,$DonorYield,$Expenses,$balanceNew,$prestOut,$sentNext)
        $out    = @($header) + $rows + $newRow
        $out | Set-Content -Encoding UTF8 -Path $p.LogPath
    } else {
        $newRow = ("{0},{1},{2},{3},{4},{5},{6}" -f $Week,$School,$DonorYield,$Expenses,$balanceNew,$prestOut,$sentNext)
        "week,school,donor_yield,expenses,balance,prestige_change,sentiment" | Out-File $p.LogPath -Encoding utf8
        Add-Content -Path $p.LogPath -Value $newRow
    }

    # keep legacy state.json in sync (compat)
    $state = Get-Content $p.StatePath | ConvertFrom-Json
    $state.week             = $Week
    $state.balance          = $balanceNew
    $state.last_donor_yield = $DonorYield
    $state.last_expenses    = $Expenses
    $state.last_prestige    = $prestOut
    $state.sentiment        = $sentNext
    $state | ConvertTo-Json | Out-File $p.StatePath -Encoding utf8

    # update world snapshot
    $world.schools[$School].balance   = $balanceNew
    $world.schools[$School].sentiment = $sentNext
    if ($Week -gt [int]$world.globals.week) { $world.globals.week = $Week }
    Save-World $world

    Write-Host ("💾 Week {0} | {1} | Balance: {2} | Sentiment: {3}" -f $Week, $School, $balanceNew, $sentNext)
}

function Show-FinanceState {
    $p = Get-FinancePaths
    if (-not (Test-Path $p.StatePath)) { Write-Warning "No state file found. Run Initialize-Finance."; return }
    Get-Content $p.StatePath | Write-Output
}

function Update-WorldSnapshot {
    param(
        [Parameter(Mandatory)][string]$School,
        [int]$Week = $null,
        [double]$Balance = $null,
        [double]$Sentiment = $null
    )
    $world = Get-World
    $world.schools = ConvertTo-Hashtable $world.schools
    Ensure-School -world $world -School $School

    if ($PSBoundParameters.ContainsKey('Balance'))   { $world.schools[$School].balance   = $Balance }
    if ($PSBoundParameters.ContainsKey('Sentiment')) { $world.schools[$School].sentiment = $Sentiment }
    if ($PSBoundParameters.ContainsKey('Week') -and $Week -gt [int]$world.globals.week) { $world.globals.week = $Week }

    $balOut  = $world.schools[$School].balance
    $sentOut = $world.schools[$School].sentiment
    $weekOut = $world.globals.week

    Save-World $world
    Write-Host "✅ world.json updated → School: $School | Balance: $balOut | Sentiment: $sentOut | Week: $weekOut"
}

function Sync-WorldFromFinanceLog {
    $p = Get-FinancePaths
    if (-not (Test-Path $p.LogPath)) { throw "Missing $($p.LogPath)" }

    $header = (Get-Content $p.LogPath -First 1).Trim()
    if ($header -ne "week,school,donor_yield,expenses,balance,prestige_change,sentiment") {
        throw "Unexpected CSV header: '$header'"
    }

    $world = Get-World
    $world.schools = ConvertTo-Hashtable $world.schools

    $rows = Import-Csv $p.LogPath
    $latestBySchool = $rows | Group-Object school | ForEach-Object {
        $_.Group | Sort-Object {[int]$_.week} | Select-Object -Last 1
    }

    foreach ($r in $latestBySchool) {
        $s = $r.school
        Ensure-School -world $world -School $s
        $world.schools[$s].balance   = [math]::Round([double]$r.balance, 2)
        $world.schools[$s].sentiment = [math]::Round([double]$r.sentiment, 2)
        if ([int]$r.week -gt [int]$world.globals.week) { $world.globals.week = [int]$r.week }
    }

    Save-World $world
    Write-Host "✅ world.json synchronized from FINANCE_LOG.csv"
}
# helper: read (Week,School) row or return zeros
function Get-FinanceWeekRow {
    param([int]$Week, [string]$School)
    $p = Get-FinancePaths
    if (-not (Test-Path $p.LogPath)) {
        return [pscustomobject]@{ week=$Week; school=$School; donor_yield=0; expenses=0; prestige_change=0 }
    }
    $rows = Import-Csv $p.LogPath | Where-Object { [int]$_.week -eq $Week -and $_.school -eq $School }
    if ($rows) {
        $r = $rows[-1]
        return [pscustomobject]@{
            week=[int]$r.week; school=$r.school;
            donor_yield=[double]$r.donor_yield; expenses=[double]$r.expenses; prestige_change=[double]$r.prestige_change
        }
    }
    return [pscustomobject]@{ week=$Week; school=$School; donor_yield=0; expenses=0; prestige_change=0 }
}

# safer Commit-SportsOps: handles missing last_ops_week + uses latest week intelligently
function Commit-SportsOps {
    param(
        [Parameter(Mandatory)][string]$School,
        [int]$Week = $null,
        [switch]$Force
    )
    $world = Get-World
    Ensure-Sports -world $world -School $School
    $world.schools = ConvertTo-Hashtable $world.schools
    $sch = $world.schools[$School]

    # choose week: explicit > world.globals.week > latest in CSV > 1
    $chosenWeek = $Week
    if ($null -eq $chosenWeek -or $chosenWeek -le 0) {
        $chosenWeek = [int]$world.globals.week
        $p = Get-FinancePaths
        if (Test-Path $p.LogPath) {
            $maxCsv = (Import-Csv $p.LogPath | Measure-Object -Property week -Maximum).Maximum
            if ($maxCsv -and [int]$maxCsv -gt $chosenWeek) { $chosenWeek = [int]$maxCsv }
        }
        if ($chosenWeek -le 0) { $chosenWeek = 1 }
    }

    # safe read for last_ops_week
    $lastOpsProp = $sch.psobject.Properties['last_ops_week']
    $lastOpsWeek = if ($lastOpsProp) { [int]$lastOpsProp.Value } else { $null }
    if (-not $Force -and $lastOpsWeek -eq $chosenWeek) {
        Write-Warning "$School already committed sports ops for week $chosenWeek. Use -Force to reapply."
        return
    }

    # compute weekly ops total (baseline * level * (1 - sponsor_disc)) / 52
    $costs  = Get-SportCosts
    $levels = $sch.sports_levels
    $disc   = Get-SponsorDiscount -School $School

    $annualTotal = 0.0
    foreach ($p in $costs.PSObject.Properties) {
        $sport = $p.Name
        $baseAnnual = [double]$p.Value
        $level = ($levels.$sport ?? "Maintain")
        $mult  = [double]$script:SportLevelMap[$level]
        $annualTotal += ($baseAnnual * $mult * (1.0 - $disc))
    }
    $weeklyOps = [math]::Round(($annualTotal / 52.0), 2)

    # merge into (Week,School) row
    $row     = Get-FinanceWeekRow -Week $chosenWeek -School $School
    $newDon  = [double]$row.donor_yield
    $newExp  = [math]::Round(([double]$row.expenses + $weeklyOps), 2)
    $newPrest= [double]$row.prestige_change

    Add-FinanceTick -Week $chosenWeek -School $School -DonorYield $newDon -Expenses $newExp -PrestigeChange $newPrest

    # persist last_ops_week (create if missing)
    if ($lastOpsProp) { $sch.last_ops_week = $chosenWeek }
    else { $sch | Add-Member -NotePropertyName last_ops_week -NotePropertyValue $chosenWeek }
    Save-World $world

    Write-Host ("✅ Committed sports ops for {0} (Week {1}) → +{2:n0} expenses (after {3:p0} sponsor discount)" -f $School, $chosenWeek, $weeklyOps, $disc)
}
function Advance-Week {
  param([int]$Week = $null,[string]$Sport='Football',[switch]$AutoBank)
  $w = Get-World
  if ($null -eq $Week -or $Week -le 0) { $Week = [int]$w.globals.week; if ($Week -le 0) { $Week = 1 } }
  $w.schools = ConvertTo-Hashtable $w.schools
  $hasEvents = [bool](Get-Command Apply-EventWeekEffects -ErrorAction SilentlyContinue)
  $hasDonors = [bool](Get-Command Process-DonorsForWeek  -ErrorAction SilentlyContinue)
  $hasMatch  = [bool](Get-Command Apply-MatchingGifts    -ErrorAction SilentlyContinue)
  foreach ($s in $w.schools.Keys) {
    if ($hasEvents) { Apply-EventWeekEffects -School $s -Week $Week }
    if ($hasDonors) { Process-DonorsForWeek  -School $s -Sport $Sport -Week $Week }
    if ($hasMatch)  { Apply-MatchingGifts    -School $s -Week $Week }
    Apply-DonorDecayToWeek -School $s -Sport $Sport -Week $Week
    $t = Update-GovernanceSignals -School $s -Sport $Sport -Week $Week
# --- v19.3 Threshold Events Hook BEGIN ---
. "$PSScriptRoot\Threshold-Events.ps1"
$thresholds = Apply-ThresholdEvents -World $world -Week $week
if ($thresholds.Count -gt 0) {
    Write-Host "⚠ Threshold events triggered:" ($thresholds | Select-Object -ExpandProperty event -Unique -Join ', ')
}
# --- v19.3 Threshold Events Hook END ---
# --- v19.3 Threshold Events Hook BEGIN ---
. "$PSScriptRoot\Threshold-Events.ps1"
$thresholds = Apply-ThresholdEvents -World $world -Week $week
if ($thresholds.Count -gt 0) {
    Write-Host "⚠ Threshold events triggered:" ($thresholds | Select-Object -ExpandProperty event -Unique -Join ', ')
}
# --- v19.3 Threshold Events Hook END ---
    "{0}: trend={1} donorDecay={2:p0} morale={3} board={4} ADhot={5} Coach({6})={7}" -f `
      $t.school, $t.loss_trend_5, $t.donor_decay_pct, $t.donor_morale, $t.board_conf, $t.ad_hotseat, $Sport, $t.coach_hotseat | Write-Host
    if ($AutoBank) { Bank-SettleNow -School $s }
  }
  $w.globals.week = [int]$Week + 1
  Save-World $w
  if (Test-Path .\scripts\Finance-Trends.ps1) { .\scripts\Finance-Trends.ps1 | Out-Null }
  Write-Host ("✅ Closed Week {0} → advanced to Week {1}" -f $Week, $w.globals.week)
}


