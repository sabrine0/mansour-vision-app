$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$requiredSecrets = @(
    "infra/secrets/postgres_password",
    "infra/secrets/redis_password"
)

foreach ($path in $requiredSecrets) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing deployment secret: $path. Run make secrets or follow infra/secrets/README.md."
    }
    $value = (Get-Content -Raw -LiteralPath $path).Trim()
    if ($value.Length -lt 32) {
        throw "Deployment secret is too short: $path"
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is not installed or not on PATH."
}

docker compose -f infra/compose/docker-compose.yml config --quiet
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose configuration is invalid."
}

if ($env:ENVIRONMENT -eq "production") {
    if (-not $env:MEDIA_PUBLIC_HOST -or $env:MEDIA_PUBLIC_HOST -eq "127.0.0.1") {
        throw "MEDIA_PUBLIC_HOST must be browser-reachable in production."
    }
    if (-not $env:TLS_CERTIFICATE_PATH -or -not $env:TLS_PRIVATE_KEY_PATH) {
        throw "TLS_CERTIFICATE_PATH and TLS_PRIVATE_KEY_PATH are required for public production."
    }
}

Write-Output "Deployment configuration and secret checks passed."
