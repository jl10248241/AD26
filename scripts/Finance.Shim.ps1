# Finance.Shim.ps1 — temporary NO-OPs while finance system is removed
Set-StrictMode -Version Latest
function _FinMsg([string]$name){ Write-Warning "$name is temporarily unavailable (finance system removed)."; }
function AD-FinInit   { _FinMsg "AD-FinInit" }
function AD-FinShow   { _FinMsg "AD-FinShow" }
function AD-FinMove   { _FinMsg "AD-FinMove" }
function AD-FinEarn   { _FinMsg "AD-FinEarn" }
function AD-FinSpend  { _FinMsg "AD-FinSpend" }
function AD-FinSnap   { _FinMsg "AD-FinSnap" }
function AD-FinReport { _FinMsg "AD-FinReport" }
# Optional: keep old short aliases pointing to stubs (comment out if you prefer hard failures)
Set-Alias spend AD-FinSpend -Scope Global -Force
Set-Alias earn  AD-FinEarn  -Scope Global -Force
