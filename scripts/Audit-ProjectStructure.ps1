[CmdletBinding()]
param(
  [string]$ProjectRoot = (Get-Location).Path,

  [ValidateSet("root","scripts")]
  [string]$CanonicalStart = "scripts",

  [ValidateSet("dot","underscore")]
  [string]$CanonicalPolicy = "underscore",

  [switch]$Apply
)

function Out-Note($t){ Write-Host $t -ForegroundColor Cyan }
function Out-Ok($t){ Write-Host $t -ForegroundColor Green }
function Out-Warn($t){ Write-Warning $t }

function Disable-NonCanonical($path) {
  if (-not (Test-Path -LiteralPath $path)) { return $null }
  $dir  = [System.IO.Path]::GetDirectoryName($path)
  $base = [System.IO.Path]::GetFileName($path)
  $stamp = (Get-Date -Format "yyyyMMdd_HHmmss")
  $newName = "$base.conflict.$stamp.disabled"
  Rename-Item -LiteralPath $path -NewName $newName -ErrorAction Stop
  return (Join-Path -Path $dir -ChildPath $newName)
}

Set-Location $ProjectRoot
Out-Note "== Project Structure Audit (dry-run unless -Apply) =="

# --------------------------
# Gather files
# --------------------------
$all = Get-ChildItem -Recurse -File -ErrorAction SilentlyContinue

# Case-insensitive filename duplicates
$byName = $all | Group-Object { $_.Name.ToLowerInvariant() } | Where-Object { $_.Count -gt 1 }

# Content duplicates (SHA256)
$hashes = @{}
foreach($f in $all){
  try {
    $h = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
    if (-not $hashes.ContainsKey($h)) { $hashes[$h] = @() }
    $hashes[$h] += $f
  } catch {}
}
$byHash = @($hashes.GetEnumerator() | Where-Object { $_.Value.Count -gt 1 })

# --------------------------
# Print summary
# --------------------------
if ($byName.Count) {
  Out-Warn "Duplicate filenames detected (case-insensitive):"
  foreach($g in $byName) {
    Write-Host ("  Name: {0}" -f $g.Name)
    $g.Group | ForEach-Object { Write-Host ("    - {0}" -f $_.FullName) }
  }
} else { Out-Ok "No duplicate filenames." }

if ($byHash.Count) {
  Out-Warn "Identical-content files detected (SHA256 match):"
  foreach($h in $byHash) {
    Write-Host ("  Hash: {0}" -f $h.Key.Substring(0,16))
    $h.Value | ForEach-Object { Write-Host ("    - {0}" -f $_.FullName) }
  }
} else { Out-Ok "No identical-content duplicates." }

# --------------------------
# Known hot spots (safe fix)
# --------------------------
$startRoot    = Join-Path $ProjectRoot "start_v18.ps1"
$startScripts = Join-Path $ProjectRoot "scripts\start_v18.ps1"

if ((Test-Path $startRoot) -and (Test-Path $startScripts)) {
  Out-Warn "Found both start_v18.ps1 files:"
  Write-Host "  - $startRoot"
  Write-Host "  - $startScripts"
  $keep = if ($CanonicalStart -eq "root") { $startRoot } else { $startScripts }
  $lose = if ($CanonicalStart -eq "root") { $startScripts } else { $startRoot }

  $hKeep = (Get-FileHash -LiteralPath $keep -Algorithm SHA256).Hash
  $hLose = (Get-FileHash -LiteralPath $lose -Algorithm SHA256).Hash

  if ($Apply) {
    if ($hKeep -eq $hLose) {
      Remove-Item -LiteralPath $lose -Force
      Out-Ok "Removed duplicate (identical): $lose"
    } else {
      $renamed = Disable-NonCanonical $lose
      Out-Warn "Disabled conflicting file: $renamed"
    }
  } else {
    Out-Note "Dry-run: Would keep '$CanonicalStart' copy and resolve the other."
  }
} else { Out-Ok "No start_v18.ps1 conflict." }

$policyDot        = Join-Path $ProjectRoot "engine\config\comm_auto.policy.json"
$policyUnderscore = Join-Path $ProjectRoot "engine\config\comm_auto_policy.json"
if ((Test-Path $policyDot) -and (Test-Path $policyUnderscore)) {
  Out-Warn "Found both comm_auto policy filenames:"
  Write-Host "  - $policyDot"
  Write-Host "  - $policyUnderscore"
  $keep = if ($CanonicalPolicy -eq "dot") { $policyDot } else { $policyUnderscore }
  $lose = if ($CanonicalPolicy -eq "dot") { $policyUnderscore } else { $policyDot }

  $hKeep = (Get-FileHash -LiteralPath $keep -Algorithm SHA256).Hash
  $hLose = (Get-FileHash -LiteralPath $lose -Algorithm SHA256).Hash

  if ($Apply) {
    if ($hKeep -eq $hLose) {
      Remove-Item -LiteralPath $lose -Force
      Out-Ok "Removed duplicate (identical): $lose"
    } else {
      $renamed = Disable-NonCanonical $lose
      Out-Warn "Disabled conflicting file: $renamed"
    }
  } else {
    Out-Note "Dry-run: Would keep '$CanonicalPolicy' filename and resolve the other."
  }
} else { Out-Ok "No comm_auto policy filename conflict." }

# --------------------------
# Optional CSV if status\ exists
# --------------------------
$statusDir = Join-Path $ProjectRoot "status"
if (Test-Path -LiteralPath $statusDir) {
  $csv = Join-Path $statusDir "STRUCT_AUDIT_v18.csv"
  $rows = @()

  foreach($g in $byName){
    foreach($f in $g.Group){
      $rows += [pscustomobject]@{ Kind="NameDuplicate"; Key=$g.Name; Path=$f.FullName; Size=$f.Length }
    }
  }
  foreach($h in $byHash){
    foreach($f in $h.Value){
      $rows += [pscustomobject]@{ Kind="HashDuplicate"; Key=$h.Key; Path=$f.FullName; Size=$f.Length }
    }
  }

  if ($rows.Count) {
    $rows | Export-Csv -NoTypeInformation -Path $csv -Encoding UTF8
    Out-Ok "Wrote audit CSV: status\STRUCT_AUDIT_v18.csv"
  }
} else {
  Out-Note "status\ not present; skipping CSV (Rule #1)."
}
