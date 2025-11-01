param()
$ErrorActionPreference = "Stop"

# Scan roots; exclude snapshot dirs; ignore editor temp/backup patterns; skip anything under \archive\
$roots = @(
  @{ Path = ".\docs";          ExcludeDirs = @("_golden") },
  @{ Path = ".\engine\config"; ExcludeDirs = @() }
)

$ignoreNameRegex = '(\.bak($|[^/\\]))|(~$)|(#[^/\\]*$)|(\.tmp$)|(\.swp$)|(\.swx$)'
$files = @()

foreach ($r in $roots) {
  if (-not (Test-Path $r.Path)) { continue }

  Get-ChildItem $r.Path -Recurse -File | Where-Object {
    # exclude archive trees completely
    $_.FullName -notmatch '\\archive\\' -and
    # exclude specific leaf directories (_golden snapshots)
    ($r.ExcludeDirs -notcontains (Split-Path $_.DirectoryName -Leaf)) -and
    # ignore temp/backup filenames
    ($_.Name -notmatch $ignoreNameRegex)
  } | ForEach-Object { $files += $_ }
}

# Group by case-insensitive BaseName
$dups = $files | Group-Object { $_.BaseName.ToLowerInvariant() } | Where-Object { $_.Count -gt 1 }

if ($dups.Count -gt 0) {
  Write-Host "VALIDATION FAILED" -ForegroundColor Red
  foreach ($g in $dups) {
    Write-Host (" - Duplicate base name (config/docs) found: {0}" -f $g.Name) -ForegroundColor Red
    $g.Group | ForEach-Object { Write-Host ("   - {0}" -f $_.FullName) }
  }
  exit 1
}

Write-Host "Duplicate-basename scan OK." -ForegroundColor Green
exit 0
