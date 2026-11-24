"""
Seed idempotente para EventCut en Amazon RDS MySQL + imágenes reales en Amazon S3.
Soporta ejecución modular por microservicio:
  - python /app/scripts/seed_aws_db.py --mode ensure-dbs
  - python /app/scripts/seed_aws_db.py --mode auth
  - python /app/scripts/seed_aws_db.py --mode events
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

SEED_ADMIN_ID = "00000000-0000-4000-8000-000000000001"
SEED_DEMO_ID = "00000000-0000-4000-8000-000000000002"

CATEGORIES_SEED = [
    ("academico", "Académico"),
    ("deportes", "Deportes"),
    ("cultura-y-arte", "Cultura y Arte"),
    ("vida-estudiantil", "Vida Estudiantil"),
    ("talleres-y-cursos", "Talleres y Cursos"),
    ("desarrollo-profesional", "Desarrollo Profesional"),
    ("tecnologia-e-innovacion", "Tecnología e Innovación"),
    ("salud-y-bienestar", "Salud y Bienestar"),
    ("voluntariado", "Voluntariado y Acción Social"),
    ("social-y-networking", "Social y Networking"),
    ("orientacion-y-bienvenida", "Orientación y Bienvenida"),
    ("conferencias-y-seminarios", "Conferencias y Seminarios"),
]


def ensure_databases_exist() -> None:
    import pymysql

    host = os.getenv("MYSQL_HOST", "localhost")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "root")
    auth_db = os.getenv("AUTH_MYSQL_DB", "eventcut_auth_db")
    events_db = os.getenv("EVENTS_MYSQL_DB", "eventcut_events_db")

    conn = pymysql.connect(host=host, port=port, user=user, password=password, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{auth_db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{events_db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        print(f"[+] Bases de datos aseguradas en RDS: {auth_db}, {events_db}")
    finally:
        conn.close()


def seed_users() -> tuple[str, str]:
    from auth.db.session import SessionLocal as AuthSessionLocal
    from auth.models.user import User
    from auth.security.passwords import hash_password

    admin_email = os.getenv("SEED_ADMIN_EMAIL", "admin@eventcut.edu.mx")
    admin_pass = os.getenv("SEED_ADMIN_PASSWORD", "AdminEventCut2026!")
    demo_email = os.getenv("SEED_DEMO_EMAIL", "demo@eventcut.edu.mx")
    demo_pass = os.getenv("SEED_DEMO_PASSWORD", "DemoEventCut2026!")

    db = AuthSessionLocal()
    try:
        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            admin = User(
                id=SEED_ADMIN_ID,
                username="admin_eventcut",
                email=admin_email,
                password=hash_password(admin_pass),
                first_name="Administrador",
                last_name="EventCut",
                role="ROLE_ADMIN",
                active=True,
                email_verified=True,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            print(f"[+] Usuario Admin creado: {admin_email} (id={admin.id})")
        else:
            print(f"[i] Usuario Admin ya existe: {admin_email} (id={admin.id})")

        demo = db.query(User).filter(User.email == demo_email).first()
        if not demo:
            demo = User(
                id=SEED_DEMO_ID,
                username="estudiante_demo",
                email=demo_email,
                password=hash_password(demo_pass),
                first_name="Efrain",
                last_name="Cardona",
                role="ROLE_USER",
                active=True,
                email_verified=True,
            )
            db.add(demo)
            db.commit()
            db.refresh(demo)
            print(f"[+] Usuario Demo creado: {demo_email} (id={demo.id})")
        else:
            print(f"[i] Usuario Demo ya existe: {demo_email} (id={demo.id})")

        return admin.id, demo.id
    finally:
        db.close()


def _render_banner_webp(
    title: str,
    subtitle: str,
    bg_top: tuple[int, int, int],
    bg_bottom: tuple[int, int, int],
) -> bytes:
    from PIL import Image, ImageDraw

    width, height = 1200, 630
    img = Image.new("RGB", (width, height), bg_top)
    draw = ImageDraw.Draw(img)

    for y in range(height):
        ratio = y / max(height - 1, 1)
        r = int(bg_top[0] * (1 - ratio) + bg_bottom[0] * ratio)
        g = int(bg_top[1] * (1 - ratio) + bg_bottom[1] * ratio)
        b = int(bg_top[2] * (1 - ratio) + bg_bottom[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    draw.ellipse([width - 360, -120, width + 80, 320], outline=(255, 255, 255), width=4)
    draw.ellipse([-120, height - 280, 260, height + 100], outline=(255, 255, 255), width=3)
    draw.rounded_rectangle([70, 80, 330, 130], radius=24, fill=(255, 255, 255))
    draw.text((98, 97), "EVENTCUT AWS CLOUD", fill=bg_top)
    draw.text((70, 230), title[:60], fill=(255, 255, 255))
    draw.text((70, 290), subtitle[:78], fill=(226, 232, 240))
    draw.text((70, 520), "Alojado en Amazon S3  |  FastAPI Microservices + Amazon RDS MySQL", fill=(203, 213, 225))

    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=85)
    return buf.getvalue()


def _upload_seed_image(s3_client, bucket: str, public_host: str, key: str, title: str, subtitle: str, c1, c2) -> str:
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
    except Exception:
        data = _render_banner_webp(title, subtitle, c1, c2)
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType="image/webp",
            CacheControl="public, max-age=31536000, immutable",
        )
        print(f"[+] Imagen seed subida a S3: s3://{bucket}/{key}")
    return f"{public_host}/{key}"


def seed_events_domain(admin_id: str = SEED_ADMIN_ID, demo_id: str = SEED_DEMO_ID) -> None:
    import boto3

    from events_service.app.db.session import SessionLocal as EventsSessionLocal
    from events_service.app.models.category import Category
    from events_service.app.models.community import Community, CommunityStatus
    from events_service.app.models.community_event import CommunityEvent
    from events_service.app.models.event import Event
    from events_service.app.services.storage_service import get_aws_region, get_bucket_name, get_public_host

    bucket = get_bucket_name()
    region = get_aws_region()
    public_host = get_public_host()
    s3_client = boto3.client("s3", region_name=region) if bucket else None

    def _img(key: str, title: str, subtitle: str, c1: tuple, c2: tuple) -> str | None:
        if not s3_client or not bucket or not public_host:
            return None
        return _upload_seed_image(s3_client, bucket, public_host, key, title, subtitle, c1, c2)

    db = EventsSessionLocal()
    try:
        cat_map: dict[str, Category] = {}
        for slug, name in CATEGORIES_SEED:
            existing = db.query(Category).filter(Category.slug == slug).first()
            if not existing:
                existing = Category(slug=slug, name=name)
                db.add(existing)
                db.flush()
            cat_map[slug] = existing
        db.commit()
        print(f"[+] Categorías aseguradas: {len(cat_map)}")

        communities_spec = [
            {
                "name": "Departamento de Ciencias Computacionales Oficial",
                "description": (
                    "<p>Comunidad oficial enfocada en desarrollo de software, arquitectura en la nube AWS, "
                    "ciberseguridad, inteligencia artificial y proyectos estudiantiles de alto impacto.</p>"
                ),
                "contact_email": "computacion@eventcut.edu.mx",
                "category_slug": "tecnologia-e-innovacion",
                "owner_id": admin_id,
                "img_key": "comunidad/seed-dcc-oficial.webp",
                "colors": ((15, 23, 42), (37, 99, 235)),
            },
            {
                "name": "Club de Esports y Desarrollo de Videojuegos CUT",
                "description": (
                    "<p>Espacio estudiantil para torneos competitivos, game jams, talleres de Unity/Godot "
                    "y transmisión de competencias universitarias.</p>"
                ),
                "contact_email": "esports@eventcut.edu.mx",
                "category_slug": "vida-estudiantil",
                "owner_id": demo_id,
                "img_key": "comunidad/seed-esports-cut.webp",
                "colors": ((88, 28, 135), (219, 39, 119)),
            },
        ]

        comm_map: dict[str, Community] = {}
        for spec in communities_spec:
            comm = db.query(Community).filter(Community.name == spec["name"]).first()
            if not comm:
                img_url = _img(spec["img_key"], spec["name"], "Comunidad Universitaria Oficial", *spec["colors"])
                comm = Community(
                    id=str(uuid.uuid4()),
                    name=spec["name"],
                    description=spec["description"],
                    image_url=img_url,
                    owner_id=spec["owner_id"],
                    contact_email=spec["contact_email"],
                    category_id=cat_map[spec["category_slug"]].id,
                    status=CommunityStatus.ACTIVE.value,
                    is_accepted_terms=True,
                    is_active=True,
                )
                db.add(comm)
                db.flush()
                print(f"[+] Comunidad creada: {comm.name}")
            comm_map[spec["name"]] = comm
        db.commit()

        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        events_spec = [
            {
                "title": "ExpoDIT 2026: Innovación, Tecnología y Talento Universitario",
                "description": (
                    "<p>Muestra anual de proyectos de ingeniería, computación en la nube, robótica e "
                    "innovación tecnológica desarrollados por estudiantes y docentes.</p>"
                ),
                "location": "Explanada del Instituto de Energías Renovables",
                "category_slug": "tecnologia-e-innovacion",
                "owner_id": admin_id,
                "start_offset_days": 3,
                "duration_hours": 6,
                "img_key": "events/seed-expodit-2026.webp",
                "colors": ((14, 116, 144), (30, 58, 138)),
                "community": "Departamento de Ciencias Computacionales Oficial",
            },
            {
                "title": "Hackathon Capture The Flag (CTF) Cloud & Security",
                "description": (
                    "<p>Competencia práctica de ciberseguridad, análisis forense, endurecimiento de APIs "
                    "y arquitectura resiliente en AWS.</p>"
                ),
                "location": "Aula Amplia 1 - Edificio de Cómputo",
                "category_slug": "talleres-y-cursos",
                "owner_id": admin_id,
                "start_offset_days": 6,
                "duration_hours": 5,
                "img_key": "events/seed-hackathon-ctf.webp",
                "colors": ((15, 118, 110), (17, 24, 39)),
                "community": "Departamento de Ciencias Computacionales Oficial",
            },
            {
                "title": "Torneo 5v5 Universitario de Esports",
                "description": (
                    "<p>Fase clasificatoria presencial y transmisión en vivo con equipos registrados "
                    "de todas las licenciaturas del centro universitario.</p>"
                ),
                "location": "Salón CRT 201",
                "category_slug": "deportes",
                "owner_id": demo_id,
                "start_offset_days": 8,
                "duration_hours": 4,
                "img_key": "events/seed-torneo-esports.webp",
                "colors": ((109, 40, 217), (190, 24, 93)),
                "community": "Club de Esports y Desarrollo de Videojuegos CUT",
            },
            {
                "title": "Taller Práctico: Infraestructura como Código y Alta Disponibilidad en AWS",
                "description": (
                    "<p>Aprende a desplegar microservicios FastAPI + Vue 3 con Application Load Balancer, "
                    "Auto Scaling Groups, Amazon RDS y Amazon S3 con pruebas de caos en vivo.</p>"
                ),
                "location": "Laboratorio de Redes y Nube 2",
                "category_slug": "conferencias-y-seminarios",
                "owner_id": admin_id,
                "start_offset_days": 11,
                "duration_hours": 3,
                "img_key": "events/seed-taller-aws.webp",
                "colors": ((180, 83, 9), (124, 45, 18)),
                "community": "Departamento de Ciencias Computacionales Oficial",
            },
            {
                "title": "Jornada Universitaria de Salud, Bienestar y Deporte",
                "description": (
                    "<p>Actividades recreativas, nutrición deportiva, pausas activas y orientación integral "
                    "para toda la comunidad estudiantil.</p>"
                ),
                "location": "Polideportivo Central",
                "category_slug": "salud-y-bienestar",
                "owner_id": demo_id,
                "start_offset_days": 14,
                "duration_hours": 4,
                "img_key": "events/seed-salud-bienestar.webp",
                "colors": ((21, 128, 61), (6, 78, 59)),
                "community": None,
            },
        ]

        created_events = 0
        for spec in events_spec:
            existing = db.query(Event).filter(Event.title == spec["title"]).first()
            if not existing:
                start_dt = now + timedelta(days=spec["start_offset_days"], hours=10)
                end_dt = start_dt + timedelta(hours=spec["duration_hours"])
                img_url = _img(spec["img_key"], spec["title"], spec["location"], *spec["colors"])
                ev = Event(
                    id=str(uuid.uuid4()),
                    title=spec["title"],
                    description=spec["description"],
                    image_url=img_url,
                    start_datetime=start_dt,
                    end_datetime=end_dt,
                    location=spec["location"],
                    owner_id=spec["owner_id"],
                    category_id=cat_map[spec["category_slug"]].id,
                    is_active=True,
                )
                db.add(ev)
                db.flush()
                created_events += 1

                if spec["community"] and spec["community"] in comm_map:
                    link = CommunityEvent(
                        community_id=comm_map[spec["community"]].id,
                        event_id=ev.id,
                        status="APPROVED",
                        requested_by=spec["owner_id"],
                        reviewed_by=admin_id,
                        reviewed_at=now,
                    )
                    db.add(link)

        db.commit()
        print(f"[+] Eventos seed creados: {created_events} (total en BD: {db.query(Event).count()})")
    finally:
        db.close()


def _run_with_rds_lock(lock_name: str, fn) -> None:
    """Usa MySQL GET_LOCK en RDS para serializar migraciones/seed entre múltiples nodos EC2 del ASG."""
    import pymysql

    host = os.getenv("MYSQL_HOST", "localhost")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "root")

    conn = pymysql.connect(host=host, port=port, user=user, password=password, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT GET_LOCK(%s, 180)", (lock_name,))
            acquired = cur.fetchone()[0]
            if acquired != 1:
                raise RuntimeError(f"No se pudo adquirir lock distribuido RDS '{lock_name}'")
        print(f"[+] Lock distribuido RDS adquirido: {lock_name}")
        fn()
    finally:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
        except Exception:
            pass
        conn.close()


def _run_alembic(service_dir: str) -> None:
    import subprocess

    cwd = str(BACKEND_ROOT / service_dir)
    print(f"[*] Ejecutando alembic upgrade head en {service_dir}...")
    subprocess.run(["alembic", "-c", "alembic.ini", "upgrade", "head"], cwd=cwd, check=True)
    print(f"[+] Migraciones Alembic aplicadas en {service_dir}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed idempotente de EventCut para AWS RDS + S3")
    parser.add_argument(
        "--mode",
        choices=["ensure-dbs", "auth", "events", "all", "bootstrap-auth", "bootstrap-events"],
        default="all",
    )
    args = parser.parse_args()

    if args.mode == "bootstrap-auth":
        def _job():
            ensure_databases_exist()
            _run_alembic("auth")
            seed_users()
        _run_with_rds_lock("eventcut_bootstrap_auth", _job)
        return

    if args.mode == "bootstrap-events":
        def _job():
            ensure_databases_exist()
            _run_alembic("events_service")
            seed_events_domain()
        _run_with_rds_lock("eventcut_bootstrap_events", _job)
        return

    if args.mode in ("ensure-dbs", "all"):
        ensure_databases_exist()
    if args.mode in ("auth", "all"):
        seed_users()
    if args.mode in ("events", "all"):
        seed_events_domain()


if __name__ == "__main__":
    main()
