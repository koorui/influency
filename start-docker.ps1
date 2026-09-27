$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$docker = (Get-Command docker.exe -ErrorAction SilentlyContinue).Source
if (!$docker) {
    foreach ($candidate in @(
        "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe",
        'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
    )) { if (Test-Path -LiteralPath $candidate) { $docker = $candidate; break } }
}
if (!$docker) { throw 'Docker is not installed.' }
$env:PATH = (Split-Path -Parent $docker) + [IO.Path]::PathSeparator + $env:PATH
if (!(Test-Path -LiteralPath '.env.docker')) { throw 'Missing .env.docker; prepare deployment data first.' }
& $docker info --format '{{.OSType}}'
if ($LASTEXITCODE -ne 0) { throw 'Docker engine is not ready. Start Docker Desktop; complete WSL setup and restart Windows if required.' }
$composeArgs = @('compose','--env-file','.env.docker','-f','compose.yaml')
$releasePointer = Join-Path $PSScriptRoot '.local-runtime/active-release.txt'
if (Test-Path -LiteralPath $releasePointer) {
    $releaseConfig = (Get-Content -LiteralPath $releasePointer -Raw).Trim()
    if (!(Test-Path -LiteralPath $releaseConfig)) { throw 'Selected release is missing; restore it before starting.' }
    $composeArgs += @('-f',$releaseConfig)
}
& $docker @composeArgs config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Invalid Docker Compose configuration.' }
& $docker @composeArgs up --no-build --detach --wait --wait-timeout 240
if ($LASTEXITCODE -ne 0) { throw 'Container deployment failed; inspect Docker Compose logs.' }
& $docker @composeArgs exec -T pipeline-worker python -m app.deployment_check
if ($LASTEXITCODE -ne 0) { throw 'Container data, CLI or relay configuration check failed.' }
& $docker @composeArgs ps
Write-Host 'Docker deployment is running. Default URL: http://localhost:18080'
