from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .detachment_manager import DetachmentManagerBase


@dataclass(frozen=True)
class BloodTitheAbility:
    key: str
    name: str
    cost: int
    summary: str


BLOOD_TITHE_ENRAGED_ABJURATION = BloodTitheAbility(
    key="ENRAGED_ABJURATION",
    name="Enraged Abjuration",
    cost=2,
    summary="FNP 5+ vs Psychic attacks and mortal wounds for BLOOD LEGIONS/WORLD EATERS.",
)
BLOOD_TITHE_DAEMONIC_RAGE = BloodTitheAbility(
    key="DAEMONIC_RAGE",
    name="Daemonic Rage",
    cost=3,
    summary="BLOOD LEGIONS melee weapons gain [LANCE].",
)
BLOOD_TITHE_BOON_OF_BLOOD = BloodTitheAbility(
    key="BOON_OF_BLOOD",
    name="Boon of Blood",
    cost=4,
    summary="BLOOD LEGIONS units gain a 4+ invulnerable save.",
)
BLOOD_TITHE_MIGHT_OF_KHORNE = BloodTitheAbility(
    key="MIGHT_OF_KHORNE",
    name="Might of Khorne",
    cost=5,
    summary="BLOOD LEGIONS units gain the Blessings of Khorne ability.",
)

BLOOD_TITHE_ABILITIES: tuple[BloodTitheAbility, ...] = (
    BLOOD_TITHE_ENRAGED_ABJURATION,
    BLOOD_TITHE_DAEMONIC_RAGE,
    BLOOD_TITHE_BOON_OF_BLOOD,
    BLOOD_TITHE_MIGHT_OF_KHORNE,
)


class WorldEatersDetachmentManager(DetachmentManagerBase):
    faction_id = "WE"

    def __init__(self, army=None):
        super().__init__(army)
        self.blood_tithe_points: int = 0
        self.blood_tithe_active: set[str] = set()
        self._blood_tithe_command_phase_key: Optional[tuple] = None

    def is_berzerker_warband(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Berzerker Warband")

    def is_khorne_daemonkin(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Khorne Daemonkin")

    def _unit_has_keyword(self, unit, keyword: str) -> bool:
        if unit is None:
            return False
        try:
            return bool(unit.has_any_keyword(keyword))
        except Exception:
            pass
        kw = (keyword or "").strip().lower()
        if not kw:
            return False
        try:
            if kw in [k.lower() for k in (getattr(unit, "keywords", []) or [])]:
                return True
        except Exception:
            pass
        try:
            if kw in [k.lower() for k in (getattr(unit, "faction_keywords", []) or [])]:
                return True
        except Exception:
            pass
        return False

    def _attached_unit_has_keyword(self, unit, keyword: str) -> bool:
        if unit is None:
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        for u in members:
            if self._unit_has_keyword(u, keyword):
                return True
        return False

    def unit_is_blood_legions(self, unit) -> bool:
        return self._attached_unit_has_keyword(unit, "BLOOD LEGIONS")

    def unit_is_world_eaters(self, unit) -> bool:
        return self._attached_unit_has_keyword(unit, "WORLD EATERS")

    def unit_is_blood_tithe_eligible(self, unit) -> bool:
        return self.unit_is_blood_legions(unit) or self.unit_is_world_eaters(unit)

    def relentless_rage_applies(self, unit) -> bool:
        if not self.is_berzerker_warband():
            return False
        if unit is None:
            return False
        try:
            if unit.has_any_keyword("WORLD EATERS"):
                return True
            return False
        except Exception:
            return self._army_faction_matches(self.faction_id)

    def _command_phase_key(self, game, player) -> tuple:
        try:
            br = int(getattr(game, "turn", 0) or 0)
        except Exception:
            br = 0
        return (br, id(player))

    def get_blood_tithe_abilities(self) -> tuple[BloodTitheAbility, ...]:
        return BLOOD_TITHE_ABILITIES

    def get_active_blood_tithe_abilities(self) -> list[BloodTitheAbility]:
        active = set(str(k or "").strip().upper() for k in (self.blood_tithe_active or set()))
        return [ab for ab in BLOOD_TITHE_ABILITIES if ab.key in active]

    def is_blood_tithe_active(self, key: str) -> bool:
        kk = str(key or "").strip().upper()
        return kk in (self.blood_tithe_active or set())

    def get_available_blood_tithe_abilities(self) -> list[BloodTitheAbility]:
        points = int(self.blood_tithe_points or 0)
        active = set(str(k or "").strip().upper() for k in (self.blood_tithe_active or set()))
        return [ab for ab in BLOOD_TITHE_ABILITIES if ab.key not in active and ab.cost <= points]

    def add_blood_tithe_points(self, amount: int) -> int:
        try:
            amt = int(amount or 0)
        except Exception:
            amt = 0
        if amt <= 0:
            return int(self.blood_tithe_points or 0)
        self.blood_tithe_points = int(self.blood_tithe_points or 0) + int(amt)
        return int(self.blood_tithe_points or 0)

    def _choice_from_name(self, name: str) -> Optional[BloodTitheAbility]:
        key = str(name or "").strip().lower()
        if not key:
            return None
        for ab in BLOOD_TITHE_ABILITIES:
            if ab.name.strip().lower() == key:
                return ab
        return None

    def can_activate_blood_tithe(
        self,
        ability_key: str,
        *,
        game=None,
        player=None,
        timing: str = "command_phase",
        ignore_command_phase_limit: bool = False,
    ) -> bool:
        kk = str(ability_key or "").strip().upper()
        if not kk:
            return False
        if not self.is_khorne_daemonkin():
            return False
        if self.is_blood_tithe_active(kk):
            return False
        ability = next((a for a in BLOOD_TITHE_ABILITIES if a.key == kk), None)
        if ability is None:
            return False
        if int(self.blood_tithe_points or 0) < int(ability.cost):
            return False
        if not ignore_command_phase_limit and str(timing or "").strip().lower() in ("command", "command_phase"):
            if game is not None and player is not None:
                key = self._command_phase_key(game, player)
                if self._blood_tithe_command_phase_key == key:
                    return False
        return True

    def activate_blood_tithe(
        self,
        ability_key: str,
        *,
        game=None,
        player=None,
        timing: str = "command_phase",
        ignore_command_phase_limit: bool = False,
    ) -> bool:
        if not self.can_activate_blood_tithe(
            ability_key,
            game=game,
            player=player,
            timing=timing,
            ignore_command_phase_limit=ignore_command_phase_limit,
        ):
            return False
        kk = str(ability_key or "").strip().upper()
        ability = next((a for a in BLOOD_TITHE_ABILITIES if a.key == kk), None)
        if ability is None:
            return False
        try:
            self.blood_tithe_points = int(self.blood_tithe_points or 0) - int(ability.cost)
        except Exception:
            return False
        if self.blood_tithe_points < 0:
            self.blood_tithe_points = 0
        self.blood_tithe_active.add(kk)
        if not ignore_command_phase_limit and str(timing or "").strip().lower() in ("command", "command_phase"):
            if game is not None and player is not None:
                self._blood_tithe_command_phase_key = self._command_phase_key(game, player)
        try:
            es = getattr(game, "event_system", None) if game is not None else None
            if es is not None:
                es.publish(
                    "blood_tithe_activated",
                    player=player,
                    ability=ability,
                    total=int(self.blood_tithe_points or 0),
                )
                es.publish(
                    "blood_tithe_updated",
                    player=player,
                    total=int(self.blood_tithe_points or 0),
                    active=[a.name for a in self.get_active_blood_tithe_abilities()],
                )
        except Exception:
            pass
        return True

    def blood_tithe_enraged_abjuration_applies(self, unit) -> bool:
        if not self.is_blood_tithe_active("ENRAGED_ABJURATION"):
            return False
        if not self.is_khorne_daemonkin():
            return False
        return self.unit_is_blood_tithe_eligible(unit)

    def blood_tithe_daemonic_rage_applies(self, unit) -> bool:
        if not self.is_blood_tithe_active("DAEMONIC_RAGE"):
            return False
        if not self.is_khorne_daemonkin():
            return False
        return self.unit_is_blood_legions(unit)

    def blood_tithe_boon_of_blood_applies(self, unit) -> bool:
        if not self.is_blood_tithe_active("BOON_OF_BLOOD"):
            return False
        if not self.is_khorne_daemonkin():
            return False
        return self.unit_is_blood_legions(unit)

    def blood_tithe_might_of_khorne_applies(self, unit) -> bool:
        if not self.is_blood_tithe_active("MIGHT_OF_KHORNE"):
            return False
        if not self.is_khorne_daemonkin():
            return False
        return self.unit_is_blood_legions(unit)

    def prompt_blood_tithe_activation(
        self,
        *,
        game=None,
        player=None,
        timing: str = "command_phase",
        source: str = "",
        ignore_command_phase_limit: bool = False,
    ) -> bool:
        if game is None or player is None:
            return False
        options = list(self.get_available_blood_tithe_abilities() or [])
        if not options:
            return False
        if not ignore_command_phase_limit and str(timing or "").strip().lower() in ("command", "command_phase"):
            key = self._command_phase_key(game, player)
            if self._blood_tithe_command_phase_key == key:
                return False
        is_human = False
        try:
            is_human = bool(getattr(getattr(player, "type", None), "name", "") == "HUMAN")
        except Exception:
            is_human = False
        if is_human:
            try:
                es = getattr(game, "event_system", None)
                subs = getattr(es, "subscribers", {}) if es is not None else {}
                if isinstance(subs, dict) and subs.get("blood_tithe_prompt"):
                    es.publish(
                        "blood_tithe_prompt",
                        player=player,
                        game=game,
                        manager=self,
                        options=options,
                        points=int(self.blood_tithe_points or 0),
                        timing=timing,
                        source=source,
                        ignore_command_phase_limit=bool(ignore_command_phase_limit),
                    )
                    return True
            except Exception:
                pass
            return False

        choice = None
        try:
            ctx = {
                "ability": "Blood Tithe",
                "options": [a.name for a in options],
                "points": int(self.blood_tithe_points or 0),
                "timing": timing,
                "source": source,
            }
            choice = player._choose_optional_value("BLOOD_TITHE", [a.name for a in options], ctx)
        except Exception:
            choice = None
        if isinstance(choice, str):
            chosen = self._choice_from_name(choice)
            if chosen is not None:
                return self.activate_blood_tithe(
                    chosen.key,
                    game=game,
                    player=player,
                    timing=timing,
                    ignore_command_phase_limit=ignore_command_phase_limit,
                )
        return False

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if game is None or player is None:
            return
        if not self.is_khorne_daemonkin():
            return
        if player is not getattr(self.army, "player", None):
            return
        if int(self.blood_tithe_points or 0) <= 0:
            return
        self.prompt_blood_tithe_activation(game=game, player=player, timing="command_phase", source="Command phase")

    def validate_detachment_rules(self) -> list[str]:
        errors: list[str] = []
        army = self.army
        if army is None:
            return errors
        if not self.is_khorne_daemonkin():
            return errors

        points_limit = int(getattr(army, "points_limit", 0) or 0)
        if points_limit <= 1000:
            cap = 500
            size_label = "Incursion"
        elif points_limit <= 2000:
            cap = 1000
            size_label = "Strike Force"
        else:
            cap = 1500
            size_label = "Onslaught"

        blood_legions_units = [u for u in list(getattr(army, "units", []) or []) if self.unit_is_blood_legions(u)]
        blood_legions_points = 0
        for u in blood_legions_units:
            try:
                blood_legions_points += int(u.get_unit_cost() or 0)
            except Exception:
                continue
        if blood_legions_points > cap:
            errors.append(
                f"Khorne Daemonkin: total BLOOD LEGIONS points ({blood_legions_points}) exceed {size_label} cap of {cap}."
            )

        warlord = None
        try:
            warlord = getattr(army, "warlord", None)
        except Exception:
            warlord = None
        if warlord is None:
            try:
                for u in list(getattr(army, "units", []) or []):
                    if getattr(u, "is_warlord", False):
                        warlord = u
                        break
            except Exception:
                warlord = None

        if warlord is not None and self.unit_is_blood_legions(warlord):
            errors.append("Khorne Daemonkin: BLOOD LEGIONS models cannot be your WARLORD.")

        try:
            enh = getattr(warlord, "enhancement", None) if warlord is not None else None
            enh_id = str(getattr(enh, "id", "") or "").strip()
        except Exception:
            enh_id = ""
        if enh_id == "000010078004":
            errors.append("Khorne Daemonkin: Disciple of Khorne cannot be your WARLORD.")

        return errors
