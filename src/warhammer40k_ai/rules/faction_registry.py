from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FactionRuleProfile:
    faction_id: str
    name: str
    primary_keyword: str
    aliases: tuple[str, ...] = ()


FACTION_RULE_PROFILES: tuple[FactionRuleProfile, ...] = (
    FactionRuleProfile("AC", "Adeptus Custodes", "ADEPTUS CUSTODES"),
    FactionRuleProfile("ADM", "Adeptus Mechanicus", "ADEPTUS MECHANICUS"),
    FactionRuleProfile("AE", "Aeldari", "AELDARI"),
    FactionRuleProfile("AM", "Astra Militarum", "ASTRA MILITARUM"),
    FactionRuleProfile("AOI", "Imperial Agents", "AGENTS OF THE IMPERIUM"),
    FactionRuleProfile("AS", "Adepta Sororitas", "ADEPTA SORORITAS"),
    FactionRuleProfile("CD", "Chaos Daemons", "CHAOS DAEMONS"),
    FactionRuleProfile("CK", "Chaos Knights", "CHAOS KNIGHTS", aliases=("QT",)),
    FactionRuleProfile("CSM", "Chaos Space Marines", "HERETIC ASTARTES"),
    FactionRuleProfile("DG", "Death Guard", "DEATH GUARD"),
    FactionRuleProfile("DRU", "Drukhari", "DRUKHARI"),
    FactionRuleProfile("EC", "Emperor's Children", "EMPEROR'S CHILDREN"),
    FactionRuleProfile("GC", "Genestealer Cults", "GENESTEALER CULTS"),
    FactionRuleProfile("GK", "Grey Knights", "GREY KNIGHTS"),
    FactionRuleProfile("IK", "Imperial Knights", "IMPERIAL KNIGHTS", aliases=("QI",)),
    FactionRuleProfile("LOV", "Leagues of Votann", "LEAGUES OF VOTANN"),
    FactionRuleProfile("NEC", "Necrons", "NECRONS"),
    FactionRuleProfile("ORK", "Orks", "ORKS"),
    FactionRuleProfile("SM", "Space Marines", "ADEPTUS ASTARTES"),
    FactionRuleProfile("TAU", "T'au Empire", "T'AU EMPIRE"),
    FactionRuleProfile("TS", "Thousand Sons", "THOUSAND SONS"),
    FactionRuleProfile("TYR", "Tyranids", "TYRANIDS"),
    FactionRuleProfile("WE", "World Eaters", "WORLD EATERS"),
)

_PROFILES_BY_ID: dict[str, FactionRuleProfile] = {}
for _profile in FACTION_RULE_PROFILES:
    _PROFILES_BY_ID[_profile.faction_id] = _profile
    for _alias in _profile.aliases:
        _PROFILES_BY_ID[_alias] = _profile


def normalize_faction_id(faction_id: str | None) -> str:
    fid = str(faction_id or "").strip().upper()
    profile = _PROFILES_BY_ID.get(fid)
    return profile.faction_id if profile is not None else fid


def get_faction_profile(faction_id: str | None) -> FactionRuleProfile | None:
    fid = str(faction_id or "").strip().upper()
    return _PROFILES_BY_ID.get(fid)


def faction_ids_match(left: str | None, right: str | None) -> bool:
    return bool(normalize_faction_id(left)) and normalize_faction_id(left) == normalize_faction_id(right)
