# Contexto del Sistema Actual (Events Service - CEMS)
Actúa como un Arquitecto de Software y Desarrollador Backend Senior experto en Python, FastAPI, SQLAlchemy y Alembic.

Actualmente tenemos un microservicio de eventos (`events_service`) que maneja la publicación, descubrimiento y guardado a favoritos de eventos.
- **Base de datos:** MySQL 8+ gestionada con Alembic. Las migraciones actuales van en la revisión `20260329_0002`.
- **Autenticación y Usuarios:** Vía JWT provisto por un `auth-service` externo. **IMPORTANTE:** Este servicio de eventos NO administra usuarios ni credenciales. La identidad viene del JWT y las validaciones remotas se hacen contra `auth-service`.
- **Arquitectura:** Patrones de soft-delete (`is_active`), respuestas estandarizadas (envelopes de `success`, `message`, `data`), e integración con frontend manejando errores 422 detallados.

# Nuevos Requerimientos a Implementar

## 1. Módulo de "Comunidades" (Estilo Luma)
- **Creación y Flujo de Aprobación:** Cualquier usuario (`ROLE_USER`) puede solicitar crear una comunidad. Al enviarla, entra en estado `PENDING`. Solo un usuario con `ROLE_ADMIN` puede cambiar el estado a `ACTIVE` para que sea pública.
- **Datos de la Comunidad:** Debe incluir nombre, foto/imagen (`image_url`), descripción, `owner_id` (quien la crea), correo de contacto registrado en EventCut, y un flag de aceptación de términos/responsabilidad (`is_accepted_terms`).
- **Flujo de Eventos:** Al crear un evento, el usuario puede solicitar opcionalmente que su evento se una a una comunidad específica. El dueño (`owner_id`) de esa comunidad tendrá un panel para APROBAR o RECHAZAR esta solicitud.
- **Visualización:** Existirá una vista pública por comunidad con un "schedule" de los eventos aprobados para dicha comunidad.

## 2. Redes Sociales (Feature Global)
- Tanto los **Eventos** como las **Comunidades** deben poder almacenar links opcionales a redes sociales (limitado a WhatsApp, Facebook e Instagram por ahora).

## 3. Panel de Control de Administrador (Admin Dashboard)
- Los administradores necesitan endpoints dedicados para gestionar la plataforma.
- **Funciones:** Ver listado general de eventos (incluso inactivos/pendientes), gestionar las solicitudes de nuevas comunidades (aprobar/rechazar) y gestionar usuarios (ver y banear).
- **Reto Arquitectónico (Baneos):** Dado que los usuarios viven en `auth-service`, diseña una solución eficiente para banear usuarios a nivel del `events_service` (ej. una tabla local de `banned_users` que bloquee cualquier mutación, o un flujo para notificar al `auth-service`).

# Tarea
Diseña un **Plan de Implementación Técnico Completo** en formato Markdown. El plan debe contener estrictamente lo siguiente:

## 1. Diseño de Base de Datos (Esquema Alembic)
- Define las nuevas tablas: `communities`, la tabla pivote de solicitudes `community_events`, y cualquier tabla necesaria para las redes sociales (o si usarás un campo JSON en `events` y `communities`). Explica la decisión.
- Define la estrategia para la lista de usuarios baneados.
- Redacta el código base de la migración de Alembic que seguiría después de la revisión `20260329_0002`.

## 2. Diseño de la API (Endpoints)
Define los nuevos endpoints manteniendo el contrato estandarizado de la API actual (Envelope de success/error). Incluye método, path, roles requeridos y payload de ejemplo para:
- **Comunidades:** Solicitar creación (User), Listar activas (Público), Solicitar añadir evento (Dueño de evento), Aprobar/Rechazar evento (Dueño de comunidad).
- **Admin Dashboard:** Listar solicitudes de comunidades (Admin), Activar/Rechazar comunidad (Admin), Banear/Desbanear usuario (Admin), Listar todos los eventos para moderación (Admin).

## 3. Lógica de Negocio y Servicios (Backend)
- Explica cómo se modificará el endpoint actual `POST /api/v1/events` para aceptar la solicitud de comunidad y las redes sociales.
- Detalla el middleware o dependencia de seguridad para verificar y bloquear peticiones de escritura si el `current_user.id` está en la lista de baneados.

## 4. Guía de Integración Frontend
- Enumera los cambios clave para el equipo de frontend: modificaciones a los formularios existentes (agregando campos de links sociales) y las nuevas vistas requeridas (Formulario de solicitud de comunidad, Dashboard del Owner de comunidad, Dashboard del Admin General).

## 5. Documentacion 
- el paso final es crear la documentacion necesaria para que el equipo de frontend pueda implementarlo.

## 6. nota importante
- Esta es una idea general de cómo estructurar el plan. El objetivo es que sea lo suficientemente detallado para que un desarrollador backend pueda implementarlo sin necesidad de aclaraciones adicionales, y que el equipo de frontend tenga una guía clara de los cambios necesarios para integrar las nuevas funcionalidades.
