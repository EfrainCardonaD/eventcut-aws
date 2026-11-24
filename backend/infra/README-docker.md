# Docker deployment (Traefik + Auth + Events + MySQL + ngrok)

## Objetivo
- Exponer solo `http://localhost:8080`.
- Todo el trafico externo entra por Traefik.
- `auth-service`, `events-service`, `auth-mysql` y `events-mysql` quedan sin puertos publicados al host.
- `events-service` consume endpoints internos de `auth-service` por red Docker usando `http://auth-service:8000`.
- `/api/internal/*` se bloquea publicamente en el API gateway.

## Documentacion relacionada
- Guia operativa completa: [`docs/gateway-compose.md`](../docs/gateway-compose.md)
- Configuracion dinamica de Traefik: [`infra/traefik/dynamic.yml`](./traefik/dynamic.yml)

## Estructura esperada
- `auth/.env` y `events_service/.env` para configuracion por microservicio.
- `auth/alembic.ini` + `auth/alembic/` para migraciones del auth-service.
- `events_service/alembic.ini` + `events_service/alembic/` para migraciones del events-service.

## Convencion de health
- Auth: `GET /api/health`
- Events: `GET /api/events/health` (Traefik reescribe internamente a `/api/health` del service)

## Gateway (Traefik)
- `traefik` usa **file provider** con `infra/traefik/dynamic.yml`.
- El routing no depende de labels Docker para discovery.
- Reglas clave:
  - `auth`: `/api/auth`, `/api/users`, `/api/verify`, `/api/password-recovery`, `/api/health`
  - `events`: `/api/v1`
  - `events-health`: `/api/events/health` -> rewrite a `/api/health`
  - `block-internal`: `/api/internal/*` -> `blocked-responder` (403)

## Gateway local aislado (IDE)
- Servicio opcional: `traefik-local` (contenedor `eventcut-traefik-local-ide`).
- Configuracion: `infra/traefik/dynamic.local.yml`.
- Puerto host: `http://localhost:8080`.
- Uso: enruta a servicios levantados en tu host/IDE (`host.docker.internal:8000/8001`).

```powershell
docker compose --profile local-gateway up -d traefik-local
docker compose --profile local-gateway logs --no-color --tail=120 traefik-local
```

## Levantar stack
1) Copia plantillas de entorno:

```powershell
Copy-Item auth/.env.example auth/.env
Copy-Item events_service/.env.example events_service/.env
Copy-Item infra/.env.example .env
```

2) Ajusta secretos en `.env`, `auth/.env` y `events_service/.env`.

3) Levanta contenedores:

```powershell
docker compose up -d --build
docker compose ps
```

## Migraciones Alembic al iniciar
- `auth-migrate` ejecuta `alembic -c alembic.ini upgrade head` en `/app/auth`.
- `events-migrate` ejecuta `alembic -c alembic.ini upgrade head` en `/app/events_service`.
- Los servicios API esperan a que cada migrate finalice con exito.

## Ver logs
```powershell
docker compose logs --no-color --tail=120 traefik
docker compose logs --no-color --tail=120 auth-service
docker compose logs --no-color --tail=120 events-service
docker compose logs -f ngrok
```

## Endpoints via gateway
- `http://localhost:8080/api/health`
- `http://localhost:8080/api/events/health`
- `http://localhost:8080/api/v1/categories`
- `http://localhost:8080/api/v1/events?month=2026-05&sort_by=score&limit=10`

## Smoke check rapido
```powershell
curl.exe -i http://localhost:8080/api/health
curl.exe -i http://localhost:8080/api/events/health
curl.exe -i http://localhost:8080/api/internal/ping
```

Esperado:
- `200` para auth health.
- `200` para events health.
- `403` para rutas internas bloqueadas.

## ngrok (tunel unico)
- El servicio `ngrok` abre un solo tunel al gateway (`traefik:8080`).
- Revisa la URL publica en logs de `ngrok`.

## Seguridad de red
- Redes internas con `internal: true`: `auth_net_internal`, `events_net_internal`.
- Solo Traefik publica puerto (`8080`).
- MySQL y servicios API no publican puertos al host.

