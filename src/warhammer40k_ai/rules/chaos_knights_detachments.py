from __future__ import annotations

from typing import Iterable, Optional

from .detachment_manager import DetachmentManagerBase
from ..utility.aura_utils import unit_within_range_of_unit
from ..utility.dice import get_roll
from ..utility.entity_ids import get_entity_id


class ChaosKnightsDetachmentManager(DetachmentManagerBase):
    faction_id = "QT"

    MALEFIC_SURGE_NAME = "Malefic Surge"
    MARKED_PREY_NAME = "Marked Prey"
    DARK_SACRIFICE_NAME = "Dark Sacrifice"
    TYRANNICAL_COURT_NAME = "Tyrannical Court"
    PARAGONS_OF_TERROR_NAME = "Paragons of Terror"
    DETACHMENT_INFERNAL_LANCE = "Infernal Lance"
    DETACHMENT_HOUNDPACK_LANCE = "Houndpack Lance"
    DETACHMENT_ICONOCLAST_FIEFDOM = "Iconoclast Fiefdom"
    DETACHMENT_LORDS_OF_DREAD = "Lords of Dread"
    DETACHMENT_TRAITORIS_LANCE = "Traitoris Lance"
    HOUNDPACK_CHARACTER_SELECTION_ABILITY = "houndpack_lance_character_selection"
    ICONOCLAST_DARK_SACRIFICE_ABILITY = "iconoclast_dark_sacrifice"
    ICONOCLAST_PAVE_THE_WAY_SELECTION_ABILITY = "iconoclast_pave_the_way_selection"
    TRAITORIS_PARAGONS_ABILITY = "traitoris_paragons_of_terror_bonus"
    HOUNDPACK_PREYSLAYERS_MANTLE_ENHANCEMENT_ID = "000010312002"
    HOUNDPACK_FINAL_HOWL_ENHANCEMENT_ID = "000010312003"
    HOUNDPACK_LOPING_PREDATOR_ENHANCEMENT_ID = "000010312004"
    HOUNDPACK_PANOPLY_ENHANCEMENT_ID = "000010312005"
    ICONOCLAST_PROFANE_ALTAR_ENHANCEMENT_ID = "000009765002"
    ICONOCLAST_PAVE_THE_WAY_ENHANCEMENT_ID = "000009765003"
    ICONOCLAST_TYRANTS_BANNER_ENHANCEMENT_ID = "000009765004"
    ICONOCLAST_DIABOLICAL_RESILIENCE_ENHANCEMENT_ID = "000009765005"

    def __init__(self, army=None):
        super().__init__(army)
        self._malefic_surge_declined_turn: Optional[int] = None
        self._malefic_surge_declined_owner: str = ""
        self.houndpack_marked_prey_unit_id: str = ""
        self.houndpack_marked_prey_turn: int = 0
        self.houndpack_marked_prey_owner_id: str = ""
        self._houndpack_character_unit_ids: set[str] = set()
        self._houndpack_character_selection_resolved: bool = False
        self._iconoclast_pave_the_way_unit_ids: set[str] = set()
        self._iconoclast_pave_the_way_selection_resolved: bool = False
        self._lords_of_dread_claimed_for_dark_gods_used_round: int = 0
        self._traitoris_paragons_bonus_round: int = 0

    def is_infernal_lance(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_INFERNAL_LANCE)

    def is_houndpack_lance(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_HOUNDPACK_LANCE)

    def is_iconoclast_fiefdom(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_ICONOCLAST_FIEFDOM)

    def is_lords_of_dread(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_LORDS_OF_DREAD)

    def is_traitoris_lance(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches(self.DETACHMENT_TRAITORIS_LANCE)

    @staticmethod
    def _unit_root(unit):
        if unit is None:
            return None
        root_fn = getattr(unit, "get_attached_unit_root", None)
        if callable(root_fn):
            root = root_fn()
            if root is not None:
                return root
        return unit

    def _unit_root_id(self, unit) -> str:
        root = self._unit_root(unit)
        if root is None:
            return ""
        return str(get_entity_id(root) or "")

    def _iter_unique_army_roots(self) -> Iterable:
        army = self.army
        if army is None:
            return []
        seen: set[str] = set()
        roots = []
        for unit in list(getattr(army, "units", []) or []):
            root = self._unit_root(unit)
            if root is None:
                continue
            root_id = self._unit_root_id(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            roots.append(root)
        return roots

    def _unit_belongs_to_army(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        parent_fn = getattr(root, "get_parent_army", None)
        if callable(parent_fn):
            return parent_fn() is self.army
        return getattr(root, "parent_army", None) is self.army

    def _unit_has_war_dog_keyword(self, unit) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if self._unit_has_keyword(root, "WAR DOG"):
            return True
        root_name = str(getattr(root, "name", "") or "")
        return "war dog" in self._norm(root_name)

    def _model_has_war_dog_keyword(self, model, *, unit=None) -> bool:
        if model is not None:
            has_any = getattr(model, "has_any_keyword", None)
            if callable(has_any) and bool(has_any("WAR DOG")):
                return True
        return self._unit_has_war_dog_keyword(unit)

    @staticmethod
    def _unit_is_enemy_of_player(unit, player) -> bool:
        if unit is None or player is None:
            return False
        root = ChaosKnightsDetachmentManager._unit_root(unit)
        if root is None:
            return False
        parent_fn = getattr(root, "get_parent_army", None)
        if callable(parent_fn):
            unit_army = parent_fn()
        else:
            unit_army = getattr(root, "parent_army", None)
        player_army = getattr(player, "army", None)
        if unit_army is None or player_army is None:
            return False
        return unit_army is not player_army

    def _warlord_root(self):
        army = self.army
        if army is None:
            return None
        warlord = getattr(army, "warlord", None)
        if warlord is None:
            for unit in list(getattr(army, "units", []) or []):
                if bool(getattr(unit, "is_warlord", False)):
                    warlord = unit
                    break
        return self._unit_root(warlord)

    def _unit_is_damned(self, unit) -> bool:
        return self._unit_has_keyword(unit, "DAMNED")

    def _unit_is_titanic(self, unit) -> bool:
        return self._unit_has_keyword(unit, "TITANIC")

    def _iconoclast_damned_points_cap(self) -> int:
        army = self.army
        if army is None:
            return 0
        limit = int(getattr(army, "points_limit", 0) or 0)
        if limit <= 0:
            return 0
        if limit <= 1000:
            return 250
        if limit <= 2000:
            return 500
        return 750

    def _iconoclast_unit_has_active_enhancement(
        self,
        unit,
        *,
        flag_key: str,
        enhancement_id: str,
        enhancement_name: str,
    ) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        checker = getattr(root, "_attached_unit_has_active_enhancement", None)
        if callable(checker):
            return bool(
                checker(
                    flag_key,
                    enhancement_id=enhancement_id,
                    enhancement_name=enhancement_name,
                )
            )
        sr = self._unit_sr(root)
        if flag_key and bool(sr.get(flag_key)):
            return True
        enh = getattr(root, "enhancement", None)
        if enh is None:
            return False
        enh_id = str(getattr(enh, "id", "") or "").strip()
        if enhancement_id and enh_id == enhancement_id:
            return True
        enh_name = str(getattr(enh, "name", "") or "").strip().lower()
        return bool(enhancement_name and enh_name == enhancement_name.strip().lower())

    def _iconoclast_profane_altar_active(self, source_unit) -> bool:
        return self._iconoclast_unit_has_active_enhancement(
            source_unit,
            flag_key="enhancement_iconoclast_profane_altar",
            enhancement_id=self.ICONOCLAST_PROFANE_ALTAR_ENHANCEMENT_ID,
            enhancement_name="Profane Altar",
        )

    def _iconoclast_tyrants_banner_active(self, source_unit) -> bool:
        return self._iconoclast_unit_has_active_enhancement(
            source_unit,
            flag_key="enhancement_iconoclast_tyrants_banner",
            enhancement_id=self.ICONOCLAST_TYRANTS_BANNER_ENHANCEMENT_ID,
            enhancement_name="Tyrant's Banner",
        )

    def _iconoclast_pave_the_way_active(self, source_unit) -> bool:
        return self._iconoclast_unit_has_active_enhancement(
            source_unit,
            flag_key="enhancement_iconoclast_pave_the_way",
            enhancement_id=self.ICONOCLAST_PAVE_THE_WAY_ENHANCEMENT_ID,
            enhancement_name="Pave the Way",
        )

    def _houndpack_unit_has_active_enhancement(
        self,
        unit,
        *,
        flag_key: str,
        enhancement_id: str,
        enhancement_name: str,
    ) -> bool:
        return self._iconoclast_unit_has_active_enhancement(
            unit,
            flag_key=flag_key,
            enhancement_id=enhancement_id,
            enhancement_name=enhancement_name,
        )

    def _houndpack_final_howl_active(self, source_unit) -> bool:
        return self._houndpack_unit_has_active_enhancement(
            source_unit,
            flag_key="enhancement_houndpack_final_howl",
            enhancement_id=self.HOUNDPACK_FINAL_HOWL_ENHANCEMENT_ID,
            enhancement_name="Final Howl (Aura)",
        )

    def _houndpack_panoply_active(self, source_unit) -> bool:
        return self._houndpack_unit_has_active_enhancement(
            source_unit,
            flag_key="enhancement_houndpack_panoply_of_the_cursed_knight",
            enhancement_id=self.HOUNDPACK_PANOPLY_ENHANCEMENT_ID,
            enhancement_name="Panoply of the Cursed Knight",
        )

    def houndpack_final_howl_applies(self, *, attacker_unit=None, source_unit=None) -> bool:
        if not self.is_houndpack_lance():
            return False
        attacker_root = self._unit_root(attacker_unit)
        source_root = self._unit_root(source_unit)
        if attacker_root is None or source_root is None:
            return False
        if not self._unit_belongs_to_army(attacker_root) or not self._unit_belongs_to_army(source_root):
            return False
        if not self._unit_has_war_dog_keyword(attacker_root):
            return False
        if not self._unit_has_war_dog_keyword(source_root):
            return False
        if not self._houndpack_final_howl_active(source_root):
            return False
        if not self._unit_on_battlefield(attacker_root) or not self._unit_on_battlefield(source_root):
            return False
        source_sr = self._unit_sr(source_root)
        try:
            aura_range = float(source_sr.get("enhancement_houndpack_final_howl_range", 6.0) or 6.0)
        except (TypeError, ValueError):
            aura_range = 6.0
        return bool(
            unit_within_range_of_unit(
                source_root,
                attacker_root,
                float(max(0.0, aura_range)),
                use_attached_aggregate=True,
            )
        )

    def houndpack_panoply_ap_worsen(self, attacker_model, target_unit, *, weapon_profile=None, game=None) -> tuple[int, str]:
        del weapon_profile
        del game
        if not self.is_houndpack_lance():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return 0, ""
        if not self._unit_belongs_to_army(target_root):
            return 0, ""
        if not self._houndpack_panoply_active(target_root):
            return 0, ""
        if not self._unit_on_battlefield(target_root):
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._unit_root(attacker_unit)
        if attacker_root is not None and self._unit_belongs_to_army(attacker_root):
            return 0, ""
        return 1, "Panoply of the Cursed Knight"

    @staticmethod
    def _iter_alive_models(unit) -> list:
        root = ChaosKnightsDetachmentManager._unit_root(unit)
        if root is None:
            return []
        models_fn = getattr(root, "get_attached_unit_models", None)
        models = list(models_fn() or []) if callable(models_fn) else list(getattr(root, "models", []) or [])
        alive = []
        for model in models:
            if model is None:
                continue
            alive_attr = getattr(model, "is_alive", True)
            try:
                is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            except (TypeError, ValueError):
                is_alive = True
            if not is_alive:
                continue
            alive.append(model)
        alive.sort(key=lambda m: str(get_entity_id(m) or ""))
        return alive

    def _iconoclast_units_visible(self, source_unit, target_unit, *, game=None) -> bool:
        source_root = self._unit_root(source_unit)
        target_root = self._unit_root(target_unit)
        if source_root is None or target_root is None:
            return False
        if source_root is target_root:
            return True

        resolved_game = game
        if resolved_game is None:
            player = getattr(getattr(self.army, "player", None), "game", None) if self.army is not None else None
            resolved_game = player
        resolved_map = getattr(resolved_game, "map", None) if resolved_game is not None else None
        if resolved_map is None:
            return True

        source_models = list(self._iter_alive_models(source_root) or [])
        if not source_models:
            return False

        can_see_unit = getattr(resolved_game, "_model_can_see_unit", None)
        if callable(can_see_unit):
            for model in source_models:
                if bool(can_see_unit(model, target_root, game_map=resolved_map)):
                    return True
            return False

        los_fn = getattr(source_root, "_has_line_of_sight_to_target", None)
        if callable(los_fn):
            for model in source_models:
                if bool(los_fn(model, target_root, resolved_map)):
                    return True
            return False

        can_see_model = getattr(resolved_map, "can_model_see_model", None)
        if not callable(can_see_model):
            return True
        target_models = list(self._iter_alive_models(target_root) or [])
        if not target_models:
            return True
        for source_model in source_models:
            for target_model in target_models:
                if bool(can_see_model(source_model, target_model)):
                    return True
        return False

    @staticmethod
    def _iconoclast_mode_is_valid(mode: str) -> bool:
        return str(mode or "").strip().upper() in {"LETHAL_HITS", "SUSTAINED_HITS_1"}

    def _clear_iconoclast_dark_sacrifice(self, unit) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = self._unit_sr(root)
        for key in (
            "iconoclast_dark_sacrifice_active",
            "iconoclast_dark_sacrifice_choice",
            "iconoclast_dark_sacrifice_dual_keywords",
            "iconoclast_dark_sacrifice_source",
            "iconoclast_dark_sacrifice_expires_phase",
            "iconoclast_dark_sacrifice_turn",
            "iconoclast_dark_sacrifice_owner",
        ):
            sr.pop(key, None)
        root.special_rules = sr

    @staticmethod
    def _iconoclast_current_phase(game) -> str:
        phase = getattr(getattr(game, "phase", None), "name", None)
        if not phase:
            phase = getattr(game, "phase", "")
        return str(phase or "").strip().upper()

    @staticmethod
    def _iconoclast_current_owner_id(game) -> str:
        if game is None or not hasattr(game, "get_current_player"):
            return ""
        current_player = game.get_current_player()
        return str(getattr(current_player, "id", "") or "")

    def active_iconoclast_dark_sacrifice_mode(self, unit, *, game=None, player=None) -> str:
        root = self._unit_root(unit)
        if root is None:
            return ""
        sr = self._unit_sr(root)
        if not bool(sr.get("iconoclast_dark_sacrifice_active")):
            return ""
        mode = str(sr.get("iconoclast_dark_sacrifice_choice", "") or "").strip().upper()
        if not self._iconoclast_mode_is_valid(mode):
            self._clear_iconoclast_dark_sacrifice(root)
            return ""
        if game is not None:
            expires_phase = str(sr.get("iconoclast_dark_sacrifice_expires_phase", "") or "").strip().upper()
            if expires_phase and expires_phase != self._iconoclast_current_phase(game):
                self._clear_iconoclast_dark_sacrifice(root)
                return ""
            owner_id = str(sr.get("iconoclast_dark_sacrifice_owner", "") or "")
            current_owner = str(getattr(player, "id", "") or "") if player is not None else self._iconoclast_current_owner_id(game)
            if owner_id and current_owner and owner_id != current_owner:
                self._clear_iconoclast_dark_sacrifice(root)
                return ""
            try:
                active_turn = int(sr.get("iconoclast_dark_sacrifice_turn", 0) or 0)
                current_turn = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                active_turn = 0
                current_turn = 0
            if active_turn and current_turn and active_turn != current_turn:
                self._clear_iconoclast_dark_sacrifice(root)
                return ""
        return mode

    def iconoclast_dark_sacrifice_weapon_keywords(self, model, *, attack_type: str = "", game=None) -> tuple[list[str], str]:
        del attack_type
        if not self.is_iconoclast_fiefdom():
            return [], ""
        if model is None:
            return [], ""
        source_unit = getattr(model, "parent_unit", None)
        root = self._unit_root(source_unit)
        if root is None:
            return [], ""
        if not self._unit_belongs_to_army(root):
            return [], ""
        if not self._unit_is_chaos_knights(root):
            return [], ""
        mode = self.active_iconoclast_dark_sacrifice_mode(root, game=game)
        if not mode:
            return [], ""
        sr = self._unit_sr(root)
        dual_keywords = bool(sr.get("iconoclast_dark_sacrifice_dual_keywords"))
        keywords: list[str] = []
        if dual_keywords or mode == "LETHAL_HITS":
            keywords.append("LETHAL HITS")
        if dual_keywords or mode == "SUSTAINED_HITS_1":
            keywords.append("SUSTAINED HITS 1")
        if not keywords:
            return [], ""
        return keywords, self.DARK_SACRIFICE_NAME

    def iconoclast_dark_sacrifice_weapon_keyword(self, model, *, attack_type: str = "", game=None) -> tuple[str, str]:
        keywords, source = self.iconoclast_dark_sacrifice_weapon_keywords(
            model,
            attack_type=attack_type,
            game=game,
        )
        if not keywords:
            return "", ""
        return str(keywords[0] or ""), source

    def iconoclast_dread_tyrants_applies(self, *, attacker_unit=None, source_unit=None) -> bool:
        if not self.is_iconoclast_fiefdom():
            return False
        attacker_root = self._unit_root(attacker_unit)
        source_root = self._unit_root(source_unit)
        if attacker_root is None or source_root is None:
            return False
        if not self._unit_belongs_to_army(attacker_root) or not self._unit_belongs_to_army(source_root):
            return False
        if not self._unit_is_damned(attacker_root):
            return False
        if not self._unit_is_chaos_knights(source_root):
            return False
        if not self._unit_is_titanic(source_root):
            return False
        if not self._unit_on_battlefield(attacker_root) or not self._unit_on_battlefield(source_root):
            return False
        return bool(
            unit_within_range_of_unit(
                source_root,
                attacker_root,
                9.0,
                use_attached_aggregate=True,
            )
        )

    def _iconoclast_dark_sacrifice_candidates(self, source_unit, *, game=None) -> list:
        source_root = self._unit_root(source_unit)
        if source_root is None:
            return []
        if not self._unit_on_battlefield(source_root):
            return []
        tyrants_banner_active = self._iconoclast_tyrants_banner_active(source_root)
        candidates = []
        seen_ids: set[str] = set()
        for root in list(self._iter_unique_army_roots()):
            if root is None:
                continue
            if not self._unit_is_damned(root):
                continue
            if not self._unit_on_battlefield(root):
                continue
            within_6 = bool(unit_within_range_of_unit(source_root, root, 6.0, use_attached_aggregate=True))
            visible = bool(tyrants_banner_active and self._iconoclast_units_visible(source_root, root, game=game))
            if not within_6 and not visible:
                continue
            unit_id = self._unit_root_id(root)
            if not unit_id or unit_id in seen_ids:
                continue
            seen_ids.add(unit_id)
            candidates.append(root)
        candidates.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return candidates

    def _pending_iconoclast_dark_sacrifice_request(self, game, *, source_unit_id: str, trigger: str) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        source_id = str(source_unit_id or "")
        trigger_key = str(trigger or "").strip().lower()
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != self.ICONOCLAST_DARK_SACRIFICE_ABILITY:
                continue
            if source_id and str(ctx.get("source_unit_id", "") or "") != source_id:
                continue
            if trigger_key and str(ctx.get("trigger", "") or "").strip().lower() != trigger_key:
                continue
            return True
        return False

    def queue_iconoclast_dark_sacrifice_choice(self, source_unit, *, trigger: str, game=None):
        if not self.is_iconoclast_fiefdom():
            return None
        if self.army is None:
            return None
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return None
        source_root = self._unit_root(source_unit)
        if source_root is None:
            return None
        if not self._unit_belongs_to_army(source_root):
            return None
        if not self._unit_is_chaos_knights(source_root):
            return None
        if not self._unit_on_battlefield(source_root):
            return None
        owner = getattr(self.army, "player", None)
        if owner is None:
            return None
        if hasattr(game, "get_current_player") and game.get_current_player() is not owner:
            return None
        source_unit_id = str(get_entity_id(source_root) or "")
        if not source_unit_id:
            return None
        trigger_key = str(trigger or "").strip().lower()
        if not trigger_key:
            return None
        if self._pending_iconoclast_dark_sacrifice_request(
            game,
            source_unit_id=source_unit_id,
            trigger=trigger_key,
        ):
            return None

        candidates = list(self._iconoclast_dark_sacrifice_candidates(source_root, game=game) or [])
        if not candidates:
            return None
        profane_altar_active = self._iconoclast_profane_altar_active(source_root)
        tyrants_banner_active = self._iconoclast_tyrants_banner_active(source_root)
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        options = [
            DecisionOption.create(
                "None",
                payload={
                    "skip": True,
                    "action": "skip",
                    "source_unit_id": source_unit_id,
                    "trigger": trigger_key,
                },
            )
        ]
        candidate_ids = []
        for candidate in candidates:
            candidate_id = str(get_entity_id(candidate) or "")
            if not candidate_id:
                continue
            candidate_ids.append(candidate_id)
            name = str(getattr(candidate, "name", "Unit") or "Unit")
            if profane_altar_active:
                options.append(
                    DecisionOption.create(
                        f"{name}: Lethal Hits + Sustained Hits 1",
                        payload={
                            "target_unit_id": candidate_id,
                            "damned_unit_id": candidate_id,
                            "source_unit_id": source_unit_id,
                            "sacrifice_mode": "LETHAL_HITS",
                            "trigger": trigger_key,
                        },
                    )
                )
                continue
            options.append(
                DecisionOption.create(
                    f"{name}: Lethal Hits",
                    payload={
                        "target_unit_id": candidate_id,
                        "damned_unit_id": candidate_id,
                        "source_unit_id": source_unit_id,
                        "sacrifice_mode": "LETHAL_HITS",
                        "trigger": trigger_key,
                    },
                )
            )
            options.append(
                DecisionOption.create(
                    f"{name}: Sustained Hits 1",
                    payload={
                        "target_unit_id": candidate_id,
                        "damned_unit_id": candidate_id,
                        "source_unit_id": source_unit_id,
                        "sacrifice_mode": "SUSTAINED_HITS_1",
                        "trigger": trigger_key,
                    },
                )
            )
        if len(options) <= 1:
            return None

        range_or_visibility_text = 'within 6"' if not tyrants_banner_active else 'within 6" or visible'

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"Dark Sacrifice: select one friendly DAMNED unit {range_or_visibility_text} and choose a weapon bonus (or None).",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "ability": self.ICONOCLAST_DARK_SACRIFICE_ABILITY,
                "ability_name": self.DARK_SACRIFICE_NAME,
                "army_id": str(get_entity_id(self.army) or ""),
                "source_unit_id": source_unit_id,
                "trigger": trigger_key,
                "candidate_damned_unit_ids": sorted({cid for cid in candidate_ids if cid}),
                "allowed_modes": ["LETHAL_HITS"] if profane_altar_active else ["LETHAL_HITS", "SUSTAINED_HITS_1"],
                "profane_altar_active": bool(profane_altar_active),
                "tyrants_banner_active": bool(tyrants_banner_active),
                "optional": True,
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)
        return request

    def validate_iconoclast_dark_sacrifice_choice(
        self,
        source_unit,
        damned_unit,
        *,
        mode: str,
        game=None,
        player=None,
    ) -> tuple[bool, str]:
        if not self.is_iconoclast_fiefdom():
            return False, "Dark Sacrifice requires Iconoclast Fiefdom."
        source_root = self._unit_root(source_unit)
        if source_root is None:
            return False, "Dark Sacrifice source unit is missing."
        if not self._unit_belongs_to_army(source_root):
            return False, "Dark Sacrifice source unit must belong to your army."
        if not self._unit_is_chaos_knights(source_root):
            return False, "Dark Sacrifice source must be a CHAOS KNIGHTS unit."
        if not self._unit_on_battlefield(source_root):
            return False, "Dark Sacrifice source unit must be on the battlefield."
        if player is not None and getattr(self.army, "player", None) is not player:
            return False, "Dark Sacrifice can only be selected by the controlling player."
        mode_key = str(mode or "").strip().upper()
        if not self._iconoclast_mode_is_valid(mode_key):
            return False, "Dark Sacrifice mode must be LETHAL_HITS or SUSTAINED_HITS_1."
        damned_root = self._unit_root(damned_unit)
        if damned_root is None:
            return False, "Dark Sacrifice requires a DAMNED unit target."
        if not self._unit_belongs_to_army(damned_root):
            return False, "Dark Sacrifice target must be a friendly unit."
        if not self._unit_is_damned(damned_root):
            return False, "Dark Sacrifice target must have the DAMNED keyword."
        if not self._unit_on_battlefield(damned_root):
            return False, "Dark Sacrifice target must be on the battlefield."
        within_6 = bool(unit_within_range_of_unit(source_root, damned_root, 6.0, use_attached_aggregate=True))
        tyrants_banner_active = self._iconoclast_tyrants_banner_active(source_root)
        visible = bool(tyrants_banner_active and self._iconoclast_units_visible(source_root, damned_root, game=game))
        if not within_6 and not visible:
            if tyrants_banner_active:
                return False, "Dark Sacrifice target must be within 6\" or visible."
            return False, "Dark Sacrifice target must be within 6\"."
        return True, ""

    def _destroy_models_for_dark_sacrifice(self, unit, *, count: int, game=None) -> int:
        root = self._unit_root(unit)
        if root is None:
            return 0
        try:
            target = int(count or 0)
        except (TypeError, ValueError):
            target = 0
        if target <= 0:
            return 0
        models = [model for model in list(getattr(root, "models", []) or []) if model is not None and bool(getattr(model, "is_alive", False))]
        models.sort(key=lambda m: str(get_entity_id(m) or ""))
        removed = 0
        for model in models:
            if removed >= target:
                break
            remove_model = getattr(root, "remove_model", None)
            if not callable(remove_model):
                break
            remove_model(model, False, game_map=getattr(game, "map", None) if game is not None else None)
            removed += 1
        return removed

    def apply_iconoclast_dark_sacrifice(
        self,
        source_unit,
        damned_unit,
        *,
        mode: str,
        game=None,
        player=None,
    ) -> dict:
        source_root = self._unit_root(source_unit)
        damned_root = self._unit_root(damned_unit)
        valid, reason = self.validate_iconoclast_dark_sacrifice_choice(
            source_root,
            damned_root,
            mode=mode,
            game=game,
            player=player,
        )
        if not valid:
            return {"ok": False, "reason": reason}
        mode_key = str(mode or "").strip().upper()
        leadership_fn = getattr(damned_root, "pass_leadership_check", None)
        if not callable(leadership_fn):
            return {"ok": False, "reason": "Dark Sacrifice requires a Leadership test handler."}
        passed = bool(leadership_fn())
        raw = get_roll("D3")
        try:
            rolled = int(raw or 0)
        except (TypeError, ValueError):
            rolled = 0
        if rolled <= 0:
            rolled = 1
        profane_altar_active = self._iconoclast_profane_altar_active(source_root)
        if profane_altar_active:
            destroy_count = 3 if passed else 6
        else:
            destroy_count = rolled if passed else rolled + 3
        destroyed_models = self._destroy_models_for_dark_sacrifice(damned_root, count=destroy_count, game=game)

        sr = self._unit_sr(source_root)
        sr["iconoclast_dark_sacrifice_active"] = True
        sr["iconoclast_dark_sacrifice_choice"] = mode_key
        sr["iconoclast_dark_sacrifice_dual_keywords"] = bool(profane_altar_active)
        sr["iconoclast_dark_sacrifice_source"] = self.DARK_SACRIFICE_NAME
        sr["iconoclast_dark_sacrifice_expires_phase"] = self._iconoclast_current_phase(game)
        sr["iconoclast_dark_sacrifice_turn"] = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        owner = player if player is not None else getattr(self.army, "player", None)
        sr["iconoclast_dark_sacrifice_owner"] = str(getattr(owner, "id", "") or "")
        source_root.special_rules = sr
        granted_keywords = (
            ["LETHAL HITS", "SUSTAINED HITS 1"]
            if profane_altar_active
            else (["LETHAL HITS"] if mode_key == "LETHAL_HITS" else ["SUSTAINED HITS 1"])
        )
        return {
            "ok": True,
            "source_unit_id": self._unit_root_id(source_root),
            "damned_unit_id": self._unit_root_id(damned_root),
            "mode": mode_key,
            "weapon_keywords": list(granted_keywords),
            "leadership_passed": passed,
            "destroy_target": int(destroy_count),
            "destroyed_models": int(destroyed_models or 0),
        }

    def _validate_iconoclast_restrictions(self) -> list[str]:
        errors: list[str] = []
        if not self.is_iconoclast_fiefdom():
            return errors
        damned_units = []
        seen_ids: set[str] = set()
        for root in list(self._iter_unique_army_roots()):
            if root is None:
                continue
            root_id = self._unit_root_id(root)
            if root_id and root_id in seen_ids:
                continue
            if root_id:
                seen_ids.add(root_id)
            if self._unit_is_damned(root):
                damned_units.append(root)
        if not damned_units:
            return errors
        points_cap = self._iconoclast_damned_points_cap()
        total_points = sum(int(getattr(unit, "get_unit_cost", lambda: 0)() or 0) for unit in damned_units)
        if points_cap <= 0 or total_points > points_cap:
            errors.append(
                f"Iconoclast Fiefdom (Wretched Thralls): DAMNED units total {int(total_points)} points (cap {int(points_cap)})."
            )
        for unit in damned_units:
            if bool(getattr(unit, "is_warlord", False)):
                errors.append("Iconoclast Fiefdom (Wretched Thralls): DAMNED units cannot be your Warlord.")
                break
        return errors

    def tyrannical_court_objective_control_bonus(self, model, *, unit=None) -> tuple[int, str]:
        if not self.is_lords_of_dread():
            return 0, ""
        if model is None:
            return 0, ""
        root = self._unit_root(unit or getattr(model, "parent_unit", None))
        if root is None:
            return 0, ""
        if not self._unit_belongs_to_army(root):
            return 0, ""
        if not self._unit_is_chaos_knights(root):
            return 0, ""
        is_character = bool(getattr(model, "is_character", False))
        if not is_character and not self._unit_has_keyword(root, "CHARACTER"):
            return 0, ""
        return 2, self.TYRANNICAL_COURT_NAME

    def warlord_on_battlefield(self) -> bool:
        if not self.is_lords_of_dread():
            return False
        warlord = self._warlord_root()
        if warlord is None:
            return False
        if not self._unit_belongs_to_army(warlord):
            return False
        return self._unit_on_battlefield(warlord)

    def can_use_tyrannical_court_claimed_for_dark_gods_discount(self, *, game=None) -> bool:
        if not self.is_lords_of_dread():
            return False
        if not self.warlord_on_battlefield():
            return False
        game_obj = game
        if game_obj is None:
            game_obj = getattr(getattr(self.army, "player", None), "game", None) if self.army is not None else None
        if game_obj is None:
            return False
        try:
            battle_round = int(getattr(game_obj, "turn", 0) or 0)
        except (TypeError, ValueError):
            return False
        if battle_round <= 0:
            return False
        return int(self._lords_of_dread_claimed_for_dark_gods_used_round or 0) != battle_round

    def mark_tyrannical_court_claimed_for_dark_gods_discount_used(self, *, game=None) -> None:
        game_obj = game
        if game_obj is None:
            game_obj = getattr(getattr(self.army, "player", None), "game", None) if self.army is not None else None
        if game_obj is None:
            return
        try:
            battle_round = int(getattr(game_obj, "turn", 0) or 0)
        except (TypeError, ValueError):
            return
        if battle_round <= 0:
            return
        self._lords_of_dread_claimed_for_dark_gods_used_round = battle_round

    def can_queue_traitoris_paragons_bonus_choice(self, *, battle_round: int, game=None) -> bool:
        if not self.is_traitoris_lance():
            return False
        try:
            br = int(battle_round or 0)
        except (TypeError, ValueError):
            br = 0
        if br != 1:
            return False
        if int(self._traitoris_paragons_bonus_round or 0) == br:
            return False
        if game is not None and not bool(getattr(game, "is_authoritative", True)):
            return False
        harbingers = getattr(self.army, "harbingers_of_dread", None) if self.army is not None else None
        if harbingers is None:
            return False
        available = list(getattr(harbingers, "get_available_dread_abilities", lambda: [])() or [])
        return bool(available)

    def mark_traitoris_paragons_bonus_used(self, *, battle_round: int | None = None, game=None) -> None:
        br = battle_round
        if br is None and game is not None:
            br = getattr(game, "turn", 0)
        try:
            resolved = int(br or 0)
        except (TypeError, ValueError):
            resolved = 0
        if resolved <= 0:
            return
        self._traitoris_paragons_bonus_round = resolved

    def _pending_traitoris_paragons_request(self, game, *, army_id: str, battle_round: int) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_CHOOSE_HARBINGER

        target_army_id = str(army_id or "")
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_HARBINGER:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != self.TRAITORIS_PARAGONS_ABILITY:
                continue
            if target_army_id and str(ctx.get("army_id", "") or "") != target_army_id:
                continue
            try:
                req_round = int(ctx.get("battle_round", 0) or 0)
            except (TypeError, ValueError):
                req_round = 0
            if req_round and req_round != int(battle_round or 0):
                continue
            return True
        return False

    def queue_traitoris_paragons_bonus_choice(self, *, battle_round: int, game=None, player=None):
        if not self.can_queue_traitoris_paragons_bonus_choice(battle_round=battle_round, game=game):
            return None
        if game is None:
            return None
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return None
        harbingers = getattr(self.army, "harbingers_of_dread", None) if self.army is not None else None
        if harbingers is None:
            return None
        available = list(getattr(harbingers, "get_available_dread_abilities", lambda: [])() or [])
        available.sort(key=lambda dread: str(getattr(dread, "key", "") or ""))
        if not available:
            self.mark_traitoris_paragons_bonus_used(battle_round=battle_round, game=game)
            return None

        from ..engine.decision_kinds import DECISION_CHOOSE_HARBINGER
        from ..engine.decisions import DecisionOption, DecisionRequest

        army_id = str(get_entity_id(self.army) or "")
        if self._pending_traitoris_paragons_request(game, army_id=army_id, battle_round=int(battle_round or 0)):
            return None

        options = [
            DecisionOption.create(
                "None",
                payload={"skip": True, "action": "skip", "army_id": army_id},
            )
        ]
        allowed_choice_keys: list[str] = []
        for dread in available:
            dread_key = str(getattr(dread, "key", "") or "").strip().upper()
            if not dread_key:
                continue
            allowed_choice_keys.append(dread_key)
            options.append(
                DecisionOption.create(
                    str(getattr(dread, "name", dread_key) or dread_key),
                    payload={
                        "choice_key": dread_key,
                        "summary": str(getattr(dread, "summary", "") or ""),
                        "army_id": army_id,
                    },
                )
            )
        if len(options) <= 1:
            self.mark_traitoris_paragons_bonus_used(battle_round=battle_round, game=game)
            return None

        request = DecisionRequest.create(
            DECISION_CHOOSE_HARBINGER,
            "Paragons of Terror: select one additional Dread ability (or None).",
            player_id=getattr(owner, "id", None),
            options=options,
            context={
                "army_id": army_id,
                "battle_round": int(battle_round or 0),
                "ability": self.TRAITORIS_PARAGONS_ABILITY,
                "ability_name": self.PARAGONS_OF_TERROR_NAME,
                "allowed_choice_keys": list(allowed_choice_keys),
                "optional": True,
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)
        return request

    def apply_houndpack_lance_battleline_keywords(self, unit=None) -> None:
        if not self.is_houndpack_lance():
            return
        roots = [self._unit_root(unit)] if unit is not None else list(self._iter_unique_army_roots())
        for root in roots:
            if root is None:
                continue
            if not self._unit_has_war_dog_keyword(root):
                continue
            keywords = list(getattr(root, "keywords", []) or [])
            if any(str(keyword).strip().upper() == "BATTLELINE" for keyword in keywords):
                continue
            keywords.append("Battleline")
            root.keywords = keywords

    def _remove_houndpack_character_keyword(self, unit) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        sr = self._unit_sr(root)
        if not bool(sr.get("houndpack_lance_character_granted")):
            return
        keywords = [
            keyword
            for keyword in list(getattr(root, "keywords", []) or [])
            if str(keyword).strip().upper() != "CHARACTER"
        ]
        root.keywords = keywords
        sr.pop("houndpack_lance_character_granted", None)
        root.special_rules = sr

    def _grant_houndpack_character_keyword(self, unit) -> None:
        root = self._unit_root(unit)
        if root is None:
            return
        keywords = list(getattr(root, "keywords", []) or [])
        if not any(str(keyword).strip().upper() == "CHARACTER" for keyword in keywords):
            keywords.append("Character")
            root.keywords = keywords
        sr = self._unit_sr(root)
        sr["houndpack_lance_character_granted"] = True
        root.special_rules = sr

    def _reconcile_houndpack_character_keywords(self) -> None:
        if not self.is_houndpack_lance():
            return
        selected_ids = {str(unit_id or "").strip() for unit_id in self._houndpack_character_unit_ids if str(unit_id or "").strip()}
        valid_ids: set[str] = set()
        for root in list(self._iter_unique_army_roots()):
            if root is None:
                continue
            root_id = self._unit_root_id(root)
            if not root_id:
                continue
            if root_id in selected_ids:
                valid_ids.add(root_id)
                self._grant_houndpack_character_keyword(root)
                continue
            self._remove_houndpack_character_keyword(root)
        self._houndpack_character_unit_ids = valid_ids

    def _houndpack_character_candidates(self) -> list:
        candidates = []
        seen_ids: set[str] = set()
        for root in list(self._iter_unique_army_roots()):
            if root is None:
                continue
            if not self._unit_has_war_dog_keyword(root):
                continue
            root_id = self._unit_root_id(root)
            if not root_id or root_id in seen_ids:
                continue
            seen_ids.add(root_id)
            candidates.append(root)
        candidates.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return candidates

    def can_select_houndpack_character_unit(self, unit) -> bool:
        if not self.is_houndpack_lance():
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self._unit_has_war_dog_keyword(root):
            return False
        root_id = self._unit_root_id(root)
        if not root_id:
            return False
        if root_id in self._houndpack_character_unit_ids:
            return True
        return len(self._houndpack_character_unit_ids) < 3

    def select_houndpack_character_unit(self, unit) -> bool:
        if not self.can_select_houndpack_character_unit(unit):
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        root_id = self._unit_root_id(root)
        if not root_id:
            return False
        self._houndpack_character_unit_ids.add(root_id)
        self._grant_houndpack_character_keyword(root)
        self._reconcile_houndpack_character_keywords()
        return True

    def ensure_houndpack_character_selection(self) -> None:
        if not self.is_houndpack_lance():
            return
        candidates = list(self._houndpack_character_candidates())
        if len(candidates) < 3:
            self._reconcile_houndpack_character_keywords()
            return
        candidate_ids = {self._unit_root_id(unit) for unit in candidates}
        selected = [
            unit_id
            for unit_id in sorted(self._houndpack_character_unit_ids)
            if unit_id in candidate_ids
        ]
        prioritized = sorted(
            candidates,
            key=lambda unit: (
                0 if getattr(unit, "enhancement", None) is not None or bool(getattr(unit, "is_warlord", False)) else 1,
                str(get_entity_id(unit) or ""),
            ),
        )
        for candidate in prioritized:
            if len(selected) >= 3:
                break
            root_id = self._unit_root_id(candidate)
            if not root_id or root_id in selected:
                continue
            selected.append(root_id)
        self._houndpack_character_unit_ids = set(selected[:3])
        self._reconcile_houndpack_character_keywords()

    def _pending_houndpack_character_request(self, game, *, army_id: str) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS

        target_army_id = str(army_id or "")
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_SELECT_REALM_OF_CHAOS_UNITS:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != self.HOUNDPACK_CHARACTER_SELECTION_ABILITY:
                continue
            if target_army_id and str(ctx.get("army_id", "") or "") != target_army_id:
                continue
            return True
        return False

    def queue_houndpack_lance_character_selection_request(self, *, game=None, player=None) -> None:
        if not self.is_houndpack_lance():
            return
        if self.army is None:
            return
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return

        self.apply_houndpack_lance_battleline_keywords()
        candidates = list(self._houndpack_character_candidates() or [])
        if len(candidates) < 3:
            return
        if len(candidates) == 3:
            self.ensure_houndpack_character_selection()
            self._houndpack_character_selection_resolved = True
            return
        if self._houndpack_character_selection_resolved and len(self._houndpack_character_unit_ids) == 3:
            return

        army_id = str(get_entity_id(self.army) or "")
        if self._pending_houndpack_character_request(game, army_id=army_id):
            return

        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
        from ..engine.decisions import DecisionOption, DecisionRequest

        candidate_ids = [str(get_entity_id(unit) or "") for unit in candidates if str(get_entity_id(unit) or "")]
        if len(candidate_ids) < 3:
            return
        request = DecisionRequest.create(
            DECISION_SELECT_REALM_OF_CHAOS_UNITS,
            "Houndpack Lance: select exactly three WAR DOG units to gain CHARACTER.",
            player_id=getattr(owner, "id", None),
            options=[DecisionOption.create("Confirm", payload={"action": "confirm"})],
            context={
                "army_id": army_id,
                "ability": self.HOUNDPACK_CHARACTER_SELECTION_ABILITY,
                "ability_name": "Marked Prey",
                "phase": "Muster Armies step",
                "max_units": 3,
                "required_units": 3,
                "allowed_unit_ids": list(candidate_ids),
                "title": "Houndpack Lance",
                "subtitle": "Select exactly three WAR DOG units.",
                "instruction": "Selected units gain the CHARACTER keyword until the end of the battle.",
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)

    def houndpack_character_selection_is_valid(self, unit_ids, *, game=None) -> tuple[bool, str]:
        del game
        if not self.is_houndpack_lance():
            return False, "Houndpack Lance is not active for this army."
        if not isinstance(unit_ids, list):
            return False, "Houndpack Lance selection requires unit_ids."
        unique_ids = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        if len(unique_ids) != 3:
            return False, "Houndpack Lance must select exactly three WAR DOG units."
        candidates = {
            str(get_entity_id(unit) or ""): unit
            for unit in list(self._houndpack_character_candidates() or [])
            if str(get_entity_id(unit) or "")
        }
        for uid in unique_ids:
            if uid not in candidates:
                return False, "Houndpack Lance selection contains an ineligible unit."
        return True, ""

    def apply_houndpack_lance_character_selection(self, unit_ids, *, game=None) -> list[str]:
        del game
        selected = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        valid, _reason = self.houndpack_character_selection_is_valid(selected)
        if not valid:
            return []
        self._houndpack_character_unit_ids = set(selected)
        self._houndpack_character_selection_resolved = True
        self._reconcile_houndpack_character_keywords()
        return list(selected)

    def _iconoclast_pave_the_way_sources(self) -> list:
        if not self.is_iconoclast_fiefdom():
            return []
        sources = []
        seen_ids: set[str] = set()
        for root in list(self._iter_unique_army_roots()):
            if root is None:
                continue
            if not self._iconoclast_pave_the_way_active(root):
                continue
            unit_id = self._unit_root_id(root)
            if not unit_id or unit_id in seen_ids:
                continue
            seen_ids.add(unit_id)
            sources.append(root)
        sources.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return sources

    def _iconoclast_pave_the_way_scout_distance(self) -> float:
        distance = 6.0
        for source in list(self._iconoclast_pave_the_way_sources() or []):
            sr = self._unit_sr(source)
            try:
                value = float(sr.get("enhancement_iconoclast_pave_the_way_scouts_distance", 6) or 6)
            except (TypeError, ValueError):
                value = 6.0
            if value > distance:
                distance = float(value)
        return float(max(0.0, distance))

    def _iconoclast_pave_the_way_candidates(self) -> list:
        if not self.is_iconoclast_fiefdom():
            return []
        if not list(self._iconoclast_pave_the_way_sources() or []):
            return []
        candidates = []
        seen_ids: set[str] = set()
        for root in list(self._iter_unique_army_roots()):
            if root is None:
                continue
            if not self._unit_is_damned(root):
                continue
            unit_id = self._unit_root_id(root)
            if not unit_id or unit_id in seen_ids:
                continue
            seen_ids.add(unit_id)
            candidates.append(root)
        candidates.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return candidates

    def _pending_iconoclast_pave_the_way_request(self, game, *, army_id: str) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS

        target_army_id = str(army_id or "")
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_SELECT_REALM_OF_CHAOS_UNITS:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != self.ICONOCLAST_PAVE_THE_WAY_SELECTION_ABILITY:
                continue
            if target_army_id and str(ctx.get("army_id", "") or "") != target_army_id:
                continue
            return True
        return False

    def queue_iconoclast_pave_the_way_selection_request(self, *, game=None, player=None) -> None:
        if not self.is_iconoclast_fiefdom():
            return
        if self.army is None:
            return
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        owner = player if player is not None else getattr(self.army, "player", None)
        if owner is None:
            return
        if self._iconoclast_pave_the_way_selection_resolved:
            return
        candidates = list(self._iconoclast_pave_the_way_candidates() or [])
        if not candidates:
            return
        army_id = str(get_entity_id(self.army) or "")
        if self._pending_iconoclast_pave_the_way_request(game, army_id=army_id):
            return
        candidate_ids = [str(get_entity_id(unit) or "") for unit in candidates if str(get_entity_id(unit) or "")]
        if not candidate_ids:
            return

        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
        from ..engine.decisions import DecisionOption, DecisionRequest

        request = DecisionRequest.create(
            DECISION_SELECT_REALM_OF_CHAOS_UNITS,
            'Pave the Way: select up to three friendly DAMNED units to gain Scouts 6" (or None).',
            player_id=getattr(owner, "id", None),
            options=[DecisionOption.create("Confirm", payload={"action": "confirm"})],
            context={
                "army_id": army_id,
                "ability": self.ICONOCLAST_PAVE_THE_WAY_SELECTION_ABILITY,
                "ability_name": "Pave the Way",
                "phase": "Declare Battle Formations step",
                "max_units": 3,
                "allowed_unit_ids": list(candidate_ids),
                "title": "Pave the Way",
                "subtitle": "Select up to three DAMNED units.",
                "instruction": 'Selected units gain Scouts 6" for this battle.',
                "optional": True,
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)

    def iconoclast_pave_the_way_selection_is_valid(self, unit_ids, *, game=None, player=None) -> tuple[bool, str]:
        del game
        if not self.is_iconoclast_fiefdom():
            return False, "Pave the Way requires Iconoclast Fiefdom."
        if player is not None and getattr(self.army, "player", None) is not player:
            return False, "Pave the Way can only be selected by the controlling player."
        if not isinstance(unit_ids, list):
            return False, "Pave the Way selection requires unit_ids."
        selected = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        if len(selected) > 3:
            return False, "Pave the Way can select up to three units."
        candidate_ids = {
            str(get_entity_id(unit) or "")
            for unit in list(self._iconoclast_pave_the_way_candidates() or [])
            if str(get_entity_id(unit) or "")
        }
        for uid in selected:
            if uid not in candidate_ids:
                return False, "Pave the Way selection contains an ineligible unit."
        return True, ""

    def apply_iconoclast_pave_the_way_selection(self, unit_ids, *, game=None, player=None) -> list[str]:
        del game
        selected = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        valid, _reason = self.iconoclast_pave_the_way_selection_is_valid(selected, player=player)
        if not valid:
            return []
        selected_ids = set(selected)
        scout_distance = self._iconoclast_pave_the_way_scout_distance()
        for root in list(self._iter_unique_army_roots()):
            if root is None:
                continue
            root_id = self._unit_root_id(root)
            sr = self._unit_sr(root)
            if root_id in selected_ids:
                sr["iconoclast_pave_the_way_active"] = True
                sr["iconoclast_pave_the_way_source"] = "Pave the Way"
                sr["iconoclast_pave_the_way_scout_distance"] = float(scout_distance)
            else:
                sr.pop("iconoclast_pave_the_way_active", None)
                sr.pop("iconoclast_pave_the_way_source", None)
                sr.pop("iconoclast_pave_the_way_scout_distance", None)
            root.special_rules = sr
        self._iconoclast_pave_the_way_unit_ids = set(selected_ids)
        self._iconoclast_pave_the_way_selection_resolved = True
        return list(sorted(selected_ids))

    def clear_marked_prey(self) -> None:
        self.houndpack_marked_prey_unit_id = ""
        self.houndpack_marked_prey_turn = 0
        self.houndpack_marked_prey_owner_id = ""

    def _collect_marked_prey_candidates(self, *, game=None, player=None) -> list:
        if game is None or player is None:
            return []
        get_enemy_units = getattr(game, "get_enemy_units", None)
        if not callable(get_enemy_units):
            return []
        enemy_units = list(get_enemy_units(player) or [])
        candidates = []
        seen_ids: set[str] = set()
        for enemy in enemy_units:
            root = self._unit_root(enemy)
            if root is None:
                continue
            root_id = self._unit_root_id(root)
            if not root_id or root_id in seen_ids:
                continue
            seen_ids.add(root_id)
            if not self._unit_on_battlefield(root):
                continue
            if not self._unit_is_enemy_of_player(root, player):
                continue
            candidates.append(root)
        candidates.sort(key=lambda unit: (self._norm(getattr(unit, "name", "")), self._unit_root_id(unit)))
        return candidates

    def build_marked_prey_request(self, *, game=None, player=None):
        if not self.is_houndpack_lance():
            return None
        if game is None or player is None:
            return None
        if self.army is None or getattr(self.army, "player", None) is not player:
            return None
        if not bool(getattr(game, "is_authoritative", True)):
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                if str(getattr(req, "player_id", "") or "") != str(getattr(player, "id", "") or ""):
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") == "marked_prey":
                    return None

        candidates = self._collect_marked_prey_candidates(game=game, player=player)
        if not candidates:
            return None

        options = []
        candidate_ids = []
        for candidate in candidates:
            unit_id = self._unit_root_id(candidate)
            if not unit_id:
                continue
            candidate_ids.append(unit_id)
            options.append(
                DecisionOption.create(
                    str(getattr(candidate, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": unit_id},
                )
            )
        if not options:
            return None
        army_id = str(get_entity_id(self.army) or "")
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Marked Prey: select one enemy unit.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "marked_prey",
                "ability_name": self.MARKED_PREY_NAME,
                "army_id": army_id,
                "candidate_unit_ids": list(candidate_ids),
                "optional": False,
            },
        )

    def is_valid_marked_prey_target(self, target_unit, *, player=None, game=None) -> bool:
        del game  # API parity with other target validators.
        if not self.is_houndpack_lance():
            return False
        root = self._unit_root(target_unit)
        if root is None:
            return False
        if not self._unit_on_battlefield(root):
            return False
        if player is not None and not self._unit_is_enemy_of_player(root, player):
            return False
        return bool(self._unit_root_id(root))

    def select_marked_prey(self, target_unit, *, game=None, player=None) -> bool:
        if not self.is_valid_marked_prey_target(target_unit, player=player, game=game):
            return False
        self.houndpack_marked_prey_unit_id = self._unit_root_id(target_unit)
        if game is not None:
            self.houndpack_marked_prey_turn = int(getattr(game, "turn", 0) or 0)
        else:
            self.houndpack_marked_prey_turn = 0
        self.houndpack_marked_prey_owner_id = str(getattr(player, "id", "") or "")
        return True

    def is_marked_prey_target(self, target_unit) -> bool:
        target_id = self._unit_root_id(target_unit)
        if not target_id:
            return False
        return str(self.houndpack_marked_prey_unit_id or "") == str(target_id)

    def marked_prey_sustained_hits_value(self, attacker_model, target_unit, *, game_map=None) -> tuple[int, str]:
        if not self.is_houndpack_lance():
            return 0, ""
        if not str(self.houndpack_marked_prey_unit_id or "").strip():
            return 0, ""
        if attacker_model is None or target_unit is None:
            return 0, ""
        target_root = self._unit_root(target_unit)
        if target_root is None or not self.is_marked_prey_target(target_root):
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._unit_root(attacker_unit)
        if attacker_root is None:
            return 0, ""
        if not self._unit_belongs_to_army(attacker_root):
            return 0, ""
        if not self._model_has_war_dog_keyword(attacker_model, unit=attacker_root):
            return 0, ""

        resolved_map = game_map
        if resolved_map is None:
            attacker_army = getattr(attacker_root, "get_parent_army", lambda: None)()
            attacker_player = getattr(attacker_army, "player", None) if attacker_army is not None else None
            game = getattr(attacker_player, "game", None) if attacker_player is not None else None
            resolved_map = getattr(game, "map", None) if game is not None else None
        los_fn = getattr(attacker_root, "_has_line_of_sight_to_target", None)
        if resolved_map is not None and callable(los_fn):
            if not bool(los_fn(attacker_model, target_root, resolved_map)):
                return 0, ""
        return 1, self.MARKED_PREY_NAME

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if game is None or player is None or self.army is None:
            return
        if getattr(self.army, "player", None) is not player:
            return
        if self.is_houndpack_lance():
            self.clear_marked_prey()
            request = self.build_marked_prey_request(game=game, player=player)
            if request is not None and hasattr(game, "request_decision"):
                game.request_decision(request)
        if self.is_infernal_lance():
            self.clear_empowered_at_command_phase_start(game=game, player=player)
            self.prompt_malefic_surge_selection(game=game, player=player)

    def validate_detachment_rules(self) -> list[str]:
        errors: list[str] = []
        if self.is_houndpack_lance():
            self.apply_houndpack_lance_battleline_keywords()
            candidates = list(self._houndpack_character_candidates())
            if len(candidates) < 3:
                errors.append("Houndpack Lance: your army must include three or more WAR DOG units.")
                self._reconcile_houndpack_character_keywords()
                return errors
            candidate_ids = {self._unit_root_id(unit) for unit in candidates}
            selected_valid = {
                unit_id for unit_id in self._houndpack_character_unit_ids
                if unit_id in candidate_ids
            }
            if len(selected_valid) > 3:
                errors.append("Houndpack Lance: exactly three WAR DOG units can gain the CHARACTER keyword.")
            self._houndpack_character_unit_ids = set(selected_valid)
            self.ensure_houndpack_character_selection()
            if len(self._houndpack_character_unit_ids) != 3:
                errors.append("Houndpack Lance: exactly three WAR DOG units must be selected to gain the CHARACTER keyword.")
        if self.is_iconoclast_fiefdom():
            errors.extend(self._validate_iconoclast_restrictions())
        return errors

    def _unit_is_chaos_knights(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if hasattr(unit, "has_any_keyword") and unit.has_any_keyword("CHAOS KNIGHTS"):
                return True
        except Exception:
            pass
        try:
            for kw in list(getattr(unit, "faction_keywords", []) or []):
                if str(kw or "").strip().upper() == "CHAOS KNIGHTS":
                    return True
        except Exception:
            pass
        try:
            return str(getattr(unit, "faction", "") or "").strip().upper() == "QT"
        except Exception:
            return False

    def _unit_on_battlefield(self, unit) -> bool:
        if unit is None:
            return False
        try:
            if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                return False
        except Exception:
            return False
        try:
            if not bool(getattr(unit, "deployed", True)):
                return False
        except Exception:
            pass
        try:
            if hasattr(unit, "is_in_reserves") and callable(unit.is_in_reserves) and unit.is_in_reserves():
                return False
            if bool(getattr(unit, "is_embarked", False)) or bool(getattr(unit, "embarked_in", None)):
                return False
        except Exception:
            pass
        return True

    def _current_turn_key(self, game=None) -> int:
        try:
            return int(getattr(game, "turn", 0) or 0)
        except Exception:
            return 0

    def _current_owner_id(self, unit=None, game=None) -> str:
        if unit is not None:
            try:
                army = unit.get_parent_army()
                player = getattr(army, "player", None) if army is not None else None
                return str(getattr(player, "id", "") or "")
            except Exception:
                return ""
        if game is not None:
            try:
                player = game.get_current_player()
                return str(getattr(player, "id", "") or "")
            except Exception:
                return ""
        return ""

    def _unit_sr(self, unit) -> dict:
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        return sr

    def is_unit_empowered(self, unit, *, game=None) -> bool:
        if unit is None:
            return False
        sr = self._unit_sr(unit)
        if not sr.get("malefic_surge_empowered"):
            return False
        owner = str(sr.get("malefic_surge_empowered_owner", "") or "")
        if owner:
            current = self._current_owner_id(unit=unit, game=game)
            if current and owner != current:
                return False
        return True

    def unit_used_malefic_surge_this_turn(self, unit, *, game=None) -> bool:
        if unit is None:
            return False
        sr = self._unit_sr(unit)
        owner = str(sr.get("malefic_surge_last_owner", "") or "")
        if owner:
            current = self._current_owner_id(unit=unit, game=game)
            if current and owner != current:
                return False
        try:
            return int(sr.get("malefic_surge_last_turn", -1) or -1) == int(self._current_turn_key(game))
        except Exception:
            return False

    def can_unit_malefic_surge(self, unit, *, game=None, ignore_used: bool = False) -> bool:
        if unit is None:
            return False
        if not self.is_infernal_lance():
            return False
        if not self._unit_is_chaos_knights(unit):
            return False
        if not self._unit_on_battlefield(unit):
            return False
        if not ignore_used and self.unit_used_malefic_surge_this_turn(unit, game=game):
            return False
        return True

    def _mark_empowered(self, unit, *, game=None, source: str = "") -> None:
        sr = self._unit_sr(unit)
        sr["malefic_surge_empowered"] = True
        sr["malefic_surge_empowered_turn"] = int(self._current_turn_key(game))
        sr["malefic_surge_empowered_owner"] = self._current_owner_id(unit=unit, game=game)
        if source:
            sr["malefic_surge_source"] = str(source or "").strip()
        unit.special_rules = sr

    def _mark_used(self, unit, *, game=None, choice: str | None = None) -> None:
        sr = self._unit_sr(unit)
        sr["malefic_surge_last_turn"] = int(self._current_turn_key(game))
        sr["malefic_surge_last_owner"] = self._current_owner_id(unit=unit, game=game)
        if choice:
            sr["malefic_surge_last_choice"] = str(choice or "").strip()
        for key in (
            "malefic_surge_empowered",
            "malefic_surge_empowered_turn",
            "malefic_surge_empowered_owner",
            "malefic_surge_source",
        ):
            sr.pop(key, None)
        unit.special_rules = sr

    def clear_empowered_at_command_phase_start(self, *, game=None, player=None) -> None:
        if not self.is_infernal_lance():
            return
        if self.army is None:
            return
        current_turn = int(self._current_turn_key(game))
        current_owner = str(getattr(player, "id", "") or "") if player is not None else ""
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("malefic_surge_empowered"):
                continue
            owner = str(sr.get("malefic_surge_empowered_owner", "") or "")
            if current_owner and owner and owner != current_owner:
                continue
            try:
                emp_turn = int(sr.get("malefic_surge_empowered_turn", -1) or -1)
            except Exception:
                emp_turn = -1
            if emp_turn >= 0 and emp_turn == current_turn:
                continue
            for key in (
                "malefic_surge_empowered",
                "malefic_surge_empowered_turn",
                "malefic_surge_empowered_owner",
                "malefic_surge_source",
            ):
                sr.pop(key, None)
            sr.pop("malefic_surge_choice_pending", None)
            unit.special_rules = sr
        if player is not None:
            self._malefic_surge_declined_turn = None
            self._malefic_surge_declined_owner = ""

    def _declined_this_turn(self, player=None, game=None) -> bool:
        if player is None:
            return False
        if self._malefic_surge_declined_turn is None:
            return False
        try:
            if int(self._malefic_surge_declined_turn) != int(self._current_turn_key(game)):
                return False
        except Exception:
            return False
        return str(self._malefic_surge_declined_owner or "") == str(getattr(player, "id", "") or "")

    def record_declined(self, *, player=None, game=None) -> None:
        if player is None:
            return
        self._malefic_surge_declined_turn = int(self._current_turn_key(game))
        self._malefic_surge_declined_owner = str(getattr(player, "id", "") or "")

    def get_malefic_surge_candidates(self, *, game=None) -> list:
        if self.army is None or not self.is_infernal_lance():
            return []
        units = []
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None:
                continue
            if root in units:
                continue
            if not self.can_unit_malefic_surge(root, game=game):
                continue
            units.append(root)
        units.sort(key=lambda u: str(getattr(u, "name", "")))
        return units

    def prompt_malefic_surge_selection(self, *, game=None, player=None) -> None:
        if game is None or player is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        if not self.is_infernal_lance():
            return
        if self._declined_this_turn(player=player, game=game):
            return
        candidates = self.get_malefic_surge_candidates(game=game)
        if not candidates:
            return
        from ..engine.decision_kinds import DECISION_CHOOSE_MALEFIC_SURGE_UNIT
        from ..engine.decisions import DecisionOption, DecisionRequest

        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_MALEFIC_SURGE_UNIT:
                    continue
                if str(getattr(req, "player_id", "") or "") == str(getattr(player, "id", "") or ""):
                    return

        options = []
        for unit in candidates:
            options.append(
                DecisionOption.create(
                    getattr(unit, "name", "Unit"),
                    payload={"unit_id": get_entity_id(unit)},
                )
            )
        options.append(
            DecisionOption.create(
                "None",
                payload={"skip": True, "action": "skip", "summary": "Do not select additional units."},
            )
        )
        ctx = {
            "ability": "malefic_surge",
            "ability_name": self.MALEFIC_SURGE_NAME,
            "battle_round": self._current_turn_key(game),
        }
        req = DecisionRequest.create(
            DECISION_CHOOSE_MALEFIC_SURGE_UNIT,
            "Select a unit to make a Malefic Surge (or None).",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        game.request_decision(req)

    def apply_malefic_surge(self, unit, *, game=None, ignore_used: bool = False) -> dict:
        if unit is None:
            return {"ok": False, "reason": "unit missing"}
        if not self.can_unit_malefic_surge(unit, game=game, ignore_used=ignore_used):
            return {"ok": False, "reason": "unit not eligible"}
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return {"ok": False, "reason": "unit missing"}
        extra_rerolls = []
        try:
            sr = self._unit_sr(root)
            if sr.get("enhancement_blasphemous_engine"):
                extra_rerolls.append("Blasphemous Engine")
        except Exception:
            extra_rerolls = []
        passed = bool(
            getattr(root, "pass_leadership_check", lambda **_k: True)(
                extra_reroll_sources=extra_rerolls,
                reroll_reason="Malefic Surge",
            )
        )
        if not passed:
            try:
                mortal = int(get_roll("D3") or 0)
            except Exception:
                mortal = 0
            if mortal <= 0:
                mortal = 1
            try:
                root._apply_mortal_wounds_to_unit(root, mortal, game_map=getattr(game, "map", None))
            except Exception:
                pass
        self._mark_empowered(root, game=game, source=self.MALEFIC_SURGE_NAME)
        try:
            if game is not None and hasattr(game, "event_system"):
                army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
                player = getattr(army, "player", None) if army is not None else None
                game.event_system.publish(
                    "malefic_surge_applied",
                    unit=root,
                    player=player,
                    game=game,
                )
        except Exception:
            pass
        return {"ok": True, "passed": passed}

    def queue_malefic_surge_choice(self, unit, *, trigger: str, game=None) -> None:
        if unit is None or game is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        if not self.is_infernal_lance():
            return
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return
        if not self.is_unit_empowered(root, game=game):
            return
        sr = self._unit_sr(root)
        if sr.get("malefic_surge_choice_pending"):
            return
        from ..engine.decision_kinds import DECISION_CHOOSE_MALEFIC_SURGE_ABILITY
        from ..engine.decisions import DecisionOption, DecisionRequest

        trigger_key = str(trigger or "").strip().lower()
        if not trigger_key:
            return

        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_MALEFIC_SURGE_ABILITY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("unit_id", "")) == str(get_entity_id(root)) and str(ctx.get("trigger", "")) == trigger_key:
                    return

        options = []
        header = "Select a Malefic Surge ability."
        if trigger_key == "movement":
            options.append(
                DecisionOption.create(
                    "Unholy Hunger",
                    payload={"choice": "UNHOLY_HUNGER", "summary": "Until end of phase, add 3\" to Move."},
                )
            )
            header = "Use Unholy Hunger for this move?"
        elif trigger_key in ("shooting", "fight"):
            options.append(
                DecisionOption.create(
                    "Lethal Hits",
                    payload={"choice": "LETHAL_HITS", "summary": "Weapons gain [LETHAL HITS] until end of phase."},
                )
            )
            options.append(
                DecisionOption.create(
                    "Sustained Hits 1",
                    payload={"choice": "SUSTAINED_HITS_1", "summary": "Weapons gain [SUSTAINED HITS 1] until end of phase."},
                )
            )
            header = "Select Diabolic Power ability."
        elif trigger_key in ("targeted_shooting", "targeted_fight"):
            options.append(
                DecisionOption.create(
                    "5+ Invulnerable Save",
                    payload={"choice": "INVULN_5", "summary": "Models gain a 5+ invulnerable save until end of phase."},
                )
            )
            options.append(
                DecisionOption.create(
                    "Feel No Pain 6+",
                    payload={"choice": "FNP_6", "summary": "Models gain Feel No Pain 6+ until end of phase."},
                )
            )
            header = "Select Unnatural Fortitude effect."
        else:
            return
        options.append(
            DecisionOption.create(
                "Skip",
                payload={"skip": True, "action": "skip", "summary": "Do not use Malefic Surge now."},
            )
        )
        player = None
        try:
            player = root.get_parent_army().player
        except Exception:
            player = None
        ctx = {
            "ability": "malefic_surge",
            "ability_name": self.MALEFIC_SURGE_NAME,
            "unit_id": get_entity_id(root),
            "trigger": trigger_key,
        }
        req = DecisionRequest.create(
            DECISION_CHOOSE_MALEFIC_SURGE_ABILITY,
            header,
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        sr["malefic_surge_choice_pending"] = True
        root.special_rules = sr
        game.request_decision(req)

    def apply_malefic_surge_choice(self, unit, *, trigger: str, choice: str, game=None) -> bool:
        if unit is None or game is None:
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        if root is None:
            return False
        if not self.is_unit_empowered(root, game=game):
            return False
        trigger_key = str(trigger or "").strip().lower()
        choice_key = str(choice or "").strip().upper()
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if not phase_name:
            phase_name = "SHOOTING_PHASE"
        if trigger_key == "movement" and choice_key == "UNHOLY_HUNGER":
            self._apply_unholy_hunger(root, phase_name=phase_name)
            try:
                if bool(getattr(game, "is_authoritative", True)):
                    from ..engine.decision_handlers.movement import _maybe_request_move_modifier_choice
                    _maybe_request_move_modifier_choice(game, root, action_type="move")
            except Exception:
                pass
        elif trigger_key in ("shooting", "fight") and choice_key in ("LETHAL_HITS", "SUSTAINED_HITS_1"):
            attack_type = "ranged" if trigger_key == "shooting" else "melee"
            self._apply_diabolic_power(root, choice_key, attack_type=attack_type, phase_name=phase_name)
        elif trigger_key in ("targeted_shooting", "targeted_fight") and choice_key in ("INVULN_5", "FNP_6"):
            self._apply_unnatural_fortitude(root, choice_key, phase_name=phase_name)
        else:
            return False
        self._mark_used(root, game=game, choice=choice_key)
        sr = self._unit_sr(root)
        sr.pop("malefic_surge_choice_pending", None)
        root.special_rules = sr
        return True

    def clear_pending_choice(self, unit) -> None:
        if unit is None:
            return
        sr = self._unit_sr(unit)
        sr.pop("malefic_surge_choice_pending", None)
        unit.special_rules = sr

    def _apply_unholy_hunger(self, unit, *, phase_name: str) -> None:
        try:
            models = list(unit.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(unit, "models", []) or [])
        for model in list(models or []):
            if model is None or not getattr(model, "is_alive", True):
                continue
            if not isinstance(getattr(model, "_temporary_effects", None), dict):
                model._temporary_effects = {}
            key = f"malefic_surge_unholy_hunger:{get_entity_id(model)}".strip().lower()
            model._temporary_effects[key] = {
                "expires_phase": str(phase_name or "").strip().upper(),
                "movement_bonus": 3,
                "movement_bonus_source": "Unholy Hunger",
            }
        sr = self._unit_sr(unit)
        sr["malefic_surge_unholy_hunger_active"] = True
        sr["malefic_surge_unholy_hunger_expires_phase"] = str(phase_name or "").strip().upper()
        sr["malefic_surge_unholy_hunger_source"] = self.MALEFIC_SURGE_NAME
        unit.special_rules = sr

    def _apply_diabolic_power(self, unit, choice: str, *, attack_type: str, phase_name: str) -> None:
        sr = self._unit_sr(unit)
        sr["malefic_surge_diabolic_active"] = True
        sr["malefic_surge_diabolic_choice"] = str(choice or "").strip().upper()
        sr["malefic_surge_diabolic_attack_type"] = str(attack_type or "").strip().lower()
        sr["malefic_surge_diabolic_expires_phase"] = str(phase_name or "").strip().upper()
        sr["malefic_surge_diabolic_source"] = self.MALEFIC_SURGE_NAME
        unit.special_rules = sr

    def _apply_unnatural_fortitude(self, unit, choice: str, *, phase_name: str) -> None:
        try:
            models = list(unit.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(unit, "models", []) or [])
        for model in list(models or []):
            if model is None or not getattr(model, "is_alive", True):
                continue
            if choice == "INVULN_5":
                setter = getattr(model, "set_temporary_invulnerable_save", None)
                if callable(setter):
                    setter(
                        key=f"malefic_surge_invuln:{get_entity_id(model)}",
                        value=5,
                        source="Unnatural Fortitude",
                        expires_phase=str(phase_name or "").strip().upper(),
                    )
            elif choice == "FNP_6":
                setter = getattr(model, "set_temporary_fnp", None)
                if callable(setter):
                    setter(
                        key=f"malefic_surge_fnp:{get_entity_id(model)}",
                        value=6,
                        source="Unnatural Fortitude",
                        expires_phase=str(phase_name or "").strip().upper(),
                    )
        sr = self._unit_sr(unit)
        sr["malefic_surge_unnatural_fortitude_active"] = True
        sr["malefic_surge_unnatural_fortitude_expires_phase"] = str(phase_name or "").strip().upper()
        sr["malefic_surge_unnatural_fortitude_source"] = self.MALEFIC_SURGE_NAME
        if sr.get("enhancement_fleshmetal_fusion"):
            sr["fleshmetal_fusion_fortitude_active"] = True
            sr["fleshmetal_fusion_fortitude_expires_phase"] = str(phase_name or "").strip().upper()
            sr["fleshmetal_fusion_fortitude_source"] = "Fleshmetal Fusion"
        unit.special_rules = sr
