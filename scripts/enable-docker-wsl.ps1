$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$logFolder = Join-Path $projectRoot '.local-runtime/logs'
New-Item -ItemType Directory -Path $logFolder -Force | Out-Null
$stateFile = Join-Path $logFolder 'wsl-setup-status.json'
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (!$isAdmin) { throw 'Run this script as Administrator to enable Windows virtualization features.' }
Start-Transcript -Path (Join-Path $logFolder 'wsl-setup.log') -Append
$featuresEnabled = $false
try {
    foreach ($feature in @('VirtualMachinePlatform', 'Microsoft-Windows-Subsystem-Linux')) {
        & dism.exe /online /enable-feature "/featurename:$feature" /all /norestart
        if ($LASTEXITCODE -notin @(0,3010)) { throw "Windows feature installation failed: $feature (exit $LASTEXITCODE)" }
    }
    $featuresEnabled = $true
    $package = Join-Path $projectRoot '.local-runtime/installers/wsl-x64.msi'
    if (Test-Path -LiteralPath $package) {
        $msiLog = Join-Path $logFolder 'wsl-msi.log'
        $msiArgs = @('/i', ('"{0}"' -f $package), '/qn', '/norestart', '/L*v', ('"{0}"' -f $msiLog))
        $installer = Start-Process -FilePath 'msiexec.exe' -ArgumentList $msiArgs -WindowStyle Hidden -Wait -PassThru
        $wslCode = $installer.ExitCode
    } else {
        & wsl.exe --install --no-distribution --web-download
        $wslCode = $LASTEXITCODE
    }
    if ($wslCode -notin @(0,3010)) { throw "WSL installation failed (exit $wslCode)" }
    $restartRequired = ($wslCode -eq 3010) -or (Test-Path -LiteralPath 'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending')
    @{ featuresEnabled=$true; wslInstallExitCode=$wslCode; restartRequired=$restartRequired; automaticallyRestarted=$false } |
        ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding UTF8
    if ($restartRequired) { Write-Host 'Save your work and restart Windows before starting Docker.' }
    else { Write-Host 'WSL installed. Start Docker Desktop.' }
} catch {
    @{ featuresEnabled=$featuresEnabled; restartRequired=$featuresEnabled; error=$_.Exception.Message; automaticallyRestarted=$false } |
        ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding UTF8
    throw
} finally {
    Stop-Transcript
}
