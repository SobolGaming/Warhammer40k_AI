from __future__ import annotations


from ..utility.ability_support import ABILITY_BONDSMAN, army_has_ability_id


_BONDSMAN_EFFECTS = {
    "paladin's duty": {"lethal_hits": True, "lance": True},
    "errant's duty": {"reroll_advance": True, "assault_ranged": True},
    "warden's duty": {"sustained_hits": 1, "ignores_cover_ranged": True},
    "gallant's duty": {"reroll_charge": True, "reroll_hit_melee": True},
    "crusader's duty": {"ranged_hit_bonus": 1},
    "acheron's duty": {"acheron_battleshock": True},
    "atrapos' duty": {"reroll_hit_wound_vs_titanic": True},
    "castigator's duty": {"sustained_hits_ranged": 1, "ap_bonus_ranged": 1},
    "lancer's duty": {"charge_after_advance": True},
    "magaera's duty": {"magaera_bonus": True},
    "styrix's duty": {"styrix_battleshock": True},
    "mentor": {"reroll_wound_vs_quarry": True},
    "defender's duty": {"damage_reduction": 1},
}


def _norm(text: str) -> str:
    return (text or "").replace("\u2019", "'").replace("\u00e2\u20ac\u2122", "'").strip().lower()


class BondsmanManager:
    """
    Imperial Knights army rule: Bondsman.

    In your Command phase, each model with a Bondsman ability can select one friendly
    ARMIGER model within 12" that is not already affected by a Bondsman ability.
    The selected ARMIGER gains the Bondsman ability's effects until your next Command phase.
    """

    def __init__(self, army=None):
        self.army = army

    def _army_has_bondsman(self) -> bool:
        if self.army is None:
            return False
        try:
            faction_id = str(getattr(self.army, "faction_id", "") or "").strip().upper()
        except Exception:
            faction_id = ""
        if faction_id and faction_id != "QI":
            return False
        if army_has_ability_id(self.army, ABILITY_BONDSMAN):
            return True
        for unit in list(getattr(self.army, "units", []) or []):
            if self._unit_has_bondsman_ability(unit):
                return True
        return False

    def _unit_has_bondsman_ability(self, unit) -> bool:
        if unit is None:
            return False
        for ab in (list(getattr(unit, "possible_abilities", []) or []) + list(getattr(unit, "abilities", []) or [])):
            try:
                name = ab if isinstance(ab, str) else getattr(ab, "name", "")
                if "bondsman" in _norm(name):
                    return True
            except Exception:
                continue
        return False

    def _unit_is_armiger(self, unit) -> bool:
        if unit is None:
            return False
        try:
            return bool(unit.has_any_keyword("ARMIGER"))
        except Exception:
            return False

    def _unit_is_valid_source(self, unit) -> bool:
        if unit is None or not self._unit_has_bondsman_ability(unit):
            return False
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                return False
        except Exception:
            return False
        try:
            if hasattr(unit, "deployed") and not bool(getattr(unit, "deployed", True)):
                return False
        except Exception:
            pass
        return True

    def _bondsman_ability_names(self, unit) -> list[str]:
        names: list[str] = []
        for ab in (list(getattr(unit, "possible_abilities", []) or []) + list(getattr(unit, "abilities", []) or [])):
            try:
                name = ab if isinstance(ab, str) else getattr(ab, "name", "")
            except Exception:
                name = ""
            if "bondsman" in _norm(name):
                names.append(str(name))
        return names

    def get_bondsman_ability_names(self, unit) -> list[str]:
        return self._bondsman_ability_names(unit)

    def _bondsman_effects_for_unit(self, unit) -> dict:
        effects: dict[str, int | bool] = {}
        for name in self._bondsman_ability_names(unit):
            key = _norm(name).replace(" (bondsman)", "").strip()
            data = _BONDSMAN_EFFECTS.get(key, {})
            for eff_key, value in data.items():
                if isinstance(value, bool):
                    effects[eff_key] = bool(value) or bool(effects.get(eff_key, False))
                else:
                    effects[eff_key] = max(int(value), int(effects.get(eff_key, 0) or 0))
        return effects

    def clear_bondsman_effects(self) -> None:
        if self.army is None:
            return
        for unit in list(getattr(self.army, "units", []) or []):
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not sr:
                continue
            for key in list(sr.keys()):
                if str(key).startswith("bondsman_"):
                    sr.pop(key, None)
            unit.special_rules = sr

    def get_bondsman_sources(self) -> list:
        if not self._army_has_bondsman():
            return []
        sources = []
        for unit in list(getattr(self.army, "units", []) or []):
            if self._unit_is_valid_source(unit):
                sources.append(unit)
        sources.sort(key=lambda u: str(getattr(u, "name", "")))
        return sources

    def get_eligible_armigers(self, source_unit, *, game_map=None) -> list:
        if self.army is None or source_unit is None:
            return []
        if not self._unit_is_valid_source(source_unit):
            return []
        eligible = []
        for unit in list(getattr(self.army, "units", []) or []):
            if not self._unit_is_armiger(unit):
                continue
            if unit is source_unit:
                continue
            try:
                if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                    continue
            except Exception:
                continue
            try:
                if hasattr(unit, "deployed") and not bool(getattr(unit, "deployed", True)):
                    continue
            except Exception:
                pass
            try:
                sr = getattr(unit, "special_rules", None)
                if isinstance(sr, dict) and sr.get("bondsman_active"):
                    continue
            except Exception:
                pass
            if game_map is not None:
                try:
                    dist = float(game_map.get_distance_between_units(source_unit, unit))
                    if dist > 12.0:
                        continue
                except Exception:
                    pass
            eligible.append(unit)
        eligible.sort(key=lambda u: str(getattr(u, "name", "")))
        return eligible

    def apply_bondsman_effects(self, source_unit, target_unit) -> bool:
        if source_unit is None or target_unit is None:
            return False
        effects = self._bondsman_effects_for_unit(source_unit)
        if not effects:
            return False
        sr = getattr(target_unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr["bondsman_active"] = True
        sr["bondsman_source_name"] = str(getattr(source_unit, "name", "") or "")
        sr["bondsman_ability_names"] = list(self._bondsman_ability_names(source_unit))
        if effects.get("lethal_hits"):
            sr["bondsman_lethal_hits"] = True
        if effects.get("lance"):
            sr["bondsman_lance"] = True
        if effects.get("reroll_advance"):
            sr["bondsman_reroll_advance"] = True
        if effects.get("assault_ranged"):
            sr["bondsman_assault_ranged"] = True
        if effects.get("sustained_hits"):
            sr["bondsman_sustained_hits"] = int(effects.get("sustained_hits", 1) or 1)
        if effects.get("sustained_hits_ranged"):
            sr["bondsman_sustained_hits_ranged"] = int(effects.get("sustained_hits_ranged", 1) or 1)
        if effects.get("ignores_cover_ranged"):
            sr["bondsman_ignores_cover_ranged"] = True
        if effects.get("reroll_charge"):
            sr["bondsman_reroll_charge"] = True
        if effects.get("reroll_hit_melee"):
            sr["bondsman_reroll_hit_melee"] = True
        if effects.get("ranged_hit_bonus"):
            sr["bondsman_ranged_hit_bonus"] = int(effects.get("ranged_hit_bonus", 1) or 1)
        if effects.get("acheron_battleshock"):
            sr["bondsman_acheron_battleshock"] = True
        if effects.get("reroll_hit_wound_vs_titanic"):
            sr["bondsman_reroll_hit_wound_vs_titanic"] = True
        if effects.get("ap_bonus_ranged"):
            sr["bondsman_ap_bonus_ranged"] = int(effects.get("ap_bonus_ranged", 1) or 1)
        if effects.get("charge_after_advance"):
            sr["bondsman_charge_after_advance"] = True
        if effects.get("magaera_bonus"):
            sr["bondsman_magaera_bonus"] = True
        if effects.get("styrix_battleshock"):
            sr["bondsman_styrix_battleshock"] = True
        if effects.get("reroll_wound_vs_quarry"):
            sr["bondsman_reroll_wound_vs_quarry"] = True
        if effects.get("damage_reduction"):
            sr["bondsman_damage_reduction"] = int(effects.get("damage_reduction", 1) or 1)
        target_unit.special_rules = sr
        return True

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        self.clear_bondsman_effects()
        if not self._army_has_bondsman():
            return
        if player is None and self.army is not None:
            player = getattr(self.army, "player", None)
        try:
            game_map = getattr(game, "map", None)
        except Exception:
            game_map = None
        for source in self.get_bondsman_sources():
            targets = self.get_eligible_armigers(source, game_map=game_map)
            if not targets:
                continue
            chosen = None
            if len(targets) == 1:
                chosen = targets[0]
            else:
                choice = None
                try:
                    if player is not None:
                        ctx = {
                            "source": getattr(source, "name", "") or "",
                            "options": [getattr(t, "name", "") for t in targets],
                        }
                        choice = player._choose_optional_value("BONDSMAN_TARGET", list(targets), ctx)
                except Exception:
                    choice = None
                if choice in targets:
                    chosen = choice
                elif isinstance(choice, str):
                    choice_norm = choice.strip().lower()
                    for target in targets:
                        if str(getattr(target, "name", "") or "").strip().lower() == choice_norm:
                            chosen = target
                            break
            if chosen is None:
                continue
            self.apply_bondsman_effects(source, chosen)

    def on_fight_phase_start(self, *, game=None) -> None:
        if self.army is None:
            return
        sources = []
        for unit in list(getattr(self.army, "units", []) or []):
            sr = getattr(unit, "special_rules", None)
            if isinstance(sr, dict) and sr.get("bondsman_acheron_battleshock"):
                sources.append(unit)
        if not sources:
            return
        try:
            game_map = getattr(game, "map", None)
        except Exception:
            game_map = None
        if game_map is None:
            return
        affected = set()
        for source in sources:
            try:
                enemies = list(game_map.get_enemy_units(source) or [])
            except Exception:
                enemies = []
            for enemy in enemies:
                try:
                    if not enemy.is_alive():
                        continue
                except Exception:
                    continue
                try:
                    if not game_map.is_within_engagement_range(source, enemy):
                        continue
                except Exception:
                    continue
                try:
                    key = str(getattr(enemy, "_id", None) or id(enemy))
                except Exception:
                    key = str(id(enemy))
                if key in affected:
                    continue
                affected.add(key)
                self._apply_battleshock(enemy, game=game, modifier=-1)

    def on_unit_shooting_resolved(self, attacker_unit=None, hits_by_target=None, *, game=None) -> None:
        if attacker_unit is None:
            return
        try:
            sr = getattr(attacker_unit, "special_rules", None)
            if not (isinstance(sr, dict) and sr.get("bondsman_styrix_battleshock")):
                return
        except Exception:
            return
        if not hits_by_target:
            return
        options = []
        for unit, hits in list(hits_by_target.items()):
            try:
                if int(hits or 0) <= 0:
                    continue
            except Exception:
                continue
            options.append((unit, int(hits or 0)))
        if not options:
            return
        options.sort(key=lambda pair: (-pair[1], str(getattr(pair[0], "name", ""))))
        target = options[0][0]
        self._apply_battleshock(target, game=game, modifier=-1)

    def on_fight_sequence_complete(self, unit=None, *, game=None) -> None:
        if unit is None:
            return
        try:
            sr = getattr(unit, "special_rules", None)
            if not (isinstance(sr, dict) and sr.get("bondsman_styrix_battleshock")):
                return
        except Exception:
            return
        targets = []
        try:
            targets = list(getattr(unit.round_state, "last_fight_targets", []) or [])
        except Exception:
            targets = list(getattr(unit, "_last_fight_targets", []) or [])
        if not targets:
            return
        target = targets[0]
        self._apply_battleshock(target, game=game, modifier=-1)

    def _apply_battleshock(self, unit, *, game=None, modifier: int = 0) -> None:
        if unit is None:
            return
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        current = int(sr.get("battle_shock_test_modifier", 0) or 0)
        sr["battle_shock_test_modifier"] = current + int(modifier or 0)
        unit.special_rules = sr
        try:
            battle_round = int(getattr(game, "turn", 0) or 0)
        except Exception:
            battle_round = 1
        try:
            unit.take_battle_shock_test(battle_round)
        except Exception:
            return
