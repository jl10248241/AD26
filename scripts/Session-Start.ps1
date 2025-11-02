[CmdletBinding()]
param(
  [switch]$Fix,                 # apply safe fixes (policy + inbox dedupe)
  [switch]$SetResumeFromNewest, # set resume anchor to newest inbox item
  [switch]$QuickActions,        # show ranked list before launch
  [switch]$QASetResumeOnTop,    # also set resume to #1 ranked item
  [switch]$Phone,               # run a Phone scene on top priority item
  [switch]$Meeting,             # run a Meeting scene on top priority item
  [string]$PythonCmd = ""       # explicit python path (optional)
)

function Say($t,$c="Cyan"){ Write-Host $t -ForegroundColor $c }
function Ok($t){ Write-Host $t -ForegroundColor Green }
function Warn($t){ Write-Warning $t }
function Get-Json($p){ try { Get-Content $p -Raw | ConvertFrom-Json -ErrorAction Stop } catch { $null } }

function Normalize-ForHash($obj){
  $copy=@{}
  foreach($p in $obj.PSObject.Properties){
    if($p.Name -in @("id","timestamp","metadata")){ continue }
    $copy[$p.Name]=$p.Value
  }
  ($copy.GetEnumerator()|Sort-Object Name|ForEach-Object{
    $v = $_.Value
    if($v -is [System.Collections.IEnumerable] -and -not ($v -is [string])){
      $v = ($v|ConvertTo-Json -Depth 8 -Compress)
    }
    "{0}={1};" -f $_.Name, $v
  }) -join ""
}

function HashText($text){
  $bytes=[System.Text.Encoding]::UTF8.GetBytes($text)
  $sha=[System.Security.Cryptography.SHA256]::Create()
  ($sha.ComputeHash($bytes)|ForEach-Object{$_.ToString("x2")}) -join ""
}

function Resolve-Python([string]$Preferred){
  foreach($c in @($Preferred,"py","python","python3")){
    if([string]::IsNullOrWhiteSpace($c)){continue}
    try{ $v=& $c --version 2>$null; if($LASTEXITCODE -eq 0 -and $v){ return $c } }catch{}
  }
  return $null
}

# ------------ session start -------------
$root=(Get-Location).Path
$env:COLLEGE_AD_VERSION="18"
Ok "COLLEGE_AD_VERSION=18"

# 1) Audit (read-only)
if (Test-Path .\scripts\Audit-ProjectStructure.ps1) {
  Say "Audit: scanning project structure (dry-run)…"
  .\scripts\Audit-ProjectStructure.ps1 | Out-Host
}

# 2) Optional safe fixes and inbox de-duplication
if ($Fix) {
  if (Test-Path .\scripts\Audit-ProjectStructure.ps1) {
    Say "Applying safe fixes…"
    .\scripts\Audit-ProjectStructure.ps1 -CanonicalStart scripts -CanonicalPolicy underscore -Apply | Out-Host
  }
  if (Test-Path .\scripts\Dedup-Inbox.ps1) {
    Say "De-duplicating INBOX…"
    .\scripts\Dedup-Inbox.ps1 -Apply | Out-Host
  }
}

# 3) Quick Actions (optionally set resume = #1)
if ($QuickActions -and (Test-Path .\scripts\Inbox-QuickActions.ps1)) {
  Say "Quick Actions (preview)…"
  if ($QASetResumeOnTop) {
    .\scripts\Inbox-QuickActions.ps1 -SetResumeOnTop | Out-Host
  } else {
    .\scripts\Inbox-QuickActions.ps1 | Out-Host
  }
}

# 4) Resume hint (load SESSION_STATE and point to matching inbox item if present)
$statePath = Join-Path $root "scripts\SESSION_STATE_v18.json"
$inboxDir  = Join-Path $root "logs\INBOX"

function Save-ResumeFromFile($filePath){
  if (-not (Test-Path -LiteralPath $filePath)) { return $false }
  $j = Get-Json $filePath
  if(-not $j){ return $false }
  $sig = HashText (Normalize-ForHash $j)
  $channel = ""
  if($j.channel){ $channel = ""+$j.channel } elseif($j.type){ $channel = ""+$j.type }
  $state = [pscustomobject]@{
    Path=$filePath; Signature=$sig; Subject=$j.subject; Channel=$channel; Week=$j.week; SavedAt=(Get-Date)
  }
  $state | ConvertTo-Json -Depth 6 | Out-File -FilePath $statePath -Encoding UTF8 -Force
  return $true
}

if ($SetResumeFromNewest -and (Test-Path -LiteralPath $inboxDir)) {
  $newest = Get-ChildItem $inboxDir -Filter *.json -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($newest) {
    if (Save-ResumeFromFile $newest.FullName) { Ok ("Resume anchor set to newest: {0}" -f $newest.Name) }
  }
}

if ((Test-Path -LiteralPath $statePath) -and (Test-Path -LiteralPath $inboxDir)) {
  $resumeInfo = Get-Json $statePath
  if ($resumeInfo) {
    $match = $null
    foreach($f in (Get-ChildItem $inboxDir -Filter *.json -File)){
      $j = Get-Json $f.FullName; if(-not $j){ continue }
      $sig = HashText (Normalize-ForHash $j)
      if($sig -eq $resumeInfo.Signature){ $match = $f; break }
    }
    if ($match) {
      Say ("Resume hint: {0} (Week {1}) — file: {2}" -f $resumeInfo.Subject, $resumeInfo.Week, $match.Name) "Yellow"
    }
  }
}

# 5) Optional Phone/Meeting scene on top priority item
if (($Phone -or $Meeting) -and (Test-Path .\scripts\Run-Scene.ps1)) {
  if ($Phone)   { .\scripts\Run-Scene.ps1 -Mode Phone   -PythonCmd $PythonCmd | Out-Host }
  if ($Meeting) { .\scripts\Run-Scene.ps1 -Mode Meeting -PythonCmd $PythonCmd | Out-Host }
}

# 6) Launch Inbox CLI
$inboxCli=Join-Path $root "engine\src\ui_inbox_cli.py"
if (-not (Test-Path -LiteralPath $inboxCli)) { Write-Warning "Missing: engine\src\ui_inbox_cli.py"; exit 1 }
$py=Resolve-Python $PythonCmd
if(-not $py){ Write-Warning "Python not found"; exit 1 }
Say ("Using Python: {0}" -f $py)
Say "Launching Inbox CLI…"
& $py $inboxCli

