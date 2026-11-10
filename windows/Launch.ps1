Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Common.ps1')
$profilePath = Get-ProfilePath
$model = 'claude-azure-sol[1m]'
$claudeArgs = @($args)
if ($claudeArgs.Count -gt 0 -and $claudeArgs[0] -in @('--luna', '--sol', '--astra', '--grok')) {
    $model = @{ '--luna' = 'claude-azure-luna[1m]'; '--sol' = 'claude-azure-sol[1m]';
        '--astra' = 'claude-azure-astra[1m]'; '--grok' = 'claude-azure-grok' }[$claudeArgs[0]]
    $claudeArgs = @($claudeArgs | Select-Object -Skip 1)
}
$settings = Get-Content -Raw (Join-Path $profilePath 'settings.json') | ConvertFrom-Json
try { $null = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$($settings.port)/health/liveliness" -TimeoutSec 5 }
catch { throw 'Gateway unavailable. Start Docker Desktop and run the ClaudeAzureLocal task in Task Scheduler.' }
$values = @{
    CLAUDE_CONFIG_DIR = (Join-Path $profilePath 'claude')
    ANTHROPIC_BASE_URL = "http://127.0.0.1:$($settings.port)"
    ANTHROPIC_AUTH_TOKEN = [IO.File]::ReadAllText((Join-Path $profilePath 'gateway-token')).Trim()
    ANTHROPIC_MODEL = $model; ANTHROPIC_DEFAULT_OPUS_MODEL = 'claude-azure-grok'
    ANTHROPIC_DEFAULT_OPUS_MODEL_NAME = $settings.grok_deployment
    ANTHROPIC_DEFAULT_OPUS_MODEL_DESCRIPTION = 'Azure Foundry · ' + $settings.grok_deployment
    ANTHROPIC_DEFAULT_SONNET_MODEL = 'claude-azure-sol[1m]'
    ANTHROPIC_DEFAULT_SONNET_MODEL_NAME = $settings.sol_deployment
    ANTHROPIC_DEFAULT_SONNET_MODEL_DESCRIPTION = 'Azure Foundry · ' + $settings.sol_deployment
    ANTHROPIC_DEFAULT_HAIKU_MODEL = 'claude-azure-luna[1m]'
    ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME = $settings.luna_deployment
    ANTHROPIC_DEFAULT_HAIKU_MODEL_DESCRIPTION = 'Azure Foundry · ' + $settings.luna_deployment
    ANTHROPIC_CUSTOM_MODEL_OPTION = 'claude-azure-astra[1m]'
    ANTHROPIC_CUSTOM_MODEL_OPTION_NAME = $settings.astra_deployment
    ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION = 'Azure Foundry · ' + $settings.astra_deployment
    CLAUDE_CODE_SUBAGENT_MODEL = 'claude-azure-luna[1m]'; CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY = '0'
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
