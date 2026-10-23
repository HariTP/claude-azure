$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$previousLocal = $env:LOCALAPPDATA
$previousKey = $env:ANTHROPIC_API_KEY
$previousBase = $env:ANTHROPIC_BASE_URL
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('claude-azure-launch-' + [Guid]::NewGuid().ToString())
$env:LOCALAPPDATA = $fixture
$profilePath = Join-Path $env:LOCALAPPDATA 'ClaudeAzureLocal'
$null = New-Item -ItemType Directory -Path $profilePath -Force
'{"port":48763}' | Set-Content (Join-Path $profilePath 'settings.json')
'mock-token' | Set-Content (Join-Path $profilePath 'gateway-token')
$env:ANTHROPIC_API_KEY = 'original-user-credential-placeholder'
$env:ANTHROPIC_BASE_URL = 'https://original.invalid'
function global:Invoke-WebRequest { param($Uri, $TimeoutSec, [switch]$UseBasicParsing) return @{StatusCode=200} }
function global:claude {
    if ($env:ANTHROPIC_MODEL -ne 'claude-azure-luna') { throw 'Wrong model' }
    if ($env:ANTHROPIC_API_KEY) { throw 'Inherited API key was not removed' }
    if ($env:ANTHROPIC_AUTH_TOKEN -ne 'mock-token') { throw 'Wrong gateway token' }
    if (($args -join ' ') -ne '--model claude-azure-luna --resume') { throw ('Arguments corrupted: ' + ($args -join ' ')) }
    $global:LaunchCalled = $true
    $global:LASTEXITCODE = 0
}
& (Join-Path $repo 'windows/Launch.ps1') --luna --resume
if (-not $global:LaunchCalled) { throw 'Claude was not invoked' }
if ($env:ANTHROPIC_API_KEY -ne 'original-user-credential-placeholder') { throw 'Parent credential was changed' }
if ($env:ANTHROPIC_BASE_URL -ne 'https://original.invalid') { throw 'Parent URL was changed' }
Write-Host 'Windows launcher argument forwarding and parent-environment restoration passed (mocked commands).'

$env:LOCALAPPDATA = $previousLocal
$env:ANTHROPIC_API_KEY = $previousKey
$env:ANTHROPIC_BASE_URL = $previousBase
Remove-Item -LiteralPath $fixture -Recurse -Force
