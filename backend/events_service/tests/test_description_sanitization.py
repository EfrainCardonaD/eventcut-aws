from __future__ import annotations

from datetime import datetime

from events_service.app.schemas.community import CommunityCreate, CommunityUpdate
from events_service.app.schemas.event import EventCreate, EventUpdate


def test_event_create_preserves_tiptap_html_whitelist_structure() -> None:
    payload = EventCreate(
        title="Meetup Seguridad",
        description=(
            '<h2>🚀 Titulo</h2>'
            '<p><span data-color-pair="emerald" class="rt-color-pair-emerald">✅ Texto</span></p>'
            "<blockquote>Frase</blockquote>"
            '<pre><code class="language-cpp">int main(){}</code></pre>'
            '<p><a href="https://tresjs.org/">https://tresjs.org/</a></p>'
        ),
        image_url="https://cdn.example.com/events/demo.png",
        start_datetime=datetime(2026, 4, 10, 10, 0, 0),
        end_datetime=datetime(2026, 4, 10, 12, 0, 0),
        location="Sala Principal",
        category_id=1,
    )

    assert "<h2>🚀 Titulo</h2>" in payload.description
    assert '<span data-color-pair="emerald" class="rt-color-pair-emerald">✅ Texto</span>' in payload.description
    assert "<blockquote>Frase</blockquote>" in payload.description
    assert '<pre><code class="language-cpp">int main(){}</code></pre>' in payload.description
    assert (
        '<a href="https://tresjs.org/" target="_blank" rel="noopener noreferrer">https://tresjs.org/</a>'
        in payload.description
    )
    assert "&lt;h2&gt;" not in payload.description


def test_event_update_removes_dangerous_tags_and_attributes() -> None:
    payload = EventUpdate(
        description=(
            "<script>alert(1)</script>"
            '<p onclick="evil()">Texto</p>'
            '<iframe src="https://evil.example"></iframe>'
            '<form><input value="x"><button>ok</button></form>'
        )
    )

    assert "<script" not in payload.description
    assert "<iframe" not in payload.description
    assert "<form" not in payload.description
    assert "<input" not in payload.description
    assert "<button" not in payload.description
    assert "onclick" not in payload.description
    assert "<p>Texto</p>" in payload.description


def test_community_create_sanitizes_description() -> None:
    payload = CommunityCreate(
        name="Comunidad Front",
        description='<p>Bienvenidos <a href="https://example.com">link</a></p>',
        image_url="https://cdn.example.com/comunidad/demo.png",
        contact_email="owner@example.com",
        is_accepted_terms=True,
    )

    assert (
        '<a href="https://example.com" target="_blank" rel="noopener noreferrer">link</a>' in payload.description
    )


def test_community_update_sanitizes_optional_description() -> None:
    payload = CommunityUpdate(description='<p>Texto <a href="javascript:alert(1)">malicioso</a></p>')

    assert "javascript:" not in payload.description
    assert "href=" not in payload.description


def test_event_description_allows_span_with_safe_color_pair_class() -> None:
    payload = EventUpdate(description='<p><span class="rt-color-pair-blue" data-color-pair="blue">Texto</span></p>')

    assert '<span class="rt-color-pair-blue" data-color-pair="blue">' in payload.description


def test_event_description_removes_unsafe_span_classes_and_attributes() -> None:
    payload = EventUpdate(
        description='<p><span class="rt-color-pair-emerald evil" style="color:red" data-color-pair="emerald">Texto</span></p>'
    )

    assert "evil" not in payload.description
    assert "style=" not in payload.description
    assert "class=" not in payload.description
    assert "data-color-pair=" in payload.description


def test_event_description_removes_mismatched_span_color_pair() -> None:
    payload = EventUpdate(
        description='<p><span class="rt-color-pair-violet" data-color-pair="amber">Texto</span></p>'
    )

    assert "rt-color-pair-violet" not in payload.description
    assert 'data-color-pair="amber"' not in payload.description


def test_event_description_allows_http_images_and_blocks_javascript_protocol() -> None:
    payload = EventUpdate(
        description=(
            '<p><img src="https://cdn.example.com/a.png" alt="ok" loading="lazy" class="event-image"></p>'
            '<p><img src="javascript:alert(1)" alt="bad"></p>'
        )
    )

    assert '<img src="https://cdn.example.com/a.png" alt="ok" loading="lazy" class="event-image">' in payload.description
    assert "javascript:" not in payload.description


