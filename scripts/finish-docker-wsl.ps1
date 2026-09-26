$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$record = Join-Path $projectRoot '.local-runtime/wsl-setup.pid'
if (Test-Path -LiteralPath $record) {
    $originalId = [int](Get-Content -LiteralPath $record -Raw)
    $original = Get-CimInstance Win32_Process -Filter "ProcessId=$originalId"
    if ($original -and $original.Name -eq 'powershell.exe' -and $original.CommandLine.Contains('enable-docker-wsl.ps1')) {
        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$originalId"
        foreach ($child in $children) {
            if ($child.Name -eq 'wsl.exe' -and $child.CommandLine.Contains('--install')) {
                Stop-Process -Id $child.ProcessId -Force
            }
        }
        Wait-Process -Id $originalId -Timeout 15 -ErrorAction SilentlyContinue
    }
}
& (Join-Path $PSScriptRoot 'enable-docker-wsl.ps1')
