param()
$ErrorActionPreference = "Stop"

$roots = @(
  @{ Path = ".\docs";          ExcludeDirsLike = @("^_golden") },  # ignore any dir that starts with _golden
  @{ Path = ".\engine\config"; ExcludeDirsLike = @() }
)

# ignore typical backup/temp names
$ignoreNameRegex = '(\.bak($|[^/\\]))|(~$)|(#[^/\\]*$)|(\.tmp$)|(\.swp$)|(\.swx$)'

$files = @()
foreach ($r in $roots) {
  if (Test-Path $r.Path) {
    Get-ChildItem $r.Path -Recurse -File | Where-Object {
      $dirLeaf = Split-Path -Leaf $_.DirectoryName

      # excluded if the *leaf* folder matches any pattern (e.g., _golden*)
      $excluded = $false
      foreach ($pat in $r.ExcludeDirsLike) {
        if ($dirLeaf -match $pat) { $excluded = $true; break }
      }

      (-not $excluded) -and
      ($_.Name -notmatch $ignoreNameRegex) -and
      ($_.FullName -notmatch '\\archive\\')
    } | ForEach-Object { $files += $_ }
  }
}

# Group by BaseName (case-insensitive)
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
