from __future__ import annotations

import pytest

from events_service.app.core.exceptions import AppError
from events_service.app.core.settings import settings
import events_service.app.services.storage_service as storage_service


def test_promote_pending_rejects_oversized_upload(monkeypatch: pytest.MonkeyPatch) -> None:
    deleted: list[str] = []

    monkeypatch.setattr(storage_service, "object_exists", lambda key: True)
    monkeypatch.setattr(
        storage_service,
        "_head_object",
        lambda key: {
            "ContentLength": settings.upload_max_image_size_bytes + 1,
            "ContentType": "image/png",
        },
    )
    monkeypatch.setattr(storage_service, "delete_object", lambda key: deleted.append(key))

    with pytest.raises(AppError) as exc:
        storage_service.promote_pending_object("events/pending/big-file.png", namespace="events")

    assert exc.value.status_code == 422
    assert deleted == ["events/pending/big-file.png"]


def test_promote_pending_rejects_non_image_content_type(monkeypatch: pytest.MonkeyPatch) -> None:
    deleted: list[str] = []

    monkeypatch.setattr(storage_service, "object_exists", lambda key: True)
    monkeypatch.setattr(
        storage_service,
        "_head_object",
        lambda key: {
            "ContentLength": 1024,
            "ContentType": "application/octet-stream",
        },
    )
    monkeypatch.setattr(storage_service, "delete_object", lambda key: deleted.append(key))

    with pytest.raises(AppError) as exc:
        storage_service.promote_pending_object("events/pending/not-image.bin", namespace="events")

    assert exc.value.status_code == 422
    assert deleted == ["events/pending/not-image.bin"]

