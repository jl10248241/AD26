param([string]$Root = (Get-Location))

$ErrorActionPreference = "Stop"
$fail = @()
function Fail($m){ $script:fail += $m }

Write-Host "=== College AD Workspace Validator (v2) ==="

# 0) Paths
$cfgRoot = Join-Path $Root "engine\config"
$docsRoot = Join-Path $Root "docs"
$logsRoot = Join-Path $Root "logs"

# 1) Forbidden dirs (should not exist)
$forbidden = @("configs","engine\docs","engine\logs")
foreach($d in $forbidden){
  if(Test-Path (Join-Path $Root $d)){ Fail "Forbidden path exists: $d" }
}

# 2) Required dirs/files
$reqDirs = @("engine\config","engine\src","logs\INBOX","docs")
foreach($d in $reqDirs){
  if(-not (Test-Path (Join-Path $Root $d))){ Fail "Missing required directory: $d" }
}
if(-not (Test-Path (Join-Path $Root ".env"))){ Fail "Missing .env file" }

# 3) .env keys must be canonical
$envTxt = (Get-Content (Join-Path $Root ".env") -Raw)
function HasKey($k,$v){ return ($envTxt -match ("(?m)^\s*{0}\s*=\s*{1}\s*$" -f [regex]::Escape($k),[regex]::Escape($v))) }
if(-not (HasKey "CONFIG_DIR" "engine/config")){ Fail "CONFIG_DIR must be engine/config" }
if(-not (HasKey "LOG_DIR" "logs")){ Fail "LOG_DIR must be logs" }
if(-not (HasKey "INBOX_DIR" "logs/INBOX")){ Fail "INBOX_DIR must be logs/INBOX" }

# 4) Required config presence (warn-only for optional new ones)
$requiredCfg = @(
  "reg_catalog.json","reg_weights.json","trait_components.json","trait_gravity.json","trait_engine.cfg",
  "ad_archetypes.json","archetype_anchors.json","core_principles.json","context_gravity.json",
  "interaction_catalog.json","personality_profiles.json","player_quiz_map.json"
)
$optionalCfg = @("bridge_filters.json","donor_decay.json","pledge_rules.json")  # v17.7+

foreach($f in $requiredCfg){
  if(-not (Test-Path (Join-Path $cfgRoot $f))){ Fail "Missing config: engine/config/$f" }
}
foreach($f in $optionalCfg){
  if(-not (Test-Path (Join-Path $cfgRoot $f))){
    Write-Host "WARN: optional config not found (ok for pre-17.7): engine/config/$f" -ForegroundColor Yellow
  }
}

# 5) Duplicate name check (ONLY configs & docs; JSON/MD/CFG)
$scan = @($cfgRoot, $docsRoot)
$files = foreach($rootPath in $scan){
  if(Test-Path $rootPath){
    Get-ChildItem -Recurse -File $rootPath | Where-Object {
      $_.Extension -in ".json",".md",".cfg" -and
      $_.FullName -notmatch "\\Archive\\" -and
      $_.FullName -notmatch "\\logs\\" -and
      $_.FullName -notmatch "\\engine\\bridge_in\\" -and
      $_.FullName -notmatch "\\engine\\bridge_out\\" -and
      $_.FullName -notmatch "\\engine\\sandbox\\" -and
      $_.FullName -notmatch "\\engine\\data\\" -and
      $_.FullName -notmatch "\\tools\\"
    }
  }
}
$dupes = $files | Group-Object BaseName | Where-Object { $_.Count -gt 1 }
foreach($g in $dupes){
  $paths = $g.Group.FullName
  Fail ("Duplicate base name (config/docs) found: {0}`n - {1}" -f $g.Name, ($paths -join "`n - "))
}

# 6) Forbidden templates in docs
$templates = Get-ChildItem $docsRoot -Filter "*_TEMPLATE.md" -File -ErrorAction SilentlyContinue
if($templates){ Fail ("Docs templates present (remove after shipping): {0}" -f ($templates.Name -join ", ")) }

# 7) Pass/Fail
if ($fail.Count) {
  Write-Host ""
  Write-Host "VALIDATION FAILED" -ForegroundColor Red
  $fail | ForEach-Object { Write-Host " - $_" -ForegroundColor Red }
  exit 1
} else {
  Write-Host ""
  Write-Host "VALIDATION PASSED - structure is canonical." -ForegroundColor Green
  exit 0
}