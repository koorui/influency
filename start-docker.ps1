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
& $docker compose --env-file .env.docker config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Invalid Docker Compose configuration.' }
& $docker compose --env-file .env.docker up --build --detach --wait --wait-timeout 240
if ($LASTEXITCODE -ne 0) { throw 'Container deployment failed; inspect Docker Compose logs.' }
& $docker compose --env-file .env.docker exec -T pipeline-worker python -m app.deployment_check
if ($LASTEXITCODE -ne 0) { throw 'Container data, CLI or relay configuration check failed.' }
& $docker compose --env-file .env.docker ps
Write-Host 'Docker deployment is running. Default URL: http://localhost:18080'
