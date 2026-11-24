from __future__ import annotations

import events_service.app.main as app_main
import events_service.app.services.storage_service as storage_service


def test_cleanup_pending_image_from_public_url_deletes_pending_key(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        storage_service,
        "extract_file_key_from_public_url",
        lambda _url: "events/pending/demo.png",
    )
    monkeypatch.setattr(storage_service, "is_pending_key", lambda key: key.startswith("events/pending/"))
    monkeypatch.setattr(storage_service, "delete_object", lambda key: calls.append(key))

    cleaned = storage_service.cleanup_pending_image_from_public_url("https://cdn.example.com/events/pending/demo.png")

    assert cleaned is True
    assert calls == ["events/pending/demo.png"]


def test_validation_cleanup_applies_to_events_and_communities_post_and_patch(monkeypatch) -> None:
    seen_urls: list[str | None] = []
    monkeypatch.setattr(
        app_main,
        "cleanup_pending_image_from_public_url",
        lambda image_url: seen_urls.append(image_url),
    )

    app_main.cleanup_pending_image_after_validation_error(
        path="/api/v1/categories",
        method="POST",
        payload={"image_url": "https://cdn.example.com/events/pending/one.png"},
    )
    app_main.cleanup_pending_image_after_validation_error(
        path="/api/v1/events",
        method="GET",
        payload={"image_url": "https://cdn.example.com/events/pending/two.png"},
    )
    app_main.cleanup_pending_image_after_validation_error(
        path="/api/v1/events",
        method="POST",
        payload={"image_url": "https://cdn.example.com/events/pending/three.png"},
    )
    app_main.cleanup_pending_image_after_validation_error(
        path="/api/v1/events/abc-123",
        method="PATCH",
        payload={"image_url": "https://cdn.example.com/events/pending/four.png"},
    )
    app_main.cleanup_pending_image_after_validation_error(
        path="/api/v1/communities",
        method="POST",
        payload={"image_url": "https://cdn.example.com/comunidad/pending/five.png"},
    )

    assert seen_urls == [
        "https://cdn.example.com/events/pending/three.png",
        "https://cdn.example.com/events/pending/four.png",
        "https://cdn.example.com/comunidad/pending/five.png",
    ]


def test_validation_cleanup_ignores_non_dict_payload(monkeypatch) -> None:
    called = {"value": False}

    def _mark(_image_url: str | None) -> bool:
        called["value"] = True
        return True

    monkeypatch.setattr(app_main, "cleanup_pending_image_from_public_url", _mark)

    app_main.cleanup_pending_image_after_validation_error(
        path="/api/v1/events",
        method="POST",
        payload=["not", "a", "dict"],
    )

    assert called["value"] is False

