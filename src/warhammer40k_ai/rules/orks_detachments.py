from __future__ import annotations

import re

from .detachment_manager import DetachmentManagerBase
from ..utility.dice import get_roll
from ..utility.entity_ids import get_entity_id


class OrksDetachmentManager(DetachmentManagerBase):
    faction_id = "ORK"
    _SECOND_WAAAGH_NAMED_UNITS = ("nobz", "meganobz")
    _GREEN_TIDE_BOYZ_NAMED_UNITS = ("boyz",)
    _GREEN_TIDE_MOB_MENTALITY_SOURCE = "Mob Mentality"
    _KULT_OF_SPEED_SPEED_FREEKS_KEYWORD = "SPEED FREEKS"
    _KULT_OF_SPEED_ADRENALINE_JUNKIES_SOURCE = "Adrenaline Junkies"
    _SPEEDWAAAGH_TURBO_BOOSTAS_ABILITY = "orks_speedwaaagh_turbo_boostas"
    _SPEEDWAAAGH_TURBO_BOOSTAS_SOURCE = "Turbo Boostas"
    _SPEEDWAAAGH_TURBO_BOOSTAS_MOVE_CHARACTERISTIC = 24
    _SPEEDWAAAGH_TRUKK_KEYWORD = "TRUKK"
    _BLITZ_BRIGADE_EAGER_SOURCE = "Eager for the Fight"
    _MORE_DAKKA_QUALIFYING_KEYWORDS = ("INFANTRY", "WALKER")
    _MORE_DAKKA_SOURCE = "Dakka! Dakka! Dakka!"
    _WAZDAKKA_GUTSMEK_NAMED_UNITS = ("wazdakka gutsmek",)
    _WAZDAKKA_WARBIKERS_NAMED_UNITS = ("warbikers",)
    _TAKTIKAL_BRIGADE_STORMBOYZ_NAMED_UNITS = ("stormboyz",)
    _TAKTIKAL_BRIGADE_TAKTIK_GET_STUCK_IN = "get_stuck_in"
    _TAKTIKAL_BRIGADE_TAKTIK_GET_ON_WIV_IT = "get_on_wiv_it"
    _TAKTIKAL_BRIGADE_TAKTIK_SNEAKY_STALKIN = "sneaky_stalkin"
    _TAKTIKAL_BRIGADE_TAKTIK_SHOOTA_DRILLS = "shoota_drills"
    _TAKTIKAL_BRIGADE_TAKTIKS = (
        _TAKTIKAL_BRIGADE_TAKTIK_GET_STUCK_IN,
        _TAKTIKAL_BRIGADE_TAKTIK_GET_ON_WIV_IT,
        _TAKTIKAL_BRIGADE_TAKTIK_SNEAKY_STALKIN,
        _TAKTIKAL_BRIGADE_TAKTIK_SHOOTA_DRILLS,
    )
    _TAKTIKAL_BRIGADE_TAKTIK_LABELS = {
        _TAKTIKAL_BRIGADE_TAKTIK_GET_STUCK_IN: "Get Stuck In",
        _TAKTIKAL_BRIGADE_TAKTIK_GET_ON_WIV_IT: "Get On Wiv It",
        _TAKTIKAL_BRIGADE_TAKTIK_SNEAKY_STALKIN: "Sneaky Stalkin'",
        _TAKTIKAL_BRIGADE_TAKTIK_SHOOTA_DRILLS: "Shoota Drills",
    }
    _TAKTIKAL_BRIGADE_SOURCE = "Lissen 'Ere"
    _TAKTIKAL_BRIGADE_RANGE = 6.0
    _DA_BIG_HUNT_PREY_KEYWORDS = ("MONSTER", "VEHICLE", "CHARACTER")
    _HERE_BE_LOOT_QUALIFYING_KEYWORDS = ("INFANTRY", "MOUNTED", "WALKER")
    _DREAD_MOB_BUTTON_SUSTAINED = "SUSTAINED_HITS_1"
    _DREAD_MOB_BUTTON_LETHAL = "LETHAL_HITS"
    _DREAD_MOB_BUTTON_CRIT_AP = "CRITICAL_WOUND_AP_2"
    _DREAD_MOB_BUTTON_EFFECTS = (
        _DREAD_MOB_BUTTON_SUSTAINED,
        _DREAD_MOB_BUTTON_LETHAL,
        _DREAD_MOB_BUTTON_CRIT_AP,
    )
    _DREAD_MOB_BUTTON_LABELS = {
        _DREAD_MOB_BUTTON_SUSTAINED: "Sustained Hits 1",
        _DREAD_MOB_BUTTON_LETHAL: "Lethal Hits",
        _DREAD_MOB_BUTTON_CRIT_AP: "Critical Wound AP +2",
    }
    _NEXT_COMMAND_PHASE_ANY_SOURCE_PREFIXES = (
        "stratagem:orks_next_command_phase:dats_ours:",
    )
    _NEXT_COMMAND_PHASE_OWNER_SOURCE_PREFIXES = (
        "stratagem:orks_next_command_phase:huge_show_offs:",
    )

    def __init__(self, army=None):
        super().__init__(army)
        self.da_big_hunt_prey_unit_id: str = ""
        self.da_big_hunt_prey_turn: int = 0
        self.da_big_hunt_prey_owner_id: str = ""
        self.freebooter_loot_objective_id: str = ""
        self.freebooter_loot_battle_round: int = 0
        self.freebooter_loot_turn_owner_id: str = ""
        self._taktikal_brigade_issued_by_model_round: dict[str, int] = {}
        self._taktikal_brigade_issued_to_unit_round: dict[str, int] = {}

    def is_war_horde(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("War Horde")

    def is_bully_boyz(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Bully Boyz")

    def is_da_big_hunt(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Da Big Hunt")

    def is_dread_mob(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Dread Mob")

    def is_freebooter_krew(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Freebooter Krew")

    def is_green_tide(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Green Tide")

    def is_kult_of_speed(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Kult of Speed")

    def is_speedwaaagh(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Speedwaaagh!")

    def is_blitz_brigade(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Blitz Brigade")

    def is_more_dakka(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("More Dakka!")

    def is_taktikal_brigade(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Taktikal Brigade")

    @staticmethod
    def _normalize_name(text: str) -> str:
        value = re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower())
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _phase_key_from_game(game) -> str:
        if game is None:
            return ""
        phase = getattr(game, "phase", None)
        return str(getattr(phase, "name", "") or phase or "").strip().upper()

    @staticmethod
    def _unit_is_alive(unit) -> bool:
        if unit is None:
            return False
        is_alive_fn = getattr(unit, "is_alive", None)
        if callable(is_alive_fn):
            return bool(is_alive_fn())
        return bool(getattr(unit, "is_alive", True))

    @staticmethod
    def _model_is_alive(model) -> bool:
        if model is None:
            return False
        is_alive_val = getattr(model, "is_alive", None)
        if callable(is_alive_val):
            return bool(is_alive_val())
        return bool(is_alive_val)

    @staticmethod
    def _unit_is_deployed_on_battlefield(unit) -> bool:
        if unit is None:
            return False
        if not bool(getattr(unit, "deployed", True)):
            return False
        status = str(getattr(unit, "reserve_status", "deployed") or "deployed").strip().lower()
        if status != "deployed":
            return False
        in_reserves_fn = getattr(unit, "is_in_reserves", None)
        if callable(in_reserves_fn):
            return not bool(in_reserves_fn())
        return True

    @staticmethod
    def _unit_is_battle_shocked(unit) -> bool:
        if unit is None:
            return False
        fn = getattr(unit, "is_battle_shocked", None)
        if callable(fn):
            return bool(fn())
        return bool(getattr(unit, "battle_shocked", False))

    def _transport_is_on_battlefield(self, transport_unit) -> bool:
        if transport_unit is None:
            return False
        if not self._unit_is_alive(transport_unit):
            return False
        return self._unit_is_deployed_on_battlefield(transport_unit)

    def _unit_is_on_battlefield_or_embarked(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_is_alive(unit):
            return False
        embarked_in = getattr(unit, "embarked_in", None)
        if embarked_in is not None:
            return self._transport_is_on_battlefield(embarked_in)
        return self._unit_is_deployed_on_battlefield(unit)

    def _unit_contains_keyword(self, unit, keyword: str) -> bool:
        if unit is None:
            return False
        if self._unit_has_keyword(unit, keyword):
            return True
        members_fn = getattr(unit, "get_attached_unit_members", None)
        if not callable(members_fn):
            return False
        members = list(members_fn() or [])
        for member in members:
            if self._unit_has_keyword(member, keyword):
                return True
        return False

    def _unit_contains_any_keyword(self, unit, keywords: tuple[str, ...]) -> bool:
        for keyword in keywords:
            if self._unit_contains_keyword(unit, keyword):
                return True
        return False

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

    @staticmethod
    def _model_id(model) -> str:
        if model is None:
            return ""
        return str(get_entity_id(model) or "")

    def _attached_member_units(self, unit) -> list:
        root = self._unit_root(unit)
        if root is None:
            return []
        members_fn = getattr(root, "get_attached_unit_members", None)
        members = list(members_fn() or []) if callable(members_fn) else [root]
        if not members:
            members = [root]
        members.sort(key=lambda member: str(get_entity_id(member) or ""))
        return members

    def _unit_has_active_enhancement_flag(self, unit, *, flag_key: str) -> bool:
        if unit is None:
            return False
        sr = getattr(unit, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not bool(sr.get(flag_key)):
            return False
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
        if bearer_id:
            for model in list(getattr(unit, "models", []) or []):
                if self._model_id(model) != bearer_id:
                    continue
                return self._model_is_alive(model)
            return False
        get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
        if callable(get_bearer):
            return self._model_is_alive(get_bearer())
        for model in list(getattr(unit, "models", []) or []):
            if self._model_is_alive(model):
                return True
        return False

    def _collect_active_enhancement_source_units(self, unit, *, flag_key: str) -> list:
        root = self._unit_root(unit)
        if root is None or not self._unit_belongs_to_army(root):
            return []
        sources = []
        for member in self._attached_member_units(root):
            if self._unit_has_active_enhancement_flag(member, flag_key=flag_key):
                sources.append(member)
        sources.sort(key=lambda member: str(get_entity_id(member) or ""))
        return sources

    @staticmethod
    def _enhancement_source_name(unit, *, source_key: str, default: str) -> str:
        sr = getattr(unit, "special_rules", None)
        if isinstance(sr, dict):
            source = str(sr.get(source_key, "") or "").strip()
            if source:
                return source
        return str(default or "").strip() or default

    def _model_is_active_enhancement_bearer(self, model, *, flag_key: str) -> bool:
        if model is None:
            return False
        source_unit = getattr(model, "parent_unit", None)
        if source_unit is None:
            return False
        sr = getattr(source_unit, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(flag_key)):
            return False
        model_id = self._model_id(model)
        if not model_id:
            return False
        bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "")
        if bearer_id:
            return bearer_id == model_id and self._model_is_alive(model)
        return self._model_is_alive(model)

    def _taktikal_issue_range_for_model(self, issuer_model) -> float:
        base_range = float(self._TAKTIKAL_BRIGADE_RANGE)
        if issuer_model is None:
            return base_range
        if not self._model_is_active_enhancement_bearer(issuer_model, flag_key="enhancement_gob_boomer"):
            return base_range
        source_unit = getattr(issuer_model, "parent_unit", None)
        sr = getattr(source_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return base_range
        try:
            bonus_range = float(sr.get("enhancement_taktikal_issue_range", 18.0) or 18.0)
        except (TypeError, ValueError):
            bonus_range = 18.0
        return float(max(base_range, bonus_range))

    def _unit_is_enemy_of_player(self, unit, player) -> bool:
        if unit is None or player is None:
            return False
        root = self._unit_root(unit)
        get_parent_army = getattr(root, "get_parent_army", None) if root is not None else None
        if callable(get_parent_army):
            unit_army = get_parent_army()
        else:
            unit_army = getattr(root, "parent_army", None)
        unit_player = getattr(unit_army, "player", None) if unit_army is not None else None
        return unit_player is not None and unit_player is not player

    def _unit_is_on_battlefield(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_is_alive(unit):
            return False
        if not self._unit_is_deployed_on_battlefield(unit):
            return False
        if bool(getattr(unit, "is_embarked", False)):
            return False
        if getattr(unit, "embarked_in", None) is not None:
            return False
        return True

    def _unit_name_matches_any(self, unit, names: tuple[str, ...]) -> bool:
        if unit is None:
            return False
        unit_name = self._normalize_name(getattr(unit, "name", ""))
        if unit_name in names:
            return True
        members_fn = getattr(unit, "get_attached_unit_members", None)
        if not callable(members_fn):
            return False
        members = list(members_fn() or [])
        for member in members:
            member_name = self._normalize_name(getattr(member, "name", ""))
            if member_name in names:
                return True
        return False

    def _unit_total_model_count(self, unit) -> int:
        root = self._unit_root(unit)
        if root is None:
            return 0
        members_fn = getattr(root, "get_attached_unit_members", None)
        if callable(members_fn):
            members = list(members_fn() or [])
        else:
            members = [root]
        total = 0
        for member in members:
            total += len(list(getattr(member, "models", []) or []))
        return int(total)

    def _green_tide_effective_model_count(self, unit, *, scope: str, game=None) -> int:
        root = self._unit_root(unit)
        if root is None:
            return 0
        fn = getattr(root, "orks_effective_model_count_for_evaluation", None)
        if callable(fn):
            if game is None:
                army_player = getattr(self.army, "player", None) if self.army is not None else None
                game = getattr(army_player, "game", None) if army_player is not None else None
            game_map = getattr(game, "map", None) if game is not None else None
            return int(fn(scope, game=game, game_map=game_map) or 0)
        return int(self._unit_total_model_count(root) or 0)

    def green_tide_mob_mentality_invulnerable_save(self, target_model, *, attack_type: str = "") -> tuple[int, str]:
        del attack_type
        if not self.is_green_tide():
            return 0, ""
        if target_model is None:
            return 0, ""
        target_unit = getattr(target_model, "parent_unit", None)
        root = self._unit_root(target_unit)
        if root is None or not self._unit_belongs_to_army(root):
            return 0, ""
        if not self._unit_contains_keyword(root, "BOYZ"):
            if not self._unit_name_matches_any(root, self._GREEN_TIDE_BOYZ_NAMED_UNITS):
                return 0, ""
        model_count = self._green_tide_effective_model_count(root, scope="detachment")
        if model_count >= 10:
            return 5, self._GREEN_TIDE_MOB_MENTALITY_SOURCE
        if model_count > 0:
            return 6, self._GREEN_TIDE_MOB_MENTALITY_SOURCE
        return 0, ""

    def _green_tide_bloodthirsty_belligerence_source_unit(self, unit):
        root = self._unit_root(unit)
        if root is None or not self._unit_belongs_to_army(root):
            return None
        leaders = list(getattr(root, "attached_leaders", []) or [])
        if not leaders:
            return None
        leader_ids = {str(get_entity_id(leader) or "") for leader in leaders}
        sources = self._collect_active_enhancement_source_units(
            root,
            flag_key="enhancement_green_tide_bloodthirsty_belligerence",
        )
        for source_unit in sources:
            source_id = str(get_entity_id(source_unit) or "")
            if source_unit in leaders or source_id in leader_ids:
                return source_unit
        return None

    def green_tide_bloodthirsty_belligerence_reroll_advance_applies(self, unit, *, game=None) -> bool:
        del game
        if not self.is_green_tide():
            return False
        return self._green_tide_bloodthirsty_belligerence_source_unit(unit) is not None

    def green_tide_bloodthirsty_belligerence_reroll_charge_applies(self, unit, *, game=None) -> bool:
        if not self.green_tide_bloodthirsty_belligerence_reroll_advance_applies(unit, game=game):
            return False
        return bool(
            self._green_tide_effective_model_count(
                unit,
                scope="enhancement",
                game=game,
            )
            >= 10
        )

    def green_tide_ferocious_show_off_melee_strength_bonus(
        self,
        attacker_model,
        *,
        attack_type: str = "",
        game=None,
    ) -> tuple[int, str]:
        if str(attack_type or "").strip().lower() not in ("", "melee"):
            return 0, ""
        if not self.is_green_tide():
            return 0, ""
        if attacker_model is None:
            return 0, ""
        if not self._model_is_active_enhancement_bearer(
            attacker_model,
            flag_key="enhancement_green_tide_ferocious_show_off",
        ):
            return 0, ""
        source_unit = getattr(attacker_model, "parent_unit", None)
        root = self._unit_root(source_unit)
        if root is None or not self._unit_belongs_to_army(root):
            return 0, ""
        sr = getattr(source_unit, "special_rules", None)
        if not isinstance(sr, dict):
            return 0, ""
        try:
            base_bonus = int(sr.get("enhancement_green_tide_ferocious_show_off_base_bonus", 1) or 1)
        except (TypeError, ValueError):
            base_bonus = 1
        try:
            enhanced_bonus = int(sr.get("enhancement_green_tide_ferocious_show_off_enhanced_bonus", 3) or 3)
        except (TypeError, ValueError):
            enhanced_bonus = 3
        effective_count = self._green_tide_effective_model_count(root, scope="enhancement", game=game)
        bonus = int(enhanced_bonus if int(effective_count or 0) >= 10 else base_bonus)
        source_name = self._enhancement_source_name(
            source_unit,
            source_key="enhancement_green_tide_ferocious_show_off_source",
            default="Ferocious Show Off",
        )
        return int(max(0, bonus)), source_name

    def kult_of_speed_adrenaline_junkies_applies(self, unit) -> bool:
        if not self.is_kult_of_speed():
            return False
        if unit is None:
            return False
        root = self._unit_root(unit)
        if root is None or not self._unit_belongs_to_army(root):
            return False
        if not self._unit_contains_keyword(root, self._KULT_OF_SPEED_SPEED_FREEKS_KEYWORD):
            return False
        return True

    def speedwaaagh_turbo_boostas_eligible(self, unit) -> bool:
        if not self.is_speedwaaagh():
            return False
        if unit is None:
            return False
        root = self._unit_root(unit)
        if root is None or not self._unit_belongs_to_army(root):
            return False
        if self._unit_contains_keyword(root, "AIRCRAFT"):
            return False
        return bool(
            self._unit_contains_keyword(root, self._KULT_OF_SPEED_SPEED_FREEKS_KEYWORD)
            or self._unit_contains_keyword(root, self._SPEEDWAAAGH_TRUKK_KEYWORD)
        )

    def queue_speedwaaagh_turbo_boostas_choice(self, unit, *, game=None, player=None):
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return None
        if not self.speedwaaagh_turbo_boostas_eligible(unit):
            return None
        root = self._unit_root(unit)
        if root is None:
            return None
        unit_id = self._unit_root_id(root)
        if not unit_id:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != "CONFIRM_YES_NO":
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != self._SPEEDWAAAGH_TURBO_BOOSTAS_ABILITY:
                    continue
                if str(ctx.get("unit_id", "") or "") == unit_id:
                    return req
        if player is None and self.army is not None:
            player = getattr(self.army, "player", None)
        from ..engine.decision_kinds import DECISION_CONFIRM_YES_NO
        from ..engine.decisions import DecisionOption, DecisionRequest

        options = [
            DecisionOption.create(
                "Use Turbo Boostas",
                payload={
                    "choice": True,
                    "unit_id": unit_id,
                    "ability": self._SPEEDWAAAGH_TURBO_BOOSTAS_ABILITY,
                    "summary": 'Do not roll; Move characteristic becomes 24", move straight with no pivot, gain Assault, and cannot charge.',
                },
            ),
            DecisionOption.create(
                "Advance normally",
                payload={
                    "choice": False,
                    "unit_id": unit_id,
                    "ability": self._SPEEDWAAAGH_TURBO_BOOSTAS_ABILITY,
                    "summary": "Make a normal Advance roll.",
                },
            ),
        ]
        request = DecisionRequest.create(
            DECISION_CONFIRM_YES_NO,
            f"Use Turbo Boostas for {getattr(root, 'name', 'Unit')}?",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": self._SPEEDWAAAGH_TURBO_BOOSTAS_ABILITY,
                "ability_name": self._SPEEDWAAAGH_TURBO_BOOSTAS_SOURCE,
                "unit_id": unit_id,
                "movement_type": "advance",
                "optional": True,
            },
        )
        request_decision = getattr(game, "request_decision", None)
        if callable(request_decision):
            request_decision(request)
        return request

    def apply_speedwaaagh_turbo_boostas_choice(self, unit, *, use_turbo: bool, game=None, player=None) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        if not self.speedwaaagh_turbo_boostas_eligible(root):
            return False
        if game is None and self.army is not None:
            player_obj = getattr(self.army, "player", None)
            game = getattr(player_obj, "game", None) if player_obj is not None else None
        if player is None and self.army is not None:
            player = getattr(self.army, "player", None)
        if player is None and game is not None:
            get_current = getattr(game, "get_current_player", None)
            player = get_current() if callable(get_current) else None
        owner_id = str(getattr(player, "id", "") or "").strip()
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            turn = 0
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr = dict(sr)
        effect_id = "detachment:speedwaaagh:turbo_boostas"
        sr["speedwaaagh_turbo_boostas_declined_turn_owner"] = owner_id
        sr["speedwaaagh_turbo_boostas_declined_turn"] = int(turn)
        advance_effects = [
            dict(entry)
            for entry in list(sr.get("advance_no_roll_effects", []) or [])
            if isinstance(entry, dict) and str(entry.get("tag", "") or "") != effect_id
        ]
        temp_effects = [
            dict(entry)
            for entry in list(sr.get("orks_temp_effects", []) or [])
            if isinstance(entry, dict) and str(entry.get("id", "") or "") != effect_id
        ]
        if use_turbo:
            sr["speedwaaagh_turbo_boostas_active"] = True
            sr["speedwaaagh_turbo_boostas_turn_owner"] = owner_id
            sr["speedwaaagh_turbo_boostas_turn"] = int(turn)
            sr["speedwaaagh_turbo_boostas_source"] = self._SPEEDWAAAGH_TURBO_BOOSTAS_SOURCE
            sr["speedwaaagh_turbo_boostas_move_characteristic"] = int(
                self._SPEEDWAAAGH_TURBO_BOOSTAS_MOVE_CHARACTERISTIC
            )
            sr["speedwaaagh_turbo_boostas_straight_line_only"] = True
            sr["speedwaaagh_turbo_boostas_no_pivot"] = True
            sr["speedwaaagh_turbo_boostas_no_charge"] = True
            sr["speedwaaagh_turbo_boostas_ranged_assault"] = True
            advance_effects.append(
                {
                    "tag": effect_id,
                    "source": self._SPEEDWAAAGH_TURBO_BOOSTAS_SOURCE,
                    "distance": 0,
                    "move_characteristic": int(self._SPEEDWAAAGH_TURBO_BOOSTAS_MOVE_CHARACTERISTIC),
                    "straight_line_only": True,
                    "no_pivot": True,
                    "expires_phase": "MOVEMENT_PHASE",
                }
            )
            temp_effects.append(
                {
                    "id": effect_id,
                    "detachment": "speedwaaagh",
                    "source": self._SPEEDWAAAGH_TURBO_BOOSTAS_SOURCE,
                    "effect": "keyword",
                    "attack_type": "ranged",
                    "keyword": "ASSAULT",
                    "expires_mode": "turn",
                    "turn_owner_id": owner_id,
                    "turn": int(turn),
                }
            )
            temp_effects.sort(key=lambda entry: str(entry.get("id", "") or ""))
            sr["orks_temp_effects"] = temp_effects
        else:
            for key in (
                "speedwaaagh_turbo_boostas_active",
                "speedwaaagh_turbo_boostas_turn_owner",
                "speedwaaagh_turbo_boostas_turn",
                "speedwaaagh_turbo_boostas_source",
                "speedwaaagh_turbo_boostas_move_characteristic",
                "speedwaaagh_turbo_boostas_straight_line_only",
                "speedwaaagh_turbo_boostas_no_pivot",
                "speedwaaagh_turbo_boostas_no_charge",
                "speedwaaagh_turbo_boostas_ranged_assault",
            ):
                sr.pop(key, None)
        if advance_effects:
            advance_effects.sort(key=lambda entry: str(entry.get("tag", "") or ""))
            sr["advance_no_roll_effects"] = advance_effects
        else:
            sr.pop("advance_no_roll_effects", None)
        if temp_effects:
            sr["orks_temp_effects"] = temp_effects
        else:
            sr.pop("orks_temp_effects", None)
        root.special_rules = sr
        round_state = getattr(root, "round_state", None)
        if round_state is not None:
            try:
                round_state.advance_roll = None
            except AttributeError:
                pass
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict):
            cache.clear()
        return True

    def speedwaaagh_turbo_boostas_active(self, unit, *, game=None) -> bool:
        root = self._unit_root(unit)
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("speedwaaagh_turbo_boostas_active")):
            return False
        if game is None and self.army is not None:
            player = getattr(self.army, "player", None)
            game = getattr(player, "game", None) if player is not None else None
        if game is None:
            return True
        owner_id = str(sr.get("speedwaaagh_turbo_boostas_turn_owner", "") or "").strip()
        if owner_id:
            get_current = getattr(game, "get_current_player", None)
            current = get_current() if callable(get_current) else None
            current_id = str(getattr(current, "id", "") or "").strip()
            if current_id and current_id != owner_id:
                return False
        try:
            effect_turn = int(sr.get("speedwaaagh_turbo_boostas_turn", 0) or 0)
            current_turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            return False
        if effect_turn and current_turn and effect_turn != current_turn:
            return False
        return True

    def speedwaaagh_turbo_boostas_can_shoot_after_advance(self, unit, profile=None, *, game=None) -> bool:
        if not self.speedwaaagh_turbo_boostas_active(unit, game=game):
            return False
        if profile is None:
            return True
        parent_wargear = getattr(profile, "parent_wargear", None)
        is_ranged_fn = getattr(parent_wargear, "is_ranged", None) if parent_wargear is not None else None
        return bool(callable(is_ranged_fn) and is_ranged_fn())

    def speedwaaagh_turbo_boostas_blocks_charge(self, unit, *, game=None) -> bool:
        if not self.speedwaaagh_turbo_boostas_active(unit, game=game):
            return False
        root = self._unit_root(unit)
        sr = getattr(root, "special_rules", None) if root is not None else None
        return bool(isinstance(sr, dict) and sr.get("speedwaaagh_turbo_boostas_no_charge"))

    def blitz_brigade_eager_for_the_fight_eligible(self, unit, *, transport_unit=None) -> bool:
        if not self.is_blitz_brigade():
            return False
        root = self._unit_root(unit)
        if root is None or not self._unit_belongs_to_army(root):
            return False
        if not self._unit_has_keyword_or_faction(root, "ORKS", faction_id=self.faction_id):
            return False
        transport_root = self._unit_root(transport_unit)
        if transport_root is None or not self._unit_belongs_to_army(transport_root):
            return False
        is_transport = bool(getattr(transport_root, "is_transport", False))
        return bool(is_transport or self._unit_contains_keyword(transport_root, "TRANSPORT"))

    def apply_blitz_brigade_eager_for_the_fight_on_disembark(
        self,
        unit,
        *,
        transport_unit=None,
        game=None,
        current_turn: int = 0,
    ) -> bool:
        if not self.blitz_brigade_eager_for_the_fight_eligible(unit, transport_unit=transport_unit):
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if game is None and self.army is not None:
            player_obj = getattr(self.army, "player", None)
            game = getattr(player_obj, "game", None) if player_obj is not None else None
        player = None
        if game is not None:
            get_current = getattr(game, "get_current_player", None)
            player = get_current() if callable(get_current) else None
        if player is None and self.army is not None:
            player = getattr(self.army, "player", None)
        owner_id = str(getattr(player, "id", "") or "").strip()
        try:
            turn = int(getattr(game, "turn", current_turn) or current_turn or 0)
        except (TypeError, ValueError):
            turn = int(current_turn or 0)

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        sr = dict(sr)
        effect_prefix = "detachment:blitz_brigade:eager_for_the_fight"
        temp_effects = [
            dict(entry)
            for entry in list(sr.get("orks_temp_effects", []) or [])
            if isinstance(entry, dict)
            and not str(entry.get("id", "") or "").startswith(effect_prefix)
        ]
        common = {
            "detachment": "blitz_brigade",
            "source": self._BLITZ_BRIGADE_EAGER_SOURCE,
            "expires_mode": "turn",
            "turn_owner_id": owner_id,
            "turn": int(turn),
        }
        temp_effects.extend(
            [
                {
                    **common,
                    "id": f"{effect_prefix}:advance",
                    "effect": "reroll_advance_roll",
                    "attack_type": "any",
                },
                {
                    **common,
                    "id": f"{effect_prefix}:charge",
                    "effect": "charge_reroll",
                    "attack_type": "any",
                },
            ]
        )
        temp_effects.sort(key=lambda entry: str(entry.get("id", "") or ""))
        sr["orks_temp_effects"] = temp_effects
        sr["blitz_brigade_eager_for_the_fight_active"] = True
        sr["blitz_brigade_eager_for_the_fight_turn_owner"] = owner_id
        sr["blitz_brigade_eager_for_the_fight_turn"] = int(turn)
        root.special_rules = sr
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict):
            cache.clear()
        return True

    def _more_dakka_unit_is_eligible(self, unit) -> bool:
        if not self.is_more_dakka():
            return False
        if unit is None:
            return False
        root = self._unit_root(unit)
        if root is None or not self._unit_belongs_to_army(root):
            return False
        if not self._unit_has_keyword_or_faction(root, "ORKS", faction_id=self.faction_id):
            return False
        if not self._unit_contains_any_keyword(root, self._MORE_DAKKA_QUALIFYING_KEYWORDS):
            return False
        return True

    def more_dakka_assault_applies(self, unit, *, attack_type: str = "", profile=None) -> bool:
        if not self._more_dakka_unit_is_eligible(unit):
            return False
        attack = str(attack_type or "").strip().lower()
        if attack and attack != "ranged":
            return False
        if profile is not None:
            parent_wargear = getattr(profile, "parent_wargear", None)
            is_ranged_fn = getattr(parent_wargear, "is_ranged", None) if parent_wargear is not None else None
            if callable(is_ranged_fn) and not bool(is_ranged_fn()):
                return False
        return True

    def more_dakka_sustained_hits_value(self, attacker_model, *, attack_type: str = "", game=None) -> int:
        if str(attack_type or "").strip().lower() not in ("", "ranged"):
            return 0
        attacker_unit = getattr(attacker_model, "parent_unit", None) if attacker_model is not None else None
        root = self._unit_root(attacker_unit)
        if not self._more_dakka_unit_is_eligible(root):
            return 0
        army = self.army
        if army is None:
            return 0
        waaagh_mgr = getattr(army, "waaagh", None)
        if waaagh_mgr is None:
            return 0
        if game is None:
            player = getattr(army, "player", None)
            game = getattr(player, "game", None) if player is not None else None
        unit_is_affected_fn = getattr(waaagh_mgr, "unit_is_affected", None)
        if not callable(unit_is_affected_fn):
            return 0
        if not bool(unit_is_affected_fn(root, game=game)):
            return 0
        phase_name = self._phase_key_from_game(game)
        if phase_name and phase_name != "SHOOTING_PHASE":
            return 0
        return 1

    def _unit_contains_warboss_model(self, unit) -> bool:
        if unit is None:
            return False
        if self._unit_contains_keyword(unit, "WARBOSS"):
            return True
        members_fn = getattr(unit, "get_attached_unit_members", None)
        members = list(members_fn() or []) if callable(members_fn) else [unit]
        for member in members:
            models = list(getattr(member, "models", []) or [])
            for model in models:
                keywords = list(getattr(model, "keywords", []) or [])
                for token in keywords:
                    if str(token or "").strip().upper() == "WARBOSS":
                        return True
        return False

    def can_call_second_waaagh(self, *, game=None, player=None) -> bool:
        if not self.is_bully_boyz():
            return False
        army = self.army
        if army is None:
            return False
        if player is not None:
            army_player = getattr(army, "player", None)
            if army_player is not None and army_player is not player:
                return False
        units = list(getattr(army, "units", []) or [])
        for unit in units:
            if unit is None:
                continue
            if not self._unit_contains_warboss_model(unit):
                continue
            if self._unit_is_on_battlefield_or_embarked(unit):
                return True
        return False

    def bully_boyz_second_waaagh_unit_applies(self, unit) -> bool:
        if not self.is_bully_boyz():
            return False
        if unit is None:
            return False
        if self._unit_contains_keyword(unit, "WARBOSS"):
            return True
        if self._unit_contains_keyword(unit, "NOBZ"):
            return True
        if self._unit_contains_keyword(unit, "MEGANOBZ"):
            return True
        return self._unit_name_matches_any(unit, self._SECOND_WAAAGH_NAMED_UNITS)

    @staticmethod
    def _model_has_keyword(model, keyword: str) -> bool:
        if model is None:
            return False
        token = str(keyword or "").strip().upper()
        if not token:
            return False
        keywords = [str(k or "").strip().upper() for k in list(getattr(model, "keywords", []) or [])]
        return token in set(keywords)

    def _unit_belongs_to_army(self, unit) -> bool:
        if unit is None:
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        get_parent_army = getattr(root, "get_parent_army", None)
        if callable(get_parent_army):
            return get_parent_army() is self.army
        return getattr(root, "parent_army", None) is self.army

    def _taktikal_label(self, taktik_key: str) -> str:
        return str(self._TAKTIKAL_BRIGADE_TAKTIK_LABELS.get(str(taktik_key or "").strip().lower(), "") or "")

    def _model_has_any_keyword(self, model, keywords: tuple[str, ...]) -> bool:
        for keyword in keywords:
            if self._model_has_keyword(model, keyword):
                return True
        return False

    def _model_is_taktikal_issuer(self, model) -> bool:
        if model is None:
            return False
        if self._model_has_any_keyword(model, ("MEK", "WARBOSS")):
            return True
        model_name = self._normalize_name(getattr(model, "name", ""))
        if model_name == "boss snikrot":
            return True
        parent_unit = getattr(model, "parent_unit", None)
        parent_name = self._normalize_name(getattr(parent_unit, "name", ""))
        return parent_name == "boss snikrot"

    def _model_is_meganobz(self, model) -> bool:
        if model is None:
            return False
        if self._model_has_keyword(model, "MEGANOBZ"):
            return True
        model_name = self._normalize_name(getattr(model, "name", ""))
        return "meganob" in model_name

    def _taktikal_current_battle_round(self, game=None) -> int:
        if game is None and self.army is not None:
            player = getattr(self.army, "player", None)
            game = getattr(player, "game", None) if player is not None else None
        if game is None:
            return 0
        try:
            return int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def _cleanup_taktikal_tracking_for_round(self, battle_round: int) -> None:
        current = int(battle_round or 0)
        if current <= 0:
            return
        self._taktikal_brigade_issued_by_model_round = {
            str(model_id): int(round_value)
            for model_id, round_value in dict(self._taktikal_brigade_issued_by_model_round or {}).items()
            if int(round_value or 0) >= current
        }
        self._taktikal_brigade_issued_to_unit_round = {
            str(unit_id): int(round_value)
            for unit_id, round_value in dict(self._taktikal_brigade_issued_to_unit_round or {}).items()
            if int(round_value or 0) >= current
        }

    def _taktikal_issuer_used_this_round(self, issuer_model, *, battle_round: int) -> bool:
        model_id = str(get_entity_id(issuer_model) or "")
        if not model_id:
            return False
        return int(self._taktikal_brigade_issued_by_model_round.get(model_id, 0) or 0) == int(battle_round or 0)

    def _taktikal_target_used_this_round(self, target_unit, *, battle_round: int) -> bool:
        unit_id = self._unit_root_id(target_unit)
        if not unit_id:
            return False
        return int(self._taktikal_brigade_issued_to_unit_round.get(unit_id, 0) or 0) == int(battle_round or 0)

    def _mark_taktikal_usage(
        self,
        issuer_model,
        target_unit,
        *,
        battle_round: int,
    ) -> None:
        model_id = str(get_entity_id(issuer_model) or "")
        unit_id = self._unit_root_id(target_unit)
        if model_id:
            self._taktikal_brigade_issued_by_model_round[model_id] = int(battle_round or 0)
        if unit_id:
            self._taktikal_brigade_issued_to_unit_round[unit_id] = int(battle_round or 0)

    def _collect_taktikal_issuer_models(self, *, unit=None) -> list:
        if not self.is_taktikal_brigade() or self.army is None:
            return []
        if unit is None:
            roots = []
            seen_root_ids: set[str] = set()
            for entry in list(getattr(self.army, "units", []) or []):
                root = self._unit_root(entry)
                if root is None:
                    continue
                rid = self._unit_root_id(root)
                if rid and rid in seen_root_ids:
                    continue
                if rid:
                    seen_root_ids.add(rid)
                roots.append(root)
        else:
            root = self._unit_root(unit)
            roots = [root] if root is not None else []
        issuers = []
        for root in roots:
            if root is None or not self._unit_belongs_to_army(root):
                continue
            if not self._unit_is_on_battlefield(root):
                continue
            members_fn = getattr(root, "get_attached_unit_members", None)
            members = list(members_fn() or []) if callable(members_fn) else [root]
            for member in members:
                for model in list(getattr(member, "models", []) or []):
                    if not self._model_is_alive(model):
                        continue
                    if not self._model_is_taktikal_issuer(model):
                        continue
                    issuers.append(model)
        issuers.sort(key=lambda model: str(get_entity_id(model) or ""))
        return issuers

    def _collect_taktikal_target_units_for_issuer(self, issuer_model, *, game=None) -> list:
        if issuer_model is None or self.army is None:
            return []
        issuer_unit = getattr(issuer_model, "parent_unit", None)
        issuer_root = self._unit_root(issuer_unit)
        if issuer_root is None or not self._unit_belongs_to_army(issuer_root):
            return []
        if not self._unit_is_on_battlefield(issuer_root):
            return []
        from ..utility.aura_utils import model_within_range_of_unit

        battle_round = self._taktikal_current_battle_round(game)
        issue_range = self._taktikal_issue_range_for_model(issuer_model)
        candidates = []
        seen_ids: set[str] = set()
        for candidate in list(getattr(self.army, "units", []) or []):
            root = self._unit_root(candidate)
            if root is None:
                continue
            rid = self._unit_root_id(root)
            if not rid or rid in seen_ids:
                continue
            seen_ids.add(rid)
            if not self._unit_belongs_to_army(root):
                continue
            if not self._unit_is_on_battlefield(root):
                continue
            if self._unit_is_battle_shocked(root):
                continue
            if not self._unit_has_keyword_or_faction(root, "ORKS", faction_id=self.faction_id):
                continue
            if battle_round and self._taktikal_target_used_this_round(root, battle_round=battle_round):
                continue
            if not model_within_range_of_unit(
                issuer_model,
                root,
                float(issue_range),
                use_attached_aggregate=True,
            ):
                continue
            candidates.append(root)
        candidates.sort(key=lambda root: (self._normalize_name(getattr(root, "name", "")), self._unit_root_id(root)))
        return candidates

    def _pending_taktikal_request_for_issuer(self, game, *, player, issuer_model, battle_round: int, trigger: str) -> bool:
        if game is None or player is None or issuer_model is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        issuer_id = str(get_entity_id(issuer_model) or "")
        trigger_key = str(trigger or "").strip().lower()
        for request in list(queue.list() or []):
            context = dict(getattr(request, "context", {}) or {})
            if str(context.get("ability", "") or "") != "taktikal_brigade_lissen_ere":
                continue
            if str(getattr(request, "player_id", "") or "") != str(getattr(player, "id", "") or ""):
                continue
            if str(context.get("issuer_model_id", "") or "") != issuer_id:
                continue
            if int(context.get("battle_round", 0) or 0) != int(battle_round or 0):
                continue
            if str(context.get("trigger", "") or "").strip().lower() != trigger_key:
                continue
            return True
        return False

    def build_taktikal_brigade_lissen_ere_request(
        self,
        issuer_model,
        *,
        game=None,
        player=None,
        trigger: str = "command_phase",
        battle_round: int = 0,
    ):
        if not self.is_taktikal_brigade() or self.army is None:
            return None
        if issuer_model is None or not self._model_is_taktikal_issuer(issuer_model):
            return None
        if not self._model_is_alive(issuer_model):
            return None
        if player is None:
            player = getattr(self.army, "player", None)
        if player is None:
            return None
        if game is None:
            game = getattr(player, "game", None)
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return None
        if player is not getattr(self.army, "player", None):
            return None
        trigger_key = str(trigger or "").strip().lower()
        if trigger_key not in ("command_phase", "set_up"):
            return None
        if battle_round <= 0:
            battle_round = self._taktikal_current_battle_round(game)
        self._cleanup_taktikal_tracking_for_round(int(battle_round or 0))
        if self._taktikal_issuer_used_this_round(issuer_model, battle_round=int(battle_round or 0)):
            return None
        if self._pending_taktikal_request_for_issuer(
            game,
            player=player,
            issuer_model=issuer_model,
            battle_round=int(battle_round or 0),
            trigger=trigger_key,
        ):
            return None

        targets = self._collect_taktikal_target_units_for_issuer(issuer_model, game=game)
        if not targets:
            return None

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        options = [
            DecisionOption.create(
                "Do not issue Taktiks",
                payload={
                    "issuer_model_id": str(get_entity_id(issuer_model) or ""),
                    "action": "none",
                },
            )
        ]
        candidate_unit_ids = []
        for target in targets:
            target_id = self._unit_root_id(target)
            if not target_id:
                continue
            candidate_unit_ids.append(target_id)
            target_name = str(getattr(target, "name", "") or "Unit")
            for taktik in self._TAKTIKAL_BRIGADE_TAKTIKS:
                taktik_label = self._taktikal_label(taktik) or taktik
                options.append(
                    DecisionOption.create(
                        f"{taktik_label}: {target_name}",
                        payload={
                            "issuer_model_id": str(get_entity_id(issuer_model) or ""),
                            "target_unit_id": str(target_id),
                            "taktik": str(taktik),
                        },
                    )
                )

        if len(options) <= 1:
            return None

        issuer_name = str(getattr(issuer_model, "name", "Model") or "Model")
        issuer_unit = getattr(issuer_model, "parent_unit", None)
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"Lissen 'Ere: choose Taktiks to issue from {issuer_name}.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "taktikal_brigade_lissen_ere",
                "ability_name": self._TAKTIKAL_BRIGADE_SOURCE,
                "army_id": str(get_entity_id(self.army) or ""),
                "issuer_model_id": str(get_entity_id(issuer_model) or ""),
                "issuer_model_name": issuer_name,
                "issuer_unit_id": self._unit_root_id(issuer_unit),
                "battle_round": int(battle_round or 0),
                "trigger": trigger_key,
                "candidate_unit_ids": list(candidate_unit_ids),
                "candidate_taktiks": list(self._TAKTIKAL_BRIGADE_TAKTIKS),
                "optional": True,
            },
        )

    def validate_taktikal_brigade_lissen_ere_choice(
        self,
        issuer_model,
        payload: dict,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
        trigger: str = "",
    ) -> tuple[bool, str]:
        if not self.is_taktikal_brigade():
            return False, "Lissen 'Ere requires Taktikal Brigade detachment."
        if self.army is None:
            return False, "Lissen 'Ere army not found."
        if issuer_model is None or not self._model_is_taktikal_issuer(issuer_model):
            return False, "Lissen 'Ere issuer model is not eligible."
        if not self._model_is_alive(issuer_model):
            return False, "Lissen 'Ere issuer model must be alive."
        issuer_unit = getattr(issuer_model, "parent_unit", None)
        issuer_root = self._unit_root(issuer_unit)
        if issuer_root is None or not self._unit_belongs_to_army(issuer_root):
            return False, "Lissen 'Ere issuer model must belong to your army."
        if not self._unit_is_on_battlefield(issuer_root):
            return False, "Lissen 'Ere issuer model must be on the battlefield."
        if player is not None:
            army_player = getattr(self.army, "player", None)
            if army_player is not None and player is not army_player:
                return False, "Lissen 'Ere must be resolved by the owning player."
        trigger_key = str(trigger or "").strip().lower()
        if trigger_key and trigger_key not in ("command_phase", "set_up"):
            return False, "Lissen 'Ere trigger must be command_phase or set_up."
        if battle_round <= 0:
            battle_round = self._taktikal_current_battle_round(game)
        self._cleanup_taktikal_tracking_for_round(int(battle_round or 0))
        if self._taktikal_issuer_used_this_round(issuer_model, battle_round=int(battle_round or 0)):
            return False, "Lissen 'Ere issuer model has already issued Taktiks this battle round."

        action = str(dict(payload or {}).get("action", "") or "").strip().lower()
        if action == "none":
            return True, ""

        taktik = str(dict(payload or {}).get("taktik", "") or "").strip().lower()
        if taktik not in set(self._TAKTIKAL_BRIGADE_TAKTIKS):
            return False, "Lissen 'Ere selected Taktik is not valid."
        target_unit = dict(payload or {}).get("target_unit")
        if target_unit is None:
            return False, "Lissen 'Ere selected target unit was not found."
        target_root = self._unit_root(target_unit)
        if target_root is None or not self._unit_belongs_to_army(target_root):
            return False, "Lissen 'Ere target must be a friendly ORKS unit."
        if not self._unit_is_on_battlefield(target_root):
            return False, "Lissen 'Ere target must be on the battlefield."
        if self._unit_is_battle_shocked(target_root):
            return False, "Lissen 'Ere cannot target Battle-shocked units."
        if not self._unit_has_keyword_or_faction(target_root, "ORKS", faction_id=self.faction_id):
            return False, "Lissen 'Ere target must be an ORKS unit."
        if self._taktikal_target_used_this_round(target_root, battle_round=int(battle_round or 0)):
            return False, "Lissen 'Ere target unit has already had Taktiks issued this battle round."

        from ..utility.aura_utils import model_within_range_of_unit

        if not model_within_range_of_unit(
            issuer_model,
            target_root,
            float(self._taktikal_issue_range_for_model(issuer_model)),
            use_attached_aggregate=True,
        ):
            range_in = self._taktikal_issue_range_for_model(issuer_model)
            range_text = str(int(range_in)) if float(range_in).is_integer() else str(range_in)
            return False, f"Lissen 'Ere target must be within {range_text}\" of the issuing model."
        return True, ""

    def _set_taktikal_effect_on_unit(
        self,
        target_root,
        *,
        taktik: str,
        issuer_model,
        battle_round: int,
        trigger: str,
    ) -> None:
        source = self._TAKTIKAL_BRIGADE_SOURCE
        label = self._taktikal_label(taktik) or taktik
        special_rules = getattr(target_root, "special_rules", None)
        if not isinstance(special_rules, dict):
            special_rules = {}
        special_rules["taktikal_brigade_taktik_active"] = True
        special_rules["taktikal_brigade_taktik_key"] = str(taktik)
        special_rules["taktikal_brigade_taktik_label"] = str(label)
        special_rules["taktikal_brigade_taktik_source"] = str(source)
        special_rules["taktikal_brigade_taktik_battle_round"] = int(battle_round or 0)
        special_rules["taktikal_brigade_taktik_trigger"] = str(trigger or "").strip().lower()
        special_rules["taktikal_brigade_taktik_issuer_model_id"] = str(get_entity_id(issuer_model) or "")
        special_rules["taktikal_brigade_taktik_issuer_model_name"] = str(getattr(issuer_model, "name", "Model") or "Model")
        target_root.special_rules = special_rules

    def clear_taktikal_brigade_active_taktiks(self) -> None:
        if self.army is None:
            return
        keys = (
            "taktikal_brigade_taktik_active",
            "taktikal_brigade_taktik_key",
            "taktikal_brigade_taktik_label",
            "taktikal_brigade_taktik_source",
            "taktikal_brigade_taktik_battle_round",
            "taktikal_brigade_taktik_trigger",
            "taktikal_brigade_taktik_issuer_model_id",
            "taktikal_brigade_taktik_issuer_model_name",
        )
        seen: set[str] = set()
        for entry in list(getattr(self.army, "units", []) or []):
            root = self._unit_root(entry)
            if root is None:
                continue
            rid = self._unit_root_id(root)
            if rid and rid in seen:
                continue
            if rid:
                seen.add(rid)
            special_rules = getattr(root, "special_rules", None)
            if not isinstance(special_rules, dict):
                continue
            if not any(k in special_rules for k in keys):
                continue
            updated = dict(special_rules)
            for key in keys:
                updated.pop(key, None)
            root.special_rules = updated

    def _unit_active_taktikal_taktik_key(self, unit, *, game=None) -> str:
        del game
        if not self.is_taktikal_brigade():
            return ""
        root = self._unit_root(unit)
        if root is None or not self._unit_belongs_to_army(root):
            return ""
        special_rules = getattr(root, "special_rules", None)
        if not isinstance(special_rules, dict):
            return ""
        if not bool(special_rules.get("taktikal_brigade_taktik_active")):
            return ""
        if self._unit_is_battle_shocked(root):
            return ""
        taktik = str(special_rules.get("taktikal_brigade_taktik_key", "") or "").strip().lower()
        if taktik not in set(self._TAKTIKAL_BRIGADE_TAKTIKS):
            return ""
        return taktik

    def taktikal_brigade_get_stuck_in_charge_reroll_applies(self, unit, *, game=None) -> bool:
        return self._unit_active_taktikal_taktik_key(unit, game=game) == self._TAKTIKAL_BRIGADE_TAKTIK_GET_STUCK_IN

    def taktikal_brigade_get_on_wiv_it_melee_strength_bonus(self, attacker_model, *, attack_type: str = "", game=None) -> tuple[int, str]:
        if str(attack_type or "").strip().lower() not in ("", "melee"):
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None) if attacker_model is not None else None
        if self._unit_active_taktikal_taktik_key(attacker_unit, game=game) != self._TAKTIKAL_BRIGADE_TAKTIK_GET_ON_WIV_IT:
            return 0, ""
        return 1, f"{self._TAKTIKAL_BRIGADE_SOURCE}: {self._taktikal_label(self._TAKTIKAL_BRIGADE_TAKTIK_GET_ON_WIV_IT)}"

    def taktikal_brigade_shoota_drills_hit_bonus(
        self,
        attacker_model,
        *,
        attack_type: str = "",
        game=None,
    ) -> tuple[int, str]:
        if str(attack_type or "").strip().lower() not in ("", "ranged"):
            return 0, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None) if attacker_model is not None else None
        if self._unit_active_taktikal_taktik_key(attacker_unit, game=game) != self._TAKTIKAL_BRIGADE_TAKTIK_SHOOTA_DRILLS:
            return 0, ""
        if attacker_model is None:
            return 0, ""
        if not self._model_has_any_keyword(attacker_model, ("INFANTRY", "MOUNTED")):
            return 0, ""
        return 1, f"{self._TAKTIKAL_BRIGADE_SOURCE}: {self._taktikal_label(self._TAKTIKAL_BRIGADE_TAKTIK_SHOOTA_DRILLS)}"

    def taktikal_brigade_sneaky_stalkin_stealth_applies(self, unit, *, game=None) -> bool:
        if self._unit_active_taktikal_taktik_key(unit, game=game) != self._TAKTIKAL_BRIGADE_TAKTIK_SNEAKY_STALKIN:
            return False
        root = self._unit_root(unit)
        if root is None:
            return False
        if self._unit_contains_keyword(root, "MEGANOBZ"):
            return False
        return self._unit_contains_any_keyword(root, ("INFANTRY", "MOUNTED"))

    def taktikal_brigade_sneaky_stalkin_benefit_of_cover(self, target_model, *, attack_type: str = "", game=None) -> tuple[bool, str]:
        if str(attack_type or "").strip().lower() not in ("", "ranged"):
            return False, ""
        if target_model is None:
            return False, ""
        target_unit = getattr(target_model, "parent_unit", None)
        if self._unit_active_taktikal_taktik_key(target_unit, game=game) != self._TAKTIKAL_BRIGADE_TAKTIK_SNEAKY_STALKIN:
            return False, ""
        if self._model_is_meganobz(target_model):
            return False, ""
        if not self._model_has_any_keyword(target_model, ("INFANTRY", "MOUNTED")):
            return False, ""
        return True, f"{self._TAKTIKAL_BRIGADE_SOURCE}: {self._taktikal_label(self._TAKTIKAL_BRIGADE_TAKTIK_SNEAKY_STALKIN)}"

    def mek_kaptin_ranged_hit_reroll_applies(
        self,
        attacker_model,
        *,
        attack_type: str = "",
    ) -> tuple[bool, str]:
        if str(attack_type or "").strip().lower() not in ("", "ranged"):
            return False, ""
        if attacker_model is None:
            return False, ""
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._unit_root(attacker_unit)
        if attacker_root is None or not self._unit_belongs_to_army(attacker_root):
            return False, ""
        sources = self._collect_active_enhancement_source_units(
            attacker_root,
            flag_key="enhancement_mek_kaptin",
        )
        if not sources:
            return False, ""
        source_name = self._enhancement_source_name(
            sources[0],
            source_key="enhancement_mek_kaptin_source",
            default="Mek Kaptin",
        )
        return True, source_name

    def surly_as_a_squiggoth_defensive_wound_mod_entry(self, target_unit) -> dict | None:
        root = self._unit_root(target_unit)
        if root is None or not self._unit_belongs_to_army(root):
            return None
        leaders = list(getattr(root, "attached_leaders", []) or [])
        if not leaders:
            return None
        sources = self._collect_active_enhancement_source_units(
            root,
            flag_key="enhancement_surly_as_a_squiggoth",
        )
        if not sources:
            return None
        leader_ids = {str(get_entity_id(leader) or "") for leader in leaders}
        matched_source = None
        for source_unit in sources:
            source_id = str(get_entity_id(source_unit) or "")
            if source_unit in leaders or source_id in leader_ids:
                matched_source = source_unit
                break
        if matched_source is None:
            return None
        source_name = self._enhancement_source_name(
            matched_source,
            source_key="enhancement_surly_as_a_squiggoth_source",
            default="Surly as a Squiggoth",
        )
        return {
            "value": 1,
            "attack_type": "any",
            "source": source_name,
            "requires_strength_gt_toughness": True,
        }

    def apply_taktikal_brigade_stormboyz_battleline_keywords(self, unit=None) -> None:
        if not self.is_taktikal_brigade() or self.army is None:
            return
        if unit is None:
            entries = list(getattr(self.army, "units", []) or [])
        else:
            entries = [unit]
        for entry in entries:
            root = self._unit_root(entry)
            if root is None or not self._unit_belongs_to_army(root):
                continue
            if not self._unit_contains_keyword(root, "STORMBOYZ"):
                if not self._unit_name_matches_any(root, self._TAKTIKAL_BRIGADE_STORMBOYZ_NAMED_UNITS):
                    continue
            keywords = list(getattr(root, "keywords", []) or [])
            if not any(str(keyword or "").strip().lower() == "battleline" for keyword in keywords):
                keywords.append("Battleline")
                root.keywords = keywords

    def _army_warlord_is_wazdakka(self) -> bool:
        if self.army is None:
            return False
        warlord = getattr(self.army, "warlord", None)
        if warlord is None:
            for candidate in list(getattr(self.army, "units", []) or []):
                if bool(getattr(candidate, "is_warlord", False)):
                    warlord = candidate
                    break
        root = self._unit_root(warlord)
        if root is None:
            return False
        if self._unit_name_matches_any(root, self._WAZDAKKA_GUTSMEK_NAMED_UNITS):
            return True
        for name, desc in root._iter_ability_entries_for_rules(model=None):
            text = root._normalize_rules_text(f"{name} {desc}")
            normalized = text.replace("\u2019", "'").lower()
            normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if "waaagh wazdakka" in normalized and "warbikers" in normalized and "battleline" in normalized:
                return True
        return False

    def apply_wazdakka_warbikers_battleline_keywords(self, unit=None) -> None:
        if self.army is None or not self._army_warlord_is_wazdakka():
            return
        units = list(getattr(self.army, "units", []) or []) if unit is None else [unit]
        for entry in units:
            root = self._unit_root(entry)
            if root is None or not self._unit_belongs_to_army(root):
                continue
            if not self._unit_name_matches_any(root, self._WAZDAKKA_WARBIKERS_NAMED_UNITS):
                if not self._unit_contains_keyword(root, "WARBIKERS"):
                    continue
            keywords = list(getattr(root, "keywords", []) or [])
            if not any(str(keyword or "").strip().lower() == "battleline" for keyword in keywords):
                keywords.append("Battleline")
                root.keywords = keywords

    def queue_taktikal_brigade_lissen_ere_requests(
        self,
        *,
        game=None,
        player=None,
        trigger: str = "command_phase",
        unit=None,
    ) -> None:
        if not self.is_taktikal_brigade() or self.army is None:
            return
        if game is None:
            player = getattr(self.army, "player", None) if player is None else player
            game = getattr(player, "game", None) if player is not None else None
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        if player is None:
            player = getattr(self.army, "player", None)
        if player is None or player is not getattr(self.army, "player", None):
            return
        battle_round = self._taktikal_current_battle_round(game)
        self._cleanup_taktikal_tracking_for_round(int(battle_round or 0))
        trigger_key = str(trigger or "").strip().lower()
        issuers = self._collect_taktikal_issuer_models(unit=unit)
        for issuer in issuers:
            request = self.build_taktikal_brigade_lissen_ere_request(
                issuer,
                game=game,
                player=player,
                trigger=trigger_key,
                battle_round=int(battle_round or 0),
            )
            if request is not None and hasattr(game, "request_decision"):
                game.request_decision(request)

    def apply_taktikal_brigade_lissen_ere_choice(
        self,
        issuer_model,
        payload: dict,
        *,
        game=None,
        player=None,
        battle_round: int = 0,
        trigger: str = "",
    ):
        valid, reason = self.validate_taktikal_brigade_lissen_ere_choice(
            issuer_model,
            payload,
            game=game,
            player=player,
            battle_round=battle_round,
            trigger=trigger,
        )
        if not valid:
            return {"valid": False, "reason": str(reason or "")}
        action = str(dict(payload or {}).get("action", "") or "").strip().lower()
        if action == "none":
            return {
                "action": "none",
                "issuer_model_id": str(get_entity_id(issuer_model) or ""),
                "issuer_model_name": str(getattr(issuer_model, "name", "Model") or "Model"),
                "source": self._TAKTIKAL_BRIGADE_SOURCE,
            }

        target_unit = dict(payload or {}).get("target_unit")
        target_root = self._unit_root(target_unit)
        if target_root is None:
            return {"valid": False, "reason": "Lissen 'Ere target unit was not found."}
        taktik = str(dict(payload or {}).get("taktik", "") or "").strip().lower()
        if battle_round <= 0:
            battle_round = self._taktikal_current_battle_round(game)
        issuer_unit = getattr(issuer_model, "parent_unit", None)
        issuer_root = self._unit_root(issuer_unit)
        leadership_passed = True
        test_fn = getattr(issuer_root, "pass_leadership_check_for_model", None) if issuer_root is not None else None
        if callable(test_fn):
            leadership_passed = bool(test_fn(issuer_model))

        mortal_wounds = 0
        if not leadership_passed:
            apply_mortal_wounds = getattr(target_root, "_apply_mortal_wounds_to_unit", None)
            if callable(apply_mortal_wounds):
                game_map = getattr(game, "map", None) if game is not None else None
                apply_mortal_wounds(target_root, 1, game_map=game_map)
                mortal_wounds = 1

        self._set_taktikal_effect_on_unit(
            target_root,
            taktik=taktik,
            issuer_model=issuer_model,
            battle_round=int(battle_round or 0),
            trigger=str(trigger or "").strip().lower(),
        )
        self._mark_taktikal_usage(
            issuer_model,
            target_root,
            battle_round=int(battle_round or 0),
        )
        return {
            "action": "issue",
            "issuer_model_id": str(get_entity_id(issuer_model) or ""),
            "issuer_model_name": str(getattr(issuer_model, "name", "Model") or "Model"),
            "target_unit_id": self._unit_root_id(target_root),
            "target_unit_name": str(getattr(target_root, "name", "Unit") or "Unit"),
            "taktik": str(taktik),
            "taktik_label": self._taktikal_label(taktik) or taktik,
            "leadership_passed": bool(leadership_passed),
            "mortal_wounds": int(mortal_wounds),
            "source": self._TAKTIKAL_BRIGADE_SOURCE,
        }

    def _da_big_hunt_prey_active(self) -> bool:
        if not self.is_da_big_hunt():
            return False
        return bool(str(self.da_big_hunt_prey_unit_id or "").strip())

    def clear_da_big_hunt_prey(self) -> None:
        self.da_big_hunt_prey_unit_id = ""
        self.da_big_hunt_prey_turn = 0
        self.da_big_hunt_prey_owner_id = ""

    def _iter_unique_army_unit_roots(self) -> list:
        if self.army is None:
            return []
        seen: set[str] = set()
        roots: list = []
        for entry in list(getattr(self.army, "units", []) or []):
            root = self._unit_root(entry)
            if root is None:
                continue
            root_id = self._unit_root_id(root)
            if root_id and root_id in seen:
                continue
            if root_id:
                seen.add(root_id)
            roots.append(root)
        roots.sort(key=lambda unit: self._unit_root_id(unit))
        return roots

    def clear_orks_next_command_phase_effects(self, *, player=None) -> None:
        owner = getattr(self.army, "player", None) if self.army is not None else None
        owner_command_phase = owner is not None and player is owner
        for root in self._iter_unique_army_unit_roots():
            remove_mods = getattr(root, "remove_characteristic_modifiers_by_source", None)
            if callable(remove_mods):
                for prefix in self._NEXT_COMMAND_PHASE_ANY_SOURCE_PREFIXES:
                    remove_mods(prefix)
                if owner_command_phase:
                    for prefix in self._NEXT_COMMAND_PHASE_OWNER_SOURCE_PREFIXES:
                        remove_mods(prefix)
            special_rules = getattr(root, "special_rules", None)
            if not isinstance(special_rules, dict):
                continue
            effects = list(special_rules.get("orks_temp_effects", []) or [])
            if not effects:
                continue
            kept = []
            for entry in effects:
                if not isinstance(entry, dict):
                    continue
                if str(entry.get("expires_mode", "") or "").strip().lower() == "next_command_phase":
                    expires_scope = str(entry.get("expires_scope", "") or "").strip().lower()
                    if expires_scope == "owner_command_phase" and not owner_command_phase:
                        kept.append(dict(entry))
                        continue
                    continue
                kept.append(dict(entry))
            updated = dict(special_rules)
            if kept:
                updated["orks_temp_effects"] = kept
            else:
                updated.pop("orks_temp_effects", None)
            root.special_rules = updated

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if self.army is None:
            self.clear_da_big_hunt_prey()
            self.clear_taktikal_brigade_active_taktiks()
            return
        self.clear_orks_next_command_phase_effects(player=player)
        army_player = getattr(self.army, "player", None)
        if player is not None and army_player is not None and army_player is not player:
            return
        if self.is_freebooter_krew():
            self.clear_here_be_loot_objective()
            request = self.build_here_be_loot_request(game=game, player=army_player)
            if request is not None and hasattr(game, "request_decision"):
                game.request_decision(request)
        if self.is_da_big_hunt():
            self.clear_da_big_hunt_prey()
        if self.is_taktikal_brigade():
            self.apply_taktikal_brigade_stormboyz_battleline_keywords()
            self.clear_taktikal_brigade_active_taktiks()
            self.queue_taktikal_brigade_lissen_ere_requests(
                game=game,
                player=army_player,
                trigger="command_phase",
            )

    def on_unit_set_up(self, *, unit=None, game=None, set_up_as_reinforcements: bool = False) -> None:
        self.apply_taktikal_brigade_stormboyz_battleline_keywords(unit=unit)
        if not self.is_taktikal_brigade() or self.army is None:
            return
        if not bool(set_up_as_reinforcements):
            return
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return
        phase_name = self._phase_key_from_game(game)
        if phase_name != "MOVEMENT_PHASE":
            return
        owner = getattr(self.army, "player", None)
        current_player = getattr(game, "get_current_player", lambda: None)()
        if owner is None or current_player is not owner:
            return
        root = self._unit_root(unit)
        if root is None or not self._unit_belongs_to_army(root):
            return
        if not self._unit_is_on_battlefield(root):
            return
        self.queue_taktikal_brigade_lissen_ere_requests(
            game=game,
            player=owner,
            trigger="set_up",
            unit=root,
        )

    @staticmethod
    def _objective_point_for_entry(objective):
        if objective is None:
            return None
        point = getattr(objective, "location", None)
        if point is not None:
            return point
        if hasattr(objective, "x") and hasattr(objective, "y"):
            return objective
        return None

    def _collect_objective_entries(self, *, game=None, game_map=None) -> list[tuple[str, object, object]]:
        if game is None and self.army is not None:
            player = getattr(self.army, "player", None)
            game = getattr(player, "game", None) if player is not None else None
        if game_map is None and game is not None:
            game_map = getattr(game, "map", None)
        pool = []
        if game is not None:
            pool.extend(list(getattr(game, "objectives", []) or []))
        if game_map is not None:
            pool.extend(list(getattr(game_map, "objectives", []) or []))

        entries = []
        seen_ids: set[str] = set()
        for objective in pool:
            point = self._objective_point_for_entry(objective)
            if point is None or bool(getattr(point, "removed", False)):
                continue
            objective_id = str(get_entity_id(objective) or get_entity_id(point) or "")
            if not objective_id or objective_id in seen_ids:
                continue
            seen_ids.add(objective_id)
            entries.append((objective_id, objective, point))
        entries.sort(key=lambda item: str(item[0]))
        return entries

    def _objective_entry_by_id(self, objective_id: str, *, game=None, game_map=None):
        target_id = str(objective_id or "").strip()
        if not target_id:
            return None
        for entry in self._collect_objective_entries(game=game, game_map=game_map):
            if str(entry[0]) == target_id:
                return entry
        return None

    def clear_here_be_loot_objective(self) -> None:
        self.freebooter_loot_objective_id = ""
        self.freebooter_loot_battle_round = 0
        self.freebooter_loot_turn_owner_id = ""

    def build_here_be_loot_request(self, *, game=None, player=None):
        if not self.is_freebooter_krew():
            return None
        if self.army is None:
            return None
        if player is None:
            player = getattr(self.army, "player", None)
        if player is None:
            return None
        if game is None:
            game = getattr(player, "game", None)
        if game is None or not bool(getattr(game, "is_authoritative", True)):
            return None

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        entries = self._collect_objective_entries(game=game)
        if not entries:
            return None
        objective_ids = [str(entry[0]) for entry in entries]
        try:
            turn = int(getattr(game, "turn", 0) or 0)
        except (TypeError, ValueError):
            turn = 0
        turn_owner_id = str(getattr(player, "id", "") or "")

        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                if str(getattr(req, "player_id", "") or "") != str(getattr(player, "id", "") or ""):
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "here_be_loot":
                    continue
                if int(ctx.get("turn", 0) or 0) != int(turn or 0):
                    continue
                if str(ctx.get("turn_owner_id", "") or "") != turn_owner_id:
                    continue
                return None

        options = []
        for idx, (objective_id, objective, point) in enumerate(entries):
            label = str(getattr(objective, "name", "") or f"Objective {idx + 1}")
            try:
                label = (
                    f"{label} "
                    f"({float(getattr(point, 'x', 0.0)):.1f}, "
                    f"{float(getattr(point, 'y', 0.0)):.1f})"
                )
            except (TypeError, ValueError):
                pass
            options.append(
                DecisionOption.create(
                    label,
                    payload={"objective_id": str(objective_id)},
                )
            )
        if not options:
            return None

        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Here Be Loot: select one objective marker to be your loot objective until the start of your next Command phase.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "here_be_loot",
                "ability_name": "Here Be Loot",
                "army_id": str(get_entity_id(self.army) or ""),
                "phase_name": "Command phase",
                "turn": int(turn or 0),
                "turn_owner_id": turn_owner_id,
                "candidate_objective_ids": list(objective_ids),
                "optional": False,
            },
        )

    def validate_here_be_loot_objective_choice(
        self,
        objective_id: str,
        *,
        game=None,
        player=None,
        turn: int = 0,
        turn_owner_id: str = "",
    ) -> tuple[bool, str]:
        if not self.is_freebooter_krew():
            return False, "Here Be Loot requires Freebooter Krew detachment."
        if self.army is None:
            return False, "Here Be Loot army not found."
        if player is not None:
            army_player = getattr(self.army, "player", None)
            if army_player is not None and army_player is not player:
                return False, "Here Be Loot must be resolved by the owning player."
        objective_id = str(objective_id or "").strip()
        if not objective_id:
            return False, "Here Be Loot selection requires objective_id."
        if self._objective_entry_by_id(objective_id, game=game) is None:
            return False, "Here Be Loot selected objective marker was not found."
        expected_turn = int(turn or 0)
        expected_owner_id = str(turn_owner_id or "").strip()
        if game is not None:
            if self._phase_key_from_game(game) != "COMMAND_PHASE":
                return False, "Here Be Loot selection is no longer in the current Command phase."
            try:
                current_turn = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_turn = 0
            if expected_turn and current_turn and current_turn != expected_turn:
                return False, "Here Be Loot selection is no longer in the current Command phase."
            if expected_owner_id:
                current_player = getattr(game, "get_current_player", lambda: None)()
                current_owner_id = str(getattr(current_player, "id", "") or "")
                if current_owner_id and current_owner_id != expected_owner_id:
                    return False, "Here Be Loot selection is no longer in the current Command phase."
        return True, ""

    def select_here_be_loot_objective(
        self,
        objective_id: str,
        *,
        game=None,
        player=None,
        turn: int = 0,
        turn_owner_id: str = "",
    ):
        valid, reason = self.validate_here_be_loot_objective_choice(
            objective_id,
            game=game,
            player=player,
            turn=turn,
            turn_owner_id=turn_owner_id,
        )
        if not valid:
            return None
        entry = self._objective_entry_by_id(str(objective_id or "").strip(), game=game)
        if entry is None:
            return None
        objective_key, objective, _point = entry
        self.freebooter_loot_objective_id = str(objective_key)
        if game is not None:
            try:
                self.freebooter_loot_battle_round = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                self.freebooter_loot_battle_round = int(turn or 0)
            current_player = getattr(game, "get_current_player", lambda: None)()
            self.freebooter_loot_turn_owner_id = str(getattr(current_player, "id", "") or turn_owner_id or "")
        else:
            self.freebooter_loot_battle_round = int(turn or 0)
            self.freebooter_loot_turn_owner_id = str(turn_owner_id or "")
        return {
            "objective_id": str(objective_key),
            "objective_name": str(getattr(objective, "name", "") or "Objective marker"),
            "battle_round": int(self.freebooter_loot_battle_round or 0),
            "turn_owner_id": str(self.freebooter_loot_turn_owner_id or ""),
            "source": "Here Be Loot",
        }

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if self.is_taktikal_brigade():
            self.apply_taktikal_brigade_stormboyz_battleline_keywords()
            self._cleanup_taktikal_tracking_for_round(int(battle_round or 0))

    def _active_here_be_loot_objective_point(self, *, game=None, game_map=None):
        if not self.is_freebooter_krew():
            return None
        objective_id = str(self.freebooter_loot_objective_id or "").strip()
        if not objective_id:
            return None
        if game is None and self.army is not None:
            player = getattr(self.army, "player", None)
            game = getattr(player, "game", None) if player is not None else None
        if game is not None and int(self.freebooter_loot_battle_round or 0):
            try:
                current_round = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_round = 0
            if current_round and current_round > int(self.freebooter_loot_battle_round or 0):
                current_player = getattr(game, "get_current_player", lambda: None)()
                current_owner_id = str(getattr(current_player, "id", "") or "")
                stored_owner_id = str(self.freebooter_loot_turn_owner_id or "")
                if not stored_owner_id or stored_owner_id == current_owner_id:
                    return None
        entry = self._objective_entry_by_id(objective_id, game=game, game_map=game_map)
        if entry is None:
            return None
        _objective_key, objective, point = entry
        if point is None or bool(getattr(point, "removed", False)):
            return None
        return objective, point

    def freebooter_here_be_loot_sustained_hits_value(
        self,
        attacker_model,
        *,
        target_unit=None,
        game=None,
        game_map=None,
    ) -> int:
        if not self.is_freebooter_krew():
            return 0
        if attacker_model is None:
            return 0
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        attacker_root = self._unit_root(attacker_unit)
        if attacker_root is None or not self._unit_belongs_to_army(attacker_root):
            return 0
        if not self._unit_contains_any_keyword(attacker_root, self._HERE_BE_LOOT_QUALIFYING_KEYWORDS):
            return 0
        active = self._active_here_be_loot_objective_point(game=game, game_map=game_map)
        if not isinstance(active, tuple):
            return 0
        _objective, objective_point = active
        in_attacker_range = False
        in_target_range = False
        is_within = getattr(attacker_root, "is_within_objective_range", None)
        if callable(is_within):
            in_attacker_range = bool(is_within(objective_point))
        target_root = self._unit_root(target_unit)
        if target_root is not None:
            target_is_within = getattr(target_root, "is_within_objective_range", None)
            if callable(target_is_within):
                in_target_range = bool(target_is_within(objective_point))
        if in_attacker_range or in_target_range:
            return 1
        return 0

    def _collect_da_big_hunt_prey_candidates(self, *, game=None, player=None) -> list:
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
            rid = self._unit_root_id(root)
            if not rid or rid in seen_ids:
                continue
            seen_ids.add(rid)
            if not self._unit_is_on_battlefield(root):
                continue
            if not self._unit_contains_any_keyword(root, self._DA_BIG_HUNT_PREY_KEYWORDS):
                continue
            if not self._unit_is_enemy_of_player(root, player):
                continue
            candidates.append(root)
        candidates.sort(key=lambda unit: (self._normalize_name(getattr(unit, "name", "")), self._unit_root_id(unit)))
        return candidates

    def build_da_big_hunt_prey_request(self, *, game=None, player=None):
        if not self.is_da_big_hunt():
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
                if str(ctx.get("ability", "") or "") == "da_big_hunt_prey":
                    return None

        candidates = self._collect_da_big_hunt_prey_candidates(game=game, player=player)
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
            "Da Hunt Is On: select one enemy MONSTER, VEHICLE, or CHARACTER unit as your Prey.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "da_big_hunt_prey",
                "ability_name": "Da Hunt Is On",
                "army_id": army_id,
                "candidate_unit_ids": list(candidate_ids),
                "optional": False,
            },
        )

    def is_valid_da_big_hunt_prey_target(self, target_unit, *, player=None, game=None) -> bool:
        if not self.is_da_big_hunt():
            return False
        root = self._unit_root(target_unit)
        if root is None:
            return False
        if not self._unit_is_on_battlefield(root):
            return False
        if not self._unit_contains_any_keyword(root, self._DA_BIG_HUNT_PREY_KEYWORDS):
            return False
        if player is not None and not self._unit_is_enemy_of_player(root, player):
            return False
        return bool(self._unit_root_id(root))

    def select_da_big_hunt_prey(self, target_unit, *, game=None, player=None) -> bool:
        if not self.is_valid_da_big_hunt_prey_target(target_unit, player=player, game=game):
            return False
        self.da_big_hunt_prey_unit_id = self._unit_root_id(target_unit)
        if game is not None:
            try:
                self.da_big_hunt_prey_turn = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                self.da_big_hunt_prey_turn = 0
        else:
            self.da_big_hunt_prey_turn = 0
        self.da_big_hunt_prey_owner_id = str(getattr(player, "id", "") or "")
        return True

    def is_da_big_hunt_prey_target(self, target_unit) -> bool:
        if not self._da_big_hunt_prey_active():
            return False
        target_id = self._unit_root_id(target_unit)
        if not target_id:
            return False
        return str(self.da_big_hunt_prey_unit_id or "") == str(target_id)

    def _unit_is_beast_snagga(self, unit) -> bool:
        if unit is None:
            return False
        return self._unit_contains_keyword(unit, "BEAST SNAGGA")

    def da_big_hunt_charge_reroll_applies(self, unit, *, target_units=None, game=None) -> bool:
        if not self._da_big_hunt_prey_active():
            return False
        if unit is None or not self._unit_belongs_to_army(unit):
            return False
        if not self._unit_is_beast_snagga(unit):
            return False
        if target_units is None:
            return False
        if isinstance(target_units, (list, tuple, set)):
            targets = [t for t in list(target_units or []) if t is not None]
        else:
            targets = [target_units]
        for target in targets:
            if self.is_da_big_hunt_prey_target(target):
                return True
        return False

    def da_big_hunt_ap_bonus(self, attacker_model, target_unit, *, weapon_profile=None) -> int:
        if not self._da_big_hunt_prey_active():
            return 0
        if attacker_model is None or target_unit is None:
            return 0
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if attacker_unit is None or not self._unit_belongs_to_army(attacker_unit):
            return 0
        is_beast_snagga_model = self._model_has_keyword(attacker_model, "BEAST SNAGGA")
        if not is_beast_snagga_model and not self._unit_is_beast_snagga(attacker_unit):
            return 0
        if not self.is_da_big_hunt_prey_target(target_unit):
            return 0
        return 1

    def _dread_mob_unit_is_eligible(self, unit) -> bool:
        if unit is None:
            return False
        if not self._unit_belongs_to_army(unit):
            return False
        is_mek = self._unit_contains_keyword(unit, "MEK")
        is_walker = self._unit_contains_keyword(unit, "WALKER")
        is_grots_vehicle = self._unit_contains_keyword(unit, "GROTS") and self._unit_contains_keyword(unit, "VEHICLE")
        return bool(is_mek or is_walker or is_grots_vehicle)

    def apply_dread_mob_gretchin_battleline_keywords(self, unit=None) -> None:
        if not self.is_dread_mob() or self.army is None:
            return
        if unit is None:
            units = list(getattr(self.army, "units", []) or [])
        else:
            units = [unit]
        for entry in units:
            if entry is None:
                continue
            root = self._unit_root(entry)
            if root is None:
                continue
            if not self._unit_belongs_to_army(root):
                continue
            if not self._unit_contains_keyword(root, "GRETCHIN"):
                continue
            keywords = list(getattr(root, "keywords", []) or [])
            if not any(str(k or "").strip().lower() == "battleline" for k in keywords):
                keywords.append("Battleline")
                root.keywords = keywords

    def _dread_mob_effect_from_roll(self, roll_value: int) -> str:
        if int(roll_value or 0) <= 2:
            return self._DREAD_MOB_BUTTON_SUSTAINED
        if int(roll_value or 0) <= 4:
            return self._DREAD_MOB_BUTTON_LETHAL
        return self._DREAD_MOB_BUTTON_CRIT_AP

    def _dread_mob_effect_label(self, effect_key: str) -> str:
        key = str(effect_key or "").strip().upper()
        return str(self._DREAD_MOB_BUTTON_LABELS.get(key, key) or key)

    def queue_dread_mob_try_dat_button_choice(self, unit, *, trigger: str = "", game=None):
        if not self.is_dread_mob() or self.army is None or game is None:
            return None
        if not bool(getattr(game, "is_authoritative", True)):
            return None
        root = self._unit_root(unit)
        if root is None or not self._dread_mob_unit_is_eligible(root):
            return None
        if not self._unit_is_alive(root):
            return None
        player = getattr(self.army, "player", None)
        if player is None:
            return None
        trigger_key = str(trigger or "").strip().lower()
        if trigger_key not in ("shooting", "fight"):
            return None

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest

        unit_id = self._unit_root_id(root)
        phase_name = self._phase_key_from_game(game)
        queue = getattr(game, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
                    continue
                if str(getattr(req, "player_id", "") or "") != str(getattr(player, "id", "") or ""):
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "dread_mob_try_dat_button":
                    continue
                if str(ctx.get("unit_id", "") or "") != str(unit_id):
                    continue
                if str(ctx.get("phase_name", "") or "") != phase_name:
                    continue
                if str(ctx.get("trigger", "") or "") != trigger_key:
                    continue
                return None

        options = [
            DecisionOption.create(
                "Roll D6 (no Hazardous)",
                payload={"button_mode": "roll"},
            ),
            DecisionOption.create(
                "Sustained Hits 1 + Hazardous",
                payload={
                    "button_mode": "manual",
                    "button_effect": self._DREAD_MOB_BUTTON_SUSTAINED,
                },
            ),
            DecisionOption.create(
                "Lethal Hits + Hazardous",
                payload={
                    "button_mode": "manual",
                    "button_effect": self._DREAD_MOB_BUTTON_LETHAL,
                },
            ),
            DecisionOption.create(
                "Critical Wound AP +2 + Hazardous",
                payload={
                    "button_mode": "manual",
                    "button_effect": self._DREAD_MOB_BUTTON_CRIT_AP,
                },
            ),
        ]
        return DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"Try Dat Button!: choose effect for {getattr(root, 'name', 'Unit')}.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "ability": "dread_mob_try_dat_button",
                "ability_name": "Try Dat Button!",
                "army_id": str(get_entity_id(self.army) or ""),
                "unit_id": unit_id,
                "phase_name": phase_name,
                "trigger": trigger_key,
                "candidate_button_modes": ["roll", "manual"],
                "candidate_button_effects": list(self._DREAD_MOB_BUTTON_EFFECTS),
                "optional": False,
            },
        )

    def validate_dread_mob_try_dat_button_choice(
        self,
        unit,
        payload: dict,
        *,
        game=None,
        player=None,
        phase_name: str = "",
        trigger: str = "",
    ) -> tuple[bool, str]:
        if not self.is_dread_mob():
            return False, "Try Dat Button! requires Dread Mob detachment."
        root = self._unit_root(unit)
        if root is None or not self._dread_mob_unit_is_eligible(root):
            return False, "Try Dat Button! source unit is not an eligible Mek, Orks Walker, or Grots Vehicle unit."
        if not self._unit_is_alive(root):
            return False, "Try Dat Button! source unit must be alive."
        if player is not None:
            army_player = getattr(self.army, "player", None)
            if army_player is not None and army_player is not player:
                return False, "Try Dat Button! must be resolved by the owning player."
        trigger_key = str(trigger or "").strip().lower()
        if trigger_key and trigger_key not in ("shooting", "fight"):
            return False, "Try Dat Button! trigger must be shooting or fight."
        expected_phase = str(phase_name or "").strip().upper()
        if expected_phase and game is not None:
            current_phase = self._phase_key_from_game(game)
            if current_phase and current_phase != expected_phase:
                return False, "Try Dat Button! request is no longer in the current phase."

        mode = str(dict(payload or {}).get("button_mode", "") or "").strip().lower()
        if mode == "roll":
            return True, ""
        if mode != "manual":
            return False, "Try Dat Button! requires button_mode of roll or manual."
        effect_key = str(dict(payload or {}).get("button_effect", "") or "").strip().upper()
        if effect_key not in set(self._DREAD_MOB_BUTTON_EFFECTS):
            return False, "Try Dat Button! selected effect is not valid."
        return True, ""

    def apply_dread_mob_try_dat_button_choice(
        self,
        unit,
        payload: dict,
        *,
        game=None,
        player=None,
        phase_name: str = "",
        trigger: str = "",
    ):
        valid, reason = self.validate_dread_mob_try_dat_button_choice(
            unit,
            payload,
            game=game,
            player=player,
            phase_name=phase_name,
            trigger=trigger,
        )
        if not valid:
            return None
        root = self._unit_root(unit)
        if root is None:
            return None
        mode = str(dict(payload or {}).get("button_mode", "") or "").strip().lower()
        effect_key = ""
        effect_keys: list[str] = []
        rolled = 0
        rolled_values: list[int] = []
        hazardous = False
        if mode == "roll":
            roll_count = 1
            roll_count_fn = getattr(root, "selected_to_shoot_try_dat_button_roll_count", None)
            if callable(roll_count_fn):
                try:
                    roll_count = int(roll_count_fn(trigger=str(trigger or "").strip().lower()) or 1)
                except (TypeError, ValueError):
                    roll_count = 1
            roll_count = max(1, int(roll_count))
            for _roll_index in range(roll_count):
                rolled_value = get_roll("D6")
                if rolled_value < 1:
                    rolled_value = 1
                if rolled_value > 6:
                    rolled_value = 6
                rolled_values.append(int(rolled_value))
                mapped_effect = self._dread_mob_effect_from_roll(int(rolled_value))
                if mapped_effect and mapped_effect not in effect_keys:
                    effect_keys.append(str(mapped_effect))
            rolled = int(rolled_values[0] or 0) if rolled_values else 0
            effect_key = str(effect_keys[0] or "") if effect_keys else ""
        else:
            effect_key = str(dict(payload or {}).get("button_effect", "") or "").strip().upper()
            effect_keys = [effect_key] if effect_key else []
            hazardous = True
        if effect_key not in set(self._DREAD_MOB_BUTTON_EFFECTS):
            return None

        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        current_phase = self._phase_key_from_game(game)
        if not current_phase:
            current_phase = str(phase_name or "").strip().upper()
        try:
            current_turn = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        except (TypeError, ValueError):
            current_turn = 0

        sr["dread_mob_try_dat_button_active"] = True
        sr["dread_mob_try_dat_button_effect"] = str(effect_key)
        sr["dread_mob_try_dat_button_effects"] = list(effect_keys)
        sr["dread_mob_try_dat_button_hazardous"] = bool(hazardous)
        sr["dread_mob_try_dat_button_mode"] = str(mode)
        sr["dread_mob_try_dat_button_roll"] = int(rolled)
        sr["dread_mob_try_dat_button_rolls"] = list(rolled_values)
        sr["dread_mob_try_dat_button_expires_phase"] = str(current_phase)
        sr["dread_mob_try_dat_button_turn"] = int(current_turn)
        sr["dread_mob_try_dat_button_trigger"] = str(trigger or "").strip().lower()
        sr["dread_mob_try_dat_button_source"] = "Try Dat Button!"
        root.special_rules = sr
        return {
            "unit_id": self._unit_root_id(root),
            "unit_name": str(getattr(root, "name", "Unit") or "Unit"),
            "mode": str(mode),
            "effect_key": str(effect_key),
            "effect_keys": list(effect_keys),
            "effect_label": self._dread_mob_effect_label(effect_key),
            "effect_labels": [self._dread_mob_effect_label(key) for key in list(effect_keys or [])],
            "hazardous": bool(hazardous),
            "roll": int(rolled),
            "rolls": list(rolled_values),
            "source": "Try Dat Button!",
            "phase_name": str(current_phase),
        }

    def _dread_mob_try_dat_button_entry(self, attacker_model, *, game=None):
        if not self.is_dread_mob():
            return None
        if attacker_model is None:
            return None
        attacker_unit = getattr(attacker_model, "parent_unit", None)
        if attacker_unit is None:
            return None
        root = self._unit_root(attacker_unit)
        if root is None or not self._unit_belongs_to_army(root):
            return None
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get("dread_mob_try_dat_button_active")):
            return None
        effect_keys = [
            str(value or "").strip().upper()
            for value in list(sr.get("dread_mob_try_dat_button_effects", []) or [])
            if str(value or "").strip()
        ]
        effect_keys = [key for key in effect_keys if key in set(self._DREAD_MOB_BUTTON_EFFECTS)]
        effect_key = str(sr.get("dread_mob_try_dat_button_effect", "") or "").strip().upper()
        if effect_key in set(self._DREAD_MOB_BUTTON_EFFECTS) and effect_key not in effect_keys:
            effect_keys.insert(0, effect_key)
        if not effect_keys:
            return None
        if game is None:
            army = root.get_parent_army() if hasattr(root, "get_parent_army") else None
            player = getattr(army, "player", None) if army is not None else None
            game = getattr(player, "game", None) if player is not None else None
        expected_phase = str(sr.get("dread_mob_try_dat_button_expires_phase", "") or "").strip().upper()
        if expected_phase and game is not None:
            current_phase = self._phase_key_from_game(game)
            if current_phase and current_phase != expected_phase:
                return None
        try:
            effect_turn = int(sr.get("dread_mob_try_dat_button_turn", 0) or 0)
        except (TypeError, ValueError):
            effect_turn = 0
        if effect_turn and game is not None:
            try:
                current_turn = int(getattr(game, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_turn = 0
            if current_turn and current_turn != effect_turn:
                return None
        rolls = [int(value or 0) for value in list(sr.get("dread_mob_try_dat_button_rolls", []) or [])]
        if not rolls:
            first_roll = int(sr.get("dread_mob_try_dat_button_roll", 0) or 0)
            if first_roll:
                rolls = [int(first_roll)]
        return {
            "effect_key": str(effect_keys[0] or ""),
            "effect_keys": list(effect_keys),
            "hazardous": bool(sr.get("dread_mob_try_dat_button_hazardous")),
            "source": str(sr.get("dread_mob_try_dat_button_source", "") or "Try Dat Button!"),
            "rolls": list(rolls),
        }

    def dread_mob_try_dat_button_lethal_hits_applies(self, attacker_model, *, game=None) -> bool:
        entry = self._dread_mob_try_dat_button_entry(attacker_model, game=game)
        if not isinstance(entry, dict):
            return False
        return self._DREAD_MOB_BUTTON_LETHAL in {
            str(value or "").strip().upper() for value in list(entry.get("effect_keys", []) or [])
        }

    def dread_mob_try_dat_button_sustained_hits_value(self, attacker_model, *, game=None) -> int:
        entry = self._dread_mob_try_dat_button_entry(attacker_model, game=game)
        if not isinstance(entry, dict):
            return 0
        if self._DREAD_MOB_BUTTON_SUSTAINED not in {
            str(value or "").strip().upper() for value in list(entry.get("effect_keys", []) or [])
        }:
            return 0
        return 1

    def dread_mob_try_dat_button_critical_wound_ap_bonus(self, attacker_model, attack_instance, *, game=None) -> tuple[int, str]:
        if not isinstance(attack_instance, dict):
            return 0, ""
        if not bool(attack_instance.get("crit_wound", False)):
            return 0, ""
        entry = self._dread_mob_try_dat_button_entry(attacker_model, game=game)
        if not isinstance(entry, dict):
            return 0, ""
        if self._DREAD_MOB_BUTTON_CRIT_AP not in {
            str(value or "").strip().upper() for value in list(entry.get("effect_keys", []) or [])
        }:
            return 0, ""
        source = str(entry.get("source", "") or "Try Dat Button!").strip() or "Try Dat Button!"
        return 2, source

    def dread_mob_try_dat_button_manual_hazardous_applies(self, attacker_model, *, game=None) -> bool:
        entry = self._dread_mob_try_dat_button_entry(attacker_model, game=game)
        if not isinstance(entry, dict):
            return False
        return bool(entry.get("hazardous", False))

    def war_horde_sustained_hits_value(self, unit, *, attack_type: str = "", keyword: str = "ORKS") -> int:
        if not self.is_war_horde():
            return 0
        if unit is None:
            return 0
        if str(attack_type or "").strip().lower() not in ("", "melee"):
            return 0
        if not self._unit_has_keyword_or_faction(unit, keyword, faction_id=self.faction_id):
            return 0
        return 1
