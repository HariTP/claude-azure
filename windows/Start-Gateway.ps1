Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Common.ps1')
$profilePath = Get-ProfilePath
function Test-DockerReady {
    $prior = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & docker info --format '{{.OSType}}' 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } finally { $ErrorActionPreference = $prior }
}
if (-not (Test-DockerReady)) {
    foreach ($app in @((Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe'),
                        (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'))) {
        if (Test-Path $app) { Start-Process -FilePath $app; break }
    }
}
$ready = $false
for ($i = 0; $i -lt 120; $i++) {
    if (Test-DockerReady) { $ready = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $ready) { exit 1 }
$existing = & docker ps -aq --filter 'name=^/claude-azure-local$'
if ($existing) {
    $labels = (& docker inspect --format '{{json .Config.Labels}}' claude-azure-local) | ConvertFrom-Json
        $label = $labels.'org.claude-azure-local.managed'
    if ($label -ne 'true') { throw 'Container name is occupied by an unmanaged container.' }
    & docker rm -f claude-azure-local 2>$null | Out-Null
}
$settings = Get-Content -Raw (Join-Path $profilePath 'settings.json') | ConvertFrom-Json
$blob = [IO.File]::ReadAllBytes((Join-Path $profilePath 'azure-key.dpapi'))
$bytes = [Security.Cryptography.ProtectedData]::Unprotect($blob, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
try {
    $key = [Text.Encoding]::UTF8.GetString($bytes).Trim()
    $token = [IO.File]::ReadAllText((Join-Path $profilePath 'gateway-token')).Trim()
    $config = New-GatewayConfig $settings $key $token
    $payload = $config | ConvertTo-Json -Depth 30 -Compress
    $dockerArgs = Get-GatewayDockerArgs (Join-Path $profilePath 'src') $settings.port $settings.image
    # The secret is stdin only: no Azure key in Docker metadata, argv, environment, or host plaintext files.
    $OutputEncoding = [Text.UTF8Encoding]::new($false)
    $payload | & docker @dockerArgs > $null 2> $null
    $result = $LASTEXITCODE
} finally {
    [Array]::Clear($bytes, 0, $bytes.Length)
    $key = $null; $token = $null; $config = $null; $payload = $null
}
exit $result
