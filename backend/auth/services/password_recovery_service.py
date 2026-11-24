from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from auth.core.datetime_utils import is_expired
from auth.core.settings import settings
from auth.models.reset_token import ResetToken
from auth.models.user import User
from auth.security.passwords import hash_password
from auth.services.mail_service import mail_service


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def create_or_replace_reset_token(db: Session, *, user: User) -> ResetToken:
    stmt = select(ResetToken).where(
        and_(
            ResetToken.user_id == user.id,
            ResetToken.used_at.is_(None),
        )
    )
    for t in db.scalars(stmt).all():
        t.used_at = _now_utc()
        db.add(t)

    token = ResetToken(
        user_id=user.id,
        token=_new_token(),
        expires_at=_now_utc() + timedelta(minutes=settings.reset_token_ttl_minutes),
        used_at=None,
        attempts=0,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


async def send_reset_email(*, user: User, token: str) -> None:
    reset_url = f"{settings.app_frontend_base_url.rstrip('/')}/reset-password?token={token}"

    subject = "Recuperación de contraseña"
    html = f"""
    <html>
      <body>
        <p>Hola {user.first_name},</p>
        <p>Recibimos una solicitud para restablecer tu contraseña:</p>
        <p><a href=\"{reset_url}\">Restablecer contraseña</a></p>
        <p>Si no fuiste tú, ignora este correo.</p>
      </body>
    </html>
    """.strip()
    text = f"Hola {user.first_name}. Restablece tu contraseña aquí: {reset_url}"

    await mail_service.send_email(to_email=user.email, subject=subject, html_body=html, text_body=text)


async def forgot_password(db: Session, *, email: str) -> None:
    # Respuesta silenciosa para evitar enumeración de cuentas.
    stmt = select(User).where(User.email == email)
    user = db.scalar(stmt)
    if not user:
        return

    token = create_or_replace_reset_token(db, user=user)
    try:
        await send_reset_email(user=user, token=token.token)
    except Exception:
        return


def reset_password(db: Session, *, token: str, new_password: str) -> None:
    stmt = select(ResetToken).where(ResetToken.token == token)
    reset = db.scalar(stmt)
    if not reset:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido")

    now = _now_utc()
    if reset.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token ya usado")
    if is_expired(reset.expires_at, now=now):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token expirado")

    user = db.get(User, reset.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuario no encontrado")

    reset.used_at = now
    reset.attempts = int(reset.attempts or 0) + 1
    db.add(reset)

    user.password = hash_password(new_password)
    # Invalida refresh tokens previos tras cambio de contraseña.
    user.token_version += 1
    db.add(user)

    db.commit()

