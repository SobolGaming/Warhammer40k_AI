from __future__ import annotations

from typing import Optional

from ..utility.entity_ids import get_entity_id
from ..utility.dice import get_roll
from .detachment_manager import DetachmentManagerBase
from .nurgles_gift import DEFAULT_PLAGUES, NurglesGiftManager


class DeathGuardDetachmentManager(DetachmentManagerBase):
    faction_id = "DG"
    _MANIFOLD_MALADIES_SOURCE = "Manifold Maladies"
    _FINAL_INGREDIENT_SOURCE = "Final Ingredient"
    _VISIONS_OF_VIRULENCE_SOURCE = "Visions of Virulence"
    _VISIONS_OF_VIRULENCE_TRIGGER_SOURCE = "Pestilent Fallout"
    _NEEDLE_OF_NURGLE_SOURCE = "Needle of Nurgle"
    _CORNUCOPHAGUS_SOURCE = "Cornucophagus"
    _FACE_OF_DEATH_SOURCE = "Face of Death"
    _VILE_VIGOUR_SOURCE = "Vile Vigour"
    _WARPROT_TALISMAN_SOURCE = "Warprot Talisman"
    _HELM_OF_THE_FLY_KING_SOURCE = "Helm of the Fly King"
    _DRONING_CHORUS_SOURCE = "Droning Chorus"
    _INSECTILE_MURMURATION_SOURCE = "Insectile Murmuration"
    _REJUVENATING_SWARM_SOURCE = "Rejuvenating Swarm"
    _PLAGUEVEIL_SOURCE = "Plagueveil"
    _EYE_OF_AFFLICTION_SOURCE = "Eye of Affliction"
    _BILEMAW_BLIGHT_SOURCE = "Bilemaw Blight"
    _SHRIEKWORM_FAMILIAR_SOURCE = "Shriekworm Familiar"
    _TENDRILOUS_EMISSIONS_SOURCE = "Tendrilous Emissions"
    _WITHERBONE_PIPES_SOURCE = "Witherbone Pipes"
    _LORD_OF_THE_WALKING_POX_SOURCE = "Lord of the Walking Pox"
    _SORROWSYPHON_SOURCE = "Sorrowsyphon"
    _TALISMAN_OF_BURGEONING_SOURCE = "Talisman of Burgeoning"
    _BECKONING_BLIGHT_SOURCE = "Beckoning Blight"
    _FELL_HARVESTER_SOURCE = "Fell Harvester"
    _ENTROPIC_KNELL_SOURCE = "Entropic Knell"
    _TOME_OF_BOUNTEOUS_BLESSINGS_SOURCE = "Tome of Bounteous Blessings"
    _MIASMIC_BOMBARDMENT_SOURCE = "Miasmic Bombardment"
    _MIASMIC_BOMBARDMENT_RANGE = 12.0
    _NUMBERLESS_HORDE_SOURCE = "Numberless Horde"
    _NUMBERLESS_HORDE_POXWALKERS_NAME = "Poxwalkers"
    _NUMBERLESS_HORDE_STARTING_STRENGTH = 10
    _REVERBERANT_RANCIDITY_SOURCE = "Reverberant Rancidity"
    _REVERBERANT_RANCIDITY_RANGE = 7.0
    _REVERBERANT_RANCIDITY_CONTAGION_BONUS = 3.0
    _WORLD_BLIGHT_SOURCE = "worldblight"
    _VERMINOUS_HAZE_SCOUT_DISTANCE = 5.0

    def __init__(self, army=None):
        super().__init__(army=army)
        self.manifold_maladies_resolved_round: Optional[int] = None
        self.miasmic_bombardment_resolved_round: Optional[int] = None
        self.numberless_horde_spawned_rounds: set[int] = set()
        self._numberless_horde_cached_datasheet = None

    def is_champions_of_contagion(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Champions of Contagion")

    def is_flyblown_host(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Flyblown Host")

    def is_death_lords_chosen(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Death Lord's Chosen")

    def is_virulent_vectorium(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Virulent Vectorium")

    def is_mortarions_hammer(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Mortarion's Hammer")

    def is_shamblerot_vectorium(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Shamblerot Vectorium")

    def is_tallyband_summoners(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Tallyband Summoners")

    def _resolve_battle_round(self, *, game=None, battle_round=None) -> Optional[int]:
        if battle_round is not None:
            try:
                return int(battle_round)
            except (TypeError, ValueError):
                return None
        if game is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(player, "game", None) if player is not None else None
        if game is None:
            return None
        try:
            return int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_valid_plague_choice(choice_key: str) -> bool:
        key = str(choice_key or "").strip().upper()
        if not key:
            return False
        return any(str(getattr(plague, "key", "")).strip().upper() == key for plague in list(DEFAULT_PLAGUES))

    def can_select_manifold_maladies(self, *, game=None, battle_round=None) -> bool:
        if not self.is_champions_of_contagion():
            return False
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None:
            return False
        if self.manifold_maladies_resolved_round is not None and int(self.manifold_maladies_resolved_round) == int(round_value):
            return False
        gift_mgr = getattr(self.army, "nurgles_gift", None) if self.army is not None else None
        if gift_mgr is None:
            return False
        return bool(getattr(gift_mgr, "_army_has_gift", lambda: False)())

    def select_manifold_maladies(self, choice, *, battle_round=None) -> bool:
        if not self.is_champions_of_contagion():
            return False
        round_value = self._resolve_battle_round(battle_round=battle_round)
        if round_value is None:
            return False
        if self.manifold_maladies_resolved_round is not None and int(self.manifold_maladies_resolved_round) == int(round_value):
            return False
        gift_mgr = getattr(self.army, "nurgles_gift", None) if self.army is not None else None
        if gift_mgr is None:
            return False
        choice_key = str(choice or "").strip().upper()
        if choice_key in ("", "NONE", "SKIP"):
            self.manifold_maladies_resolved_round = int(round_value)
            return True
        if not self._is_valid_plague_choice(choice_key):
            return False
        gift_mgr.active_plague_key = choice_key
        self.manifold_maladies_resolved_round = int(round_value)
        return True

    def _pending_manifold_maladies_request(self, game, *, army_id: str, battle_round: int):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_PLAGUE

        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_PLAGUE:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != "manifold_maladies":
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id):
                continue
            if int(ctx.get("battle_round", 0) or 0) != int(battle_round):
                continue
            return req
        return None

    def build_manifold_maladies_request(self, *, game=None, player=None, battle_round=None):
        if not self.is_champions_of_contagion():
            return None
        if game is None or player is None:
            return None
        if not bool(getattr(game, "is_authoritative", True)):
            return None
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None:
            return None
        if not self.can_select_manifold_maladies(game=game, battle_round=round_value):
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_PLAGUE
        from ..engine.decisions import DecisionOption, DecisionRequest

        army_id = str(get_entity_id(self.army) or "") if self.army is not None else ""
        if self._pending_manifold_maladies_request(game, army_id=army_id, battle_round=int(round_value)):
            return None

        options = [
            DecisionOption.create(
                "None",
                payload={
                    "action": "skip",
                    "skip": True,
                    "choice_key": "",
                    "army_id": army_id,
                    "battle_round": int(round_value),
                },
            )
        ]
        for plague in list(DEFAULT_PLAGUES):
            options.append(
                DecisionOption.create(
                    str(getattr(plague, "name", "Plague") or "Plague"),
                    payload={
                        "choice_key": str(getattr(plague, "key", "") or ""),
                        "summary": str(getattr(plague, "summary", "") or ""),
                        "army_id": army_id,
                        "battle_round": int(round_value),
                    },
                )
            )

        request = DecisionRequest.create(
            DECISION_CHOOSE_PLAGUE,
            "Manifold Maladies: select one Plague (or None).",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "manifold_maladies",
                "ability_name": self._MANIFOLD_MALADIES_SOURCE,
                "army_id": army_id,
                "battle_round": int(round_value),
                "allowed_choice_keys": [str(getattr(plague, "key", "") or "") for plague in list(DEFAULT_PLAGUES)],
                "optional": True,
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)
        return request

    @staticmethod
    def _model_identifier(model) -> str:
        if model is None:
            return ""
        return str(get_entity_id(model) or getattr(model, "id", getattr(model, "_id", "")) or "").strip()

    def _resolve_champions_source_root(self, source_unit):
        if source_unit is None:
            return None
        root = source_unit.get_attached_unit_root() if hasattr(source_unit, "get_attached_unit_root") else source_unit
        if root is None or not self._unit_in_army(root):
            return None
        return root

    @staticmethod
    def _source_root_special_rules(root) -> dict:
        sr = getattr(root, "special_rules", None)
        if isinstance(sr, dict):
            return sr
        return {}

    @staticmethod
    def _set_source_root_special_rules(root, sr: dict) -> None:
        root.special_rules = dict(sr or {})

    def _attached_root_has_enhancement_flag(self, root, *, flag_key: str) -> bool:
        if root is None or not flag_key:
            return False
        members = list(root.get_attached_unit_members() or [])
        for member in members:
            sr = getattr(member, "special_rules", None)
            if isinstance(sr, dict) and bool(sr.get(flag_key, False)):
                return True
        return False

    def _attached_root_enhancement_bearer_id(self, root, *, specific_key: str) -> str:
        if root is None:
            return ""
        members = list(root.get_attached_unit_members() or [])
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            bearer_id = str(sr.get(specific_key, "") or sr.get("enhancement_bearer_model_id", "") or "").strip()
            if bearer_id:
                return bearer_id
        return ""

    def _champions_enhancement_sources(self, *, flag_key: str) -> list:
        if not self.is_champions_of_contagion() or self.army is None:
            return []
        roots: list = []
        for root in list(self._iter_unique_attached_roots() or []):
            if root is None or not self._unit_in_army(root):
                continue
            if self._attached_root_has_enhancement_flag(root, flag_key=flag_key):
                roots.append(root)
        roots.sort(key=lambda item: str(get_entity_id(item) or ""))
        return roots

    def _pending_choose_plague_request(self, game, *, ability: str, army_id: str, source_unit_id: str = ""):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_PLAGUE

        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_PLAGUE:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != str(ability or "").strip().lower():
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id):
                continue
            if source_unit_id and str(ctx.get("source_unit_id", "") or "") != str(source_unit_id):
                continue
            return req
        return None

    def _build_choose_plague_request_for_source(
        self,
        *,
        game,
        player,
        source_root,
        ability: str,
        ability_name: str,
        optional: bool,
        prompt: str,
    ):
        if game is None or player is None or source_root is None:
            return None
        from ..engine.decision_kinds import DECISION_CHOOSE_PLAGUE
        from ..engine.decisions import DecisionOption, DecisionRequest

        army_id = str(get_entity_id(self.army) or "") if self.army is not None else ""
        source_unit_id = str(get_entity_id(source_root) or "")
        if self._pending_choose_plague_request(
            game,
            ability=str(ability),
            army_id=army_id,
            source_unit_id=source_unit_id,
        ):
            return None

        options: list = []
        if optional:
            options.append(
                DecisionOption.create(
                    "None",
                    payload={
                        "action": "skip",
                        "skip": True,
                        "choice_key": "",
                        "army_id": army_id,
                        "source_unit_id": source_unit_id,
                    },
                )
            )
        for plague in list(DEFAULT_PLAGUES):
            options.append(
                DecisionOption.create(
                    str(getattr(plague, "name", "Plague") or "Plague"),
                    payload={
                        "choice_key": str(getattr(plague, "key", "") or ""),
                        "summary": str(getattr(plague, "summary", "") or ""),
                        "army_id": army_id,
                        "source_unit_id": source_unit_id,
                    },
                )
            )
        if not options:
            return None

        request = DecisionRequest.create(
            DECISION_CHOOSE_PLAGUE,
            prompt,
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": str(ability),
                "ability_name": str(ability_name),
                "army_id": army_id,
                "source_unit_id": source_unit_id,
                "allowed_choice_keys": [str(getattr(plague, "key", "") or "") for plague in list(DEFAULT_PLAGUES)],
                "optional": bool(optional),
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)
        return request

    @staticmethod
    def _model_is_character(target_model, *, target_unit=None) -> bool:
        if target_model is None and target_unit is None:
            return False
        if target_model is not None and bool(getattr(target_model, "is_character", False)):
            return True
        if target_model is not None:
            for fn_name in ("has_any_keyword", "has_keyword"):
                fn = getattr(target_model, fn_name, None)
                if callable(fn) and bool(fn("CHARACTER")):
                    return True
        if target_unit is None and target_model is not None:
            target_unit = getattr(target_model, "parent_unit", None)
        if target_unit is None:
            return False
        for fn_name in ("has_any_keyword", "has_keyword"):
            fn = getattr(target_unit, fn_name, None)
            if callable(fn) and bool(fn("CHARACTER")):
                return True
        keywords = list(getattr(target_unit, "keywords", []) or []) + list(getattr(target_unit, "faction_keywords", []) or [])
        return any(str(token or "").strip().upper() == "CHARACTER" for token in keywords)

    def can_select_final_ingredient(self, source_unit, *, game=None) -> bool:
        if not self.is_champions_of_contagion():
            return False
        source_root = self._resolve_champions_source_root(source_unit)
        if source_root is None:
            return False
        if not self._attached_root_has_enhancement_flag(source_root, flag_key="enhancement_final_ingredient"):
            return False
        sr = self._source_root_special_rules(source_root)
        if bool(sr.get("enhancement_final_ingredient_used", False)):
            return False
        if not bool(sr.get("enhancement_final_ingredient_pending", False)):
            return False
        if game is not None:
            try:
                current_turn = int(getattr(game, "turn", 0) or 0)
                pending_turn = int(sr.get("enhancement_final_ingredient_pending_turn", 0) or 0)
            except (TypeError, ValueError):
                current_turn = 0
                pending_turn = 0
            if pending_turn > 0 and current_turn > 0 and pending_turn != current_turn:
                return False
        return True

    def select_final_ingredient(self, source_unit, choice, *, game=None) -> bool:
        source_root = self._resolve_champions_source_root(source_unit)
        if source_root is None:
            return False
        if not self.can_select_final_ingredient(source_root, game=game):
            return False
        choice_key = str(choice or "").strip().upper()
        if not self._is_valid_plague_choice(choice_key):
            return False
        sr = self._source_root_special_rules(source_root)
        sr["enhancement_final_ingredient_selected_plague_key"] = choice_key
        sr["enhancement_final_ingredient_used"] = True
        sr["enhancement_final_ingredient_pending"] = False
        sr.pop("enhancement_final_ingredient_pending_turn", None)
        self._set_source_root_special_rules(source_root, sr)
        return True

    def note_final_ingredient_character_model_destroyed(
        self,
        *,
        attacker_unit=None,
        target_model=None,
        target_unit=None,
        game=None,
    ) -> None:
        source_root = self._resolve_champions_source_root(attacker_unit)
        if source_root is None:
            return
        if not self._attached_root_has_enhancement_flag(source_root, flag_key="enhancement_final_ingredient"):
            return
        if not self._model_is_character(target_model, target_unit=target_unit):
            return
        sr = self._source_root_special_rules(source_root)
        if bool(sr.get("enhancement_final_ingredient_used", False)):
            return
        sr["enhancement_final_ingredient_pending"] = True
        try:
            sr["enhancement_final_ingredient_pending_turn"] = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            sr["enhancement_final_ingredient_pending_turn"] = 0
        self._set_source_root_special_rules(source_root, sr)

    def queue_final_ingredient_request_for_unit(self, source_unit, *, game=None):
        source_root = self._resolve_champions_source_root(source_unit)
        if source_root is None:
            return None
        if game is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(player, "game", None) if player is not None else None
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return None
        if not self.can_select_final_ingredient(source_root, game=game):
            return None
        player = getattr(self.army, "player", None) if self.army is not None else None
        if player is None:
            return None
        return self._build_choose_plague_request_for_source(
            game=game,
            player=player,
            source_root=source_root,
            ability="final_ingredient",
            ability_name=self._FINAL_INGREDIENT_SOURCE,
            optional=False,
            prompt="Final Ingredient: select one additional Plague.",
        )

    def can_select_cornucophagus(self, source_unit, *, game=None) -> bool:
        if not self.is_champions_of_contagion():
            return False
        source_root = self._resolve_champions_source_root(source_unit)
        if source_root is None:
            return False
        if not self._attached_root_has_enhancement_flag(source_root, flag_key="enhancement_cornucophagus"):
            return False
        sr = self._source_root_special_rules(source_root)
        if str(sr.get("enhancement_cornucophagus_selected_plague_key", "") or "").strip().upper():
            return False
        if game is None:
            return True
        if not bool(getattr(game, "is_authoritative", True)):
            return False
        return True

    def select_cornucophagus(self, source_unit, choice) -> bool:
        source_root = self._resolve_champions_source_root(source_unit)
        if source_root is None:
            return False
        if not self.can_select_cornucophagus(source_root):
            return False
        choice_key = str(choice or "").strip().upper()
        if not self._is_valid_plague_choice(choice_key):
            return False
        sr = self._source_root_special_rules(source_root)
        sr["enhancement_cornucophagus_selected_plague_key"] = choice_key
        self._set_source_root_special_rules(source_root, sr)
        return True

    def queue_cornucophagus_declare_requests(self, *, game=None, player=None) -> list:
        if not self.is_champions_of_contagion():
            return []
        if game is None or player is None:
            return []
        if not bool(getattr(game, "is_authoritative", True)):
            return []
        requests = []
        for source_root in list(self._champions_enhancement_sources(flag_key="enhancement_cornucophagus") or []):
            if not self.can_select_cornucophagus(source_root, game=game):
                continue
            request = self._build_choose_plague_request_for_source(
                game=game,
                player=player,
                source_root=source_root,
                ability="cornucophagus",
                ability_name=self._CORNUCOPHAGUS_SOURCE,
                optional=False,
                prompt="Cornucophagus: select one additional Plague for the bearer.",
            )
            if request is not None:
                requests.append(request)
        return requests

    def _resolve_unit_by_id_in_army(self, unit_id: str):
        uid = str(unit_id or "").strip()
        if not uid or self.army is None:
            return None
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
            if str(get_entity_id(root) or "") == uid:
                return root
        return None

    def visions_of_virulence_afflicts_wracked_unit(self, unit, *, game=None) -> bool:
        if not self.is_champions_of_contagion():
            return False
        if unit is None or self.army is None:
            return False
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not bool(sr.get("wracked_with_agonies_active", False)):
            return False
        owner = getattr(self.army, "player", None)
        owner_id = str(getattr(owner, "id", "") or "")
        if owner_id and str(sr.get("wracked_with_agonies_owner", "") or "") != owner_id:
            return False
        source_name = str(sr.get("wracked_with_agonies_source", "") or "").strip().lower()
        if self._norm(self._VISIONS_OF_VIRULENCE_TRIGGER_SOURCE) not in self._norm(source_name):
            return False
        source_unit_id = str(sr.get("wracked_with_agonies_source_unit_id", "") or "").strip()
        if not source_unit_id:
            return False
        source_root = self._resolve_unit_by_id_in_army(source_unit_id)
        if source_root is None:
            return False
        if not self._attached_root_has_enhancement_flag(source_root, flag_key="enhancement_visions_of_virulence"):
            return False
        expected_bearer_id = self._attached_root_enhancement_bearer_id(
            source_root,
            specific_key="enhancement_visions_of_virulence_bearer_model_id",
        )
        source_model_id = str(sr.get("wracked_with_agonies_source_model_id", "") or "").strip()
        if expected_bearer_id and source_model_id and expected_bearer_id != source_model_id:
            return False
        return True

    def _unit_within_cornucophagus_range(self, source_root, target_unit, *, game=None, game_map=None) -> bool:
        if source_root is None or target_unit is None or self.army is None:
            return False
        if game is None:
            player = getattr(self.army, "player", None)
            game = getattr(player, "game", None) if player is not None else None
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)
        if game_map is None:
            return False
        gift_mgr = getattr(self.army, "nurgles_gift", None)
        if gift_mgr is None:
            return False
        valid_source = getattr(gift_mgr, "_unit_is_valid_contagion_source", None)
        if not callable(valid_source) or not bool(valid_source(source_root, game=game, game_map=game_map)):
            return False
        battle_round = self._resolve_battle_round(game=game)
        if battle_round is None:
            return False
        from ..utility import aura_utils as _aura_utils

        contagion_range = float(
            gift_mgr.get_contagion_range(int(battle_round), source_unit=source_root, game=game, game_map=game_map)
        )
        return bool(
            _aura_utils.unit_within_range_of_unit(
                source_root,
                target_unit,
                float(contagion_range),
                use_attached_aggregate=True,
            )
        )

    def additional_afflicted_plague_keys_for_unit(
        self,
        unit,
        *,
        game=None,
        game_map=None,
        is_afflicted: bool = False,
    ) -> list[str]:
        if not self.is_champions_of_contagion() or unit is None:
            return []
        keys: list[str] = []
        owner = getattr(self.army, "player", None) if self.army is not None else None
        owner_id = str(getattr(owner, "id", "") or "")

        target_sr = getattr(unit, "special_rules", None)
        if isinstance(target_sr, dict) and bool(target_sr.get("deaths_heads_active", False)):
            effect_owner = str(target_sr.get("deaths_heads_owner", "") or "")
            effect_active = bool(effect_owner and effect_owner == owner_id)
            if effect_active and game is not None:
                get_current_player = getattr(game, "get_current_player", None)
                current_player = get_current_player() if callable(get_current_player) else None
                current_owner = str(getattr(current_player, "id", "") or "")
                try:
                    effect_turn = int(target_sr.get("deaths_heads_turn", 0) or 0)
                except (TypeError, ValueError):
                    effect_turn = 0
                try:
                    current_turn = int(getattr(game, "turn", 0) or 0)
                except (TypeError, ValueError):
                    current_turn = 0
                if effect_turn and current_turn and current_turn > effect_turn and current_owner == owner_id:
                    effect_active = False
            if effect_active:
                for plague in list(DEFAULT_PLAGUES or []):
                    key = str(getattr(plague, "key", "") or "").strip().upper()
                    if key:
                        keys.append(key)

        if bool(is_afflicted):
            for source_root in list(self._champions_enhancement_sources(flag_key="enhancement_final_ingredient") or []):
                sr = self._source_root_special_rules(source_root)
                choice_key = str(sr.get("enhancement_final_ingredient_selected_plague_key", "") or "").strip().upper()
                if not choice_key:
                    continue
                if not bool(sr.get("enhancement_final_ingredient_used", False)):
                    continue
                if not self._is_valid_plague_choice(choice_key):
                    continue
                keys.append(choice_key)

        for source_root in list(self._champions_enhancement_sources(flag_key="enhancement_cornucophagus") or []):
            sr = self._source_root_special_rules(source_root)
            choice_key = str(sr.get("enhancement_cornucophagus_selected_plague_key", "") or "").strip().upper()
            if not choice_key:
                continue
            if not self._is_valid_plague_choice(choice_key):
                continue
            if not self._unit_within_cornucophagus_range(source_root, unit, game=game, game_map=game_map):
                continue
            keys.append(choice_key)

        return list(dict.fromkeys([str(key or "").strip().upper() for key in list(keys or []) if str(key or "").strip()]))

    def _detachment_source_member(
        self,
        unit,
        *,
        detachment_is_active: bool,
        flag_key: str,
        require_bearer_alive: bool = True,
        require_bearer_leading: bool = False,
    ):
        if not bool(detachment_is_active):
            return None, None, None, None
        if unit is None or not flag_key:
            return None, None, None, None
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if root is None or not self._unit_in_army(root):
            return None, None, None, None
        members = list(root.get_attached_unit_members() or [])
        members.sort(key=lambda item: str(get_entity_id(item) or ""))
        for member in members:
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(flag_key, False)):
                continue
            if require_bearer_leading and not bool(getattr(member, "is_attached_leader", False)):
                continue
            bearer = None
            bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "").strip()
            if bearer_id:
                for model in list(getattr(member, "models", []) or []):
                    model_id = self._model_identifier(model)
                    if model_id != bearer_id:
                        continue
                    bearer = model
                    break
            if bearer is None:
                get_bearer = getattr(member, "_get_enhancement_bearer_model", None)
                bearer = get_bearer() if callable(get_bearer) else None
            if require_bearer_alive:
                if bearer is None:
                    continue
                alive_attr = getattr(bearer, "is_alive", False)
                bearer_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                if not bearer_alive:
                    continue
            return root, member, sr, bearer
        return root, None, None, None

    def _death_lords_source_member(
        self,
        unit,
        *,
        flag_key: str,
        require_bearer_alive: bool = True,
        require_bearer_leading: bool = False,
    ):
        return self._detachment_source_member(
            unit,
            detachment_is_active=self.is_death_lords_chosen(),
            flag_key=flag_key,
            require_bearer_alive=require_bearer_alive,
            require_bearer_leading=require_bearer_leading,
        )

    def _flyblown_source_member(
        self,
        unit,
        *,
        flag_key: str,
        require_bearer_alive: bool = True,
        require_bearer_leading: bool = False,
    ):
        return self._detachment_source_member(
            unit,
            detachment_is_active=self.is_flyblown_host(),
            flag_key=flag_key,
            require_bearer_alive=require_bearer_alive,
            require_bearer_leading=require_bearer_leading,
        )

    def _mortarions_source_member(
        self,
        unit,
        *,
        flag_key: str,
        require_bearer_alive: bool = True,
        require_bearer_leading: bool = False,
    ):
        return self._detachment_source_member(
            unit,
            detachment_is_active=self.is_mortarions_hammer(),
            flag_key=flag_key,
            require_bearer_alive=require_bearer_alive,
            require_bearer_leading=require_bearer_leading,
        )

    def _shamblerot_source_member(
        self,
        unit,
        *,
        flag_key: str,
        require_bearer_alive: bool = True,
        require_bearer_leading: bool = False,
    ):
        return self._detachment_source_member(
            unit,
            detachment_is_active=self.is_shamblerot_vectorium(),
            flag_key=flag_key,
            require_bearer_alive=require_bearer_alive,
            require_bearer_leading=require_bearer_leading,
        )

    def _tallyband_source_member(
        self,
        unit,
        *,
        flag_key: str,
        require_bearer_alive: bool = True,
        require_bearer_leading: bool = False,
    ):
        return self._detachment_source_member(
            unit,
            detachment_is_active=self.is_tallyband_summoners(),
            flag_key=flag_key,
            require_bearer_alive=require_bearer_alive,
            require_bearer_leading=require_bearer_leading,
        )

    def death_lords_chosen_vile_vigour_movement_bonus(self, unit, *, game=None) -> tuple[int, str]:
        del game
        if not self.is_death_lords_chosen() or unit is None:
            return 0, ""
        root, _member, source_sr, _bearer = self._death_lords_source_member(
            unit,
            flag_key="enhancement_vile_vigour",
            require_bearer_alive=True,
            require_bearer_leading=True,
        )
        if source_sr is None or root is None:
            return 0, ""
        if not self._unit_in_army(root) or not root.is_alive() or not bool(getattr(root, "deployed", False)):
            return 0, ""
        source = str(source_sr.get("enhancement_vile_vigour_source", "") or self._VILE_VIGOUR_SOURCE).strip()
        if not source:
            source = self._VILE_VIGOUR_SOURCE
        try:
            bonus = int(source_sr.get("enhancement_vile_vigour_move_bonus", 1) or 1)
        except (TypeError, ValueError):
            bonus = 1
        return max(0, int(bonus)), source

    def death_lords_chosen_vile_vigour_reroll_advance_applies(self, unit, *, game=None) -> bool:
        del game
        if not self.is_death_lords_chosen() or unit is None:
            return False
        root, _member, source_sr, _bearer = self._death_lords_source_member(
            unit,
            flag_key="enhancement_vile_vigour",
            require_bearer_alive=True,
            require_bearer_leading=True,
        )
        if source_sr is None or root is None:
            return False
        if not self._unit_in_army(root) or not root.is_alive() or not bool(getattr(root, "deployed", False)):
            return False
        return bool(source_sr.get("enhancement_vile_vigour_reroll_advance", True))

    def death_lords_chosen_helm_of_the_fly_king_ranged_targeting_cap(self, target_unit, *, game=None) -> tuple[float, str]:
        del game
        if not self.is_death_lords_chosen():
            return 0.0, ""
        root, _member, source_sr, _bearer = self._death_lords_source_member(
            target_unit,
            flag_key="enhancement_helm_of_the_fly_king",
            require_bearer_alive=True,
            require_bearer_leading=True,
        )
        if source_sr is None or root is None:
            return 0.0, ""
        if not self._unit_in_army(root) or not root.is_alive() or not bool(getattr(root, "deployed", False)):
            return 0.0, ""
        try:
            cap = float(source_sr.get("enhancement_helm_of_the_fly_king_ranged_targeting_max_distance", 18.0) or 18.0)
        except (TypeError, ValueError):
            cap = 18.0
        source = str(source_sr.get("enhancement_helm_of_the_fly_king_source", "") or self._HELM_OF_THE_FLY_KING_SOURCE).strip()
        if not source:
            source = self._HELM_OF_THE_FLY_KING_SOURCE
        return max(0.0, float(cap)), source

    def flyblown_host_droning_chorus_assault_applies(self, unit, weapon_profile=None, *, game=None) -> bool:
        del game
        if not self.is_flyblown_host():
            return False
        parent_wargear = getattr(weapon_profile, "parent_wargear", None)
        if parent_wargear is None or not bool(getattr(parent_wargear, "is_ranged", lambda: False)()):
            return False
        root, _member, source_sr, _bearer = self._flyblown_source_member(
            unit,
            flag_key="enhancement_droning_chorus",
            require_bearer_alive=True,
            require_bearer_leading=False,
        )
        if source_sr is None or root is None:
            return False
        if not self._unit_in_army(root) or not root.is_alive() or not bool(getattr(root, "deployed", False)):
            return False
        return bool(source_sr.get("enhancement_droning_chorus_assault_ranged", True))

    def _unit_within_any_friendly_contagion_range(self, target_unit, *, game=None, game_map=None) -> bool:
        if target_unit is None or self.army is None:
            return False
        if game is None:
            player = getattr(self.army, "player", None)
            game = getattr(player, "game", None) if player is not None else None
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)
        if game is None or game_map is None:
            return False
        battle_round = self._resolve_battle_round(game=game)
        if battle_round is None:
            return False
        gift_mgr = getattr(self.army, "nurgles_gift", None)
        if gift_mgr is None:
            return False
        valid_source = getattr(gift_mgr, "_unit_is_valid_contagion_source", None)
        if not callable(valid_source):
            return False
        from ..utility import aura_utils as _aura_utils

        for source_unit in list(self._iter_unique_attached_roots() or []):
            if source_unit is None:
                continue
            if not bool(valid_source(source_unit, game=game, game_map=game_map)):
                continue
            contagion_range = float(
                gift_mgr.get_contagion_range(
                    int(battle_round),
                    source_unit=source_unit,
                    game=game,
                    game_map=game_map,
                )
            )
            if _aura_utils.unit_within_range_of_unit(
                source_unit,
                target_unit,
                float(contagion_range),
                use_attached_aggregate=True,
            ):
                return True
        return False

    def flyblown_host_insectile_murmuration_reroll_wound_ones(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        target_unit=None,
        game=None,
        game_map=None,
    ) -> tuple[bool, str]:
        del weapon_profile
        if not self.is_flyblown_host():
            return False, ""
        if attacker_model is None or target_unit is None:
            return False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root, _member, source_sr, _bearer = self._flyblown_source_member(
            attacker_unit,
            flag_key="enhancement_insectile_murmuration",
            require_bearer_alive=True,
            require_bearer_leading=False,
        )
        if source_sr is None or root is None:
            return False, ""
        if not self._unit_in_army(root) or not root.is_alive() or not bool(getattr(root, "deployed", False)):
            return False, ""
        if not self._unit_within_any_friendly_contagion_range(target_unit, game=game, game_map=game_map):
            return False, ""
        source = str(
            source_sr.get("enhancement_insectile_murmuration_source", "") or self._INSECTILE_MURMURATION_SOURCE
        ).strip()
        if not source:
            source = self._INSECTILE_MURMURATION_SOURCE
        return True, source

    def flyblown_host_plagueveil_ranged_targeting_cap(self, target_unit, *, game=None) -> tuple[float, str]:
        if not self.is_flyblown_host():
            return 0.0, ""
        root, _member, source_sr, _bearer = self._flyblown_source_member(
            target_unit,
            flag_key="enhancement_plagueveil",
            require_bearer_alive=True,
            require_bearer_leading=False,
        )
        if source_sr is None or root is None:
            return 0.0, ""
        if not self._unit_in_army(root) or not root.is_alive() or not bool(getattr(root, "deployed", False)):
            return 0.0, ""
        if bool(source_sr.get("enhancement_plagueveil_requires_within_controlled_objective_range", True)):
            if game is None:
                owner = getattr(self.army, "player", None) if self.army is not None else None
                game = getattr(owner, "game", None) if owner is not None else None
            game_map = getattr(game, "map", None) if game is not None else None
            within_controlled = getattr(root, "_within_controlled_objective_range", None)
            if not callable(within_controlled) or not bool(within_controlled(game_map)):
                return 0.0, ""
        try:
            cap = float(source_sr.get("enhancement_plagueveil_ranged_targeting_max_distance", 18.0) or 18.0)
        except (TypeError, ValueError):
            cap = 18.0
        source = str(source_sr.get("enhancement_plagueveil_source", "") or self._PLAGUEVEIL_SOURCE).strip()
        if not source:
            source = self._PLAGUEVEIL_SOURCE
        return max(0.0, float(cap)), source

    def mortarions_hammer_eye_of_affliction_ranged_ignores_cover(
        self,
        attacker_model,
        target_unit,
        *,
        game=None,
        game_map=None,
    ) -> tuple[bool, str]:
        if not self.is_mortarions_hammer():
            return False, ""
        if attacker_model is None or target_unit is None:
            return False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root, _member, source_sr, _bearer = self._mortarions_source_member(
            attacker_unit,
            flag_key="enhancement_eye_of_affliction",
            require_bearer_alive=True,
            require_bearer_leading=False,
        )
        if source_sr is None or root is None:
            return False, ""
        if not self._unit_in_army(root) or not root.is_alive() or not bool(getattr(root, "deployed", False)):
            return False, ""
        if game is None:
            owner = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(owner, "game", None) if owner is not None else None
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)
        afflicted = NurglesGiftManager.get_afflicted_plague_for_unit(target_unit, game=game, game_map=game_map)
        if afflicted is None:
            return False, ""
        source = str(source_sr.get("enhancement_eye_of_affliction_source", "") or self._EYE_OF_AFFLICTION_SOURCE).strip()
        if not source:
            source = self._EYE_OF_AFFLICTION_SOURCE
        return True, source

    @staticmethod
    def _weapon_profile_matches_name(weapon_profile, expected_name: str) -> bool:
        if weapon_profile is None or not expected_name:
            return False
        expected = "".join(ch for ch in str(expected_name).lower() if ch.isalnum())
        if not expected:
            return False
        candidates = []
        profile_name = str(getattr(weapon_profile, "name", "") or "").strip()
        if profile_name:
            candidates.append(profile_name)
        parent_wargear = getattr(weapon_profile, "parent_wargear", None)
        wargear_name = str(getattr(parent_wargear, "name", "") or "").strip()
        if wargear_name:
            candidates.append(wargear_name)
        for candidate in candidates:
            normalized = "".join(ch for ch in str(candidate).lower() if ch.isalnum())
            if not normalized:
                continue
            if expected == normalized or expected in normalized or normalized in expected:
                return True
        return False

    def mortarions_hammer_bilemaw_blight_range_bonus(
        self,
        attacker_model,
        weapon_profile,
        *,
        game=None,
    ) -> tuple[int, str]:
        if not self.is_mortarions_hammer():
            return 0, ""
        if attacker_model is None or weapon_profile is None:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root, _member, source_sr, bearer = self._mortarions_source_member(
            attacker_unit,
            flag_key="enhancement_bilemaw_blight",
            require_bearer_alive=True,
            require_bearer_leading=False,
        )
        if source_sr is None or root is None or bearer is None:
            return 0, ""
        if not self._unit_in_army(root) or not root.is_alive() or not bool(getattr(root, "deployed", False)):
            return 0, ""
        if self._model_identifier(attacker_model) != self._model_identifier(bearer):
            return 0, ""
        expected_weapon = str(source_sr.get("enhancement_bilemaw_blight_weapon_name", "") or "Plague Wind").strip()
        if not self._weapon_profile_matches_name(weapon_profile, expected_weapon):
            return 0, ""
        if game is None:
            owner = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(owner, "game", None) if owner is not None else None
        if game is None:
            return 0, ""
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_name != "SHOOTING_PHASE":
            return 0, ""
        owner = getattr(self.army, "player", None)
        current_player = getattr(game, "get_current_player", lambda: None)()
        if owner is None or current_player is not owner:
            return 0, ""
        try:
            bonus = int(source_sr.get("enhancement_bilemaw_blight_range_bonus", 12) or 12)
        except (TypeError, ValueError):
            bonus = 12
        source = str(source_sr.get("enhancement_bilemaw_blight_source", "") or self._BILEMAW_BLIGHT_SOURCE).strip()
        if not source:
            source = self._BILEMAW_BLIGHT_SOURCE
        return max(0, int(bonus)), source

    def _unit_is_death_guard_vehicle(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_in_army(unit):
            return False
        if not self._unit_eligible_for_deadly_vectors(unit):
            return False
        if not self._unit_is_death_guard(unit):
            return False
        return self._unit_has_keyword(unit, "VEHICLE")

    def _friendly_vehicle_units_within_range_of_source(
        self,
        source_unit,
        *,
        range_inches: float,
    ) -> list:
        if source_unit is None:
            return []
        from ..utility import aura_utils as _aura_utils

        units_in_range: list = []
        for candidate in list(self._iter_unique_attached_roots() or []):
            if candidate is None or candidate is source_unit:
                continue
            if not self._unit_is_death_guard_vehicle(candidate):
                continue
            if not _aura_utils.unit_within_range_of_unit(
                source_unit,
                candidate,
                float(range_inches),
                use_attached_aggregate=True,
            ):
                continue
            units_in_range.append(candidate)
        units_in_range.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return units_in_range

    def mortarions_hammer_tendrilous_emissions_lone_operative_applies(self, unit, *, game=None, game_map=None) -> bool:
        del game, game_map
        if not self.is_mortarions_hammer():
            return False
        root, _member, source_sr, _bearer = self._mortarions_source_member(
            unit,
            flag_key="enhancement_tendrilous_emissions",
            require_bearer_alive=True,
            require_bearer_leading=False,
        )
        if source_sr is None or root is None:
            return False
        if not self._unit_in_army(root) or not root.is_alive() or not bool(getattr(root, "deployed", False)):
            return False
        if not bool(source_sr.get("enhancement_tendrilous_emissions_grant_lone_operative_to_bearer", True)):
            return False
        try:
            aura_range = float(source_sr.get("enhancement_tendrilous_emissions_vehicle_aura_range", 3.0) or 3.0)
        except (TypeError, ValueError):
            aura_range = 3.0
        if aura_range <= 0:
            return False
        nearby = self._friendly_vehicle_units_within_range_of_source(root, range_inches=float(aura_range))
        return bool(nearby)

    def mortarions_hammer_tendrilous_emissions_vehicle_reroll_wound_ones(
        self,
        attacker_model,
        target_unit,
        *,
        weapon_profile=None,
        game=None,
        game_map=None,
    ) -> tuple[bool, str]:
        if not self.is_mortarions_hammer():
            return False, ""
        if attacker_model is None or target_unit is None:
            return False, ""
        if weapon_profile is None:
            return False, ""
        parent_wargear = getattr(weapon_profile, "parent_wargear", None)
        is_ranged = bool(getattr(parent_wargear, "is_ranged", lambda: False)()) if parent_wargear is not None else False
        if not is_ranged:
            return False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = attacker_unit.get_attached_unit_root() if attacker_unit is not None else None
        if not self._unit_is_death_guard_vehicle(attacker_root):
            return False, ""
        if game is None:
            owner = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(owner, "game", None) if owner is not None else None
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)
        if game_map is None:
            return False, ""
        source_entries: list[tuple[object, dict, object]] = []
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            source_root, _member, source_sr, bearer = self._mortarions_source_member(
                unit,
                flag_key="enhancement_tendrilous_emissions",
                require_bearer_alive=True,
                require_bearer_leading=False,
            )
            if source_sr is None or source_root is None or bearer is None:
                continue
            source_id = str(get_entity_id(source_root) or "")
            if source_id in seen:
                continue
            seen.add(source_id)
            source_entries.append((source_root, source_sr, bearer))
        source_entries.sort(key=lambda entry: str(get_entity_id(entry[0]) or ""))
        target_root = target_unit.get_attached_unit_root() if hasattr(target_unit, "get_attached_unit_root") else target_unit
        for source_root, source_sr, bearer in source_entries:
            if not self._unit_in_army(source_root) or not source_root.is_alive() or not bool(getattr(source_root, "deployed", False)):
                continue
            if not bool(source_sr.get("enhancement_tendrilous_emissions_vehicle_reroll_wound_ones", True)):
                continue
            try:
                aura_range = float(source_sr.get("enhancement_tendrilous_emissions_vehicle_aura_range", 3.0) or 3.0)
            except (TypeError, ValueError):
                aura_range = 3.0
            if aura_range <= 0:
                continue
            nearby_units = self._friendly_vehicle_units_within_range_of_source(source_root, range_inches=float(aura_range))
            attacker_id = str(get_entity_id(attacker_root) or "")
            nearby_ids = {str(get_entity_id(unit) or "") for unit in list(nearby_units or [])}
            if attacker_id not in nearby_ids:
                continue
            has_los_fn = getattr(source_root, "_has_line_of_sight_to_target", None)
            if callable(has_los_fn) and not bool(has_los_fn(bearer, target_root, game_map)):
                continue
            source = str(
                source_sr.get("enhancement_tendrilous_emissions_source", "") or self._TENDRILOUS_EMISSIONS_SOURCE
            ).strip()
            if not source:
                source = self._TENDRILOUS_EMISSIONS_SOURCE
            return True, source
        return False, ""

    def shamblerot_witherbone_pipes_objective_control_bonus(self, model, *, unit=None, game=None) -> tuple[int, str]:
        del game
        if not self.is_shamblerot_vectorium():
            return 0, ""
        if model is None:
            return 0, ""
        root, _member, source_sr, _bearer = self._shamblerot_source_member(
            unit,
            flag_key="enhancement_witherbone_pipes",
            require_bearer_alive=True,
            require_bearer_leading=True,
        )
        if source_sr is None or root is None:
            return 0, ""
        if not self._unit_is_poxwalkers(root):
            return 0, ""
        model_unit = getattr(model, "parent_unit", None)
        model_root = model_unit.get_attached_unit_root() if hasattr(model_unit, "get_attached_unit_root") else model_unit
        if model_root is not root:
            return 0, ""
        try:
            bonus = int(source_sr.get("enhancement_witherbone_pipes_objective_control_bonus", 1) or 1)
        except (TypeError, ValueError):
            bonus = 1
        source = str(source_sr.get("enhancement_witherbone_pipes_source", "") or self._WITHERBONE_PIPES_SOURCE).strip()
        if not source:
            source = self._WITHERBONE_PIPES_SOURCE
        return max(0, int(bonus)), source

    def shamblerot_witherbone_pipes_leadership_test_modifier(self, unit, *, game=None) -> tuple[int, str]:
        del game
        if not self.is_shamblerot_vectorium():
            return 0, ""
        root, _member, source_sr, _bearer = self._shamblerot_source_member(
            unit,
            flag_key="enhancement_witherbone_pipes",
            require_bearer_alive=True,
            require_bearer_leading=True,
        )
        if source_sr is None or root is None:
            return 0, ""
        if not self._unit_is_poxwalkers(root):
            return 0, ""
        try:
            modifier = int(source_sr.get("enhancement_witherbone_pipes_leadership_test_modifier", 1) or 1)
        except (TypeError, ValueError):
            modifier = 1
        source = str(source_sr.get("enhancement_witherbone_pipes_source", "") or self._WITHERBONE_PIPES_SOURCE).strip()
        if not source:
            source = self._WITHERBONE_PIPES_SOURCE
        return int(modifier), source

    def shamblerot_lord_of_the_walking_pox_strategic_reserves_round_bonus(self, unit, *, game=None) -> tuple[int, str]:
        if not self.is_shamblerot_vectorium():
            return 0, ""
        root, _member, source_sr, _bearer = self._shamblerot_source_member(
            unit,
            flag_key="enhancement_lord_of_the_walking_pox",
            require_bearer_alive=True,
            require_bearer_leading=True,
        )
        if source_sr is None or root is None:
            return 0, ""
        if not self._unit_is_poxwalkers(root):
            return 0, ""
        is_in_reserves = bool(getattr(root, "is_in_strategic_reserves", lambda: False)())
        if not is_in_reserves:
            return 0, ""
        if game is None:
            owner = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(owner, "game", None) if owner is not None else None
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        if current_turn <= 0:
            return 0, ""
        effective_turn = 3
        bonus = int(max(0, int(effective_turn) - int(current_turn)))
        if bonus <= 0:
            return 0, ""
        source = str(
            source_sr.get("enhancement_lord_of_the_walking_pox_source", "")
            or self._LORD_OF_THE_WALKING_POX_SOURCE
        ).strip()
        if not source:
            source = self._LORD_OF_THE_WALKING_POX_SOURCE
        return int(bonus), source

    def shamblerot_sorrowsyphon_plague_wind_damage_bonus(
        self,
        attacker_model,
        weapon_profile,
        *,
        game=None,
    ) -> tuple[int, str]:
        if not self.is_shamblerot_vectorium():
            return 0, ""
        if attacker_model is None or weapon_profile is None:
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        root, _member, source_sr, bearer = self._shamblerot_source_member(
            attacker_unit,
            flag_key="enhancement_sorrowsyphon",
            require_bearer_alive=True,
            require_bearer_leading=True,
        )
        if source_sr is None or root is None or bearer is None:
            return 0, ""
        if not self._unit_is_poxwalkers(root):
            return 0, ""
        if self._model_identifier(attacker_model) != self._model_identifier(bearer):
            return 0, ""
        expected_weapon = str(source_sr.get("enhancement_sorrowsyphon_weapon_name", "") or "Plague Wind").strip()
        if not self._weapon_profile_matches_name(weapon_profile, expected_weapon):
            return 0, ""
        if game is None:
            owner = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(owner, "game", None) if owner is not None else None
        if game is not None:
            owner = getattr(self.army, "player", None)
            current_player = getattr(game, "get_current_player", lambda: None)()
            if owner is None or current_player is not owner:
                return 0, ""
        try:
            bonus = int(source_sr.get("enhancement_sorrowsyphon_plague_wind_damage_bonus", 1) or 1)
        except (TypeError, ValueError):
            bonus = 1
        source = str(source_sr.get("enhancement_sorrowsyphon_source", "") or self._SORROWSYPHON_SOURCE).strip()
        if not source:
            source = self._SORROWSYPHON_SOURCE
        return max(0, int(bonus)), source

    def shamblerot_note_sorrowsyphon_plague_wind_attacks(
        self,
        attacker_unit,
        *,
        weapon_declarations=None,
        game=None,
    ) -> bool:
        if not self.is_shamblerot_vectorium():
            return False
        if attacker_unit is None:
            return False
        root, _member, source_sr, bearer = self._shamblerot_source_member(
            attacker_unit,
            flag_key="enhancement_sorrowsyphon",
            require_bearer_alive=True,
            require_bearer_leading=True,
        )
        if source_sr is None or root is None or bearer is None:
            return False
        if not self._unit_is_poxwalkers(root):
            return False
        expected_weapon = str(source_sr.get("enhancement_sorrowsyphon_weapon_name", "") or "Plague Wind").strip()
        bearer_id = self._model_identifier(bearer)
        used_plague_wind = False
        for declaration in list(weapon_declarations or []):
            if not isinstance(declaration, dict):
                continue
            weapon_profile = declaration.get("weapon_profile")
            if not self._weapon_profile_matches_name(weapon_profile, expected_weapon):
                continue
            models = list(declaration.get("models") or [])
            if not models:
                continue
            selected_ids = {self._model_identifier(model) for model in models if model is not None}
            if bearer_id and bearer_id in selected_ids:
                used_plague_wind = True
                break
        if not used_plague_wind:
            return False
        root_sr = getattr(root, "special_rules", None)
        if not isinstance(root_sr, dict):
            root_sr = {}
        root_sr["enhancement_sorrowsyphon_pending_bodyguard_loss"] = True
        try:
            root_sr["enhancement_sorrowsyphon_pending_turn"] = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            root_sr["enhancement_sorrowsyphon_pending_turn"] = 0
        owner = getattr(self.army, "player", None) if self.army is not None else None
        root_sr["enhancement_sorrowsyphon_pending_owner"] = str(getattr(owner, "id", "") or "")
        root.special_rules = root_sr
        return True

    def shamblerot_consume_sorrowsyphon_bodyguard_loss(self, attacker_unit, *, game=None) -> tuple[int, str, object, object]:
        if not self.is_shamblerot_vectorium():
            return 0, "", None, None
        if attacker_unit is None:
            return 0, "", None, None
        root, source_unit, source_sr, _bearer = self._shamblerot_source_member(
            attacker_unit,
            flag_key="enhancement_sorrowsyphon",
            require_bearer_alive=True,
            require_bearer_leading=True,
        )
        if source_sr is None or root is None or source_unit is None:
            return 0, "", None, None
        if not self._unit_is_poxwalkers(root):
            return 0, "", None, None
        root_sr = getattr(root, "special_rules", None)
        if not isinstance(root_sr, dict):
            return 0, "", None, None
        if not bool(root_sr.get("enhancement_sorrowsyphon_pending_bodyguard_loss", False)):
            return 0, "", None, None
        if game is not None:
            try:
                marked_turn = int(root_sr.get("enhancement_sorrowsyphon_pending_turn", 0) or 0)
            except (TypeError, ValueError):
                marked_turn = 0
            try:
                current_turn = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_turn = 0
            if marked_turn and current_turn and marked_turn != current_turn:
                root_sr.pop("enhancement_sorrowsyphon_pending_bodyguard_loss", None)
                root_sr.pop("enhancement_sorrowsyphon_pending_turn", None)
                root_sr.pop("enhancement_sorrowsyphon_pending_owner", None)
                root.special_rules = root_sr
                return 0, "", None, None
        root_sr.pop("enhancement_sorrowsyphon_pending_bodyguard_loss", None)
        root_sr.pop("enhancement_sorrowsyphon_pending_turn", None)
        root_sr.pop("enhancement_sorrowsyphon_pending_owner", None)
        root.special_rules = root_sr
        alive_bodyguard: list = []
        for model in list(getattr(root, "models", []) or []):
            alive_attr = getattr(model, "is_alive", False)
            model_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if model_alive:
                alive_bodyguard.append(model)
        if not alive_bodyguard:
            return 0, "", None, None
        loss_die = str(source_sr.get("enhancement_sorrowsyphon_bodyguard_loss_die", "") or "D3").strip().upper() or "D3"
        try:
            loss_count = int(get_roll(loss_die) or 0)
        except (TypeError, ValueError):
            loss_count = 0
        loss_count = int(max(0, min(int(loss_count), len(alive_bodyguard))))
        if loss_count <= 0:
            return 0, "", None, None
        source = str(source_sr.get("enhancement_sorrowsyphon_source", "") or self._SORROWSYPHON_SOURCE).strip()
        if not source:
            source = self._SORROWSYPHON_SOURCE
        return int(loss_count), source, source_unit, root

    def shamblerot_talisman_of_burgeoning_toughness_bonus(self, model, *, unit=None, game=None) -> tuple[int, str]:
        del game
        if not self.is_shamblerot_vectorium():
            return 0, ""
        if model is None:
            return 0, ""
        root, _member, source_sr, _bearer = self._shamblerot_source_member(
            unit,
            flag_key="enhancement_talisman_of_burgeoning",
            require_bearer_alive=True,
            require_bearer_leading=True,
        )
        if source_sr is None or root is None:
            return 0, ""
        if not self._unit_is_poxwalkers(root):
            return 0, ""
        model_unit = getattr(model, "parent_unit", None)
        model_root = model_unit.get_attached_unit_root() if hasattr(model_unit, "get_attached_unit_root") else model_unit
        if model_root is not root:
            return 0, ""
        if model_unit is not root and not self._model_has_keyword(model, "POXWALKERS"):
            return 0, ""
        try:
            bonus = int(source_sr.get("enhancement_talisman_of_burgeoning_toughness_bonus", 1) or 1)
        except (TypeError, ValueError):
            bonus = 1
        source = str(
            source_sr.get("enhancement_talisman_of_burgeoning_source", "")
            or self._TALISMAN_OF_BURGEONING_SOURCE
        ).strip()
        if not source:
            source = self._TALISMAN_OF_BURGEONING_SOURCE
        return max(0, int(bonus)), source

    def tallyband_beckoning_blight_deep_strike_min_enemy_distance(
        self,
        unit,
        *,
        prospective_positions=None,
        game=None,
        game_map=None,
    ) -> tuple[float, str]:
        del game
        del game_map
        if not self.is_tallyband_summoners():
            return 0.0, ""
        if unit is None:
            return 0.0, ""
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if root is None or not self._unit_in_army(root):
            return 0.0, ""
        if not self._unit_is_plague_legions(root):
            return 0.0, ""
        prospective = list(prospective_positions or [])
        if not prospective:
            return 0.0, ""

        models = list(getattr(root, "models", []) or [])
        if not models:
            return 0.0, ""
        potential_bases = []
        for idx, (x, y, z, facing) in enumerate(prospective):
            if idx >= len(models):
                break
            make_base = getattr(root, "_create_potential_base", None)
            if not callable(make_base):
                return 0.0, ""
            base = make_base(x, y, z, facing, model=models[idx])
            if base is None:
                return 0.0, ""
            potential_bases.append(base)
        if not potential_bases:
            return 0.0, ""

        from ..utility import aura_utils as _aura_utils

        best_distance: Optional[float] = None
        best_source = ""
        seen_source_roots: set[str] = set()
        for source_unit in list(getattr(self.army, "units", []) or []):
            source_root, _member, source_sr, bearer = self._tallyband_source_member(
                source_unit,
                flag_key="enhancement_beckoning_blight",
                require_bearer_alive=True,
                require_bearer_leading=False,
            )
            if source_sr is None or source_root is None or bearer is None:
                continue
            source_root_id = str(get_entity_id(source_root) or "")
            if source_root_id in seen_source_roots:
                continue
            seen_source_roots.add(source_root_id)
            if not self._unit_eligible_for_deadly_vectors(source_root):
                continue

            bearer_base = getattr(bearer, "model_base", None)
            if bearer_base is None:
                continue
            try:
                bearer_range = float(source_sr.get("enhancement_beckoning_blight_bearer_range", 12.0) or 12.0)
            except (TypeError, ValueError):
                bearer_range = 12.0
            try:
                min_enemy_distance = float(
                    source_sr.get("enhancement_beckoning_blight_min_enemy_distance", 6.0) or 6.0
                )
            except (TypeError, ValueError):
                min_enemy_distance = 6.0
            if bearer_range <= 0.0 or min_enemy_distance <= 0.0:
                continue

            wholly_within = True
            for potential_base in list(potential_bases):
                dist = float(_aura_utils.horizontal_distance_between_bases_2d(potential_base, bearer_base))
                if dist > float(bearer_range) + 1e-6:
                    wholly_within = False
                    break
            if not wholly_within:
                continue

            source = str(
                source_sr.get("enhancement_beckoning_blight_source", "") or self._BECKONING_BLIGHT_SOURCE
            ).strip()
            if not source:
                source = self._BECKONING_BLIGHT_SOURCE
            if best_distance is None or float(min_enemy_distance) < float(best_distance):
                best_distance = float(min_enemy_distance)
                best_source = source

        if best_distance is None:
            return 0.0, ""
        return float(best_distance), str(best_source or self._BECKONING_BLIGHT_SOURCE)

    def _tallyband_tome_sources_for_unit(self, unit, *, game=None, game_map=None):
        del game
        del game_map
        if not self.is_tallyband_summoners() or unit is None or self.army is None:
            return []
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if root is None or not self._unit_in_army(root):
            return []
        if not self._unit_is_plague_legions(root):
            return []
        if not self._unit_eligible_for_deadly_vectors(root):
            return []

        from ..utility import aura_utils as _aura_utils

        entries = []
        seen_sources: set[str] = set()
        for source_unit in list(getattr(self.army, "units", []) or []):
            source_root, _member, source_sr, bearer = self._tallyband_source_member(
                source_unit,
                flag_key="enhancement_tome_of_bounteous_blessings",
                require_bearer_alive=True,
                require_bearer_leading=False,
            )
            if source_sr is None or source_root is None or bearer is None:
                continue
            source_root_id = str(get_entity_id(source_root) or "")
            if source_root_id in seen_sources:
                continue
            seen_sources.add(source_root_id)
            if not self._unit_eligible_for_deadly_vectors(source_root):
                continue
            try:
                aura_range = float(source_sr.get("enhancement_tome_of_bounteous_blessings_range", 12.0) or 12.0)
            except (TypeError, ValueError):
                aura_range = 12.0
            if aura_range <= 0.0:
                continue
            if not bool(
                _aura_utils.model_within_range_of_unit(
                    bearer,
                    root,
                    float(aura_range),
                    use_attached_aggregate=True,
                )
            ):
                continue
            entries.append((source_root, source_sr, bearer))
        entries.sort(key=lambda entry: str(get_entity_id(entry[0]) or ""))
        return entries

    def tallyband_tome_of_bounteous_blessings_battle_shock_modifier(self, unit, *, game=None) -> tuple[int, str]:
        entries = list(self._tallyband_tome_sources_for_unit(unit, game=game, game_map=getattr(game, "map", None)))
        if not entries:
            return 0, ""
        total = 0
        source_names: list[str] = []
        for _source_root, source_sr, _bearer in list(entries):
            try:
                modifier = int(
                    source_sr.get("enhancement_tome_of_bounteous_blessings_battle_shock_test_modifier", 1) or 1
                )
            except (TypeError, ValueError):
                modifier = 1
            total += int(modifier)
            source_name = str(
                source_sr.get("enhancement_tome_of_bounteous_blessings_source", "")
                or self._TOME_OF_BOUNTEOUS_BLESSINGS_SOURCE
            ).strip()
            if not source_name:
                source_name = self._TOME_OF_BOUNTEOUS_BLESSINGS_SOURCE
            if source_name not in source_names:
                source_names.append(source_name)
        if not source_names:
            return int(total), self._TOME_OF_BOUNTEOUS_BLESSINGS_SOURCE
        if len(source_names) == 1:
            return int(total), source_names[0]
        return int(total), " / ".join(source_names)

    def tallyband_tome_of_bounteous_blessings_on_battle_shock_pass(self, unit, *, game=None) -> list[dict]:
        entries = list(self._tallyband_tome_sources_for_unit(unit, game=game, game_map=getattr(game, "map", None)))
        if not entries:
            return []
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if root is None:
            return []
        game_map = getattr(game, "map", None) if game is not None else None
        outcomes: list[dict] = []
        is_battleline = bool(self._unit_has_keyword(root, "BATTLELINE"))

        for _source_root, source_sr, _bearer in list(entries):
            roll_expr = str(
                source_sr.get("enhancement_tome_of_bounteous_blessings_restore_die", "") or "D3"
            ).strip().upper() or "D3"
            try:
                amount = int(get_roll(roll_expr) or 0)
            except (TypeError, ValueError):
                amount = 0
            amount = int(max(0, amount))
            source = str(
                source_sr.get("enhancement_tome_of_bounteous_blessings_source", "")
                or self._TOME_OF_BOUNTEOUS_BLESSINGS_SOURCE
            ).strip()
            if not source:
                source = self._TOME_OF_BOUNTEOUS_BLESSINGS_SOURCE
            healed = 0
            returned = 0
            if amount > 0:
                if is_battleline:
                    destroyed = list(getattr(root, "models_lost", []) or [])
                    destroyed.sort(key=lambda model: str(get_entity_id(model) or ""))
                    for model in list(destroyed[: int(amount)]):
                        if hasattr(root, "models_lost") and model in root.models_lost:
                            root.models_lost.remove(model)
                        set_parent = getattr(model, "set_parent_unit", None)
                        if callable(set_parent):
                            set_parent(root)
                        else:
                            model.parent_unit = root
                        try:
                            model.wounds = int(
                                getattr(model, "_base_wounds", 0)
                                or getattr(model, "base_wounds", 0)
                                or getattr(model, "max_wounds", 0)
                                or 1
                            )
                        except (TypeError, ValueError):
                            model.wounds = 1
                        check_profile = getattr(model, "_check_damaged_profile", None)
                        if callable(check_profile):
                            check_profile()
                        mark_pending = getattr(root, "_mark_models_pending_placement", None)
                        if callable(mark_pending):
                            mark_pending([model], source="tome_of_bounteous_blessings")
                        add_model = getattr(root, "add_model", None)
                        if callable(add_model):
                            add_model(model)
                        else:
                            root.models.append(model)
                        returned += 1
                    request_pending = getattr(root, "_request_pending_placement_decision", None)
                    if int(returned) > 0 and callable(request_pending):
                        request_pending(game_map=game_map)
                    update_coherency = getattr(root, "update_coherency", None)
                    if int(returned) > 0 and callable(update_coherency):
                        update_coherency()
                else:
                    attached_models_fn = getattr(root, "get_attached_unit_models", None)
                    models = list(attached_models_fn() or []) if callable(attached_models_fn) else list(getattr(root, "models", []) or [])
                    wounded = []
                    for model in list(models or []):
                        alive_attr = getattr(model, "is_alive", False)
                        model_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                        if not model_alive:
                            continue
                        try:
                            max_wounds = int(
                                getattr(model, "max_wounds", 0)
                                or getattr(model, "_base_wounds", 0)
                                or getattr(model, "base_wounds", 0)
                                or 0
                            )
                        except (TypeError, ValueError):
                            max_wounds = 0
                        try:
                            current_wounds = int(getattr(model, "wounds", max_wounds) or 0)
                        except (TypeError, ValueError):
                            current_wounds = 0
                        if max_wounds <= 0 or current_wounds >= max_wounds:
                            continue
                        wounded.append((str(get_entity_id(model) or ""), model, current_wounds, max_wounds))
                    wounded.sort(key=lambda entry: entry[0])
                    if wounded:
                        _model_id, target_model, current_wounds, max_wounds = wounded[0]
                        heal_fn = getattr(target_model, "heal", None)
                        if callable(heal_fn):
                            heal_fn(int(amount))
                        else:
                            updated = min(int(max_wounds), int(current_wounds) + int(amount))
                            target_model.wounds = int(updated)
                        try:
                            post_wounds = int(getattr(target_model, "wounds", 0) or 0)
                        except (TypeError, ValueError):
                            post_wounds = int(current_wounds)
                        healed = int(max(0, min(int(amount), int(post_wounds) - int(current_wounds))))
            outcomes.append(
                {
                    "target_unit_id": str(get_entity_id(root) or ""),
                    "source": source,
                    "roll": int(amount),
                    "healed_wounds": int(healed),
                    "returned_models": int(returned),
                    "battleline_target": bool(is_battleline),
                }
            )
        return outcomes

    def resolve_tallyband_entropic_knell_forced_tests(
        self,
        *,
        game=None,
        opponent_player=None,
        tested_ids: Optional[set[str]] = None,
    ) -> list[dict]:
        if not self.is_tallyband_summoners() or self.army is None:
            return []
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return []
        owner = getattr(self.army, "player", None)
        if owner is None or opponent_player is None or opponent_player is owner:
            return []
        game_map = getattr(game, "map", None)
        if game_map is None:
            return []
        try:
            turn = int(getattr(game, "turn", 0) or 1)
        except (TypeError, ValueError):
            turn = 1

        from ..utility import aura_utils as _aura_utils

        outcomes: list[dict] = []
        seen_sources: set[str] = set()
        source_entries = []
        for source_unit in list(getattr(self.army, "units", []) or []):
            source_root, _member, source_sr, bearer = self._tallyband_source_member(
                source_unit,
                flag_key="enhancement_entropic_knell",
                require_bearer_alive=True,
                require_bearer_leading=False,
            )
            if source_sr is None or source_root is None or bearer is None:
                continue
            source_root_id = str(get_entity_id(source_root) or "")
            if source_root_id in seen_sources:
                continue
            seen_sources.add(source_root_id)
            if not self._unit_eligible_for_deadly_vectors(source_root):
                continue
            source_entries.append((source_root, source_sr, bearer))
        source_entries.sort(key=lambda entry: str(get_entity_id(entry[0]) or ""))

        for source_root, source_sr, bearer in list(source_entries):
            try:
                aura_range = float(source_sr.get("enhancement_entropic_knell_range", 6.0) or 6.0)
            except (TypeError, ValueError):
                aura_range = 6.0
            if aura_range <= 0.0:
                continue
            try:
                test_modifier = int(source_sr.get("enhancement_entropic_knell_battle_shock_test_modifier", -1) or -1)
            except (TypeError, ValueError):
                test_modifier = -1
            source = str(source_sr.get("enhancement_entropic_knell_source", "") or self._ENTROPIC_KNELL_SOURCE).strip()
            if not source:
                source = self._ENTROPIC_KNELL_SOURCE

            candidate_targets: dict[str, object] = {}
            for enemy in list(game_map.get_enemy_units(source_root) or []):
                if enemy is None:
                    continue
                enemy_root = enemy.get_attached_unit_root() if hasattr(enemy, "get_attached_unit_root") else enemy
                enemy_id = str(get_entity_id(enemy_root) or "")
                if not enemy_id:
                    continue
                candidate_targets[enemy_id] = enemy_root
            for enemy_id in sorted(candidate_targets):
                target_root = candidate_targets[enemy_id]
                if target_root is None:
                    continue
                if tested_ids is not None and enemy_id in tested_ids:
                    continue
                if not self._unit_eligible_for_deadly_vectors(target_root):
                    continue
                below_starting_fn = getattr(target_root, "is_below_starting_strength", None)
                if not callable(below_starting_fn) or not bool(below_starting_fn()):
                    continue
                if not bool(
                    _aura_utils.model_within_range_of_unit(
                        bearer,
                        target_root,
                        float(aura_range),
                        use_attached_aggregate=True,
                    )
                ):
                    continue
                if test_modifier:
                    target_sr = getattr(target_root, "special_rules", None)
                    if not isinstance(target_sr, dict):
                        target_sr = {}
                    target_sr = dict(target_sr)
                    current_modifier = int(target_sr.get("battle_shock_test_modifier", 0) or 0)
                    target_sr["battle_shock_test_modifier"] = int(current_modifier + int(test_modifier))
                    reasons = list(target_sr.get("battle_shock_test_modifier_reasons", []) or [])
                    reasons.append(f"{source} ({int(test_modifier):+d})")
                    target_sr["battle_shock_test_modifier_reasons"] = reasons
                    target_root.special_rules = target_sr
                take_test = getattr(target_root, "take_battle_shock_test", None)
                if not callable(take_test):
                    continue
                take_test(int(turn))
                if tested_ids is not None:
                    tested_ids.add(enemy_id)
                outcomes.append(
                    {
                        "source_unit_id": str(get_entity_id(source_root) or ""),
                        "target_unit_id": enemy_id,
                        "source": source,
                        "modifier": int(test_modifier),
                    }
                )
        return outcomes

    def resolve_rejuvenating_swarm_phase_end(self, *, phase=None, game=None) -> list[dict]:
        del phase
        if not self.is_flyblown_host() or self.army is None:
            return []
        if game is not None and not bool(getattr(game, "is_authoritative", True)):
            return []
        outcomes: list[dict] = []
        seen_roots: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root, _member, source_sr, bearer = self._flyblown_source_member(
                unit,
                flag_key="enhancement_rejuvenating_swarm",
                require_bearer_alive=True,
                require_bearer_leading=False,
            )
            if source_sr is None or root is None or bearer is None:
                continue
            root_id = str(get_entity_id(root) or "")
            if root_id in seen_roots:
                continue
            seen_roots.add(root_id)
            if not self._unit_in_army(root) or not root.is_alive():
                continue
            try:
                max_wounds = int(
                    getattr(bearer, "max_wounds", 0)
                    or getattr(bearer, "_base_wounds", 0)
                    or 0
                )
            except (TypeError, ValueError):
                max_wounds = 0
            try:
                current_wounds = int(getattr(bearer, "wounds", max_wounds) or 0)
            except (TypeError, ValueError):
                current_wounds = 0
            if max_wounds <= 0:
                continue
            lost_wounds = max(0, max_wounds - current_wounds)
            if lost_wounds <= 0:
                continue
            heal_fn = getattr(bearer, "heal", None)
            if not callable(heal_fn):
                continue
            heal_fn(int(lost_wounds))
            source = str(
                source_sr.get("enhancement_rejuvenating_swarm_source", "") or self._REJUVENATING_SWARM_SOURCE
            ).strip()
            if not source:
                source = self._REJUVENATING_SWARM_SOURCE
            outcomes.append(
                {
                    "source_unit_id": str(get_entity_id(root) or ""),
                    "bearer_model_id": self._model_identifier(bearer),
                    "healed": int(lost_wounds),
                    "source": source,
                }
            )
        return outcomes

    def on_phase_end(self, phase, active_player=None, *, game=None) -> None:
        del active_player
        self.resolve_rejuvenating_swarm_phase_end(phase=phase, game=game)

    def resolve_face_of_death(self, *, game=None) -> list[dict]:
        if not self.is_death_lords_chosen() or self.army is None:
            return []
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return []
        game_map = getattr(game, "map", None)
        if game_map is None:
            return []
        owner = getattr(self.army, "player", None)
        if owner is None:
            return []
        try:
            current_turn = int(getattr(game, "turn", 0) or 1)
        except (TypeError, ValueError):
            current_turn = 1
        outcomes: list[dict] = []
        source_roots: list = []
        seen_source_ids: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root, _member, source_sr, _bearer = self._death_lords_source_member(
                unit,
                flag_key="enhancement_face_of_death",
                require_bearer_alive=True,
                require_bearer_leading=False,
            )
            if source_sr is None or root is None:
                continue
            root_id = str(get_entity_id(root) or "")
            if root_id in seen_source_ids:
                continue
            seen_source_ids.add(root_id)
            source_roots.append((root, source_sr))
        source_roots.sort(key=lambda entry: str(get_entity_id(entry[0]) or ""))

        for source_root, source_sr in source_roots:
            if not self._unit_eligible_for_deadly_vectors(source_root):
                continue
            tested_enemy_ids: set[str] = set()
            enemy_roots: list = []
            for enemy in list(game_map.get_enemy_units(source_root) or []):
                if enemy is None:
                    continue
                enemy_root = enemy.get_attached_unit_root()
                enemy_id = str(get_entity_id(enemy_root) or "")
                if enemy_id in tested_enemy_ids:
                    continue
                tested_enemy_ids.add(enemy_id)
                enemy_roots.append(enemy_root)
            enemy_roots.sort(key=self._enemy_root_sort_key)
            source_name = str(source_sr.get("enhancement_face_of_death_source", "") or self._FACE_OF_DEATH_SOURCE).strip()
            if not source_name:
                source_name = self._FACE_OF_DEATH_SOURCE
            for enemy_root in enemy_roots:
                if enemy_root is None:
                    continue
                if not self._unit_eligible_for_deadly_vectors(enemy_root):
                    continue
                if not bool(game_map.is_within_engagement_range(source_root, enemy_root)):
                    continue
                take_test = getattr(enemy_root, "take_battle_shock_test", None)
                if not callable(take_test):
                    continue
                take_test(int(current_turn))
                outcomes.append(
                    {
                        "source_unit_id": str(get_entity_id(source_root) or ""),
                        "target_unit_id": str(get_entity_id(enemy_root) or ""),
                        "source": source_name,
                    }
                )
        return outcomes

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None:
            return
        if (
            self.manifold_maladies_resolved_round is not None
            and int(self.manifold_maladies_resolved_round) != int(round_value)
        ):
            self.manifold_maladies_resolved_round = None
        if (
            self.miasmic_bombardment_resolved_round is not None
            and int(self.miasmic_bombardment_resolved_round) != int(round_value)
        ):
            self.miasmic_bombardment_resolved_round = None
        if not bool(getattr(game, "is_authoritative", True)):
            return
        player = getattr(self.army, "player", None) if self.army is not None else None
        if player is None:
            return
        if self.is_champions_of_contagion():
            self.build_manifold_maladies_request(game=game, player=player, battle_round=round_value)
        else:
            self.manifold_maladies_resolved_round = None

        if self.is_mortarions_hammer():
            self.build_miasmic_bombardment_request(game=game, player=player, battle_round=round_value)
        else:
            self.miasmic_bombardment_resolved_round = None
            self._clear_miasmic_bombardment_marks(game=game)

        if self.is_shamblerot_vectorium():
            self.apply_shamblerot_vectorium_poxwalkers_battleline_keywords()
        else:
            self.numberless_horde_spawned_rounds = set()

    def _numberless_horde_points_limit(self, *, game=None) -> int:
        points_limit = 0
        if self.army is not None:
            try:
                points_limit = int(getattr(self.army, "points_limit", 0) or 0)
            except (TypeError, ValueError):
                points_limit = 0
        if points_limit > 0:
            return points_limit
        battlefield = getattr(game, "battlefield", None) if game is not None else None
        if battlefield is None:
            return 0
        try:
            return int(getattr(battlefield, "points", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def _numberless_horde_spawn_rounds(self, *, game=None) -> tuple[int, ...]:
        points_limit = int(self._numberless_horde_points_limit(game=game) or 0)
        if points_limit <= 1000:
            return (2, 3)
        if points_limit <= 2000:
            return (2, 3, 4)
        return (2, 3, 4, 5)

    def _unit_is_poxwalkers(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, "POXWALKERS"):
            return True
        return "poxwalker" in self._norm(getattr(unit, "name", ""))

    def apply_shamblerot_vectorium_poxwalkers_battleline_keywords(self, unit=None) -> None:
        if not self.is_shamblerot_vectorium() or self.army is None:
            return
        entries = list(getattr(self.army, "units", []) or []) if unit is None else [unit]
        for entry in entries:
            root = entry.get_attached_unit_root() if entry is not None else None
            if root is None or not self._unit_in_army(root):
                continue
            if not self._unit_is_poxwalkers(root):
                continue
            keywords = list(getattr(root, "keywords", []) or [])
            if any(str(token or "").strip().lower() == "battleline" for token in keywords):
                continue
            keywords.append("Battleline")
            root.keywords = keywords

    def _numberless_horde_poxwalkers_datasheet(self):
        if self._numberless_horde_cached_datasheet is not None:
            return self._numberless_horde_cached_datasheet
        if self.army is not None:
            for unit in list(getattr(self.army, "units", []) or []):
                if unit is None or not self._unit_is_poxwalkers(unit):
                    continue
                datasheet = getattr(unit, "_datasheet", None)
                if datasheet is not None:
                    self._numberless_horde_cached_datasheet = datasheet
                    return datasheet
        from ..waha_helper.waha_helper import WahaHelper

        helper = WahaHelper()
        datasheet = helper.get_full_datasheet_info_by_name(
            self._NUMBERLESS_HORDE_POXWALKERS_NAME,
            faction_id=self.faction_id,
        )
        if datasheet is not None:
            self._numberless_horde_cached_datasheet = datasheet
        return datasheet

    def _create_numberless_horde_poxwalkers_unit(self):
        datasheet = self._numberless_horde_poxwalkers_datasheet()
        if datasheet is None:
            return None
        from ..units.unit import Unit as UnitClass

        try:
            unit = UnitClass(datasheet, quantity=int(self._NUMBERLESS_HORDE_STARTING_STRENGTH))
        except TypeError:
            unit = UnitClass(datasheet)
        unit.spawned_in_battle = True
        return unit

    def _prepare_numberless_horde_unit(self, unit, *, game=None) -> bool:
        if unit is None or self.army is None:
            return False
        set_parent = getattr(unit, "set_parent_army", None)
        if callable(set_parent):
            set_parent(self.army)
        else:
            unit.parent_army = self.army
        set_reserve = getattr(unit, "set_reserve_status", None)
        if callable(set_reserve):
            set_reserve("strategic_reserves")
        else:
            unit.reserve_status = "strategic_reserves"
        mark_midgame = getattr(unit, "mark_entered_reserves_midgame", None)
        if callable(mark_midgame):
            mark_midgame(game=game)
        unit.deployed = True
        unit.reserve_turn_deployed = None
        unit.arrived_from_reserves_this_turn = False
        self.army.add_unit(unit)
        self.apply_shamblerot_vectorium_poxwalkers_battleline_keywords(unit)
        game_map = getattr(game, "map", None) if game is not None else None
        if game_map is not None and hasattr(game_map, "units") and unit in game_map.units:
            game_map.units.remove(unit)
        return True

    def spawn_numberless_horde_unit(self, *, game=None, battle_round=None):
        if not self.is_shamblerot_vectorium():
            return None
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None or int(round_value) <= 0:
            return None
        if int(round_value) not in set(self._numberless_horde_spawn_rounds(game=game)):
            return None
        if int(round_value) in set(int(v) for v in list(self.numberless_horde_spawned_rounds or set())):
            return None
        unit = self._create_numberless_horde_poxwalkers_unit()
        if unit is None:
            return None
        if not self._prepare_numberless_horde_unit(unit, game=game):
            return None
        self.numberless_horde_spawned_rounds.add(int(round_value))
        return unit

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if not self.is_shamblerot_vectorium():
            return
        owner = getattr(self.army, "player", None) if self.army is not None else None
        if owner is None or player is not owner:
            return
        if game is None:
            game = getattr(owner, "game", None)
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        if phase_name and phase_name != "COMMAND_PHASE":
            return
        self.apply_shamblerot_vectorium_poxwalkers_battleline_keywords()
        round_value = self._resolve_battle_round(game=game)
        if round_value is None:
            return
        spawned = self.spawn_numberless_horde_unit(game=game, battle_round=int(round_value))
        if spawned is None:
            return
        event_system = getattr(game, "event_system", None)
        if event_system is not None:
            event_system.publish(
                "action_log",
                player=owner,
                message=(
                    f"{self._NUMBERLESS_HORDE_SOURCE}: added "
                    f"{getattr(spawned, 'name', self._NUMBERLESS_HORDE_POXWALKERS_NAME)} "
                    "to Strategic Reserves at Starting Strength 10."
                ),
            )

    def _miasmic_bombardment_max_units(self, *, game=None) -> int:
        points_limit = 0
        battlefield = getattr(game, "battlefield", None) if game is not None else None
        if battlefield is not None:
            try:
                points_limit = int(getattr(battlefield, "points", 0) or 0)
            except (TypeError, ValueError):
                points_limit = 0
        if points_limit <= 0:
            try:
                points_limit = int(getattr(self.army, "points_limit", 0) or 0)
            except (TypeError, ValueError):
                points_limit = 0
        if points_limit <= 1000:
            return 1
        if points_limit <= 2000:
            return 2
        return 3

    def _collect_miasmic_bombardment_candidates(self, *, game=None) -> list:
        if game is None or self.army is None:
            return []
        from ..utility import aura_utils as _aura_utils

        friendly_sources = [
            root
            for root in list(self._iter_unique_attached_roots() or [])
            if self._unit_eligible_for_deadly_vectors(root)
        ]
        owner = getattr(self.army, "player", None)
        candidates_by_id: dict[str, object] = {}
        for player in list(getattr(game, "players", []) or []):
            if player is None or player is owner:
                continue
            enemy_army = getattr(player, "army", None)
            if enemy_army is None and hasattr(player, "get_army"):
                enemy_army = player.get_army()
            for root in list(self._iter_unique_enemy_roots(enemy_army) or []):
                root_id = str(get_entity_id(root) or "")
                if not root_id or root_id in candidates_by_id:
                    continue
                if not self._unit_eligible_for_deadly_vectors(root):
                    continue
                too_close = False
                for source in friendly_sources:
                    if _aura_utils.unit_within_range_of_unit(
                        source,
                        root,
                        float(self._MIASMIC_BOMBARDMENT_RANGE),
                        use_attached_aggregate=True,
                    ):
                        too_close = True
                        break
                if too_close:
                    continue
                candidates_by_id[root_id] = root
        return [candidates_by_id[uid] for uid in sorted(candidates_by_id)]

    def _pending_miasmic_bombardment_request(self, game, *, army_id: str, battle_round: int):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None:
            return None
        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS

        for req in list(getattr(queue, "list", lambda: [])() or []):
            if str(getattr(req, "decision_type", "") or "") != DECISION_SELECT_REALM_OF_CHAOS_UNITS:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "").strip().lower() != "miasmic_bombardment":
                continue
            if str(ctx.get("army_id", "") or "") != str(army_id):
                continue
            if int(ctx.get("battle_round", 0) or 0) != int(battle_round):
                continue
            return req
        return None

    @staticmethod
    def _clear_miasmic_bombardment_mark(unit) -> None:
        if unit is None:
            return
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return
        changed = False
        for key in (
            "miasmic_bombardment_active",
            "miasmic_bombardment_owner",
            "miasmic_bombardment_round",
            "miasmic_bombardment_source",
        ):
            if key in sr:
                sr.pop(key, None)
                changed = True
        if changed:
            unit.special_rules = sr

    def _clear_miasmic_bombardment_marks(self, *, game=None, keep_round: int = 0) -> None:
        if game is None or self.army is None:
            return
        owner = getattr(self.army, "player", None)
        owner_id = str(getattr(owner, "id", "") or "")
        if not owner_id:
            return
        keep_round_value = int(keep_round or 0)
        for player in list(getattr(game, "players", []) or []):
            if player is None or player is owner:
                continue
            enemy_army = getattr(player, "army", None)
            if enemy_army is None and hasattr(player, "get_army"):
                enemy_army = player.get_army()
            for root in list(self._iter_unique_enemy_roots(enemy_army) or []):
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if not bool(sr.get("miasmic_bombardment_active", False)):
                    continue
                if str(sr.get("miasmic_bombardment_owner", "") or "") != owner_id:
                    continue
                try:
                    marked_round = int(sr.get("miasmic_bombardment_round", 0) or 0)
                except (TypeError, ValueError):
                    marked_round = 0
                if keep_round_value > 0 and marked_round == keep_round_value:
                    continue
                self._clear_miasmic_bombardment_mark(root)

    def can_select_miasmic_bombardment(self, *, game=None, battle_round=None) -> bool:
        if not self.is_mortarions_hammer():
            return False
        if game is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(player, "game", None) if player is not None else None
        if game is None:
            return False
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None:
            return False
        if (
            self.miasmic_bombardment_resolved_round is not None
            and int(self.miasmic_bombardment_resolved_round) == int(round_value)
        ):
            return False
        candidates = list(self._collect_miasmic_bombardment_candidates(game=game) or [])
        if not candidates:
            return False
        return int(self._miasmic_bombardment_max_units(game=game) or 0) > 0

    def miasmic_bombardment_selection_is_valid(self, unit_ids, *, game=None, battle_round=None) -> tuple[bool, str]:
        if not self.is_mortarions_hammer():
            return False, "Miasmic Bombardment requires Mortarion's Hammer."
        if game is None:
            player = getattr(self.army, "player", None) if self.army is not None else None
            game = getattr(player, "game", None) if player is not None else None
        if game is None:
            return False, "Miasmic Bombardment requires a game context."
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None or int(round_value) <= 0:
            return False, "Miasmic Bombardment requires a valid battle round."
        if (
            self.miasmic_bombardment_resolved_round is not None
            and int(self.miasmic_bombardment_resolved_round) == int(round_value)
        ):
            return False, "Miasmic Bombardment has already resolved this battle round."
        if not isinstance(unit_ids, list):
            return False, "Miasmic Bombardment selection requires unit_ids."

        selected_ids = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        max_units = int(self._miasmic_bombardment_max_units(game=game) or 0)
        if len(selected_ids) > max(0, max_units):
            return False, f"Miasmic Bombardment can select at most {int(max_units)} unit(s)."

        candidate_ids = {
            str(get_entity_id(unit) or "")
            for unit in list(self._collect_miasmic_bombardment_candidates(game=game) or [])
            if str(get_entity_id(unit) or "")
        }
        for uid in selected_ids:
            if uid not in candidate_ids:
                return False, "Miasmic Bombardment selection contains an ineligible unit."
        return True, ""

    def apply_miasmic_bombardment_selection(self, unit_ids, *, game=None, battle_round: int = 0) -> list[str]:
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None:
            return []
        valid, _reason = self.miasmic_bombardment_selection_is_valid(
            unit_ids,
            game=game,
            battle_round=round_value,
        )
        if not valid:
            return []

        selected_ids = sorted({str(uid or "").strip() for uid in list(unit_ids or []) if str(uid or "").strip()})
        max_units = int(self._miasmic_bombardment_max_units(game=game) or 0)
        candidates_by_id = {
            str(get_entity_id(unit) or ""): unit
            for unit in list(self._collect_miasmic_bombardment_candidates(game=game) or [])
            if str(get_entity_id(unit) or "")
        }

        self._clear_miasmic_bombardment_marks(game=game)
        owner = getattr(self.army, "player", None) if self.army is not None else None
        owner_id = str(getattr(owner, "id", "") or "")
        applied_ids: list[str] = []
        for uid in list(selected_ids)[: max(0, int(max_units))]:
            unit = candidates_by_id.get(str(uid))
            if unit is None:
                continue
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            sr["miasmic_bombardment_active"] = True
            sr["miasmic_bombardment_owner"] = owner_id
            sr["miasmic_bombardment_round"] = int(round_value)
            sr["miasmic_bombardment_source"] = self._MIASMIC_BOMBARDMENT_SOURCE
            unit.special_rules = sr
            applied_ids.append(str(uid))

        self.miasmic_bombardment_resolved_round = int(round_value)
        return applied_ids

    def build_miasmic_bombardment_request(self, *, game=None, player=None, battle_round=None):
        if not self.is_mortarions_hammer():
            return None
        if game is None or player is None:
            return None
        if not bool(getattr(game, "is_authoritative", True)):
            return None
        round_value = self._resolve_battle_round(game=game, battle_round=battle_round)
        if round_value is None:
            return None
        if (
            self.miasmic_bombardment_resolved_round is not None
            and int(self.miasmic_bombardment_resolved_round) == int(round_value)
        ):
            return None

        army_id = str(get_entity_id(self.army) or "") if self.army is not None else ""
        if self._pending_miasmic_bombardment_request(game, army_id=army_id, battle_round=int(round_value)):
            return None

        self._clear_miasmic_bombardment_marks(game=game, keep_round=int(round_value))
        candidates = list(self._collect_miasmic_bombardment_candidates(game=game) or [])
        candidate_ids = sorted(
            {str(get_entity_id(unit) or "") for unit in candidates if str(get_entity_id(unit) or "")}
        )
        max_units = min(
            int(self._miasmic_bombardment_max_units(game=game) or 0),
            len(candidate_ids),
        )
        if max_units <= 0 or not candidate_ids:
            self.miasmic_bombardment_resolved_round = int(round_value)
            return None

        from ..engine.decision_kinds import DECISION_SELECT_REALM_OF_CHAOS_UNITS
        from ..engine.decisions import DecisionOption, DecisionRequest

        request = DecisionRequest.create(
            DECISION_SELECT_REALM_OF_CHAOS_UNITS,
            "Miasmic Bombardment: select enemy units to become Afflicted.",
            player_id=getattr(player, "id", None),
            options=[
                DecisionOption.create("Confirm", payload={"action": "confirm"}),
                DecisionOption.create("None", payload={"action": "skip", "skip": True}),
            ],
            context={
                "ability": "miasmic_bombardment",
                "ability_name": self._MIASMIC_BOMBARDMENT_SOURCE,
                "army_id": army_id,
                "battle_round": int(round_value),
                "max_units": int(max_units),
                "allowed_unit_ids": list(candidate_ids),
                "optional": True,
                "title": self._MIASMIC_BOMBARDMENT_SOURCE,
                "subtitle": f"Select up to {int(max_units)} enemy unit(s) more than 12\" away.",
                "instruction": "Selected units are Afflicted until end of battle round.",
                "skip_label": "None (do not select units)",
            },
        )
        if hasattr(game, "request_decision"):
            game.request_decision(request)
        return request

    def _unit_in_army(self, unit) -> bool:
        if unit is None or self.army is None:
            return False
        return unit.get_parent_army() is self.army

    def _unit_is_death_guard(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword_or_faction(unit, "DEATH GUARD", faction_id=self.faction_id)

    def _unit_is_plague_legions(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_has_keyword(unit, "PLAGUE LEGIONS")

    @staticmethod
    def _unit_points(unit) -> int:
        if unit is None:
            return 0
        get_cost = getattr(unit, "get_unit_cost", None)
        if callable(get_cost):
            try:
                return int(get_cost() or 0)
            except (TypeError, ValueError, AttributeError):
                return 0
        try:
            return int(getattr(unit, "points", 0) or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _tallyband_summoners_plague_legions_points_cap(points_limit: int) -> tuple[int, str]:
        if points_limit <= 1000:
            return 500, "Incursion"
        if points_limit <= 2000:
            return 1000, "Strike Force"
        return 1500, "Onslaught"

    def _unit_is_reverberant_rancidity_eligible(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_in_army(unit):
            return False
        return self._unit_eligible_for_deadly_vectors(unit)

    def _reverberant_rancidity_has_nearby_unit(self, source_unit, *, keyword: str) -> bool:
        if source_unit is None or not keyword:
            return False
        if not self._unit_is_reverberant_rancidity_eligible(source_unit):
            return False
        from ..utility import aura_utils as _aura_utils

        for root in self._iter_unique_attached_roots():
            if root is None or root is source_unit:
                continue
            if not self._unit_is_reverberant_rancidity_eligible(root):
                continue
            if not self._unit_has_keyword(root, keyword):
                continue
            if _aura_utils.unit_within_range_of_unit(
                source_unit,
                root,
                float(self._REVERBERANT_RANCIDITY_RANGE),
                use_attached_aggregate=True,
            ):
                return True
        return False

    def reverberant_rancidity_grants_nurgles_gift_source(self, unit, *, game=None, game_map=None) -> bool:
        del game
        del game_map
        if not self.is_tallyband_summoners():
            return False
        if unit is None:
            return False
        root = unit.get_attached_unit_root()
        if root is None:
            return False
        if not self._unit_is_plague_legions(root):
            return False
        return self._reverberant_rancidity_has_nearby_unit(root, keyword="DEATH GUARD")

    def reverberant_rancidity_contagion_range_bonus_for_unit(self, unit, *, game=None, game_map=None) -> float:
        del game
        del game_map
        if not self.is_tallyband_summoners():
            return 0.0
        if unit is None:
            return 0.0
        root = unit.get_attached_unit_root()
        if root is None:
            return 0.0
        if not self._unit_is_death_guard(root):
            return 0.0
        if not self._reverberant_rancidity_has_nearby_unit(root, keyword="PLAGUE LEGIONS"):
            return 0.0
        return float(self._REVERBERANT_RANCIDITY_CONTAGION_BONUS)

    def _iter_unique_attached_roots(self):
        if self.army is None:
            return
        seen: set[str] = set()
        for unit in list(getattr(self.army, "units", []) or []):
            root = unit.get_attached_unit_root()
            uid = get_entity_id(root)
            if uid in seen:
                continue
            seen.add(uid)
            yield root

    @staticmethod
    def _enemy_root_sort_key(unit) -> str:
        return str(get_entity_id(unit) or "")

    def _iter_unique_enemy_roots(self, enemy_army):
        if enemy_army is None:
            return []
        roots = []
        seen: set[str] = set()
        for unit in list(getattr(enemy_army, "units", []) or []):
            if unit is None:
                continue
            root = unit.get_attached_unit_root()
            uid = str(get_entity_id(root) or "")
            if uid in seen:
                continue
            seen.add(uid)
            roots.append(root)
        roots.sort(key=self._enemy_root_sort_key)
        return roots

    def _unit_eligible_for_deadly_vectors(self, unit) -> bool:
        if unit is None:
            return False
        if not bool(getattr(unit, "deployed", False)):
            return False
        if not bool(unit.is_alive()):
            return False
        if bool(getattr(unit, "is_embarked", False)):
            return False
        if bool(unit.is_in_reserves()):
            return False
        return True

    def _unit_is_verminous_haze_eligible(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_in_army(unit):
            return False
        if not self._unit_is_death_guard(unit):
            return False
        if not self._unit_has_keyword(unit, "INFANTRY"):
            return False
        if self._unit_has_keyword(unit, "POXWALKERS"):
            return False
        if bool(getattr(unit, "is_embarked", False)) or bool(getattr(unit, "embarked_in", None)):
            return False
        return True

    def verminous_haze_applies_to_unit(self, unit) -> bool:
        if not self.is_flyblown_host():
            return False
        return self._unit_is_verminous_haze_eligible(unit)

    def verminous_haze_scout_distance_for_unit(self, unit) -> float:
        if not self.verminous_haze_applies_to_unit(unit):
            return 0.0
        return float(self._VERMINOUS_HAZE_SCOUT_DISTANCE)

    def resolve_deadly_vectors(self, *, game=None, opponent_player=None) -> list[dict]:
        if not self.is_death_lords_chosen():
            return []
        if game is None or opponent_player is None:
            return []
        if not bool(getattr(game, "is_authoritative", True)):
            return []
        opponent_army = getattr(opponent_player, "army", None)
        if opponent_army is None or opponent_army is self.army:
            return []
        game_map = getattr(game, "map", None)
        if game_map is None:
            return []

        outcomes: list[dict] = []
        for unit in self._iter_unique_enemy_roots(opponent_army):
            if not self._unit_eligible_for_deadly_vectors(unit):
                continue
            afflicted = NurglesGiftManager.get_afflicted_plague_for_unit(unit, game=game, game_map=game_map)
            if afflicted is None:
                continue
            roll_2d6 = int(get_roll("2D6") or 0)
            modifier = -1 if bool(unit.is_below_half_strength()) else 0
            total = int(roll_2d6 + modifier)
            mortal_wounds = 0
            if total <= 6:
                mortal_wounds = int(get_roll("D3") or 0)
                if mortal_wounds > 0:
                    unit._apply_mortal_wounds_to_unit(unit, int(mortal_wounds), game_map=game_map)
            outcomes.append(
                {
                    "unit_id": str(get_entity_id(unit) or ""),
                    "roll_2d6": int(roll_2d6),
                    "modifier": int(modifier),
                    "total": int(total),
                    "mortal_wounds": int(max(0, mortal_wounds)),
                }
            )
        return outcomes

    def _unit_eligible_for_worldblight(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_in_army(unit):
            return False
        if not self._unit_is_death_guard(unit):
            return False
        if not unit.is_alive():
            return False
        if not bool(getattr(unit, "deployed", False)):
            return False
        if unit.is_battle_shocked():
            return False
        return True

    def _attached_unit_has_arch_contaminator(self, unit) -> bool:
        if unit is None:
            return False
        root = unit.get_attached_unit_root()
        members = list(root.get_attached_unit_members() or [])
        for member in members:
            sr = getattr(member, "special_rules", None)
            if isinstance(sr, dict) and sr.get("enhancement_arch_contaminator"):
                return True
        return False

    def _root_within_controlled_objective(self, root, game) -> bool:
        if root is None or game is None:
            return False
        game_map = getattr(game, "map", None)
        if game_map is None:
            return False
        player = getattr(self.army, "player", None)
        if player is None:
            return False
        objectives = list(getattr(game_map, "objectives", []) or [])
        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            loc.update_control(game)
            if getattr(loc, "controlling_player", None) is not player:
                continue
            if root.is_within_objective_range(loc):
                return True
        return False

    def arch_contaminator_reroll_wounds(self, unit, *, game=None) -> bool:
        if not self.is_virulent_vectorium():
            return False
        if unit is None or game is None:
            return False
        root = unit.get_attached_unit_root()
        if not self._unit_in_army(root):
            return False
        if not self._unit_is_death_guard(root):
            return False
        if not root.is_alive() or not bool(getattr(root, "deployed", False)):
            return False
        if not self._attached_unit_has_arch_contaminator(root):
            return False
        return self._root_within_controlled_objective(root, game)

    def on_command_phase_end(self, *, game=None, player=None) -> None:
        if not self.is_virulent_vectorium():
            return
        if game is None or player is None:
            return
        if getattr(player, "army", None) is not self.army:
            return
        game_map = getattr(game, "map", None)
        if game_map is None:
            return
        objectives = list(getattr(game_map, "objectives", []) or [])
        if not objectives:
            return

        # Ensure control state is up to date before applying sticky effects.
        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            loc.update_control(game)

        for obj in objectives:
            loc = getattr(obj, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            if getattr(loc, "controlling_player", None) is not player:
                continue

            has_eligible_unit = False
            for root in self._iter_unique_attached_roots():
                if not self._unit_eligible_for_worldblight(root):
                    continue
                if root.is_within_objective_range(loc):
                    has_eligible_unit = True
                    break
            if not has_eligible_unit:
                continue

            loc.set_sticky_control(player, source=self._WORLD_BLIGHT_SOURCE)
            loc.worldblight_controller = player
            loc.worldblight_source = self._WORLD_BLIGHT_SOURCE

    def validate_detachment_rules(self) -> list[str]:
        errors: list[str] = []
        if not self.is_tallyband_summoners():
            return errors
        if self.army is None:
            return errors

        points_limit = int(getattr(self.army, "points_limit", 0) or 0)
        cap, size_label = self._tallyband_summoners_plague_legions_points_cap(points_limit)
        plague_legions_points = 0
        for unit in list(getattr(self.army, "units", []) or []):
            if unit is None:
                continue
            if not self._unit_is_plague_legions(unit):
                continue
            plague_legions_points += self._unit_points(unit)
        if plague_legions_points > cap:
            errors.append(
                f"Tallyband Summoners ({self._REVERBERANT_RANCIDITY_SOURCE}): "
                f"PLAGUE LEGIONS points ({plague_legions_points}) exceed the {size_label} cap of {cap}."
            )

        warlord = getattr(self.army, "warlord", None)
        if warlord is None:
            for unit in list(getattr(self.army, "units", []) or []):
                if bool(getattr(unit, "is_warlord", False)):
                    warlord = unit
                    break
        if warlord is not None and self._unit_is_plague_legions(warlord):
            errors.append(
                f"Tallyband Summoners ({self._REVERBERANT_RANCIDITY_SOURCE}): "
                "PLAGUE LEGIONS models cannot be your WARLORD."
            )
        return errors
