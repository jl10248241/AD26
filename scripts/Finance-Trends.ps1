# scripts/Finance-Trends.ps1
Set-StrictMode -Version Latest
$logPath = "logs\FINANCE_LOG.csv"
$docPath = "docs\FINANCE_TRENDS.md"

if (-not (Test-Path $logPath)) { throw "Missing $logPath" }
$rows = Import-Csv $logPath
if (-not $rows) { "No finance rows yet." | Set-Content -Encoding UTF8 -Path $docPath; exit }

$latestWeek = ($rows | Measure-Object -Property week -Maximum).Maximum

$bySchool = $rows | Group-Object school | ForEach-Object {
  $g = $_.Group | Sort-Object {[int]$_.week}
  $latest = $g[-1]
  $last4  = if ($g.Count -ge 4) { $g[-4..-1] } else { $g }

  $donorSum   = ($g | Measure-Object -Property donor_yield -Sum).Sum
  $expenseSum = ($g | Measure-Object -Property expenses -Sum).Sum

  $firstBal = [double]$last4[0].balance
  $lastBal  = [double]$last4[-1].balance
  $drift4   = [math]::Round($lastBal - $firstBal, 2)
  $avgPrest = [math]::Round((($g | Measure-Object -Property prestige_change -Average).Average), 2)

  [pscustomobject]@{
    school          = $_.Name
    weeks_logged    = $g.Count
    latest_week     = [int]$latest.week
    donor_total     = [double]$donorSum
    expense_total   = [double]$expenseSum
    ending_balance  = [double]$latest.balance
    latest_sent     = [double]$latest.sentiment
    drift_last4     = $drift4
    avg_prestige    = $avgPrest
  }
}

$lines = @()
$lines += "# Finance Trends"
$lines += "_Updated: $(Get-Date -Format 'yyyy-MM-dd HH:mm') — Latest Week: $latestWeek"
$lines += ""
$lines += "| School | Weeks | Donors Σ | Expenses Σ | Ending Balance | Sentiment (latest) | Drift (last 4) | Avg ΔPrestige |"
$lines += "|---|---:|---:|---:|---:|---:|---:|---:|"

foreach ($s in $bySchool | Sort-Object school) {
  $lines += ("| {0} | {1} | {2:n0} | {3:n0} | {4:n0} | {5:n2} | {6:n0} | {7:n2} |" -f `
    $s.school, $s.weeks_logged, $s.donor_total, $s.expense_total, $s.ending_balance, $s.latest_sent, $s.drift_last4, $s.avg_prestige)
}

$lines | Set-Content -Encoding UTF8 -Path $docPath
Write-Host "✅ Wrote $docPath"

