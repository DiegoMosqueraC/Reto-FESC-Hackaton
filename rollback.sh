#!/usr/bin/env bash
# Devuelve un dominio a LEGACY. Uso: ./rollback.sh affiliations
# Con Afiliaciones en LEGACY, Subsidios vuelve a registrar retiros directo con
# sp_registrar_retiro; el gateway sigue sirviendo consultas.
set -euo pipefail
cd "$(dirname "$0")"

DOMAIN="${1:-affiliations}"
SET_LEGACY=(python -m app.migration set "$DOMAIN" LEGACY)

# Si el gateway está apagado, se usa un contenedor temporal con el mismo volumen de estado.
if ! docker compose exec -T gateway "${SET_LEGACY[@]}"; then
    docker compose run --rm --no-deps -T gateway "${SET_LEGACY[@]}"
fi

echo "Rollback listo: dominio $DOMAIN en LEGACY"
