$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$docker = (Get-Command docker.exe -ErrorAction SilentlyContinue).Source
if (!$docker) { $docker = "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe" }
$env:PATH = (Split-Path -Parent $docker) + [IO.Path]::PathSeparator + $env:PATH
& $docker compose --env-file .env.docker stop
if ($LASTEXITCODE -ne 0) { throw 'Failed to stop Docker deployment.' }
Write-Host 'Containers stopped. Database and material volumes are retained.'
