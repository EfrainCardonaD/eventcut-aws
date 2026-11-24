from __future__ import annotations

import pytest
from pydantic import ValidationError

from auth.schemas.verify import VerifyEmailResendRequest


def test_verify_resend_request_requires_valid_email() -> None:
    with pytest.raises(ValidationError):
        VerifyEmailResendRequest(email="not-an-email")


def test_verify_resend_request_accepts_valid_email() -> None:
    payload = VerifyEmailResendRequest(email="user@example.com")
    assert str(payload.email) == "user@example.com"

