# EventCut AWS — Plataforma Web Universitaria Resiliente en la Nube

Proyecto integral de despliegue automatizado (Infrastructure as Code en Python + Boto3) para la plataforma web **EventCut** sobre **Amazon Web Services (AWS)**, con migración completa de almacenamiento multimedia de **Cloudflare R2 → Amazon S3**, alta disponibilidad Multi-AZ y suite automatizada de pruebas de resiliencia (Chaos Engineering).

## Estructura del Monorepo

```text
eventcut-aws/
├── frontend/                  # SPA Vue 3 + Vite + Tailwind + Pinia + TresJS (S3 Static Website)
├── backend/                   # Microservicios FastAPI (auth + events_service) + Traefik + Alembic + Seed AWS
├── infra/                     # Infraestructura como Código (Python + Boto3)
│   ├── wizard_server.py       # Wizard Web Interactivo paso a paso con botón 'Continuar' y 'Limpiar todo AWS'
│   ├── aws_deployer.py        # Motor IaC determinista de 10 pasos (también ejecutable por CLI)
│   ├── resilience_tests.py    # Suite en vivo de 4 pruebas de resiliencia + generador de gráficas
│   └── config.py              # Configuración centralizada y estado local
├── .github/workflows/         # Pipelines CI/CD con GitHub Actions (Frontend y Backend por ruta)
└── docs/                      # Documentación PDF, Guía de Resiliencia PDF y Presentación (.pptx/.pdf)
```

## Arquitectura AWS

- **Frontend SPA**: Amazon S3 Static Website Hosting (`index.html` + SPA fallback).
- **Balanceo y Seguridad Perimetral**: Application Load Balancer (ALB) Multi-AZ + Security Groups de mínimo privilegio (`ALB :80 → EC2 :8080 → RDS :3306`).
- **Cómputo Auto-Reparable**: Auto Scaling Group (`Min=2, Desired=2, Max=4`, Multi-AZ `us-east-1a/1b`) con instancias EC2 Amazon Linux 2023 ejecutando Docker Compose (`Traefik v3.4` + `auth-service` + `events-service`, `restart: always`) y escalado Target Tracking por CPU (60%).
- **Base de Datos Relacional Privada**: Amazon RDS MySQL 8.0 (`db.t3.micro`, `PubliclyAccessible=False`, backups automáticos 7 días) con migraciones Alembic serializadas mediante MySQL `GET_LOCK`.
- **Almacenamiento Multimedia (Migrado desde Cloudflare R2)**: Amazon S3 nativo autenticado con `LabInstanceProfile` (IMDSv2, sin credenciales estáticas), CORS, optimización WebP con Pillow y reglas Lifecycle de limpieza automática para `pending/`.
- **Observabilidad**: Amazon CloudWatch (4 alarmas críticas) + Amazon SNS (`eventcut-alerts`).

## Uso Rápido

### 1. Modo Wizard Web Interactivo (Recomendado para demostración en clase)
```powershell
python infra/wizard_server.py
```
Se abrirá automáticamente `http://127.0.0.1:8765` con los 10 steps guiados, botón **Continuar (Ejecutar Step)**, botón **Limpiar Todo AWS (Desde 0)** y consola en tiempo real.

### 2. Modo CLI (Paso a paso o Automático)
```powershell
# Interactivo en consola (pide Enter en cada step)
python infra/aws_deployer.py --cli-interactive

# Limpiar y desplegar absolutamente todo desde 0 automáticamente
python infra/aws_deployer.py --all

# Ejecutar solo limpieza total
python infra/aws_deployer.py --step cleanup
```

### 3. Ejecutar Pruebas de Resiliencia en Vivo
```powershell
python infra/resilience_tests.py
```
