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
        self._hallowed_conclave_fall_back_candidates: dict[str, list[dict[str, str]]] = {}

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

    def _brotherhood_strike_used_deep_strike_setup(
        self,
        unit,
        *,
        set_up_as_reinforcements: bool = False,
        used_deep_strike: bool = False,
    ) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        used_deep_strike_setup = bool(used_deep_strike)
        if not used_deep_strike_setup and bool(set_up_as_reinforcements):
            has_deep_strike = getattr(root, "has_deep_strike", None)
            if callable(has_deep_strike):
                used_deep_strike_setup = bool(has_deep_strike())
        return bool(used_deep_strike_setup)

    def _brotherhood_strike_enhancement_source_member(
        self,
        unit,
        *,
        flag_key: str,
        bearer_keys: tuple[str, ...],
        require_bearer_alive: bool = True,
    ):
        if not self.is_brotherhood_strike():
            return None, None, None, None
        root = self._attached_root(unit)
        if root is None or not self._unit_is_active(root):
            return None, None, None, None
        try:
            if root.get_parent_army() is not self.army:
                return None, None, None, None
        except Exception:
            return None, None, None, None
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for member in list(members or []):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(str(flag_key), False)):
                continue
            bearer = self._resolve_member_bearer_model(member, bearer_keys=bearer_keys)
            if require_bearer_alive and bearer is None:
                continue
            return root, member, sr, bearer
        return None, None, None, None

    def _brotherhood_strike_turn_context(self, game) -> tuple[str, int]:
        owner_id = ""
        turn_now = 0
        if game is None:
            return owner_id, turn_now
        current_player = getattr(game, "get_current_player", lambda: None)()
        owner_id = str(getattr(current_player, "id", "") or "")
        if not owner_id:
            player = getattr(self.army, "player", None)
            owner_id = str(getattr(player, "id", "") or "")
        try:
            turn_now = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn_now = 0
        return owner_id, turn_now

    def _hallowed_conclave_enhancement_source_member(
        self,
        unit,
        *,
        flag_key: str,
        bearer_keys: tuple[str, ...],
        require_bearer_alive: bool = True,
    ):
        if not self.is_hallowed_conclave():
            return None, None, None, None
        root = self._attached_root(unit)
        if root is None or not self._unit_is_active(root):
            return None, None, None, None
        try:
            if root.get_parent_army() is not self.army:
                return None, None, None, None
        except Exception:
            return None, None, None, None
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for member in list(members or []):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(str(flag_key), False)):
                continue
            bearer = self._resolve_member_bearer_model(member, bearer_keys=bearer_keys)
            if require_bearer_alive and bearer is None:
                continue
            return root, member, sr, bearer
        return None, None, None, None

    def _sanctic_spearhead_enhancement_source_member(
        self,
        unit,
        *,
        flag_key: str,
        bearer_keys: tuple[str, ...],
        require_bearer_alive: bool = True,
    ):
        if not self.is_sanctic_spearhead():
            return None, None, None, None
        root = self._attached_root(unit)
        if root is None or not self._unit_is_active(root):
            return None, None, None, None
        try:
            if root.get_parent_army() is not self.army:
                return None, None, None, None
        except Exception:
            return None, None, None, None
        try:
            members = list(root.get_attached_unit_members() or [])
        except Exception:
            members = [root]
        if not members:
            members = [root]
        for member in list(members or []):
            sr = getattr(member, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get(str(flag_key), False)):
                continue
            bearer = self._resolve_member_bearer_model(member, bearer_keys=bearer_keys)
            if require_bearer_alive and bearer is None:
                continue
            return root, member, sr, bearer
        return None, None, None, None

    def _pending_hallowed_inescapable_judgement_request(
        self,
        game,
        *,
        source_unit_id: str,
        moving_unit_id: str,
        turn: int,
    ) -> bool:
        if game is None:
            return False
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        for req in list(queue.list() or []):
            if str(getattr(req, "decision_type", "") or "") != "CHOOSE_QUARRY":
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("ability", "") or "") != "grey_knights_hallowed_inescapable_judgement":
                continue
            if str(ctx.get("source_unit_id", "") or "") != str(source_unit_id or ""):
                continue
            if str(ctx.get("moving_unit_id", "") or "") != str(moving_unit_id or ""):
                continue
            if int(ctx.get("turn", 0) or 0) != int(turn or 0):
                continue
            return True
        return False

    def _activate_brotherhood_strike_blinding_aura(self, root, *, game=None, source_name: str = "") -> bool:
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner_id, turn_now = self._brotherhood_strike_turn_context(game)
        sr["brotherhood_strike_blinding_aura_no_overwatch"] = True
        if owner_id:
            sr["brotherhood_strike_blinding_aura_turn_owner"] = owner_id
        if turn_now:
            sr["brotherhood_strike_blinding_aura_turn"] = int(turn_now)
        if source_name:
            sr["brotherhood_strike_blinding_aura_source"] = str(source_name).strip()
        root.special_rules = sr
        player = getattr(self.army, "player", None)
        if player is not None:
            from ..utility.event_bus import append_action

            append_action(
                player,
                f"{str(source_name or 'Blinding Aura').strip() or 'Blinding Aura'}: "
                f"{getattr(root, 'name', 'Unit')} cannot be targeted with Fire Overwatch until end of turn.",
            )
        return True

    def _activate_brotherhood_strike_purity_of_purpose(self, root, *, game=None, source_name: str = "") -> bool:
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict):
            sr = {}
        owner_id, turn_now = self._brotherhood_strike_turn_context(game)
        sr["brotherhood_strike_purity_of_purpose_charge_reroll"] = True
        if owner_id:
            sr["brotherhood_strike_purity_of_purpose_turn_owner"] = owner_id
        if turn_now:
            sr["brotherhood_strike_purity_of_purpose_turn"] = int(turn_now)
        if source_name:
            sr["brotherhood_strike_purity_of_purpose_source"] = str(source_name).strip()
        root.special_rules = sr
        player = getattr(self.army, "player", None)
        if player is not None:
            from ..utility.event_bus import append_action

            append_action(
                player,
                f"{str(source_name or 'Purity of Purpose').strip() or 'Purity of Purpose'}: "
                f"{getattr(root, 'name', 'Unit')} can re-roll Charge rolls until end of turn.",
            )
        return True

    def _resolve_banishing_wave_on_unit_set_up(self, unit, *, game=None) -> None:
        if game is None:
            return
        root, _source_unit, sr, bearer = self._brotherhood_strike_enhancement_source_member(
            unit,
            flag_key="enhancement_banishing_wave",
            bearer_keys=("enhancement_banishing_wave_bearer_model_id",),
            require_bearer_alive=True,
        )
        if root is None or not isinstance(sr, dict) or bearer is None:
            return
        player = getattr(self.army, "player", None)
        if player is None:
            return
        try:
            range_value = int(sr.get("enhancement_banishing_wave_range", 12) or 12)
        except Exception:
            range_value = 12
        try:
            low_roll_min = int(sr.get("enhancement_banishing_wave_low_roll_min", 2) or 2)
        except Exception:
            low_roll_min = 2
        try:
            low_roll_max = int(sr.get("enhancement_banishing_wave_low_roll_max", 5) or 5)
        except Exception:
            low_roll_max = 5
        try:
            low_mortal_wounds = int(sr.get("enhancement_banishing_wave_low_mortal_wounds", 1) or 1)
        except Exception:
            low_mortal_wounds = 1
        try:
            high_roll_threshold = int(sr.get("enhancement_banishing_wave_high_roll_threshold", 6) or 6)
        except Exception:
            high_roll_threshold = 6
        high_mortal_wounds_roll = str(
            sr.get("enhancement_banishing_wave_high_mortal_wounds_roll", "D3") or "D3"
        ).strip().upper() or "D3"
        source_name = str(sr.get("enhancement_banishing_wave_source", "") or "Banishing Wave").strip() or "Banishing Wave"

        from ..utility.dice import get_roll
        from ..utility.event_bus import append_action, append_dice

        in_range_fn = getattr(game, "_unit_within_range_of_model", None)
        apply_mortal = getattr(root, "_apply_mortal_wounds_to_unit", None)
        if not callable(apply_mortal):
            apply_mortal = None
        game_map = getattr(game, "map", None)
        for enemy_root in list(self._iter_enemy_roots(game, owner_player=player) or []):
            if callable(in_range_fn):
                if not bool(in_range_fn(bearer, enemy_root, range_value=float(range_value))):
                    continue
            enemy_name = str(getattr(enemy_root, "name", "Unit") or "Unit")
            try:
                roll = int(get_roll("D6") or 0)
            except Exception:
                roll = 0
            append_dice(player, f"{source_name}: {enemy_name} roll {int(roll)}")
            mortal_wounds = 0
            if int(low_roll_min) <= int(roll) <= int(low_roll_max):
                mortal_wounds = int(max(0, low_mortal_wounds))
            elif int(roll) >= int(high_roll_threshold):
                try:
                    mortal_wounds = int(get_roll(high_mortal_wounds_roll) or 0)
                except Exception:
                    mortal_wounds = 0
                append_dice(
                    player,
                    f"{source_name}: {enemy_name} {high_mortal_wounds_roll} = {int(max(0, mortal_wounds))}",
                )
            if int(mortal_wounds) > 0 and callable(apply_mortal):
                apply_mortal(enemy_root, int(mortal_wounds), game_map=game_map)
                append_action(player, f"{source_name}: {enemy_name} suffers {int(mortal_wounds)} mortal wounds.")
            else:
                append_action(player, f"{source_name}: {enemy_name} suffers no mortal wounds.")

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

    def _attached_unit_disembarked_from_transport_this_round(self, unit) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        round_state = getattr(root, "round_state", None)
        if round_state is None:
            return False
        if not bool(getattr(round_state, "disembarked_this_round", False)):
            return False
        transport_id = str(getattr(round_state, "disembarked_from_transport_id", "") or "").strip()
        return bool(transport_id)

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

    def on_enemy_unit_move_started(self, enemy_unit, *, game=None, action: str | None = None) -> None:
        if game is None or enemy_unit is None:
            return
        if not self.is_hallowed_conclave():
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        if str(action or "").strip().lower() != "fall_back":
            return
        game_map = getattr(game, "map", None)
        if game_map is None:
            return
        enemy_root = self._attached_root(enemy_unit)
        enemy_root_id = str(get_entity_id(enemy_root) or "") if enemy_root is not None else ""
        if enemy_root is None or not enemy_root_id:
            return
        entries: list[dict[str, str]] = []
        for source_unit in sorted(
            list(self._iter_unique_army_units() or []),
            key=lambda item: str(get_entity_id(item) or ""),
        ):
            sr = getattr(source_unit, "special_rules", None)
            if not isinstance(sr, dict) or not bool(sr.get("enhancement_inescapable_judgement", False)):
                continue
            root = self._attached_root(source_unit)
            if root is None or not self._unit_is_active(root):
                continue
            source_root_id = str(get_entity_id(root) or "")
            source_unit_id = str(get_entity_id(source_unit) or "")
            if not source_root_id or not source_unit_id:
                continue
            if bool(sr.get("enhancement_inescapable_judgement_requires_bearer_alive", True)):
                bearer = self._resolve_member_bearer_model(
                    source_unit,
                    bearer_keys=("enhancement_inescapable_judgement_bearer_model_id",),
                )
                if bearer is None:
                    continue
            try:
                if not bool(game_map.is_within_engagement_range(root, enemy_root)):
                    continue
            except Exception:
                continue
            entries.append(
                {
                    "source_unit_id": source_unit_id,
                    "source_root_id": source_root_id,
                }
            )
        if not entries:
            self._hallowed_conclave_fall_back_candidates.pop(enemy_root_id, None)
            return
        entries.sort(key=lambda item: (str(item.get("source_root_id", "")), str(item.get("source_unit_id", ""))))
        self._hallowed_conclave_fall_back_candidates[enemy_root_id] = entries

    def on_enemy_unit_move_ended(self, enemy_unit, *, game=None, action: str | None = None) -> None:
        if game is None or enemy_unit is None:
            return
        if not self.is_hallowed_conclave():
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        if str(action or "").strip().lower() != "fall_back":
            return
        enemy_root = self._attached_root(enemy_unit)
        enemy_root_id = str(get_entity_id(enemy_root) or "") if enemy_root is not None else ""
        if enemy_root is None or not enemy_root_id:
            return
        entries = list(self._hallowed_conclave_fall_back_candidates.pop(enemy_root_id, []) or [])
        if not entries:
            return
        player = getattr(self.army, "player", None)
        if player is None:
            return
        try:
            turn_now = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn_now = 0
        phase_name = self._phase_name(game)
        current_player = getattr(game, "get_current_player", lambda: None)()
        turn_owner_id = str(getattr(current_player, "id", "") or "")

        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

        resolve_unit = getattr(game, "_resolve_unit_by_id", None)
        for entry in list(entries or []):
            source_unit_id = str(entry.get("source_unit_id", "") or "")
            if not source_unit_id:
                continue
            source_unit = resolve_unit(source_unit_id) if callable(resolve_unit) else None
            if source_unit is None:
                continue
            source_root = self._attached_root(source_unit)
            if source_root is None or not self._unit_is_active(source_root):
                continue
            source_sr = getattr(source_unit, "special_rules", None)
            if not isinstance(source_sr, dict) or not bool(source_sr.get("enhancement_inescapable_judgement", False)):
                continue
            if bool(source_sr.get("enhancement_inescapable_judgement_requires_bearer_alive", True)):
                bearer = self._resolve_member_bearer_model(
                    source_unit,
                    bearer_keys=("enhancement_inescapable_judgement_bearer_model_id",),
                )
                if bearer is None:
                    continue
            if self._pending_hallowed_inescapable_judgement_request(
                game,
                source_unit_id=source_unit_id,
                moving_unit_id=enemy_root_id,
                turn=int(turn_now),
            ):
                continue
            ability_name = str(
                source_sr.get("enhancement_inescapable_judgement_source", "") or "Inescapable Judgement"
            ).strip() or "Inescapable Judgement"
            low_roll_min = int(source_sr.get("enhancement_inescapable_judgement_low_roll_min", 2) or 2)
            low_roll_max = int(source_sr.get("enhancement_inescapable_judgement_low_roll_max", 5) or 5)
            high_roll_threshold = int(
                source_sr.get("enhancement_inescapable_judgement_high_roll_threshold", 6) or 6
            )
            options = [
                DecisionOption.create(
                    f"Use on {getattr(enemy_root, 'name', 'Unit')}",
                    payload={"target_unit_id": enemy_root_id},
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
                        f"{ability_name}: choose whether {getattr(enemy_root, 'name', 'Unit')} suffers mortal wounds "
                        f"on a {int(low_roll_min)}-{int(low_roll_max)}/{int(high_roll_threshold)} roll."
                    ),
                    player_id=getattr(player, "id", None),
                    options=options,
                    context={
                        "ability": "grey_knights_hallowed_inescapable_judgement",
                        "ability_name": ability_name,
                        "phase_name": phase_name,
                        "phase": phase_name.replace("_", " ").title(),
                        "source_unit_id": source_unit_id,
                        "unit_id": source_unit_id,
                        "moving_unit_id": enemy_root_id,
                        "candidate_unit_ids": [enemy_root_id],
                        "low_roll_min": int(low_roll_min),
                        "low_roll_max": int(low_roll_max),
                        "low_mortal_wounds_roll": str(
                            source_sr.get("enhancement_inescapable_judgement_low_mortal_wounds_roll", "D3") or "D3"
                        ).strip().upper()
                        or "D3",
                        "high_roll_threshold": int(high_roll_threshold),
                        "high_mortal_wounds_roll": str(
                            source_sr.get("enhancement_inescapable_judgement_high_mortal_wounds_roll", "D3+3")
                            or "D3+3"
                        ).strip().upper()
                        or "D3+3",
                        "bearer_model_id": str(
                            source_sr.get("enhancement_inescapable_judgement_bearer_model_id", "")
                            or source_sr.get("enhancement_bearer_model_id", "")
                            or ""
                        ).strip(),
                        "requires_bearer_alive": bool(
                            source_sr.get("enhancement_inescapable_judgement_requires_bearer_alive", True)
                        ),
                        "optional": bool(source_sr.get("enhancement_inescapable_judgement_optional", True)),
                        "turn_owner_id": turn_owner_id,
                        "turn": int(turn_now),
                    },
                )
            )

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
        if game is None or unit is None:
            return
        if not bool(getattr(game, "is_authoritative", True)):
            return
        if not bool(set_up_as_reinforcements):
            return
        root = self._attached_root(unit)
        if root is None or not self._unit_is_active(root):
            return
        if self.is_brotherhood_strike() and self._brotherhood_strike_used_deep_strike_setup(
            root,
            set_up_as_reinforcements=set_up_as_reinforcements,
            used_deep_strike=used_deep_strike,
        ):
            self._resolve_banishing_wave_on_unit_set_up(root, game=game)
            aura_root, _aura_source_unit, aura_sr, _aura_bearer = self._brotherhood_strike_enhancement_source_member(
                root,
                flag_key="enhancement_blinding_aura",
                bearer_keys=("enhancement_blinding_aura_bearer_model_id",),
                require_bearer_alive=True,
            )
            if aura_root is not None and isinstance(aura_sr, dict):
                self._activate_brotherhood_strike_blinding_aura(
                    aura_root,
                    game=game,
                    source_name=str(aura_sr.get("enhancement_blinding_aura_source", "") or "Blinding Aura"),
                )
            purity_root, _purity_source_unit, purity_sr, _purity_bearer = self._brotherhood_strike_enhancement_source_member(
                root,
                flag_key="enhancement_purity_of_purpose",
                bearer_keys=("enhancement_purity_of_purpose_bearer_model_id",),
                require_bearer_alive=True,
            )
            if purity_root is not None and isinstance(purity_sr, dict):
                self._activate_brotherhood_strike_purity_of_purpose(
                    purity_root,
                    game=game,
                    source_name=str(purity_sr.get("enhancement_purity_of_purpose_source", "") or "Purity of Purpose"),
                )
        if not self.is_augurium_task_force():
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

    def _brotherhood_strike_turn_scoped_effect_active(
        self,
        unit,
        *,
        active_key: str,
        owner_key: str,
        turn_key: str,
        game=None,
    ) -> bool:
        root = self._attached_root(unit)
        if root is None:
            return False
        sr = getattr(root, "special_rules", None)
        if not isinstance(sr, dict) or not bool(sr.get(str(active_key), False)):
            return False
        if game is None:
            player = getattr(self.army, "player", None)
            if player is not None:
                game = getattr(player, "game", None)
        if game is None:
            return True
        owner_id = str(sr.get(str(owner_key), "") or "")
        if owner_id:
            current_player = getattr(game, "get_current_player", lambda: None)()
            current_owner_id = str(getattr(current_player, "id", "") or "")
            if current_owner_id and current_owner_id != owner_id:
                return False
        try:
            marked_turn = int(sr.get(str(turn_key), 0) or 0)
        except Exception:
            marked_turn = 0
        try:
            current_turn = int(getattr(game, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        if marked_turn and current_turn and marked_turn != current_turn:
            return False
        return True

    def brotherhood_strike_blinding_aura_no_overwatch_applies(self, unit, *, game=None) -> bool:
        if not self.is_brotherhood_strike():
            return False
        return self._brotherhood_strike_turn_scoped_effect_active(
            unit,
            active_key="brotherhood_strike_blinding_aura_no_overwatch",
            owner_key="brotherhood_strike_blinding_aura_turn_owner",
            turn_key="brotherhood_strike_blinding_aura_turn",
            game=game,
        )

    def brotherhood_strike_purity_of_purpose_charge_reroll_applies(self, unit, *, game=None) -> bool:
        if not self.is_brotherhood_strike():
            return False
        return self._brotherhood_strike_turn_scoped_effect_active(
            unit,
            active_key="brotherhood_strike_purity_of_purpose_charge_reroll",
            owner_key="brotherhood_strike_purity_of_purpose_turn_owner",
            turn_key="brotherhood_strike_purity_of_purpose_turn",
            game=game,
        )

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

    @staticmethod
    def _clear_unit_ability_cache(unit) -> None:
        if unit is None:
            return
        root = unit
        get_root = getattr(unit, "get_attached_unit_root", None)
        if callable(get_root):
            root = get_root()
        if root is None:
            return
        invalidate = getattr(root, "_invalidate_ability_cache", None)
        if callable(invalidate):
            invalidate()
            return
        cache = getattr(root, "_ability_cache", None)
        if isinstance(cache, dict):
            cache.clear()
            root._ability_cache = cache

    def _augurium_phase_effect_state(self, unit, *, prefix: str, game=None) -> tuple[object | None, dict]:
        if not self.is_augurium_task_force():
            return None, {}
        root = self._attached_root(unit)
        if root is None:
            return None, {}
        get_parent_army = getattr(root, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        if parent_army is not self.army:
            return None, {}
        sr = getattr(root, "special_rules", None)
        if not (isinstance(sr, dict) and bool(sr.get(f"{prefix}_active", False))):
            return None, {}
        game_obj = game
        if game_obj is None:
            player = getattr(self.army, "player", None)
            game_obj = getattr(player, "game", None) if player is not None else None
        if game_obj is None:
            return root, sr
        expected_phase = str(sr.get(f"{prefix}_expires_phase", "") or "").strip().upper()
        current_phase = self._phase_name(game_obj)
        if expected_phase and current_phase and current_phase != expected_phase:
            return None, {}
        try:
            effect_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            effect_turn = 0
        try:
            current_turn = int(getattr(game_obj, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        if effect_turn > 0 and current_turn > 0 and effect_turn != current_turn:
            return None, {}
        effect_owner = str(sr.get(f"{prefix}_turn_owner", "") or "").strip()
        current_player = getattr(game_obj, "get_current_player", lambda: None)()
        current_owner = str(getattr(current_player, "id", "") or "").strip()
        if effect_owner and current_owner and effect_owner != current_owner:
            return None, {}
        return root, sr

    def _hallowed_conclave_phase_effect_state(self, unit, *, prefix: str, game=None) -> tuple[object | None, dict]:
        if not self.is_hallowed_conclave():
            return None, {}
        root = self._attached_root(unit)
        if root is None:
            return None, {}
        get_parent_army = getattr(root, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        if parent_army is not self.army:
            return None, {}
        sr = getattr(root, "special_rules", None)
        if not (isinstance(sr, dict) and bool(sr.get(f"{prefix}_active", False))):
            return None, {}
        game_obj = game
        if game_obj is None:
            player = getattr(self.army, "player", None)
            game_obj = getattr(player, "game", None) if player is not None else None
        if game_obj is None:
            return root, sr
        expected_phase = str(sr.get(f"{prefix}_expires_phase", "") or "").strip().upper()
        current_phase = self._phase_name(game_obj)
        if expected_phase and current_phase and current_phase != expected_phase:
            return None, {}
        try:
            effect_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
        except (TypeError, ValueError):
            effect_turn = 0
        try:
            current_turn = int(getattr(game_obj, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        if effect_turn > 0 and current_turn > 0 and effect_turn != current_turn:
            return None, {}
        effect_owner = str(sr.get(f"{prefix}_turn_owner", "") or "").strip()
        current_player = getattr(game_obj, "get_current_player", lambda: None)()
        current_owner = str(getattr(current_player, "id", "") or "").strip()
        if effect_owner and current_owner and effect_owner != current_owner:
            return None, {}
        return root, sr

    def _banishers_phase_effect_state(
        self,
        unit,
        *,
        prefix: str,
        game=None,
        require_phase_match: bool = True,
        require_turn_match: bool = True,
        require_owner_match: bool = True,
    ) -> tuple[object | None, dict]:
        if not self.is_banishers():
            return None, {}
        root = self._attached_root(unit)
        if root is None:
            return None, {}
        get_parent_army = getattr(root, "get_parent_army", None)
        parent_army = get_parent_army() if callable(get_parent_army) else getattr(root, "parent_army", None)
        if parent_army is not self.army:
            return None, {}
        sr = getattr(root, "special_rules", None)
        if not (isinstance(sr, dict) and bool(sr.get(f"{prefix}_active", False))):
            return None, {}
        game_obj = game
        if game_obj is None:
            player = getattr(self.army, "player", None)
            game_obj = getattr(player, "game", None) if player is not None else None
        if game_obj is None:
            return root, sr
        if require_phase_match:
            expected_phase = str(sr.get(f"{prefix}_expires_phase", "") or "").strip().upper()
            current_phase = self._phase_name(game_obj)
            if expected_phase and current_phase and current_phase != expected_phase:
                return None, {}
        if require_turn_match:
            try:
                effect_turn = int(sr.get(f"{prefix}_turn", 0) or 0)
            except (TypeError, ValueError):
                effect_turn = 0
            try:
                current_turn = int(getattr(game_obj, "turn", 0) or 0)
            except (TypeError, ValueError):
                current_turn = 0
            if effect_turn > 0 and current_turn > 0 and effect_turn != current_turn:
                return None, {}
        if require_owner_match:
            effect_owner = str(sr.get(f"{prefix}_turn_owner", "") or "").strip()
            current_player = getattr(game_obj, "get_current_player", lambda: None)()
            current_owner = str(getattr(current_player, "id", "") or "").strip()
            if effect_owner and current_owner and effect_owner != current_owner:
                return None, {}
        return root, sr

    def banishers_celerity_can_charge_after_advance(self, unit, *, game=None) -> bool:
        root, _sr = self._banishers_phase_effect_state(
            unit,
            prefix="banishers_celerity",
            game=game,
            require_phase_match=False,
        )
        if root is None or not self._is_grey_knights_unit(root):
            return False
        if not self._attached_unit_has_keyword(root, "PSYKER"):
            return False
        if not self._attached_unit_has_keyword(root, "INFANTRY"):
            return False
        round_state = getattr(root, "round_state", None)
        return bool(getattr(round_state, "advanced_this_round", False))

    def banishers_chaos_bane_attack_keyword_rule(
        self,
        attacker_model,
        *,
        attack_type: str = "any",
        weapon_profile=None,
        game=None,
    ) -> dict | None:
        if attacker_model is None:
            return None
        atype = str(attack_type or "").strip().lower()
        if atype not in ("", "any", "ranged"):
            return None
        if weapon_profile is not None:
            parent = getattr(weapon_profile, "parent_wargear", None)
            is_ranged = getattr(parent, "is_ranged", None) if parent is not None else None
            if callable(is_ranged) and not bool(is_ranged()):
                return None
        root, sr = self._banishers_phase_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix="banishers_chaos_bane",
            game=game,
        )
        if root is None or not self._is_grey_knights_unit(root):
            return None
        if not self._attached_unit_has_keyword(root, "PSYKER"):
            return None
        source = str(sr.get("banishers_chaos_bane_source", "") or "CHAOS BANE").strip() or "CHAOS BANE"
        return {
            "attack_type": "ranged",
            "keyword": "ANTI-CHAOS 4+",
            "source": source,
        }

    def banishers_circle_of_sanctuary_reserves_denial(self, unit, *, game=None) -> dict | None:
        game_obj = game
        if game_obj is None:
            player = getattr(self.army, "player", None)
            game_obj = getattr(player, "game", None) if player is not None else None
        if game_obj is None or not bool(getattr(game_obj, "reinforcements_step_active", False)):
            return None
        try:
            step_turn = int(getattr(game_obj, "reinforcements_step_turn", 0) or 0)
        except (TypeError, ValueError):
            step_turn = 0
        try:
            current_turn = int(getattr(game_obj, "turn", 0) or 0)
        except (TypeError, ValueError):
            current_turn = 0
        if step_turn and current_turn and step_turn != current_turn:
            return None
        step_player_id = str(getattr(game_obj, "reinforcements_step_player_id", "") or "").strip()
        current_player = getattr(game_obj, "get_current_player", lambda: None)()
        current_player_id = str(getattr(current_player, "id", "") or "").strip()
        if step_player_id and current_player_id and step_player_id != current_player_id:
            return None
        root, sr = self._banishers_phase_effect_state(
            unit,
            prefix="banishers_circle_of_sanctuary",
            game=game_obj,
        )
        if root is None or not self._is_grey_knights_unit(root) or not self._unit_is_active(root):
            return None
        try:
            min_distance = float(sr.get("banishers_circle_of_sanctuary_range", 12.0) or 12.0)
        except (TypeError, ValueError):
            min_distance = 12.0
        if min_distance <= 0.0:
            return None
        source_model_id = str(sr.get("banishers_circle_of_sanctuary_source_model_id", "") or "").strip()
        source_model = None
        get_models = getattr(root, "get_attached_unit_models", None)
        models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
        for model in list(models or []):
            model_id = str(get_entity_id(model) or "").strip()
            if source_model_id and model_id != source_model_id:
                continue
            alive_attr = getattr(model, "is_alive", True)
            is_alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
            if not is_alive:
                continue
            source_model = model
            if model_id:
                source_model_id = model_id
            break
        if source_model is None:
            return None
        source = str(
            sr.get("banishers_circle_of_sanctuary_source", "") or "CIRCLE OF SANCTUARY"
        ).strip() or "CIRCLE OF SANCTUARY"
        return {
            "range": float(min_distance),
            "horizontal_only": True,
            "source": source,
            "source_model_id": source_model_id,
        }

    def augurium_aggressive_anticipation_ignore_hit_modifiers_rule(
        self,
        attacker_model,
        *,
        game=None,
    ) -> dict | None:
        if attacker_model is None:
            return None
        root, sr = self._augurium_phase_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix="augurium_aggressive_anticipation",
            game=game,
        )
        if root is None or not self._is_grey_knights_unit(root):
            return None
        source = (
            str(sr.get("augurium_aggressive_anticipation_source", "") or "AGGRESSIVE ANTICIPATION").strip()
            or "AGGRESSIVE ANTICIPATION"
        )
        return {
            "name": source,
            "attack_type": "any",
            "skill_kinds": {"ballistic", "weapon"},
            "allow_hit": True,
            "default_choice": "ignore_negative",
        }

    def augurium_appointed_hour_crit_hit_threshold(
        self,
        attacker_model,
        *,
        weapon_profile=None,
        game=None,
    ) -> tuple[int, str]:
        _ = weapon_profile
        if attacker_model is None:
            return 0, ""
        root, sr = self._augurium_phase_effect_state(
            getattr(attacker_model, "parent_unit", None),
            prefix="augurium_appointed_hour",
            game=game,
        )
        if root is None or not self._is_grey_knights_unit(root):
            return 0, ""
        try:
            threshold = int(sr.get("augurium_appointed_hour_crit_threshold", 0) or 0)
        except (TypeError, ValueError):
            threshold = 0
        if threshold <= 0:
            return 0, ""
        source = str(sr.get("augurium_appointed_hour_source", "") or "APPOINTED HOUR").strip() or "APPOINTED HOUR"
        return max(2, min(6, threshold)), source

    def augurium_necessary_end_fight_on_death_rule(
        self,
        unit,
        *,
        model=None,
        game=None,
    ) -> dict | None:
        _ = model
        root, sr = self._augurium_phase_effect_state(
            unit,
            prefix="augurium_necessary_end",
            game=game,
        )
        if root is None or not self._is_grey_knights_unit(root):
            return None
        if not self._attached_unit_has_keyword(root, "INFANTRY"):
            return None
        try:
            threshold = int(sr.get("augurium_necessary_end_threshold", 0) or 0)
        except (TypeError, ValueError):
            threshold = 0
        if threshold < 2 or threshold > 6:
            return None
        source = str(sr.get("augurium_necessary_end_source", "") or "NECESSARY END").strip() or "NECESSARY END"
        return {
            "threshold": int(threshold),
            "source": source,
            "allow_any_fight_phase_destruction": True,
        }

    def hallowed_conclave_shining_resolve_wound_roll_penalty(
        self,
        unit,
        *,
        strength=None,
        target_toughness=None,
        game=None,
    ) -> tuple[int, str]:
        root, sr = self._hallowed_conclave_phase_effect_state(
            unit,
            prefix="hallowed_conclave_shining_resolve",
            game=game,
        )
        if root is None or not self._is_grey_knights_unit(root):
            return 0, ""
        if not self._attached_unit_has_keyword(root, "INFANTRY"):
            return 0, ""
        try:
            strength_value = int(strength)
        except (TypeError, ValueError):
            return 0, ""
        if isinstance(target_toughness, int):
            toughness_value = int(target_toughness)
        else:
            try:
                toughness_value = int(getattr(root, "toughness", 0) or 0)
            except (TypeError, ValueError):
                toughness_value = 0
        if toughness_value <= 0 or strength_value <= toughness_value:
            return 0, ""
        source = str(
            sr.get("hallowed_conclave_shining_resolve_source", "") or "SHINING RESOLVE"
        ).strip() or "SHINING RESOLVE"
        return 1, source

    def hallowed_conclave_unending_fidelity_fight_on_death_rule(
        self,
        unit,
        *,
        model=None,
        game=None,
    ) -> dict | None:
        _ = model
        root, sr = self._hallowed_conclave_phase_effect_state(
            unit,
            prefix="hallowed_conclave_unending_fidelity",
            game=game,
        )
        if root is None or not self._is_grey_knights_unit(root):
            return None
        if not self._attached_unit_has_keyword(root, "INFANTRY"):
            return None
        if str(sr.get("hallowed_conclave_unending_fidelity_mode", "") or "").strip().lower() != "fight":
            return None
        try:
            threshold = int(sr.get("hallowed_conclave_unending_fidelity_threshold", 0) or 0)
        except (TypeError, ValueError):
            threshold = 0
        if threshold < 2 or threshold > 6:
            return None
        source = str(
            sr.get("hallowed_conclave_unending_fidelity_source", "") or "UNENDING FIDELITY"
        ).strip() or "UNENDING FIDELITY"
        return {
            "threshold": int(threshold),
            "source": source,
            "allow_any_fight_phase_destruction": True,
        }

    def hallowed_conclave_unending_fidelity_shoot_on_death_rule(
        self,
        unit,
        *,
        model=None,
        game=None,
    ) -> dict | None:
        _ = model
        root, sr = self._hallowed_conclave_phase_effect_state(
            unit,
            prefix="hallowed_conclave_unending_fidelity",
            game=game,
        )
        if root is None or not self._is_grey_knights_unit(root):
            return None
        if not self._attached_unit_has_keyword(root, "INFANTRY"):
            return None
        if str(sr.get("hallowed_conclave_unending_fidelity_mode", "") or "").strip().lower() != "shoot":
            return None
        try:
            threshold = int(sr.get("hallowed_conclave_unending_fidelity_threshold", 0) or 0)
        except (TypeError, ValueError):
            threshold = 0
        if threshold < 2 or threshold > 6:
            return None
        source = str(
            sr.get("hallowed_conclave_unending_fidelity_source", "") or "UNENDING FIDELITY"
        ).strip() or "UNENDING FIDELITY"
        return {
            "threshold": int(threshold),
            "source": source,
            "attack_type": "any",
        }

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

    def quickening_foci_reroll_charge_applies(self, unit, *, game=None) -> bool:
        if not self.is_sanctic_spearhead():
            return False
        root, _member, sr, _bearer = self._sanctic_spearhead_enhancement_source_member(
            unit,
            flag_key="enhancement_quickening_foci",
            bearer_keys=("enhancement_quickening_foci_bearer_model_id",),
            require_bearer_alive=True,
        )
        if root is None or not isinstance(sr, dict):
            return False
        if not bool(sr.get("enhancement_quickening_foci_charge_reroll", True)):
            return False
        if not self._attached_unit_disembarked_from_transport_this_round(root):
            return False
        game_obj = game
        if game_obj is None:
            player = getattr(self.army, "player", None)
            game_obj = getattr(player, "game", None) if player is not None else None
        if game_obj is None:
            return True
        current_player = getattr(game_obj, "get_current_player", lambda: None)()
        player = getattr(self.army, "player", None)
        if current_player is None or player is None:
            return False
        return str(getattr(current_player, "id", "") or "") == str(getattr(player, "id", "") or "")

    def spiritus_machina_wound_reroll(self, unit, *, attack_type: str = "any", game=None) -> dict:
        if not self.is_sanctic_spearhead():
            return {}
        atype = str(attack_type or "").strip().lower()
        if atype not in ("any", "ranged"):
            return {}
        root, _member, sr, _bearer = self._sanctic_spearhead_enhancement_source_member(
            unit,
            flag_key="enhancement_spiritus_machina",
            bearer_keys=("enhancement_spiritus_machina_bearer_model_id",),
            require_bearer_alive=True,
        )
        if root is None or not isinstance(sr, dict):
            return {}
        if not bool(sr.get("enhancement_spiritus_machina_reroll_wound", True)):
            return {}
        if not self._attached_unit_disembarked_from_transport_this_round(root):
            return {}
        game_obj = game
        if game_obj is None:
            player = getattr(self.army, "player", None)
            game_obj = getattr(player, "game", None) if player is not None else None
        if not self._is_active_army_player_phase(game_obj, phase_name="SHOOTING_PHASE"):
            return {}
        source_name = str(
            sr.get("enhancement_spiritus_machina_source", "") or "Spiritus Machina"
        ).strip() or "Spiritus Machina"
        return {
            "reroll_wound_full": True,
            "reroll_wound_full_reasons": (f"{source_name}: re-roll Wound roll",),
        }

    def queue_sanctic_sigil_of_exigence_for_target(self, target_unit, *, attacking_unit=None, game=None) -> bool:
        if not self.is_sanctic_spearhead() or game is None or target_unit is None:
            return False
        if not bool(getattr(game, "is_authoritative", True)):
            return False
        if self._phase_name(game) != "SHOOTING_PHASE":
            return False
        player = getattr(self.army, "player", None)
        if player is None:
            return False
        current_player = getattr(game, "get_current_player", lambda: None)()
        if current_player is None:
            return False
        if str(getattr(current_player, "id", "") or "") == str(getattr(player, "id", "") or ""):
            return False
        root, source_unit, sr, bearer = self._sanctic_spearhead_enhancement_source_member(
            target_unit,
            flag_key="enhancement_sigil_of_exigence",
            bearer_keys=("enhancement_sigil_of_exigence_bearer_model_id",),
            require_bearer_alive=True,
        )
        if root is None or source_unit is None or not isinstance(sr, dict) or bearer is None:
            return False
        attacker_root = self._attached_root(attacking_unit)
        if attacker_root is None or not self._unit_is_active(attacker_root):
            return False
        try:
            if attacker_root.get_parent_army() is self.army:
                return False
        except Exception:
            return False
        root_id = str(get_entity_id(root) or "")
        source_unit_id = str(get_entity_id(source_unit) or "")
        attacker_root_id = str(get_entity_id(attacker_root) or "")
        if not root_id or not source_unit_id or not attacker_root_id:
            return False
        once_key = str(
            sr.get("enhancement_sigil_of_exigence_once_key", "") or "sigil_of_exigence"
        ).strip().lower() or "sigil_of_exigence"
        used_once = getattr(root, "has_used_unit_once_per_battle", None)
        if callable(used_once) and bool(used_once(once_key)):
            return False
        try:
            turn_now = int(getattr(game, "turn", 0) or 0)
        except Exception:
            turn_now = 0
        existing = self._pending_choose_quarry_request(
            game,
            ability="grey_knights_sanctic_sigil_of_exigence",
            source_unit_id=source_unit_id,
            turn=int(turn_now or 0),
            phase_name="SHOOTING_PHASE",
        )
        if existing is not None:
            return True
        ability_name = str(
            sr.get("enhancement_sigil_of_exigence_source", "") or "Sigil of Exigence"
        ).strip() or "Sigil of Exigence"
        bearer_model_id = str(
            sr.get("enhancement_sigil_of_exigence_bearer_model_id", "")
            or sr.get("enhancement_bearer_model_id", "")
            or ""
        ).strip()
        min_enemy_distance_horiz = int(
            sr.get("enhancement_sigil_of_exigence_min_enemy_distance_horiz", 9) or 9
        )

        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY

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
                    f"{ability_name}: choose whether {getattr(root, 'name', 'Unit')} is removed and set up again "
                    f"more than {int(min_enemy_distance_horiz)}\" horizontally from enemy units."
                ),
                player_id=getattr(player, "id", None),
                options=options,
                context={
                    "ability": "grey_knights_sanctic_sigil_of_exigence",
                    "ability_name": ability_name,
                    "source_unit_id": source_unit_id,
                    "target_unit_id": root_id,
                    "unit_id": root_id,
                    "attacking_unit_id": attacker_root_id,
                    "candidate_unit_ids": [root_id],
                    "phase_name": "SHOOTING_PHASE",
                    "phase": "Shooting phase",
                    "turn_owner_id": str(getattr(current_player, "id", "") or ""),
                    "turn": int(turn_now or 0),
                    "once_key": once_key,
                    "bearer_model_id": bearer_model_id,
                    "requires_bearer_alive": bool(
                        sr.get("enhancement_sigil_of_exigence_requires_bearer_alive", True)
                    ),
                    "min_enemy_distance_horiz": int(min_enemy_distance_horiz),
                    "optional": bool(sr.get("enhancement_sigil_of_exigence_optional", True)),
                },
            )
        )
        return True

    def mark_sanctic_sigil_of_exigence_used(
        self,
        unit,
        *,
        ability_name: str = "Sigil of Exigence",
    ) -> bool:
        if not self.is_sanctic_spearhead():
            return False
        root, _source_unit, sr, _bearer = self._sanctic_spearhead_enhancement_source_member(
            unit,
            flag_key="enhancement_sigil_of_exigence",
            bearer_keys=("enhancement_sigil_of_exigence_bearer_model_id",),
            require_bearer_alive=False,
        )
        if root is None or not isinstance(sr, dict):
            return False
        once_key = str(
            sr.get("enhancement_sigil_of_exigence_once_key", "") or "sigil_of_exigence"
        ).strip().lower() or "sigil_of_exigence"
        mark_used = getattr(root, "mark_unit_once_per_battle_used", None)
        if not callable(mark_used):
            return False
        mark_used(
            once_key,
            ability_name=str(ability_name or "Sigil of Exigence").strip() or "Sigil of Exigence",
        )
        return True

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
