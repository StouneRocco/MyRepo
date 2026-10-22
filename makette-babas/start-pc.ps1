param(
    [switch]$Projector,
    [int]$CameraIndex = 0,
    [int]$ProjectorX = 1920,
    [int]$ProjectorY = 0
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not $env:MONGO_DB) { $env:MONGO_DB = 'calibration_app_pc' }
$tlsDirectory = Join-Path $PSScriptRoot 'backend/.tls'
$tlsCertificate = Join-Path $tlsDirectory 'server-cert.pem'
$tlsKey = Join-Path $tlsDirectory 'server-key.pem'
if (-not $env:TLS_CERT_FILE -and (Test-Path -LiteralPath $tlsCertificate) -and (Test-Path -LiteralPath $tlsKey)) {
    $env:TLS_CERT_FILE = $tlsCertificate
    $env:TLS_KEY_FILE = $tlsKey
    $env:TLS_CA_FILE = Join-Path $tlsDirectory 'maquette-ca.crt'
    $tlsConfig = Get-Content -LiteralPath (Join-Path $tlsDirectory 'config.json') -Raw | ConvertFrom-Json
    $env:TLS_PUBLIC_HOST = $tlsConfig.hostAddress
}
$python = Join-Path $PSScriptRoot 'backend/.venv/Scripts/python.exe'
if (-not (Test-Path $python)) { throw 'Installe les dépendances indiquées dans README.md avant le lancement.' }
$ErrorActionPreference = 'Continue'
& $python -c 'from pymongo import MongoClient; MongoClient(serverSelectionTimeoutMS=2000).admin.command(chr(112)+chr(105)+chr(110)+chr(103))' 2>$null
$mongoAvailable = $LASTEXITCODE -eq 0
$ErrorActionPreference = 'Stop'
if (-not $mongoAvailable) {
    docker compose up -d mongo
    if ($LASTEXITCODE -ne 0) { throw 'MongoDB ne démarre pas. Vérifie Docker Desktop et le port 27017.' }
}
if (-not (Test-Path 'frontend/dist/index.html')) {
    Push-Location frontend
    try { npm.cmd run build; if ($LASTEXITCODE -ne 0) { throw 'La construction du frontend a échoué.' } }
    finally { Pop-Location }
}
if ($Projector) {
    $env:CAMERA_INDEX = "$CameraIndex"
    $env:PROJECTOR_X = "$ProjectorX"
    $env:PROJECTOR_Y = "$ProjectorY"
    Start-Process -FilePath $python -ArgumentList 'projector-pi/color_receiver.py' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
}
if ($env:TLS_CERT_FILE) {
    Write-Host "Application : https://$($env:TLS_PUBLIC_HOST):5000 (Ctrl+C pour arrêter)"
    Write-Host "Installation du certificat sur tablette : http://$($env:TLS_PUBLIC_HOST):5080/"
} else { Write-Host 'Application : http://localhost:5000 (Ctrl+C pour arrêter le serveur web)' }
& $python backend/app.py
