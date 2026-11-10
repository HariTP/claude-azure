Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
. (Join-Path $PSScriptRoot 'Common.ps1')
$profilePath = Get-ProfilePath
$settings = Get-Content -Raw (Join-Path $profilePath 'settings.json') | ConvertFrom-Json
$base = "http://127.0.0.1:$($settings.port)"
$token = [IO.File]::ReadAllText((Join-Path $profilePath 'gateway-token')).Trim()
$headers = @{ Authorization = "Bearer $token"; 'anthropic-version' = '2023-06-01' }
function Request-Message($Payload) {
    try {
        return Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$base/v1/messages" -Headers $headers -ContentType 'application/json' -Body ($Payload | ConvertTo-Json -Depth 30 -Compress) -TimeoutSec 120
    } catch { throw 'Gateway verification request failed. Raw response withheld; check deployment names and the documented API/reasoning settings.' }
}
$ready = $false
for ($i = 0; $i -lt 90; $i++) {
    try {
        $null = Invoke-WebRequest -UseBasicParsing -Uri "$base/health/liveliness" -TimeoutSec 2
        $ready = $true; break
    } catch { Start-Sleep -Seconds 2 }
}
if (-not $ready) { throw 'Gateway did not become ready. Check Docker Desktop and Task Scheduler.' }
try { $models = (Invoke-RestMethod -Uri "$base/v1/models" -Headers $headers -TimeoutSec 5).data.id }
catch { throw 'Gateway authentication or discovery failed; raw response withheld.' }
foreach ($model in @('claude-azure-sol[1m]', 'claude-azure-luna[1m]',
                     'claude-azure-astra[1m]', 'claude-azure-grok')) {
    if ($models -notcontains $model) { throw "Discovery is missing $model" }
    $messages = @(@{ role = 'user'; content = 'Call choose_color with color blue.' })
    $payload = @{ model = $model; max_tokens = 1024; stream = $true; messages = $messages
        tools = @(@{ name = 'choose_color'; description = 'Choose a color.'; input_schema = @{
            type = 'object'; properties = @{ color = @{ type = 'string'; enum = @('blue') } }
            required = @('color'); additionalProperties = $false } })
        tool_choice = @{ type = 'tool'; name = 'choose_color' } }
    $response = Request-Message $payload
    $tool = $null; $arguments = ''; $stopped = $false
    foreach ($line in ([string]$response.Content -split '\r?\n')) {
        if (-not $line.StartsWith('data:')) { continue }
        $raw = $line.Substring(5).Trim()
        if ($raw -eq '[DONE]') { continue }
        $event = $raw | ConvertFrom-Json
        switch ($event.type) {
            'error' { throw "Gateway streaming error for $model; raw response withheld." }
            'content_block_start' { if ($event.content_block.type -eq 'tool_use') { $tool = $event.content_block } }
            'content_block_delta' { if ($event.delta.type -eq 'input_json_delta') { $arguments += $event.delta.partial_json } }
            'message_stop' { $stopped = $true }
        }
    }
    if (-not $stopped -or $null -eq $tool -or $tool.name -ne 'choose_color') { throw "Streaming tool call failed for $model" }
    $inputValue = $tool.input
    if ($arguments) { $inputValue = $arguments | ConvertFrom-Json }
    if ($inputValue.color -ne 'blue') { throw "Tool arguments failed for $model" }
    $payload.messages = @($messages[0],
        @{ role = 'assistant'; content = @(@{ type = 'tool_use'; id = $tool.id; name = $tool.name; input = $inputValue }) },
        @{ role = 'user'; content = @(@{ type = 'tool_result'; tool_use_id = $tool.id; content = 'Color recorded: blue.' }) })
    $payload.stream = $false
    $payload.tool_choice = @{ type = 'none' }
    $result = (Request-Message $payload).Content | ConvertFrom-Json
    $hasText = @($result.content | Where-Object { $_.type -eq 'text' -and $_.text }).Count -gt 0
    if (-not $hasText) { throw "Tool-result continuation failed for $model" }
    Write-Host "$model : discovery, streaming, tool call, and continuation passed."
}
