Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Security

function Get-ProfilePath { return (Join-Path $env:LOCALAPPDATA 'ClaudeAzureLocal') }
function Get-TaskName { return ('ClaudeAzureLocal-' + [Security.Principal.WindowsIdentity]::GetCurrent().User.Value) }
function Get-AzureEndpoint([string]$Value) {
    $u = $null
    if (-not [Uri]::TryCreate($Value.Trim(), [UriKind]::Absolute, [ref]$u) -or
        $u.Scheme -ne 'https' -or $u.UserInfo -or $u.Query -or $u.Fragment) {
        throw 'Use an HTTPS Azure resource URL without credentials, query or fragment.'
    }
    $path = $u.AbsolutePath.TrimEnd('/') -replace '/(responses|chat/completions)$', ''
    if ($path -eq '' -or $path -eq '/openai') { $path = '/openai/v1' }
    if ($path -ne '/openai/v1') { throw 'Expected one Azure resource or /openai/v1/ endpoint.' }
    return ('https://' + $u.Authority + $path + '/')
}
function Protect-Profile([string]$Path) {
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $acl = [Security.AccessControl.DirectorySecurity]::new()
    $acl.SetOwner($sid)
    $acl.SetAccessRuleProtection($true, $false)
    $inherit = [Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit'
    $propagate = [Security.AccessControl.PropagationFlags]::None
    $allow = [Security.AccessControl.AccessControlType]::Allow
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', $inherit, $propagate, $allow))
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-5-18'), 'FullControl', $inherit, $propagate, $allow))
    Set-Acl -LiteralPath $Path -AclObject $acl
}
function Read-LocalSetting([string]$Prompt, [string]$Default) {
    $value = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value.Trim()
}
function New-GatewayToken {
    $bytes = New-Object byte[] 40
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ('sk-' + [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_'))
}
function New-GatewayConfig($Settings, [string]$AzureKey, [string]$Token) {
    $models = @()
    foreach ($entry in @(@('claude-azure-sol', $Settings.sol_deployment, 'low', 'Azure Sol'),
                          @('claude-azure-luna', $Settings.luna_deployment, 'none', 'Azure Luna'))) {
        $models += @{
            model_name = $entry[0]
            litellm_params = @{ model = ('openai/' + $entry[1]); api_base = $Settings.endpoint;
                api_key = $AzureKey.Trim(); reasoning_effort = $entry[2]; use_chat_completions_api = $true }
            model_info = @{ display_name = $entry[3] }
        }
    }
    return @{
        model_list = $models
        litellm_settings = @{ drop_params = $true; set_verbose = $false; turn_off_message_logging = $true;
            telemetry = $false; use_chat_completions_url_for_anthropic_messages = $true;
            route_all_chat_openai_to_responses = $false; callbacks = @('compat.handler') }
        general_settings = @{ master_key = $Token; disable_spend_logs = $true }
    }
}
function Get-GatewayDockerArgs([string]$Source, [int]$Port, [string]$Image) {
    if ($Source.Contains(',')) { throw 'The install path cannot contain a comma (Docker mount syntax).' }
    return @('run', '--rm', '-i', '--name', 'claude-azure-local',
        '--label', 'org.claude-azure-local.managed=true',
        '--publish', "127.0.0.1:${Port}:4000", '--user', '65532:65532', '--read-only',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--pids-limit', '256',
        '--memory', '2g', '--cpus', '2', '--log-driver', 'none',
        '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m,mode=1777',
        '--env', 'HOME=/tmp', '--env', 'PYTHONPATH=/opt/claude-azure',
        '--env', 'LITELLM_TELEMETRY=False', '--env', 'LITELLM_LOCAL_MODEL_COST_MAP=True',
        '--env', 'LITELLM_USE_CHAT_COMPLETIONS_URL_FOR_ANTHROPIC_MESSAGES=true',
        '--env', 'LITELLM_ROUTE_ALL_CHAT_OPENAI_TO_RESPONSES=false',
        '--mount', "type=bind,src=$Source,dst=/opt/claude-azure,readonly",
        '--entrypoint', '/app/.venv/bin/python', $Image, '/opt/claude-azure/bootstrap.py')
}
