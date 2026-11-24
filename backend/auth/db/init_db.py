from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.models.user import User


def ensure_admin_user(db: Session) -> None:
    stmt = select(User).where(User.role == "ROLE_ADMIN")
    admin = db.scalar(stmt)
    if admin:
        return

    # TODO: poblar admin inicial desde variables seguras en entorno de despliegue.
    user = User(
        username="admin",
        email="admin@example.com",
        password="$2b$12$M8N5vTaY8L8f3QsljvT7Ve4y7m3g7D0kWw2mM9X4f4KQfNw0Wm5w2",  # placeholder
        first_name="System",
        last_name="Admin",
        role="ROLE_ADMIN",
        active=True,
        email_verified=True,
    )
    db.add(user)
    db.commit()
