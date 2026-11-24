from __future__ import annotations

from pydantic import BaseModel


class CurrentUser(BaseModel):
    id: str
    username: str
    email: str
    role: str

    @classmethod
    def from_token_payload(cls, payload: dict[str, object]) -> "CurrentUser":
        return cls(
            id=str(payload["sub"]),
            username=str(payload["username"]),
            email=str(payload["email"]),
            role=str(payload["role"]),
        )

