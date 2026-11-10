# Windows PowerShell 5.1+, Docker Desktop in Linux-container mode, Claude Code.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Common.ps1')
if ($env:OS -ne 'Windows_NT') { throw 'Use setup.sh on Linux.' }
foreach ($command in @('docker', 'claude', 'Register-ScheduledTask')) { $null = Get-Command $command -ErrorAction Stop }
$repo = Split-Path $PSScriptRoot -Parent
$profilePath = Get-ProfilePath
$installed = Test-Path (Join-Path $profilePath 'installed.json')
if ((Get-Command claude-azure -ErrorAction SilentlyContinue) -and -not $installed) { throw 'claude-azure already exists; it was left unchanged.' }
$original = Join-Path $env:USERPROFILE '.claude'
if ($env:CLAUDE_CONFIG_DIR) { $original = $env:CLAUDE_CONFIG_DIR }
$projects = Join-Path $original 'projects'
if (-not (Test-Path $projects -PathType Container)) { throw 'Start normal Claude Code once before setup.' }
$platform = & docker info --format '{{.OSType}}/{{.Architecture}}'
if ($LASTEXITCODE -ne 0 -or $platform -notmatch '^linux/(x86_64|amd64)$') { throw 'Start Docker Desktop in Linux-container mode on x64 Windows.' }
if ($installed) {
    $existing = & docker ps -aq --filter 'name=^/claude-azure-local$'
    if ($existing) {
        $labels = (& docker inspect --format '{{json .Config.Labels}}' claude-azure-local) | ConvertFrom-Json
        $label = $labels.'org.claude-azure-local.managed'
        if ($label -ne 'true') { throw 'Container name occupied by an unmanaged container; left unchanged.' }
    }
}
$old = @{ endpoint = ''; sol_deployment = 'gpt-6.1-sol'; luna_deployment = 'gpt-6-luna';
    astra_deployment = 'gpt-6-astra'; grok_deployment = 'grok-4.6'; port = 48763 }
if (Test-Path (Join-Path $profilePath 'settings.json')) { $old = Get-Content -Raw (Join-Path $profilePath 'settings.json') | ConvertFrom-Json }
Write-Host 'Credential storage: Windows DPAPI CurrentUser. Startup runs at sign-in under this account.'
$endpoint = Get-AzureEndpoint (Read-LocalSetting 'Azure endpoint' $old.endpoint)
$sol = Read-LocalSetting 'Sol deployment' $old.sol_deployment
$luna = Read-LocalSetting 'Luna deployment' $old.luna_deployment
$astra = Read-LocalSetting 'Astra deployment' $old.astra_deployment
$grok = Read-LocalSetting 'Grok deployment' $old.grok_deployment
foreach ($name in @($sol, $luna, $astra, $grok)) { if ($name -notmatch '^[A-Za-z0-9_.-]{1,128}$') { throw 'Invalid deployment name.' } }
$port = [int](Read-LocalSetting 'Local port' ([string]$old.port))
if ($port -lt 1024 -or $port -gt 65535) { throw 'Port must be between 1024 and 65535.' }
if (-not $installed) {
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $port)
    try { $listener.Start() } finally { $listener.Stop() }
}
$lock = Get-Content -Raw (Join-Path $repo 'image-lock.json') | ConvertFrom-Json
$image = $lock.images.amd64
& docker pull $image
if ($LASTEXITCODE -ne 0) { throw 'Pinned image download failed; no credential was requested.' }
$settings = @{ endpoint = $endpoint; sol_deployment = $sol; luna_deployment = $luna;
    astra_deployment = $astra; grok_deployment = $grok; port = $port; image = $image }
Write-Host 'Sol and Astra tool calls use Responses; Luna uses Chat Completions with reasoning disabled.'
$secure = Read-Host 'Azure key (hidden)' -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$bytes = $null
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim()
    if (-not $plain) { throw 'No Azure key entered.' }
    $bytes = [Text.Encoding]::UTF8.GetBytes($plain)
    $protected = [Security.Cryptography.ProtectedData]::Protect($bytes, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    if ($null -ne $bytes) { [Array]::Clear($bytes, 0, $bytes.Length) }
    $plain = $null; $secure.Dispose()
}
$null = New-Item -ItemType Directory -Path $profilePath -Force
Protect-Profile $profilePath
$taskName = Get-TaskName
if ($installed) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    & docker stop --time 20 claude-azure-local 2>$null | Out-Null
}
[IO.File]::WriteAllBytes((Join-Path $profilePath 'azure-key.dpapi'), $protected)
foreach ($file in @('Common.ps1', 'Start-Gateway.ps1', 'Launch.ps1', 'Verify.ps1', 'Uninstall.ps1')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination (Join-Path $profilePath $file) -Force
}
Copy-Item -LiteralPath (Join-Path $repo 'src') -Destination $profilePath -Recurse -Force
$settings | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $profilePath 'settings.json') -Encoding UTF8
$tokenPath = Join-Path $profilePath 'gateway-token'
if (-not (Test-Path $tokenPath)) { [IO.File]::WriteAllText($tokenPath, (New-GatewayToken)) }
$claudeProfile = Join-Path $profilePath 'claude'
$null = New-Item -ItemType Directory -Path $claudeProfile -Force
$target = Join-Path $claudeProfile 'projects'
if (-not (Test-Path $target)) { $null = New-Item -ItemType Junction -Path $target -Target (Resolve-Path $projects).Path }
elseif ((Get-Item -LiteralPath $target).Target -notcontains (Resolve-Path $projects).Path) { throw 'Existing chat-history link points elsewhere; left unchanged.' }
$claudeSettingsPath = Join-Path $claudeProfile 'settings.json'
$claudeSettings = [pscustomobject]@{}
if (Test-Path $claudeSettingsPath) {
    $claudeSettings = Get-Content -Raw $claudeSettingsPath | ConvertFrom-Json
}
$claudeSettings | Add-Member -NotePropertyName availableModels -NotePropertyValue @(
    'claude-azure-sol[1m]', 'claude-azure-luna[1m]', 'claude-azure-astra[1m]', 'claude-azure-grok') -Force
if (-not $claudeSettings.PSObject.Properties['modelSettings']) {
    $claudeSettings | Add-Member -NotePropertyName modelSettings -NotePropertyValue ([pscustomobject]@{})
}
foreach ($alias in @('claude-azure-sol', 'claude-azure-luna', 'claude-azure-astra')) {
    $name = $alias + '[1m]'
    if (-not $claudeSettings.modelSettings.PSObject.Properties[$name]) {
        $claudeSettings.modelSettings | Add-Member -NotePropertyName $name -NotePropertyValue ([pscustomobject]@{})
    }
    $claudeSettings.modelSettings.PSObject.Properties[$name].Value |
        Add-Member -NotePropertyName autoCompactWindow -NotePropertyValue 900000 -Force
}
$claudeSettings | ConvertTo-Json -Depth 20 | Set-Content $claudeSettingsPath -Encoding UTF8
$bin = Join-Path $profilePath 'bin'
$null = New-Item -ItemType Directory -Path $bin -Force
$cmd = '@echo off' + "`r`n" + 'powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File "%LOCALAPPDATA%\ClaudeAzureLocal\Launch.ps1" %*' + "`r`n" + 'exit /b %errorlevel%'
$cmd | Set-Content -LiteralPath (Join-Path $bin 'claude-azure.cmd') -Encoding ASCII
$currentPath = [string][Environment]::GetEnvironmentVariable('Path', 'User')
if (($currentPath -split ';') -notcontains $bin) { [Environment]::SetEnvironmentVariable('Path', ($currentPath.TrimEnd(';') + ';' + $bin), 'User') }
$account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File "' + (Join-Path $profilePath 'Start-Gateway.ps1') + '"')
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $account
$principal = New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
$taskSettings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$null = Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $taskSettings -Force
'{"version":1,"storage":"DPAPI-CurrentUser"}' | Set-Content (Join-Path $profilePath 'installed.json') -Encoding UTF8
Start-ScheduledTask -TaskName $taskName
Write-Host 'Installed. The sign-in task starts Docker Desktop when found. Open a new terminal for claude-azure.'
& (Join-Path $profilePath 'Verify.ps1')
