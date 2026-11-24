## Plan: Refactor de estructura + Alembic por microservicio + base Docker-ready

El fallo viene de que el Alembic “global” en la raíz sigue apuntando a imports `app.*`, pero el servicio real ya vive en `auth/*` (y la raíz solo tiene un `main.py` puente). La prioridad es mover y corregir Alembic para que quede **dentro de `auth/`** y use imports `auth.*`. Después, separar `.env` por servicio y dejar ambos microservicios auto-contenidos (`auth/` y `events_service/`). Con esa base limpia, ya se puede dockerizar con Traefik (8080), DBs internas y migraciones automáticas al arranque.

### Steps 6
1. Corregir Alembic del auth-service: mover `alembic.ini` + `alembic/` a `auth/` y actualizar imports/rutas.
2. Eliminar residuos de raíz: remover `main.py` (puente), `.env` global, y cualquier config global ya no usada.
3. Separar variables por microservicio: crear `auth/.env(.example)` y `events_service/.env(.example)` con valores y placeholders.
4. Alinear entrypoints: ejecutar auth como `uvicorn auth.main:app` y events como `uvicorn events_service.main:app`.
5. Ajustar documentación `.http` y docs internas para usar servicio/puerto correcto (luego gateway 8080).
6. Preparar dockerización posterior: Dockerfiles por servicio + compose con Traefik + ngrok + migraciones automáticas.

### Further Considerations 3
1. Mantener `requirements.txt` raíz vs mover a `auth/requirements.txt` para builds aislados.
2. Confirmar dónde está el `Base` real del auth-service: `auth/db/base.py` vs algún `auth/db/base.py` importado por modelos.
3. Definir ruta única de health: `/api/health` (auth) y `/api/events/health` (events) para evitar colisiones.

---

## Verificación (lo que pediste: “sí es correcto pero igual verifica”)
Sí: el Alembic de la raíz es del **auth-service**, y además está “desalineado” con la refactorización:

- `alembic.ini` root usa `sqlalchemy.url=.../auth_db` (auth).
- `alembic/env.py` root importa `from app.core.settings import settings` y `from app.db.base import Base`.
- En tu repo actual, el servicio apunta a `auth.*` (tu `main.py` root ya importa `from auth.main import app`).
- Eso confirma el problema: **alembic root quedó con imports antiguos (`app.*`)** ⇒ al mover a `auth/` hay que actualizarlo a `auth.core.settings` y `auth.db.base` (o la ruta real que corresponda, según el código dentro de `auth/`).

---

## Step 1 (prioridad) más detallado: “¿a dónde se supone debería ir Alembic?”
**Debe ir dentro de `auth/`**, así:

- `auth/alembic.ini`
- `auth/alembic/env.py`
- `auth/alembic/versions/*.py`

Y el `auth/alembic.ini` debería tener:
- `script_location = alembic` (porque ahora correrás desde `auth/`)
- o dejar `script_location = auth/alembic` si prefieres correr desde la raíz, pero eso choca con tu objetivo (“no main en la raíz” y servicios autocontenidos). Recomendación: correr desde `auth/`.

Además, `auth/alembic/env.py` debe importar:
- `from auth.core.settings import settings`
- `from auth.db.base import Base`
(no `app.*`)

---

## Notas importantes para que el plan sea ejecutable
- En tu árbol existe `auth/db/base.py` y define un `Base` válido.
- El `alembic/env.py` actual apunta a `app.db.base` ⇒ es casi seguro que esa importación está rota o depende de un alias/paquete residual.
- Por eso, mover Alembic sin corregir imports seguiría fallando: el arreglo consiste en **mover + ajustar rutas**.

