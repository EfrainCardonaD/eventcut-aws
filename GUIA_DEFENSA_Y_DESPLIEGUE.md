# Guía Completa y Tutorial de Despliegue y Defensa — EventCut AWS

Esta guía explica **exactamente qué rol cumple cada parte del repositorio**, **qué único archivo necesitas llevar contigo** el día de la presentación y **cómo ejecutar todo desde cero paso a paso** (despliegue automatizado, demostración de la aplicación y pruebas de resiliencia en vivo).

---

## 1. ¿Qué rol cumple el Repositorio de GitHub y por qué solo necesitas llevar 1 script?

Originalmente tenías dos proyectos separados en tu computadora:
- `EventCut` (Frontend Vue 3 en WebStorm, pensado para Vercel)
- `FastAPIProject` (Backend FastAPI en PyCharm, conectado a MySQL local y Cloudflare R2)

Para el proyecto final en AWS, **ambos fueron unificados, adaptados a AWS y subidos a un único monorepo público en GitHub**:
> 🔗 **https://github.com/EfrainCardonaD/eventcut-aws**

### ¿Por qué es tan importante este repositorio?
Tus proyectos locales viejos (`WebstormProjects\EventCut` y `PycharmProjects\FastAPIProject`) **ya NO los necesitas llevar ni tocar**. El monorepo en GitHub cumple **4 roles críticos**:

| Carpeta en GitHub | Rol dentro de la arquitectura | Qué hace el script con ella |
| :--- | :--- | :--- |
| **`frontend/`** | Aplicación web Vue 3 + Vite + Tailwind + TresJS adaptada para apuntar al ALB de AWS y subir imágenes al proxy S3. | En el **Step 8**, el script le inyecta la URL real del ALB recién creado (`.env.production`), ejecuta `npm run build` y sube `dist/` al bucket **Amazon S3 Static Website**. |
| **`backend/`** | Microservicios `auth` (:8000) y `events_service` (:8001) detrás de `Traefik` (:8080), **migrados de Cloudflare R2 → Amazon S3** usando IAM (`LabInstanceProfile`), con `docker-compose.aws.yml` y `scripts/seed_aws_db.py`. | En el **Step 5**, el script empaqueta `backend/` en `backend-latest.tar.gz` y lo sube a un bucket S3 privado de artefactos. Cada vez que una instancia EC2 arranca (o el Auto Scaling crea un reemplazo tras un fallo), **la propia EC2 descarga ese paquete desde S3, construye Docker, corre Alembic + Seed con lock distribuido en RDS y levanta la API sola**. |
| **`infra/`** | Código de Infraestructura como Código (IaC) en Python + Boto3: el **Wizard Web** (`wizard_server.py`), el **motor de 10 steps** (`aws_deployer.py`) y la **suite de Chaos Engineering** (`resilience_tests.py`). | Orquesta toda la creación/destrucción de AWS sin hacer un solo clic en la consola web. |
| **`.github/workflows/`** | **Pipelines CI/CD con GitHub Actions** (`frontend-ci-cd.yml` y `backend-ci-cd.yml`). | Cada vez que haces `git push` a `main`, GitHub ejecuta automáticamente los **59 tests `pytest`** del backend y compila el frontend Vue 3 (y si configuras secretos AWS en el repo, despliega directo a S3 y refresca el ASG). |
| **`docs/`** | Entregables documentales: los 2 PDFs, la presentación `.pptx`/`.pdf`, diagramas y gráficas reales de resiliencia. | Respaldo oficial del proyecto para entregar al profesor. |

### El flujo completo de código → nube:
```text
 [Solo llevas: eventcut_launcher.py + labsuser.pem]
                     │
                     ▼ (clona automáticamente si no existe)
      GitHub (EfrainCardonaD/eventcut-aws)
          ├── backend/  ──► Step 5: tar.gz ──► S3 Artefactos ──► EC2 ASG (x2 Multi-AZ) ──► RDS MySQL 8.0 + S3 Media
          ├── frontend/ ──► Step 8: npm build ──► S3 Static Website (URL pública de la app)
          └── infra/    ──► Wizard Web local (http://127.0.0.1:8765) + Pruebas de Resiliencia
```

---

## 2. Recorrido del Diagrama de Arquitectura: Flujo de Datos y Función de Cada Servicio AWS

Durante tu defensa en clase, cuando muestres el diagrama (`docs/evidencias/arquitectura_eventcut_aws.png` o la Diapositiva 3–4), recórrelo de **izquierda a derecha** explicando estos **4 flujos de datos**:

1. **Carga del Frontend SPA (`Usuario → Amazon S3 Website`):**
   El navegador del usuario entra al sitio estático en **Amazon S3 Static Website Hosting** y descarga `index.html` + los bundles de Vue 3, Tailwind y TresJS. Al servirse directamente desde S3, el frontend escala automáticamente y no consume recursos de los servidores EC2.
2. **Tráfico API y Microservicios (`Usuario → ALB → EC2/Traefik → Auth / Events → RDS`):**
   El SPA envía las peticiones REST al **Application Load Balancer (`eventcut-alb`, puerto `:80`)**, que las reparte 50/50 entre **2 instancias EC2 (`t3.small`)** en distintas Zonas de Disponibilidad (`us-east-1a` y `us-east-1b`) por el puerto `:8080`. Dentro de cada EC2, **Traefik v3.4** bloquea `/api/internal` (HTTP 403) y enruta `/api/auth`, `/api/users` y `/api/health` a `auth-service` (`:8000`) y `/api/v1/*` a `events-service` (`:8001`). Ambos consultan de forma privada **Amazon RDS MySQL 8.0** (`:3306`).
3. **Subida y Lectura de Imágenes (`Usuario → ALB → events-service → Amazon S3 Media`):**
   Al subir una imagen, `events-service` la valida y optimiza con Pillow y la guarda en el bucket **Amazon S3 Media** (migrado desde Cloudflare R2) bajo `pending/`, autenticándose sin llaves fijas gracias al **IAM Instance Profile (`LabInstanceProfile`)** vía IMDSv2. Al confirmarse el evento, el objeto se promueve a `events/` y el navegador lo lee directo por HTTPS desde S3. Si alguien abandona el formulario, una regla **S3 Lifecycle** borra el archivo temporal a las 24 horas.
4. **Automatización, Auto-Healing y Observabilidad (`Wizard/GitHub Actions → S3 Artefactos → ASG → CloudWatch/SNS`):**
   El código backend se empaqueta en `backend-latest.tar.gz` y vive en **S3 Artefactos**. Si una EC2 muere o sube la CPU por encima del 60%, el **Auto Scaling Group** crea una nueva instancia usando el **Launch Template** (AMI AL2023 consultada en **SSM Parameter Store**), descarga el paquete de S3, coordina migraciones con `GET_LOCK` en RDS y se registra en el ALB. **CloudWatch** monitorea salud del ALB, errores 5XX y CPU, notificando por **Amazon SNS**.

### Resumen rápido — Función de cada servicio AWS usado:
| Servicio AWS | Función exacta en EventCut |
| :--- | :--- |
| **Amazon VPC + Subnets Multi-AZ** | Red privada aislada repartida en `us-east-1a` y `us-east-1b` para tolerancia a fallos. |
| **Security Groups (3 capas)** | Firewall por mínimo privilegio: `ALB (:80)` → `EC2 (:8080)` → `RDS (:3306)`. |
| **Amazon S3 (3 Buckets)** | (1) Hosting SPA Vue 3, (2) Almacenamiento multimedia ex-Cloudflare R2 con Lifecycle, (3) Artefactos de despliegue para EC2. |
| **Application Load Balancer (ALB)** | Entrada única HTTP capa 7, balanceo Multi-AZ y Health Checks cada 15s (`/api/health`). |
| **Amazon EC2** | Servidores Amazon Linux 2023 ejecutando Docker Compose (`Traefik`, `auth`, `events`, `restart: always`). |
| **Auto Scaling Group + Launch Template** | Mantiene mínimo 2 instancias sanas (auto-reparación) y escala hasta 4 si CPU > 60%. |
| **Amazon RDS MySQL 8.0** | Base de datos privada (`PubliclyAccessible=False`) para `eventcut_auth_db` y `eventcut_events_db` con backups de 7 días. |
| **AWS IAM (`LabInstanceProfile`)** | Otorga permisos temporales rotativos a los contenedores Docker para operar S3 sin llaves estáticas. |
| **AWS SSM Parameter Store** | Obtiene dinámicamente la última AMI oficial de Amazon Linux 2023 al desplegar. |
| **Amazon CloudWatch + Amazon SNS** | 4 alarmas críticas (UnHealthyHosts, HTTP 5XX, ASG CPU, RDS CPU) conectadas al tópico `eventcut-alerts`. |

---

## 3. ¿Qué necesitas llevar contigo el día de la presentación?

Literalmente **solo 3 cosas**:
1. **`eventcut_launcher.py`** (un único archivo Python portable; está en la raíz del repo y en `py-aws/`).
2. **`labsuser.pem`** (tu llave privada SSH descargada de AWS Academy Learner Lab — solo es necesaria para la Prueba 2 de resiliencia por SSH; el despliegue completo funciona incluso sin ella).
3. Acceso a tu sesión activa de **AWS Academy Learner Lab** (para copiar las credenciales temporales vigentes de 4 horas).

> **Prerrequisitos en la computadora donde presentes:** Python 3.10+, Git y Node.js (para compilar el frontend en Step 8). Si corres en tu propia laptop, ya tienes todo instalado.

---

## 4. Tutorial Paso a Paso (Desde una PC en blanco o desde tu Laptop)

### Paso A: Actualizar tus credenciales de AWS Academy Learner Lab
Cada vez que inicias el laboratorio en AWS Academy, tus credenciales temporales cambian (duran 4 horas):
1. En AWS Academy, presiona **Start Lab** hasta que el punto esté en verde.
2. Haz clic en **AWS Details** → **AWS CLI: Show**.
3. Copia todo el bloque `[default]` (`aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`).
4. Pégalo en tu archivo de credenciales de Windows:
   - Ruta: `C:\Users\<TU_USUARIO>\.aws\credentials`
   - Y asegúrate de tener `region = us-east-1` en `C:\Users\<TU_USUARIO>\.aws\config`.

### Paso B: Ejecutar tu único script portable
Abre PowerShell en la carpeta donde tienes `eventcut_launcher.py` y ejecuta:

```powershell
python eventcut_launcher.py
```
*(Si quieres indicar explícitamente dónde está tu llave `.pem`, usa `python eventcut_launcher.py --pem C:\ruta\labsuser.pem`)*

**¿Qué ocurrirá automáticamente?**
1. Si la carpeta `eventcut-aws/` no existe, el script hará `git clone https://github.com/EfrainCardonaD/eventcut-aws.git`.
2. Si faltan librerías (`boto3`, `requests`, `matplotlib`, `Pillow`), creará `.venv` e instalará `infra/requirements.txt`.
3. Validará tu cuenta AWS con `sts:GetCallerIdentity`.
4. Abrirá automáticamente tu navegador en **`http://127.0.0.1:8765`** mostrando el **Wizard Web Interactivo de EventCut AWS**.

---

## 5. Recorrido de los 10 Steps en el Wizard Web (Qué explicar al profesor en cada clic)

En el navegador verás la barra de progreso, los 10 pasos y el botón azul **`▶ Continuar (Ejecutar Step)`** junto con el botón rojo **`🗑 Limpiar Todo AWS (Desde 0)`**.

| Step | Acción al pulsar «Continuar» | Tiempo | Qué destacar en tu explicación |
| :--- | :--- | :---: | :--- |
| **Step 0** | **Validar Entorno y Credenciales AWS** | ~5 s | Demuestra que verifica tu identidad STS (`002627054381`), `LabInstanceProfile` (sin crear roles IAM prohibidos en Lab), KeyPair `vockey` y `npm`. |
| **Step 1** | **Limpieza Total del Entorno AWS (Desde 0)** | ~2-4 min | **Cumple la regla de entorno limpio:** elimina automáticamente ASGs, ALBs, EC2, RDS, S3, DynamoDB, CloudWatch y Security Groups previos para garantizar construcción 100% desde cero. |
| **Step 2** | **Red Multi-AZ y Security Groups** | ~15 s | Aplica mínimo privilegio: Internet solo entra al ALB (`:80`), el ALB solo entra a EC2 (`:8080`) y **solo las EC2 pueden tocar RDS (`:3306`)**. |
| **Step 3** | **Buckets Amazon S3 (ex-Cloudflare R2)** | ~20 s | Crea 3 buckets: **Media** (reemplaza Cloudflare R2, con CORS y regla Lifecycle que purga `pending/` en 1 día), **Frontend SPA** (Website Hosting con fallback `index.html`) y **Artefactos** (privado). |
| **Step 4** | **Amazon RDS MySQL 8.0** | ~4-6 min | Crea `eventcut-mysql-db` (`db.t3.micro`) con `PubliclyAccessible=False` (sin IP pública) y backups automáticos de 7 días. |
| **Step 5** | **Empaquetar Backend → S3** | ~10 s | Comprime `backend/` en `backend-latest.tar.gz` (sin `.env` ni secretos) y lo sube a S3 Artefactos. |
| **Step 6** | **Application Load Balancer Multi-AZ** | ~2-3 min | Crea el ALB público en `us-east-1a` y `us-east-1b`, con Health Check `GET /api/health` cada 15s y deregistration delay de 15s para failover veloz. |
| **Step 7** | **Launch Template + Auto Scaling Group** | ~4-6 min | Lanza **2 EC2 `t3.small`** en distintas Zonas de Disponibilidad. Su `user_data` descarga el código de S3, usa un **lock distribuido MySQL (`GET_LOCK`)** para evitar race conditions al correr Alembic y Seed, sube imágenes WebP de muestra a S3 y levanta Docker Compose (`Traefik` + `auth` + `events`). |
| **Step 8** | **Build y Deploy Frontend Vue 3 en S3** | ~45 s | Genera `.env.production` apuntando al DNS del ALB recién creado, ejecuta `npm run build` y sube los 85 archivos estáticos a S3 Website con headers `Cache-Control`. |
| **Step 9** | **CloudWatch, SNS y Verificación E2E** | ~20 s | Configura 4 alarmas en CloudWatch conectadas a SNS (`eventcut-alerts`) y corre 6 pruebas reales (Frontend 200, balanceo en 2 AZs, bloqueo `/api/internal` 403, Login JWT Admin, eventos RDS e imagen S3 200). |

> **Tip de tiempo para clase:** Si el profesor quiere ver el proceso completo desde 0 sin esperar 15 minutos en vivo, puedes llegar con todo ya desplegado y mostrar el Step 0 + la app viva + las pruebas de resiliencia, **o** pulsar el botón rojo **`Limpiar Todo AWS`** al final para demostrar cómo destruye todo (Computación Sustentable) y el botón **`Continuar`** en los primeros steps.

---

## 6. Cómo Demostrar la Aplicación Web Funcionando en Vivo

Cuando termine el Step 9, el panel inferior derecho del Wizard te mostrará enlaces directos clicables:

1. **Abre el enlace de `Frontend S3`** (`http://eventcut-web-002627054381-us-east-1.s3-website-us-east-1.amazonaws.com`).
2. Verás la landing de **EventCut**, la cartelera con los **5 eventos seed** y las **2 comunidades**, cuyas imágenes ya cargan directo desde **Amazon S3** (`https://eventcut-media-...s3.us-east-1.amazonaws.com/...`).
3. **Inicia sesión como Administrador**:
   - Correo: `admin@eventcut.edu.mx`
   - Contraseña: `AdminEventCut2026!`
4. **Crea un nuevo evento subiendo una imagen desde tu computadora**:
   - El frontend pide URL de subida → envía la imagen al backend tras el ALB → `events-service` la optimiza con Pillow → la sube a **Amazon S3 usando `LabInstanceProfile` (sin llaves fijas)** → al crear el evento la promueve de `events/pending/` a `events/`.
   - Abre la imagen en una pestaña nueva y muéstrale al profesor la URL `amazonaws.com` demostrando que **ya no existe Cloudflare R2**.
5. **Muestra el balanceo Multi-AZ**: abre `http://<ALB_DNS>/api/health` y presiona F5 varias veces; verás alternar `node_id` y `availability_zone` entre `us-east-1a` y `us-east-1b`.

---

## 7. Cómo Demostrar las Pruebas de Resiliencia en Vivo

Tienes dos formas:

### Forma 1 (1 clic desde el Wizard Web — Recomendada)
Haz clic en el botón **`🧪 Correr Pruebas de Resiliencia`** en `http://127.0.0.1:8765` (o ejecuta `python eventcut_launcher.py --resilience`). Ejecutará automáticamente las 4 pruebas reales:
1. **Carga concurrente (60 peticiones):** confirma 100% disponibilidad y reparto 50/50 entre ambas AZs.
2. **Crash de contenedor Docker (`kill -9` al PID de `auth-service`):** demuestra auto-recuperación por `restart: always` en ~4-5 segundos.
3. **Seguridad y validación S3:** intenta subir un binario corrupto (HTTP 415) y hacer path traversal fuera de `pending/` (HTTP 422), luego sube una imagen válida (HTTP 200).
4. **Destrucción catastrófica de una instancia EC2 (`terminate-instances`):** mata uno de los 2 servidores completos mientras sigue recibiendo peticiones cada 2 segundos; el nodo sobreviviente mantiene la app viva (~96% disponibilidad) y el Auto Scaling Group crea y levanta un servidor nuevo desde cero hasta volver a 2/2 `healthy`.

### Forma 2 (Manual dramática en consola durante la defensa)
Abre dos terminales lado a lado:
- **Terminal 1 (Monitor continuo de la app):**
  ```powershell
  while ($true) {
    try { (Invoke-RestMethod "http://<TU_ALB_DNS>/api/health") | ConvertTo-Json -Compress }
    catch { Write-Host "REINTENTANDO..." -ForegroundColor Red }
    Start-Sleep 1
  }
  ```
- **Terminal 2 (Destruir una instancia EC2 en vivo):**
  ```powershell
  aws ec2 terminate-instances --instance-ids <ID_DE_UNA_DE_LAS_2_EC2>
  ```
  El profesor verá en vivo cómo la Terminal 1 **no se cae**, sigue respondiendo desde la otra Zona de Disponibilidad y minutos después aparece el nuevo `node_id` creado automáticamente por AWS Auto Scaling.

---

## 8. Modos Alternativos del Script Portable

Si por alguna razón prefieres no abrir el navegador local:
```powershell
# Modo interactivo en consola (muestra cada step y pide presionar ENTER para continuar)
python eventcut_launcher.py --cli

# Modo 100% automático (limpia todo desde 0 y ejecuta los 10 steps seguidos)
python eventcut_launcher.py --auto

# Ejecutar solo las pruebas de resiliencia
python eventcut_launcher.py --resilience

# Ejecutar un único step específico (ej. solo limpiar todo al terminar la clase)
python eventcut-aws/infra/aws_deployer.py --step cleanup
```

---

## 9. Preguntas Frecuentes en la Defensa (y cómo responderlas)

1. **¿Por qué usaron GitHub Actions en vez de AWS CodeBuild y S3 Website en vez de CloudFront?**
   > Porque verificamos mediante AWS CLI las políticas del rol `voclabs` en AWS Academy Learner Lab: `codebuild:ListProjects` y `cloudfront:ListDistributions` devuelven `AccessDenied`. En lugar de quedarnos bloqueados, diseñamos una arquitectura 100% funcional con servicios autorizados (ALB, ASG, EC2, RDS, S3, CloudWatch, SNS) complementada con GitHub Actions para CI/CD.
2. **¿Qué pasa si expiran las credenciales de 4 horas de AWS Academy mientras la app está corriendo?**
   > La aplicación en la nube **sigue funcionando normalmente**, porque los contenedores dentro de EC2 no usan llaves estáticas en `.env`: se autentican contra Amazon S3 mediante el IAM Instance Profile (`LabInstanceProfile`) usando metadatos IMDSv2 (`HttpPutResponseHopLimit=2`), que rotan credenciales automáticamente.
3. **¿Cómo evitan que las 2 instancias EC2 choquen al correr migraciones de Alembic al mismo tiempo?**
   > Implementamos un candado distribuido en MySQL RDS (`SELECT GET_LOCK('eventcut_bootstrap_auth', 180)`) dentro de `backend/scripts/seed_aws_db.py`. El primer nodo adquiere el lock, crea las bases, migra Alembic y ejecuta el seed; el segundo nodo espera ordenadamente y valida de forma idempotente sin errores.
4. **¿Qué pasa con las imágenes subidas si alguien abandona el formulario sin guardar el evento?**
   > Todas las subidas pasan primero por el prefijo `events/pending/` o `comunidad/pending/`. Al guardar el evento se promueven a la carpeta definitiva; si se abandonan, una regla **S3 Lifecycle** configurada automáticamente en el Step 3 las elimina tras 24 horas para evitar costos basura.
5. **¿Cómo aplican Computación Sustentable?**
   > Además de dimensionar instancias eficientes (`t3.small` y `db.t3.micro`) con escalado dinámico por CPU (60%), el script incluye el **Step 1 / botón de Limpieza Total** que destruye todos los recursos ociosos al concluir las pruebas, evitando consumo eléctrico y costos innecesarios (y en producción proponemos apagado programado en horario académico reduciendo el costo anual en un 42.6%).
