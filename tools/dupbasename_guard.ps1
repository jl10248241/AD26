param()
$ErrorActionPreference = "Stop"

$roots = @(
  @{ Path = ".\docs";          ExcludeDirs = @("_golden") },
  @{ Path = ".\engine\config"; ExcludeDirs = @() }
)

# ignore file basenames/suffixes that are editor/backups
$ignoreNameRegex = '(\.bak($|[^/\\]))|(~$)|(#[^/\\]*$)|(\.tmp$)|(\.swp$)|(\.swx$)'

$files = @()
foreach ($r in $roots) {
  if (Test-Path $r.Path) {
    Get-ChildItem $r.Path -Recurse -File | ForEach-Object {
      $leaf = Split-Path $_.DirectoryName -Leaf
      if ($r.ExcludeDirs -contains $leaf) { return }
      if ($_.Name -match $ignoreNameRegex) { return }
      $files += $_
    }
  }
}

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
