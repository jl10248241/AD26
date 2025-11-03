# AD-Menu.ps1 — gameplay command aliases

# --- Finance Command Aliases (v19.2 Minimal) ---
Set-Alias finance-init Initialize-Finance
Set-Alias finance-add  Add-FinanceTick
Set-Alias finance-show Show-FinanceState


Set-Alias finance-init      Initialize-Finance
Set-Alias finance-add       Add-FinanceTick
Set-Alias finance-show      Show-FinanceState
Set-Alias finance-update    Update-WorldSnapshot
Set-Alias finance-sync      Sync-WorldFromFinanceLog


function finance-validate { param([Parameter(ValueFromRemainingArguments=$true)]$Args) & .\scripts\Finance-Validate.ps1 @Args }
function finance-report   { & .\scripts\Finance-Trends.ps1 }

function close-year { param([switch]$ResetWeek) & .\scripts\Close-Year.ps1 @PSBoundParameters }
function budget-open  { param([int]$OpenWeek,[int]$WindowWeeks) Start-BudgetPlanning @PSBoundParameters }
function budget-close { Close-BudgetPlanning }
function budget-info  { Get-SeasonInfo }

Set-Alias close-week Close-Week

Set-Alias close-week Advance-Week
Set-Alias check-thresholds Apply-ThresholdEvents
Set-Alias check-thresholds Apply-ThresholdEvents
