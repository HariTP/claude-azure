param([switch]$SkipDpapi)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
foreach ($file in (Get-ChildItem -LiteralPath $root -Filter '*.ps1' -Recurse)) {
    $tokens = $null; $parseErrors = $null
    $null = [Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$parseErrors)
    if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
}
. (Join-Path $root 'windows/Common.ps1')
function Assert-Equal($Actual, $Expected, [string]$Message) {
    if ($Actual -ne $Expected) { throw $Message }
}
Assert-Equal (Get-AzureEndpoint 'https://example.test/openai/v1/responses') 'https://example.test/openai/v1/' 'Endpoint normalization failed.'
$rejected = $false
try { $null = Get-AzureEndpoint 'https://user:secret@example.test/' } catch { $rejected = $true }
if (-not $rejected) { throw 'Credential-bearing URL was accepted.' }
$settings = @{ endpoint = 'https://example.test/openai/v1/'; sol_deployment = 'gpt-6.1-sol';
    luna_deployment = 'gpt-6-luna'; astra_deployment = 'gpt-6-astra';
    grok_deployment = 'grok-4.6'; port = 48763 }
$config = New-GatewayConfig $settings '  mock-key  ' 'mock-token'
Assert-Equal $config.model_list[0].litellm_params.reasoning_effort 'low' 'Sol reasoning default failed.'
Assert-Equal $config.model_list[2].litellm_params.reasoning_effort 'none' 'Luna reasoning default failed.'
Assert-Equal $config.model_list[4].litellm_params.reasoning_effort 'low' 'Astra reasoning default failed.'
Assert-Equal $config.model_list[6].model_info.display_name 'grok-4.6' 'Grok display name failed.'
if ($config.model_list[6].litellm_params.ContainsKey('reasoning_effort')) { throw 'Grok unexpectedly has a reasoning setting.' }
Assert-Equal $config.model_list[0].litellm_params.api_key 'mock-key' 'Key trimming failed.'
$dockerArgs = Get-GatewayDockerArgs 'C:\Users\Example User\src' 48763 'image@sha256:mock'
if ($dockerArgs -notcontains '127.0.0.1:48763:4000') { throw 'Localhost binding missing.' }
if (($dockerArgs -join ' ') -match 'mock-key|mock-token') { throw 'Credential leaked into Docker arguments.' }
if (-not $SkipDpapi) {
    $plain = [Text.Encoding]::UTF8.GetBytes('dummy-ci-secret')
    $blob = [Security.Cryptography.ProtectedData]::Protect($plain, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
    $roundTrip = [Security.Cryptography.ProtectedData]::Unprotect($blob, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
    Assert-Equal ([Text.Encoding]::UTF8.GetString($roundTrip)) 'dummy-ci-secret' 'DPAPI round-trip failed.'
    [Array]::Clear($plain, 0, $plain.Length)
    [Array]::Clear($roundTrip, 0, $roundTrip.Length)
    Write-Host 'Windows DPAPI CurrentUser dummy-secret round trip passed.'
}
Write-Host 'PowerShell syntax and shared configuration tests passed.'
