[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9]+$')]
    [string]$Issue,

    [Parameter(Mandatory = $true)]
    [ValidateSet('feature', 'fix', 'docs', 'chore')]
    [string]$Type,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Title
)

$ErrorActionPreference = 'Stop'

$repoRoot = git rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0 -or -not $repoRoot) {
    throw 'Run this script from inside the project Git repository.'
}

$status = git status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw 'Could not read Git working-tree status.'
}
if ($status) {
    throw "Working tree is not clean. Save or finish current changes before creating a new feature branch.`n$status"
}

$slug = $Title.ToLowerInvariant()
$slug = [regex]::Replace($slug, '[^a-z0-9]+', '-')
$slug = $slug.Trim('-')
if (-not $slug) {
    throw 'Title must contain at least one English letter or number for the branch slug.'
}
if ($slug.Length -gt 48) {
    $slug = $slug.Substring(0, 48).TrimEnd('-')
}

$branch = "$Type/$Issue-$slug"

git fetch origin main
if ($LASTEXITCODE -ne 0) {
    throw 'Fetching origin/main failed. Check network and remote configuration.'
}

git show-ref --verify --quiet "refs/heads/$branch"
if ($LASTEXITCODE -eq 0) {
    throw "Local branch already exists: $branch"
}

git switch --create $branch origin/main
if ($LASTEXITCODE -ne 0) {
    throw "Could not create branch $branch from origin/main."
}

Write-Host "Created $branch from origin/main. Work on this branch for Issue #$Issue only."
