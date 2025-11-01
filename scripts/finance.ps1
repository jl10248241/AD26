# scripts/finance.ps1 — quick validator
Set-Location -Path "$PSScriptRoot\.."
python -m engine.src.finance_validator --issues-only --limit 10 --ascii
