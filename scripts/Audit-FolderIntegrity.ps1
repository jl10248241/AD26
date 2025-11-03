param(
    [switch]$Apply,
    [switch]$ShowAll
)

Set-StrictMode -Version Latest

# Resolve project root:
# - When running as a script: use $PSScriptRoot\..
# - When sourced/interactive: fall back to current location.
$ProjectRoot = if ($PSScriptRoot) {
    Split-Path -Parent $PSScriptRoot
} else {
    (Get-Location).Path
}

# Baseline top-level + nested paths
$Baseline = @(
    "scripts",
    "engine",
    "engine\src",
    "data",
    "logs",
    "docs",
    "archive"
    # add "notes","tools" here if you want them treated as official
)

# Top-level directory names at the project root
$Top = Get-ChildItem -Directory -Path $ProjectRoot | ForEach-Object { $_.Name }
if (-not $ShowAll) { $Top = $Top | Where-Object { $_ -notlike ".*" } }

# Missing: check each baseline path under ProjectRoot (supports nested)
$Missing = @()
foreach ($b in $Baseline) {
    $abs = Join-Path $ProjectRoot $b
    if (-not (Test-Path -Path $abs -PathType Container)) { $Missing += $b }
}

# Extra: compare top-level names only
$BaselineTop = $Baseline | ForEach-Object { ($_ -split '[\\/]')[0] } | Select-Object -Unique
$Extra = $Top | Where-Object { $BaselineTop -notcontains $_ }

Write-Host "=== Folder Integrity Audit ==="
Write-Host "Root: $ProjectRoot`n"

if ($Missing.Count -gt 0) {
    Write-Host "🟥 Missing baseline folders:" -ForegroundColor Red
    $Missing | ForEach-Object { Write-Host "  - $_" }
} else {
    Write-Host "✅ All baseline folders present."
}

if ($Extra.Count -gt 0) {
    Write-Host "`n🟨 Extra (non-baseline) folders detected:" -ForegroundColor Yellow
    $Extra | ForEach-Object { Write-Host "  - $_" }
} else {
    Write-Host "`n✅ No unexpected top-level folders detected."
}

if ($Apply) {
    $LogPath = Join-Path $ProjectRoot "docs\FOLDER_CHANGES_LOG.md"
    if (-not (Test-Path $LogPath)) { "# Folder Changes Log" | Out-File $LogPath -Encoding utf8 }
    Add-Content $LogPath "`n### Audit run $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

    foreach ($m in $Missing) {
        $abs = Join-Path $ProjectRoot $m
        New-Item -ItemType Directory -Force -Path $abs | Out-Null
        Add-Content $LogPath "- Created folder: $m"
        Write-Host "📁 Created: $m"
    }
    Write-Host "`n💾 Changes applied and logged to $LogPath"
}
