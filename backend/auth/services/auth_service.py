from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from auth.models.revoked_token import RevokedToken
from auth.models.user import User
from auth.schemas.auth import RegisterRequest
from auth.security import jwt as jwt_utils
from auth.security.passwords import hash_password, verify_password
from auth.security.roles import is_valid_role, normalize_role


def register_user(db: Session, req: RegisterRequest) -> User:
    # Validación duplicados
    stmt = select(User).where(or_(User.username == req.username, User.email == str(req.email)))
    existing = db.scalar(stmt)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username o email ya existe")

    user = User(
        username=req.username,
        email=str(req.email),
        password=hash_password(req.password),
        first_name=req.first_name,
        last_name=req.last_name,
        role="ROLE_USER",
        active=False,
        email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User:
    # Compatibilidad: permite login por username o correo.
    stmt = select(User).where(or_(User.username == username, User.email == username))
    user = db.scalar(stmt)
    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credenciales inválidas")

    if not user.email_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Correo no verificado")
    if not user.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cuenta inactiva")

    user.last_login_at = datetime.now(UTC)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def issue_token_pair(user: User) -> jwt_utils.TokenPair:
    access = jwt_utils.create_access_token(
        user_id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
    )
    refresh = jwt_utils.create_refresh_token(user_id=user.id, token_version=user.token_version)
    return jwt_utils.TokenPair(token=access, refresh_token=refresh)


def revoke_token(db: Session, token: str, *, reason: str) -> None:
    payload = jwt_utils.decode_token(token)
    revoke_token_payload(db, payload, reason=reason)


def revoke_token_payload(db: Session, payload: dict[str, object], *, reason: str) -> None:
    jti = jwt_utils.get_token_jti(payload)
    exp = jwt_utils.get_token_expires_at(payload)

    # Idempotente: si ya existe, no falla
    existing = db.get(RevokedToken, jti)
    if existing:
        return

    db.add(RevokedToken(jti=jti, expires_at=exp, reason=reason))
    db.commit()


def refresh_tokens(db: Session, refresh_token: str) -> jwt_utils.TokenPair:
    payload = jwt_utils.decode_token(refresh_token)
    try:
        token_type = jwt_utils.get_token_type(payload)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Refresh token inválido")

    if token_type != "refresh":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Refresh token inválido")

    # rotation: revoca el refresh usado
    revoke_token_payload(db, payload, reason="refresh_rotated")

    user_id = payload.get("sub")
    stmt = select(User).where(User.id == user_id)
    user = db.scalar(stmt)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuario no encontrado")

    if not user.active or not user.email_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuario no habilitado")

    token_version = payload.get("token_version")
    if not isinstance(token_version, int) or token_version != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido")

    return issue_token_pair(user)


def list_users(db: Session, *, limit: int = 50, offset: int = 0) -> list[User]:
    stmt = select(User).offset(offset).limit(limit).order_by(User.created_at.desc())
    return list(db.scalars(stmt).all())


def get_user_by_id(db: Session, *, user_id: str) -> User | None:
    stmt = select(User).where(User.id == user_id)
    return db.scalar(stmt)


def list_user_summaries_by_ids(db: Session, *, user_ids: list[str]) -> dict[str, User]:
    unique_ids = list(dict.fromkeys(user_ids))
    if not unique_ids:
        return {}

    stmt = select(User).where(User.id.in_(unique_ids))
    users = list(db.scalars(stmt).all())
    return {user.id: user for user in users}


def update_user_role(db: Session, *, user_id: str, role: str) -> User:
    stmt = select(User).where(User.id == user_id)
    user = db.scalar(stmt)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")


    normalized_role = normalize_role(role)
    if not is_valid_role(normalized_role):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rol no permitido")

    user.role = normalized_role
    # Invalida toda la familia de refresh tokens vigente para que el nuevo rol aplique pronto.
    user.token_version += 1
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

