"""Configuración centralizada y manejo de estado para el despliegue EventCut en AWS."""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
INFRA_DIR = Path(__file__).resolve().parent
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"
DOCS_DIR = REPO_ROOT / "docs"
EVIDENCIAS_DIR = DOCS_DIR / "evidencias"
STATE_DIR = INFRA_DIR / "state"
STATE_FILE = STATE_DIR / "deployment_state.json"

PROJECT_TAG = "EventCut"
DEFAULT_REGION = "us-east-1"
DEFAULT_KEY_NAME = "vockey"
DEFAULT_INSTANCE_PROFILE = "LabInstanceProfile"
DEFAULT_EC2_TYPE = "t3.small"
DEFAULT_RDS_CLASS = "db.t3.micro"
DEFAULT_RDS_ID = "eventcut-mysql-db"
DEFAULT_DB_USER = "eventcut_admin"
DEFAULT_AUTH_DB = "eventcut_auth_db"
DEFAULT_EVENTS_DB = "eventcut_events_db"

DEFAULT_ADMIN_EMAIL = "admin@eventcut.edu.mx"
DEFAULT_ADMIN_PASS = "AdminEventCut2026!"
DEFAULT_DEMO_EMAIL = "demo@eventcut.edu.mx"
DEFAULT_DEMO_PASS = "DemoEventCut2026!"


def find_pem_path() -> str:
    candidates = [
        os.getenv("EVENTCUT_PEM_PATH", ""),
        str(REPO_ROOT / "labsuser.pem"),
        str(REPO_ROOT.parent / "labsuser.pem"),
        str(Path.home() / "Downloads" / "labsuser.pem"),
    ]
    for path in candidates:
        if path and Path(path).is_file():
            return str(Path(path).resolve())
    return str((REPO_ROOT.parent / "labsuser.pem").resolve())


def default_state() -> dict[str, Any]:
    return {
        "region": DEFAULT_REGION,
        "account_id": None,
        "caller_arn": None,
        "pem_path": find_pem_path(),
        "key_name": DEFAULT_KEY_NAME,
        "instance_profile": DEFAULT_INSTANCE_PROFILE,
        "ec2_instance_type": DEFAULT_EC2_TYPE,
        "rds_instance_class": DEFAULT_RDS_CLASS,
        "rds_identifier": DEFAULT_RDS_ID,
        "db_user": DEFAULT_DB_USER,
        "db_password": f"EvtCut{secrets.token_hex(6)}!",
        "jwt_secret": secrets.token_hex(24),
        "gateway_secret": secrets.token_hex(20),
        "admin_email": DEFAULT_ADMIN_EMAIL,
        "admin_password": DEFAULT_ADMIN_PASS,
        "demo_email": DEFAULT_DEMO_EMAIL,
        "demo_password": DEFAULT_DEMO_PASS,
        "smtp_enabled": False,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_username": "",
        "smtp_password": "",
        "smtp_from": "noreply@eventcut.edu.mx",
        "vpc_id": None,
        "subnet_ids": [],
        "availability_zones": [],
        "alb_sg_id": None,
        "app_sg_id": None,
        "rds_sg_id": None,
        "media_bucket": None,
        "media_public_host": None,
        "frontend_bucket": None,
        "frontend_website_url": None,
        "artifacts_bucket": None,
        "rds_endpoint": None,
        "rds_port": 3306,
        "alb_arn": None,
        "alb_dns": None,
        "alb_url": None,
        "tg_arn": None,
        "listener_arn": None,
        "launch_template_id": None,
        "asg_name": "eventcut-asg",
        "ec2_instances": [],
        "sns_topic_arn": None,
        "cloudwatch_alarms": [],
        "completed_steps": [],
    }


def load_state() -> dict[str, Any]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    base = default_state()
    if STATE_FILE.is_file():
        try:
            saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            base.update(saved)
        except Exception:
            pass
    if not base.get("pem_path") or not Path(base["pem_path"]).is_file():
        base["pem_path"] = find_pem_path()
    return base


def save_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def reset_state_keep_prefs(state: dict[str, Any]) -> dict[str, Any]:
    fresh = default_state()
    for key in (
        "region",
        "account_id",
        "caller_arn",
        "pem_path",
        "key_name",
        "smtp_enabled",
        "smtp_host",
        "smtp_port",
        "smtp_username",
        "smtp_password",
        "smtp_from",
        "admin_email",
        "admin_password",
        "demo_email",
        "demo_password",
    ):
        if key in state and state[key] is not None:
            fresh[key] = state[key]
    save_state(fresh)
    return fresh
