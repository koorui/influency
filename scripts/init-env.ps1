$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectRoot '.env'
if (Test-Path -LiteralPath $envPath) { Write-Host '.env 已存在，未覆盖'; exit 0 }
function New-Secret {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLower()
}
$dbSecret = New-Secret
$rootSecret = New-Secret
$sessionSecret = New-Secret
$config = @"
MYSQL_ROOT_PASSWORD=$rootSecret
MYSQL_PASSWORD=$dbSecret
SECRET_KEY=$sessionSecret
DATABASE_URL=mysql+pymysql://impact:$dbSecret@127.0.0.1:13307/impact?charset=utf8mb4
STORAGE_DIR=./storage
ALLOWED_ORIGIN=http://localhost:5173
COOKIE_SECURE=false
EVALUATION_ADAPTER=mock
"@
[IO.File]::WriteAllText($envPath, $config, (New-Object Text.UTF8Encoding $false))
Write-Host '已生成本地环境配置和随机密钥。'
