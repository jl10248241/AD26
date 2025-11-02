[CmdletBinding()]
param(
  [string]$ProjectRoot = (Get-Location).Path,
  [int]$MaxItems = 12,
  [switch]$SetResumeOnTop,
  [switch]$WriteCsv  # writes to status\QUICK_ACTIONS_v18.csv if status\ exists
)

function say($t,$c="Cyan"){ Write-Host $t -ForegroundColor $c }
function warn($t){ Write-Warning $t }
function ok($t){ Write-Host $t -ForegroundColor Green }

function J($p){ try { Get-Content $p -Raw | ConvertFrom-Json -ErrorAction Stop } catch { $null } }

function BoolToInt($b){ if($b){1}else{0} }
function Coalesce([object[]]$vals){
  foreach($v in $vals){ if($null -ne $v -and $v -ne ""){ return $v } }
  return ""
}

function Score($j){
  $urg = 3
  try { if($j.urgency -as [int]){ $urg = [int]$j.urgency } } catch {}
  if($urg -lt 1 -or $urg -gt 5){ $urg = 3 }

  $toneTxt = ("" + $j.tone).ToLower()
  $toneBump = BoolToInt( $toneTxt -match "angry|upset|negative|frustrat|mad" )

  $isContact = (("" + $j.subject).ToLower() -match "contact_required") -or (("" + $j.type).ToLower() -eq "contact_required")
  $contactBump = if($isContact){2}else{0}

  $w = 0
  try {
    $wStr = "" + $j.week
    if($wStr -match "\d+"){ $w = [int]([regex]::Match($wStr,"\d+").Value) }
  } catch {}
  $recency = [Math]::Max(0,$w) / 10.0

  return $urg + $toneBump + $contactBump + $recency
}

function Normalize($j){
  $copy=@{}
  foreach($p in $j.PSObject.Properties){
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

function ParseWhen($j,$path){
  try { if($j.timestamp){ return [datetime]::Parse($j.timestamp) } } catch {}
  return (Get-Item -LiteralPath $path).LastWriteTime
}

# ----- main -----
Set-Location $ProjectRoot
$inbox = Join-Path $ProjectRoot "logs\INBOX"
if(-not(Test-Path -LiteralPath $inbox)){ throw "logs\INBOX not found (Rule #1: not creating it)." }

$files = Get-ChildItem $inbox -Filter *.json -File -ErrorAction SilentlyContinue
if(-not $files){ say "No inbox files found."; exit 0 }

$rows = foreach($f in $files){
  $j = J $f.FullName
  if(-not $j){ continue }
  $typeVal = Coalesce @($j.type, $j.channel, "update")
  $whoVal  = Coalesce @($j.from, $j.participants, "unknown")
  $subject = Coalesce @($j.subject, "(no subject)")
  $weekStr = "" + $j.week
  $s = Score $j

  [pscustomobject]@{
    Score   = [math]::Round($s,2)
    Week    = $weekStr
    Type    = "" + $typeVal
    Subject = "" + $subject
    Who     = "" + $whoVal
    File    = $f.Name
    Full    = $f.FullName
    When    = ParseWhen $j $f.FullName
    Sig     = HashText (Normalize $j)
  }
}

# Guard against empty rows
if(-not $rows -or $rows.Count -eq 0){
  say "No actionable items."; exit 0
}

$ranked = $rows | Sort-Object @{Expression="Score";Descending=$true}, @{Expression="When";Descending=$true}
$topList = $ranked | Select-Object -First $MaxItems

if(-not $topList -or $topList.Count -eq 0){ say "No actionable items."; exit 0 }

say "== Quick Actions (Top $MaxItems) ==" "Cyan"
$idx=1
$topList | ForEach-Object {
  $wk = if([string]::IsNullOrWhiteSpace($_.Week)){"?"}else{$_.Week}
  $line = "{0,2}. [{1}] {2} — {3} (Week {4})" -f $idx, $_.Type, $_.Subject, $_.Who, $wk
  Write-Host $line
  $idx++
}

if($WriteCsv){
  $statusDir = Join-Path $ProjectRoot "status"
  if(Test-Path -LiteralPath $statusDir){
    $csv = Join-Path $statusDir "QUICK_ACTIONS_v18.csv"
    $topList | Select-Object Score,Week,Type,Subject,Who,File,When | Export-Csv -NoTypeInformation -Path $csv -Encoding UTF8
    ok "Wrote status\QUICK_ACTIONS_v18.csv"
  } else {
    say "status\ not present; skipping CSV (Rule #1)."
  }
}

if($SetResumeOnTop){
  $top1 = $topList | Select-Object -First 1
  if($null -ne $top1){
    $statePath = Join-Path $ProjectRoot "scripts\SESSION_STATE_v18.json"
    $state = [pscustomobject]@{
      Path = $top1.Full
      Signature = $top1.Sig
      Subject = $top1.Subject
      Channel = $top1.Type
      Week = $top1.Week
      SavedAt = (Get-Date)
    }
    $state | ConvertTo-Json -Depth 6 | Out-File -FilePath $statePath -Encoding UTF8 -Force
    ok ("Resume anchor set to: {0} (Week {1})" -f $top1.Subject, $top1.Week)
  }
}
