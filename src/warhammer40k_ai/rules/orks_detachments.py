from __future__ import annotations

import re

from .detachment_manager import DetachmentManagerBase
from ..utility.dice import get_roll
from ..utility.entity_ids import get_entity_id


class OrksDetachmentManager(DetachmentManagerBase):
    faction_id = "ORK"
    _SECOND_WAAAGH_NAMED_UNITS = ("nobz", "meganobz")
    _DA_BIG_HUNT_PREY_KEYWORDS = ("MONSTER", "VEHICLE", "CHARACTER")
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

    def __init__(self, army=None):
        super().__init__(army)
        self.da_big_hunt_prey_unit_id: str = ""
        self.da_big_hunt_prey_turn: int = 0
        self.da_big_hunt_prey_owner_id: str = ""

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

    def _da_big_hunt_prey_active(self) -> bool:
        if not self.is_da_big_hunt():
            return False
        return bool(str(self.da_big_hunt_prey_unit_id or "").strip())

    def clear_da_big_hunt_prey(self) -> None:
        self.da_big_hunt_prey_unit_id = ""
        self.da_big_hunt_prey_turn = 0
        self.da_big_hunt_prey_owner_id = ""

    def on_command_phase_start(self, *, game=None, player=None) -> None:
        if not self.is_da_big_hunt():
            return
        if self.army is None:
            self.clear_da_big_hunt_prey()
            return
        army_player = getattr(self.army, "player", None)
        if player is not None and army_player is not None and army_player is not player:
            return
        self.clear_da_big_hunt_prey()

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
        rolled = 0
        hazardous = False
        if mode == "roll":
            rolled = int(get_roll("D6") or 1)
            if rolled < 1:
                rolled = 1
            if rolled > 6:
                rolled = 6
            effect_key = self._dread_mob_effect_from_roll(int(rolled))
        else:
            effect_key = str(dict(payload or {}).get("button_effect", "") or "").strip().upper()
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
        sr["dread_mob_try_dat_button_hazardous"] = bool(hazardous)
        sr["dread_mob_try_dat_button_mode"] = str(mode)
        sr["dread_mob_try_dat_button_roll"] = int(rolled)
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
            "effect_label": self._dread_mob_effect_label(effect_key),
            "hazardous": bool(hazardous),
            "roll": int(rolled),
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
        effect_key = str(sr.get("dread_mob_try_dat_button_effect", "") or "").strip().upper()
        if effect_key not in set(self._DREAD_MOB_BUTTON_EFFECTS):
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
        return {
            "effect_key": effect_key,
            "hazardous": bool(sr.get("dread_mob_try_dat_button_hazardous")),
            "source": str(sr.get("dread_mob_try_dat_button_source", "") or "Try Dat Button!"),
        }

    def dread_mob_try_dat_button_lethal_hits_applies(self, attacker_model, *, game=None) -> bool:
        entry = self._dread_mob_try_dat_button_entry(attacker_model, game=game)
        if not isinstance(entry, dict):
            return False
        return str(entry.get("effect_key", "") or "") == self._DREAD_MOB_BUTTON_LETHAL

    def dread_mob_try_dat_button_sustained_hits_value(self, attacker_model, *, game=None) -> int:
        entry = self._dread_mob_try_dat_button_entry(attacker_model, game=game)
        if not isinstance(entry, dict):
            return 0
        if str(entry.get("effect_key", "") or "") != self._DREAD_MOB_BUTTON_SUSTAINED:
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
        if str(entry.get("effect_key", "") or "") != self._DREAD_MOB_BUTTON_CRIT_AP:
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
