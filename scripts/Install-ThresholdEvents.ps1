# Install-ThresholdEvents.ps1 — v19.3 PowerShell-only installer
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root    = (Get-Location).Path
$scripts = Join-Path $root "scripts"
$data    = Join-Path $root "data"
$logs    = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

function Write-File($Path, [string]$Content) {
  $dir = Split-Path -Parent $Path
  if (!(Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  $Content | Set-Content -Path $Path -Encoding utf8
}

# 1) Create Threshold-Events.ps1 (idempotent overwrite)
$thresholdsPath = Join-Path $scripts "Threshold-Events.ps1"
$thresholdsCode = @"
# College AD — Threshold Events (v19.3)
Set-StrictMode -Version Latest

function Get-WorldSafe {
    if (Get-Command Get-World -ErrorAction SilentlyContinue) { return (Get-World) }
    \$path = Join-Path -Path (Get-Location) -ChildPath "data\world.json"
    if (!(Test-Path \$path)) { throw "Get-WorldSafe: data\world.json not found at \$path" }
    return (Get-Content \$path -Raw | ConvertFrom-Json)
}

function Save-WorldSafe {
    param([Parameter(Mandatory=\$true)][object]\$World)
    if (Get-Command Save-World -ErrorAction SilentlyContinue) { Save-World \$World | Out-Null; return }
    \$path = Join-Path -Path (Get-Location) -ChildPath "data\world.json"
    \$World | ConvertTo-Json -Depth 100 | Set-Content -Path \$path -Encoding utf8
}

function Ensure-LogsFolder {
    \$logs = Join-Path -Path (Get-Location) -ChildPath "logs"
    if (!(Test-Path \$logs)) { New-Item -ItemType Directory -Path \$logs | Out-Null }
    return \$logs
}

function Get-WeekSafe {
    param([object]\$World)
    if (\$World -and \$World.PSObject.Properties.Name -contains 'week' -and \$World.week -ne \$null) {
        return [int]\$World.week
    }
    # try to infer from FINANCE_LOG.csv (max week)
    \$fin = Join-Path (Get-Location) "logs\FINANCE_LOG.csv"
    if (Test-Path \$fin) {
        try {
            \$last = Import-Csv \$fin | Select-Object -ExpandProperty week -ErrorAction Stop |
                    ForEach-Object {[int]\$_} | Sort-Object | Select-Object -Last 1
            if (\$last -ne \$null) { return [int]\$last }
        } catch {}
    }
    return 0
}

function Test-ThresholdEvents {
    [CmdletBinding()]
    param([Parameter()][object]\$World)

    if (-not \$World) { \$World = Get-WorldSafe }

    \$events = @()
    foreach (\$school in \$World.schools.Keys) {
        \$node = \$World.schools.\$school
        if (\$null -eq \$node -or \$null -eq \$node.signals) { continue }
        \$s = \$node.signals

        if (\$s.ad_hotseat -ge 90) {
            \$events += [pscustomobject]@{school=\$school;event="VOTE_NO_CONFIDENCE";impact="major"}
            \$s.board_confidence = [math]::Max(0,  (\$s.board_confidence + 0) - 0.15)
            \$s.sentiment        = [math]::Max(-1, (\$s.sentiment        + 0) - 0.10)
        } elseif (\$s.ad_hotseat -ge 70) {
            \$events += [pscustomobject]@{school=\$school;event="BOARD_DEMANDS_PLAN";impact="minor"}
            \$s.sentiment        = [math]::Max(-1, (\$s.sentiment        + 0) - 0.05)
            \$s.donor_morale     = [math]::Max(0,  (\$s.donor_morale     + 0) - 0.03)
        }

        if (\$s.coach_hotseat -ge 80) {
            \$events += [pscustomobject]@{school=\$school;event="BACK_OR_FIRE";impact="minor"}
            \$s.sentiment        = [math]::Max(-1, (\$s.sentiment        + 0) - 0.04)
            \$s.board_confidence = [math]::Max(0,  (\$s.board_confidence + 0) - 0.05)
        }

        if (\$s.donor_morale -le 0.25) {
            \$events += [pscustomobject]@{school=\$school;event="BOOSTER_RIFT";impact="minor"}
        }

        if (\$s.board_confidence -le 0.30) {
            \$events += [pscustomobject]@{school=\$school;event="EMERGENCY_MEETING";impact="major"}
        }
    }
    return ,\$events
}

function Apply-ThresholdEvents {
    [CmdletBinding()]
    param(
        [Parameter()][object]\$World,
        [Parameter()][int]\$Week
    )

    if (-not \$World) { \$World = Get-WorldSafe }
    if (-not \$PSBoundParameters.ContainsKey('Week')) { \$Week = Get-WeekSafe -World \$World }

    \$hits = Test-ThresholdEvents -World \$World
    if (\$hits.Count -gt 0) {
        \$logs = Ensure-LogsFolder
        \$logPath = Join-Path \$logs "THRESHOLD_EVENTS.csv"
        if (!(Test-Path \$logPath)) { "week,school,event,impact" | Out-File \$logPath -Encoding utf8 }
        foreach (\$e in \$hits) { "\$Week,\$((\$e.school)),\$((\$e.event)),\$((\$e.impact))" | Out-File \$logPath -Append -Encoding utf8 }
        Save-WorldSafe -World \$World
    }
    return \$hits
}

Export-ModuleMember -Function Test-ThresholdEvents,Apply-ThresholdEvents -ErrorAction SilentlyContinue
"@

Write-File $thresholdsPath $thresholdsCode

# 2) Create SelfTest-Thresholds.ps1
$testPath = Join-Path $scripts "SelfTest-Thresholds.ps1"
$testCode = @"
# SelfTest-Thresholds.ps1 — v19.3 smoke test
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Load finance helpers if available
$finance = Join-Path $PSScriptRoot "Finance-Min.ps1"
if (Test-Path $finance) { . $finance }

# Load threshold module
. (Join-Path $PSScriptRoot "Threshold-Events.ps1")

# Pull world (safe) and force some triggers on the first school
$w = if (Get-Command Get-World -ErrorAction SilentlyContinue) { Get-World } else { Get-Content (Join-Path (Split-Path $PSScriptRoot -Parent) "data\world.json") -Raw | ConvertFrom-Json }
$wk = if ($w.week) { [int]$w.week } else { 0 }
$school = ($w.schools.Keys | Select-Object -First 1)
$w.schools.$school.signals.ad_hotseat = 95
$w.schools.$school.signals.coach_hotseat = 82
$w.schools.$school.signals.board_confidence = 0.28
$w.schools.$school.signals.donor_morale = 0.20

$hits = Apply-ThresholdEvents -World $w -Week $wk
"Hits: $($hits.Count)"
$hits | Format-Table -AutoSize

$log = Join-Path (Join-Path (Split-Path $PSScriptRoot -Parent) "logs") "THRESHOLD_EVENTS.csv"
if (Test-Path $log) {
  "---- tail THRESHOLD_EVENTS.csv ----"
  Get-Content $log | Select-Object -Last 10
} else { "THRESHOLD_EVENTS.csv not found." }
"@

Write-File $testPath $testCode

# 3) Hook into Finance-Min.ps1 after Update-GovernanceSignals
$finance = Join-Path $scripts "Finance-Min.ps1"
if (!(Test-Path $finance)) { throw "Missing required file: $finance" }

$hookBegin = "# --- v19.3 Threshold Events Hook BEGIN ---"
$hookEnd   = "# --- v19.3 Threshold Events Hook END ---"
$hookBlock = @"
$hookBegin
. `"$PSScriptRoot\Threshold-Events.ps1`"
# world/week may or may not exist in caller scope; fall back if needed
try {
  if (-not (Get-Variable -Name world -Scope 1 -ErrorAction SilentlyContinue)) { throw "world var not found" }
  if (-not (Get-Variable -Name week  -Scope 1 -ErrorAction SilentlyContinue)) { throw "week var not found" }
} catch {
  if (Get-Command Get-World -ErrorAction SilentlyContinue) {
    $world = Get-World
  } else {
    $wpath = Join-Path (Split-Path -Parent $PSScriptRoot) "data\world.json"
    $world = Get-Content $wpath -Raw | ConvertFrom-Json
  }
  $week  = if ($world.week) { [int]$world.week } else { 0 }
}
$thresholds = Apply-ThresholdEvents -World $world -Week $week
if ($thresholds.Count -gt 0) {
    Write-Host "⚠ Threshold events triggered:" ($thresholds | Select-Object -ExpandProperty event -Unique -Join ', ')
}
$hookEnd
"@

$fm = Get-Content $finance -Raw
if ($fm -notmatch [regex]::Escape($hookBegin)) {
  $pattern = 'Update-GovernanceSignals[^\r\n]*[\r\n]'
  if ($fm -match $pattern) {
    $fm = [regex]::Replace($fm, $pattern, ('$0' + $hookBlock + "`r`n"), 1)
    $fm | Set-Content -Path $finance -Encoding utf8
    Write-Host "Patched Finance-Min.ps1 with Threshold Events hook."
  } else {
    Write-Warning "Could not find 'Update-GovernanceSignals' call; appending hook to end of file."
    Add-Content -Path $finance -Value "`r`n$hookBlock`r`n"
  }
} else {
  Write-Host "Finance-Min.ps1 already contains Threshold Events hook. Skipping."
}

# 4) Add alias to AD-Menu.ps1
$menu = Join-Path $scripts "AD-Menu.ps1"
if (Test-Path $menu) {
  $aliasLine = 'Set-Alias check-thresholds Apply-ThresholdEvents'
  $menuText = Get-Content $menu -Raw
  if ($menuText -notmatch [regex]::Escape($aliasLine)) {
    Add-Content -Path $menu -Value "`r`n$aliasLine`r`n"
    Write-Host "Added alias 'check-thresholds' to AD-Menu.ps1."
  } else {
    Write-Host "Alias 'check-thresholds' already present. Skipping."
  }
} else {
  Write-Warning "AD-Menu.ps1 not found; alias not added. (Optional step)"
}

# 5) Load into this session + smoke test (non-destructive)
. $finance
. $thresholdsPath

try {
  $w = if (Get-Command Get-World -ErrorAction SilentlyContinue) { Get-World } else { Get-Content (Join-Path $data "world.json") -Raw | ConvertFrom-Json }
  $wk = if ($w.week) { [int]$w.week } else { 0 }
  $hits = Apply-ThresholdEvents -World $w -Week $wk
  if ($hits.Count -gt 0) {
    Write-Host "Smoke test: $($hits.Count) threshold event(s) logged for week $wk."
  } else {
    Write-Host "Smoke test: no thresholds currently tripped (this is fine)."
  }
} catch {
  Write-Warning "Smoke test skipped: $($_.Exception.Message)"
}

Write-Host "✅ Install-ThresholdEvents complete."
