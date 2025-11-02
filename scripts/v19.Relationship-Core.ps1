<# 
v19.Relationship-Core.ps1
College AD — v19 Task 1: AI Relationship Core (PowerShell wrappers)

USAGE (session-safe):
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  . .\scripts\v19.Relationship-Core.ps1

Provided Commands:
  Init-RelationshipCore           → Creates/validates data\relationships.json (no new folders auto-created)
  Apply-RelEvent                  → Applies an event to relationship scores
  Advance-RelationshipWeek        → Applies weekly decay & saves log
  Show-RelationshipReport         → Prints a table summary in console
  Export-RelationshipReport       → Writes docs\RELATIONSHIP_REPORT_v19.md (if docs\ exists)

Rule #1 honored: this script only writes to existing folders (data\, logs\, docs\ if present).
#>

Set-StrictMode -Version Latest

function Use-ProjectPython {
  param([string]$PythonExe = "python")
  $ver = & $PythonExe --version 2>$null
  if (-not $ver) { throw "Python not found on PATH. Install Python 3.9+ or add 'python' to PATH." }
  return $PythonExe
}

function Get-ProjectRoot {
  # Resolve from typical structure where this script lives under scripts\
  $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
  return (Split-Path -Parent $scriptDir)
}

function _RelCorePath {
  param([string]$rel)
  $root = Get-ProjectRoot
  return (Join-Path $root $rel)
}

function Init-RelationshipCore {
  [CmdletBinding()]
  param(
    [switch]$Force
  )
  $root = Get-ProjectRoot
  $dataDir = Join-Path $root "data"
  $logsDir = Join-Path $root "logs"

  if (-not (Test-Path $dataDir)) { throw "Missing folder: data\  (Rule #1 prohibits auto-creating. Please create it.)" }
  if (-not (Test-Path $logsDir)) { Write-Host "Note: logs\ not found. Logging will be skipped until it exists." -ForegroundColor Yellow }

  $file = Join-Path $dataDir "relationships.json"
  if ((-not (Test-Path $file)) -or $Force) {
    $py = Use-ProjectPython
    & $py (_RelCorePath "engine\src\relationship_core.py") init --project-root $root | Write-Host
  } else {
    Write-Host "relationships.json already exists. Use -Force to reinitialize." -ForegroundColor Yellow
  }
}

function Apply-RelEvent {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory=$true)][string]$Subject,   # e.g., "Player_AD"
    [Parameter(Mandatory=$true)][string]$Target,    # e.g., "Coach.HeadCoach"
    [Parameter(Mandatory=$true)][ValidateSet("win","loss","donation","scandal","praise","conflict","meeting_good","meeting_bad","media_heat")][string]$Effect,
    [int]$Intensity = 10,
    [ValidateSet("positive","negative","neutral")][string]$Tone = "neutral"
  )
  $py = Use-ProjectPython
  $root = Get-ProjectRoot
  & $py (_RelCorePath "engine\src\relationship_core.py") apply `
      --project-root $root `
      --subject $Subject `
      --target $Target `
      --effect $Effect `
      --intensity $Intensity `
      --tone $Tone
}

function Advance-RelationshipWeek {
  [CmdletBinding()]
  param([int]$Weeks = 1)
  $py = Use-ProjectPython
  $root = Get-ProjectRoot
  & $py (_RelCorePath "engine\src\relationship_core.py") tick --project-root $root --weeks $Weeks
}

function Show-RelationshipReport {
  [CmdletBinding()]
  param([int]$Top = 20)
  $py = Use-ProjectPython
  $root = Get-ProjectRoot
  & $py (_RelCorePath "engine\src\ui_relationship_report.py") --project-root $root --top $Top
}

function Export-RelationshipReport {
  [CmdletBinding()]
  param()
  $root = Get-ProjectRoot
  $docsDir = Join-Path $root "docs"
  if (-not (Test-Path $docsDir)) { throw "docs\ folder not found. Create it to export the markdown report." }
  $out = Join-Path $docsDir "RELATIONSHIP_REPORT_v19.md"
  $py = Use-ProjectPython
  & (Use-ProjectPython) (_RelCorePath "engine\src\ui_relationship_report.py") --project-root $root --md > $out
  Write-Host "Exported: $out" -ForegroundColor Green
}

Set-Alias rel.init Init-RelationshipCore
Set-Alias rel.apply Apply-RelEvent
Set-Alias rel.tick  Advance-RelationshipWeek
Set-Alias rel.show  Show-RelationshipReport
Set-Alias rel.md    Export-RelationshipReport
