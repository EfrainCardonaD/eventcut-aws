from __future__ import annotations

import pytest
from pydantic import ValidationError

from events_service.app.schemas.social import SocialLinks


def test_whatsapp_accepts_direct_and_group_links() -> None:
    direct = SocialLinks(whatsapp="https://wa.me/573001112233")
    group = SocialLinks(whatsapp="https://chat.whatsapp.com/G62iYOwRf5EDJcZhe4XLIx")

    assert direct.whatsapp == "https://wa.me/573001112233"
    assert group.whatsapp == "https://chat.whatsapp.com/G62iYOwRf5EDJcZhe4XLIx"


def test_empty_social_links_are_treated_as_none() -> None:
    links = SocialLinks(whatsapp="", facebook="   ", instagram="")

    assert links.whatsapp is None
    assert links.facebook is None
    assert links.instagram is None
    assert links.to_dict() is None


def test_whatsapp_rejects_invalid_domain() -> None:
    with pytest.raises(ValidationError) as exc:
        SocialLinks(whatsapp="https://whatsapp.com/channel/abc")

    assert "https://wa.me/" in str(exc.value)
    assert "https://chat.whatsapp.com/" in str(exc.value)

