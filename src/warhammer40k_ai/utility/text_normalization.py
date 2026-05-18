"""Shared text normalization for Wahapedia and user-authored rules text."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Any


_TEXT_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("\u00e2\u0080\u0098", "'"),
    ("\u00e2\u0080\u0099", "'"),
    ("\u00e2\u0080\u009c", '"'),
    ("\u00e2\u0080\u009d", '"'),
    ("\u00e2\u0080\u0093", "-"),
    ("\u00e2\u0080\u0094", "-"),
    ("\u00c3\u00a2\u00e2\u201a\u00ac\u00e2\u201e\u00a2", "'"),
    ("\u00c3\u00a2\u00e2\u201a\u00ac\u00c5\u201c", '"'),
    ("\u00c3\u00a2\u00e2\u201a\u00ac\u009d", '"'),
    ("\u00c3\u00a2\u00e2\u201a\u00ac\u201c", "-"),
    ("\u00c3\u00a2\u00e2\u201a\u00ac\u0094", "-"),
    ("\u2018", "'"),
    ("\u2019", "'"),
    ("\u201a", "'"),
    ("\u201b", "'"),
    ("\u2032", "'"),
    ("\u2035", "'"),
    ("\u02bc", "'"),
    ("\u201c", '"'),
    ("\u201d", '"'),
    ("\u201e", '"'),
    ("\u201f", '"'),
    ("\u2033", '"'),
    ("\u2036", '"'),
    ("\u2010", "-"),
    ("\u2011", "-"),
    ("\u2012", "-"),
    ("\u2013", "-"),
    ("\u2014", "-"),
    ("\u2015", "-"),
    ("\u2212", "-"),
    ("\u00a0", " "),
    ("\u1680", " "),
    ("\u2000", " "),
    ("\u2001", " "),
    ("\u2002", " "),
    ("\u2003", " "),
    ("\u2004", " "),
    ("\u2005", " "),
    ("\u2006", " "),
    ("\u2007", " "),
    ("\u2008", " "),
    ("\u2009", " "),
    ("\u200a", " "),
    ("\u202f", " "),
    ("\u205f", " "),
    ("\u3000", " "),
    ("\u200b", ""),
    ("\u200c", ""),
    ("\u200d", ""),
    ("\ufeff", ""),
)

DISALLOWED_SOURCE_TEXT_CHARACTERS: frozenset[str] = frozenset(
    source for source, _replacement in _TEXT_REPLACEMENTS if len(source) == 1 and source
)
DISALLOWED_SOURCE_TEXT_FRAGMENTS: tuple[str, ...] = tuple(
    source for source, _replacement in _TEXT_REPLACEMENTS if len(source) > 1 and source
)


@lru_cache(maxsize=65536)
def _normalize_display_text_str(value: str) -> str:
    """Return readable text with Wahapedia's unstable punctuation normalized."""

    value = unicodedata.normalize("NFC", value)
    for source, replacement in _TEXT_REPLACEMENTS:
        value = value.replace(source, replacement)
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\s+([,.])", r"\1", value)
    return value


def normalize_display_text(text: object) -> str:
    """Return readable text with Wahapedia's unstable punctuation normalized."""

    return _normalize_display_text_str(str(text or ""))


def canonical_rules_key(text: object) -> str:
    """Return a stable lowercase key for matching rules names and wargear."""

    value = normalize_display_text(text).lower()
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_wahapedia_value(value: Any) -> Any:
    """Recursively normalize strings in a decoded Wahapedia JSON value."""

    if isinstance(value, dict):
        return {key: normalize_wahapedia_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_wahapedia_value(item) for item in value]
    if isinstance(value, str):
        return normalize_display_text(value)
    return value


def has_disallowed_source_text_character(text: object) -> bool:
    value = str(text or "")
    return any(character in value for character in DISALLOWED_SOURCE_TEXT_CHARACTERS)


def has_disallowed_source_text_fragment(text: object) -> bool:
    value = str(text or "")
    return any(fragment in value for fragment in DISALLOWED_SOURCE_TEXT_FRAGMENTS)
