# FastAPI Auth Service

Implementacion FastAPI del microservicio de autenticacion en `auth/`.

## Requisitos
- Python 3.11+
- MySQL 8+

## Configuracion
1. Copia variables de entorno del servicio auth:

```powershell
Copy-Item auth/.env.example auth/.env
```

2. Ajusta credenciales MySQL en `auth/.env`:
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_DB`
- `APP_FORCE_HTTPS` (`true` en produccion detras de TLS)

3. Ejecuta migraciones del auth-service:

```powershell
Push-Location auth
alembic -c alembic.ini upgrade head
Pop-Location
```

## SMTP (verificacion de email)
Para enviar correos reales:
- `APP_MAIL_ENABLED=true`
- Configura `MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_USE_TLS`
- Define `APP_FRONTEND_BASE_URL` para construir el link de confirmacion.

## Ejecutar

```powershell
uvicorn auth.main:app --host 127.0.0.1 --port 8000 --reload
```

## Probar
- Ver `test_auth.http`

Endpoints:
- `POST /api/auth/register`
- `POST /api/auth/verify/email/resend`
- `POST /api/auth/verify/email/confirm`
- `POST /api/auth/login` (`username` acepta username o email)
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/users/me`
- `GET /api/users` (requiere `ROLE_ADMIN` o `ROLE_SECURITY_ADMIN`)
- `PATCH /api/users/{user_id}/role` (requiere `ROLE_ADMIN`)
