[CmdletBinding()]
param(
  [ValidateSet("Phone","Meeting")]
  [string]$Mode = "Phone",
  [string]$ProjectRoot = (Get-Location).Path,
  [string]$PythonCmd = ""
)

function Say($t,$c="Cyan"){ Write-Host $t -ForegroundColor $c }
function Ok($t){ Write-Host $t -ForegroundColor Green }
function Warn($t){ Write-Warning $t }
function J($p){ try { Get-Content $p -Raw | ConvertFrom-Json -ErrorAction Stop } catch { $null } }
function Coalesce([object[]]$vals){ foreach($v in $vals){ if($null -ne $v -and $v -ne ""){ return $v } } return "" }
function BoolToInt($b){ if($b){1}else{0} }

function Score($j){
  $urg = 3; try { if($j.urgency -as [int]){ $urg=[int]$j.urgency } } catch {}
  if($urg -lt 1 -or $urg -gt 5){ $urg=3 }
  $toneTxt= ("" + $j.tone).ToLower()
  $toneBump = BoolToInt($toneTxt -match "angry|upset|negative|frustrat|mad")
  $isContact = (("" + $j.subject).ToLower() -match "contact_required") -or (("" + $j.type).ToLower() -eq "contact_required")
  $contactBump = if($isContact){2}else{0}
  $w=0; try{ $wStr=""+$j.week; if($wStr -match "\d+"){$w=[int]([regex]::Match($wStr,"\d+").Value)} }catch{}
  $recency = [Math]::Max(0,$w)/10.0
  return $urg + $toneBump + $contactBump + $recency
}

function Resolve-Python([string]$Preferred){
  foreach($c in @($Preferred,"py","python","python3")){
    if([string]::IsNullOrWhiteSpace($c)){continue}
    try{$v=& $c --version 2>$null; if($LASTEXITCODE -eq 0 -and $v){return $c}}catch{}
  }
  return $null
}

# ---------- pick target ----------
$inbox = Join-Path $ProjectRoot "logs\INBOX"
if(-not(Test-Path -LiteralPath $inbox)){ Warn "logs\INBOX not found (Rule #1: not creating it)."; exit 1 }

$files = Get-ChildItem $inbox -Filter *.json -File -ErrorAction SilentlyContinue
if(-not $files){ Warn "No inbox files present."; exit 1 }

$rows = foreach($f in $files){
  $j = J $f.FullName
  if(-not $j){ continue }
  $typeVal = Coalesce @($j.type, $j.channel, "update")
  $whoVal  = Coalesce @($j.from, $j.from_name, $j.sender, $j.participants, "unknown")
  $subject = Coalesce @($j.subject, "(no subject)")
  $s = Score $j
  [pscustomobject]@{
    Score=$s; Week=(""+$j.week); Type=(""+$typeVal); Who=(""+$whoVal); Subject=(""+$subject)
    Path=$f.FullName; Name=$f.Name; When=(Get-Item $f.FullName).LastWriteTime
  }
}

if(-not $rows){ Warn "No actionable items."; exit 1 }
$top = $rows | Sort-Object @{Expression="Score";Descending=$true}, @{Expression="When";Descending=$true} | Select-Object -First 1

Say ("Scene target: [{0}] {1} — {2} (Week {3})" -f $top.Type, $top.Subject, $top.Who, $top.Week) "Yellow"

# ---------- try Python scene first ----------
$py=Resolve-Python $PythonCmd
$phonePy   = Join-Path $ProjectRoot "engine\src\ui_phone_cli.py"
$meetingPy = Join-Path $ProjectRoot "engine\src\ui_meeting_cli.py"

if ($py -and $Mode -eq "Phone" -and (Test-Path -LiteralPath $phonePy)) {
  Say ("Launching Python phone scene with: {0}" -f $top.Name)
  & $py $phonePy $top.Path
  exit $LASTEXITCODE
}
if ($py -and $Mode -eq "Meeting" -and (Test-Path -LiteralPath $meetingPy)) {
  Say ("Launching Python meeting scene with: {0}" -f $top.Name)
  & $py $meetingPy $top.Path
  exit $LASTEXITCODE
}

# ---------- lightweight PowerShell scene (fallback; no folder creation) ----------
$style = if($Mode -eq "Phone"){"Call"}else{"Meeting"}
Say ("Running {0} scene (PowerShell fallback)…" -f $style)

# Load JSON for details
$J = J $top.Path
$urg = Coalesce @($J.urgency, 3)
$tone= ("" + $J.tone)
$body= Coalesce @($J.body, "")
Write-Host ""
Write-Host ("{0} with: {1}" -f $style, $top.Who) -ForegroundColor Cyan
Write-Host ("Subject: {0}" -f $top.Subject)
Write-Host ("Week: {0} | Type: {1} | Urgency: {2} | Tone: {3}" -f $top.Week, $top.Type, $urg, $tone)
if($body){ Write-Host ("Context: {0}" -f $body.Substring(0,[Math]::Min(160,$body.Length))) }

Write-Host ""
Write-Host "Choose your approach:"
Write-Host "  1) Supportive & relationship-first"
Write-Host "  2) Direct & accountability-focused"
Write-Host "  3) Defer — schedule follow-up"
Write-Host "  4) Escalate to AD/President's Office"
Write-Host "  q) Quit"
$choice = Read-Host "> "

$decision = switch ($choice) {
  "1" { "Supportive" }
  "2" { "Direct" }
  "3" { "Defer" }
  "4" { "Escalate" }
  default { "Quit" }
}

if ($decision -eq "Quit") { Say "Scene cancelled."; exit 0 }

# Optional transcript if status\ exists
$statusDir = Join-Path $ProjectRoot "status"
if (Test-Path -LiteralPath $statusDir) {
  $stamp = (Get-Date -Format "yyyyMMdd_HHmmss")
  $file = Join-Path $statusDir ("SCENE_{0}_{1}.md" -f $Mode.ToUpper(), $stamp)
  $md = @()
  $md += "# Scene — $Mode"
  $md += "- When: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")"
  $md += "- Target: $($top.Who)"
  $md += "- Subject: $($top.Subject)"
  $md += "- Week: $($top.Week)"
  $md += "- Decision: $decision"
  $md += ""
  if ($decision -eq "Supportive") {
    $md += "Outcome: You reassured the stakeholder, acknowledged concerns, and asked for one actionable next step this week."
  } elseif ($decision -eq "Direct") {
    $md += "Outcome: You held a firm line on expectations and timelines; stakeholder agreed to a checkpoint next week."
  } elseif ($decision -eq "Defer") {
    $md += "Outcome: You scheduled a follow-up; goodwill neutral, urgency slightly increased."
  } elseif ($decision -eq "Escalate") {
    $md += "Outcome: You escalated the issue; prestige risk lowered if resolved, but relationship warmth dipped."
  }
  $md | Out-File -FilePath $file -Encoding UTF8 -Force
  Ok ("Transcript saved: status\{0}" -f (Split-Path -Leaf $file))
} else {
  Say "status\ not present; transcript skipped (Rule #1)." "DarkCyan"
}

Ok "Scene complete."
