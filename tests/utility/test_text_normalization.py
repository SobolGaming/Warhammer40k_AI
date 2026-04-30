from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from warhammer40k_ai.utility.text_normalization import (
    has_disallowed_source_text_character,
    has_disallowed_source_text_fragment,
    normalize_display_text,
)


def _json_strings(value: Any):
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str):
                yield key
            yield from _json_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _json_strings(item)
    elif isinstance(value, str):
        yield value


def test_normalize_display_text_replaces_wahapedia_punctuation_variants() -> None:
    assert normalize_display_text("Juggernaut\u2019s\u00a0bladed\u2013horn") == "Juggernaut's bladed-horn"
    assert normalize_display_text("\u00e2\u0080\u0098quoted\u00e2\u0080\u0099") == "'quoted'"


def test_normalize_display_text_accepts_unhashable_inputs() -> None:
    assert normalize_display_text(["Juggernaut\u2019s", "horn"]) == "['Juggernaut's', 'horn']"


def test_committed_wahapedia_json_has_no_disallowed_text_variants() -> None:
    root = Path(__file__).resolve().parents[2] / "wahapedia_data"
    failures: list[str] = []
    for path in sorted(root.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for text in _json_strings(data):
            if has_disallowed_source_text_character(text) or has_disallowed_source_text_fragment(text):
                failures.append(f"{path.name}: {text!r}")
                break
    assert failures == []
