from __future__ import annotations

from ..utility.entity_ids import get_entity_id
from .detachment_manager import DetachmentManagerBase


class GreyKnightsDetachmentManager(DetachmentManagerBase):
    faction_id = "GK"

    def __init__(self, army=None):
        super().__init__(army)
        self._hallowed_ground_phase_key: tuple | None = None
        self._hallowed_ground_nml_active: bool = False
        self._hallowed_ground_enemy_active: bool = False

    def is_brotherhood_strike(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Brotherhood Strike")

    def is_hallowed_conclave(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Hallowed Conclave")

    def is_sanctic_spearhead(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Sanctic Spearhead")

    def is_augurium_task_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Augurium Task Force")

    def is_banishers(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Banishers")

    def is_warpbane_task_force(self) -> bool:
        if not self._army_faction_matches(self.faction_id):
            return False
        return self.detachment_matches("Warpbane Task Force")

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

    def _is_grey_knights_unit(self, unit) -> bool:
        if unit is None:
            return False
        if self._attached_unit_has_keyword(unit, "GREY KNIGHTS"):
            return True
        return self._army_faction_matches(self.faction_id)

    def _is_purifier_squad_unit(self, unit) -> bool:
        if unit is None:
            return False
        if self._attached_unit_has_keyword(unit, "PURIFIER SQUAD"):
            return True
        return "purifier squad" in str(getattr(unit, "name", "") or "").lower()

    def _unit_is_active(self, unit) -> bool:
        if unit is None:
            return False
        fn = getattr(unit, "is_active_for_rules", None)
        if callable(fn):
            return bool(fn())
        is_alive = getattr(unit, "is_alive", None)
        if callable(is_alive) and not is_alive():
            return False
        if not bool(getattr(unit, "deployed", True)):
            return False
        if str(getattr(unit, "reserve_status", "deployed") or "deployed") != "deployed":
            return False
        if bool(getattr(unit, "is_embarked", False)):
            return False
        if getattr(unit, "embarked_in", None) is not None:
            return False
        return True

    def _iter_unique_army_units(self) -> list:
        army = getattr(self, "army", None)
        if army is None:
            return []
        seen: set[str] = set()
        units: list = []
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            unit_id = str(get_entity_id(unit) or "")
            if unit_id and unit_id in seen:
                continue
            if unit_id:
                seen.add(unit_id)
            units.append(unit)
        return units

    def _iter_enemy_roots(self, game, *, owner_player=None) -> list:
        if game is None:
            return []
        enemies: list = []
        seen: set[str] = set()
        for player in list(getattr(game, "players", []) or []):
            if player is None or player is owner_player:
                continue
            army = getattr(player, "army", None)
            if army is None:
                get_army = getattr(player, "get_army", None)
                army = get_army() if callable(get_army) else None
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                if unit is None:
                    continue
                root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
                if root is None:
                    continue
                root_id = str(get_entity_id(root) or "")
                if root_id and root_id in seen:
                    continue
                if root_id:
                    seen.add(root_id)
                if not self._unit_is_active(root):
                    continue
                enemies.append(root)
        enemies.sort(key=lambda unit: str(get_entity_id(unit) or ""))
        return enemies

    def _resolve_member_bearer_model(self, member, *, bearer_keys: tuple[str, ...]) -> object | None:
        if member is None:
            return None
        sr = getattr(member, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        bearer_id = ""
        for key in list(bearer_keys or ()):
            value = str(sr.get(str(key), "") or "").strip()
            if value:
                bearer_id = value
                break
        if not bearer_id:
            bearer_id = str(sr.get("enhancement_bearer_model_id", "") or "").strip()
        models = list(getattr(member, "models", []) or [])
        if bearer_id:
            for model in models:
                if model is None:
                    continue
                model_id = str(get_entity_id(model) or getattr(model, "id", getattr(model, "_id", "")) or "").strip()
                if model_id != bearer_id:
                    continue
                alive_attr = getattr(model, "is_alive", True)
                return model if bool(alive_attr() if callable(alive_attr) else alive_attr) else None
            return None
        for model in models:
            if model is None:
                continue
            alive_attr = getattr(model, "is_alive", True)
            if bool(alive_attr() if callable(alive_attr) else alive_attr):
                return model
        return None

    @staticmethod
    def _phase_name(game) -> str:
        return str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()

    def _is_active_army_player_phase(self, game, *, phase_name: str) -> bool:
        if game is None:
            return False
        if self._phase_name(game) != str(phase_name or "").strip().upper():
            return False
        player = getattr(self.army, "player", None)
        if player is None:
            return False
        current_player = getattr(game, "get_current_player", lambda: None)()
        if current_player is None:
            return False
        return str(getattr(current_player, "id", "") or "") == str(getattr(player, "id", "") or "")

    @staticmethod
    def _pending_choose_quarry_request(
        game,
        *,
        ability: str,
        source_unit_id: str,
        turn: int = 0,
        battle_round: int = 0,
        phase_name: str = "",
    ):
        if game is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return None
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != str(ability or ""):
                continue
            if str(ctx.get("source_unit_id", "") or "") != str(source_unit_id or ""):
                continue
            if phase_name and str(ctx.get("phase_name", "") or "").strip().upper() != str(phase_name).strip().upper():
                continue
            if int(turn or 0) and int(ctx.get("turn", 0) or 0) != int(turn):
                continue
            if int(battle_round or 0) and int(ctx.get("battle_round", 0) or 0) != int(battle_round):
                continue
            return req
        return None

    def _hallowed_ground_phase_key_for_game(self, game) -> tuple:
        try:
            round_num = int(getattr(game, "turn", 0) or 0)
        except Exception:
            round_num = 0
        try:
            phase_name = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        except Exception:
            phase_name = ""
        return (round_num, phase_name)

    def on_phase_start(self, *, game=None) -> None:
        if game is None:
            return
        player = getattr(self.army, "player", None)
        if self.is_warpbane_task_force():
            if player is None:
                return
            phase_key = self._hallowed_ground_phase_key_for_game(game)
            self._hallowed_ground_phase_key = phase_key
            self._hallowed_ground_nml_active = False
            self._hallowed_ground_enemy_active = False
            zones = set()
            if hasattr(game, "_shadow_of_chaos_zones"):
                zones = set(game._shadow_of_chaos_zones(player))
            self._hallowed_ground_nml_active = "nml" in zones
            self._hallowed_ground_enemy_active = "enemy" in zones
        if self.is_banishers():
            self._queue_ephemeral_tome_requests(game=game)
            self._queue_pyresoul_requests(game=game)
        if self.is_augurium_task_force():
            self._queue_grimoire_of_conjunctions_requests(game=game)

    def _queue_ephemeral_tome_requests(self, *, game=None) -> None:
        if not self.is_banishers() or game is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        if not self._is_active_army_player_phase(game, phase_name="SHOOTING_PHASE"):
            return
        player = getattr(self.army, "player", None)
        if player is None:
            return
        turn_now = int(getattr(game, "turn", 0) or 0)
        unit_is_engaged = getattr(game, "_unit_is_engaged_with_enemy", None)

        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        for source_unit in list(self._iter_unique_army_units() or []):
            sr = getattr(source_unit, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_ephemeral_tome", False)):
                continue
            root = self._attached_root(source_unit)
            if root is None or not self._unit_is_active(root):
                continue
            if callable(unit_is_engaged) and bool(unit_is_engaged(root)):
                continue
            source_unit_id = str(get_entity_id(source_unit) or "")
            root_id = str(get_entity_id(root) or "")
            if not source_unit_id or not root_id:
                continue
            if self._pending_choose_quarry_request(
                game,
                ability="grey_knights_banishers_ephemeral_tome",
                source_unit_id=source_unit_id,
                turn=int(turn_now),
                phase_name="SHOOTING_PHASE",
            ):
                continue
            bearer = self._resolve_member_bearer_model(
                source_unit,
                bearer_keys=("enhancement_ephemeral_tome_bearer_model_id",),
            )
            if bool(sr.get("enhancement_ephemeral_tome_requires_bearer_alive", True)) and bearer is None:
                continue
            bearer_model_id = str(
                sr.get("enhancement_ephemeral_tome_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            move_roll = str(sr.get("enhancement_ephemeral_tome_move_roll", "D6") or "D6").strip().upper() or "D6"
            options = [
                DecisionOption.create(
                    f"Use on {getattr(root, 'name', 'Unit')}",
                    payload={"target_unit_id": root_id},
                ),
                DecisionOption.create(
                    "None",
                    payload={"action": "skip", "skip": True},
                ),
            ]
            game.request_decision(
                DecisionRequest.create(
                    DECISION_CHOOSE_QUARRY,
                    (
                        f"The Ephemeral Tome: choose whether {getattr(root, 'name', 'Unit')} makes a Normal move of up to "
                        f"{move_roll}\" and cannot declare a charge this turn."
                    ),
                    player_id=getattr(player, "id", None),
                    options=options,
                    context={
                        "ability": "grey_knights_banishers_ephemeral_tome",
                        "ability_name": "The Ephemeral Tome",
                        "source_unit_id": source_unit_id,
                        "target_unit_id": root_id,
                        "unit_id": source_unit_id,
                        "candidate_unit_ids": [root_id],
                        "move_roll": move_roll,
                        "no_charge_this_turn": bool(sr.get("enhancement_ephemeral_tome_no_charge_this_turn", True)),
                        "phase_name": "SHOOTING_PHASE",
                        "phase": "Shooting phase",
                        "turn_owner_id": str(getattr(player, "id", "") or ""),
                        "turn": int(turn_now or 0),
                        "bearer_model_id": bearer_model_id,
                        "optional": bool(sr.get("enhancement_ephemeral_tome_optional", True)),
                    },
                )
            )

    def _queue_pyresoul_requests(self, *, game=None) -> None:
        if not self.is_banishers() or game is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        if not self._is_active_army_player_phase(game, phase_name="SHOOTING_PHASE"):
            return
        player = getattr(self.army, "player", None)
        if player is None:
            return
        turn_now = int(getattr(game, "turn", 0) or 0)

        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        for source_unit in list(self._iter_unique_army_units() or []):
            sr = getattr(source_unit, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_pyresoul", False)):
                continue
            root = self._attached_root(source_unit)
            if root is None or not self._unit_is_active(root):
                continue
            source_unit_id = str(get_entity_id(source_unit) or "")
            if not source_unit_id:
                continue
            if self._pending_choose_quarry_request(
                game,
                ability="grey_knights_banishers_pyresoul",
                source_unit_id=source_unit_id,
                turn=int(turn_now),
                phase_name="SHOOTING_PHASE",
            ):
                continue
            bearer = self._resolve_member_bearer_model(
                source_unit,
                bearer_keys=("enhancement_pyresoul_bearer_model_id",),
            )
            if bool(sr.get("enhancement_pyresoul_requires_bearer_alive", True)) and bearer is None:
                continue
            bearer_model_id = str(
                sr.get("enhancement_pyresoul_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            range_value = int(sr.get("enhancement_pyresoul_range", 24) or 24)
            requires_visibility = bool(sr.get("enhancement_pyresoul_requires_visibility", True))
            candidates: list = []
            for enemy_root in list(self._iter_enemy_roots(game, owner_player=player) or []):
                if bearer is None:
                    continue
                in_range_fn = getattr(game, "_unit_within_range_of_model", None)
                if callable(in_range_fn):
                    if not bool(in_range_fn(bearer, enemy_root, range_value=float(range_value))):
                        continue
                if requires_visibility:
                    can_see_fn = getattr(game, "_model_can_see_unit", None)
                    if callable(can_see_fn):
                        if not bool(can_see_fn(bearer, enemy_root, game_map=getattr(game, "map", None))):
                            continue
                candidates.append(enemy_root)
            if not candidates:
                continue
            options = [DecisionOption.create("None", payload={"action": "skip", "skip": True})]
            candidate_ids: list[str] = []
            for enemy_root in list(candidates or []):
                enemy_id = str(get_entity_id(enemy_root) or "")
                if not enemy_id:
                    continue
                candidate_ids.append(enemy_id)
                options.append(
                    DecisionOption.create(
                        str(getattr(enemy_root, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": enemy_id},
                    )
                )
            if len(options) <= 1:
                continue
            game.request_decision(
                DecisionRequest.create(
                    DECISION_CHOOSE_QUARRY,
                    "Pyresoul: select one visible enemy unit within 24\" to suffer D3 mortal wounds (or None).",
                    player_id=getattr(player, "id", None),
                    options=options,
                    context={
                        "ability": "grey_knights_banishers_pyresoul",
                        "ability_name": "Pyresoul",
                        "phase_name": "SHOOTING_PHASE",
                        "phase": "Shooting phase",
                        "source_unit_id": source_unit_id,
                        "unit_id": source_unit_id,
                        "model_id": bearer_model_id,
                        "range": int(range_value),
                        "requires_visibility": bool(requires_visibility),
                        "mortal_wounds_roll": str(sr.get("enhancement_pyresoul_mortal_wounds_roll", "D3") or "D3"),
                        "candidate_unit_ids": list(candidate_ids),
                        "optional": bool(sr.get("enhancement_pyresoul_optional", True)),
                        "turn_owner_id": str(getattr(player, "id", "") or ""),
                        "turn": int(turn_now or 0),
                    },
                )
            )

    def _queue_grimoire_of_conjunctions_requests(self, *, game=None) -> None:
        if not self.is_augurium_task_force() or game is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        if self._phase_name(game) != "FIGHT_PHASE":
            return
        player = getattr(self.army, "player", None)
        if player is None:
            return
        try:
            turn_now = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn_now = 0

        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        for source_unit in list(self._iter_unique_army_units() or []):
            sr = getattr(source_unit, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_grimoire_of_conjunctions", False)):
                continue
            root = self._attached_root(source_unit)
            if root is None or not self._unit_is_active(root):
                continue
            source_unit_id = str(get_entity_id(source_unit) or "")
            root_id = str(get_entity_id(root) or "")
            if not source_unit_id or not root_id:
                continue
            once_key = str(
                sr.get("enhancement_grimoire_of_conjunctions_once_key", "") or "grimoire_of_conjunctions"
            ).strip().lower() or "grimoire_of_conjunctions"
            used_once = getattr(source_unit, "has_used_unit_once_per_battle", None)
            if callable(used_once) and bool(used_once(once_key)):
                continue
            if self._pending_choose_quarry_request(
                game,
                ability="grey_knights_augurium_grimoire_of_conjunctions",
                source_unit_id=source_unit_id,
                turn=int(turn_now),
                phase_name="FIGHT_PHASE",
            ):
                continue
            bearer = self._resolve_member_bearer_model(
                source_unit,
                bearer_keys=("enhancement_grimoire_of_conjunctions_bearer_model_id",),
            )
            if bool(sr.get("enhancement_grimoire_of_conjunctions_requires_bearer_alive", True)) and bearer is None:
                continue
            bearer_model_id = str(
                sr.get("enhancement_grimoire_of_conjunctions_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            options = [
                DecisionOption.create(
                    f"Use on {getattr(root, 'name', 'Unit')}",
                    payload={"target_unit_id": root_id},
                ),
                DecisionOption.create(
                    "None",
                    payload={"action": "skip", "skip": True},
                ),
            ]
            game.request_decision(
                DecisionRequest.create(
                    DECISION_CHOOSE_QUARRY,
                    (
                        f"Grimoire of Conjunctions: choose whether {getattr(root, 'name', 'Unit')} gains "
                        "the bearer's +4 Strength melee bonus this phase."
                    ),
                    player_id=getattr(player, "id", None),
                    options=options,
                    context={
                        "ability": "grey_knights_augurium_grimoire_of_conjunctions",
                        "ability_name": "Grimoire of Conjunctions",
                        "source_unit_id": source_unit_id,
                        "target_unit_id": root_id,
                        "unit_id": source_unit_id,
                        "candidate_unit_ids": [root_id],
                        "phase_name": "FIGHT_PHASE",
                        "phase": "Fight phase",
                        "turn": int(turn_now or 0),
                        "once_key": once_key,
                        "bearer_model_id": bearer_model_id,
                        "optional": True,
                    },
                )
            )

    def on_battle_round_start(self, battle_round: int, *, game=None) -> None:
        if not self.is_augurium_task_force() or game is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        player = getattr(self.army, "player", None)
        if player is None:
            return
        try:
            round_now = int(battle_round or 0)
        except Exception:
            round_now = 0

        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        for source_unit in list(self._iter_unique_army_units() or []):
            sr = getattr(source_unit, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_shield_of_prophecy", False)):
                continue
            root = self._attached_root(source_unit)
            if root is None or not self._unit_is_active(root):
                continue
            source_unit_id = str(get_entity_id(source_unit) or "")
            root_id = str(get_entity_id(root) or "")
            if not source_unit_id or not root_id:
                continue
            once_key = str(
                sr.get("enhancement_shield_of_prophecy_once_key", "") or "shield_of_prophecy"
            ).strip().lower() or "shield_of_prophecy"
            used_once = getattr(source_unit, "has_used_unit_once_per_battle", None)
            if callable(used_once) and bool(used_once(once_key)):
                continue
            if self._pending_choose_quarry_request(
                game,
                ability="grey_knights_augurium_shield_of_prophecy",
                source_unit_id=source_unit_id,
                battle_round=int(round_now),
            ):
                continue
            bearer = self._resolve_member_bearer_model(
                source_unit,
                bearer_keys=("enhancement_shield_of_prophecy_bearer_model_id",),
            )
            if bool(sr.get("enhancement_shield_of_prophecy_requires_bearer_alive", True)) and bearer is None:
                continue
            bearer_model_id = str(
                sr.get("enhancement_shield_of_prophecy_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            options = [
                DecisionOption.create(
                    f"Use on {getattr(root, 'name', 'Unit')}",
                    payload={"target_unit_id": root_id},
                ),
                DecisionOption.create(
                    "None",
                    payload={"action": "skip", "skip": True},
                ),
            ]
            game.request_decision(
                DecisionRequest.create(
                    DECISION_CHOOSE_QUARRY,
                    (
                        f"Shield of Prophecy: choose whether {getattr(root, 'name', 'Unit')} gains "
                        "+2 Toughness until the end of the battle round."
                    ),
                    player_id=getattr(player, "id", None),
                    options=options,
                    context={
                        "ability": "grey_knights_augurium_shield_of_prophecy",
                        "ability_name": "Shield of Prophecy",
                        "source_unit_id": source_unit_id,
                        "target_unit_id": root_id,
                        "unit_id": source_unit_id,
                        "candidate_unit_ids": [root_id],
                        "battle_round": int(round_now or 0),
                        "turn": int(round_now or 0),
                        "once_key": once_key,
                        "bearer_model_id": bearer_model_id,
                        "optional": True,
                    },
                )
            )

    def shield_of_prophecy_toughness_bonus(self, model, *, unit=None, game=None) -> tuple[int, str]:
        if not self.is_augurium_task_force():
            return 0, ""
        source_unit = unit
        if source_unit is None and model is not None:
            source_unit = getattr(model, "parent_unit", None)
        root = self._attached_root(source_unit)
        if root is None:
            return 0, ""
        game_obj = game
        if game_obj is None:
            player = getattr(self.army, "player", None)
            game_obj = getattr(player, "game", None) if player is not None else None
        try:
            current_round = int(getattr(game_obj, "turn", 0) or 0) if game_obj is not None else 0
        except Exception:
            current_round = 0
        members = list(root.get_attached_unit_members() or []) if hasattr(root, "get_attached_unit_members") else [root]
        if not members:
            members = [root]
        for member in list(members or []):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_shield_of_prophecy_active", False)):
                continue
            try:
                effect_round = int(sr.get("enhancement_shield_of_prophecy_battle_round", 0) or 0)
            except Exception:
                effect_round = 0
            if effect_round and current_round and effect_round != current_round:
                continue
            try:
                bonus = int(sr.get("enhancement_shield_of_prophecy_bearer_unit_toughness_bonus", 2) or 2)
            except Exception:
                bonus = 2
            if bonus <= 0:
                continue
            source_name = str(
                sr.get("enhancement_shield_of_prophecy_active_source", "")
                or sr.get("enhancement_shield_of_prophecy_source", "")
                or "Shield of Prophecy"
            ).strip() or "Shield of Prophecy"
            return int(bonus), source_name
        return 0, ""

    def on_unit_set_up(
        self,
        unit,
        *,
        game=None,
        set_up_as_reinforcements: bool = False,
        used_deep_strike: bool = False,
    ) -> None:
        _ = used_deep_strike
        if game is None or unit is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        if not bool(set_up_as_reinforcements):
            return
        if not self.is_augurium_task_force():
            return
        root = self._attached_root(unit)
        if root is None or not self._unit_is_active(root):
            return
        player = getattr(self.army, "player", None)
        if player is None:
            return
        try:
            turn_now = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn_now = 0
        phase_name = self._phase_name(game)

        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        members = list(root.get_attached_unit_members() or []) if hasattr(root, "get_attached_unit_members") else [root]
        if not members:
            members = [root]
        for source_unit in list(members or []):
            sr = getattr(source_unit, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_doomseers_amulet", False)):
                continue
            source_unit_id = str(get_entity_id(source_unit) or "")
            if not source_unit_id:
                continue
            if self._pending_choose_quarry_request(
                game,
                ability="phase_select_enemy_battleshock",
                source_unit_id=source_unit_id,
                turn=int(turn_now),
                phase_name=phase_name,
            ):
                continue
            bearer = self._resolve_member_bearer_model(
                source_unit,
                bearer_keys=("enhancement_doomseers_amulet_bearer_model_id",),
            )
            if bool(sr.get("enhancement_doomseers_amulet_requires_bearer_alive", True)) and bearer is None:
                continue
            bearer_model_id = str(
                sr.get("enhancement_doomseers_amulet_bearer_model_id", "")
                or sr.get("enhancement_bearer_model_id", "")
                or ""
            ).strip()
            try:
                range_value = int(sr.get("enhancement_doomseers_amulet_range", 12) or 12)
            except Exception:
                range_value = 12
            try:
                test_penalty = int(sr.get("enhancement_doomseers_amulet_test_penalty", 1) or 1)
            except Exception:
                test_penalty = 1
            requires_visibility = bool(sr.get("enhancement_doomseers_amulet_requires_visibility", True))
            candidates: list = []
            for enemy_root in list(self._iter_enemy_roots(game, owner_player=player) or []):
                if bearer is None:
                    continue
                in_range_fn = getattr(game, "_unit_within_range_of_model", None)
                if callable(in_range_fn):
                    if not bool(in_range_fn(bearer, enemy_root, range_value=float(range_value))):
                        continue
                if requires_visibility:
                    can_see_fn = getattr(game, "_model_can_see_unit", None)
                    if callable(can_see_fn):
                        if not bool(can_see_fn(bearer, enemy_root, game_map=getattr(game, "map", None))):
                            continue
                candidates.append(enemy_root)
            if not candidates:
                continue
            options = [DecisionOption.create("None", payload={"action": "skip", "skip": True})]
            candidate_ids: list[str] = []
            for enemy_root in list(candidates or []):
                enemy_id = str(get_entity_id(enemy_root) or "")
                if not enemy_id:
                    continue
                candidate_ids.append(enemy_id)
                options.append(
                    DecisionOption.create(
                        str(getattr(enemy_root, "name", "Unit") or "Unit"),
                        payload={"target_unit_id": enemy_id},
                    )
                )
            if len(options) <= 1:
                continue
            game.request_decision(
                DecisionRequest.create(
                    DECISION_CHOOSE_QUARRY,
                    "Doomseer's Amulet: select one visible enemy unit within 12\" to take a Battle-shock test (or None).",
                    player_id=getattr(player, "id", None),
                    options=options,
                    context={
                        "ability": "phase_select_enemy_battleshock",
                        "ability_name": "Doomseer's Amulet",
                        "ability_key": "doomseers_amulet",
                        "phase_name": phase_name,
                        "phase": phase_name.replace("_", " ").title(),
                        "source_unit_id": source_unit_id,
                        "unit_id": source_unit_id,
                        "model_id": bearer_model_id,
                        "range": int(range_value),
                        "test_penalty": int(max(0, test_penalty)),
                        "requires_visibility": bool(requires_visibility),
                        "candidate_unit_ids": list(candidate_ids),
                        "optional": bool(sr.get("enhancement_doomseers_amulet_optional", True)),
                        "once_per_turn": False,
                        "turn": int(turn_now or 0),
                    },
                )
            )

    def _active_hallowed_ground_zones(self, game) -> set[str]:
        zones = {"own"}
        if game is None:
            return zones
        phase_key = self._hallowed_ground_phase_key_for_game(game)
        if self._hallowed_ground_phase_key == phase_key:
            if self._hallowed_ground_nml_active:
                zones.add("nml")
            if self._hallowed_ground_enemy_active:
                zones.add("enemy")
        return zones

    def _iter_purifier_units(self) -> list:
        army = getattr(self, "army", None)
        if army is None:
            return []
        seen: set[str] = set()
        sources: list = []
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
            if root is None:
                continue
            rid = get_entity_id(root)
            if rid in seen:
                continue
            seen.add(rid)
            if not self._is_purifier_squad_unit(root):
                continue
            if not self._unit_is_active(root):
                continue
            sources.append(root)
        return sources

    def _model_is_within_hallowed_ground(
        self,
        model,
        *,
        game,
        player,
        opponent,
        zones: set[str],
        purifier_units: list,
    ) -> bool:
        if model is None:
            return False
        if not getattr(model, "is_alive", True):
            return False
        if not hasattr(model, "get_location"):
            return False
        location = model.get_location()
        if location is None or len(location) < 2:
            return False
        x = float(location[0])
        y = float(location[1])
        base = getattr(model, "model_base", None)
        if base is None:
            return False

        in_own = game.is_position_wholly_in_deployment_zone(x, y, base, player.id)
        in_enemy = False
        if opponent is not None:
            in_enemy = game.is_position_wholly_in_deployment_zone(x, y, base, opponent.id)

        if in_own and "own" in zones:
            return True
        if in_enemy and "enemy" in zones:
            return True
        if (not in_own and not in_enemy) and "nml" in zones:
            return True

        from ..utility.aura_utils import model_wholly_within_range_of_unit

        for source in purifier_units:
            if model_wholly_within_range_of_unit(source, model, 6.0, use_attached_aggregate=True):
                return True
        return False

    def _paragon_treat_as_within_hallowed_ground_active(self, unit, *, game=None) -> bool:
        if unit is None:
            return False
        if game is None:
            player = getattr(self.army, "player", None)
            if player is not None:
                game = getattr(player, "game", None)
        if game is None:
            return False
        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False
        if not bool(sr.get("paragon_of_sanctity_hallowed_ground_active", False)):
            return False
        try:
            effect_turn = int(sr.get("paragon_of_sanctity_hallowed_ground_turn", 0) or 0)
        except Exception:
            effect_turn = 0
        effect_phase = str(sr.get("paragon_of_sanctity_hallowed_ground_phase", "") or "").strip().upper()
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        current_phase = str(getattr(getattr(game, "phase", None), "name", "") or "").strip().upper()
        return bool(effect_turn == current_turn and effect_phase and effect_phase == current_phase)

    def model_wholly_within_hallowed_ground(self, model, *, game=None) -> bool:
        if not self.is_warpbane_task_force():
            return False
        if model is None:
            return False
        player = getattr(self.army, "player", None)
        if player is None:
            return False
        if game is None:
            game = getattr(player, "game", None)
        if game is None:
            return False
        opponent = next((p for p in (getattr(game, "players", None) or []) if p is not player), None)
        zones = self._active_hallowed_ground_zones(game)
        purifier_units = self._iter_purifier_units()
        return self._model_is_within_hallowed_ground(
            model,
            game=game,
            player=player,
            opponent=opponent,
            zones=zones,
            purifier_units=purifier_units,
        )

    def unit_within_hallowed_ground(self, unit, *, game=None) -> bool:
        if not self.is_warpbane_task_force():
            return False
        if self.unit_wholly_within_hallowed_ground(unit, game=game):
            return True
        return self._paragon_treat_as_within_hallowed_ground_active(unit, game=game)

    def unit_wholly_within_hallowed_ground(self, unit, *, game=None) -> bool:
        if not self.is_warpbane_task_force():
            return False
        if unit is None:
            return False
        player = getattr(self.army, "player", None)
        if player is None:
            return False
        if game is None:
            game = getattr(player, "game", None)
        if game is None:
            return False
        opponent = next((p for p in (getattr(game, "players", None) or []) if p is not player), None)
        zones = self._active_hallowed_ground_zones(game)

        root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
        if root is None:
            return False
        if hasattr(root, "get_attached_unit_models"):
            models = list(root.get_attached_unit_models() or [])
        else:
            models = list(getattr(root, "models", []) or [])
        if not models:
            return False

        purifier_units = self._iter_purifier_units()

        for model in models:
            if not self._model_is_within_hallowed_ground(
                model,
                game=game,
                player=player,
                opponent=opponent,
                zones=zones,
                purifier_units=purifier_units,
            ):
                return False
        return True

    def hallowed_ground_hit_reroll_mods(
        self,
        attacker_model,
        target_unit,
        *,
        attack_type: str = "any",
        game=None,
        game_map=None,
        target_visible: bool | None = None,
    ) -> dict:
        if not self.is_warpbane_task_force():
            return {}
        unit = getattr(attacker_model, "parent_unit", None)
        if unit is None or not self._is_grey_knights_unit(unit):
            return {}
        atype = str(attack_type or "").strip().lower()
        if atype not in ("melee", "ranged"):
            return {}
        if atype == "ranged":
            if target_visible is False:
                return {}
            if target_visible is None:
                if game_map is not None and hasattr(unit, "_has_line_of_sight_to_target"):
                    target_visible = bool(unit._has_line_of_sight_to_target(attacker_model, target_unit, game_map))
                else:
                    target_visible = False
            if not target_visible:
                return {}

        if game is None:
            player = getattr(self.army, "player", None)
            game = getattr(player, "game", None) if player is not None else None

        reroll_values = {1}
        reroll_reasons = ["Hallowed Ground: re-roll Hit rolls of 1"]
        reroll_full = False
        reroll_full_reasons: list[str] = []
        if self._is_purifier_squad_unit(unit) or self.unit_wholly_within_hallowed_ground(unit, game=game):
            reroll_full = True
            reroll_full_reasons.append("Hallowed Ground: re-roll Hit roll")

        return {
            "reroll_values": tuple(sorted(reroll_values)),
            "reroll_reasons": tuple(reroll_reasons),
            "reroll_full": bool(reroll_full),
            "reroll_full_reasons": tuple(reroll_full_reasons),
        }

    def duty_before_all_applies(self, unit) -> bool:
        if not self.is_hallowed_conclave():
            return False
        if unit is None:
            return False
        return self._attached_unit_has_keyword(unit, "GREY KNIGHTS") and self._attached_unit_has_keyword(unit, "TERMINATOR")

    def fury_of_titan_applies(self, unit, *, used_deep_strike: bool = False) -> bool:
        if not self.is_brotherhood_strike():
            return False
        if unit is None or not used_deep_strike:
            return False
        return True

    def apply_fury_of_titan(self, unit) -> bool:
        if unit is None:
            return False
        if not self.is_brotherhood_strike():
            return False
        try:
            root = unit.get_attached_unit_root()
        except Exception:
            root = unit
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        for member in members:
            try:
                sr = getattr(member, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["fury_of_titan_active"] = True
                sr["fury_of_titan_expires_phase"] = "FIGHT_PHASE"
                member.special_rules = sr
            except Exception:
                continue
        return True

    @staticmethod
    def _normalize_channelled_force_choice(choice: str) -> str:
        raw = str(choice or "").strip().upper().replace("-", "_").replace(" ", "_")
        if raw in {"LETHAL", "LETHAL_HITS", "LETHALHITS"}:
            return "LETHAL_HITS"
        if raw in {"SUSTAINED", "SUSTAINED_HITS", "SUSTAINED_HITS_1", "SUSTAINEDHITS1"}:
            return "SUSTAINED_HITS_1"
        return raw

    def _attached_root(self, unit):
        if unit is None:
            return None
        try:
            return unit.get_attached_unit_root()
        except Exception:
            return unit

    def _channelled_force_root_is_eligible(self, unit) -> bool:
        if not self.is_banishers():
            return False
        root = self._attached_root(unit)
        if root is None:
            return False
        try:
            if root.get_parent_army() is not self.army:
                return False
        except Exception:
            return False
        if not self._is_grey_knights_unit(root):
            return False
        if not self._unit_is_active(root):
            return False
        return True

    def banishers_sigil_of_the_hunt_hit_reroll_mods(self, attacker_model, *, attack_type: str = "any", game=None) -> dict:
        if not self.is_banishers():
            return {}
        if str(attack_type or "").strip().lower() != "ranged":
            return {}
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._attached_root(unit)
        if root is None or not self._channelled_force_root_is_eligible(root):
            return {}
        game_obj = game
        if game_obj is None:
            player = getattr(self.army, "player", None)
            game_obj = getattr(player, "game", None) if player is not None else None
        if not self._is_active_army_player_phase(game_obj, phase_name="SHOOTING_PHASE"):
            return {}
        members = list(root.get_attached_unit_members() or []) if hasattr(root, "get_attached_unit_members") else [root]
        if not members:
            members = [root]
        for member in list(members or []):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_sigil_of_the_hunt", False)):
                continue
            if bool(sr.get("enhancement_sigil_of_the_hunt_requires_bearer_alive", True)):
                bearer = self._resolve_member_bearer_model(
                    member,
                    bearer_keys=("enhancement_sigil_of_the_hunt_bearer_model_id",),
                )
                if bearer is None:
                    continue
            source_name = str(
                sr.get("enhancement_sigil_of_the_hunt_source", "") or "Sigil of the Hunt"
            ).strip() or "Sigil of the Hunt"
            return {
                "reroll_values": (1,),
                "reroll_reasons": (f"{source_name}: re-roll Hit rolls of 1",),
            }
        return {}

    def banishers_sixty_sixth_seal_ap_bonus(
        self,
        attacker_model,
        *,
        target_unit=None,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        _ = target_unit
        if not self.is_banishers():
            return 0, ""
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._attached_root(unit)
        if root is None or not self._channelled_force_root_is_eligible(root):
            return 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is None or not bool(getattr(parent, "is_ranged", lambda: False)()):
                return 0, ""
        game_obj = game
        if game_obj is None:
            player = getattr(self.army, "player", None)
            game_obj = getattr(player, "game", None) if player is not None else None
        if not self._is_active_army_player_phase(game_obj, phase_name="SHOOTING_PHASE"):
            return 0, ""
        members = list(root.get_attached_unit_members() or []) if hasattr(root, "get_attached_unit_members") else [root]
        if not members:
            members = [root]
        for member in list(members or []):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_sixty_sixth_seal", False)):
                continue
            if bool(sr.get("enhancement_sixty_sixth_seal_requires_bearer_alive", True)):
                bearer = self._resolve_member_bearer_model(
                    member,
                    bearer_keys=("enhancement_sixty_sixth_seal_bearer_model_id",),
                )
                if bearer is None:
                    continue
            bonus = int(sr.get("enhancement_sixty_sixth_seal_ap_bonus", 1) or 1)
            if bonus <= 0:
                continue
            source_name = str(
                sr.get("enhancement_sixty_sixth_seal_source", "") or "The Sixty-sixth Seal"
            ).strip() or "The Sixty-sixth Seal"
            return int(bonus), source_name
        return 0, ""

    def mailed_fist_applies(self, unit) -> bool:
        if not self.is_sanctic_spearhead():
            return False
        root = self._attached_root(unit)
        if root is None:
            return False
        try:
            if root.get_parent_army() is not self.army:
                return False
        except Exception:
            return False
        if not self._attached_unit_has_keyword(root, "GREY KNIGHTS"):
            return False
        if not self._attached_unit_has_keyword(root, "VEHICLE"):
            return False
        return True

    def mailed_fist_advance_no_roll_effect(self, unit) -> dict | None:
        if not self.mailed_fist_applies(unit):
            return None
        return {
            "distance": 6,
            "source": "Mailed Fist",
            "tag": "detachment:mailed_fist",
            "expires_phase": "MOVEMENT_PHASE",
        }

    def mailed_fist_assault_applies(self, unit, weapon_profile=None, *, game=None) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        if not self.mailed_fist_applies(root):
            return False
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is None or not bool(getattr(parent, "is_ranged", lambda: False)()):
                return False
        round_state = getattr(root, "round_state", None)
        if not bool(getattr(round_state, "advanced_this_round", False)):
            return False
        game_obj = game
        if game_obj is None:
            army_player = getattr(self.army, "player", None)
            game_obj = getattr(army_player, "game", None) if army_player is not None else None
        if game_obj is not None:
            current = getattr(game_obj, "get_current_player", lambda: None)()
            current_owner = str(getattr(current, "id", "") or "")
            owner_id = str(getattr(getattr(self.army, "player", None), "id", "") or "")
            if owner_id and current_owner and current_owner != owner_id:
                return False
        return True

    def channelled_force_has_psychic_melee_weapons(self, unit) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        get_models = getattr(root, "get_attached_unit_models", None)
        if callable(get_models):
            models = list(get_models() or [])
        else:
            models = list(getattr(root, "models", []) or [])
        try:
            models = sorted(models, key=lambda m: str(get_entity_id(m) or ""))
        except Exception:
            models = list(models)
        for model in list(models or []):
            if model is None or not bool(getattr(model, "is_alive", True)):
                continue
            for wargear in list(getattr(model, "wargear", []) or []):
                if wargear is None:
                    continue
                is_melee = getattr(wargear, "is_melee", None)
                if not callable(is_melee) or not bool(is_melee()):
                    continue
                profiles = getattr(wargear, "profiles", None)
                if isinstance(profiles, dict):
                    profile_values = list(profiles.values())
                else:
                    profile_values = []
                for profile in list(profile_values or []):
                    if profile is None:
                        continue
                    is_psychic = getattr(profile, "is_psychic", None)
                    if callable(is_psychic) and bool(is_psychic()):
                        return True
        return False

    def channelled_force_applies(self, unit, *, game=None) -> bool:
        _ = game
        if not self._channelled_force_root_is_eligible(unit):
            return False
        return True

    def clear_channelled_force_state(self, unit) -> None:
        root = self._attached_root(unit)
        if root is None:
            return
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return
        for key in (
            "channelled_force_lethal_hits_active",
            "channelled_force_sustained_hits_active",
            "channelled_force_expires_phase",
            "channelled_force_turn",
            "channelled_force_turn_owner",
            "channelled_force_source",
        ):
            sr.pop(key, None)
        root.special_rules = sr

    def apply_channelled_force_choice(self, unit, choice: str, *, game=None, player=None) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        if not self._channelled_force_root_is_eligible(root):
            return False
        choice_key = self._normalize_channelled_force_choice(choice)
        if choice_key not in {"LETHAL_HITS", "SUSTAINED_HITS_1"}:
            return False
        game_obj = game
        if game_obj is None:
            army_player = getattr(self.army, "player", None)
            game_obj = getattr(army_player, "game", None) if army_player is not None else None
        try:
            turn_now = int(getattr(game_obj, "turn", 0) or 0) if game_obj is not None else 0
        except Exception:
            turn_now = 0
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id and game_obj is not None:
            current = getattr(game_obj, "get_current_player", lambda: None)()
            owner_id = str(getattr(current, "id", "") or "")
        if not owner_id:
            owner_id = str(getattr(getattr(self.army, "player", None), "id", "") or "")
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        if choice_key == "LETHAL_HITS":
            sr["channelled_force_lethal_hits_active"] = True
        elif choice_key == "SUSTAINED_HITS_1":
            sr["channelled_force_sustained_hits_active"] = True
        sr["channelled_force_expires_phase"] = "FIGHT_PHASE"
        sr["channelled_force_turn"] = int(turn_now or 0)
        sr["channelled_force_turn_owner"] = owner_id
        sr["channelled_force_source"] = "Channelled Force"
        root.special_rules = sr
        return True

    def channelled_force_bonus(self, attacker_model, *, weapon_profile=None, game=None) -> tuple[bool, int, str]:
        if attacker_model is None:
            return False, 0, ""
        unit = getattr(attacker_model, "parent_unit", None)
        root = self._attached_root(unit)
        if root is None:
            return False, 0, ""
        if not self._channelled_force_root_is_eligible(root):
            return False, 0, ""
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            if parent is None or not bool(getattr(parent, "is_melee", lambda: False)()):
                return False, 0, ""
            is_psychic = getattr(weapon_profile, "is_psychic", None)
            if not callable(is_psychic) or not bool(is_psychic()):
                return False, 0, ""
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            return False, 0, ""
        lethal = bool(sr.get("channelled_force_lethal_hits_active"))
        sustained = bool(sr.get("channelled_force_sustained_hits_active"))
        if not lethal and not sustained:
            return False, 0, ""
        game_obj = game
        if game_obj is None:
            army_player = getattr(self.army, "player", None)
            game_obj = getattr(army_player, "game", None) if army_player is not None else None
        if game_obj is not None:
            exp = str(sr.get("channelled_force_expires_phase", "") or "").strip().upper()
            if exp:
                phase_name = str(getattr(getattr(game_obj, "phase", None), "name", "") or "").strip().upper()
                if phase_name and phase_name != exp:
                    return False, 0, ""
            owner_id = str(sr.get("channelled_force_turn_owner", "") or "")
            if owner_id:
                current = getattr(game_obj, "get_current_player", lambda: None)()
                current_owner = str(getattr(current, "id", "") or "")
                if current_owner and current_owner != owner_id:
                    return False, 0, ""
            try:
                effect_turn = int(sr.get("channelled_force_turn", 0) or 0)
            except Exception:
                effect_turn = 0
            try:
                current_turn = int(getattr(game_obj, "turn", 0) or 0)
            except Exception:
                current_turn = 0
            if effect_turn and current_turn and effect_turn != current_turn:
                return False, 0, ""
        source = str(sr.get("channelled_force_source", "") or "Channelled Force").strip() or "Channelled Force"
        return bool(lethal), (1 if sustained else 0), source
