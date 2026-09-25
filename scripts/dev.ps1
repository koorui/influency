$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath (Join-Path $projectRoot '.env'))) { throw '请先运行 scripts/init-env.ps1' }
if (!(Test-Path -LiteralPath $pythonPath)) { throw '请先安装 Python 虚拟环境和依赖，参见 README' }
Push-Location $projectRoot
try {
    docker compose up -d mysql
    if ($LASTEXITCODE -ne 0) { throw 'MySQL 启动失败' }
    Push-Location (Join-Path $projectRoot 'backend')
    try {
        & $pythonPath -m app.wait_db
        if ($LASTEXITCODE -ne 0) { throw 'MySQL 未就绪' }
        & $pythonPath -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw '数据库迁移失败' }
    } finally { Pop-Location }
    $apiProcess = Start-Process -FilePath $pythonPath -ArgumentList '-m uvicorn app.main:app --host 127.0.0.1 --port 8000' -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -PassThru
    $workerProcess = Start-Process -FilePath $pythonPath -ArgumentList '-m app.worker' -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -PassThru
    $pipelineProcess = Start-Process -FilePath $pythonPath -ArgumentList '-m app.pipeline_worker' -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -PassThru
    try {
        Write-Host '打开 http://localhost:5173；按 Ctrl+C 停止本次启动的前后端。'
        Push-Location (Join-Path $projectRoot 'frontend')
        try { npm.cmd run dev -- --host localhost } finally { Pop-Location }
    } finally {
        foreach ($serviceProcess in @($apiProcess, $workerProcess, $pipelineProcess)) {
            if (!$serviceProcess.HasExited) {
                # Include the virtualenv launcher's child process on Windows.
                taskkill.exe /PID $serviceProcess.Id /T /F | Out-Null
            }
        }
    }
} finally { Pop-Location }
