# College AD — Threshold Events (v19.3)
Set-StrictMode -Version Latest

function Get-WorldSafe {
    if (Get-Command Get-World -ErrorAction SilentlyContinue) { return (Get-World) }
    $path = Join-Path -Path (Get-Location) -ChildPath "data\world.json"
    if (!(Test-Path $path)) { throw "Get-WorldSafe: data\world.json not found at $path" }
    return (Get-Content $path -Raw | ConvertFrom-Json)
}

function Save-WorldSafe {
    param([Parameter(Mandatory=$true)][object]$World)
    if (Get-Command Save-World -ErrorAction SilentlyContinue) { Save-World $World | Out-Null; return }
    $path = Join-Path -Path (Get-Location) -ChildPath "data\world.json"
    $World | ConvertTo-Json -Depth 100 | Set-Content -Path $path -Encoding utf8
}

function Ensure-LogsFolder {
    $logs = Join-Path -Path (Get-Location) -ChildPath "logs"
    if (!(Test-Path $logs)) { New-Item -ItemType Directory -Path $logs | Out-Null }
    return $logs
}

function Get-WeekSafe {
    param([object]$World)
    if ($World -and $World.PSObject.Properties.Name -contains 'week' -and $World.week -ne $null) { return [int]$World.week }
    $fin = Join-Path (Get-Location) "logs\FINANCE_LOG.csv"
    if (Test-Path $fin) {
        try {
            $last = Import-Csv $fin | Select-Object -ExpandProperty week -ErrorAction Stop |
                    ForEach-Object {[int]$_} | Sort-Object | Select-Object -Last 1
            if ($last -ne $null) { return [int]$last }
        } catch {}
    }
    return 0
}

function Test-ThresholdEvents {
    [CmdletBinding()]
    param([Parameter()][object]$World)

    if (-not $World) { $World = Get-WorldSafe }

    $events = @()
    foreach ($school in $World.schools.Keys) {
        $node = $World.schools.$school
        if ($null -eq $node -or $null -eq $node.signals) { continue }
        $s = $node.signals

        if ($s.ad_hotseat -ge 90) {
            $events += [pscustomobject]@{school=$school;event="VOTE_NO_CONFIDENCE";impact="major"}
            $s.board_confidence = [math]::Max(0,  ($s.board_confidence + 0) - 0.15)
            $s.sentiment        = [math]::Max(-1, ($s.sentiment        + 0) - 0.10)
        } elseif ($s.ad_hotseat -ge 70) {
            $events += [pscustomobject]@{school=$school;event="BOARD_DEMANDS_PLAN";impact="minor"}
            $s.sentiment        = [math]::Max(-1, ($s.sentiment        + 0) - 0.05)
            $s.donor_morale     = [math]::Max(0,  ($s.donor_morale     + 0) - 0.03)
        }

        if ($s.coach_hotseat -ge 80) {
            $events += [pscustomobject]@{school=$school;event="BACK_OR_FIRE";impact="minor"}
            $s.sentiment        = [math]::Max(-1, ($s.sentiment        + 0) - 0.04)
            $s.board_confidence = [math]::Max(0,  ($s.board_confidence + 0) - 0.05)
        }

        if ($s.donor_morale -le 0.25) {
            $events += [pscustomobject]@{school=$school;event="BOOSTER_RIFT";impact="minor"}
        }

        if ($s.board_confidence -le 0.30) {
            $events += [pscustomobject]@{school=$school;event="EMERGENCY_MEETING";impact="major"}
        }
    }
    return ,$events
}

function Apply-ThresholdEvents {
    [CmdletBinding()]
    param(
        [Parameter()][object]$World,
        [Parameter()][int]$Week
    )

    if (-not $World) { $World = Get-WorldSafe }
    if (-not $PSBoundParameters.ContainsKey('Week')) { $Week = Get-WeekSafe -World $World }

    $hits = Test-ThresholdEvents -World $World
    if ($hits.Count -gt 0) {
        $logs = Ensure-LogsFolder
        $logPath = Join-Path $logs "THRESHOLD_EVENTS.csv"
        if (!(Test-Path $logPath)) { "week,school,event,impact" | Out-File $logPath -Encoding utf8 }
        foreach ($e in $hits) { "$Week,$($e.school),$($e.event),$($e.impact)" | Out-File $logPath -Append -Encoding utf8 }
        Save-WorldSafe -World $World
    }
    return $hits
}

if ($ExecutionContext.SessionState.Module) { Export-ModuleMember -Function Test-ThresholdEvents,Apply-ThresholdEvents }

