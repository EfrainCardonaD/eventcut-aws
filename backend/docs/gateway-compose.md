# Gateway + Docker Compose

Esta guia describe como funciona el API gateway (Traefik) en Docker Compose y como validar el arranque completo del stack.

## Arquitectura actual

- Entrada unica publica: `http://localhost:8080`.
- Gateway: `traefik`.
- Servicios backend:
  - `auth-service` en red Docker (`http://auth-service:8000`).
  - `events-service` en red Docker (`http://events-service:8001`).
- Bloqueo de rutas internas via `blocked-responder`.
- Tunel opcional via `ngrok` apuntando al gateway.

## Fuente de configuracion del gateway

- Compose: `docker-compose.yml`.
- Routing dinamico: `infra/traefik/dynamic.yml`.

Traefik usa **file provider** (no docker provider) para definir routers, middlewares y servicios. Esto evita dependencias de descubrimiento por labels y hace el routing determinista.

## Mapa de rutas

| Ruta publica | Destino interno | Notas |
|---|---|---|
| `/api/health` | `auth-service:8000/api/health` | Health de auth |
| `/api/events/health` | `events-service:8001/api/health` | Reescritura con middleware |
| `/api/auth/*`, `/api/users/*`, `/api/verify/*`, `/api/password-recovery/*` | `auth-service:8000` | Endpoints de auth |
| `/api/v1/*` | `events-service:8001` | Endpoints de events |
| `/api/internal/*` | `blocked-responder:80` | Bloqueado externamente (403) |

## Flujo de arranque en Compose

Orden esperado en `docker-compose.yml`:

1. Bases de datos (`auth-mysql`, `events-mysql`) -> `healthy`.
2. Migraciones (`auth-migrate`, `events-migrate`) -> `Exited (0)`.
3. APIs (`auth-service`, `events-service`) -> `Up`.
4. Gateway (`traefik`) y `ngrok` -> `Up`.

## Arranque rapido

```powershell
docker compose up -d --build
docker compose ps
```

## Modo local IDE (gateway aislado)

Cuando `auth-service` y `events-service` corren fuera de Docker (por ejemplo desde PyCharm), usa el gateway opcional `traefik-local`:

```powershell
docker compose --profile local-gateway up -d traefik-local
```

En este modo:
- Traefik usa `infra/traefik/dynamic.local.yml`.
- Expone `http://localhost:8080`.
- Rutea a `host.docker.internal:8000` y `host.docker.internal:8001`.

## Validacion operativa

```powershell
curl.exe -i http://localhost:8080/api/health
curl.exe -i http://localhost:8080/api/events/health
curl.exe -i http://localhost:8080/api/internal/ping
```

Resultado esperado:

- `/api/health` -> `200`
- `/api/events/health` -> `200`
- `/api/internal/ping` -> `403`

## Logs utiles para debug

```powershell
docker compose logs --no-color --tail=120 traefik
docker compose logs --no-color --tail=120 auth-service
docker compose logs --no-color --tail=120 events-service
```

## Troubleshooting rapido

### 1) Todo responde 404 en `:8080`

- Verificar que `traefik` este `Up`.
- Verificar carga del archivo `infra/traefik/dynamic.yml`.
- Revisar logs de `traefik` para confirmar routers activos (`auth@file`, `events@file`, `events-health@file`).

### 2) Health de events falla

- Verificar regla `Path(`/api/events/health`)` en `infra/traefik/dynamic.yml`.
- Verificar middleware `events-health-rewrite` con `replacePath: /api/health`.
- Confirmar que `events-service` responda internamente en `/api/health`.

### 3) Error de validacion remota Auth <-> Events

- Confirmar `AUTH_SERVICE_BASE_URL=http://auth-service:8000` en `events_service/.env`.
- Confirmar `APP_GATEWAY_SECRET` consistente entre servicios.
- Confirmar endpoint interno de auth: `GET /api/internal/auth/me`.

