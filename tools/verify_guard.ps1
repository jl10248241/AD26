# tools/verify_guard.ps1 — verify guard import, call, and compile with full diagnostics (PowerShell-safe)
$ErrorActionPreference = "Stop"

$rt = ".\engine\src\run_tick.py"
if (-not (Test-Path $rt)) { Write-Error "run_tick.py not found: $rt"; exit 1 }

$txt = Get-Content $rt -Raw

if ($txt -notmatch 'from\s+engine\.src\.selftest_guardrails\s+import\s+guard_before_advance') {
  Write-Host "❌ guard import missing in run_tick.py" -ForegroundColor Red
  exit 1
}
if ($txt -notmatch 'if\s+not\s+guard_before_advance\s*\(\s*week\s*\)\s*:') {
  Write-Host "❌ guard call missing after week assignment in run_tick.py" -ForegroundColor Red
  exit 1
}

$code = @"
import py_compile, traceback, sys
try:
    py_compile.compile(r'engine/src/run_tick.py', doraise=True)
    print('PYCOMPILE_OK')
    sys.exit(0)
except Exception:
    traceback.print_exc()
    sys.exit(1)
"@

$procOut = & python -c $code 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "❌ Python compile failed for run_tick.py:" -ForegroundColor Red
  Write-Host $procOut
  exit 1
}

Write-Host "✅ Guard present and run_tick.py compiles." -ForegroundColor Green
