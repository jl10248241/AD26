Param(
    [Parameter(Mandatory=$true)]
    [string]$EnginePath
)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspace = Split-Path $here -Parent

$envContent = @"
LOG_DIR=./logs
CONFIG_DIR=./configs
DOCS_DIR=./docs
DATA_DIR=./data
"@
Set-Content -Path (Join-Path $workspace ".env") -Value $envContent -Encoding UTF8

$engineDest = Join-Path $workspace "engine"
New-Item -ItemType Directory -Path $engineDest -Force | Out-Null
Copy-Item -Path (Join-Path $EnginePath "*") -Destination $engineDest -Recurse -Force

Write-Host "Engine copied to: $engineDest"
Write-Host ".env created with relative paths."
