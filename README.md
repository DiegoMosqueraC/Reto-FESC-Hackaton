# Legacy Escape — Diego Alejandro Mosquera Caicedo y Camilo Andres Ramirez Acevedo

## Descripción

Capa de transición para la Caja de Compensación Familiar que permite modernizar el sistema legacy sin apagarlo. Un gateway REST con adapter y modelo canónico atiende al portal, a Subsidios y a la app móvil, de modo que ninguna aplicación nueva se conecta a la base legacy. El dominio Afiliaciones queda migrado en estado DUAL: las consultas y los retiros pasan por el gateway, el legacy sigue siendo la fuente de verdad y Educación continúa leyendo la base sin cambios.

## Integrantes

- Diego Alejandro Mosquera Caicedo
- Camilo Andres Ramirez Acevedo

## Requisitos

- Docker Engine 24 o superior con Docker Compose v2 (`docker compose`).
- Linux, macOS o Windows con Docker Desktop; en Windows los scripts se ejecutan con Git Bash.
- `bash` y `curl` para los scripts y los ejemplos. Python 3.8+ solo para `./validator`.
- Puertos libres: 8082 (gateway), 8090 (Educación), 8091 (Subsidios) y 8092 (Portal).

## Instalación y ejecución

Desde una copia limpia del repositorio, en este orden:

```bash
cp .env.example .env            # y cambien los tokens y la clave por valores propios
mkdir -p logs
docker compose up -d --build    # levanta legacy-db, gateway y los consumidores
docker compose ps               # todos los servicios deben quedar Up
curl http://localhost:8082/health
```

Para devolver el dominio Afiliaciones a LEGACY (rollback, termina en segundos con código 0):

```bash
./rollback.sh affiliations
```

Para volver todo al estado inicial (borra la base y el estado del gateway): `./reset.sh`.

## Configuración

Todas las variables se definen en `.env` (no se versiona) a partir de `.env.example`:

| Variable | Para qué sirve | Ejemplo |
|---|---|---|
| `POSTGRES_DB` | Nombre de la base legacy | `legacy` |
| `POSTGRES_USER` | Usuario de la base legacy que usan el adapter, Educación y Subsidios | `legacy` |
| `POSTGRES_PASSWORD` | Clave de ese usuario | `cambiar-esta-clave` |
| `LEGACY_DB_HOST` | Host de la base dentro de la red de Docker | `legacy-db` |
| `LEGACY_DB_PORT` | Puerto de PostgreSQL | `5432` |
| `GATEWAY_URL` | URL del gateway que usan el portal y Subsidios | `http://gateway:8082` |
| `PORTAL_TOKEN` | Token Bearer del portal de servicios (lectura y escritura) | `cambiar-portal` |
| `SUBSIDIOS_TOKEN` | Token Bearer de Subsidios para registrar retiros por el gateway | `cambiar-subsidios` |
| `MOBILE_TOKEN` | Token Bearer de la app móvil (solo lectura: un POST responde 403) | `cambiar-mobile` |

## Arquitectura

```text
portal-client / subsidios-app / app móvil -> gateway (API v1 + modelo canónico) -> adapter -> legacy-db <- educacion-app
```

- **legacy-db:** PostgreSQL con las tablas heredadas y `sp_registrar_retiro`; sigue siendo la fuente de verdad.
- **gateway:** API FastAPI en el puerto 8082 (`src/app`). Autentica con un token por consumidor, audita cada petición en `logs/audit.log` con el documento enmascarado, guarda en SQLite (volumen `gateway-data`) las claves de idempotencia, la cola de retiros aceptados durante una caída y el estado de migración.
- **adapter:** `src/adapter/legacy_repository.py`, el único código que conoce tablas, columnas y códigos legacy. Detecta el cambio de esquema (`PERSON_MASTER`) y traduce al modelo canónico.
- **portal-client:** portal de servicios; solo habla HTTP con `GATEWAY_URL` usando `PORTAL_TOKEN`.
- **subsidios-app:** registra retiros por el gateway con `SUBSIDIOS_TOKEN` cuando Afiliaciones está en DUAL; tras el rollback vuelve a `sp_registrar_retiro`.
- **educacion-app:** sin cambios; lee la base y ve los retiros hechos por el gateway.
- **tests:** servicio con perfil `test` que prueba la API en funcionamiento y deja el reporte JUnit en `test-results/`.

## Uso

Todas las rutas `/api/v1` exigen `Authorization: Bearer <token>`. Los ejemplos usan el token del portal:
`TOKEN=$(grep ^PORTAL_TOKEN .env | cut -d= -f2)`.

- `GET /health`: salud del gateway y del legacy, sin token.
  `curl http://localhost:8082/health`
- `GET /api/v1/members/{document}`: afiliado con nombre, estado y empresa.
  `curl -H "Authorization: Bearer $TOKEN" http://localhost:8082/api/v1/members/1019282447`
- `GET /api/v1/members/{document}/beneficiaries`: beneficiarios del afiliado.
  `curl -H "Authorization: Bearer $TOKEN" http://localhost:8082/api/v1/members/1019282447/beneficiaries`
- `GET /api/v1/companies/{id}`: empresa con su número de afiliados activos.
  `curl -H "Authorization: Bearer $TOKEN" http://localhost:8082/api/v1/companies/2014`
- `POST /api/v1/members/{document}/retirements`: retiro idempotente; repetir el mismo `requestId` responde 200 sin duplicar.
  `curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"requestId":"ret-001","date":"2026-10-05","reason":"Retiro voluntario"}' http://localhost:8082/api/v1/members/1019282447/retirements`
- `GET /api/v1/migration/status`: estado de migración por dominio.
  `curl -H "Authorization: Bearer $TOKEN" http://localhost:8082/api/v1/migration/status`

Con la base caída las consultas responden `503` con `LEGACY_UNAVAILABLE` en menos de un segundo y los retiros quedan en cola (`202`). Subsidios sigue recibiendo `POST http://localhost:8091/retiros` y el portal `GET http://localhost:8092/portal/afiliados/{documento}`.

## Pruebas

Las pruebas automatizadas están en `tests/test_api.py` (pytest) y prueban la API en funcionamiento: salud, autenticación sin token y con token inválido, modelo canónico sin nombres legacy, errores 404 con `message` y `error_id`, beneficiarios, empresas, permisos de solo lectura de mobile, validación del cuerpo del retiro, estado de migración y enmascaramiento en la auditoría. Se ejecutan con el entorno levantado:

```bash
docker compose --profile test run --rm tests
```

El comando termina con código distinto de 0 si alguna prueba falla y deja el reporte JUnit en `test-results/report.xml`. También se puede usar `./validator check` y `./validator entregables`.

## Documentación

- [Arquitectura](docs/architecture.md)
- [Mapa de dependencias](docs/dependency-map.md)
- [Plan de migración](docs/migration-plan.md)
- [Contrato OpenAPI v1](openapi.yaml)
- [Uso de inteligencia artificial](AI_USAGE.md)

## Qué resolvimos

Construimos el gateway con adapter y modelo canónico, y el portal funciona sin conocer tablas ni códigos. Los retiros se registran por el servicio nuevo y quedan en el legacy, visibles para Educación. Resolvimos la idempotencia con el `requestId` guardado en un almacén propio (incidente 2021), la caída de la base con respuestas 503 rápidas y una cola persistente que aplica cada retiro una sola vez (incidente 2023), y el cambio de esquema detectando `PERSON_MASTER` en el adapter. La auditoría enmascara documentos (incidente 2025) y el rollback devuelve Afiliaciones a LEGACY en segundos.

## Limitaciones y pendientes

El estado de migración y la cola viven en SQLite dentro de un solo contenedor del gateway, así que no escala a varias réplicas sin una base compartida. Falta migrar los dominios Retiros, Empresas y Aportes, y comparar automáticamente las respuestas del gateway contra el legacy para medir el criterio de avance a MODERN.
