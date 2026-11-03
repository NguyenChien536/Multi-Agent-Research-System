param(
    [ValidateSet('init', 'start', 'status', 'stop', 'logs', 'backup', 'restore')]
    [string]$Action = 'status',
    [string]$Project = 'synthia-release',
    [string]$EnvFile = '',
    [int]$Port = 3080,
    [string]$BackupPath = ''
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if ($Project -notmatch '^synthia-[a-z0-9]+(-[a-z0-9]+)*$') { throw 'Use a synthia-<name> project name.' }
if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Port must be between 1024 and 65535.' }
if (-not $EnvFile) { $EnvFile = Join-Path $root 'scratch/release-local/.env' }
$EnvFile = [IO.Path]::GetFullPath($EnvFile)
$composeFile = Join-Path $root 'compose.release.yml'

function New-Secret {
    $bytes = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    return -join ($bytes | ForEach-Object { $_.ToString('x2') })
}

function Invoke-Compose {
    param([string[]]$Arguments)
    & docker compose --env-file $EnvFile -f $composeFile -p $Project @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed: $($Arguments[0])" }
}

if ($Action -eq 'init') {
    if (Test-Path -LiteralPath $EnvFile) { throw 'Release environment already exists; edit it rather than replacing its secrets.' }
    $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $EnvFile)
    $lines = @(
        '# Private local release configuration; never commit or share this file.',
        "APP_SECRET_KEY=$(New-Secret)", "POSTGRES_PASSWORD=$(New-Secret)"
    )
    $sourceEnv = Join-Path $root '.env'
    if (Test-Path -LiteralPath $sourceEnv) {
        # Copy only provider settings; keep development DB, auth and mock settings out.
        $lines += Get-Content -LiteralPath $sourceEnv | Where-Object {
            $_ -match '^(TAVILY_|OPENALEX_|CROSSREF_|SCHOLARLY_|ANTHROPIC_|OPENAI_|GEMINI_|GROQ_|LLM_PROVIDER_|EMBEDDING_PROVIDER_)'
        }
    }
    [IO.File]::WriteAllLines($EnvFile, $lines, (New-Object Text.UTF8Encoding $false))
    Write-Output "Created private configuration: $EnvFile"
    Write-Output 'Provider settings were copied locally; no values were printed. Run -Action start next.'
    exit 0
}

if (-not (Test-Path -LiteralPath $EnvFile)) { throw 'Run -Action init first.' }
$env:RELEASE_ENV_FILE = $EnvFile
$stateFile = Join-Path (Split-Path -Parent $EnvFile) "$Project-state.json"
$state = if (Test-Path -LiteralPath $stateFile) { Get-Content -Raw -LiteralPath $stateFile | ConvertFrom-Json } else { $null }
if ($state -and -not $PSBoundParameters.ContainsKey('Port')) { $Port = $state.port }
$env:RELEASE_PORT = "$Port"
$revision = (& git -C $root rev-parse --short=12 HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve release revision.' }
if ($Action -ne 'start' -and $state) { $revision = $state.revision }
$env:RELEASE_REVISION = $revision

switch ($Action) {
    'start' {
        $dirty = & git -C $root status --porcelain -- backend frontend docker scripts compose.release.yml
        if ($dirty) { throw 'Commit the runtime changes before building a release; image revision must identify its source.' }
        Invoke-Compose -Arguments @('config', '--quiet')
        Invoke-Compose -Arguments @('up', '-d', '--build', '--wait', '--wait-timeout', '240')
        @{ revision=$revision; port=$Port } | ConvertTo-Json | Set-Content -LiteralPath $stateFile
        Write-Output "Release ready: http://127.0.0.1:$Port (revision $revision)"
    }
    'status' { Invoke-Compose -Arguments @('ps') }
    'stop' { Invoke-Compose -Arguments @('stop') } # Never removes volumes or data.
    'logs' { Invoke-Compose -Arguments @('logs', '--tail', '100', 'backend', 'worker', 'gateway') }
    'backup' {
        if (-not $BackupPath) { $BackupPath = Join-Path $root "scratch/release-backups/$(Get-Date -Format yyyyMMdd-HHmmss)" }
        $BackupPath = [IO.Path]::GetFullPath($BackupPath)
        if (Test-Path -LiteralPath $BackupPath) { throw 'Choose a new backup directory.' }
        $null = New-Item -ItemType Directory -Path $BackupPath
        # Remove API ingress before checking for active work. Do not kill a live experiment.
        Invoke-Compose -Arguments @('stop', 'gateway', 'backend')
        try {
            $active = & docker compose --env-file $EnvFile -f $composeFile -p $Project exec -T postgres psql -U research_user -d research_db -Atc "SELECT count(*) FROM research_tasks WHERE status IN ('RUNNING','QUEUED');"
            if ($LASTEXITCODE -ne 0 -or [int]$active -gt 0) { throw 'Wait for queued/running research to finish before backing up.' }
            Invoke-Compose -Arguments @('stop', 'worker')
            Invoke-Compose -Arguments @('exec', '-T', 'postgres', 'pg_dump', '-U', 'research_user', '-d', 'research_db', '-Fc', '-f', '/tmp/research.dump')
            Invoke-Compose -Arguments @('cp', 'postgres:/tmp/research.dump', (Join-Path $BackupPath 'research.dump'))
            # Keep the binary archive in a named helper's tmpfs until docker cp finishes.
            # PowerShell 5 redirection/pipelines must not transport binary dump/archive bytes.
            $helper = "$Project-backup-$([guid]::NewGuid().ToString('N').Substring(0,8))"
            Invoke-Compose -Arguments @('run', '-d', '--no-deps', '--name', $helper, 'backend', 'sleep', '120')
            try {
                & docker exec $helper tar czf /tmp/artifacts.tgz -C /app/storage/artifacts .
                if ($LASTEXITCODE -ne 0) { throw 'Artifact backup failed.' }
                & docker cp "${helper}:/tmp/artifacts.tgz" (Join-Path $BackupPath 'artifacts.tgz')
                if ($LASTEXITCODE -ne 0) { throw 'Artifact archive copy failed.' }
            } finally { & docker rm -f $helper | Out-Null }
            @{ revision=$revision; project=$Project; created_at=(Get-Date).ToUniversalTime().ToString('o') } |
                ConvertTo-Json | Set-Content -LiteralPath (Join-Path $BackupPath 'manifest.json')
            Get-ChildItem -LiteralPath $BackupPath -File | Get-FileHash -Algorithm SHA256 |
                Select-Object @{Name='file';Expression={Split-Path -Leaf $_.Path}}, Hash |
                ConvertTo-Json | Set-Content -LiteralPath (Join-Path $BackupPath 'checksums.json')
            Write-Output "Backup saved: $BackupPath (contains private research; keep local)."
        } finally {
            Invoke-Compose -Arguments @('up', '-d', '--wait', '--wait-timeout', '180')
        }
    }
    'restore' {
        # A fresh rehearsal project is mandatory: restoring over the working demo is forbidden.
        if ($Project -eq 'synthia-release') { throw 'Restore only to a new synthia-restore-<name> project on another port.' }
        if ($Project -notmatch '^synthia-restore-[a-z0-9]+(-[a-z0-9]+)*$' -or $Port -eq 3080) { throw 'Use a synthia-restore-<name> project and a different port.' }
        $BackupPath = (Resolve-Path -LiteralPath $BackupPath).Path
        foreach ($name in @('research.dump','artifacts.tgz','manifest.json','checksums.json')) {
            if (-not (Test-Path -LiteralPath (Join-Path $BackupPath $name))) { throw "Backup missing $name" }
        }
        foreach ($entry in (Get-Content -Raw -LiteralPath (Join-Path $BackupPath 'checksums.json') | ConvertFrom-Json)) {
            if ($entry.file -notin @('research.dump','artifacts.tgz','manifest.json')) { throw 'Unexpected backup checksum path.' }
            if ((Get-FileHash -LiteralPath (Join-Path $BackupPath $entry.file)).Hash -ne $entry.Hash) { throw 'Backup checksum mismatch.' }
        }
        $manifest = Get-Content -Raw -LiteralPath (Join-Path $BackupPath 'manifest.json') | ConvertFrom-Json
        if ($manifest.revision -notmatch '^[0-9a-f]{12}$') { throw 'Invalid backup image revision.' }
        $revision = $manifest.revision
        $env:RELEASE_REVISION = $revision
        $existing = & docker volume ls --filter "label=com.docker.compose.project=$Project" -q
        if ($existing) { throw 'Restore target already has volumes; choose a new project.' }
        Invoke-Compose -Arguments @('up', '-d', '--wait', 'postgres', 'redis')
        Invoke-Compose -Arguments @('cp', (Join-Path $BackupPath 'research.dump'), 'postgres:/tmp/research.dump')
        Invoke-Compose -Arguments @('exec', '-T', 'postgres', 'pg_restore', '-U', 'research_user', '-d', 'research_db', '--no-owner', '--exit-on-error', '/tmp/research.dump')
        $helper = "$Project-artifacts-$([guid]::NewGuid().ToString('N').Substring(0,8))"
        Invoke-Compose -Arguments @('run', '-d', '--no-deps', '--name', $helper, 'backend', 'sleep', '120')
        try {
            & docker cp (Join-Path $BackupPath 'artifacts.tgz') "${helper}:/tmp/artifacts.tgz"
            if ($LASTEXITCODE -ne 0) { throw 'Artifact copy failed.' }
            & docker exec $helper tar xzf /tmp/artifacts.tgz -C /app/storage/artifacts
            if ($LASTEXITCODE -ne 0) { throw 'Artifact restore failed.' }
        } finally { & docker rm -f $helper | Out-Null }
        Invoke-Compose -Arguments @('up', '-d', '--wait', '--wait-timeout', '240')
        @{ revision=$revision; port=$Port } | ConvertTo-Json | Set-Content -LiteralPath $stateFile
        Write-Output "Restored rehearsal: http://127.0.0.1:$Port. Stop this project after verification."
    }
}
