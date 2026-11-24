from __future__ import annotations

import bleach
import re
from bleach.linkifier import Linker
from typing import Any, cast

_ALLOWED_COLOR_PAIRS = {"rose", "blue", "emerald", "amber", "violet", "slate"}
_ALLOWED_SPAN_CLASSES = {f"rt-color-pair-{pair}" for pair in _ALLOWED_COLOR_PAIRS}

_ALLOWED_TAGS = [
    "h1",
    "h2",
    "h3",
    "p",
    "br",
    "hr",
    "ul",
    "ol",
    "li",
    "blockquote",
    "pre",
    "code",
    "strong",
    "em",
    "u",
    "s",
    "a",
    "img",
    "span",
]
_ALLOWED_PROTOCOLS = ["http", "https"]


def _is_safe_http_url(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized.startswith("http://") or normalized.startswith("https://")


def _allow_attribute(tag: str, name: str, value: str) -> bool:
    attr = name.lower()
    if attr.startswith("on"):
        return False

    # Global class: permitido salvo en span donde se valida por whitelist estricta.
    if attr == "class" and tag != "span":
        return True

    if tag == "a":
        if attr == "href":
            return _is_safe_http_url(value)
        return attr in {"target", "rel"}

    if tag == "img":
        if attr == "src":
            return _is_safe_http_url(value)
        return attr in {"alt", "title", "loading", "class"}

    if tag == "span":
        if attr == "data-color-pair":
            return value in _ALLOWED_COLOR_PAIRS
        if attr == "class":
            classes = {token for token in value.split() if token}
            return bool(classes) and classes.issubset(_ALLOWED_SPAN_CLASSES)
        return False

    if tag in {"code", "pre"}:
        return attr == "class"

    return False


def _enforce_anchor_security(attrs: dict[tuple[str | None, str], str], new: bool = False):
    # Evita reescribir texto plano en links; solo ajusta anchors ya existentes.
    if new:
        return None

    href = attrs.get((None, "href"), "")
    if not _is_safe_http_url(href):
        attrs.pop((None, "href"), None)

    attrs[(None, "target")] = "_blank"
    attrs[(None, "rel")] = "noopener noreferrer"
    return attrs


_LINKER = Linker(
    callbacks=cast(list[Any], [_enforce_anchor_security]),
    parse_email=False,
    skip_tags=["pre", "code"],
)
_SPAN_TAG_RE = re.compile(r"<span(?P<attrs>[^>]*)>", flags=re.IGNORECASE)
_CLASS_ATTR_RE = re.compile(r'\sclass="(?P<value>[^"]*)"')
_PAIR_ATTR_RE = re.compile(r'\sdata-color-pair="(?P<value>[^"]*)"')


def _normalize_span_color_pair(cleaned: str) -> str:
    def replace(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        class_match = _CLASS_ATTR_RE.search(attrs)
        pair_match = _PAIR_ATTR_RE.search(attrs)

        if not class_match or not pair_match:
            return match.group(0)

        classes = [token for token in class_match.group("value").split() if token]
        if len(classes) != 1:
            return "<span>"

        css_class = classes[0]
        expected_class = f"rt-color-pair-{pair_match.group('value')}"
        if css_class != expected_class:
            return "<span>"

        return match.group(0)

    return _SPAN_TAG_RE.sub(replace, cleaned)


def sanitize_basic_rich_text(value: str) -> str:
    """Sanitiza HTML de TipTap por whitelist preservando estructura permitida."""
    cleaned = bleach.clean(
        value,
        tags=_ALLOWED_TAGS,
        attributes=_allow_attribute,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )
    cleaned = _normalize_span_color_pair(cleaned)
    return _LINKER.linkify(cleaned)

