from __future__ import annotations


def unit_has_keyword(unit, keyword: str) -> bool:
    if unit is None:
        return False
    kw = str(keyword or "").strip()
    if not kw:
        return False
    has_any = getattr(unit, "has_any_keyword", None)
    if callable(has_any):
        try:
            return bool(has_any(kw))
        except Exception:
            pass
    raw = []
    try:
        raw.extend(list(getattr(unit, "keywords", []) or []))
    except Exception:
        pass
    try:
        raw.extend(list(getattr(unit, "faction_keywords", []) or []))
    except Exception:
        pass
    kw_lower = kw.lower()
    return kw_lower in {str(k or "").strip().lower() for k in raw if str(k).strip()}
