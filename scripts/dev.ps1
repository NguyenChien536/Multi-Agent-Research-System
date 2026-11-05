param(
    [ValidateSet('init', 'start', 'status', 'stop', 'logs', 'restart-worker')]
    [string]$Action = 'status',
    [ValidateRange(1024, 65535)][int]$UiPort = 3000,
    [ValidateRange(1024, 65535)][int]$ApiPort = 8000
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$project = 'synthia-dev'
$devDirectory = Join-Path $root 'scratch/development'
$devEnv = Join-Path $devDirectory '.env'
$stateFile = Join-Path $devDirectory 'state.json'
$composeFile = Join-Path $root 'docker-compose.yml'
if (Test-Path -LiteralPath $stateFile) {
    $state = Get-Content -Raw -LiteralPath $stateFile | ConvertFrom-Json
    if (-not $PSBoundParameters.ContainsKey('UiPort')) { $UiPort = [int]$state.ui_port }
    if (-not $PSBoundParameters.ContainsKey('ApiPort')) { $ApiPort = [int]$state.api_port }
}
if ($UiPort -eq $ApiPort) { throw 'Dev UI and API must use different ports.' }
$activeFile = Join-Path $root 'scratch/local-active.json'
if (Test-Path -LiteralPath $activeFile) {
    $demoPort = [int](Get-Content -Raw -LiteralPath $activeFile | ConvertFrom-Json).port
    if ($demoPort -in @($UiPort, $ApiPort)) { throw 'A dev port conflicts with the selected demo port.' }
}

function New-DevSecret {
    $bytes = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    return -join ($bytes | ForEach-Object { $_.ToString('x2') })
}

if ($Action -eq 'init') {
    if (Test-Path -LiteralPath $devEnv) { throw 'Development configuration already exists; secrets were not changed.' }
    $null = New-Item -ItemType Directory -Force -Path $devDirectory
    $lines = @('# Private DEV configuration. Does not copy demo keys or data.',
        "APP_SECRET_KEY=$(New-DevSecret)", "POSTGRES_PASSWORD=$(New-DevSecret)")
    [IO.File]::WriteAllLines($devEnv, $lines, (New-Object Text.UTF8Encoding $false))
    @{ ui_port=$UiPort; api_port=$ApiPort } | ConvertTo-Json | Set-Content -LiteralPath $stateFile
    Write-Output 'Created separate dev secrets. Run .\scripts\dev.ps1 -Action start next.'
    exit 0
}
if (-not (Test-Path -LiteralPath $devEnv)) { throw 'Run .\scripts\dev.ps1 -Action init first.' }
# Compose interpolates inactive profiles too. The release env is only a parser
# input here; COMPOSE_PROFILES and fixed project/service names select dev only.
$env:RELEASE_ENV_FILE = $devEnv
$env:DEV_ENV_FILE = $devEnv
$env:COMPOSE_PROFILES = 'dev'
$env:DEV_UI_PORT = "$UiPort"
$env:DEV_API_PORT = "$ApiPort"

function Invoke-DevCompose {
    param([string[]]$Arguments)
    & docker compose --profile dev --env-file $devEnv -f $composeFile -p $project @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Development Compose failed: $($Arguments[0])" }
}

switch ($Action) {
    'start' {
        Invoke-DevCompose -Arguments @('config', '--quiet')
        Invoke-DevCompose -Arguments @('up', '-d', '--build', '--wait', '--wait-timeout', '300')
        @{ ui_port=$UiPort; api_port=$ApiPort } | ConvertTo-Json | Set-Content -LiteralPath $stateFile
    }
    'status' { Invoke-DevCompose -Arguments @('ps') }
    'stop' { Invoke-DevCompose -Arguments @('stop') }
    'logs' { Invoke-DevCompose -Arguments @('logs', '--tail', '80', 'dev-backend', 'dev-worker', 'dev-frontend', 'dev-gateway') }
    'restart-worker' {
        $active = & docker compose --profile dev --env-file $devEnv -f $composeFile -p $project exec -T dev-postgres psql -U research_user -d research_db -Atc "SELECT count(*) FROM research_tasks WHERE status IN ('RUNNING','QUEUED');"
        if ($LASTEXITCODE -ne 0 -or [int]$active -gt 0) { throw 'Wait for dev research jobs to finish before restarting the worker.' }
        Invoke-DevCompose -Arguments @('restart', '--timeout', '120', 'dev-worker')
        Invoke-DevCompose -Arguments @('up', '-d', '--no-build', '--no-deps', '--wait', '--wait-timeout', '180', 'dev-worker')
    }
}
if ($Action -ne 'stop') {
    Write-Output "DEV UI: http://127.0.0.1:$UiPort | API docs: http://127.0.0.1:$ApiPort/api/v1/docs"
}
