param([Parameter(Mandatory=$true)][string]$IpAddress)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$parsedAddress = [System.Net.IPAddress]::Parse($IpAddress)
if ($parsedAddress.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { throw 'Adresse IPv4 du PC requise.' }
$tlsDirectory = Join-Path $PSScriptRoot 'backend/.tls'
$caDirectory = Join-Path $tlsDirectory 'ca'
New-Item -ItemType Directory -Force -Path $caDirectory | Out-Null
$mkcert = Join-Path $tlsDirectory 'mkcert.exe'
if (-not (Test-Path -LiteralPath $mkcert)) {
    # Binaire officiel ; aucune modification des magasins de certificats Windows.
    Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-windows-amd64.exe' -OutFile $mkcert
}
$previousCaRoot = $env:CAROOT
try {
    $env:CAROOT = $caDirectory
    & $mkcert -cert-file (Join-Path $tlsDirectory 'server-cert.pem') -key-file (Join-Path $tlsDirectory 'server-key.pem') $IpAddress localhost 127.0.0.1 ::1
    if ($LASTEXITCODE -ne 0) { throw 'La génération du certificat a échoué.' }
    Copy-Item -LiteralPath (Join-Path $caDirectory 'rootCA.pem') -Destination (Join-Path $tlsDirectory 'maquette-ca.crt')
    @{hostAddress=$IpAddress} | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $tlsDirectory 'config.json')
} finally { $env:CAROOT = $previousCaRoot }
Write-Host "HTTPS prêt : https://${IpAddress}:5000"
Write-Host 'Lance start-pc.ps1. Télécharge et installe uniquement maquette-ca.crt sur la tablette.'
Write-Host "Certificat public : http://${IpAddress}:5080/maquette-ca.crt"
