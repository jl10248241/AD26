# College AD — v18 Launcher (structural fidelity)
[CmdletBinding()]
param(
  [string]$PythonCmd = "",
  [switch]$Inbox,
  [switch]$ApplyStatus,
  [string]$StatusPath = "status\PROJECT_STATUS_v18.0.md",
  [switch]$VerboseMode
)

function Write-Info($m){Write-Host $m -ForegroundColor Cyan}
function Write-Ok($m){Write-Host $m -ForegroundColor Green}
function Write-Warn($m){Write-Warning $m}

$root=(Get-Location).Path
$inboxCli=Join-Path $root "engine\src\ui_inbox_cli.py"
$cfgDir=Join-Path $root "engine\config"
$inboxDir=Join-Path $root "logs\INBOX"

$missing=@()
foreach($p in @($inboxCli,$cfgDir,$inboxDir)){if(-not(Test-Path $p)){$missing+=$p}}
if($missing.Count){
  Write-Warn "Missing expected paths (no creation per Rule #1):"
  $missing|%{Write-Warn "  - $_"}
  exit 1
}

$env:COLLEGE_AD_VERSION="18"
Write-Ok "COLLEGE_AD_VERSION=18"

function Resolve-Python([string]$Preferred){
  foreach($c in @($Preferred,"py","python","python3")){
    if(!$c){continue}
    try{
      $v=& $c --version 2>$null
      if($LASTEXITCODE -eq 0){return $c}
    }catch{}
  };return $null
}

$py=Resolve-Python $PythonCmd
if(-not$py){Write-Warn "Python not found";exit 1}
if($VerboseMode){Write-Info "Using Python: $py"}

if($ApplyStatus){
  $statusFile=Join-Path $root $StatusPath
  $parent=Split-Path -Parent $statusFile
  if(Test-Path $parent){
@"
# College AD v18
Started: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
"@|Out-File -FilePath $statusFile -Encoding UTF8 -Force
    Write-Ok "Wrote $StatusPath"
  }else{
    Write-Warn "Parent folder missing (Rule #1): $parent"
  }
}

Write-Info "Launching Inbox CLI..."
& $py $inboxCli
