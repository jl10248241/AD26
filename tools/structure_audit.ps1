param(
  # Optional: override repo root (defaults to parent of this script's folder)
  [string]$Root
)

# ---------- Resolve repo root ----------
if (-not $PSBoundParameters.ContainsKey('Root') -or [string]::IsNullOrWhiteSpace($Root)) {
  # If script is in ...\tools, go one level up
  $Root = Resolve-Path (Join-Path $PSScriptRoot "..")
} else {
  $Root = Resolve-Path $Root
}

# ---------- Helpers ----------
function New-Dir($p){ New-Item -ItemType Directory -Force -Path $p | Out-Null }
function Write-Utf8NoBom($Path, $Content){
  $enc = [System.Text.UTF8Encoding]::new($false)
  [System.IO.File]::WriteAllText((Resolve-Path $Path), $Content, $enc)
}
function Test-Utf8Bom([byte[]]$bytes){
  return ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
}
function Test-JsonFile($path){
  try{
    $raw = Get-Content $path -Raw -Encoding Byte
    $hasBom = Test-Utf8Bom $raw
    $offset = if($hasBom){3}else{0}
    $text  = [System.Text.Encoding]::UTF8.GetString($raw, $offset, $raw.Length - $offset)
    $null = $text | ConvertFrom-Json -ErrorAction Stop
    return @{ ok=$true; bom=$hasBom; err=$null }
  }catch{
    return @{ ok=$false; bom=$false; err=$_.Exception.Message }
  }
}

# ---------- Prep report ----------
$stamp  = Get-Date -Format "yyyy-MM-dd_HHmmss"
$docs   = Join-Path $Root "docs"
New-Dir $docs
$report = Join-Path $docs ("STRUCTURE_AUDIT_{0}.md" -f $stamp)

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# Structure Audit — $stamp")
$lines.Add("")
$lines.Add("**Repo root:** `$( $Root )`")
$lines.Add("")

# ---------- Directories ----------
$requiredDirs = @(
  "engine","engine\config","engine\src","engine\state","docs","logs","logs\INBOX","logs\MEDIA"
)
$missingDirs = @()
foreach($d in $requiredDirs){
  if (-not (Test-Path (Join-Path $Root $d))) { $missingDirs += $d }
}
$lines.Add("## Directories")
if ($missingDirs.Count -eq 0) {
  $lines.Add("*All required directories present.*")
} else {
  $lines.Add("Missing dirs: `" + ($missingDirs -join "`, `") + "`")
}

# ---------- Key Python files ----------
$requiredPy = @(
  "engine\__init__.py",
  "engine\src\__init__.py",
  "engine\src\media_desk.py",
  "engine\src\ui_media_cli.py",
  "engine\src\relationship_engine.py",
  "engine\src\ui_relationships_cli.py",
  "engine\src\schedule_engine.py",
  "engine\src\ui_schedule_cli.py",
  "engine\src\assistant_ad_engine.py",
  "engine\src\ui_aad_cli.py",
  "engine\src\comm_auto_engine.py",
  "engine\src\ui_comm_auto_cli.py",
  "engine\src\media_map.py",
  "engine\src\ui_media_map_cli.py",
  "engine\src\recruiting_influence.py",
  "engine\src\ui_recruiting_influence_cli.py"
)
$missingPy = $requiredPy | Where-Object { -not (Test-Path (Join-Path $Root $_)) }
$lines.Add("")
$lines.Add("## Key Python files")
if ($missingPy.Count -eq 0) {
  $lines.Add("*All key Python files present.*")
} else {
  $lines.Add("Missing files: `" + ($missingPy -join "`, `") + "`")
}

# ---------- Config sanity (JSON + BOM) ----------
$lines.Add("")
$lines.Add("## Config JSON validity & BOM")
$configDir = Join-Path $Root "engine\config"
$configs = @(Get-ChildItem $configDir -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -ieq ".json" })
if ($configs.Count -eq 0){
  $lines.Add("_No config JSON files found._")
} else {
  $bad = @()
  $withBom = @()
  foreach($c in $configs){
    $res = Test-JsonFile $c.FullName
    if (-not $res.ok){ $bad += ("`"{0}`" — {1}" -f $c.Name, $res.err) }
    if ($res.bom){ $withBom += $c.FullName }
  }
  if ($bad.Count -eq 0){ $lines.Add("*All config JSON parse OK.*") } else {
    $lines.Add("Invalid JSON:"); $bad | ForEach-Object { $lines.Add("- $_") }
  }
  if ($withBom.Count -gt 0){
    $lines.Add(""); $lines.Add("Files with **UTF-8 BOM** (normalized):")
    foreach($p in $withBom){
      $raw = Get-Content $p -Raw
      Write-Utf8NoBom $p $raw
      $lines.Add("- normalized: `$(Split-Path $p -Leaf)`")
    }
  } else { $lines.Add("*No BOM detected in configs.*") }
}

# ---------- .config twins ----------
$lines.Add("")
$lines.Add("## .config twins (should be removed)")
$twins = @(Get-ChildItem $configDir -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -ieq ".config" })
if ($twins.Count -gt 0){
  $lines.Add("Found `.config` files. **Copy** content into matching `.json`, then delete:")
  $twins | ForEach-Object { $lines.Add("- `engine\config\$($_.Name)`") }
} else { $lines.Add("*No stray .config files.*") }

# ---------- State JSON sanity ----------
$lines.Add("")
$lines.Add("## State JSON validity")
$stateDir = Join-Path $Root "engine\state"
$stateJson = @(Get-ChildItem $stateDir -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -ieq ".json" })
if ($stateJson.Count -gt 0){
  $badState = @()
  foreach($s in $stateJson){
    $r = Test-JsonFile $s.FullName
    if (-not $r.ok){ $badState += ("`"{0}`" — {1}" -f $s.Name, $r.err) }
  }
  if ($badState.Count -eq 0){ $lines.Add("*All state JSON parse OK.*") } else {
    $lines.Add("Invalid state JSON:"); $badState | ForEach-Object { $lines.Add("- $_") }
  }
}else{
  $lines.Add("_No state JSON files found (OK if first run)._")
}

# ---------- Python import sanity ----------
$lines.Add("")
$lines.Add("## Python import sanity (engine packages)")
$cmds = @(
  'import importlib; importlib.import_module("engine")',
  'import importlib; importlib.import_module("engine.src")',
  'import importlib; importlib.import_module("engine.src.media_desk")',
  'import importlib; importlib.import_module("engine.src.schedule_engine")',
  'import importlib; importlib.import_module("engine.src.assistant_ad_engine")',
  'import importlib; importlib.import_module("engine.src.recruiting_influence")'
)
$importIssues = @()
foreach($py in $cmds){
  $proc = Start-Process -FilePath "python" -ArgumentList @("-c",$py) -NoNewWindow -PassThru -Wait -ErrorAction SilentlyContinue
  if (-not $proc -or $proc.ExitCode -ne 0){ $importIssues += "- Failed: `$py`" }
}
if ($importIssues.Count -eq 0){ $lines.Add("*Core module imports OK.*") } else {
  $lines.Add("Import problems:"); $importIssues | ForEach-Object { $lines.Add($_) }
}

# ---------- Docs presence ----------
$lines.Add("")
$lines.Add("## Docs presence")
$docMust = @("MEDIA_FEED.md","SCHEDULE.md","MEDIA_REACH.md","MEDIA_REACH.json","RECRUITING_READOUT.md","PROJECT_STATUS_v17.9.md","CHANGELOG.md","TODO_v17.9.md")
$docMissing = @()
foreach($d in $docMust){ if (-not (Test-Path (Join-Path $Root "docs\$d"))) { $docMissing += $d } }
if ($docMissing.Count -eq 0){
  $lines.Add("*All expected docs present.*")
} else {
  $lines.Add("Missing docs: `" + ($docMissing -join "`, `") + "`")
}

# ---------- Summary ----------
$lines.Add("")
$lines.Add("## Summary / Next steps")
if ($missingDirs -or $missingPy -or $importIssues -or $docMissing){
  $lines.Add("- Address the items above, then run `docs\\SMOKE_v17.9.ps1` again.")
}else{
  $lines.Add("- Structure healthy. ✅")
}

# Write report
Write-Utf8NoBom $report ($lines -join "`r`n")
Write-Host ("Wrote report → {0}" -f $report) -ForegroundColor Green
