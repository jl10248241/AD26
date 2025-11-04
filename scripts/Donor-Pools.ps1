Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------- Path helpers (work in files and in dot-sourcing) ----------
function _Here {
  param([string]$pssr,[string]$pscmd)
  if ($pssr)  { return $pssr }
  if ($pscmd) { return (Split-Path -Parent $pscmd) }
  return (Get-Location).Path
}
function DP-Root      { Split-Path -Parent (_Here $PSScriptRoot $PSCommandPath) }
function DP-WorldPath { Join-Path (DP-Root) 'data\world.json' }
function DP-LogsDir   { $p = Join-Path (DP-Root) 'logs'; if (!(Test-Path $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null }; $p }
function DP-LogPools    { Join-Path (DP-LogsDir) 'DONOR_POOLS.csv' }
function DP-LogReleases { Join-Path (DP-LogsDir) 'DONOR_POOL_RELEASES.csv' }

# ---------- World IO ----------
function DP-LoadWorld {
  if (Get-Command Get-World -ErrorAction SilentlyContinue) { return (Get-World) }
  $wp = DP-WorldPath
  if (!(Test-Path $wp)) { throw "world.json not found: $wp" }
  $raw = Get-Content $wp -Raw
  if (-not $raw) { throw "world.json empty: $wp" }
  return ($raw | ConvertFrom-Json)
}
function DP-SaveWorld([object]$w) {
  if (Get-Command Save-World -ErrorAction SilentlyContinue) { Save-World $w; return }
  $wp = DP-WorldPath
  $w | ConvertTo-Json -Depth 100 | Set-Content $wp -Encoding utf8
}

# --- helpers ---
function Convert-ToHashtable([object]$o){
  if ($null -eq $o) { return @{} }
  if ($o -is [hashtable]) { return $o }
  $ht=@{}; foreach($p in $o.PSObject.Properties){ $ht[$p.Name]=$p.Value }
  return $ht
}

# ---------- Schema guard (VERY defensive) ----------
function Ensure-RestrictedSchema {
  $w = DP-LoadWorld
  if ($w.schools -isnot [pscustomobject]) { throw 'world.schools must be PSCustomObject' }

  foreach ($name in $w.schools.PSObject.Properties.Name) {
    $node = $w.schools.$name
    if (-not $node) { continue }

    if (-not $node.restricted) {
      $node | Add-Member -NotePropertyName restricted -NotePropertyValue ([pscustomobject]@{}) -Force
    } elseif ($node.restricted -isnot [pscustomobject]) {
      $tmp = New-Object PSObject
      foreach ($p in $node.restricted.PSObject.Properties) { $tmp | Add-Member -NotePropertyName $p.Name -NotePropertyValue $p.Value -Force }
      $node.restricted = $tmp
    }

    if (-not $node.restricted.pools) {
      $node.restricted | Add-Member -NotePropertyName 'pools' -NotePropertyValue @() -Force
    }

    # balances => ensure hashtables for sport/project
    if (-not $node.restricted.balances) {
      $node.restricted | Add-Member -NotePropertyName 'balances' -NotePropertyValue ([pscustomobject]@{}) -Force
    }
    foreach($k in 'sport','project'){
      $cur = $node.restricted.balances.$k
      if ($null -eq $cur) {
        $node.restricted.balances | Add-Member -NotePropertyName $k -NotePropertyValue (@{}) -Force
      } elseif ($cur -isnot [hashtable]) {
        $ht=@{}; foreach($p in $cur.PSObject.Properties){ $ht[$p.Name]=$p.Value }
        $node.restricted.balances.$k = $ht
      }
    }
  }

  DP-SaveWorld $w
  return $w
}

# ---------- Pools API ----------
function New-PoolId { ([guid]::NewGuid()).ToString('N') }

function Add-DonorPool {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory)][string]$School,
    [Parameter(Mandatory)][string]$Donor,
    [Parameter(Mandatory)][double]$Amount,
    [Parameter(Mandatory)][hashtable]$Restriction,    # @{ scope='Sport'|'Project'; key='Basketball_M'|...; allowed_uses=@('recruiting') }
    [Parameter(Mandatory)][hashtable]$Condition,      # @{ type='always'|'sentiment_ge'|'week_ge'; value=... }
    [string]$AvailabilityPolicy = 'supplemental_if_before_cutoff',  # or 'always_release' | 'board_release_required'
    [int]$WeekCreated = 0
  )
  $w = DP-LoadWorld
  [void](Ensure-RestrictedSchema)
  $node = $w.schools.$School
  if (-not $node) { throw "School not found: $School" }

  $pool = [pscustomobject]@{
    id           = New-PoolId
    donor        = $Donor
    amount       = [math]::Round($Amount,2)
    remaining    = [math]::Round($Amount,2)
    restriction  = $Restriction
    condition    = $Condition
    policy       = $AvailabilityPolicy
    week_created = $WeekCreated
    status       = 'pending'   # pending|released|awaiting_board|spent
  }

  $node.restricted.pools = @($node.restricted.pools) + $pool
  DP-SaveWorld $w

  $lp = DP-LogPools
  if (!(Test-Path $lp)) { "id,week_created,school,donor,amount,scope,key,policy,status" | Out-File $lp -Encoding utf8 }
  "$($pool.id),$WeekCreated,$School,$Donor,$([math]::Round($Amount,2)),$($Restriction.scope),$($Restriction.key),$AvailabilityPolicy,$($pool.status)" |
    Out-File $lp -Append -Encoding utf8

  return $pool
}

# --- tolerant condition check ---
function DP-ConditionOK([object]$w,[string]$school,[int]$week,[object]$cond){
  $c = Convert-ToHashtable $cond
  if (-not $c.ContainsKey('type')) { return $false }
  $s = $w.schools.$school.signals
  switch ($c['type']) {
    'always'       { return $true }
    'week_ge'      { return ($week -ge [int]$c['value']) }
    'sentiment_ge' { return ($s.sentiment -ge [double]$c['value']) }
    default        { return $false }
  }
}

function DP-Availability([string]$policy,[int]$week){
  switch ($policy) {
    'always_release'         { return @{ release=$true;  deferred=$false } }
    'board_release_required' { return @{ release=$false; deferred=$true; flag='awaiting_board' } }
    'supplemental_if_before_cutoff' {
      $cutoff = 6
      if ($week -le $cutoff) { return @{ release=$true; deferred=$false } }
      return @{ release=$false; deferred=$true }
    }
    default { return @{ release=$false; deferred=$false } }
  }
}

# --- pool realization (robust to PSCustomObject restriction/condition) ---
function Realize-DonorPoolsForWeek {
  [CmdletBinding()]
  param([object]$World,[int]$Week)

  $w = if ($World) { $World } else { DP-LoadWorld }
  if (-not $PSBoundParameters.ContainsKey('Week')) { $Week = if ($w.week) { [int]$w.week } else { 0 } }

  [void](Ensure-RestrictedSchema)

  $relLog = DP-LogReleases
  if (!(Test-Path $relLog)) { "week,id,school,donor,scope,key,amount,action,timestamp" | Out-File $relLog -Encoding utf8 }

  $hits = @()
  foreach ($school in $w.schools.PSObject.Properties.Name) {
    $node = $w.schools.$school
    foreach ($p in @($node.restricted.pools)) {
      if ($p.status -ne 'pending') { continue }

      $cond  = Convert-ToHashtable $p.condition
      $restr = Convert-ToHashtable $p.restriction
      if (-not (DP-ConditionOK $w $school $Week $cond)) { continue }

      $avail = DP-Availability $p.policy $Week
      $ts    = (Get-Date).ToString('s')

      if ($avail.release) {
        $scope=$restr['scope']; $key=$restr['key']; $amt=[double]$p.remaining
        if ($scope -eq 'Sport')   { if (-not $node.restricted.balances.sport.ContainsKey($key))   { $node.restricted.balances.sport[$key]=0.0 };   $node.restricted.balances.sport[$key]   += $amt }
        if ($scope -eq 'Project') { if (-not $node.restricted.balances.project.ContainsKey($key)) { $node.restricted.balances.project[$key]=0.0 }; $node.restricted.balances.project[$key] += $amt }
        "$Week,$($p.id),$school,$($p.donor),$scope,$key,$([math]::Round($amt,2)),released,$ts" | Out-File $relLog -Append -Encoding utf8
        $hits += [pscustomobject]@{ id=$p.id; school=$school; donor=$p.donor; scope=$scope; key=$key; amount=$amt; action='released' }
        $p.status='released'; $p.remaining=0
      } elseif ($avail.deferred) {
        "$Week,$($p.id),$school,$($p.donor),$($restr['scope']),$($restr['key']),0,deferred,$ts" | Out-File $relLog -Append -Encoding utf8
        $p.status = if ($p.policy -eq 'board_release_required') { 'awaiting_board' } else { 'pending' }
      }
    }
  }

  DP-SaveWorld $w
  return ,$hits
}

# --- restricted-first spend ---
function Spend-Tagged {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory)][string]$School,
    [Parameter(Mandatory)][double]$Amount,
    [string]$UseTag,
    [string]$Sport,
    [string]$ProjectKey
  )
  $w = DP-LoadWorld
  [void](Ensure-RestrictedSchema)
  $node = $w.schools.$School
  [double]$covered = 0.0

  # only draw from restricted if a scope key is provided
  $map = $null; $key = $null
  if ($Sport)      { $map = $node.restricted.balances.sport;   $key = $Sport }
  elseif ($ProjectKey) { $map = $node.restricted.balances.project; $key = $ProjectKey }
  else { return 0.0 }

  $balance = [double]($map[$key] ?? 0)
  if ($UseTag -and $balance -gt 0.0) {
    $draw = [math]::Min($Amount, $balance)
    $map[$key] = [math]::Round($balance - $draw, 2)
    $covered = $draw
    DP-SaveWorld $w
  }
  return $covered
}