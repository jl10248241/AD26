# tools/verify_guard.ps1 — ensure run_tick guard import + call exist and file compiles

$ErrorActionPreference = "Stop"
$root  = (Get-Location).Path
$rt    = Join-Path $root 'engine\src\run_tick.py'

if (-not (Test-Path $rt)) { Write-Error "run_tick not found: $rt"; exit 1 }

# Read once
$txt = Get-Content $rt -Raw

# Check import
$hasImport = ($txt -match 'from\s+engine\.src\.selftest_guardrails\s+import\s+guard_before_advance')
if (-not $hasImport) {
  Write-Host "❌ guard import missing in run_tick.py" -ForegroundColor Red
  exit 1
}

# Check invocation (allow whitespace)
$hasCall = ($txt -match 'if\s+not\s+guard_before_advance\s*\(\s*week\s*\)\s*:')
if (-not $hasCall) {
  Write-Host "❌ guard call missing after week assignment in run_tick.py" -ForegroundColor Red
  exit 1
}

# Compile check (no exec)
$cmd = 'import py_compile,sys; py_compile.compile(r"engine/src/run_tick.py", doraise=True)'
$proc = & python -c $cmd 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "❌ Python compile failed for run_tick.py:" -ForegroundColor Red
  Write-Host $proc
  exit 1
}

Write-Host "✅ Guard present and run_tick.py compiles." -ForegroundColor Green
