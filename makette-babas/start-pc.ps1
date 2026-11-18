param(
    [switch]$Projector,
    [switch]$Update,
    [int]$CameraIndex = 0,
    [int]$ProjectorX = 1920,
    [int]$ProjectorY = 0
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not $env:MONGO_DB) { $env:MONGO_DB = 'calibration_app_pc' }
$python = Join-Path $PSScriptRoot 'backend/.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Installe les dépendances indiquées dans README.md avant le lancement.' }
if (Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Le port 5000 est déjà utilisé. Arrête le serveur actuel avec Ctrl+C avant de relancer.'
}
Write-Host "Dossier lancé : $PSScriptRoot"
& git rev-parse --short HEAD
function Test-MongoReady {
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $python backend/healthcheck.py 2>$null
        return $LASTEXITCODE -eq 0
    } finally { $ErrorActionPreference = $previousPreference }
}
if (-not (Test-MongoReady)) {
    if ($env:MONGO_URI -and $env:MONGO_URI -ne 'mongodb://127.0.0.1:27017') {
        throw 'Le serveur défini dans MONGO_URI est indisponible.'
    }
    if (Get-NetTCPConnection -LocalPort 27017 -State Listen -ErrorAction SilentlyContinue) {
        throw 'Le port 27017 est déjà occupé mais MongoDB ne répond pas au contrôle. Vérifie le service Windows et MONGO_URI ; Docker ne sera pas lancé sur ce port.'
    }
    docker compose up -d mongo
    if ($LASTEXITCODE -ne 0) { throw 'MongoDB ne démarre pas. Vérifie Docker Desktop et le port 27017.' }
    $mongoDeadline = (Get-Date).AddSeconds(30)
    while (-not (Test-MongoReady)) {
        if ((Get-Date) -gt $mongoDeadline) { throw 'MongoDB reste indisponible après 30 secondes.' }
        Start-Sleep -Milliseconds 500
    }
} else { Write-Host 'MongoDB existant disponible : réutilisation sans lancer Docker.' }
Push-Location frontend
try {
    if ($Update -or -not (Test-Path -LiteralPath node_modules)) {
        npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'Installation npm échouée.' }
    }
    # Toujours reconstruire pour ne jamais servir une ancienne interface après un pull.
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'La construction du frontend a échoué.' }
} finally { Pop-Location }
$projectorProcess = $null
try {
    if ($Projector) {
        if (Get-NetTCPConnection -LocalPort 5001 -State Listen -ErrorAction SilentlyContinue) {
            Write-Host 'Un récepteur utilise déjà le port 5001 ; il est conservé. Redémarre-le séparément après une mise à jour.'
        } else {
            $env:CAMERA_INDEX = "$CameraIndex"
            $env:PROJECTOR_X = "$ProjectorX"
            $env:PROJECTOR_Y = "$ProjectorY"
            $logDirectory = Join-Path $PSScriptRoot '.runtime'
            New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
            $projectorProcess = Start-Process -FilePath $python -ArgumentList '-u','projector-pi/color_receiver.py' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDirectory 'projector.log') -RedirectStandardError (Join-Path $logDirectory 'projector-error.log')
            Write-Host "Journaux du projecteur : $logDirectory"
        }
    }
    & $python -u backend/app.py
    if ($LASTEXITCODE -ne 0) { throw 'Le serveur web a terminé en erreur. Consulte le message ci-dessus.' }
} finally {
    if ($projectorProcess -and -not $projectorProcess.HasExited) {
        # Seuls le processus créé ici et ses enfants sont arrêtés.
        Get-CimInstance Win32_Process -Filter "ParentProcessId = $($projectorProcess.Id)" | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
        Stop-Process -Id $projectorProcess.Id -ErrorAction SilentlyContinue
    }
}
