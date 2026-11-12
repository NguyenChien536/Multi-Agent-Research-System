param(
    [string]$ApiBaseUrl = 'http://localhost:8000/api/v1',
    [string]$FrontendUrl = 'http://localhost:3000',
    [int]$TimeoutSeconds = 600
)

$ErrorActionPreference = 'Stop'
$api = $ApiBaseUrl.TrimEnd('/')
$suffix = [guid]::NewGuid().ToString('N').Substring(0, 12)
$email = "demo_$suffix@example.com"
$password = "Aa1!$([guid]::NewGuid().ToString('N'))"
$credentials = @{ email = $email; password = $password }

try {
    $startupDeadline = (Get-Date).AddSeconds(120)
    do {
        try {
            $health = Invoke-RestMethod -Uri "$api/health" -Method Get -TimeoutSec 5
            $frontend = Invoke-WebRequest -Uri $FrontendUrl -Method Get -TimeoutSec 5 -UseBasicParsing
            if ($health.status -eq 'healthy' -and $frontend.StatusCode -eq 200) { break }
        } catch {
            Start-Sleep -Seconds 3
        }
    } while ((Get-Date) -lt $startupDeadline)
    if ($health.status -ne 'healthy' -or $frontend.StatusCode -ne 200) {
        throw 'API and frontend did not become healthy within 120 seconds.'
    }
    $register = @{ username = "demo_$suffix"; email = $email; password = $password }
    $null = Invoke-RestMethod -Uri "$api/auth/register" -Method Post -ContentType 'application/json' -Body ($register | ConvertTo-Json)
    $login = Invoke-RestMethod -Uri "$api/auth/login" -Method Post -ContentType 'application/json' -Body ($credentials | ConvertTo-Json)
    $headers = @{ Authorization = "Bearer $($login.access_token)" }

    $payload = @{
        title = 'Release smoke: evidence-based research'
        research_question = 'What methods improve the traceability of claims to sources in research reports?'
        research_depth = 'SHALLOW'
        max_iterations = 1
        max_sources = 3
    }
    $task = Invoke-RestMethod -Uri "$api/research" -Method Post -Headers $headers -ContentType 'application/json' -Body ($payload | ConvertTo-Json)
    $null = Invoke-RestMethod -Uri "$api/research/$($task.id)/start" -Method Post -Headers $headers
    Write-Output "Started task $($task.id); waiting for a persisted report."

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        Start-Sleep -Seconds 5
        $state = Invoke-RestMethod -Uri "$api/research/$($task.id)" -Method Get -Headers $headers
        if ($state.status -eq 'FAILED') { throw "Research task $($task.id) failed; inspect worker logs." }
        if ($state.status -in @('COMPLETED', 'PARTIAL', 'NEEDS_REVIEW')) { break }
    } while ((Get-Date) -lt $deadline)

    if ($state.status -notin @('COMPLETED', 'PARTIAL', 'NEEDS_REVIEW')) { throw "Research task $($task.id) did not finish within $TimeoutSeconds seconds (last status: $($state.status))." }
    $report = Invoke-RestMethod -Uri "$api/research/$($task.id)/report" -Method Get -Headers $headers
    if ($report.research_task_id -ne $task.id -or [string]::IsNullOrWhiteSpace($report.content_markdown) -or $report.word_count -lt 1) {
        throw 'The completed task has no valid persisted report.'
    }
    Write-Output "PASS (runtime): task $($task.id) persisted report $($report.id) with $($report.word_count) words. Scientific status: $($state.status); PARTIAL/NEEDS_REVIEW still require review."
} catch {
    Write-Error "Release smoke failed: $($_.Exception.Message)"
    exit 1
}
