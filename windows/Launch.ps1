Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Common.ps1')
$profilePath = Get-ProfilePath
$model = 'claude-azure-sol'
$claudeArgs = @($args)
if ($claudeArgs.Count -gt 0 -and $claudeArgs[0] -in @('--luna', '--sol')) {
    if ($claudeArgs[0] -eq '--luna') { $model = 'claude-azure-luna' }
    $claudeArgs = @($claudeArgs | Select-Object -Skip 1)
}
$settings = Get-Content -Raw (Join-Path $profilePath 'settings.json') | ConvertFrom-Json
try { $null = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$($settings.port)/health/liveliness" -TimeoutSec 5 }
catch { throw 'Gateway unavailable. Start Docker Desktop and run the ClaudeAzureLocal task in Task Scheduler.' }
$values = @{
    CLAUDE_CONFIG_DIR = (Join-Path $profilePath 'claude')
    ANTHROPIC_BASE_URL = "http://127.0.0.1:$($settings.port)"
    ANTHROPIC_AUTH_TOKEN = [IO.File]::ReadAllText((Join-Path $profilePath 'gateway-token')).Trim()
    ANTHROPIC_MODEL = $model; ANTHROPIC_DEFAULT_OPUS_MODEL = 'claude-azure-sol'
    ANTHROPIC_DEFAULT_SONNET_MODEL = 'claude-azure-sol'; ANTHROPIC_DEFAULT_HAIKU_MODEL = 'claude-azure-luna'
    CLAUDE_CODE_SUBAGENT_MODEL = 'claude-azure-luna'; CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY = '1'
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = '1'
}
foreach ($name in @('ANTHROPIC_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN', 'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY')) { $values[$name] = $null }
$saved = @{}
try {
    foreach ($name in $values.Keys) {
        $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $values[$name], 'Process')
    }
    & claude --model $model @claudeArgs
    $result = $LASTEXITCODE
} finally {
    foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process') }
}
exit $result
