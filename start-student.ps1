$envFile = ".env.student"
$composeFile = "docker-compose.student.yml"

if (-not (Test-Path $envFile)) {
    Write-Host "Arquivo $envFile nao encontrado."
    Write-Host "Copie .env.student.example para .env.student e preencha os valores."
    exit 1
}

if (-not (Test-Path $composeFile)) {
    Write-Host "Arquivo $composeFile nao encontrado."
    exit 1
}

docker compose --env-file $envFile -f $composeFile up --build
