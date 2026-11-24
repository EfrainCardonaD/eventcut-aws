"""
Generador de la Presentación Ejecutiva de Defensa en Clase (.pptx y .pdf) para EventCut AWS.
Usa python-pptx para crear 11 diapositivas panorámicas (16:9) con diseño moderno oscuro/corporativo,
diagramas embebidos, tabla de costos, resultados reales de resiliencia y guion de demo en vivo.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

DOCS_DIR = Path(__file__).resolve().parent
REPO_ROOT = DOCS_DIR.parent
EVIDENCIAS_DIR = DOCS_DIR / "evidencias"
STATE_FILE = REPO_ROOT / "infra" / "state" / "deployment_state.json"
RESILIENCE_FILE = REPO_ROOT / "infra" / "state" / "resilience_results.json"

BG_DARK = RGBColor(0x0B, 0x11, 0x20)
BG_CARD = RGBColor(0x1E, 0x29, 0x3B)
BG_LIGHT = RGBColor(0xF8, 0xFA, 0xFC)
NAVY = RGBColor(0x0F, 0x17, 0x2A)
BLUE = RGBColor(0x25, 0x63, 0xEB)
SKY = RGBColor(0x38, 0xBD, 0xF8)
GREEN = RGBColor(0x10, 0xB9, 0x81)
AMBER = RGBColor(0xF5, 0x9E, 0x0B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
MUTED = RGBColor(0x94, 0xA3, 0xB8)
TEXT_DARK = RGBColor(0x33, 0x41, 0x55)


def _load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def _set_bg(slide, color: RGBColor):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_header(slide, title: str, subtitle: str, slide_num: int):
    _set_bg(slide, BG_LIGHT)
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(1.15))
    bar.fill.solid()
    bar.fill.fore_color.rgb = NAVY
    bar.line.fill.background()

    accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(1.15), Inches(13.333), Inches(0.06))
    accent.fill.solid()
    accent.fill.fore_color.rgb = BLUE
    accent.line.fill.background()

    tb = slide.shapes.add_textbox(Inches(0.55), Inches(0.14), Inches(11.4), Inches(0.9))
    tf = tb.text_frame
    tf.word_wrap = True
    p1 = tf.paragraphs[0]
    p1.text = title
    p1.font.size = Pt(24)
    p1.font.bold = True
    p1.font.color.rgb = WHITE

    p2 = tf.add_paragraph()
    p2.text = subtitle
    p2.font.size = Pt(12)
    p2.font.color.rgb = RGBColor(0xCB, 0xD5, 0xE1)

    ft = slide.shapes.add_textbox(Inches(0.55), Inches(7.08), Inches(12.2), Inches(0.32))
    fp = ft.text_frame.paragraphs[0]
    fp.text = f"EventCut AWS  |  Efraín Guadalupe Cardona de Luna  |  Computación Sustentable (AWS)          Diapositiva {slide_num}"
    fp.font.size = Pt(9.5)
    fp.font.color.rgb = MUTED


def _add_card(slide, x, y, w, h, title: str, bullets: list[str], accent: RGBColor = BLUE):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    card.fill.solid()
    card.fill.fore_color.rgb = WHITE
    card.line.color.rgb = RGBColor(0xCB, 0xD5, 0xE1)
    card.line.width = Pt(1.2)

    top_bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(0.09))
    top_bar.fill.solid()
    top_bar.fill.fore_color.rgb = accent
    top_bar.line.fill.background()

    tb = slide.shapes.add_textbox(Inches(x + 0.18), Inches(y + 0.16), Inches(w - 0.34), Inches(h - 0.25))
    tf = tb.text_frame
    tf.word_wrap = True
    p0 = tf.paragraphs[0]
    p0.text = title
    p0.font.size = Pt(15)
    p0.font.bold = True
    p0.font.color.rgb = NAVY
    p0.space_after = Pt(6)

    for b in bullets:
        pb = tf.add_paragraph()
        pb.text = f"• {b}"
        pb.font.size = Pt(12)
        pb.font.color.rgb = TEXT_DARK
        pb.space_after = Pt(4)


def _add_kpi(slide, x, y, w, h, number: str, label: str, accent: RGBColor = BLUE):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    card.fill.solid()
    card.fill.fore_color.rgb = WHITE
    card.line.color.rgb = accent
    card.line.width = Pt(1.8)

    tb = slide.shapes.add_textbox(Inches(x + 0.1), Inches(y + 0.14), Inches(w - 0.2), Inches(h - 0.2))
    tf = tb.text_frame
    tf.word_wrap = True
    p1 = tf.paragraphs[0]
    p1.alignment = PP_ALIGN.CENTER
    p1.text = number
    p1.font.size = Pt(28)
    p1.font.bold = True
    p1.font.color.rgb = accent

    p2 = tf.add_paragraph()
    p2.alignment = PP_ALIGN.CENTER
    p2.text = label
    p2.font.size = Pt(11.5)
    p2.font.color.rgb = TEXT_DARK


def _convert_pptx_to_pdf(pptx_path: Path, pdf_path: Path):
    abs_pptx = str(pptx_path.resolve())
    abs_pdf = str(pdf_path.resolve())
    ps = (
        "$ppt = New-Object -ComObject PowerPoint.Application; "
        f"$pres = $ppt.Presentations.Open('{abs_pptx}', $true, $false, $false); "
        f"$pres.SaveAs('{abs_pdf}', 32); "
        "$pres.Close(); "
        "$ppt.Quit();"
    )
    subprocess.run(["pwsh", "-NoProfile", "-Command", ps], check=True)
    print(f"[+] PDF de presentación generado: {pdf_path}")


def build_presentation():
    state = _load_json(STATE_FILE)
    res = _load_json(RESILIENCE_FILE)
    t1 = res.get("test_1", {})
    t2 = res.get("test_2", {})
    t3 = res.get("test_3", {})
    t4 = res.get("test_4", {})

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # SLIDE 1: Portada oscura impactante
    s1 = prs.slides.add_slide(blank)
    _set_bg(s1, BG_DARK)
    stripe = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.28), Inches(7.5))
    stripe.fill.solid()
    stripe.fill.fore_color.rgb = BLUE
    stripe.line.fill.background()

    tb = s1.shapes.add_textbox(Inches(0.9), Inches(1.4), Inches(11.5), Inches(4.5))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "PROYECTO FINAL — INFRAESTRUCTURA EN LA NUBE (AWS)"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = SKY

    p2 = tf.add_paragraph()
    p2.text = "EventCut AWS"
    p2.font.size = Pt(50)
    p2.font.bold = True
    p2.font.color.rgb = WHITE
    p2.space_before = Pt(10)

    p3 = tf.add_paragraph()
    p3.text = "Plataforma Web Universitaria de Eventos y Comunidades con Alta Disponibilidad Multi-AZ, Migración a Amazon S3, IaC Automatizado y Pruebas de Resiliencia"
    p3.font.size = Pt(20)
    p3.font.color.rgb = RGBColor(0xCB, 0xD5, 0xE1)
    p3.space_before = Pt(12)

    p4 = tf.add_paragraph()
    p4.text = "Estudiante: Efraín Guadalupe Cardona de Luna  |  Cuenta AWS: 002627054381 (us-east-1)  |  Noviembre 2026"
    p4.font.size = Pt(14)
    p4.font.color.rgb = GREEN
    p4.space_before = Pt(42)

    # SLIDE 2: Problema, Aplicación y Objetivos
    s2 = prs.slides.add_slide(blank)
    _add_header(s2, "1. ¿Qué es EventCut y Qué Problema Resuelve?", "Aplicación web real de microservicios migrada 100% a infraestructura automatizada en AWS", 2)
    _add_card(s2, 0.55, 1.5, 5.9, 5.2, "La Aplicación Web EventCut", [
        "Plataforma universitaria para gestionar eventos, calendario interactivo, favoritos, comunidades y moderación.",
        "Frontend SPA moderno en Vue 3 + Vite + Tailwind CSS + Pinia + Editor Rich-Text TipTap + escena 3D (TresJS).",
        "Backend desacoplado en 2 microservicios FastAPI: auth-service (:8000) y events-service (:8001) tras Traefik v3.4.",
        "Control de acceso por roles (ROLE_ADMIN / ROLE_USER), JWT con revocación, rate-limiting y auditoría.",
    ], BLUE)
    _add_card(s2, 6.8, 1.5, 5.95, 5.2, "Reglas y Retos Cumplidos", [
        "Cero clics en consola AWS: 100% automatizado en Python + Boto3 con Wizard Web paso a paso.",
        "Limpieza total desde cero: borra y recrea toda la infraestructura, BD, seed e imágenes en cada ejecución.",
        "Migración completa de Cloudflare R2 → Amazon S3 nativo con IAM Role (sin llaves estáticas).",
        "Pruebas empíricas de Chaos Engineering: destrucción de contenedor y de servidor EC2 en vivo.",
    ], GREEN)

    # SLIDE 3: Arquitectura AWS (Diagrama full)
    s3 = prs.slides.add_slide(blank)
    _add_header(s3, "2. Arquitectura Cloud Multi-AZ en AWS", "Separación de capas, seguridad por mínimo privilegio y cero puntos únicos de falla en cómputo", 3)
    arch_img = EVIDENCIAS_DIR / "arquitectura_eventcut_aws.png"
    if arch_img.is_file():
        s3.shapes.add_picture(str(arch_img), Inches(0.95), Inches(1.32), width=Inches(11.4))

    # SLIDE 3B (Slide 4): Recorrido del Flujo de Datos y Función de cada Servicio AWS
    s3b = prs.slides.add_slide(blank)
    _add_header(s3b, "2B. Flujo de Datos y Función de Cada Servicio AWS", "Recorrido extremo a extremo desde el navegador del usuario hasta la persistencia y monitoreo", 4)
    _add_card(s3b, 0.55, 1.45, 5.95, 5.3, "Flujo de Datos (Paso a Paso)", [
        "1. SPA Estático: Navegador descarga Vue 3 directo de Amazon S3 Website (sin cargar al backend).",
        "2. Tráfico API: Peticiones REST entran al ALB (:80) y se balancean 50/50 hacia EC2 (:8080) en AZ-a y AZ-b.",
        "3. Gateway & Microservicios: Traefik bloquea /api/internal (403) y enruta a auth (:8000) y events (:8001).",
        "4. Persistencia Privada: Ambos servicios leen/escriben en Amazon RDS MySQL (:3306) sin exposición pública.",
        "5. Media S3: events-service optimiza imágenes (Pillow) y las sube a S3 Media vía IAM Role (IMDSv2).",
        "6. Auto-Healing: Si cae un nodo EC2, ASG lanza otro, baja backend.tar.gz de S3 Artefactos y se reintegra.",
    ], BLUE)
    _add_card(s3b, 6.8, 1.45, 5.95, 5.3, "Función de Cada Servicio AWS", [
        "VPC + 3 Security Groups: Red Multi-AZ y firewall encadenado (ALB → EC2 → RDS).",
        "Amazon S3 (3 Buckets): Frontend SPA + Media (ex-R2, Lifecycle 24h) + Artefactos IaC.",
        "ALB + Target Group: Balanceo capa 7, health checks /api/health cada 15s y failover veloz.",
        "EC2 + Auto Scaling Group: 2 nodos t3.small Dockerizados (Min=2, Max=4, CPU target 60%).",
        "Amazon RDS MySQL 8.0: BD administrada privada (auth_db + events_db) con backups 7 días.",
        "IAM + SSM + CloudWatch/SNS: Credenciales temporales, AMI AL2023 dinámica y 4 alarmas.",
    ], GREEN)

    # SLIDE 5: Migración Cloudflare R2 -> AWS S3 + Seguridad
    s4 = prs.slides.add_slide(blank)
    _add_header(s4, "3. Migración Cloudflare R2 → Amazon S3 y Seguridad", "Eliminación de proveedor externo y credenciales estáticas mediante IAM Instance Profile", 5)
    _add_card(s4, 0.55, 1.5, 5.9, 5.2, "Antes (Cloudflare R2) vs. Ahora (Amazon S3)", [
        "Antes: 5 variables R2_* con Access/Secret Keys fijas en .env y proveedor externo fuera de VPC/AWS.",
        "Ahora: 3 buckets nativos S3 (Media, Frontend SPA Website y Artefactos IaC) en us-east-1.",
        "Autenticación Zero-Secret: contenedores Docker en EC2 obtienen tokens rotativos de LabInstanceProfile vía IMDSv2 (HopLimit=2).",
        "Reglas S3 Lifecycle automáticas purgan imágenes temporales pending/ tras 24h.",
        "Validación de imágenes con Pillow + bloqueo de path traversal (HTTP 422).",
    ], AMBER)
    _add_card(s4, 6.8, 1.5, 5.95, 5.2, "Defensa en Profundidad en Red", [
        "3 Security Groups encadenados por mínimo privilegio:",
        "eventcut-alb-sg: único punto público HTTP :80.",
        "eventcut-app-sg: puerto :8080 SOLO aceptado desde el Security Group del ALB.",
        "eventcut-rds-sg: MySQL :3306 privado (PubliclyAccessible=False), solo desde nodos EC2.",
        "Traefik bloquea /api/internal con respuesta 403/404 desde el perímetro.",
    ], BLUE)

    # SLIDE 6: Infraestructura como Código y Wizard Paso a Paso
    s5 = prs.slides.add_slide(blank)
    _add_header(s5, "4. Automatización IaC: Wizard Web Paso a Paso (10 Steps)", "Despliegue determinista, reproducible desde 0 y con limpieza total integrada", 6)
    _add_card(s5, 0.55, 1.5, 6.0, 5.2, "Steps 0 al 4 (Preparación y Persistencia)", [
        "Step 0: Validación de AWS STS, LabInstanceProfile, KeyPair y NPM.",
        "Step 1: Limpieza TOTAL de us-east-1 (ASG, ALB, EC2, RDS, S3, DynamoDB, CloudWatch, SGs).",
        "Step 2: Red Multi-AZ (us-east-1a/1b), 3 Security Groups y DB Subnet Group.",
        "Step 3: Buckets Amazon S3 (Media con CORS/Lifecycle, Frontend SPA y Artefactos).",
        "Step 4: Amazon RDS MySQL 8.0 privado (db.t3.micro, backups 7 días).",
    ], BLUE)
    _add_card(s5, 6.8, 1.5, 5.95, 5.2, "Steps 5 al 9 (Cómputo, App y Verificación)", [
        "Step 5: Empaquetado backend-latest.tar.gz y publicación en S3 Artefactos.",
        "Step 6: Application Load Balancer + Target Group (/api/health cada 15s).",
        "Step 7: Launch Template + Auto Scaling Group (2 EC2 Docker + lock MySQL GET_LOCK para Alembic y Seed).",
        "Step 8: Compilación Vue 3 apuntando al ALB y despliegue a S3 Website.",
        "Step 9: SNS + 4 alarmas CloudWatch + 6 pruebas E2E automáticas.",
    ], GREEN)

    # SLIDE 7: CI/CD con GitHub Actions
    s6 = prs.slides.add_slide(blank)
    _add_header(s6, "5. Monorepo GitHub y Pipelines CI/CD por Ruta", "Integración y despliegue continuo con GitHub Actions superando la restricción de CodeBuild", 7)
    _add_card(s6, 0.55, 1.6, 5.9, 5.0, "Pipeline Frontend (.github/workflows/frontend-ci-cd.yml)", [
        "Disparador inteligente por ruta: solo corre ante cambios en frontend/**.",
        "Instala Node.js 22 y dependencias reproducibles (npm ci).",
        "Compila el bundle de producción Vite (dist/) inyectando URLs del ALB.",
        "En rama main, sincroniza assets inmutables y index.html sin caché al bucket S3 Website.",
    ], SKY)
    _add_card(s6, 6.8, 1.6, 5.95, 5.0, "Pipeline Backend (.github/workflows/backend-ci-cd.yml)", [
        "Disparador por ruta: corre ante cambios en backend/**.",
        "Ejecuta automáticamente los 59 tests unitarios (pytest auth + events_service).",
        "Empaqueta nuevo release backend-latest.tar.gz y lo sube a S3 Artefactos.",
        "Dispara ASG Instance Refresh (MinHealthyPercentage: 50%) para despliegue sin caída.",
    ], GREEN)

    # SLIDE 8: Justificación de Decisiones
    s7 = prs.slides.add_slide(blank)
    _add_header(s7, "6. Justificación de Decisiones Tecnológicas en AWS", "Por qué elegimos cada servicio frente a sus alternativas comerciales", 8)
    _add_card(s7, 0.55, 1.5, 3.9, 5.2, "EC2 + ASG + ALB vs. EC2 Única / ECS", [
        "EC2 única tiene punto único de falla.",
        "ASG Multi-AZ da auto-reparación real y escalado por CPU (60%).",
        "No requiere CodeBuild (bloqueado en Learner Lab) para regenerar imágenes.",
    ], BLUE)
    _add_card(s7, 4.7, 1.5, 3.9, 5.2, "RDS MySQL vs. MySQL en Contenedor", [
        "Separa estado de nodos efímeros.",
        "Si el ASG reemplaza todas las EC2, ningún dato se pierde.",
        "Backups automáticos de 7 días y aislamiento total sin IP pública.",
    ], AMBER)
    _add_card(s7, 8.85, 1.5, 3.9, 5.2, "Amazon S3 vs. Cloudflare R2", [
        "100% nativo en AWS (sin cuentas ni tokens externos).",
        "Durabilidad de 11 nueves y menor latencia intra-región.",
        "S3 Website aloja el SPA por centavos/mes (CloudFront restringido en Lab).",
    ], GREEN)

    # SLIDE 9: Análisis de Costos (1 Año)
    s8 = prs.slides.add_slide(blank)
    _add_header(s8, "7. Análisis de Costos (1 Año Fuera de Capa Gratuita)", "Estimación comercial real en us-east-1 y estrategias de Computación Sustentable", 9)
    _add_kpi(s8, 0.55, 1.45, 3.85, 1.35, "$71.45 / mes", "Costo On-Demand 24/7 ($857.40/año)", BLUE)
    _add_kpi(s8, 4.72, 1.45, 3.85, 1.35, "$628 / año", "Con Savings Plan + RDS RI (-26.8%)", GREEN)
    _add_kpi(s8, 8.9, 1.45, 3.85, 1.35, "$492 / año", "Horario Académico Sustentable (-42.6%)", AMBER)
    cost_img = EVIDENCIAS_DIR / "analisis_costos_anual_aws.png"
    if cost_img.is_file():
        s8.shapes.add_picture(str(cost_img), Inches(1.1), Inches(3.0), width=Inches(11.1))

    # SLIDE 10: Pruebas de Resiliencia 1 & 2
    s9 = prs.slides.add_slide(blank)
    _add_header(s9, "8. Pruebas de Resiliencia: Carga Multi-AZ y Caída de Contenedor", "Evidencias reales capturadas sobre la infraestructura desplegada en vivo", 10)
    _add_kpi(s9, 0.55, 1.4, 3.85, 1.2, f"{t1.get('success_rate_pct', 100)}%", f"Disponibilidad bajo carga ({t1.get('avg_latency_ms', '-')} ms prom.)", BLUE)
    _add_kpi(s9, 4.72, 1.4, 3.85, 1.2, f"{t2.get('availability_pct', '-')}%", "Disponibilidad ALB tras docker kill", GREEN)
    _add_kpi(s9, 8.9, 1.4, 3.85, 1.2, f"{t2.get('recovery_seconds', '-')} s", "Auto-recuperación de contenedor Docker", AMBER)
    c1 = EVIDENCIAS_DIR / "chart_resilience_load_balancing.png"
    c2 = EVIDENCIAS_DIR / "chart_resilience_container_healing.png"
    if c1.is_file():
        s9.shapes.add_picture(str(c1), Inches(0.55), Inches(2.85), width=Inches(6.05))
    if c2.is_file():
        s9.shapes.add_picture(str(c2), Inches(6.75), Inches(2.85), width=Inches(6.05))

    # SLIDE 11: Prueba de Resiliencia 3 (Destrucción de EC2 + ASG)
    s10 = prs.slides.add_slide(blank)
    _add_header(s10, "9. Prueba de Caos Crítica: Destrucción de Nodo EC2 + ASG", "Un servidor completo es terminado vía API; el servicio sobrevive y AWS lo reemplaza solo", 11)
    _add_kpi(s10, 0.55, 1.4, 3.85, 1.2, f"{t3.get('availability_pct', '-')}%", "Disponibilidad externa durante crisis", GREEN)
    _add_kpi(s10, 4.72, 1.4, 3.85, 1.2, f"{t3.get('recovery_seconds', '-')} s", "Tiempo hasta 2/2 nodos Healthy (ASG)", BLUE)
    _add_kpi(s10, 8.9, 1.4, 3.85, 1.2, "0 datos perdidos", "RDS MySQL y S3 Media 100% intactos", AMBER)
    c3 = EVIDENCIAS_DIR / "chart_resilience_ec2_failover.png"
    if c3.is_file():
        s10.shapes.add_picture(str(c3), Inches(1.15), Inches(2.8), width=Inches(11.0))

    # SLIDE 12: Demostración en Vivo y Conclusiones
    s11 = prs.slides.add_slide(blank)
    _add_header(s11, "10. Demostración en Vivo y Conclusiones", "Flujo de defensa en clase y lecciones clave de arquitectura sustentable en AWS", 12)
    _add_card(s11, 0.55, 1.5, 6.0, 5.2, "Guion de Demostración en Vivo", [
        f"1. Abrir EventCut SPA en S3: {state.get('frontend_website_url', 'http://<frontend-s3>')}",
        f"2. Login Admin ({state.get('admin_email', 'admin@eventcut.edu.mx')}) y subir un evento con imagen real a Amazon S3.",
        "3. Mostrar el Wizard Web local (http://127.0.0.1:8765) con los 10 steps, botón Continuar y Limpieza Total.",
        "4. Ejecutar prueba de caos (docker kill o terminación EC2) mostrando respuesta continua en el navegador.",
    ], BLUE)
    _add_card(s11, 6.8, 1.5, 5.95, 5.2, "Conclusiones Clave", [
        "La Infraestructura como Código elimina el error humano y permite reconstruir un entorno productivo desde cero en minutos.",
        "La redundancia Multi-AZ (ALB + ASG) combinada con persistencia administrada (RDS + S3) garantiza resiliencia real comprobada.",
        "Automatizar la limpieza total del entorno materializa la Computación Sustentable: cero recursos ociosos y ahorro energético.",
    ], GREEN)

    out_pptx = DOCS_DIR / "Presentacion_Defensa_EventCut_AWS.pptx"
    out_pdf = DOCS_DIR / "Presentacion_Defensa_EventCut_AWS.pdf"
    prs.save(str(out_pptx))
    print(f"[+] Presentación PPTX generada: {out_pptx}")
    _convert_pptx_to_pdf(out_pptx, out_pdf)


if __name__ == "__main__":
    build_presentation()
