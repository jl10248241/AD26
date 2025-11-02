# Integrity Report

**Run:** 2025-11-02T09:19:28
**Root:** C:\COLLEGE_AD26\College_AD_Unified_Workspace_Blank_v17.2

## Folders

## Reference scan
- Found references:
  - archive_finance_20251102_091159\finance_references.txt
    - L4: C:\COLLEGE_AD26\College_AD_Unified_Workspace_Blank_v17.2\archive_v19_1_20251101_231348\scripts\v19.Finance.ps1:279: # ===== FINANCE HELPERS: Spend / Earn / Budg …
    - L8: C:\COLLEGE_AD26\College_AD_Unified_Workspace_Blank_v17.2\archive_v19_1_20251101_231348\scripts\v19.Finance.ps1:279: # ===== FINANCE HELPERS: Spend / Earn / Budg …
    - L38: C:\COLLEGE_AD26\College_AD_Unified_Workspace_Blank_v17.2\scripts\v19.Finance.ps1.bak:279: # ===== FINANCE HELPERS: Spend / Earn / Budget-Move (Corrected Impleme …
    - L42: C:\COLLEGE_AD26\College_AD_Unified_Workspace_Blank_v17.2\scripts\v19.Finance.ps1.bak:279: # ===== FINANCE HELPERS: Spend / Earn / Budget-Move (Corrected Impleme …
    - L47: C:\COLLEGE_AD26\College_AD_Unified_Workspace_Blank_v17.2\scripts\v19.Finance.ps1.bak_20251101_215110:277: # ===== v19.Finance.ps1 — Helpers: Spend / Earn / Budg …
    - L61: C:\COLLEGE_AD26\College_AD_Unified_Workspace_Blank_v17.2\scripts\v19.Finance.ps1.bak_20251101_215110:277: # ===== v19.Finance.ps1 — Helpers: Spend / Earn / Budg …
    - L76: C:\COLLEGE_AD26\College_AD_Unified_Workspace_Blank_v17.2\scripts\v19.Finance.ps1.bak_20251101_215541:277: # ===== v19.Finance.ps1 — Helpers: Spend / Earn / Budg …
    - L79: C:\COLLEGE_AD26\College_AD_Unified_Workspace_Blank_v17.2\scripts\v19.Finance.ps1.bak_20251101_215541:277: # ===== v19.Finance.ps1 — Helpers: Spend / Earn / Budg …
  - archive_v19_1_20251101_231348\scripts\v19.Finance.ps1
    - L3:    Budget-Init                → seeds data\budget.json if missing
    - L4:    Budget-Set  -Category -Amount
    - L5:    Budget-Add  -Category -Delta
    - L6:    Budget-Show               → console table of current budget
    - L7:    Fin-Log      -School -DonorYield -Expenses [-PrestigeChange] [-Sentiment] [-Week]
    - L8:    Fin-Snap                     → prints totals/last row from logs\FINANCE_LOG.csv
    - L9:    Fin-Report                  → writes docs\FINANCE_REPORT_v19.md (if docs\ exists)
    - L25: function Budget-Init {
    - L54: function Budget-Set {
    - L61:   $b = _ReadJson $file; if(-not $b){ throw "Run Budget-Init first." }
    - L67:   Budget-Show
    - L70: function Budget-Add {
    - L77:   $b = _ReadJson $file; if(-not $b){ throw "Run Budget-Init first." }
    - L83:   Budget-Show
    - L86: function Budget-Show {
    - L89:   $b = _ReadJson $file; if(-not $b){ throw "Run Budget-Init first." }
    - L100: function Fin-Log {
    - L147: # NOTE: Fin-Snap is redefined later with a crucial bug fix, but included here for completeness
    - L148: function Fin-Snap {
    - L160: function Fin-Report {
    - L165:   if(-not (Test-Path $csv)){ throw "No FINANCE_LOG.csv — run Fin-Log first." }
    - L197: Set-Alias budget.init Budget-Init
    - L198: Set-Alias budget.set  Budget-Set
    - L199: Set-Alias budget.add  Budget-Add
    - L200: Set-Alias budget.show Budget-Show
    - L201: Set-Alias fin.log     Fin-Log
    - L202: Set-Alias fin.snap    Fin-Snap
    - L203: Set-Alias fin.md      Fin-Report
    - L221: function Budget-Init {
    - L245: function Budget-Set {
    - L252:   $b = _ReadJson $file; if(-not $b){ throw "Run Budget-Init first." }
    - L258:   Budget-Show
    - L261: function Budget-Add {
    - L268:   $b = _ReadJson $file; if(-not $b){ throw "Run Budget-Init first." }
    - L274:   Budget-Show
    - L279: # ===== FINANCE HELPERS: Spend / Earn / Budget-Move (Corrected Implementation) =====
    - L284:   if (-not $b) { throw "Run Budget-Init first (data\budget.json missing)." }
    - L304: function Budget-Move {
    - L321:   Budget-Show
    - L345:     Fin-Log -School $School -DonorYield 0 -Expenses $Amount -PrestigeChange $PrestigeChange -Sentiment $Sentiment
    - L347:     Fin-Log -School $School -DonorYield 0 -Expenses $Amount -PrestigeChange $PrestigeChange
    - L361:     Fin-Log -School $School -DonorYield $Amount -Expenses 0 -PrestigeChange $PrestigeChange -Sentiment $Sentiment
    - L363:     Fin-Log -School $School -DonorYield $Amount -Expenses 0 -PrestigeChange $PrestigeChange
    - L368: # Function Fin-Snap is redefined here to include the necessary force array fix (Import-Csv bug)
    - L369: function Fin-Snap {
    - L380: # ===== END HELPERS & FIN-SNAP PATCH =====
    - L385: Set-Alias budget.move Budget-Move -Scope Global -Force
  - scripts\Session-Start_v19.ps1
    - L46:   Budget-Move @PSBoundParameters

## Script syntax
- All .ps1 files parsed cleanly.

## JSON sanity (data\\)
- json ok: anchors.json
- json ok: cfg.json
- json ok: coaches.json
- json ok: context.json
- json ok: donors.json
- json ok: G.json
- json ok: relationships.json
- json ok: reputation.json
- json ok: world.json

## CSV checks (logs\\)
- DONOR_LEDGER.csv: (no expected schema; skipped)
- REPUTATION_LOG.csv: (no expected schema; skipped)

## Session surface
- Conflicts: spend [Alias], earn [Alias]

## Git status
- Branch: v18.0.0/baseline
- Uncommitted changes present.
