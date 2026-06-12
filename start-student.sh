#!/usr/bin/env sh
set -eu

ENV_FILE=".env.student"
COMPOSE_FILE="docker-compose.student.yml"

if [ ! -f "$ENV_FILE" ]; then
  echo "Arquivo $ENV_FILE nao encontrado."
  echo "Copie .env.student.example para .env.student e preencha os valores."
  exit 1
fi

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "Arquivo $COMPOSE_FILE nao encontrado."
  exit 1
fi

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up --build
