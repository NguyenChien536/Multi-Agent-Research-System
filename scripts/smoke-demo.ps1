param(
    [string]$ApiBaseUrl = 'http://localhost:8000/api/v1',
    [int]$TimeoutSeconds = 600
)

$ErrorActionPreference = 'Stop'
$api = $ApiBaseUrl.TrimEnd('/')
$suffix = [guid]::NewGuid().ToString('N').Substring(0, 12)
$email = "demo_$suffix@example.com"
$password = "Aa1!$([guid]::NewGuid().ToString('N'))"
$credentials = @{ email = $email; password = $password }

try {
    $health = Invoke-RestMethod -Uri "$api/health" -Method Get
    $null = $health
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
        if ($state.status -eq 'COMPLETED') { break }
    } while ((Get-Date) -lt $deadline)

    if ($state.status -ne 'COMPLETED') { throw "Research task $($task.id) did not finish within $TimeoutSeconds seconds (last status: $($state.status))." }
    $report = Invoke-RestMethod -Uri "$api/research/$($task.id)/report" -Method Get -Headers $headers
    if ($report.research_task_id -ne $task.id -or [string]::IsNullOrWhiteSpace($report.content_markdown) -or $report.word_count -lt 1) {
        throw 'The completed task has no valid persisted report.'
    }
    Write-Output "PASS: task $($task.id) completed; report $($report.id) has $($report.word_count) words."
} catch {
    Write-Error "Release smoke failed: $($_.Exception.Message)"
    exit 1
}
