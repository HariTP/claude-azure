param([switch]$Purge)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Common.ps1')
$profilePath = Get-ProfilePath
$task = Get-TaskName
Stop-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction SilentlyContinue
& docker stop --time 20 claude-azure-local 2>$null | Out-Null
Remove-Item -LiteralPath (Join-Path $profilePath 'bin\claude-azure.cmd') -ErrorAction SilentlyContinue
if ($Purge) {
    # Remove the junction itself before recursively removing private profile files.
    $link = Join-Path $profilePath 'claude\projects'
    if (Test-Path $link) { [IO.Directory]::Delete($link) }
    Remove-Item -LiteralPath $profilePath -Recurse -Force
}
Write-Host 'Gateway startup removed. Normal Claude and original chat directories were not removed.'
