"""
Genera diagramas de alta resolución para la documentación y presentación de EventCut AWS:
  1. docs/evidencias/arquitectura_eventcut_aws.png — Diagrama de arquitectura completo
  2. docs/evidencias/analisis_costos_anual_aws.png — Análisis de costos mensual y anual (1 año sin capa gratuita)
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

DOCS_DIR = Path(__file__).resolve().parent
EVIDENCIAS_DIR = DOCS_DIR / "evidencias"


def _box(ax, x, y, w, h, title, subtitle="", facecolor="#ffffff", edgecolor="#1e40af", title_color="#0f172a", lw=1.8, radius=0.18, fontsize=9.5, subsize=7.6):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.06,rounding_size={radius}",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=lw,
        zorder=3,
    )
    ax.add_patch(patch)
    if subtitle:
        ax.text(x + w / 2, y + h * 0.66, title, ha="center", va="center", fontsize=fontsize, fontweight="bold", color=title_color, zorder=4)
        ax.text(x + w / 2, y + h * 0.30, subtitle, ha="center", va="center", fontsize=subsize, color="#334155", zorder=4)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=fontsize, fontweight="bold", color=title_color, zorder=4)


def _arrow(ax, x1, y1, x2, y2, label="", color="#334155", rad=0.0, lx_off=0, ly_off=0.14):
    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops=dict(arrowstyle="-|>,head_length=0.65,head_width=0.38", color=color, lw=1.6, connectionstyle=f"arc3,rad={rad}"),
        zorder=5,
    )
    if label:
        mx, my = (x1 + x2) / 2 + lx_off, (y1 + y2) / 2 + ly_off
        ax.text(mx, my, label, fontsize=7.2, fontweight="bold", color=color, ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.88), zorder=6)


def generate_architecture_diagram() -> Path:
    EVIDENCIAS_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(14, 8.2), dpi=220)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8.5)
    ax.axis("off")
    fig.patch.set_facecolor("#f8fafc")

    # Título superior
    ax.text(7.0, 8.18, "Arquitectura Cloud de EventCut en Amazon Web Services (us-east-1)",
            ha="center", va="center", fontsize=14, fontweight="bold", color="#0f172a")
    ax.text(7.0, 7.86, "Alta Disponibilidad Multi-AZ  |  Migración Cloudflare R2 → Amazon S3  |  IaC Automatizado (Python + Boto3)",
            ha="center", va="center", fontsize=9.5, color="#475569")

    # Marco AWS Cloud
    aws_frame = FancyBboxPatch((2.6, 0.35), 11.1, 7.15, boxstyle="round,pad=0.1,rounding_size=0.22",
                               facecolor="#ffffff", edgecolor="#f59e0b", linewidth=2.2, linestyle="-", zorder=1)
    ax.add_patch(aws_frame)
    ax.text(2.85, 7.3, "AWS Cloud — Cuenta 002627054381 (Región us-east-1)", fontsize=9.5, fontweight="bold", color="#b45309", zorder=2)

    # Marco VPC
    vpc_frame = FancyBboxPatch((2.85, 1.95), 7.85, 4.95, boxstyle="round,pad=0.08,rounding_size=0.2",
                               facecolor="#eff6ff", edgecolor="#2563eb", linewidth=1.6, linestyle="--", zorder=1)
    ax.add_patch(vpc_frame)
    ax.text(3.05, 6.72, "Amazon VPC (Multi-AZ: us-east-1a & us-east-1b)", fontsize=8.8, fontweight="bold", color="#1d4ed8", zorder=2)

    # Columna izquierda: Usuarios & DevOps CI/CD
    _box(ax, 0.25, 5.2, 2.0, 1.3, "Usuarios Web", "Navegador (Estudiantes\ny Administradores)", facecolor="#e0f2fe", edgecolor="#0284c7")
    _box(ax, 0.25, 2.7, 2.0, 1.35, "GitHub Actions", "Monorepo CI/CD\n(pytest + Vite build +\nS3 sync + ASG refresh)", facecolor="#f3e8ff", edgecolor="#7c3aed")
    _box(ax, 0.25, 0.55, 2.0, 1.35, "Wizard Web IaC", "Python + Boto3 Local\n10 Steps + Limpieza 0\n+ Chaos Suite", facecolor="#dcfce7", edgecolor="#16a34a")

    # ALB
    _box(ax, 3.1, 4.0, 1.95, 1.45, "Application\nLoad Balancer", "eventcut-alb (:80)\nSG: eventcut-alb-sg\nHealth: /api/health", facecolor="#dbeafe", edgecolor="#1d4ed8")

    # Auto Scaling Group Frame
    asg_frame = FancyBboxPatch((5.35, 2.25), 3.15, 4.25, boxstyle="round,pad=0.06,rounding_size=0.16",
                               facecolor="#f0fdf4", edgecolor="#16a34a", linewidth=1.5, linestyle="-", zorder=2)
    ax.add_patch(asg_frame)
    ax.text(6.92, 6.32, "Auto Scaling Group (Min:2 / Max:4)", ha="center", fontsize=8.2, fontweight="bold", color="#15803d", zorder=3)

    # EC2 Node 1 (AZ-a)
    _box(ax, 5.55, 4.45, 2.75, 1.6, "EC2 Nodo 1 (us-east-1a)", "t3.small | Docker Compose\nTraefik(:8080) → Auth(:8000)\n+ Events(:8001) | LabProfile", facecolor="#ffffff", edgecolor="#16a34a", fontsize=8.8, subsize=7.2)

    # EC2 Node 2 (AZ-b)
    _box(ax, 5.55, 2.48, 2.75, 1.6, "EC2 Nodo 2 (us-east-1b)", "t3.small | Docker Compose\nTraefik(:8080) → Auth(:8000)\n+ Events(:8001) | LabProfile", facecolor="#ffffff", edgecolor="#16a34a", fontsize=8.8, subsize=7.2)

    # RDS MySQL (Privado en VPC)
    _box(ax, 8.75, 3.35, 1.75, 2.15, "Amazon RDS\nMySQL 8.0", "db.t3.micro (Privada)\nSG: eventcut-rds-sg\nSolo :3306 desde App\neventcut_auth_db\neventcut_events_db", facecolor="#fef3c7", edgecolor="#d97706", fontsize=8.8, subsize=7.0)

    # Columna derecha (Servicios Administrados AWS fuera de VPC)
    _box(ax, 11.05, 5.6, 2.4, 1.35, "Amazon S3\nFrontend SPA", "Static Website Hosting\nVue 3 + Vite + TresJS\nFallback SPA index.html", facecolor="#ecfeff", edgecolor="#0891b2", fontsize=8.8, subsize=7.2)
    _box(ax, 11.05, 3.85, 2.4, 1.4, "Amazon S3\nMedia Bucket", "Migrado de Cloudflare R2\nWebP + CORS + Lifecycle\nAuth vía LabInstanceProfile", facecolor="#fff7ed", edgecolor="#ea580c", fontsize=8.8, subsize=7.2)
    _box(ax, 11.05, 2.15, 2.4, 1.3, "Amazon S3\nArtefactos IaC", "Bucket Privado\nbackend-latest.tar.gz\nBootstrap de ASG", facecolor="#f1f5f9", edgecolor="#475569", fontsize=8.8, subsize=7.2)

    # Banda inferior AWS: Observabilidad
    _box(ax, 3.1, 0.58, 4.4, 1.05, "Amazon CloudWatch Alarms", "4 Alarmas: UnHealthyHosts, HTTP 5XX, ASG CPU>75%, RDS CPU>80%", facecolor="#fdf2f8", edgecolor="#db2777", fontsize=8.8, subsize=7.2)
    _box(ax, 8.2, 0.58, 5.25, 1.05, "Amazon SNS (eventcut-alerts) & IAM (LabRole / LabInstanceProfile)", "Alertas operativas en tiempo real + Credenciales temporales IMDSv2 sin llaves fijas", facecolor="#f5f3ff", edgecolor="#7c3aed", fontsize=8.5, subsize=7.1)

    # Flechas de flujo
    _arrow(ax, 2.25, 6.25, 11.05, 6.55, "1. HTTP SPA (Vue 3)", color="#0891b2", rad=-0.11, lx_off=-0.4, ly_off=0.52)
    _arrow(ax, 2.25, 5.5, 3.1, 4.9, "2. API REST (:80)", color="#1d4ed8", ly_off=0.24)
    _arrow(ax, 5.05, 4.95, 5.55, 5.25, ":8080", color="#15803d", ly_off=0.18)
    _arrow(ax, 5.05, 4.45, 5.55, 3.45, ":8080", color="#15803d", ly_off=-0.2)
    _arrow(ax, 8.3, 5.1, 8.75, 4.75, ":3306", color="#b45309", ly_off=0.18)
    _arrow(ax, 8.3, 3.45, 8.75, 4.0, ":3306", color="#b45309", ly_off=-0.22)
    _arrow(ax, 8.3, 5.7, 11.05, 4.9, "Put/Copy/Del S3", color="#ea580c", rad=-0.16, lx_off=0.15, ly_off=0.45)
    _arrow(ax, 11.05, 2.7, 8.3, 2.7, "Bootstrap tar.gz", color="#475569", ly_off=-0.2)
    _arrow(ax, 2.25, 3.05, 11.05, 2.45, "CI/CD Deploy", color="#7c3aed", rad=0.21, lx_off=-0.1, ly_off=-0.92)
    _arrow(ax, 2.25, 1.1, 3.1, 1.1, "Boto3 API", color="#16a34a", ly_off=0.2)
    _arrow(ax, 7.5, 1.1, 8.2, 1.1, "Notifica", color="#db2777", ly_off=0.18)

    out_path = EVIDENCIAS_DIR / "arquitectura_eventcut_aws.png"
    plt.tight_layout()
    fig.savefig(out_path, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[+] Diagrama de arquitectura generado: {out_path}")
    return out_path


def generate_cost_chart() -> Path:
    EVIDENCIAS_DIR.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    services = [
        "EC2 t3.small (x2)\n+ 30GB gp3",
        "Application\nLoad Balancer",
        "RDS MySQL 8.0\ndb.t3.micro + 20GB",
        "Amazon S3\n(3 Buckets + Req)",
        "Data Transfer &\nCloudWatch/SNS",
    ]
    monthly_usd = [32.70, 18.20, 14.80, 1.25, 4.50]  # Total: $71.45/mes -> $857.40/año On-Demand
    colors = ["#2563eb", "#7c3aed", "#d97706", "#ea580c", "#0d9488"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6), dpi=200)

    bars = ax1.barh(services[::-1], monthly_usd[::-1], color=colors[::-1], height=0.55)
    ax1.set_title("Desglose Mensual Estimado (USD — Fuera de Capa Gratuita)", fontweight="bold", fontsize=10.5)
    ax1.set_xlabel("Costo Mensual Estimado (USD)")
    ax1.set_xlim(0, 42)
    for b in bars:
        val = b.get_width()
        ax1.text(val + 0.8, b.get_y() + b.get_height() / 2, f"${val:.2f}/mes", va="center", fontweight="bold", fontsize=9)

    scenarios = ["On-Demand\n(24/7 Actual)", "Savings Plan 1 Año\n(EC2 + RDS RI)", "Horario Académico\n(12h/día L-V)"]
    annual_usd = [round(sum(monthly_usd) * 12, 2), 628.00, 492.00]
    bar_colors = ["#1e40af", "#059669", "#0284c7"]
    bars2 = ax2.bar(scenarios, annual_usd, color=bar_colors, width=0.5)
    ax2.set_title("Proyección de Costo Anual (12 Meses — us-east-1)", fontweight="bold", fontsize=10.5)
    ax2.set_ylabel("Costo Anual Estimado (USD)")
    ax2.set_ylim(0, 1020)
    for b in bars2:
        val = b.get_height()
        ax2.text(b.get_x() + b.get_width() / 2, val + 18, f"${val:,.2f} USD", ha="center", fontweight="bold", fontsize=9.5)

    plt.tight_layout()
    out_path = EVIDENCIAS_DIR / "analisis_costos_anual_aws.png"
    fig.savefig(out_path)
    plt.close(fig)
    print(f"[+] Gráfica de análisis de costos generada: {out_path}")
    return out_path


if __name__ == "__main__":
    generate_architecture_diagram()
    generate_cost_chart()
