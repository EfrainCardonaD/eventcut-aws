# Events Service — Admin / Moderación

Base path: `/api/v1/admin`

> Nota: el CRUD de categorías requiere rol admin, pero sus rutas están bajo `/api/v1/categories`.

## Autorización

Requiere Bearer token con rol admin (validado vía dependency `require_admin`).

Header:
- `Authorization: Bearer <ACCESS_TOKEN>`

---

## CRUD de categorías

### `POST /api/v1/categories`
Crea una categoría.

Body:
```json
{ "name": "Ingeniería", "slug": "ingenieria" }
```

### `PATCH /api/v1/categories/{category_id}`
Actualiza nombre y/o slug.

Body parcial:
```json
{ "name": "Ingeniería y Tecnología" }
```

### `DELETE /api/v1/categories/{category_id}`
Elimina categoría si no tiene eventos asociados.

Respuestas frecuentes:
- `204` eliminado
- `409` categoría en uso por eventos

---

## Moderación de comunidades

### `GET /api/v1/admin/communities`
Lista comunidades para moderación.

**Query:**
- `status` (opcional; típicamente `PENDING`)
- `limit`, `offset`

### `PATCH /api/v1/admin/communities/{community_id}/status`
Aprueba o rechaza comunidades.

Body:
```json
{ "action": "ACTIVATE" }
```

Rechazo:
```json
{ "action": "REJECT", "rejection_reason": "No cumple lineamientos" }
```

---

## Sistema de baneos

### `POST /api/v1/admin/users/{user_id}/ban`
Banea usuario y despublica contenido asociado.

Body:
```json
{ "reason": "Violación de normas" }
```

### `DELETE /api/v1/admin/users/{user_id}/ban`
Desbanea usuario.

### `GET /api/v1/admin/users/banned`
Lista usuarios baneados.

Query:
- `limit`, `offset`
- `include_inactive` (bool)

### `GET /api/v1/admin/users/{user_id}/ban-status`
Consulta si un usuario tiene baneo activo.

