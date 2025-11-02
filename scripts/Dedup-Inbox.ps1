[CmdletBinding()]
param(
  [string]$ProjectRoot = (Get-Location).Path,
  [ValidateSet("newest","oldest")]
  [string]$Keep = "newest",
  [switch]$Apply,
  [switch]$ShowDetail
)

function say([string]$t,[string]$c="Cyan"){ Write-Host $t -ForegroundColor $c }
function warn([string]$t){ Write-Warning $t }

function Get-Json($path){
  try { return (Get-Content $path -Raw | ConvertFrom-Json -ErrorAction Stop) }
  catch { return $null }
}

function Normalize-ForHash($obj){
  $copy=@{}
  foreach($p in $obj.PSObject.Properties){
    if($p.Name -in @("id","timestamp","metadata")){continue}
    $copy[$p.Name]=$p.Value
  }
  $ordered=$copy.GetEnumerator()|Sort-Object Name
  $sb=New-Object System.Text.StringBuilder
  foreach($kv in $ordered){
    [void]$sb.Append($kv.Name).Append("=")
    $val=$kv.Value
    if($val -is [System.Collections.IEnumerable] -and -not ($val -is [string])){
      $val=($val|ConvertTo-Json -Depth 8 -Compress)
    }
    [void]$sb.Append($val).Append(";")
  }
  return $sb.ToString()
}

function ContentHash($text){
  $bytes=[System.Text.Encoding]::UTF8.GetBytes($text)
  $sha=[System.Security.Cryptography.SHA256]::Create()
  $hash=$sha.ComputeHash($bytes)
  ($hash|ForEach-Object{$_.ToString("x2")})-join""
}

function Parse-TimeOrFallback($json,$file){
  try{ if($json.timestamp){return [datetime]::Parse($json.timestamp)} }catch{}
  return (Get-Item -LiteralPath $file).LastWriteTime
}

function Disable-InPlace($path){
  $dir=[System.IO.Path]::GetDirectoryName($path)
  $base=[System.IO.Path]::GetFileName($path)
  $stamp=(Get-Date -Format "yyyyMMdd_HHmmss")
  $new="$base.dupe.$stamp.disabled"
  Rename-Item -LiteralPath $path -NewName $new -ErrorAction Stop
  Join-Path -Path $dir -ChildPath $new
}

Set-Location $ProjectRoot
$inbox=Join-Path $ProjectRoot "logs\INBOX"
if(-not(Test-Path -LiteralPath $inbox)){
  throw "logs\\INBOX not found (Rule #1: not creating it)."
}

say "== INBOX De-dup (dry-run unless -Apply) ==" "Cyan"

$files=Get-ChildItem $inbox -Filter *.json -File -ErrorAction SilentlyContinue
if(-not$files){ say "No INBOX json files found." "Green"; exit 0 }

$groups=@{}
foreach($f in $files){
  $j=Get-Json $f.FullName
  if(-not$j){warn "Invalid JSON: $($f.Name)";continue}
  $sigText=Normalize-ForHash $j
  $sigHash=ContentHash $sigText
  if(-not$groups.ContainsKey($sigHash)){$groups[$sigHash]=@()}
  $groups[$sigHash]+=[pscustomobject]@{
    Path=$f.FullName;Name=$f.Name;When=Parse-TimeOrFallback $j $f.FullName
  }
}

$dupeSets=$groups.GetEnumerator()|Where-Object{$_.Value.Count -gt 1}
if(-not$dupeSets){ say "? No duplicates detected (by content signature)." "Green"; exit 0 }

$dupeCount=0
foreach($set in $dupeSets){
  $items=$set.Value|Sort-Object When
  $keepItem=if($Keep -eq "newest"){$items[-1]}else{$items[0]}
  $dropItems=$items|Where-Object{$_.Path -ne $keepItem.Path}
  $dupeCount+=$dropItems.Count

  say "`nDuplicate group (sig: $($set.Key.Substring(0,12)))" "Yellow"
  say "  Keep: $($keepItem.Name)  [$($keepItem.When)]" "Green"
  foreach($d in $dropItems){ say "  Drop: $($d.Name)   [$($d.When)]" "Cyan" }

  if($Apply){
    foreach($d in $dropItems){
      $ren=Disable-InPlace $d.Path
      if($ShowDetail){ say "   -> disabled: $(Split-Path -Leaf $ren)" "DarkYellow" }
    }
  }
}

if(-not$Apply){
  say "`nDry-run complete. Re-run with -Apply to disable duplicates." "Cyan"
}else{
  say "`nDone. Disabled $dupeCount duplicate file(s)." "Green"
}
