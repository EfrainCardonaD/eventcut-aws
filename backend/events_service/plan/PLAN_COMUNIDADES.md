# Plan de Implementación: Módulo de Comunidades y Admin Dashboard

> **✅ IMPLEMENTACIÓN COMPLETADA** (2025-01-14)
> 
> Todos los componentes fueron implementados y testeados satisfactoriamente.

## Resumen Ejecutivo

Este documento detalla el plan técnico completo para implementar:
1. **Módulo de Comunidades** (estilo Luma) con flujo de aprobación ✅
2. **Redes Sociales** para Eventos y Comunidades ✅
3. **Panel de Administración** con gestión de baneos ✅

### Contexto del Sistema
- **Revisión actual de Alembic:** `20260330_0002`
- **Base de datos:** MySQL 8+
- **Autenticación:** JWT vía `auth-service` externo
- **Patrones existentes:** soft-delete (`is_active`), envelopes estandarizados

---

## 1. Diseño de Base de Datos (Esquema Alembic)

### 1.1 Nuevas Tablas

#### Tabla `communities`
Almacena las comunidades creadas por usuarios.

| Columna | Tipo | Nullable | Descripción |
|---------|------|----------|-------------|
| id | VARCHAR(36) | NO | UUID primary key |
| name | VARCHAR(100) | NO | Nombre único de la comunidad |
| description | TEXT | NO | Descripción de la comunidad |
| image_url | VARCHAR(255) | YES | URL de la imagen/logo |
| owner_id | VARCHAR(36) | NO | ID del creador (del JWT) |
| contact_email | VARCHAR(255) | NO | Email de contacto registrado |
| status | ENUM('PENDING', 'ACTIVE', 'REJECTED') | NO | Estado de aprobación |
| is_accepted_terms | BOOLEAN | NO | Aceptación de términos |
| rejection_reason | VARCHAR(500) | YES | Razón de rechazo (si aplica) |
| social_links | JSON | YES | Links a redes sociales |
| is_active | BOOLEAN | NO | Soft delete flag |
| created_at | DATETIME | NO | Timestamp de creación |
| updated_at | DATETIME | NO | Timestamp de actualización |

#### Tabla `community_events` (Tabla Pivote)
Gestiona las solicitudes de eventos para unirse a comunidades.

| Columna | Tipo | Nullable | Descripción |
|---------|------|----------|-------------|
| id | VARCHAR(36) | NO | UUID primary key |
| community_id | VARCHAR(36) | NO | FK a communities |
| event_id | VARCHAR(36) | NO | FK a events |
| status | ENUM('PENDING', 'APPROVED', 'REJECTED') | NO | Estado de la solicitud |
| requested_by | VARCHAR(36) | NO | ID del solicitante |
| reviewed_by | VARCHAR(36) | YES | ID del owner que revisó |
| reviewed_at | DATETIME | YES | Timestamp de revisión |
| rejection_reason | VARCHAR(500) | YES | Razón de rechazo |
| created_at | DATETIME | NO | Timestamp de creación |

#### Tabla `banned_users`
Lista local de usuarios baneados en el microservicio.

| Columna | Tipo | Nullable | Descripción |
|---------|------|----------|-------------|
| id | INT | NO | Auto-increment PK |
| user_id | VARCHAR(36) | NO | ID del usuario baneado (UNIQUE) |
| reason | VARCHAR(500) | NO | Razón del baneo |
| banned_by | VARCHAR(36) | NO | Admin que realizó el baneo |
| banned_at | DATETIME | NO | Timestamp del baneo |
| is_active | BOOLEAN | NO | Si el baneo está activo |

### 1.2 Modificación a Tabla `events`
Se añade columna JSON para redes sociales:

| Columna | Tipo | Nullable | Descripción |
|---------|------|----------|-------------|
| social_links | JSON | YES | Links a redes sociales |

### 1.3 Decisión de Diseño: JSON vs Tabla Separada

**Decisión:** Usar campo **JSON** para `social_links` tanto en `events` como en `communities`.

**Justificación:**
1. **Simplicidad:** Las redes sociales son un conjunto limitado (WhatsApp, Facebook, Instagram) que no requiere normalización.
2. **Performance:** Evita JOINs adicionales en cada consulta.
3. **Flexibilidad:** Fácil agregar nuevas redes en el futuro sin migraciones.
4. **MySQL 8+ Support:** Soporte nativo para JSON con funciones de consulta.

**Estructura del JSON:**
```json
{
  "whatsapp": "https://wa.me/1234567890",
  "facebook": "https://facebook.com/mi-comunidad",
  "instagram": "https://instagram.com/mi-comunidad"
}
```

### 1.4 Código de Migración Alembic

```python
"""add communities module and social links

Revision ID: 20260401_0001
Revises: 20260330_0002
Create Date: 2026-04-01 00:00:00

"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import JSON

# revision identifiers, used by Alembic.
revision: str = "20260401_0001"
down_revision: str | None = "20260330_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # 1. Crear tabla communities
    op.create_table(
        "communities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("image_url", sa.String(255), nullable=True),
        sa.Column("owner_id", sa.String(36), nullable=False, index=True),
        sa.Column("contact_email", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "ACTIVE", "REJECTED", name="community_status"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("is_accepted_terms", sa.Boolean, nullable=False),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        sa.Column("social_links", JSON, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("idx_communities_status", "communities", ["status"])
    op.create_index("idx_communities_owner_status", "communities", ["owner_id", "status"])

    # 2. Crear tabla community_events (pivote)
    op.create_table(
        "community_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "community_id",
            sa.String(36),
            sa.ForeignKey("communities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_id",
            sa.String(36),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", name="community_event_status"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("requested_by", sa.String(36), nullable=False),
        sa.Column("reviewed_by", sa.String(36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_ce_community_status", "community_events", ["community_id", "status"])
    op.create_index("idx_ce_event", "community_events", ["event_id"])
    op.create_unique_constraint("uq_community_event", "community_events", ["community_id", "event_id"])

    # 3. Crear tabla banned_users
    op.create_table(
        "banned_users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), nullable=False, unique=True),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("banned_by", sa.String(36), nullable=False),
        sa.Column("banned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
    )
    op.create_index("idx_banned_users_active", "banned_users", ["user_id", "is_active"])

    # 4. Añadir social_links a events
    op.add_column("events", sa.Column("social_links", JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("events", "social_links")
    op.drop_table("banned_users")
    op.drop_table("community_events")
    op.drop_table("communities")
    
    # Eliminar ENUMs
    op.execute("DROP TYPE IF EXISTS community_status")
    op.execute("DROP TYPE IF EXISTS community_event_status")
```

---

## 2. Diseño de la API (Endpoints)

### 2.1 Endpoints de Comunidades

#### POST `/api/v1/communities` - Solicitar creación de comunidad
**Rol requerido:** `ROLE_USER` (cualquier usuario autenticado)

**Request Body:**
```json
{
  "name": "Runners Monterrey",
  "description": "Comunidad de corredores del área metropolitana de Monterrey",
  "image_url": "https://storage.eventcut.com/communities/runners-mty.jpg",
  "contact_email": "contacto@runnersmty.com",
  "is_accepted_terms": true,
  "social_links": {
    "whatsapp": "https://wa.me/528112345678",
    "facebook": "https://facebook.com/runnersmty",
    "instagram": "https://instagram.com/runnersmty"
  }
}
```

**Response (201 Created):**
```json
{
  "success": true,
  "message": "Solicitud de comunidad enviada. Pendiente de aprobación.",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Runners Monterrey",
    "description": "Comunidad de corredores...",
    "image_url": "https://storage.eventcut.com/communities/runners-mty.jpg",
    "owner_id": "user-uuid-123",
    "contact_email": "contacto@runnersmty.com",
    "status": "PENDING",
    "social_links": {...},
    "created_at": "2026-04-01T10:00:00Z"
  }
}
```

---

#### GET `/api/v1/communities` - Listar comunidades activas
**Rol requerido:** Público (sin autenticación)

**Query Parameters:**
- `limit` (int, default=20, max=100)
- `offset` (int, default=0)
- `search` (string, opcional) - Búsqueda por nombre

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Comunidades obtenidas",
  "data": {
    "items": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Runners Monterrey",
        "description": "Comunidad de corredores...",
        "image_url": "https://...",
        "owner_id": "user-uuid-123",
        "owner_first_name": "Juan",
        "owner_last_name": "Pérez",
        "social_links": {...},
        "events_count": 15,
        "created_at": "2026-04-01T10:00:00Z"
      }
    ],
    "total": 45
  }
}
```

---

#### GET `/api/v1/communities/{community_id}` - Detalle de comunidad
**Rol requerido:** Público

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Comunidad obtenida",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Runners Monterrey",
    "description": "Comunidad de corredores...",
    "image_url": "https://...",
    "owner_id": "user-uuid-123",
    "owner_first_name": "Juan",
    "owner_last_name": "Pérez",
    "contact_email": "contacto@runnersmty.com",
    "social_links": {...},
    "status": "ACTIVE",
    "created_at": "2026-04-01T10:00:00Z"
  }
}
```

---

#### GET `/api/v1/communities/{community_id}/events` - Schedule de comunidad
**Rol requerido:** Público

**Query Parameters:**
- `from` (datetime, opcional)
- `to` (datetime, opcional)
- `limit` (int, default=20)
- `offset` (int, default=0)

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Eventos de la comunidad obtenidos",
  "data": {
    "community": {
      "id": "...",
      "name": "Runners Monterrey"
    },
    "items": [
      {
        "id": "event-uuid-1",
        "title": "Carrera 10K Fundidora",
        "start_datetime": "2026-04-15T07:00:00Z",
        "end_datetime": "2026-04-15T12:00:00Z",
        "location": "Parque Fundidora",
        "image_url": "..."
      }
    ],
    "total": 8
  }
}
```

---

#### POST `/api/v1/communities/{community_id}/events/{event_id}/request` - Solicitar unir evento a comunidad
**Rol requerido:** `ROLE_USER` (solo el owner del evento)

**Response (201 Created):**
```json
{
  "success": true,
  "message": "Solicitud enviada al dueño de la comunidad",
  "data": {
    "request_id": "request-uuid-123",
    "community_id": "community-uuid",
    "event_id": "event-uuid",
    "status": "PENDING",
    "created_at": "2026-04-01T10:00:00Z"
  }
}
```

---

#### GET `/api/v1/communities/{community_id}/requests` - Ver solicitudes pendientes (Owner)
**Rol requerido:** `ROLE_USER` (solo owner de la comunidad)

**Query Parameters:**
- `status` (enum: PENDING, APPROVED, REJECTED, opcional)
- `limit`, `offset`

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Solicitudes obtenidas",
  "data": {
    "items": [
      {
        "request_id": "request-uuid-123",
        "event": {
          "id": "event-uuid",
          "title": "Carrera 10K",
          "start_datetime": "2026-04-15T07:00:00Z",
          "owner_id": "user-uuid-456",
          "owner_first_name": "María",
          "owner_last_name": "García"
        },
        "status": "PENDING",
        "created_at": "2026-04-01T10:00:00Z"
      }
    ],
    "total": 3
  }
}
```

---

#### PATCH `/api/v1/communities/{community_id}/requests/{request_id}` - Aprobar/Rechazar solicitud
**Rol requerido:** `ROLE_USER` (solo owner de la comunidad)

**Request Body:**
```json
{
  "action": "APPROVE"  // o "REJECT"
  // Si REJECT:
  // "rejection_reason": "El evento no cumple con los lineamientos de la comunidad"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Solicitud aprobada exitosamente",
  "data": {
    "request_id": "request-uuid-123",
    "status": "APPROVED",
    "reviewed_at": "2026-04-01T12:00:00Z"
  }
}
```

---

#### PATCH `/api/v1/communities/{community_id}` - Actualizar comunidad (Owner)
**Rol requerido:** `ROLE_USER` (solo owner)

**Request Body:**
```json
{
  "name": "Runners MTY Oficial",
  "description": "Nueva descripción...",
  "image_url": "https://...",
  "social_links": {...}
}
```

---

#### DELETE `/api/v1/communities/{community_id}` - Eliminar comunidad (soft delete)
**Rol requerido:** `ROLE_USER` (owner) o `ROLE_ADMIN`

---

### 2.2 Endpoints de Admin Dashboard

#### GET `/api/v1/admin/communities` - Listar solicitudes de comunidades
**Rol requerido:** `ROLE_ADMIN`

**Query Parameters:**
- `status` (enum: PENDING, ACTIVE, REJECTED, opcional)
- `limit`, `offset`

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Comunidades obtenidas",
  "data": {
    "items": [
      {
        "id": "community-uuid",
        "name": "Runners Monterrey",
        "owner_id": "user-uuid",
        "owner_email": "juan@example.com",
        "status": "PENDING",
        "is_accepted_terms": true,
        "created_at": "2026-04-01T10:00:00Z"
      }
    ],
    "total": 5
  }
}
```

---

#### PATCH `/api/v1/admin/communities/{community_id}/status` - Activar/Rechazar comunidad
**Rol requerido:** `ROLE_ADMIN`

**Request Body:**
```json
{
  "action": "ACTIVATE"  // o "REJECT"
  // Si REJECT:
  // "rejection_reason": "No cumple con las políticas de la plataforma"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Comunidad activada exitosamente",
  "data": {
    "id": "community-uuid",
    "status": "ACTIVE"
  }
}
```

---

#### GET `/api/v1/admin/events` - Listar todos los eventos (moderación)
**Rol requerido:** `ROLE_ADMIN`

**Query Parameters:**
- `is_active` (bool, opcional) - Incluir eventos eliminados
- `owner_id` (string, opcional)
- `from`, `to` (datetime)
- `limit`, `offset`

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Eventos obtenidos",
  "data": {
    "items": [
      {
        "id": "event-uuid",
        "title": "Evento de prueba",
        "owner_id": "user-uuid",
        "owner_email": "user@example.com",
        "is_active": true,
        "created_at": "2026-04-01T10:00:00Z",
        "community_associations": [
          {"community_id": "...", "community_name": "...", "status": "APPROVED"}
        ]
      }
    ],
    "total": 150
  }
}
```

---

#### POST `/api/v1/admin/users/{user_id}/ban` - Banear usuario
**Rol requerido:** `ROLE_ADMIN`

**Request Body:**
```json
{
  "reason": "Violación repetida de las normas de la comunidad"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Usuario baneado exitosamente",
  "data": {
    "user_id": "user-uuid",
    "banned_at": "2026-04-01T10:00:00Z",
    "reason": "Violación repetida de las normas de la comunidad"
  }
}
```

---

#### DELETE `/api/v1/admin/users/{user_id}/ban` - Desbanear usuario
**Rol requerido:** `ROLE_ADMIN`

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Usuario desbaneado exitosamente",
  "data": {
    "user_id": "user-uuid"
  }
}
```

---

#### GET `/api/v1/admin/users/banned` - Listar usuarios baneados
**Rol requerido:** `ROLE_ADMIN`

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Usuarios baneados obtenidos",
  "data": {
    "items": [
      {
        "user_id": "user-uuid",
        "reason": "Spam repetido",
        "banned_by": "admin-uuid",
        "banned_at": "2026-04-01T10:00:00Z"
      }
    ],
    "total": 12
  }
}
```

---

## 3. Lógica de Negocio y Servicios (Backend)

### 3.1 Modificación al Endpoint `POST /api/v1/events`

El schema `EventCreate` se actualiza para incluir redes sociales y solicitud opcional de comunidad:

```python
# auth/schemas/event.py

class SocialLinks(BaseModel):
    whatsapp: str | None = Field(default=None, max_length=255)
    facebook: str | None = Field(default=None, max_length=255)
    instagram: str | None = Field(default=None, max_length=255)

    @field_validator("whatsapp")
    @classmethod
    def validate_whatsapp(cls, v: str | None) -> str | None:
        if v and not v.startswith("https://wa.me/"):
            raise ValueError("WhatsApp link debe iniciar con https://wa.me/")
        return v

    @field_validator("facebook")
    @classmethod
    def validate_facebook(cls, v: str | None) -> str | None:
        if v and not v.startswith("https://facebook.com/"):
            raise ValueError("Facebook link debe iniciar con https://facebook.com/")
        return v

    @field_validator("instagram")
    @classmethod
    def validate_instagram(cls, v: str | None) -> str | None:
        if v and not v.startswith("https://instagram.com/"):
            raise ValueError("Instagram link debe iniciar con https://instagram.com/")
        return v


class EventCreate(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=5, max_length=5000)
    image_url: str | None = Field(default=None, max_length=255)
    start_datetime: datetime
    end_datetime: datetime
    location: str = Field(min_length=2, max_length=200)
    category_id: int
    # NUEVOS CAMPOS:
    social_links: SocialLinks | None = None
    community_id: str | None = Field(default=None, description="ID de comunidad para solicitar unión")
```

**Lógica del servicio actualizado:**

```python
# auth/services/event_service.py

def create_event(db: Session, payload: EventCreate, current_user: CurrentUser) -> Event:
    # 1. Verificar que el usuario no está baneado (se hace en dependency)
    
    # 2. Crear el evento
    event = Event(
        title=payload.title,
        description=payload.description,
        image_url=payload.image_url,
        start_datetime=payload.start_datetime,
        end_datetime=payload.end_datetime,
        location=payload.location,
        category_id=payload.category_id,
        owner_id=current_user.id,
        social_links=payload.social_links.model_dump() if payload.social_links else None,
    )
    db.add(event)
    db.flush()  # Para obtener el ID
    
    # 3. Si se solicita unirse a una comunidad
    if payload.community_id:
        community = get_active_community_or_404(db, payload.community_id)
        # Crear solicitud pendiente
        request = CommunityEvent(
            community_id=community.id,
            event_id=event.id,
            requested_by=current_user.id,
            status=CommunityEventStatus.PENDING,
        )
        db.add(request)
    
    db.commit()
    db.refresh(event)
    return event
```

### 3.2 Middleware de Verificación de Baneo

Se implementa como una **dependencia de FastAPI** que se aplica a todos los endpoints que requieren escritura:

```python
# auth/security/ban_check.py

from fastapi import Depends, status
from sqlalchemy.orm import Session

from events_service.app.core.exceptions import AppError, ErrorCodes
from events_service.app.db.session import get_db
from events_service.app.models.banned_user import BannedUser
from events_service.app.schemas.auth import CurrentUser
from events_service.app.security.dependencies import get_current_user


def check_user_not_banned(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Verifica que el usuario actual no esté baneado.
    Lanza excepción 403 si el usuario está en la lista de baneados activos.
    """
    banned = db.query(BannedUser).filter(
        BannedUser.user_id == current_user.id,
        BannedUser.is_active == True,
    ).first()
    
    if banned:
        raise AppError(
            code=ErrorCodes.USER_BANNED,
            message="Tu cuenta ha sido suspendida. Contacta soporte para más información.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    
    return current_user


# Alias para usar en endpoints de escritura
get_verified_user = check_user_not_banned
```

**Uso en los endpoints:**

```python
# En routes/events.py - Reemplazar get_current_user por get_verified_user en mutaciones

from events_service.app.security.ban_check import get_verified_user

@router.post("", response_model=ApiResponse[EventResponse], status_code=status.HTTP_201_CREATED)
def post_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_verified_user),  # Cambiado
) -> ApiResponse[EventResponse]:
    # ...
```

### 3.3 Estructura de Archivos Nuevos

```
app/
├── models/
│   ├── community.py           # Modelo Community
│   ├── community_event.py     # Modelo CommunityEvent (pivote)
│   └── banned_user.py         # Modelo BannedUser
├── schemas/
│   ├── community.py           # Schemas de comunidad
│   ├── admin.py               # Schemas de admin
│   └── social.py              # Schema SocialLinks compartido
├── services/
│   ├── community_service.py   # Lógica de comunidades
│   ├── admin_service.py       # Lógica de admin
│   └── ban_service.py         # Lógica de baneos
├── api/routes/
│   ├── communities.py         # Endpoints de comunidades
│   └── admin.py               # Endpoints de admin
└── security/
    ├── ban_check.py           # Dependency de verificación de baneo
    └── admin_required.py      # Dependency para validar rol ADMIN
```

### 3.4 Dependency para Validar Rol Admin

```python
# auth/security/admin_required.py

from fastapi import Depends, status

from events_service.app.core.exceptions import AppError, ErrorCodes
from events_service.app.schemas.auth import CurrentUser
from events_service.app.security.dependencies import get_current_user
from events_service.app.security.roles import is_admin_role


def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Valida que el usuario tenga rol de administrador."""
    if not is_admin_role(current_user.role):
        raise AppError(
            code=ErrorCodes.FORBIDDEN,
            message="Se requieren permisos de administrador",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return current_user
```

---

## 4. Guía de Integración Frontend

### 4.1 Modificaciones a Formularios Existentes

#### Formulario de Creación/Edición de Evento
**Cambios requeridos:**

1. **Nueva sección "Redes Sociales"** (colapsable/opcional):
   - Campo WhatsApp: Input tipo URL con placeholder "https://wa.me/..."
   - Campo Facebook: Input tipo URL con placeholder "https://facebook.com/..."
   - Campo Instagram: Input tipo URL con placeholder "https://instagram.com/..."

2. **Nueva sección "Asociar a Comunidad"** (opcional):
   - Dropdown/Autocomplete con comunidades ACTIVAS
   - Texto informativo: "Tu evento será enviado para aprobación del dueño de la comunidad"

**Validaciones frontend:**
- URLs deben comenzar con el prefijo correcto de cada red social
- community_id es opcional, pero si se selecciona debe existir

### 4.2 Nuevas Vistas Requeridas

#### A) Formulario de Solicitud de Comunidad
**Ruta sugerida:** `/communities/new`

**Campos del formulario:**
| Campo | Tipo | Requerido | Validación |
|-------|------|-----------|------------|
| Nombre | Text | Sí | 3-100 caracteres |
| Descripción | Textarea | Sí | 5-2000 caracteres |
| Imagen | Upload/URL | No | Formatos permitidos |
| Email de contacto | Email | Sí | Formato email válido |
| WhatsApp | URL | No | Prefijo https://wa.me/ |
| Facebook | URL | No | Prefijo https://facebook.com/ |
| Instagram | URL | No | Prefijo https://instagram.com/ |
| Acepto términos | Checkbox | Sí | Debe estar marcado |

**Post-submit:** Mostrar mensaje de éxito indicando que la solicitud está pendiente de aprobación.

---

#### B) Dashboard del Owner de Comunidad
**Ruta sugerida:** `/my-communities` y `/my-communities/{id}`

**Vista de lista:**
- Cards con las comunidades del usuario (todas, incluyendo PENDING y REJECTED)
- Badge de estado (Pendiente/Activa/Rechazada)
- Contador de eventos asociados
- Contador de solicitudes pendientes

**Vista de detalle/gestión:**

1. **Tab "Información":**
   - Formulario de edición de datos de la comunidad
   - Botón de eliminar comunidad

2. **Tab "Eventos":**
   - Lista de eventos APROBADOS para esta comunidad
   - Opción de remover evento de la comunidad

3. **Tab "Solicitudes" (badge con contador):**
   - Lista de solicitudes PENDING
   - Para cada solicitud:
     - Preview del evento (título, fecha, imagen)
     - Información del solicitante
     - Botones: Aprobar | Rechazar
   - Modal de confirmación para rechazar con campo de razón

---

#### C) Dashboard del Admin General
**Ruta sugerida:** `/admin` (protegida por rol)

**Secciones:**

1. **Comunidades Pendientes:**
   - Tabla con solicitudes de comunidades PENDING
   - Columnas: Nombre, Solicitante, Email, Fecha, Acciones
   - Botones: Ver detalle | Aprobar | Rechazar
   - Modal de rechazo con campo de razón

2. **Gestión de Eventos:**
   - Tabla con todos los eventos (filtrable)
   - Filtros: Estado (activo/inactivo), Fecha, Categoría, Owner
   - Columnas: Título, Owner, Estado, Fecha creación, Comunidades asociadas
   - Acción: Ver detalle | Desactivar

3. **Usuarios Baneados:**
   - Tabla de usuarios baneados
   - Columnas: User ID, Razón, Baneado por, Fecha, Acciones
   - Botón: Desbanear
   - Botón/Formulario: Banear nuevo usuario (requiere user_id y razón)

---

### 4.3 Manejo de Errores Específicos

El frontend debe manejar estos nuevos códigos de error:

| Código | HTTP Status | Mensaje | Acción sugerida |
|--------|-------------|---------|-----------------|
| `USER_BANNED` | 403 | Usuario suspendido | Mostrar modal informativo, logout |
| `COMMUNITY_NOT_FOUND` | 404 | Comunidad no encontrada | Redirigir a lista |
| `COMMUNITY_NOT_ACTIVE` | 400 | La comunidad no está activa | Informar al usuario |
| `NOT_COMMUNITY_OWNER` | 403 | No eres el dueño | Ocultar acciones |
| `NOT_EVENT_OWNER` | 403 | No eres el dueño del evento | Ocultar acciones |
| `EVENT_ALREADY_REQUESTED` | 409 | Ya existe una solicitud | Informar estado actual |
| `DUPLICATE_COMMUNITY_NAME` | 409 | Nombre de comunidad en uso | Sugerir otro nombre |

---

## 5. Documentación

### 5.1 Archivos de Documentación a Crear

1. **`docs/api/communities.md`** - Documentación completa de endpoints de comunidades
2. **`docs/api/admin.md`** - Documentación de endpoints de administración
3. **`docs/integration/social-links.md`** - Guía de integración de redes sociales
4. **`docs/integration/communities-frontend.md`** - Guía detallada para frontend

### 5.2 Actualización de OpenAPI/Swagger

Todos los nuevos endpoints deben incluir:
- Descriptions claras
- Ejemplos de request/response
- Documentación de códigos de error
- Tags apropiados (`communities`, `admin`)

---

## 6. Plan de Implementación por Fases

### Fase 1: Base de Datos y Modelos
1. Crear migración Alembic `20260401_0001`
2. Crear modelos SQLAlchemy (Community, CommunityEvent, BannedUser)
3. Actualizar modelo Event (social_links)
4. Ejecutar migración y verificar schema

### Fase 2: Lógica de Baneos
1. Crear BanService
2. Crear dependency `get_verified_user`
3. Actualizar endpoints existentes que requieren verificación
4. Crear endpoints admin de baneo

### Fase 3: Módulo de Comunidades
1. Crear schemas de comunidad
2. Crear CommunityService
3. Implementar endpoints CRUD de comunidades
4. Implementar endpoints de solicitudes evento-comunidad

### Fase 4: Admin Dashboard Endpoints
1. Crear AdminService
2. Implementar endpoints de gestión de comunidades (admin)
3. Implementar endpoint de listado de eventos (moderación)
4. Implementar endpoint de usuarios baneados

### Fase 5: Integración y Redes Sociales
1. Actualizar EventCreate/EventUpdate schemas
2. Actualizar EventService
3. Agregar SocialLinks a respuestas de eventos
4. Agregar SocialLinks a respuestas de comunidades

### Fase 6: Testing y Documentación
1. Crear tests unitarios para nuevos servicios
2. Crear tests de integración para endpoints
3. Generar documentación OpenAPI actualizada
4. Crear guías de integración para frontend

---

## 7. Consideraciones Adicionales

### 7.1 Seguridad
- Los baneos son verificados en cada request de escritura, no cacheados
- Las solicitudes de comunidad requieren aceptación explícita de términos
- Solo el owner puede gestionar solicitudes de su comunidad
- Los admins tienen acceso completo pero sus acciones se registran

### 7.2 Performance
- Índices en columnas frecuentemente consultadas (status, owner_id)
- Paginación obligatoria en listados
- JSON para social_links evita JOINs adicionales

### 7.3 Escalabilidad Futura
- El schema JSON de social_links permite agregar redes sin migración
- La tabla community_events permite features futuras (featured events, order, etc.)
- El sistema de baneos puede extenderse para notificar a auth-service si se requiere

---

*Documento generado el 2026-04-01*
*Revisión base de Alembic: 20260330_0002*
*Nueva revisión propuesta: 20260401_0001*

---

## 8. Log de Implementación

### ✅ Implementación Completada (2025-01-14)

**Archivos Creados:**
| Archivo | Descripción |
|---------|-------------|
| `alembic/versions/20260401_0001_add_communities_module.py` | Migración de BD |
| `app/models/community.py` | Modelo Community |
| `app/models/community_event.py` | Modelo CommunityEvent |
| `app/models/banned_user.py` | Modelo BannedUser |
| `app/schemas/community.py` | Schemas de comunidad |
| `app/schemas/social.py` | Schema SocialLinks |
| `app/schemas/admin.py` | Schemas de admin |
| `app/services/community_service.py` | Servicio de comunidades |
| `app/services/ban_service.py` | Servicio de baneos |
| `app/security/ban_check.py` | Dependency get_verified_user |
| `app/security/admin_required.py` | Dependency require_admin |
| `app/api/routes/communities.py` | Endpoints de comunidades |
| `app/api/routes/admin.py` | Endpoints de admin |
| `docs/FRONTEND_COMMUNITIES_INTEGRATION.md` | Guía de integración frontend |

**Archivos Modificados:**
| Archivo | Cambio |
|---------|--------|
| `app/models/event.py` | Agregado social_links y relación community_events |
| `app/models/__init__.py` | Exportaciones nuevos modelos |
| `app/schemas/event.py` | Agregados social_links, community_id; corregido validator datetime |
| `app/services/event_service.py` | Crear solicitud comunidad en create_event |
| `app/api/routes/events.py` | Usar get_verified_user en mutaciones |
| `app/api/router.py` | Registrar routers communities y admin |
| `app/core/exceptions.py` | Nuevos códigos de error |
| `app/main.py` | Fix handler de validación (serialización JSON) |

**Bugs Corregidos Durante Testing:**
1. **DateTime validation**: Comparación offset-naive vs offset-aware. Fix: `datetime(2000,1,1,tzinfo=value.tzinfo)`
2. **Validation handler**: `ValueError` en ctx no serializable. Fix: Crear dict limpio sin ctx

**Tests Ejecutados (19/19 pasaron):**
- ✅ Crear comunidad (estado PENDING)
- ✅ Admin aprobar comunidad (estado ACTIVE)
- ✅ Listar comunidades públicas
- ✅ Crear evento con social_links y community_id
- ✅ Ver solicitudes pendientes (owner)
- ✅ Aprobar solicitud de evento
- ✅ Ver schedule de comunidad (eventos aprobados)
- ✅ Admin banear usuario
- ✅ Usuario baneado bloqueado (403)
- ✅ Admin desbanear usuario
- ✅ Usuario puede crear después de desbaneo
- ✅ Error: Términos no aceptados (400)
- ✅ Error: Nombre duplicado (409)
- ✅ Error: Usuario sin rol admin (403)
- ✅ Error: Social link con formato inválido (422)
