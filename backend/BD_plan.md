1. Definición Estructural del Esquema (Relacional)
   Basado en el esquema de autenticación existente (donde users.id es de tipo string, típicamente un UUID), la arquitectura del CEMS (Centralized Event Management System) se desacopla lógicamente, manteniendo integridad referencial estricta.

Tabla categories (Catálogo de Clasificación)

id: INT AUTO_INCREMENT PRIMARY KEY.

slug: VARCHAR(50) UNIQUE NOT NULL. Identificador seguro para URLs y filtrado en el frontend (ej. cinecut, ingenieria).

name: VARCHAR(50) NOT NULL. Nombre legible.

Tabla events (Entidad Transaccional Core)

id: VARCHAR(36) PRIMARY KEY. Identificador único (UUID v4) para evitar recolección secuencial de datos por usuarios malintencionados.

title: VARCHAR(150) NOT NULL.

description: TEXT NOT NULL.

image_url: VARCHAR(255). Almacena estrictamente la ruta hacia el CDN o Bucket (AWS S3/Cloud Storage). Lógica comparativa: Guardar blobs binarios en la base de datos satura el almacenamiento y bloquea el motor; almacenar la URL descarga el trabajo pesado hacia la red de entrega de contenidos.

start_datetime: DATETIME NOT NULL.

end_datetime: DATETIME NOT NULL.

location: VARCHAR(200) NOT NULL.

owner_id: VARCHAR(36) NOT NULL. Llave foránea hacia users.id. Define la propiedad del evento para el control de acceso basado en roles (RBAC) al editar o eliminar.

category_id: INT NOT NULL. Llave foránea hacia categories.id.

created_at, updated_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP.

Tabla event_favorites (Métrica de Popularidad y Personalización)

user_id: VARCHAR(36) NOT NULL. Llave foránea hacia users.id.

event_id: VARCHAR(36) NOT NULL. Llave foránea hacia events.id.

created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP.

Restricción Crítica: Se aplica una llave primaria compuesta PRIMARY KEY (user_id, event_id). Esto previene a nivel de motor de base de datos que un usuario genere registros duplicados para inflar la métrica de un evento.

2. Estrategia de Indexación para Alto Rendimiento
   Para que el frontend reactivo y el mini-calendario operen sin latencia, la consulta de datos debe estar respaldada por índices B-Tree estratégicos. Un diseño sin índices obliga al motor a realizar escaneos completos de tabla (full table scans), colapsando el rendimiento al escalar.

Índice de Rango Temporal: INDEX idx_events_dates (start_datetime, end_datetime). Vital para extraer rápidamente los eventos que pertenecen a la "semana actual" o a un "mes específico" en el widget del calendario.

Índice de Filtrado: INDEX idx_events_category_date (category_id, start_datetime). Optimiza la consulta cuando el usuario presiona los botones horizontales de categorías en la interfaz (ej. Mostrar próximos eventos de "Ingeniería").

3. Orquestación del "Score" (Eventos Destacados)
   El antipatrón manual: Crear una columna score en la tabla events que se actualice con UPDATE events SET score = score + 1 cada vez que alguien marca un favorito. Esto genera bloqueos de fila (row locks) y colisiones transaccionales (condiciones de carrera) cuando cientos de alumnos intentan interactuar simultáneamente.

La solución arquitectónica: Se define una vista SQL (o se resuelve vía consulta de agregación indexada en FastAPI): SELECT event_id, COUNT(user_id) AS score FROM event_favorites GROUP BY event_id. Al estar la tabla pivote optimizada, el motor MySQL calcula la popularidad en milisegundos, garantizando consistencia absoluta y reflejando la demanda orgánica real en el carrusel de "Destacados".

4. Puesta en Producción (Alembic y MySQL)
   Para el despliegue en entornos productivos, se configuran las siguientes directrices en la capa de datos:

Integridad Referencial: Todas las llaves foráneas llevarán la restricción ON DELETE CASCADE (para event_favorites cuando se borra un evento) o ON DELETE RESTRICT (para categories).

Connection Pooling: Dado que FastAPI operará de manera asíncrona manejando miles de peticiones, MySQL debe configurarse a través de SQLAlchemy con un Connection Pool robusto (pool_size=20, max_overflow=10) para reciclar conexiones inactivas y evitar el error Too many connections.

Automatización CI/CD: El comando alembic upgrade head se integrará como un paso obligatorio en el pipeline de despliegue (GitHub Actions, GitLab CI) inmediatamente antes de levantar los contenedores del backend. Esto anula la intervención humana en la base de datos de producción.