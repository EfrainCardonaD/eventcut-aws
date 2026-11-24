# Events Service (CEMS)

Microservicio de eventos con schema MySQL separado, lectura publica y escritura protegida por JWT + gateway interno hacia `auth-service`.

## Tabla de contenido
- [1. Vision general](#1-vision-general)
- [2. Arquitectura](#2-arquitectura)
- [3. Estructura del proyecto](#3-estructura-del-proyecto)
- [4. Requisitos](#4-requisitos)
- [5. Configuracion](#5-configuracion)
- [6. Levantar en local](#6-levantar-en-local)
- [7. API principal](#7-api-principal)
- [8. Seguridad y permisos](#8-seguridad-y-permisos)
- [9. Pruebas](#9-pruebas)
- [10. Despliegue](#10-despliegue)
- [11. Troubleshooting](#11-troubleshooting)
- [12. Documentacion complementaria](#12-documentacion-complementaria)

## 1. Vision general
Este servicio implementa el dominio de eventos:
- Catalogo de categorias.
- Publicacion y actualizacion de eventos.
- Favoritos por usuario.
- Calculo de `score` por agregacion (no persistido).

Reglas clave:
- Los eventos son publicos para lectura.
- Solo el owner o un admin puede editar/eliminar.
- Admin valido: `ROLE_ADMIN` y `ROLE_SECURITY_ADMIN`.
- El borrado de eventos es logico (`is_active=0`), no fisico.

## 2. Arquitectura
Integracion de seguridad:
1. Validacion local de JWT (`HS256`) con secretos compartidos.
2. Validacion remota opcional (`AUTH_REMOTE_VALIDATION_ENABLED=true`) contra `auth-service`.
3. Llamada interna protegida por header `X-Gateway-Secret`.

Endpoint interno esperado en auth-service:
- `GET /api/internal/auth/me`

## 3. Estructura del proyecto

```text
events_service/
  app/
    api/
      routes/
    core/
    db/
    gateway/
    models/
    schemas/
    security/
    services/
  alembic/
    versions/
  docs/
  tests/
  .env.example
  alembic.ini
  main.py
  requirements.txt
```

## 4. Requisitos
- Python 3.11+
- MySQL 8+
- `auth-service` corriendo

## 5. Configuracion
1) Copiar entorno:

```powershell
Copy-Item "events_service/.env.example" "events_service/.env"
```

2) Ajustar valores criticos en `events_service/.env`:
- `JWT_SECRET_KEY`
- `JWT_ISSUER`
- `AUTH_SERVICE_BASE_URL`
- `APP_GATEWAY_SECRET`
- `MYSQL_DB`, `MYSQL_USER`, `MYSQL_PASSWORD`

## 6. Levantar en local
1) Crear schema (si no existe):

```powershell
python -c "import pymysql; c=pymysql.connect(host='localhost',port=3306,user='root',password='sasa',autocommit=True); cur=c.cursor(); cur.execute('CREATE DATABASE IF NOT EXISTS eventcut_events_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'); cur.close(); c.close()"
```

2) Migrar:

```powershell
alembic -c "events_service/alembic.ini" upgrade head
```

3) Seed inicial de categorias:

```powershell
python -c "from events_service.app.db.session import SessionLocal; from events_service.app.db.init_db import seed_categories; db=SessionLocal(); print(seed_categories(db)); db.close()"
```

4) Ejecutar servicio:

```powershell
uvicorn events_service.main:app --host 127.0.0.1 --port 8001 --reload
```

## 7. API principal
Rutas principales:
- `GET /api/health`
- `GET /api/v1/categories`
- `GET /api/v1/events`
- `GET /api/v1/events/{event_id}`
- `POST /api/v1/events` (auth)
- `PATCH /api/v1/events/{event_id}` (auth + permisos)
- `DELETE /api/v1/events/{event_id}` (auth + permisos)
- `POST /api/v1/events/{event_id}/favorite` (auth)
- `GET /api/v1/events/my/favorites` (auth)

Contrato de respuesta (excepto `DELETE` con `204 No Content`):

```json
{
  "success": true,
  "message": "...",
  "data": {}
}
```

Errores:

```json
{
  "success": false,
  "message": "...",
  "data": {
    "code": "...",
    "details": {},
    "trace_id": "..."
  }
}
```

Filtros en `GET /api/v1/events`:
- `category_id`
- `from`, `to`
- `month` (`YYYY-MM`)
- `week_start` (`YYYY-MM-DD`)
- `sort_by` (`start_datetime` | `score`)
- `limit`, `offset`

## 8. Seguridad y permisos
Permisos de escritura:
- Crear: cualquier usuario autenticado.
- Editar/Borrar: owner o rol admin.
- Favorito: cualquier usuario autenticado.

Roles admin aceptados:
- `ROLE_ADMIN`
- `ROLE_SECURITY_ADMIN`

## 9. Pruebas
Ejecutar tests del servicio:

```powershell
python -m pytest "events_service/tests" -q
```

Ejecutar pruebas del repo completo (auth + events):

```powershell
python -m pytest "tests" "events_service/tests" -q
```

Pruebas manuales HTTP (JetBrains/REST Client):
- `events_service/test_events.http`

## 10. Despliegue
Checklist minimo de CI/CD:
1. Instalar dependencias.
2. Ejecutar tests.
3. Aplicar migraciones: `alembic upgrade head`.
4. Desplegar app.

Comando de produccion recomendado (sin `--reload`):

```powershell
uvicorn events_service.main:app --host 0.0.0.0 --port 8001
```

## 11. Troubleshooting
- `401 Token invalido`: revisar `JWT_SECRET_KEY`/`JWT_ISSUER` y expiracion.
- `503 Auth-service no disponible`: en modo fail-closed se bloquean endpoints protegidos; verificar `AUTH_SERVICE_BASE_URL` y `APP_GATEWAY_SECRET`.
- `500` en queries: confirmar migraciones y schema `MYSQL_DB`.
- Errores por configuracion: revisar `events_service/.env`.
- Para soporte, usar `trace_id` del body de error o header `X-Trace-Id`.

## 12. Documentacion complementaria
- Arquitectura: `events_service/docs/ARCHITECTURE.md`
- API detallada: `events_service/docs/API.md`
- Plan integracion frontend: `events_service/docs/FRONTEND_INTEGRATION_PLAN.md`
- Seguridad: `events_service/docs/SECURITY.md`
- Operacion/despliegue: `events_service/docs/OPERATIONS.md`
