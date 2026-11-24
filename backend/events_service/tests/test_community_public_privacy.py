from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import events_service.app.api.routes.communities as communities_route


def test_public_response_includes_contact_email() -> None:
    rich_description = (
        '<h2>🚀 Titulo</h2>'
        '<p><span data-color-pair="emerald" class="rt-color-pair-emerald">✅ Texto</span></p>'
        "<blockquote>Frase</blockquote>"
        '<pre><code class="language-cpp">int main(){}</code></pre>'
    )

    community = SimpleNamespace(
        id="com-1",
        name="Comunidad Backend",
        description=rich_description,
        image_url="https://cdn.example.com/comunidad/logo.png",
        owner_id="owner-1",
        contact_email="owner@example.com",
        category_id=1,
        status="ACTIVE",
        social_links=None,
        created_at=datetime(2026, 4, 1, 10, 0, 0),
    )

    response = communities_route._build_public_community_response(
        community,
        events_count=3,
        owner_name_index={"owner-1": ("Ada", "Lovelace")},
    )

    assert response.contact_email == "owner@example.com"
    assert response.owner_first_name == "Ada"
    assert response.events_count == 3
    assert response.description == rich_description

