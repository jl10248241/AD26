# tools/structure_audit.ps1 — project structure audit (no backticks, safe formatting)
param()
$ErrorActionPreference = 'Stop'

# --- Paths ---
$root      = (Resolve-Path .).Path
$rootDocs  = (Resolve-Path .\docs).Path
$engineSrc = Join-Path $root 'engine\src'
$engineCfg = Join-Path $root 'engine\config'

# --- Collect all "docs" directories ---
$docsDirs = Get-ChildItem -Directory -Recurse | Where-Object { $_.Name -ieq 'docs' }

# --- Duplicate-basename scan across docs + engine/config (ignore _golden + temp files) ---
$ignoreNameRegex = '(\.bak($|[^/\\]))|(~$)|(#[^/\\]*$)|(\.tmp$)|(\.swp$)|(\.swx$)'
$scanRoots = @(
  @{ Path = $rootDocs;  ExcludeDirs = @('_golden') },
  @{ Path = $engineCfg; ExcludeDirs = @()          }
)

$files = @()
foreach ($r in $scanRoots) {
  if (Test-Path $r.Path) {
    $files += Get-ChildItem $r.Path -Recurse -File |
      Where-Object {
        ($r.ExcludeDirs -notcontains (Split-Path $_.DirectoryName -Leaf)) -and
        ($_.Name -notmatch $ignoreNameRegex)
      }
  }
}

$dupGroups = $files |
  Group-Object { $_.BaseName.ToLowerInvariant() } |
  Where-Object { $_.Count -gt 1 }

# --- Hardcoded "docs/" references in code (prefer config_paths.DOCS) ---
$hardRefs = @()
if (Test-Path $engineSrc) {
  $hardRefs = Select-String -Path (Join-Path $engineSrc '*.py') `
               -Pattern '/docs/','.\docs\' -SimpleMatch -List -ErrorAction SilentlyContinue
}

# --- Build markdown report (plain quotes only) ---
$stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$outDir = $rootDocs
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$outFile = Join-Path $outDir ("STRUCTURE_AUDIT_{0}.md" -f $stamp)

$lines = @()
$lines += ("# Structure Audit — {0}" -f $stamp)
$lines += ""
$lines += "## Root"
$lines += ("- Root: {0}" -f $root)
$lines += ("- Active docs: {0}" -f $rootDocs)
$lines += ""

$lines += "## All folders named 'docs'"
if (($docsDirs | Measure-Object).Count -eq 0) {
  $lines += "_None found_"
} else {
  foreach ($d in $docsDirs) {
    $flag = if ($d.FullName -ieq $rootDocs) { "  **(ACTIVE ROOT)**" } else { "" }
    $lines += ("- {0}{1}" -f $d.FullName, $flag)
  }
}
$lines += ""

$lines += "## Duplicate basenames across 'docs' and 'engine/config'"
if (($dupGroups | Measure-Object).Count -eq 0) {
  $lines += "_No duplicates detected_"
} else {
  foreach ($g in $dupGroups) {
    $lines += ("- **{0}**" -f $g.Name)
    foreach ($p in $g.Group) { $lines += ("  - {0}" -f $p.FullName) }
  }
}
$lines += ""

$lines += "## Hardcoded 'docs/' references in code"
if (-not $hardRefs -or (($hardRefs | Measure-Object).Count -eq 0)) {
  $lines += "_No hardcoded docs/ references found (good!)_"
} else {
  foreach ($hit in $hardRefs) {
    $lines += ("- {0}:{1} — {2}" -f $hit.Path, $hit.LineNumber, ($hit.Line.Trim()))
  }
}
$lines += ""

$lines -join "`n" | Set-Content -Encoding UTF8 $outFile
Write-Host ("Audit written -> {0}" -f $outFile) -ForegroundColor Cyan

