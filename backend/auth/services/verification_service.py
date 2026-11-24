from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from auth.core.datetime_utils import is_expired
from auth.core.settings import settings
from auth.models.user import User
from auth.models.verification_token import VerificationToken
from auth.services.mail_service import mail_service


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _new_token() -> str:
    # URL-safe token
    return secrets.token_urlsafe(32)


def create_or_replace_email_token(db: Session, *, user: User) -> VerificationToken:
    # Invalida tokens previos EMAIL no usados (simple: marcarlos como usados_at=now)
    stmt = select(VerificationToken).where(
        and_(
            VerificationToken.user_id == user.id,
            VerificationToken.channel == "EMAIL",
            VerificationToken.used_at.is_(None),
        )
    )
    for t in db.scalars(stmt).all():
        t.used_at = _now_utc()
        db.add(t)

    token = VerificationToken(
        user_id=user.id,
        channel="EMAIL",
        token=_new_token(),
        expires_at=_now_utc() + timedelta(minutes=settings.verification_token_ttl_minutes),
        used_at=None,
        attempts=0,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


async def send_verification_email(*, user: User, token: str) -> None:
    confirm_url = f"{settings.app_frontend_base_url.rstrip('/')}/verify-email?token={token}"

    subject = "Verifica tu correo"
    html = f"""
    <html>
      <body>
        <p>Hola {user.first_name},</p>
        <p>Confirma tu correo para activar tu cuenta:</p>
        <p><a href=\"{confirm_url}\">Verificar email</a></p>
        <p>Si no fuiste tú, ignora este correo.</p>
      </body>
    </html>
    """.strip()

    text = f"Hola {user.first_name}. Verifica tu correo aquí: {confirm_url}"

    await mail_service.send_email(to_email=user.email, subject=subject, html_body=html, text_body=text)


def confirm_email_token(db: Session, *, token_str: str) -> User:
    stmt = select(VerificationToken).where(VerificationToken.token == token_str)
    token = db.scalar(stmt)
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido")

    now = _now_utc()
    if token.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token ya usado")
    if is_expired(token.expires_at, now=now):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token expirado")

    user = db.get(User, token.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuario no encontrado")

    token.used_at = now
    token.attempts = int(token.attempts or 0) + 1
    db.add(token)

    user.email_verified = True
    user.active = True
    db.add(user)

    db.commit()
    db.refresh(user)
    return user


async def resend_verification_email(db: Session, *, email: str) -> None:
    # Respuesta "silenciosa" para evitar enumeración, como el doc.
    stmt = select(User).where(User.email == email)
    user = db.scalar(stmt)
    if not user or user.email_verified:
        return

    token = create_or_replace_email_token(db, user=user)
    try:
        await send_verification_email(user=user, token=token.token)
    except Exception:
        return
