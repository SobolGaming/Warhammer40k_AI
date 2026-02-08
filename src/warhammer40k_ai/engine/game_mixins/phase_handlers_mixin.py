from __future__ import annotations

from ._shared import *  # noqa: F401,F403


class GamePhaseHandlersMixin:
    def _on_phase_start_optional_abilities(self, player=None, phase=None, **_kwargs) -> None:
        """
        Hook point for optional, player-decided abilities that trigger at specific timing windows.

        Currently supported:
        - Possessed Lord (Once per battle, start of Fight phase): prompt to activate.
        - Fight phase melee AP boost (Once per battle, start of Fight phase): +3 Attacks and +1 AP for bearer.
        - Enhancements that grant Fight First (Once per battle, start of Fight phase).
        """
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname:
            for p in list(getattr(self, "players", []) or []):
                if p is None:
                    continue
                army = p.get_army()
                if army is None:
                    continue
                for unit in list(army.units):
                    if unit is None:
                        continue
                    get_root = getattr(unit, "get_attached_unit_root", None)
                    root = get_root() if callable(get_root) else unit
                    if root is None or root is not unit:
                        continue
                    if not root.is_alive():
                        continue
                    if not getattr(root, "deployed", True):
                        continue
                    in_reserves_fn = getattr(root, "is_in_reserves", None)
                    in_reserves = bool(in_reserves_fn()) if callable(in_reserves_fn) else (
                        str(getattr(root, "reserve_status", "deployed")) in ("reserves", "strategic_reserves")
                    )
                    is_embarked = bool(getattr(root, "is_embarked", False)) or bool(getattr(root, "embarked_in", None))
                    if in_reserves or is_embarked:
                        continue

                    # Model-level: start-of-any-phase damage set to 1 (once per battle).
                    get_models = getattr(root, "get_attached_unit_models", None)
                    models = list(get_models() or []) if callable(get_models) else list(getattr(root, "models", []) or [])
                    for model in list(models or []):
                        if not getattr(model, "is_alive", False):
                            continue
                        get_specs = getattr(root, "model_start_any_phase_damage_set_one_specs", None)
                        specs = list(get_specs(model) or []) if callable(get_specs) else []
                        if not specs:
                            continue
                        for spec in specs:
                            key = str(spec.get("key") or "start_any_phase_damage_set_one").strip().lower()
                            if not key:
                                key = "start_any_phase_damage_set_one"
                            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                                continue
                            unit_id = maybe_entity_id(root)
                            model_id = maybe_entity_id(model)
                            ability_name = str(spec.get("source", "") or "Start of phase damage set to 1").strip()
                            ctx = {
                                "ability_name": ability_name,
                                "unit": getattr(root, "name", "") or "",
                                "model": getattr(model, "name", "") or "",
                                "phase": pname.replace("_", " ").title(),
                                "unit_id": unit_id,
                                "model_id": model_id,
                                "buff_key": key,
                            }
                            message = (
                                f"Activate {ability_name} for {getattr(model, 'name', 'Model')} "
                                f"({getattr(root, 'name', 'Unit')})?"
                            )
                            self._queue_optional_ability_confirmation(
                                player=p,
                                ability_key="start_any_phase_damage_set_one",
                                ability_name=ability_name,
                                message=message,
                                context=ctx,
                                payload={"unit_id": unit_id, "model_id": model_id, "buff_key": key},
                                instance_key=f"{model_id}:{key}",
                            )

                    # Model-level: start-of-any-phase invulnerable save (once per battle).
                    for model in list(models or []):
                        if not getattr(model, "is_alive", False):
                            continue
                        get_specs = getattr(root, "model_start_any_phase_invulnerable_save_specs", None)
                        specs = list(get_specs(model) or []) if callable(get_specs) else []
                        if not specs:
                            continue
                        for spec in specs:
                            key = str(spec.get("key") or "start_any_phase_invulnerable_save").strip().lower()
                            if not key:
                                key = "start_any_phase_invulnerable_save"
                            if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                                continue
                            unit_id = maybe_entity_id(root)
                            model_id = maybe_entity_id(model)
                            ability_name = str(spec.get("source", "") or "Start of phase invulnerable save").strip()
                            invuln = int(spec.get("value", 0) or 0)
                            if invuln <= 0:
                                continue
                            ctx = {
                                "ability_name": ability_name,
                                "unit": getattr(root, "name", "") or "",
                                "model": getattr(model, "name", "") or "",
                                "phase": pname.replace("_", " ").title(),
                                "unit_id": unit_id,
                                "model_id": model_id,
                                "buff_key": key,
                                "invuln": invuln,
                            }
                            message = (
                                f"Activate {ability_name} for {getattr(model, 'name', 'Model')} "
                                f"({getattr(root, 'name', 'Unit')})?"
                            )
                            self._queue_optional_ability_confirmation(
                                player=p,
                                ability_key="start_any_phase_invulnerable_save",
                                ability_name=ability_name,
                                message=message,
                                context=ctx,
                                payload={"unit_id": unit_id, "model_id": model_id, "buff_key": key, "invuln": invuln},
                                instance_key=f"{model_id}:{key}",
                            )

                    # Unit-level: start-of-any-phase FNP (once per battle).
                    get_fnp_specs = getattr(root, "unit_start_any_phase_fnp_specs", None)
                    specs = list(get_fnp_specs() or []) if callable(get_fnp_specs) else []
                    for spec in specs:
                        ability_key = str(spec.get("ability_key") or "start_any_phase_fnp").strip().lower()
                        if not ability_key:
                            ability_key = "start_any_phase_fnp"
                        if root.has_used_unit_once_per_battle(ability_key):
                            continue
                        unit_id = maybe_entity_id(root)
                        ability_name = str(spec.get("source", "") or "Start of phase FNP").strip()
                        ctx = {
                            "ability_name": ability_name,
                            "unit": getattr(root, "name", "") or "",
                            "phase": pname.replace("_", " ").title(),
                            "unit_id": unit_id,
                            "ability_key": ability_key,
                            "fnp_value": int(spec.get("value", 0) or 0),
                        }
                        message = f"Activate {ability_name} for {getattr(root, 'name', 'Unit')}?"
                        self._queue_optional_ability_confirmation(
                            player=p,
                            ability_key="start_any_phase_fnp",
                            ability_name=ability_name,
                            message=message,
                            context=ctx,
                            payload={"unit_id": unit_id, "ability_key": ability_key},
                            instance_key=f"{unit_id}:{ability_key}",
                        )

                    # Unit-level: start-of-any-phase Battle-shock clear (once per battle).
                    get_clear_specs = getattr(root, "unit_start_any_phase_clear_battleshock_specs", None)
                    specs = list(get_clear_specs() or []) if callable(get_clear_specs) else []
                    for spec in specs:
                        ability_key = str(spec.get("ability_key") or "start_any_phase_clear_battleshock").strip().lower()
                        if not ability_key:
                            ability_key = "start_any_phase_clear_battleshock"
                        if root.has_used_unit_once_per_battle(ability_key):
                            continue
                        model_name = str(spec.get("model_name", "") or "").strip()
                        anchor_model = None
                        if model_name:
                            find_model = getattr(root, "_find_model_named", None)
                            if callable(find_model):
                                anchor_model = find_model(model_name)
                        if anchor_model is None:
                            anchor_model = next(
                                (m for m in list(getattr(root, "models", []) or []) if getattr(m, "is_alive", False)),
                                None,
                            )
                        if anchor_model is None:
                            continue

                        keyword = str(spec.get("keyword", "") or "").strip()
                        try:
                            range_value = int(spec.get("range", 0) or 0)
                        except (TypeError, ValueError):
                            range_value = 0
                        if range_value <= 0 or not keyword:
                            continue
                        candidates = []
                        seen_candidates: set[str] = set()
                        for other in list(getattr(army, "units", []) or []):
                            if other is None:
                                continue
                            get_other_root = getattr(other, "get_attached_unit_root", None)
                            other_root = get_other_root() if callable(get_other_root) else other
                            if other_root is None:
                                continue
                            oid = str(get_entity_id(other_root))
                            if not oid or oid in seen_candidates:
                                continue
                            seen_candidates.add(oid)
                            is_alive_fn = getattr(other_root, "is_alive", None)
                            if callable(is_alive_fn):
                                if not is_alive_fn():
                                    continue
                            elif getattr(other_root, "is_alive", True) is False:
                                continue
                            if not getattr(other_root, "deployed", True):
                                continue
                            in_reserves_fn = getattr(other_root, "is_in_reserves", None)
                            in_reserves = bool(in_reserves_fn()) if callable(in_reserves_fn) else (
                                str(getattr(other_root, "reserve_status", "deployed")) in ("reserves", "strategic_reserves")
                            )
                            is_embarked = bool(getattr(other_root, "is_embarked", False)) or bool(getattr(other_root, "embarked_in", None))
                            if in_reserves or is_embarked:
                                continue
                            is_battle_shocked_fn = getattr(other_root, "is_battle_shocked", None)
                            if not callable(is_battle_shocked_fn) or not is_battle_shocked_fn():
                                continue
                            matches_keyword = getattr(root, "_unit_matches_keyword_phrase", None)
                            if not callable(matches_keyword) or not matches_keyword(other_root, keyword):
                                continue
                            in_range = getattr(root, "_model_within_range_of_unit", None)
                            if not callable(in_range) or not in_range(anchor_model, other_root, float(range_value)):
                                continue
                            candidates.append(other_root)

                        if not candidates:
                            continue
                        self._queue_start_any_phase_battleshock_clear(
                            player=p,
                            source_unit=root,
                            model=anchor_model,
                            candidates=candidates,
                            spec=spec,
                            phase_label=pname.replace("_", " ").title(),
                        )
        if pname == "FIGHT_PHASE":
            if player is None:
                return

            # Only prompt the current player for their own optional activations at the start of this Fight phase.
            if player is not self.get_current_player():
                return

            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Optional abilities require an army for {player.name}.")

            for unit in list(army.units):
                if not unit.is_alive():
                    continue
                # Check unit has Possessed Lord ability text (datasheet ability list)
                has_possessed_lord = False
                for ab in (getattr(unit, "possible_abilities", []) or []):
                    nm = str(getattr(ab, "name", "") or "").strip().lower()
                    if nm == "possessed lord":
                        has_possessed_lord = True
                        break
                if not has_possessed_lord:
                    continue

                # Apply to the first alive model in the unit (typical for character datasheets).
                models = list(unit.models or [])
                for m in models:
                    if not getattr(m, "is_alive", True):
                        continue
                    # If already used, skip.
                    if m.has_used_once_per_battle("possessed_lord"):
                        break

                    unit_id = maybe_entity_id(unit)
                    model_id = maybe_entity_id(m)
                    ctx = {
                        "ability_name": "Possessed Lord",
                        "unit": getattr(unit, "name", "") or "",
                        "model": getattr(m, "name", "") or "",
                        "phase": "Fight phase",
                        "unit_id": unit_id,
                        "model_id": model_id,
                    }
                    message = (
                        f"Activate Possessed Lord for {getattr(m, 'name', 'Model')} "
                        f"({getattr(unit, 'name', 'Unit')})?"
                    )
                    self._queue_optional_ability_confirmation(
                        player=player,
                        ability_key="possessed_lord",
                        ability_name="Possessed Lord",
                        message=message,
                        context=ctx,
                        payload={"unit_id": unit_id, "model_id": model_id},
                    )
                    break
            # Once per battle: start of Fight phase -> +3 Attacks and +1 AP (melee) for this model.
            for unit in list(army.units):
                if not unit.is_alive():
                    continue
                models = list(getattr(unit, "models", []) or [])
                for m in models:
                    if not getattr(m, "is_alive", True):
                        continue
                    specs = []
                    try:
                        specs = list(unit.model_start_fight_phase_melee_attacks_ap_boost_specs(m) or [])
                    except Exception:
                        specs = []
                    if not specs:
                        continue
                    for spec in specs:
                        key = str(spec.get("key") or "fight_phase_melee_ap_boost").strip().lower()
                        if not key:
                            key = "fight_phase_melee_ap_boost"
                        if getattr(m, "has_used_once_per_battle", lambda _k: False)(key):
                            continue
                        unit_id = maybe_entity_id(unit)
                        model_id = maybe_entity_id(m)
                        ability_name = str(spec.get("source", "") or "Fight phase melee boost").strip()
                        ctx = {
                            "ability_name": ability_name,
                            "unit": getattr(unit, "name", "") or "",
                            "model": getattr(m, "name", "") or "",
                            "phase": "Fight phase",
                            "unit_id": unit_id,
                            "model_id": model_id,
                        }
                        message = (
                            f"Activate {ability_name} for {getattr(m, 'name', 'Model')} "
                            f"({getattr(unit, 'name', 'Unit')})?"
                        )
                        self._queue_optional_ability_confirmation(
                            player=player,
                            ability_key="fight_phase_melee_ap_boost",
                            ability_name=ability_name,
                            message=message,
                            context=ctx,
                            payload={"unit_id": unit_id, "model_id": model_id, "buff_key": key},
                            instance_key=f"{model_id}:{key}",
                        )
            # Once per battle: start of Fight phase -> improve S/A/AP/D for this model.
            for unit in list(army.units):
                if not unit.is_alive():
                    continue
                models = list(getattr(unit, "models", []) or [])
                for m in models:
                    if not getattr(m, "is_alive", True):
                        continue
                    get_specs = getattr(unit, "model_start_fight_phase_melee_full_characteristic_boost_specs", None)
                    specs = list(get_specs(m) or []) if callable(get_specs) else []
                    if not specs:
                        continue
                    for spec in specs:
                        key = str(spec.get("key") or "fight_phase_melee_full_boost").strip().lower()
                        if not key:
                            key = "fight_phase_melee_full_boost"
                        if getattr(m, "has_used_once_per_battle", lambda _k: False)(key):
                            continue
                        unit_id = maybe_entity_id(unit)
                        model_id = maybe_entity_id(m)
                        ability_name = str(spec.get("source", "") or "Fight phase melee boost").strip()
                        ctx = {
                            "ability_name": ability_name,
                            "unit": getattr(unit, "name", "") or "",
                            "model": getattr(m, "name", "") or "",
                            "phase": "Fight phase",
                            "unit_id": unit_id,
                            "model_id": model_id,
                            "buff_key": key,
                            "bonus": int(spec.get("bonus", 1) or 1),
                        }
                        message = (
                            f"Activate {ability_name} for {getattr(m, 'name', 'Model')} "
                            f"({getattr(unit, 'name', 'Unit')})?"
                        )
                        self._queue_optional_ability_confirmation(
                            player=player,
                            ability_key="chance_for_glory",
                            ability_name=ability_name,
                            message=message,
                            context=ctx,
                            payload={"unit_id": unit_id, "model_id": model_id, "buff_key": key},
                            instance_key=f"{model_id}:{key}",
                        )
            # Once per battle: start of Fight phase -> add Attacks to hellforged weapons.
            for unit in list(army.units):
                if not unit.is_alive():
                    continue
                models = list(getattr(unit, "models", []) or [])
                for m in models:
                    if not getattr(m, "is_alive", True):
                        continue
                    get_specs = getattr(unit, "model_start_fight_phase_hellforged_attacks_bonus_specs", None)
                    specs = list(get_specs(m) or []) if callable(get_specs) else []
                    if not specs:
                        continue
                    for spec in specs:
                        key = str(spec.get("key") or "fight_phase_hellforged_attacks").strip().lower()
                        if not key:
                            key = "fight_phase_hellforged_attacks"
                        if getattr(m, "has_used_once_per_battle", lambda _k: False)(key):
                            continue
                        unit_id = maybe_entity_id(unit)
                        model_id = maybe_entity_id(m)
                        ability_name = str(spec.get("source", "") or "Fight phase hellforged attacks").strip()
                        ctx = {
                            "ability_name": ability_name,
                            "unit": getattr(unit, "name", "") or "",
                            "model": getattr(m, "name", "") or "",
                            "phase": "Fight phase",
                            "unit_id": unit_id,
                            "model_id": model_id,
                            "buff_key": key,
                            "weapon_name": str(spec.get("weapon_name", "") or "hellforged"),
                            "attacks_bonus": int(spec.get("attacks_bonus", 0) or 0),
                        }
                        message = (
                            f"Activate {ability_name} for {getattr(m, 'name', 'Model')} "
                            f"({getattr(unit, 'name', 'Unit')})?"
                        )
                        self._queue_optional_ability_confirmation(
                            player=player,
                            ability_key="malefic_destruction",
                            ability_name=ability_name,
                            message=message,
                            context=ctx,
                            payload={
                                "unit_id": unit_id,
                                "model_id": model_id,
                                "buff_key": key,
                                "weapon_name": ctx["weapon_name"],
                                "attacks_bonus": int(ctx["attacks_bonus"]),
                            },
                            instance_key=f"{model_id}:{key}",
                        )
            # Enhancement: once per battle, start of Fight phase -> Fight First for bearer's unit.
            for unit in list(army.units):
                if not unit.is_alive():
                    continue
                if not unit.has_enhancement_fight_first_once_per_battle():
                    continue
                if not unit.can_use_enhancement_fight_first():
                    continue
                enh_name = str(getattr(getattr(unit, "enhancement", None), "name", "") or "")
                ctx = {
                    "ability_name": enh_name or "Fight First Enhancement",
                    "unit": getattr(unit, "name", "") or "",
                    "phase": "Fight phase",
                    "unit_id": maybe_entity_id(unit),
                }
                message = f"Activate {ctx['ability_name']} for {getattr(unit, 'name', 'Unit')}?"
                self._queue_optional_ability_confirmation(
                    player=player,
                    ability_key="enhancement_fight_first",
                    ability_name=ctx["ability_name"],
                    message=message,
                    context=ctx,
                    payload={"unit_id": ctx.get("unit_id")},
                    instance_key=str(ctx.get("unit_id") or ""),
                )

            # Moment Shackle: once per battle, start of Fight phase, choose one effect.
            from ..decision_kinds import DECISION_CHOOSE_MOMENT_SHACKLE
            from ..decisions import DecisionOption, DecisionRequest

            pending_models = set()
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if getattr(req, "decision_type", None) != DECISION_CHOOSE_MOMENT_SHACKLE:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    mid = str(ctx.get("model_id", "") or "")
                    if mid:
                        pending_models.add(mid)

            for unit in list(army.units):
                if not unit.is_alive():
                    continue
                if not getattr(unit, "deployed", True):
                    continue
                is_in_reserves_fn = getattr(unit, "is_in_reserves", None)
                in_reserves = bool(is_in_reserves_fn()) if callable(is_in_reserves_fn) else (
                    str(getattr(unit, "reserve_status", "deployed")) in ("reserves", "strategic_reserves")
                )
                is_embarked = bool(getattr(unit, "is_embarked", False)) or bool(getattr(unit, "embarked_in", None))
                if in_reserves or is_embarked:
                    continue
                get_models = getattr(unit, "get_attached_unit_models", None)
                models = list(get_models() or []) if callable(get_models) else list(getattr(unit, "models", []) or [])
                for model in list(models or []):
                    if not getattr(model, "is_alive", False):
                        continue
                    get_spec = getattr(unit, "model_moment_shackle_spec", None)
                    spec = get_spec(model) if callable(get_spec) else None
                    if not spec:
                        continue
                    ability_key = str(spec.get("ability_key") or "moment_shackle").strip().lower() or "moment_shackle"
                    if getattr(model, "has_used_once_per_battle", lambda _k: False)(ability_key):
                        continue
                    unit_id = maybe_entity_id(unit)
                    model_id = maybe_entity_id(model)
                    if model_id and str(model_id) in pending_models:
                        continue
                    ability_name = str(spec.get("source") or "Moment Shackle").strip() or "Moment Shackle"
                    weapon_name = str(spec.get("weapon_name") or "Watcher's Axe").strip() or "Watcher's Axe"
                    try:
                        attacks = int(spec.get("attacks", 12) or 12)
                    except (TypeError, ValueError):
                        attacks = 12
                    try:
                        invuln = int(spec.get("invuln", 2) or 2)
                    except (TypeError, ValueError):
                        invuln = 2
                    ctx = {
                        "ability_name": ability_name,
                        "unit": getattr(unit, "name", "") or "",
                        "model": getattr(model, "name", "") or "",
                        "phase": "Fight phase",
                        "unit_id": unit_id,
                        "model_id": model_id,
                        "ability_key": ability_key,
                    }
                    options = [
                        DecisionOption.create(
                            "Do not use",
                            payload={
                                "action": "skip",
                                "unit_id": unit_id,
                                "model_id": model_id,
                                "ability_key": ability_key,
                                "summary": "Do not use Moment Shackle this phase.",
                            },
                        ),
                        DecisionOption.create(
                            f"{weapon_name} Attacks {int(attacks)}",
                            payload={
                                "choice": "attacks",
                                "unit_id": unit_id,
                                "model_id": model_id,
                                "ability_key": ability_key,
                                "weapon_name": weapon_name,
                                "attacks": int(attacks),
                                "summary": f"{weapon_name} Attacks set to {int(attacks)} until end of phase.",
                            },
                        ),
                        DecisionOption.create(
                            f"Invulnerable Save {int(invuln)}+",
                            payload={
                                "choice": "invuln",
                                "unit_id": unit_id,
                                "model_id": model_id,
                                "ability_key": ability_key,
                                "invuln": int(invuln),
                                "summary": f"Gain a {int(invuln)}+ invulnerable save until end of phase.",
                            },
                        ),
                    ]
                    request = DecisionRequest.create(
                        DECISION_CHOOSE_MOMENT_SHACKLE,
                        f"{ability_name}: select one effect.",
                        player_id=getattr(player, "id", None),
                        options=options,
                        context=ctx,
                    )
                    self.request_decision(request)
            return

        if pname != "COMMAND_PHASE":
            return
        if player is None:
            return
        if player is not self.get_current_player():
            return
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Optional abilities require an army for {player.name}.")

        for unit in list(army.units):
            if not unit.is_alive():
                continue
            if not unit.is_attached_leader:
                continue

            ability = unit.get_command_phase_bodyguard_return_ability()
            if not ability:
                continue
            bodyguard = unit.get_attached_unit_root()
            if bodyguard is None or bodyguard is unit:
                continue
            if not getattr(bodyguard, "deployed", True):
                continue
            if str(getattr(bodyguard, "reserve_status", "deployed")) != "deployed":
                continue
            if bodyguard.is_in_reserves():
                continue
            if bool(getattr(bodyguard, "embarked_in", None)):
                continue
            if bodyguard.is_embarked:
                continue
            if len(bodyguard.models or []) <= 0:
                continue
            if not list(bodyguard.models_lost or []):
                continue

            amount_roll = str(ability.get("amount_roll", "") or "").strip().upper()
            amount = int(ability.get("amount", 0) or 0)
            if amount_roll:
                try:
                    from ...utility.dice import get_roll
                    rolled = int(get_roll(amount_roll) or 0)
                except Exception:
                    rolled = 0
                if rolled <= 0:
                    continue
                amount = int(rolled)
                ability = dict(ability or {})
                ability["rolled_amount"] = int(rolled)
            if amount <= 0:
                continue
            self._queue_bodyguard_return_decision(
                player=player,
                leader_unit=unit,
                bodyguard_unit=bodyguard,
                ability=ability,
                remaining=amount,
            )

    def _on_phase_start_dance_of_death(self, player=None, phase=None, **_kwargs) -> None:
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        from ..decision_kinds import DECISION_CHOOSE_DANCE_OF_DEATH
        from ..decisions import DecisionOption, DecisionRequest

        pending_units = set()
        try:
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_DANCE_OF_DEATH:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    uid = str(ctx.get("unit_id", "") or "")
                    if uid:
                        pending_units.add(uid)
        except Exception:
            pending_units = set()

        for p in list(getattr(self, "players", []) or []):
            if p is None:
                continue
            army = p.get_army()
            if army is None:
                continue
            for unit in list(army.units or []):
                if unit is None or not unit.is_alive():
                    continue
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                if root is None or not root.is_alive():
                    continue
                try:
                    if not root.has_dance_of_death():
                        continue
                except Exception:
                    continue
                try:
                    choice_fn = getattr(root, "_dance_of_death_choice", None)
                    if callable(choice_fn) and choice_fn(game=self):
                        continue
                except Exception:
                    pass
                unit_id = str(get_entity_id(root) or "")
                if unit_id and unit_id in pending_units:
                    continue
                options = [
                    DecisionOption.create(
                        "Hero's Prowess",
                        payload={"choice": "HERO", "summary": "Re-roll Hit rolls of 1 for this unit."},
                    ),
                    DecisionOption.create(
                        "Villain's Doom",
                        payload={"choice": "VILLAIN", "summary": "Add 1 to Wound rolls for this unit."},
                    ),
                    DecisionOption.create(
                        "Trickster's Grace",
                        payload={"choice": "TRICKSTER", "summary": "Attacks against this unit suffer -1 to hit."},
                    ),
                ]
                ctx = {
                    "unit_id": unit_id,
                    "ability_name": "Dance of Death",
                    "phase_name": pname,
                }
                req = DecisionRequest.create(
                    DECISION_CHOOSE_DANCE_OF_DEATH,
                    "Dance of Death: select a performance.",
                    player_id=getattr(p, "id", None),
                    options=options,
                    context=ctx,
                )
                self.request_decision(req)

    def _on_phase_start_dark_ritual(self, player=None, phase=None, **_kwargs) -> None:
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None:
            return
        army = player.get_army()
        if army is None:
            return

        seen = set()
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None or not root.is_alive():
                continue
            rid = str(maybe_entity_id(root) or "")
            if rid in seen:
                continue
            seen.add(rid)
            if not self._unit_on_battlefield_for_reposition(root):
                continue
            try:
                rule = root.get_dark_ritual_rule()
            except Exception:
                rule = None
            if not rule:
                continue
            ability_key = str(rule.get("ability_key") or "dark_ritual").strip().lower() or "dark_ritual"
            if root.has_used_unit_once_per_battle(ability_key):
                continue
            if not root._unit_contains_model_with_keyword("CULT DEMAGOGUE"):
                continue
            sr = getattr(root, "special_rules", None)
            if isinstance(sr, dict) and sr.get("dark_ritual_active"):
                continue
            ability_name = str(rule.get("source", "") or "Dark Ritual").strip() or "Dark Ritual"
            unit_id = maybe_entity_id(root)
            ctx = {
                "ability_name": ability_name,
                "phase": "Command phase",
                "unit": getattr(root, "name", ""),
                "unit_id": unit_id,
                "ability_key": ability_key,
            }
            message = (
                f"Use {ability_name} for {getattr(root, 'name', 'Unit')}? (Once per battle)\n"
                "Until end of turn: can charge after Advance; +1 to Hit and Wound."
            )
            self._queue_optional_ability_confirmation(
                player=player,
                ability_key="dark_ritual",
                ability_name=ability_name,
                message=message,
                context=ctx,
                payload={"unit_id": unit_id, "ability_key": ability_key},
                instance_key=str(unit_id or ""),
            )

    def _on_phase_start_post_shoot_leadership_debuff_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear post-shoot Leadership/Battle-shock debuffs at the start of the owner's Shooting phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "SHOOTING_PHASE":
            return
        if player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Post-shoot debuff cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Post-shoot debuff cleanup requires an army for {p.name}.")
            for unit in list(army.units):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if str(sr.get("post_shoot_leadership_debuff_owner", "") or "") != owner_id:
                    continue
                if sr.get("post_shoot_leadership_debuff_active"):
                    unit.clear_post_shoot_leadership_debuff()

    def _on_phase_start_wracked_with_agonies_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear Wracked with Agonies effects at the start of the owner's Command phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Wracked with Agonies cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Wracked with Agonies cleanup requires an army for {p.name}.")
            for unit in list(army.units):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if str(sr.get("wracked_with_agonies_owner", "") or "") != owner_id:
                    continue
                if sr.get("wracked_with_agonies_active"):
                    clear_fn = getattr(unit, "clear_wracked_with_agonies", None)
                    if callable(clear_fn):
                        clear_fn()
                    else:
                        for key in (
                            "wracked_with_agonies_active",
                            "wracked_with_agonies_owner",
                            "wracked_with_agonies_turn",
                            "wracked_with_agonies_source",
                            "wracked_with_agonies_move_penalty",
                            "wracked_with_agonies_charge_penalty",
                        ):
                            sr.pop(key, None)
                        unit.special_rules = sr

    def _on_phase_start_snared_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear Snared effects at the start of the owner's Command phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Snared cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Snared cleanup requires an army for {p.name}.")
            for unit in list(army.units):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if str(sr.get("snared_owner", "") or "") != owner_id:
                    continue
                if sr.get("snared_active"):
                    clear_fn = getattr(unit, "clear_snared", None)
                    if callable(clear_fn):
                        clear_fn()
                    else:
                        for key in (
                            "snared_active",
                            "snared_owner",
                            "snared_turn",
                            "snared_source",
                            "snared_weapon_key",
                            "snared_weapon_name",
                        ):
                            sr.pop(key, None)
                        unit.special_rules = sr

    def _on_phase_start_post_shoot_suppression_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear post-shoot Suppressed effects at the start of the owner's Command phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Post-shoot suppression cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Post-shoot suppression cleanup requires an army for {p.name}.")
            for unit in list(army.units):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if str(sr.get("post_shoot_suppressed_owner", "") or "") != owner_id:
                    continue
                if sr.get("post_shoot_suppressed_active"):
                    for key in (
                        "post_shoot_suppressed_active",
                        "post_shoot_suppressed_owner",
                        "post_shoot_suppressed_turn",
                        "post_shoot_suppressed_source",
                    ):
                        sr.pop(key, None)
                    unit.special_rules = sr

    def _on_phase_start_post_shoot_afflicted_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear post-shoot Afflicted markers at the start of the owner's Command phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Post-shoot Afflicted cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Post-shoot Afflicted cleanup requires an army for {p.name}.")
            for unit in list(army.units):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if str(sr.get("post_shoot_afflicted_owner", "") or "") != owner_id:
                    continue
                if not sr.get("post_shoot_afflicted_active"):
                    continue
                for key in (
                    "post_shoot_afflicted_active",
                    "post_shoot_afflicted_owner",
                    "post_shoot_afflicted_turn",
                    "post_shoot_afflicted_source",
                ):
                    sr.pop(key, None)
                unit.special_rules = sr

    def _on_phase_start_pinned_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear Pinned effects at the start of the owner's Command phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Pinned cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Pinned cleanup requires an army for {p.name}.")
            for unit in list(army.units):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if str(sr.get("pinned_owner", "") or "") != owner_id:
                    continue
                if sr.get("pinned_active"):
                    clear_fn = getattr(unit, "clear_pinned", None)
                    if callable(clear_fn):
                        clear_fn()
                    else:
                        for key in (
                            "pinned_active",
                            "pinned_owner",
                            "pinned_turn",
                            "pinned_source",
                            "pinned_move_penalty",
                            "pinned_charge_penalty",
                        ):
                            sr.pop(key, None)
                        unit.special_rules = sr

    def _on_phase_end_aflame_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear Aflame effects at the end of the opponent's next turn (end of Fight phase)."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        if player is None:
            return
        current_owner = str(getattr(player, "id", "") or "")
        if not current_owner:
            return
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            current_turn = 0
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Aflame cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Aflame cleanup requires an army for {p.name}.")
            for unit in list(army.units):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if not sr.get("aflame_active"):
                    continue
                owner_id = str(sr.get("aflame_owner", "") or "")
                if not owner_id or owner_id == current_owner:
                    continue
                try:
                    marked_turn = int(sr.get("aflame_turn", 0) or 0)
                except Exception:
                    marked_turn = 0
                if marked_turn and current_turn < marked_turn:
                    continue
                clear_fn = getattr(unit, "clear_aflame", None)
                if callable(clear_fn):
                    clear_fn()
                    continue
                try:
                    unit.remove_characteristic_modifiers_by_source("ability:aflame")
                except Exception:
                    pass
                adv_mods = list(sr.get("advance_roll_modifiers", []) or [])
                kept_adv = []
                for item in adv_mods:
                    if isinstance(item, dict) and item.get("tag") == "ability:aflame":
                        continue
                    kept_adv.append(item)
                if kept_adv:
                    sr["advance_roll_modifiers"] = kept_adv
                else:
                    sr.pop("advance_roll_modifiers", None)
                charge_mods = list(sr.get("charge_roll_modifiers", []) or [])
                kept_charge = []
                for item in charge_mods:
                    if isinstance(item, dict) and item.get("tag") == "ability:aflame":
                        continue
                    kept_charge.append(item)
                if kept_charge:
                    sr["charge_roll_modifiers"] = kept_charge
                else:
                    sr.pop("charge_roll_modifiers", None)
                for key in (
                    "aflame_active",
                    "aflame_owner",
                    "aflame_turn",
                    "aflame_source",
                    "aflame_move_penalty",
                    "aflame_advance_penalty",
                    "aflame_charge_penalty",
                ):
                    sr.pop(key, None)
                unit.special_rules = sr

    def _on_phase_start_misfortune_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear Misfortune effects at the start of the owner's Command phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Misfortune cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Misfortune cleanup requires an army for {p.name}.")
            for unit in list(army.units):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if str(sr.get("misfortune_owner", "") or "") != owner_id:
                    continue
                if sr.get("misfortune_active") or sr.get("misfortune_selected_turn"):
                    for key in (
                        "misfortune_active",
                        "misfortune_owner",
                        "misfortune_turn",
                        "misfortune_source",
                        "misfortune_penalty",
                        "misfortune_selected_owner",
                        "misfortune_selected_turn",
                    ):
                        sr.pop(key, None)
                    unit.special_rules = sr

    def _on_phase_start_nurgles_rot_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear Nurgle's Rot effects at the start of the owner's Movement phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "MOVEMENT_PHASE":
            return
        if player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Nurgle's Rot cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Nurgle's Rot cleanup requires an army for {p.name}.")
            for unit in list(army.units):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if str(sr.get("nurgles_rot_owner", "") or "") != owner_id:
                    continue
                if sr.get("nurgles_rot_active"):
                    for key in (
                        "nurgles_rot_active",
                        "nurgles_rot_owner",
                        "nurgles_rot_turn",
                        "nurgles_rot_source",
                        "nurgles_rot_penalty",
                    ):
                        sr.pop(key, None)
                    unit.special_rules = sr

    def _on_phase_start_death_hex_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear Death Hex effects at the start of the owner's Movement phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "MOVEMENT_PHASE":
            return
        if player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Death Hex cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Death Hex cleanup requires an army for {p.name}.")
            for unit in list(army.units):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if str(sr.get("death_hex_owner", "") or "") != owner_id:
                    continue
                if sr.get("death_hex_active"):
                    for key in (
                        "death_hex_active",
                        "death_hex_owner",
                        "death_hex_turn",
                        "death_hex_source",
                        "death_hex_ap_bonus",
                    ):
                        sr.pop(key, None)
                    unit.special_rules = sr

    def _on_phase_end_shooting_phase_disrupt_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear Shooting phase disruption effects at the end of the active player's Shooting phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "SHOOTING_PHASE":
            return
        if player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Shooting disruption cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Shooting disruption cleanup requires an army for {p.name}.")
            for unit in list(army.units):
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if str(sr.get("shooting_phase_hit_penalty_owner", "") or "") == owner_id and sr.get("shooting_phase_hit_penalty_active"):
                    for key in (
                        "shooting_phase_hit_penalty_active",
                        "shooting_phase_hit_penalty_owner",
                        "shooting_phase_hit_penalty_turn",
                        "shooting_phase_hit_penalty_source",
                        "shooting_phase_hit_penalty_expires_phase",
                    ):
                        sr.pop(key, None)
                if str(sr.get("shooting_phase_ineligible_owner", "") or "") == owner_id and sr.get("shooting_phase_ineligible_active"):
                    for key in (
                        "shooting_phase_ineligible_active",
                        "shooting_phase_ineligible_owner",
                        "shooting_phase_ineligible_turn",
                        "shooting_phase_ineligible_source",
                        "shooting_phase_ineligible_expires_phase",
                    ):
                        sr.pop(key, None)
                unit.special_rules = sr

    def _on_phase_start_movement_phase_visible_wound_bonus_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear movement-phase wound bonus markers at the start of the owner's Command phase."""
        self._cleanup_movement_phase_visible_bonus(player=player, phase=phase, kind="wound")

    def _on_phase_start_movement_phase_visible_hit_bonus_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear movement-phase hit bonus markers at the start of the owner's Command phase."""
        self._cleanup_movement_phase_visible_bonus(player=player, phase=phase, kind="hit")

    def _on_phase_start_spirit_mark_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Clear Spirit Mark effects at the start of the owner's Movement phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "MOVEMENT_PHASE":
            return
        if player is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Spirit Mark cleanup requires an army for {getattr(player, 'name', 'player')}.")
        for unit in list(getattr(army, "units", []) or []):
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            if not sr.get("spirit_mark_active"):
                continue
            if str(sr.get("spirit_mark_owner", "") or "") != owner_id:
                continue
            try:
                mark_turn = int(sr.get("spirit_mark_turn", 0) or 0)
            except Exception:
                mark_turn = 0
            if mark_turn == int(turn or 0):
                continue
            for key in (
                "spirit_mark_active",
                "spirit_mark_owner",
                "spirit_mark_turn",
                "spirit_mark_source",
                "spirit_mark_target_id",
                "spirit_mark_sustained_hits_value",
                "spirit_mark_keyword",
            ):
                sr.pop(key, None)
            unit.special_rules = sr

    def _on_phase_start_engagement_battleshock(self, player=None, phase=None, **_kwargs) -> None:
        """Fight phase: enemy units within Engagement Range of a model must take Battle-shock tests."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        game_map = self.map
        if game_map is None:
            raise RuntimeError("Engagement Battle-shock requires a game map.")

        from ...utility.aura_utils import model_within_engagement_range_of_unit

        def _apply_battleshock(target_unit, *, modifier: int = 0, reason: str = "") -> None:
            if target_unit is None:
                return
            sr = getattr(target_unit, "special_rules", None)
            if not isinstance(sr, dict):
                sr = {}
            if modifier:
                current = int(sr.get("battle_shock_test_modifier", 0) or 0)
                sr["battle_shock_test_modifier"] = current + int(modifier)
                if reason:
                    reasons = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
                    reasons.append(reason)
                    sr["battle_shock_test_modifier_reasons"] = reasons
            target_unit.special_rules = sr
            target_unit.take_battle_shock_test(int(getattr(self, "turn", 0) or 1))

        def _unit_in_engagement_with_unit(source_unit, target_unit) -> bool:
            if source_unit is None or target_unit is None:
                return False
            within_fn = getattr(game_map, "is_within_engagement_range", None)
            if callable(within_fn):
                try:
                    return bool(within_fn(source_unit, target_unit))
                except Exception:
                    return False
            for model in list(getattr(source_unit, "models", []) or []):
                try:
                    if model_within_engagement_range_of_unit(model, target_unit):
                        return True
                except Exception:
                    continue
            return False

        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Engagement Battle-shock requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Engagement Battle-shock requires an army for {p.name}.")
            tested_units: set[tuple[str, str]] = set()
            for unit in list(army.units):
                if unit is None:
                    continue
                if not unit.is_alive() or not getattr(unit, "deployed", True):
                    continue
                if unit.is_in_reserves():
                    continue
                if unit.is_embarked:
                    continue

                enemy_roots = []
                seen_enemy = set()
                for enemy in game_map.get_enemy_units(unit):
                    if enemy is None:
                        continue
                    root = enemy.get_attached_unit_root()
                    key = get_entity_id(root)
                    if key in seen_enemy:
                        continue
                    seen_enemy.add(key)
                    if not root.is_alive() or not getattr(root, "deployed", True):
                        continue
                    if root.is_in_reserves():
                        continue
                    if root.is_embarked:
                        continue
                    enemy_roots.append(root)

                if not enemy_roots:
                    continue

                unit_specs = unit.unit_start_fight_phase_engagement_battleshock_specs() or []
                for spec in unit_specs:
                    source = str(spec.get("source", "") or "Fight phase Battle-shock").strip()
                    penalty = 0
                    try:
                        penalty = int(spec.get("penalty", 0) or 0)
                    except Exception:
                        penalty = 0
                    for enemy_root in enemy_roots:
                        if not _unit_in_engagement_with_unit(unit, enemy_root):
                            continue
                        key = (str(get_entity_id(enemy_root)), source.lower())
                        if key in tested_units:
                            continue
                        tested_units.add(key)
                        mod = 0
                        reason = ""
                        if penalty and enemy_root.is_below_half_strength():
                            mod = -penalty
                            reason = "Below Half-strength"
                        _apply_battleshock(enemy_root, modifier=mod, reason=reason)
                        from ...utility.event_bus import append_action
                        if p is not None:
                            label = f"{getattr(unit, 'name', 'Unit')} {source}".strip()
                            append_action(
                                p,
                                f"{label}: {getattr(enemy_root, 'name', 'Unit')} takes a Battle-shock test.",
                            )

                for model in list(unit.models or []):
                    if not getattr(model, "is_alive", False):
                        continue
                    specs = unit.model_start_fight_phase_engagement_battleshock_specs(model)
                    if specs:
                        for spec in specs:
                            source = str(spec.get("source", "") or "Fight phase Battle-shock").strip()
                            penalty = 0
                            try:
                                penalty = int(spec.get("penalty", 0) or 0)
                            except Exception:
                                penalty = 0
                            for enemy_root in enemy_roots:
                                if not model_within_engagement_range_of_unit(model, enemy_root):
                                    continue
                                mod = 0
                                reason = ""
                                if penalty and enemy_root.is_below_half_strength():
                                    mod = -penalty
                                    reason = "Below Half-strength"
                                _apply_battleshock(enemy_root, modifier=mod, reason=reason)
                                from ...utility.event_bus import append_action
                                if p is not None:
                                    label = f"{getattr(model, 'name', 'Model')} {source}".strip()
                                    append_action(
                                        p,
                                        f"{label}: {getattr(enemy_root, 'name', 'Unit')} takes a Battle-shock test.",
                                    )

                    aura_specs = []
                    try:
                        aura_specs = unit.model_start_fight_phase_aura_battleshock_specs(model) or []
                    except Exception:
                        aura_specs = []
                    for spec in aura_specs:
                        source = str(spec.get("source", "") or "Fight phase Battle-shock").strip()
                        try:
                            range_value = int(spec.get("range", 0) or 0)
                        except Exception:
                            range_value = 0
                        if range_value <= 0:
                            continue
                        exclude_keywords = list(spec.get("exclude_keywords", []) or [])
                        for enemy_root in enemy_roots:
                            try:
                                excluded = any(enemy_root.has_any_keyword(kw) for kw in exclude_keywords)
                            except Exception:
                                excluded = False
                            if excluded:
                                continue
                            try:
                                if not unit._model_within_range_of_unit(model, enemy_root, float(range_value)):
                                    continue
                            except Exception:
                                continue
                            _apply_battleshock(enemy_root)
                            from ...utility.event_bus import append_action
                            if p is not None:
                                label = f"{getattr(model, 'name', 'Model')} {source}".strip()
                                append_action(
                                    p,
                                    f"{label}: {getattr(enemy_root, 'name', 'Unit')} takes a Battle-shock test.",
                                )

    def _on_phase_start_empowered_by_death(self, player=None, phase=None, **_kwargs) -> None:
        """Fight phase: below Starting Strength units with Empowered by Death gain Fight First until end of phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        for p in list(getattr(self, "players", []) or []):
            if p is None:
                continue
            army = self._get_player_army(p)
            if army is None:
                continue
            processed: set[str] = set()
            for unit in list(getattr(army, "units", []) or []):
                if unit is None:
                    continue
                try:
                    root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
                except Exception:
                    root = unit
                root_id = str(get_entity_id(root) or "")
                if root_id and root_id in processed:
                    continue
                try:
                    if not getattr(unit, "has_empowered_by_death", lambda: False)():
                        continue
                except Exception:
                    continue
                try:
                    if not root.is_alive() or not getattr(root, "deployed", True):
                        continue
                except Exception:
                    continue
                try:
                    if root.is_in_reserves() or root.is_embarked:
                        continue
                except Exception:
                    pass
                try:
                    if not root.is_below_starting_strength():
                        continue
                except Exception:
                    continue
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["empowered_by_death_active"] = True
                sr["empowered_by_death_expires_phase"] = "FIGHT_PHASE"
                try:
                    sources = list(unit.empowered_by_death_sources() or [])
                    if sources:
                        sr["empowered_by_death_source"] = sources[0]
                except Exception:
                    pass
                root.special_rules = sr
                if root_id:
                    processed.add(root_id)

    def _on_phase_start_herald_of_ynnead(self, player=None, phase=None, **_kwargs) -> None:
        """Fight phase start: select an engaged enemy unit to mark for wound reroll 1s (Herald of Ynnead)."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        game_map = self.map
        if game_map is None:
            return
        from ...utility.aura_utils import model_within_engagement_range_of_unit

        pending_models = set()
        try:
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    if str(ctx.get("ability", "") or "") != "herald_of_ynnead":
                        continue
                    mid = str(ctx.get("model_id", "") or "")
                    if mid:
                        pending_models.add(mid)
        except Exception:
            pending_models = set()

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        def _model_sort_key(m):
            try:
                return str(get_entity_id(m))
            except Exception:
                return str(getattr(m, "name", "") or "")

        for p in list(getattr(self, "players", []) or []):
            if p is None:
                continue
            army = p.get_army()
            if army is None:
                continue
            for unit in sorted(list(army.units or []), key=_unit_sort_key):
                if unit is None:
                    continue
                if not unit.is_alive() or not getattr(unit, "deployed", True):
                    continue
                try:
                    if unit.is_in_reserves() or unit.is_embarked:
                        continue
                except Exception:
                    pass
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                if root is None or not root.is_alive():
                    continue
                try:
                    models = list(root.get_attached_unit_models() or [])
                except Exception:
                    models = list(getattr(root, "models", []) or [])
                if not models:
                    continue
                for model in sorted([m for m in models if getattr(m, "is_alive", True)], key=_model_sort_key):
                    model_id = str(get_entity_id(model) or "")
                    if model_id and model_id in pending_models:
                        continue
                    specs = root.model_start_fight_phase_engagement_wound_reroll_ones_specs(model) or []
                    if not specs:
                        continue
                    spec = specs[0]
                    ability_name = str(spec.get("source", "") or "Herald of Ynnead").strip() or "Herald of Ynnead"
                    keyword = str(spec.get("keyword", "") or "aeldari").strip().lower() or "aeldari"

                    candidates = []
                    seen_enemy = set()
                    for enemy in list(game_map.get_enemy_units(root) or []):
                        if enemy is None:
                            continue
                        try:
                            enemy_root = enemy.get_attached_unit_root()
                        except Exception:
                            enemy_root = enemy
                        if enemy_root is None or not enemy_root.is_alive():
                            continue
                        try:
                            if not getattr(enemy_root, "deployed", True):
                                continue
                            if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                                continue
                        except Exception:
                            pass
                        eid = str(get_entity_id(enemy_root) or "")
                        if not eid or eid in seen_enemy:
                            continue
                        seen_enemy.add(eid)
                        if not model_within_engagement_range_of_unit(model, enemy_root):
                            continue
                        candidates.append(enemy_root)

                    if not candidates:
                        continue
                    try:
                        candidates = sorted(candidates, key=_unit_sort_key)
                    except Exception:
                        pass
                    options = []
                    for cand in candidates:
                        options.append(
                            DecisionOption.create(
                                str(getattr(cand, "name", "Unit") or "Unit"),
                                payload={"target_unit_id": get_entity_id(cand)},
                            )
                        )
                    if not options:
                        continue
                    request = DecisionRequest.create(
                        DECISION_CHOOSE_QUARRY,
                        f"{ability_name}: select a target.",
                        player_id=getattr(p, "id", None),
                        options=options,
                        context={
                            "ability": "herald_of_ynnead",
                            "ability_name": ability_name,
                            "attacker_unit_id": get_entity_id(root),
                            "model_id": model_id,
                            "keyword": keyword,
                        },
                    )
                    self.request_decision(request)

    def _on_phase_start_fight_phase_target_attack_bonus(self, player=None, phase=None, **_kwargs) -> None:
        """Fight phase start: select an enemy unit to mark for attack bonuses (e.g., Blood Throne, The Eternal Dance)."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        game_map = self.map
        if game_map is None:
            return

        pending_models = set()
        try:
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    if str(ctx.get("ability", "") or "") != "fight_phase_target_attack_bonus":
                        continue
                    mid = str(ctx.get("model_id", "") or "")
                    if mid:
                        pending_models.add(mid)
        except Exception:
            pending_models = set()

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        def _model_sort_key(m):
            try:
                return str(get_entity_id(m))
            except Exception:
                return str(getattr(m, "name", "") or "")

        for p in list(getattr(self, "players", []) or []):
            if p is None:
                continue
            army = p.get_army()
            if army is None:
                continue
            enemy_roots = self._collect_enemy_unit_roots(p)
            if not enemy_roots:
                continue
            enemy_roots.sort(key=_unit_sort_key)
            for unit in sorted(list(army.units or []), key=_unit_sort_key):
                if unit is None:
                    continue
                if not unit.is_alive() or not getattr(unit, "deployed", True):
                    continue
                try:
                    if unit.is_in_reserves() or unit.is_embarked:
                        continue
                except Exception:
                    pass
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                if root is None or not root.is_alive():
                    continue
                try:
                    models = list(root.get_attached_unit_models() or [])
                except Exception:
                    models = list(getattr(root, "models", []) or [])
                if not models:
                    continue
                for model in sorted([m for m in models if getattr(m, "is_alive", True)], key=_model_sort_key):
                    model_id = str(get_entity_id(model) or "")
                    if model_id and model_id in pending_models:
                        continue
                    specs = root.model_start_fight_phase_target_attack_bonus_specs(model) or []
                    if not specs:
                        continue
                    for spec in specs:
                        try:
                            range_value = int(spec.get("range", 0) or 0)
                        except Exception:
                            range_value = 0
                        if range_value <= 0:
                            continue
                        requires_visibility = bool(spec.get("requires_visibility", False))
                        if requires_visibility:
                            candidates = self._visible_enemy_candidates_for_model(
                                source_unit=root,
                                model=model,
                                enemy_roots=enemy_roots,
                                range_value=float(range_value),
                                game_map=game_map,
                            )
                        else:
                            candidates = self._enemy_candidates_within_range_of_model(
                                model=model,
                                enemy_roots=enemy_roots,
                                range_value=float(range_value),
                            )
                        if not candidates:
                            continue
                        self._queue_fight_phase_target_attack_bonus(
                            player=p,
                            source_unit=root,
                            model=model,
                            candidates=candidates,
                            spec=spec,
                        )

    def _on_phase_start_malign_sacrifice(self, player=None, phase=None, **_kwargs) -> None:
        """Fight phase start: optional Malign Sacrifice (select Dark Disciple + engaged enemy)."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        game_map = self.map
        if game_map is None:
            return

        pending_units = set()
        try:
            queue = getattr(self, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    if str(ctx.get("ability", "") or "") != "malign_sacrifice":
                        continue
                    uid = str(ctx.get("source_unit_id", "") or "")
                    if uid:
                        pending_units.add(uid)
        except Exception:
            pending_units = set()

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        def _model_sort_key(m):
            try:
                return str(get_entity_id(m))
            except Exception:
                return str(getattr(m, "name", "") or "")

        for p in list(getattr(self, "players", []) or []):
            if p is None:
                continue
            army = p.get_army()
            if army is None:
                continue
            for unit in sorted(list(army.units or []), key=_unit_sort_key):
                if unit is None:
                    continue
                if not unit.is_alive() or not getattr(unit, "deployed", True):
                    continue
                try:
                    if unit.is_in_reserves() or unit.is_embarked:
                        continue
                except Exception:
                    pass
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                if root is None or not root.is_alive():
                    continue
                uid = str(get_entity_id(root) or "")
                if uid and uid in pending_units:
                    continue
                specs = root.unit_start_fight_phase_malign_sacrifice_specs() or []
                if not specs:
                    continue
                spec = specs[0]
                ability_name = str(spec.get("source", "") or "Malign Sacrifice").strip() or "Malign Sacrifice"
                model_name = str(spec.get("model_name", "") or "dark disciple").strip() or "dark disciple"
                norm_target = root._normalize_attached_unit_name(model_name)
                try:
                    models = list(root.get_attached_unit_models() or [])
                except Exception:
                    models = list(getattr(root, "models", []) or [])
                disciples = []
                target_tokens = set(norm_target.split()) if norm_target else set()
                for m in list(models or []):
                    try:
                        if not getattr(m, "is_alive", True):
                            continue
                    except Exception:
                        continue
                    name = root._normalize_attached_unit_name(getattr(m, "name", ""))
                    if not name:
                        continue
                    if norm_target and (norm_target in name or (target_tokens and target_tokens.issubset(set(name.split())))):
                        disciples.append(m)
                if not disciples:
                    continue

                enemy_units = []
                for enemy in list(game_map.get_enemy_units(root) or []):
                    if enemy is None:
                        continue
                    try:
                        enemy_root = enemy.get_attached_unit_root()
                    except Exception:
                        enemy_root = enemy
                    if enemy_root is None or not enemy_root.is_alive():
                        continue
                    try:
                        if not getattr(enemy_root, "deployed", True):
                            continue
                        if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                            continue
                    except Exception:
                        pass
                    try:
                        if not game_map.is_within_engagement_range(root, enemy_root):
                            continue
                    except Exception:
                        continue
                    enemy_units.append(enemy_root)
                if not enemy_units:
                    continue

                try:
                    disciples.sort(key=_model_sort_key)
                except Exception:
                    pass
                try:
                    enemy_units.sort(key=_unit_sort_key)
                except Exception:
                    pass

                from ..decisions import DecisionOption, DecisionRequest

                options = [
                    DecisionOption.create(
                        "Do not use",
                        payload={"action": "skip"},
                    )
                ]
                for disciple in disciples:
                    for enemy_root in enemy_units:
                        label = f"{getattr(disciple, 'name', 'Model')} -> {getattr(enemy_root, 'name', 'Unit')}"
                        options.append(
                            DecisionOption.create(
                                label,
                                payload={
                                    "model_id": get_entity_id(disciple),
                                    "target_unit_id": get_entity_id(enemy_root),
                                },
                            )
                        )
                if len(options) <= 1:
                    continue
                request = DecisionRequest.create(
                    DECISION_CHOOSE_QUARRY,
                    f"{ability_name}: select a sacrifice target.",
                    player_id=getattr(p, "id", None),
                    options=options,
                    context={
                        "ability": "malign_sacrifice",
                        "ability_name": ability_name,
                        "source_unit_id": uid,
                    },
                )
                self.request_decision(request)

    def _on_phase_start_hallowed_ground(self, player=None, phase=None, **_kwargs) -> None:
        if phase is None:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Hallowed Ground phase start requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Hallowed Ground requires an army for {p.name}.")
            mgr = getattr(army, "grey_knights_detachments", None)
            if mgr is None or not hasattr(mgr, "on_phase_start"):
                continue
            mgr.on_phase_start(game=self)

    def _on_phase_start_cabal_of_sorcerers(self, player=None, phase=None, **_kwargs) -> None:
        """Reset Cabal of Sorcerers usage at the start of the active player's Shooting phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "SHOOTING_PHASE":
            return
        if player is None:
            raise RuntimeError("Cabal of Sorcerers requires an active player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Cabal of Sorcerers requires an army for {player.name}.")
        mgr = getattr(army, "cabal_of_sorcerers", None)
        if mgr is None:
            return
        mgr.on_shooting_phase_start(game=self, player=player)

    def _on_phase_start_for_the_greater_good(self, player=None, phase=None, **_kwargs) -> None:
        """Prompt Observer selection at the start of the active player's Shooting phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "SHOOTING_PHASE":
            return
        if player is None:
            raise RuntimeError("For the Greater Good requires an active player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"For the Greater Good requires an army for {player.name}.")
        mgr = getattr(army, "for_the_greater_good", None)
        if mgr is None:
            return
        mgr.on_shooting_phase_start(game=self, player=player)
        es = getattr(self, "event_system", None)
        if es is None or not hasattr(es, "subscribers"):
            raise RuntimeError("Event system missing for For the Greater Good prompt.")
        subs = getattr(es, "subscribers", None)
        if not isinstance(subs, dict):
            raise RuntimeError("Event system subscribers not configured.")
        if subs.get("for_the_greater_good_prompt"):
            es.publish("for_the_greater_good_prompt", player=player, game=self)

    def _on_phase_start_shooting_phase_visible_battleshock(self, player=None, phase=None, **_kwargs) -> None:
        """Start of Shooting phase: select a visible enemy within range to take a Battle-shock test."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "SHOOTING_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        army = self._get_player_army(player)
        if army is None:
            return
        game_map = self.map
        if game_map is None:
            return

        from ...utility.entity_ids import get_entity_id

        enemy_roots = self._collect_enemy_unit_roots(player)
        if not enemy_roots:
            return

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        enemy_roots.sort(key=_unit_sort_key)

        for unit in sorted(list(army.units or []), key=_unit_sort_key):
            if unit is None:
                continue
            if not getattr(unit, "is_alive", lambda: False)():
                continue
            if not getattr(unit, "deployed", True):
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            if not models:
                continue

            def _model_sort_key(m):
                try:
                    return str(get_entity_id(m))
                except Exception:
                    return str(getattr(m, "name", "") or "")

            for model in sorted([m for m in models if getattr(m, "is_alive", True)], key=_model_sort_key):
                spec_fn = getattr(root, "model_start_shooting_phase_visible_battleshock_specs", None)
                if not callable(spec_fn):
                    continue
                specs = spec_fn(model) or []
                if not specs:
                    continue
                source_unit = getattr(model, "parent_unit", None) or root
                for spec in specs:
                    try:
                        range_value = int(spec.get("range", 0) or 0)
                    except Exception:
                        range_value = 0
                    if range_value <= 0:
                        continue
                    candidates = self._visible_enemy_candidates_for_model(
                        source_unit=source_unit,
                        model=model,
                        enemy_roots=enemy_roots,
                        range_value=float(range_value),
                        game_map=game_map,
                    )
                    if not candidates:
                        continue
                    self._queue_start_shooting_phase_visible_battleshock(
                        player=player,
                        source_unit=source_unit,
                        model=model,
                        candidates=candidates,
                        spec=spec,
                    )

    def _on_phase_start_death_hex(self, player=None, phase=None, **_kwargs) -> None:
        """Start of Shooting phase: Death Hex selection and roll."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "SHOOTING_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        army = self._get_player_army(player)
        if army is None:
            return
        game_map = self.map
        if game_map is None:
            return

        try:
            ability_used = getattr(player, "_ability_used_this_turn", None)
        except Exception:
            ability_used = None
        ability_key = "DEATH_HEX"
        if callable(ability_used) and ability_used(ability_key):
            return

        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) == "death_hex" and str(ctx.get("ability_key", "") or "") == ability_key:
                    return

        from ...utility.entity_ids import get_entity_id

        enemy_roots = self._collect_enemy_unit_roots(player)
        if not enemy_roots:
            return

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        def _model_sort_key(m):
            try:
                return str(get_entity_id(m))
            except Exception:
                return str(getattr(m, "name", "") or "")

        enemy_roots.sort(key=_unit_sort_key)
        pairs: list[tuple[Any, Any, Any, dict]] = []
        seen: set[tuple[str, str]] = set()
        ability_name = None
        ap_bonus = 1
        optional = True

        for unit in sorted(list(army.units or []), key=_unit_sort_key):
            if unit is None:
                continue
            if not getattr(unit, "is_alive", lambda: False)():
                continue
            if not getattr(unit, "deployed", True):
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            if not models:
                continue

            for model in sorted([m for m in models if getattr(m, "is_alive", True)], key=_model_sort_key):
                spec_fn = getattr(root, "model_start_shooting_phase_death_hex_specs", None)
                if not callable(spec_fn):
                    continue
                specs = spec_fn(model) or []
                if not specs:
                    continue
                source_unit = getattr(model, "parent_unit", None) or root
                for spec in specs:
                    try:
                        range_value = int(spec.get("range", 0) or 0)
                    except Exception:
                        range_value = 0
                    if range_value <= 0:
                        continue
                    candidates = self._visible_enemy_candidates_for_model(
                        source_unit=source_unit,
                        model=model,
                        enemy_roots=enemy_roots,
                        range_value=float(range_value),
                        game_map=game_map,
                    )
                    if not candidates:
                        continue
                    ability_name = ability_name or str(spec.get("source", "") or "Death Hex").strip() or "Death Hex"
                    try:
                        ap_bonus = int(spec.get("ap_bonus", 1) or 1)
                    except Exception:
                        ap_bonus = 1
                    optional = bool(spec.get("optional", True))
                    for cand in list(candidates):
                        model_id = str(get_entity_id(model) or "")
                        target_id = str(get_entity_id(cand) or "")
                        if not model_id or not target_id:
                            continue
                        key = (model_id, target_id)
                        if key in seen:
                            continue
                        seen.add(key)
                        pairs.append((model, cand, source_unit, spec))

        if not pairs:
            return

        try:
            from ..decision_kinds import DECISION_CHOOSE_QUARRY
            from ..decisions import DecisionOption, DecisionRequest
        except Exception:
            return

        options = []
        if optional:
            options.append(DecisionOption.create("None", payload={"action": "skip"}))
        pairs.sort(key=lambda t: (str(get_entity_id(t[0]) or ""), str(get_entity_id(t[1]) or "")))
        for model, cand, source_unit, _spec in pairs:
            model_id = str(get_entity_id(model) or "")
            unit_id = str(get_entity_id(source_unit) or "")
            target_id = str(get_entity_id(cand) or "")
            if not model_id or not target_id:
                continue
            label = f"{getattr(model, 'name', 'Model')} -> {getattr(cand, 'name', 'Unit')}"
            options.append(
                DecisionOption.create(
                    label,
                    payload={
                        "target_unit_id": target_id,
                        "model_id": model_id,
                        "source_unit_id": unit_id,
                    },
                )
            )
        if not options:
            return

        ability_name = ability_name or "Death Hex"
        ctx = {
            "ability": "death_hex",
            "ability_name": ability_name,
            "ability_key": ability_key,
            "phase": "Shooting phase",
            "ap_bonus": int(ap_bonus),
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            f"{ability_name}: select a target.",
            player_id=getattr(player, "id", None),
            options=options,
            context=ctx,
        )
        self.request_decision(request)

    def _on_phase_start_model_visible_vehicle_quarry(
        self,
        player=None,
        phase=None,
        *,
        ability_tag: str,
        spec_method_name: str,
        default_ability_name: str,
    ) -> None:
        """Start of Shooting phase: per-model visible enemy VEHICLE target selection helper."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "SHOOTING_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        army = self._get_player_army(player)
        if army is None:
            return
        game_map = self.map
        if game_map is None:
            return

        from ...utility.entity_ids import get_entity_id
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest

        pending_models = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != str(ability_tag or ""):
                    continue
                mid = str(ctx.get("model_id", "") or "")
                if mid:
                    pending_models.add(mid)

        enemy_roots = self._collect_enemy_unit_roots(player)
        if not enemy_roots:
            return

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        def _model_sort_key(m):
            try:
                return str(get_entity_id(m))
            except Exception:
                return str(getattr(m, "name", "") or "")

        enemy_roots.sort(key=_unit_sort_key)

        for unit in sorted(list(army.units or []), key=_unit_sort_key):
            if unit is None:
                continue
            if not getattr(unit, "is_alive", lambda: False)():
                continue
            if not getattr(unit, "deployed", True):
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            if not models:
                continue

            for model in sorted([m for m in models if getattr(m, "is_alive", True)], key=_model_sort_key):
                model_id = str(get_entity_id(model) or "")
                if model_id and model_id in pending_models:
                    continue
                spec_fn = getattr(root, spec_method_name, None)
                if not callable(spec_fn):
                    continue
                specs = list(spec_fn(model) or [])
                if not specs:
                    continue
                source_unit = getattr(model, "parent_unit", None) or root
                queued = False
                for spec in list(specs or []):
                    try:
                        range_value = int(spec.get("range", 0) or 0)
                    except Exception:
                        range_value = 0
                    max_range = float(range_value) if range_value > 0 else 9999.0
                    candidates = self._visible_enemy_candidates_for_model(
                        source_unit=source_unit,
                        model=model,
                        enemy_roots=enemy_roots,
                        range_value=max_range,
                        game_map=game_map,
                    )
                    if not candidates:
                        continue
                    vehicle_candidates = []
                    for cand in list(candidates or []):
                        if cand is None:
                            continue
                        is_vehicle = False
                        try:
                            is_vehicle = bool(cand.has_any_keyword("VEHICLE"))
                        except Exception:
                            try:
                                is_vehicle = bool(cand.has_keyword("VEHICLE"))
                            except Exception:
                                is_vehicle = False
                        if is_vehicle:
                            vehicle_candidates.append(cand)
                    if not vehicle_candidates:
                        continue

                    options = []
                    for cand in sorted(vehicle_candidates, key=_unit_sort_key):
                        target_id = str(get_entity_id(cand) or "")
                        if not target_id:
                            continue
                        options.append(
                            DecisionOption.create(
                                str(getattr(cand, "name", "Unit") or "Unit"),
                                payload={
                                    "target_unit_id": target_id,
                                    "model_id": model_id,
                                    "source_unit_id": str(get_entity_id(source_unit) or ""),
                                },
                            )
                        )
                    if not options:
                        continue
                    ability_name = str(spec.get("source", "") or default_ability_name).strip() or default_ability_name
                    request = DecisionRequest.create(
                        DECISION_CHOOSE_QUARRY,
                        f"{ability_name}: select a VEHICLE target.",
                        player_id=getattr(player, "id", None),
                        options=options,
                        context={
                            "ability": str(ability_tag or ""),
                            "ability_name": ability_name,
                            "source_unit_id": str(get_entity_id(source_unit) or ""),
                            "model_id": model_id,
                            "range": int(range_value or 0),
                            "keyword": str(spec.get("keyword", "") or "").strip().lower(),
                            "phase": "Shooting phase",
                        },
                    )
                    self.request_decision(request)
                    queued = True
                    pending_models.add(model_id)
                    break
                if queued:
                    continue

    def _on_phase_start_spirit_thief(self, player=None, phase=None, **_kwargs) -> None:
        self._on_phase_start_model_visible_vehicle_quarry(
            player=player,
            phase=phase,
            ability_tag="spirit_thief",
            spec_method_name="model_start_shooting_phase_spirit_thief_specs",
            default_ability_name="Spirit Thief",
        )

    def _on_phase_start_corrupt_machine_spirits(self, player=None, phase=None, **_kwargs) -> None:
        self._on_phase_start_model_visible_vehicle_quarry(
            player=player,
            phase=phase,
            ability_tag="corrupt_machine_spirits",
            spec_method_name="model_start_shooting_phase_corrupt_machine_spirits_specs",
            default_ability_name="Corrupt Machine Spirits",
        )

    def _on_phase_end_enrage_machine_spirits(self, player=None, phase=None, **_kwargs) -> None:
        """End of Movement phase: optional enemy VEHICLE within range takes a Battle-shock test."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "MOVEMENT_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        army = self._get_player_army(player)
        if army is None:
            return
        game_map = self.map
        if game_map is None:
            return

        from ...utility.entity_ids import get_entity_id
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest

        pending_model_ids: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "enrage_machine_spirits":
                    continue
                model_id = str(ctx.get("model_id", "") or "")
                if model_id:
                    pending_model_ids.add(model_id)

        enemy_roots = self._collect_enemy_unit_roots(player)
        if not enemy_roots:
            return

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        def _model_sort_key(m):
            try:
                return str(get_entity_id(m))
            except Exception:
                return str(getattr(m, "name", "") or "")

        enemy_roots.sort(key=_unit_sort_key)

        for unit in sorted(list(army.units or []), key=_unit_sort_key):
            if unit is None:
                continue
            if not getattr(unit, "is_alive", lambda: False)():
                continue
            if not getattr(unit, "deployed", True):
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            if not models:
                continue

            for model in sorted([m for m in models if getattr(m, "is_alive", True)], key=_model_sort_key):
                model_id = str(get_entity_id(model) or "")
                if model_id and model_id in pending_model_ids:
                    continue
                spec_fn = getattr(root, "model_movement_phase_end_vehicle_battleshock_specs", None)
                if not callable(spec_fn):
                    continue
                specs = list(spec_fn(model) or [])
                if not specs:
                    continue
                source_unit = getattr(model, "parent_unit", None) or root
                for spec in list(specs or []):
                    try:
                        range_value = int(spec.get("range", 0) or 0)
                    except Exception:
                        range_value = 0
                    if range_value <= 0:
                        continue
                    candidates = self._enemy_candidates_within_range_of_model(
                        model=model,
                        enemy_roots=enemy_roots,
                        range_value=float(range_value),
                    )
                    if not candidates:
                        continue
                    vehicle_candidates = []
                    for cand in list(candidates or []):
                        if cand is None:
                            continue
                        try:
                            if not cand.has_any_keyword("VEHICLE"):
                                continue
                        except Exception:
                            continue
                        vehicle_candidates.append(cand)
                    if not vehicle_candidates:
                        continue

                    options = []
                    if bool(spec.get("optional", False)):
                        options.append(DecisionOption.create("None", payload={"action": "skip"}))
                    for cand in sorted(list(vehicle_candidates), key=_unit_sort_key):
                        target_id = str(get_entity_id(cand) or "")
                        if not target_id:
                            continue
                        options.append(
                            DecisionOption.create(
                                str(getattr(cand, "name", "Unit") or "Unit"),
                                payload={"target_unit_id": target_id},
                            )
                        )
                    if not options:
                        continue
                    if len(options) == 1 and options[0].payload.get("action") == "skip":
                        continue
                    ability_name = str(spec.get("source", "") or "Enrage Machine Spirits").strip() or "Enrage Machine Spirits"
                    request = DecisionRequest.create(
                        DECISION_CHOOSE_QUARRY,
                        f"{ability_name}: select an enemy VEHICLE within {int(range_value)}\" (or None).",
                        player_id=getattr(player, "id", None),
                        options=options,
                        context={
                            "ability": "enrage_machine_spirits",
                            "ability_name": ability_name,
                            "phase": "Movement phase",
                            "source_unit_id": str(get_entity_id(source_unit) or ""),
                            "unit_id": str(get_entity_id(source_unit) or ""),
                            "model_id": model_id,
                            "range": int(range_value),
                            "ability_key": str(spec.get("ability_key", "") or ""),
                        },
                    )
                    self.request_decision(request)
                    if model_id:
                        pending_model_ids.add(model_id)
                    break

    def _on_phase_start_herald_of_the_apocalypse(self, player=None, phase=None, **_kwargs) -> None:
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        game_map = self.map
        if game_map is None:
            return
        from ...utility.aura_utils import unit_within_range_of_unit
        from ...utility.event_bus import append_action

        turn = int(getattr(self, "turn", 0) or 0)

        tested_targets: set[str] = set()

        for opp in list(self.players or []):
            if opp is None or opp is player:
                continue
            army = self._get_player_army(opp)
            if army is None:
                continue
            seen_sources: set[str] = set()
            for unit in list(getattr(army, "units", []) or []):
                if unit is None:
                    continue
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                source_id = str(get_entity_id(root) or "")
                if not source_id or source_id in seen_sources:
                    continue
                seen_sources.add(source_id)
                if not root.is_alive() or not getattr(root, "deployed", True):
                    continue
                try:
                    if root.is_in_reserves() or root.is_embarked:
                        continue
                except Exception:
                    pass
                if not bool(getattr(root, "has_herald_of_the_apocalypse", lambda: False)()):
                    continue

                for enemy in list(game_map.get_enemy_units(root) or []):
                    if enemy is None:
                        continue
                    try:
                        enemy_root = enemy.get_attached_unit_root()
                    except Exception:
                        enemy_root = enemy
                    if enemy_root is None:
                        continue
                    enemy_id = str(get_entity_id(enemy_root) or "")
                    if not enemy_id or enemy_id in tested_targets:
                        continue
                    if not enemy_root.is_alive() or not getattr(enemy_root, "deployed", True):
                        continue
                    try:
                        if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                            continue
                    except Exception:
                        pass
                    if not bool(getattr(enemy_root, "is_below_starting_strength", lambda: False)()):
                        continue
                    if not unit_within_range_of_unit(root, enemy_root, 6.0, use_attached_aggregate=True):
                        continue
                    tested_targets.add(enemy_id)
                    enemy_root.take_battle_shock_test(turn)
                    append_action(
                        opp,
                        f"Herald of the Apocalypse: {getattr(enemy_root, 'name', 'Unit')} takes a Battle-shock test.",
                    )

    def _on_phase_start_master_of_mechanisms_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        army = self._get_player_army(player)
        if army is None:
            return
        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        try:
            current_turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            current_turn = 0

        seen: set[str] = set()
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            uid = str(get_entity_id(root) or "")
            if not uid or uid in seen:
                continue
            seen.add(uid)
            sr = getattr(root, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("master_of_mechanisms_hit_bonus_active"):
                continue
            if str(sr.get("master_of_mechanisms_hit_bonus_owner", "") or "") != owner_id:
                continue
            try:
                selected_turn = int(sr.get("master_of_mechanisms_selected_turn", 0) or 0)
            except Exception:
                selected_turn = 0
            if selected_turn and current_turn and selected_turn == current_turn:
                continue
            for key in (
                "master_of_mechanisms_hit_bonus_active",
                "master_of_mechanisms_hit_bonus",
                "master_of_mechanisms_hit_bonus_owner",
                "master_of_mechanisms_source",
                "master_of_mechanisms_selected_turn_owner",
                "master_of_mechanisms_selected_turn",
            ):
                sr.pop(key, None)
            root.special_rules = sr

    def _on_phase_start_master_of_mechanisms(self, player=None, phase=None, **_kwargs) -> None:
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        army = self._get_player_army(player)
        if army is None:
            return
        game_map = self.map
        if game_map is None:
            return
        from ...utility.aura_utils import model_within_range_of_unit

        owner_id = str(getattr(player, "id", "") or "")
        turn = int(getattr(self, "turn", 0) or 0)

        pending_sources: set[str] = set()
        queue = getattr(self, "decision_queue", None)
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "master_of_mechanisms":
                    continue
                sid = str(ctx.get("source_unit_id", "") or "")
                if sid:
                    pending_sources.add(sid)

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        seen_sources: set[str] = set()
        for unit in sorted(list(getattr(army, "units", []) or []), key=_unit_sort_key):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            source_id = str(get_entity_id(root) or "")
            if not source_id or source_id in seen_sources:
                continue
            seen_sources.add(source_id)
            if source_id in pending_sources:
                continue
            if not root.is_alive() or not getattr(root, "deployed", True):
                continue
            try:
                if root.is_in_reserves() or root.is_embarked:
                    continue
            except Exception:
                pass
            if not bool(getattr(root, "has_master_of_mechanisms", lambda: False)()):
                continue
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            bearer = None
            for model in list(models or []):
                alive_attr = getattr(model, "is_alive", False)
                alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
                if alive:
                    bearer = model
                    break
            if bearer is None:
                continue

            candidates = []
            seen_targets: set[str] = set()
            for cand in sorted(list(getattr(army, "units", []) or []), key=_unit_sort_key):
                if cand is None:
                    continue
                try:
                    target_root = cand.get_attached_unit_root()
                except Exception:
                    target_root = cand
                target_id = str(get_entity_id(target_root) or "")
                if not target_id or target_id in seen_targets:
                    continue
                seen_targets.add(target_id)
                if target_root is root:
                    continue
                if not target_root.is_alive() or not getattr(target_root, "deployed", True):
                    continue
                try:
                    if target_root.is_in_reserves() or target_root.is_embarked:
                        continue
                except Exception:
                    pass
                try:
                    if not target_root.has_any_keyword("VEHICLE"):
                        continue
                except Exception:
                    continue
                if not model_within_range_of_unit(bearer, target_root, 3.0):
                    continue
                tsr = getattr(target_root, "special_rules", None)
                if isinstance(tsr, dict):
                    if (
                        str(tsr.get("master_of_mechanisms_selected_turn_owner", "") or "") == owner_id
                        and int(tsr.get("master_of_mechanisms_selected_turn", 0) or 0) == int(turn or 0)
                    ):
                        continue
                candidates.append(target_root)

            if not candidates:
                continue

            options = [DecisionOption.create("None", payload={"action": "skip"})]
            options.extend(
                DecisionOption.create(
                    str(getattr(c, "name", "Unit") or "Unit"),
                    payload={"target_unit_id": get_entity_id(c)},
                )
                for c in sorted(list(candidates), key=_unit_sort_key)
            )
            if not options:
                continue
            ability_name = "Master of Mechanisms"
            request = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                f"{ability_name}: select a friendly VEHICLE unit within 3\" (or None).",
                player_id=getattr(player, "id", None),
                options=options,
                context={
                    "ability": "master_of_mechanisms",
                    "ability_name": ability_name,
                    "phase": "Command phase",
                    "optional": True,
                    "source_unit_id": source_id,
                    "unit_id": source_id,
                    "model_id": str(get_entity_id(bearer) or ""),
                    "range": 3,
                    "turn_owner": owner_id,
                    "turn": int(turn or 0),
                },
            )
            self.request_decision(request)

    def _on_phase_start_opponent_shooting_phase_disrupt(self, player=None, phase=None, **_kwargs) -> None:
        """Start of opponent's Shooting phase: resolve Mischief and Confusion / Horrible Fascination."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "SHOOTING_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        game_map = self.map
        if game_map is None:
            return

        from ...utility.entity_ids import get_entity_id
        from ..decision_kinds import DECISION_CHOOSE_QUARRY
        from ..decisions import DecisionOption, DecisionRequest

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        def _model_sort_key(m):
            try:
                return str(get_entity_id(m))
            except Exception:
                return str(getattr(m, "name", "") or "")

        for opp in list(getattr(self, "players", []) or []):
            if opp is None or opp is player:
                continue
            army = self._get_player_army(opp)
            if army is None:
                continue
            enemy_roots = self._collect_enemy_unit_roots(opp)
            if not enemy_roots:
                continue
            enemy_roots.sort(key=_unit_sort_key)
            groups: dict[tuple, list[tuple]] = {}
            group_meta: dict[tuple, dict] = {}
            for unit in sorted(list(army.units or []), key=_unit_sort_key):
                if unit is None:
                    continue
                if not getattr(unit, "is_alive", lambda: False)():
                    continue
                if not getattr(unit, "deployed", True):
                    continue
                try:
                    if unit.is_in_reserves() or unit.is_embarked:
                        continue
                except Exception:
                    pass
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                try:
                    models = list(root.get_attached_unit_models() or [])
                except Exception:
                    models = list(getattr(root, "models", []) or [])
                if not models:
                    continue
                for model in sorted([m for m in models if getattr(m, "is_alive", True)], key=_model_sort_key):
                    spec_fn = getattr(root, "model_start_opponent_shooting_phase_disrupt_specs", None)
                    if not callable(spec_fn):
                        continue
                    specs = spec_fn(model) or []
                    if not specs:
                        continue
                    source_unit = getattr(model, "parent_unit", None) or root
                    for spec in specs:
                        try:
                            range_value = int(spec.get("range", 0) or 0)
                        except Exception:
                            range_value = 0
                        if range_value <= 0:
                            continue
                        candidates = self._visible_enemy_candidates_for_model(
                            source_unit=source_unit,
                            model=model,
                            enemy_roots=enemy_roots,
                            range_value=float(range_value),
                            game_map=game_map,
                        )
                        if not candidates:
                            continue
                        ability_name = str(spec.get("source", "") or "Opponent Shooting phase disruption").strip()
                        ability_key = re.sub(r"[^a-z0-9]+", "_", ability_name.lower()).strip("_") or "opponent_shooting_phase_disrupt"
                        limit_one = bool(spec.get("limit_one_per_army", False))
                        optional = bool(spec.get("optional", False))
                        mortal_on_one = bool(spec.get("mortal_on_one", False))
                        used_fn = getattr(opp, "_ability_used_this_turn", None)
                        if limit_one and callable(used_fn) and used_fn(ability_key):
                            continue
                        model_id = str(get_entity_id(model) or "")
                        if not model_id:
                            continue
                        group_key = (str(getattr(opp, "id", "") or ""), ability_key) if limit_one else (str(getattr(opp, "id", "") or ""), ability_key, model_id)
                        if group_key not in group_meta:
                            group_meta[group_key] = {
                                "ability_name": ability_name,
                                "ability_key": ability_key,
                                "optional": optional,
                                "limit_one": limit_one,
                                "mortal_on_one": mortal_on_one,
                                "model_id": None if limit_one else model_id,
                            }
                        entries = groups.setdefault(group_key, [])
                        for cand in list(candidates):
                            target_id = str(get_entity_id(cand) or "")
                            if not target_id:
                                continue
                            entries.append((model, cand, source_unit))

            if not groups:
                continue

            queue = getattr(self, "decision_queue", None)

            for group_key, entries in list(groups.items()):
                meta = dict(group_meta.get(group_key, {}) or {})
                ability_key = str(meta.get("ability_key", "") or "")
                model_filter = str(meta.get("model_id", "") or "")
                if queue is not None and hasattr(queue, "list"):
                    skip = False
                    for req in list(queue.list() or []):
                        ctx = dict(getattr(req, "context", {}) or {})
                        if str(ctx.get("ability", "")) != "opponent_shooting_phase_disrupt":
                            continue
                        if str(ctx.get("ability_key", "") or "") != ability_key:
                            continue
                        if model_filter and str(ctx.get("model_id", "") or "") != model_filter:
                            continue
                        skip = True
                        break
                    if skip:
                        continue
                options = []
                if meta.get("optional"):
                    options.append(DecisionOption.create("None", payload={"action": "skip"}))
                seen_pairs: set[tuple[str, str]] = set()
                entries.sort(key=lambda t: (str(get_entity_id(t[0]) or ""), str(get_entity_id(t[1]) or "")))
                for model, cand, source_unit in entries:
                    model_id = str(get_entity_id(model) or "")
                    target_id = str(get_entity_id(cand) or "")
                    unit_id = str(get_entity_id(source_unit) or "")
                    if not model_id or not target_id:
                        continue
                    key = (model_id, target_id)
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)
                    label = f"{getattr(model, 'name', 'Model')} -> {getattr(cand, 'name', 'Unit')}"
                    options.append(
                        DecisionOption.create(
                            label,
                            payload={
                                "target_unit_id": target_id,
                                "model_id": model_id,
                                "source_unit_id": unit_id,
                            },
                        )
                    )
                if not options:
                    continue
                ability_name = str(meta.get("ability_name", "") or "Opponent Shooting phase disruption").strip()
                ctx = {
                    "ability": "opponent_shooting_phase_disrupt",
                    "ability_name": ability_name,
                    "ability_key": ability_key,
                    "mortal_on_one": bool(meta.get("mortal_on_one", False)),
                    "optional": bool(meta.get("optional", False)),
                    "limit_one_per_army": bool(meta.get("limit_one", False)),
                    "phase": "Shooting phase",
                }
                if model_filter:
                    ctx["model_id"] = model_filter
                request = DecisionRequest.create(
                    DECISION_CHOOSE_QUARRY,
                    f"{ability_name}: select a unit.",
                    player_id=getattr(opp, "id", None),
                    options=options,
                    context=ctx,
                )
                self.request_decision(request)

    def _on_phase_start_aeldari_enhancements(self, player=None, phase=None, **_kwargs) -> None:
        """Aeldari enhancements that trigger at the start of Command or Shooting phases."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname not in ("COMMAND_PHASE", "SHOOTING_PHASE"):
            return
        if player is None or player is not self.get_current_player():
            return
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Aeldari enhancement hooks require an army for {player.name}.")
        game_map = getattr(self, "map", None)
        if game_map is None:
            raise RuntimeError("Aeldari enhancement hooks require a game map.")

        from ...utility.aura_utils import distance_between_models_bases_3d
        from ...utility.dice import get_roll
        from ...utility.entity_ids import get_entity_id
        from ...utility.event_bus import append_action, append_dice

        def _unit_active(unit, *, allow_embarked: bool = False) -> bool:
            if unit is None:
                return False
            try:
                if hasattr(unit, "is_alive") and callable(unit.is_alive) and not unit.is_alive():
                    return False
            except Exception:
                return False
            try:
                if hasattr(unit, "deployed") and not bool(getattr(unit, "deployed", False)):
                    return False
            except Exception:
                return False
            try:
                if str(getattr(unit, "reserve_status", "deployed") or "deployed") != "deployed":
                    return False
            except Exception:
                pass
            try:
                if hasattr(unit, "is_in_reserves") and callable(unit.is_in_reserves):
                    if bool(unit.is_in_reserves()):
                        return False
            except Exception:
                pass
            if not allow_embarked:
                try:
                    if bool(getattr(unit, "is_embarked", False)):
                        return False
                except Exception:
                    pass
                try:
                    if getattr(unit, "embarked_in", None) is not None:
                        return False
                except Exception:
                    pass
            return True

        def _iter_unique_roots(units):
            seen = set()
            for u in list(units or []):
                try:
                    root = u.get_attached_unit_root()
                except Exception:
                    root = u
                if root is None:
                    continue
                uid = get_entity_id(root) or id(root)
                if uid in seen:
                    continue
                seen.add(uid)
                yield root

        def _model_in_unit_range(model, target_unit, range_inches: float) -> bool:
            try:
                target_models = list(target_unit.get_attached_unit_models() or [])
            except Exception:
                target_models = list(getattr(target_unit, "models", []) or [])
            target_models = [m for m in target_models if getattr(m, "is_alive", True)]
            if not target_models:
                return False
            for tm in target_models:
                try:
                    if distance_between_models_bases_3d(model, tm) <= float(range_inches) + 1e-6:
                        return True
                except Exception:
                    continue
            return False

        def _model_within_objective(model, objective_point) -> bool:
            if model is None or objective_point is None:
                return False
            try:
                from shapely.geometry import Point as _ShPoint
                area = _ShPoint(objective_point.x, objective_point.y).buffer(
                    float(getattr(objective_point, "control_radius", 0.0) or 0.0)
                )
            except Exception:
                area = None
            try:
                if area is not None:
                    base = model.model_base.get_base_shape()
                    if base.intersects(area):
                        return True
            except Exception:
                pass
            try:
                pos = model.get_location()
            except Exception:
                pos = None
            if not pos:
                return False
            try:
                dx = float(pos[0]) - float(getattr(objective_point, "x", 0.0))
                dy = float(pos[1]) - float(getattr(objective_point, "y", 0.0))
                radius = float(getattr(objective_point, "control_radius", 0.0) or 0.0)
                base_r = float(getattr(model.model_base, "get_radius", lambda: 1.0)())
                return (dx * dx + dy * dy) ** 0.5 <= (radius + base_r)
            except Exception:
                return False

        def _within_controlled_objective(bearer_model, unit) -> bool:
            if bearer_model is None:
                return False
            objectives = list(getattr(game_map, "objectives", []) or [])
            for obj in objectives:
                loc = getattr(obj, "location", None)
                if loc is None or getattr(loc, "removed", False):
                    continue
                loc.update_control(self)
                if getattr(loc, "controlling_player", None) is not player:
                    continue
                if _model_within_objective(bearer_model, loc):
                    return True
                transport = getattr(unit, "embarked_in", None)
                if transport is not None:
                    try:
                        if transport.is_within_objective_range(loc):
                            return True
                    except Exception:
                        continue
            return False

        if pname == "SHOOTING_PHASE":
            for unit in list(getattr(army, "units", []) or []):
                sr = getattr(unit, "special_rules", None)
                if not (isinstance(sr, dict) and sr.get("enhancement_guiding_presence")):
                    continue
                if not _unit_active(unit):
                    continue
                bearer = getattr(unit, "_get_enhancement_bearer_model", None)
                bearer = bearer() if callable(bearer) else None
                if bearer is None or not getattr(bearer, "is_alive", True):
                    continue
                candidates = []
                for root in _iter_unique_roots(getattr(army, "units", []) or []):
                    if not _unit_active(root):
                        continue
                    try:
                        if not root.has_any_keyword("AELDARI"):
                            continue
                        if not root.has_any_keyword("VEHICLE"):
                            continue
                    except Exception:
                        continue
                    if not _model_in_unit_range(bearer, root, 9.0):
                        continue
                    candidates.append(root)

                if not candidates:
                    continue
                ability_name = str(getattr(getattr(unit, "enhancement", None), "name", "") or "Guiding Presence").strip()
                if len(candidates) == 1:
                    target = candidates[0]
                    tsr = getattr(target, "special_rules", None)
                    if not isinstance(tsr, dict):
                        tsr = {}
                    tsr["guiding_presence_active"] = True
                    tsr["guiding_presence_bonus"] = 1
                    tsr["guiding_presence_expires_phase"] = "SHOOTING_PHASE"
                    tsr["guiding_presence_source"] = ability_name
                    tsr["guiding_presence_owner"] = str(getattr(player, "id", "") or "")
                    target.special_rules = tsr
                    try:
                        tname = str(getattr(target, "name", "Unit") or "Unit")
                        append_action(player, f"{ability_name}: {tname} gains +1 to hit this phase.")
                    except Exception:
                        pass
                    continue

                self._queue_aeldari_guiding_presence(
                    player=player,
                    source_unit=unit,
                    model=bearer,
                    candidates=candidates,
                    ability_name=ability_name,
                    range_inches=9,
                    hit_bonus=1,
                )

        if pname == "COMMAND_PHASE":
            for unit in list(getattr(army, "units", []) or []):
                sr = getattr(unit, "special_rules", None)
                if not (isinstance(sr, dict) and sr.get("enhancement_harmonisation_matrix")):
                    continue
                if not _unit_active(unit, allow_embarked=True):
                    continue
                bearer = getattr(unit, "_get_enhancement_bearer_model", None)
                bearer = bearer() if callable(bearer) else None
                if bearer is None or not getattr(bearer, "is_alive", True):
                    continue
                if not _within_controlled_objective(bearer, unit):
                    continue
                ability_name = str(getattr(getattr(unit, "enhancement", None), "name", "") or "Harmonisation Matrix").strip()
                roll = int(get_roll("D6") or 0)
                append_dice(player, f"{ability_name} roll: {roll}")
                if roll >= 3:
                    gained = int(player.gain_command_points(1, reason=ability_name) or 0)
                    if gained:
                        append_action(player, f"{ability_name}: gained {gained} CP.")

            for unit in list(getattr(army, "units", []) or []):
                sr = getattr(unit, "special_rules", None)
                if not (isinstance(sr, dict) and sr.get("enhancement_spirit_stone_of_raelyth")):
                    continue
                if not _unit_active(unit):
                    continue
                bearer = getattr(unit, "_get_enhancement_bearer_model", None)
                bearer = bearer() if callable(bearer) else None
                if bearer is None or not getattr(bearer, "is_alive", True):
                    continue
                candidates = []
                for root in _iter_unique_roots(getattr(army, "units", []) or []):
                    if not _unit_active(root):
                        continue
                    try:
                        if not root.has_any_keyword("AELDARI"):
                            continue
                        if not root.has_any_keyword("VEHICLE"):
                            continue
                    except Exception:
                        continue
                    if not _model_in_unit_range(bearer, root, 3.0):
                        continue
                    candidates.append(root)

                if not candidates:
                    continue
                ability_name = str(getattr(getattr(unit, "enhancement", None), "name", "") or "Spirit Stone of Raelyth").strip()
                self._queue_aeldari_spirit_stone_heal(
                    player=player,
                    source_unit=unit,
                    model=bearer,
                    candidates=candidates,
                    ability_name=ability_name,
                    range_inches=3,
                    allow_skip=True,
                )

    def _on_phase_start_tears_of_isha(self, player=None, phase=None, **_kwargs) -> None:
        """Spiritseer: Tears of Isha selection at start of Command phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Tears of Isha requires an army for {player.name}.")
        game_map = getattr(self, "map", None)
        if game_map is None:
            raise RuntimeError("Tears of Isha requires a game map.")

        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0

        queue = getattr(self, "decision_queue", None)
        pending_model_ids = set()
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "")) != "tears_of_isha_target":
                    continue
                mid = str(ctx.get("model_id", "") or "")
                if mid:
                    pending_model_ids.add(mid)

        def _unit_has_keyword(root, keyword: str) -> bool:
            if not keyword:
                return True
            try:
                return bool(root.has_any_keyword(keyword) or root.has_keyword(keyword))
            except Exception:
                pass
            try:
                keys = list(getattr(root, "keywords", []) or []) + list(getattr(root, "faction_keywords", []) or [])
            except Exception:
                keys = []
            return any(str(k or "").strip().upper() == str(keyword).strip().upper() for k in keys)

        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            try:
                if not getattr(unit, "deployed", True):
                    continue
            except Exception:
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            for model in list(getattr(unit, "models", []) or []):
                if model is None:
                    continue
                try:
                    if not getattr(model, "is_alive", True):
                        continue
                except Exception:
                    continue
                mid = str(get_entity_id(model) or "")
                if mid and mid in pending_model_ids:
                    continue
                specs = unit.model_tears_of_isha_specs(model) or []
                if not specs:
                    continue
                seen_specs = set()
                for spec in list(specs or []):
                    ability_name = str(spec.get("source", "") or "Tears of Isha").strip() or "Tears of Isha"
                    key = (mid, ability_name.lower())
                    if key in seen_specs:
                        continue
                    seen_specs.add(key)
                    keyword = str(spec.get("keyword", "") or "").strip()
                    try:
                        rng = int(spec.get("range", 0) or 0)
                    except Exception:
                        rng = 0
                    if rng <= 0:
                        continue
                    candidates = []
                    seen_units = set()
                    for cand in list(getattr(army, "units", []) or []):
                        if cand is None:
                            continue
                        try:
                            root = cand.get_attached_unit_root()
                        except Exception:
                            root = cand
                        rid = str(get_entity_id(root) or "")
                        if not rid or rid in seen_units:
                            continue
                        seen_units.add(rid)
                        try:
                            if not getattr(root, "is_alive", lambda: False)():
                                continue
                        except Exception:
                            continue
                        try:
                            if not getattr(root, "deployed", True):
                                continue
                        except Exception:
                            continue
                        try:
                            if root.is_in_reserves() or root.is_embarked:
                                continue
                        except Exception:
                            pass
                        if not _unit_has_keyword(root, keyword):
                            continue
                        sr = getattr(root, "special_rules", None)
                        if isinstance(sr, dict):
                            if str(sr.get("tears_of_isha_selected_turn_owner", "") or "") == owner_id:
                                try:
                                    selected_turn = int(sr.get("tears_of_isha_selected_turn", 0) or 0)
                                except Exception:
                                    selected_turn = 0
                                if selected_turn == int(turn or 0):
                                    continue
                        if not self._unit_within_range_of_model(model, root, range_value=float(rng)):
                            continue
                        candidates.append(root)
                    if not candidates:
                        continue
                    try:
                        candidates = sorted(candidates, key=lambda u: str(get_entity_id(u) or ""))
                    except Exception:
                        candidates = list(candidates)
                    options = [
                        DecisionOption.create(
                            str(getattr(cand, "name", "Unit") or "Unit"),
                            payload={"target_unit_id": get_entity_id(cand)},
                        )
                        for cand in list(candidates)
                    ]
                    if not options:
                        continue
                    ctx = {
                        "ability": "tears_of_isha_target",
                        "ability_name": ability_name,
                        "phase": "Command phase",
                        "unit": getattr(unit, "name", "") or "",
                        "unit_id": get_entity_id(unit),
                        "source_unit_id": get_entity_id(unit),
                        "model": getattr(model, "name", "") or "",
                        "model_id": mid,
                        "range": int(rng),
                        "keyword": keyword,
                    }
                    request = DecisionRequest.create(
                        DECISION_CHOOSE_QUARRY,
                        f"{ability_name}: select a unit.",
                        player_id=getattr(player, "id", None),
                        options=options,
                        context=ctx,
                    )
                    self.request_decision(request)

    def _on_phase_start_word_of_phoenix(self, player=None, phase=None, **_kwargs) -> None:
        """Word of the Phoenix (Psychic): return destroyed bodyguard models on a 2+."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Word of the Phoenix requires an army for {player.name}.")

        from ...utility.event_bus import append_dice

        seen_roots = set()
        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            rid = str(get_entity_id(root) or "")
            if not rid or rid in seen_roots:
                continue
            seen_roots.add(rid)
            try:
                if not getattr(root, "deployed", True):
                    continue
            except Exception:
                continue
            try:
                if root.is_in_reserves() or root.is_embarked:
                    continue
            except Exception:
                pass

            specs = root.leading_word_of_phoenix_specs() or []
            if not specs:
                continue
            for spec in list(specs or []):
                leader = spec.get("leader")
                if leader is None:
                    continue
                try:
                    if not getattr(leader, "is_alive", lambda: False)():
                        continue
                except Exception:
                    continue
                try:
                    if leader.get_attached_unit_root() is not root:
                        continue
                except Exception:
                    pass
                ability_name = str(spec.get("source", "") or "Word of the Phoenix").strip() or "Word of the Phoenix"
                roll = int(get_roll("D6") or 0)
                if append_dice and player is not None:
                    append_dice(player, f"{ability_name} roll: {roll}")
                if roll < 2:
                    continue
                amount = int(get_roll("D3") or 0) + 1
                if amount <= 0:
                    continue
                destroyed = list(getattr(root, "models_lost", []) or [])
                if destroyed:
                    filtered = []
                    for m in destroyed:
                        try:
                            pu = getattr(m, "parent_unit", None)
                            if pu is not None and hasattr(pu, "has_support_weapon_ability"):
                                if pu.has_support_weapon_ability():
                                    continue
                        except Exception:
                            pass
                        filtered.append(m)
                    destroyed = filtered
                if not destroyed:
                    continue
                allowed_ids = [get_entity_id(m) for m in destroyed if get_entity_id(m)]
                self._queue_bodyguard_return_decision(
                    player=player,
                    leader_unit=leader,
                    bodyguard_unit=root,
                    ability={"name": ability_name},
                    remaining=int(amount),
                    allowed_model_ids=allowed_ids,
                    allow_skip=False,
                )

    def _on_phase_start_voice_of_command(self, player=None, phase=None, **_kwargs) -> None:
        """Astra Militarum: issue Orders at the start of the Command phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "COMMAND_PHASE":
            return
        if player is None:
            raise RuntimeError("Voice of Command requires an active player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Voice of Command requires an army for {player.name}.")
        mgr = getattr(army, "voice_of_command", None)
        if mgr is None or not mgr._army_has_voice():
            return

        mgr.clear_orders_for_player(player)

        officers = mgr.get_eligible_officers(game=self, player=player, phase_name=pname, trigger="command_phase_start")
        if not officers:
            return
        if player.has_control():
            es = getattr(self, "event_system", None)
            if es is None or not hasattr(es, "subscribers"):
                raise RuntimeError("Event system missing for Voice of Command prompt.")
            subs = getattr(es, "subscribers", None)
            if not isinstance(subs, dict):
                raise RuntimeError("Event system subscribers not configured.")
            if subs.get("voice_of_command_prompt"):
                es.publish(
                    "voice_of_command_prompt",
                    player=player,
                    game=self,
                    phase_name=pname,
                    trigger="command_phase_start",
                )
                return
        return

    def _on_phase_end_voice_of_command(self, player=None, phase=None, **_kwargs) -> None:
        """Astra Militarum: issue Orders at end of phase if an Officer disembarked or was set up."""
        if player is None:
            raise RuntimeError("Voice of Command phase end requires an active player.")
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if not pname:
            return
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Voice of Command phase end requires an army for {player.name}.")
        mgr = getattr(army, "voice_of_command", None)
        if mgr is None or not mgr._army_has_voice():
            return
        officers = mgr.get_eligible_officers(game=self, player=player, phase_name=pname, trigger="phase_end")
        if not officers:
            return
        if player.has_control():
            es = getattr(self, "event_system", None)
            if es is None or not hasattr(es, "subscribers"):
                raise RuntimeError("Event system missing for Voice of Command prompt.")
            subs = getattr(es, "subscribers", None)
            if not isinstance(subs, dict):
                raise RuntimeError("Event system subscribers not configured.")
            if subs.get("voice_of_command_prompt"):
                es.publish(
                    "voice_of_command_prompt",
                    player=player,
                    game=self,
                    phase_name=pname,
                    trigger="phase_end",
                )
                return
        return

    def _on_phase_start_custodes_enhancements(self, player=None, phase=None, **_kwargs) -> None:
        """Lions of the Emperor enhancements that trigger at the start of the Fight phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Custodes enhancement hooks require an army for {player.name}.")
        mgr = getattr(army, "adeptus_custodes_detachments", None)
        if mgr is None or not mgr.is_lions_of_the_emperor():
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            raise RuntimeError("Custodes enhancement hooks require a game map.")

        from ...utility.aura_utils import count_enemy_models_within_range

        for unit in list(army.units):
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("enhancement_fierce_conqueror"):
                continue
            bearer_id = sr.get("enhancement_fierce_conqueror_bearer_id") or sr.get("enhancement_bearer_model_id")
            if not bearer_id:
                continue
            bearer_model = None
            for model in list(getattr(unit, "models", []) or []):
                if str(getattr(model, "id", "") or "") != str(bearer_id):
                    continue
                if not getattr(model, "is_alive", True):
                    continue
                bearer_model = model
                break
            if bearer_model is None:
                continue
            enemy_models = count_enemy_models_within_range(bearer_model, 6.0, game=self, game_map=game_map)
            attacks_bonus = int(enemy_models // 5) * 2
            sr["enhancement_bearer_melee_attacks_bonus"] = int(attacks_bonus)
            sr["enhancement_bearer_melee_attacks_bonus_expires_phase"] = "FIGHT_PHASE"
            sr["enhancement_fierce_conqueror_enemy_models"] = int(enemy_models)
            unit.special_rules = sr

    def _on_phase_start_world_eaters_enhancements(self, player=None, phase=None, **_kwargs) -> None:
        """Goretrack Onslaught enhancements that trigger at the start of the Shooting phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "SHOOTING_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"World Eaters enhancement hooks require an army for {player.name}.")
        game_map = getattr(self, "map", None)
        if game_map is None:
            raise RuntimeError("World Eaters enhancement hooks require a game map.")

        from ...rules.enhancement_descriptors import get_enhancement_tool_descriptor
        from ...utility.aura_utils import distance_between_models_bases_3d
        from ..decision_kinds import DECISION_SELECT_UNLEASH_HELL_VEHICLE

        desc = get_enhancement_tool_descriptor(enhancement_id="000010086004", name="Unleash Hell")
        try:
            range_in = float(getattr(desc, "range_in", 0) or 0)
        except Exception:
            range_in = 0.0
        if range_in <= 0:
            range_in = 6.0
        try:
            exclude_mv = bool(getattr(desc, "effect_params", {}).get("suppression_excludes_monsters_vehicles", False))
        except Exception:
            exclude_mv = False

        queue = getattr(self, "decision_queue", None)
        pending = queue.list() if queue is not None else []

        def _already_pending(unit_id: str) -> bool:
            if not unit_id:
                return False
            for req in list(pending or []):
                try:
                    if req.decision_type != DECISION_SELECT_UNLEASH_HELL_VEHICLE:
                        continue
                    ctx = getattr(req, "context", {}) or {}
                    if str(ctx.get("source_unit_id", "") or "") == unit_id:
                        return True
                except Exception:
                    continue
            return False

        for unit in list(army.units):
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("enhancement_unleash_hell"):
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            if root is None or not root.is_alive():
                continue
            get_bearer = getattr(unit, "_get_enhancement_bearer_model", None)
            bearer_model = get_bearer() if callable(get_bearer) else None
            if bearer_model is None or not getattr(bearer_model, "is_alive", False):
                continue
            source_unit_id = str(get_entity_id(unit) or "")
            if not source_unit_id:
                continue

            try:
                prompt_turn = int(sr.get("unleash_hell_prompt_turn", 0) or 0)
            except Exception:
                prompt_turn = 0
            prompt_owner = str(sr.get("unleash_hell_prompt_owner", "") or "")
            prompt_phase = str(sr.get("unleash_hell_prompt_phase", "") or "").strip().upper()
            if (
                prompt_turn == int(getattr(self, "turn", 0) or 0)
                and prompt_owner == str(getattr(player, "id", "") or "")
                and prompt_phase == pname
            ):
                continue
            if _already_pending(source_unit_id):
                continue

            candidates: list[Any] = []
            if bool(getattr(root, "is_embarked", False)) and getattr(root, "embarked_in", None) is not None:
                transport = root.embarked_in
                if (
                    transport is not None
                    and transport.is_alive()
                    and bool(getattr(transport, "deployed", True))
                    and not transport.is_in_reserves()
                ):
                    candidates = [transport]
            else:
                try:
                    if not getattr(root, "deployed", True):
                        continue
                    if root.is_in_reserves():
                        continue
                except Exception:
                    continue
                for cand in list(army.units):
                    if cand is None:
                        continue
                    try:
                        cand_root = cand.get_attached_unit_root()
                    except Exception:
                        cand_root = cand
                    if cand_root is None or cand_root is not cand:
                        continue
                    if not cand.is_alive():
                        continue
                    try:
                        if not getattr(cand, "deployed", True):
                            continue
                        if cand.is_in_reserves() or cand.is_embarked:
                            continue
                    except Exception:
                        continue
                    if not getattr(cand, "is_vehicle", False):
                        continue
                    try:
                        models = list(cand.get_attached_unit_models() or [])
                    except Exception:
                        models = list(getattr(cand, "models", []) or [])
                    in_range = False
                    for model in list(models or []):
                        if not getattr(model, "is_alive", False):
                            continue
                        if distance_between_models_bases_3d(bearer_model, model) <= range_in + 1e-6:
                            in_range = True
                            break
                    if in_range:
                        candidates.append(cand)

            if not candidates:
                continue

            candidates = sorted(candidates, key=lambda u: str(get_entity_id(u) or ""))
            allowed_ids = [str(get_entity_id(cand) or "") for cand in candidates if cand is not None]

            options = [DecisionOption.create("None", payload={"action": "skip"})]
            for cand in candidates:
                options.append(
                    DecisionOption.create(
                        str(getattr(cand, "name", "Unit") or "Unit"),
                        payload={"unit_id": get_entity_id(cand)},
                    )
                )

            ctx = {
                "ability": "unleash_hell",
                "ability_name": "Unleash Hell",
                "source_unit_id": source_unit_id,
                "bearer_model_id": get_entity_id(bearer_model),
                "range": float(range_in),
                "allowed_unit_ids": allowed_ids,
                "exclude_monster_vehicle": bool(exclude_mv),
            }
            if bool(getattr(root, "is_embarked", False)) and getattr(root, "embarked_in", None) is not None:
                ctx["transport_id"] = get_entity_id(root.embarked_in)

            request = DecisionRequest.create(
                DECISION_SELECT_UNLEASH_HELL_VEHICLE,
                "Unleash Hell: select a vehicle to unleash suppression.",
                player_id=getattr(player, "id", None),
                options=options,
                context=ctx,
            )
            self.request_decision(request)

            sr["unleash_hell_prompt_turn"] = int(getattr(self, "turn", 0) or 0)
            sr["unleash_hell_prompt_owner"] = str(getattr(player, "id", "") or "")
            sr["unleash_hell_prompt_phase"] = pname
            unit.special_rules = sr

    def _on_phase_start_chaos_daemons_enhancements(self, player=None, phase=None, **_kwargs) -> None:
        """Chaos Daemons Plague Legion enhancements that trigger at the start of the Shooting phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "SHOOTING_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"Chaos Daemons enhancement hooks require an army for {getattr(player, 'name', 'Player')}.")
        mgr = getattr(army, "chaos_daemons_detachments", None)
        if mgr is None or not mgr.is_plague_legion_detachment():
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            raise RuntimeError("Chaos Daemons enhancement hooks require a game map.")

        enemy_roots = self._collect_enemy_unit_roots(player)
        if not enemy_roots:
            return

        from ...utility.entity_ids import get_entity_id

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        for unit in sorted(list(getattr(army, "units", []) or []), key=_unit_sort_key):
            if unit is None:
                continue
            if not getattr(unit, "is_alive", lambda: False)():
                continue
            if not getattr(unit, "deployed", True):
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict) or not sr.get("enhancement_maggot_maws"):
                continue
            bearer_id = sr.get("enhancement_bearer_model_id")
            if not bearer_id:
                continue
            try:
                models = list(unit.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(unit, "models", []) or [])
            bearer_model = None
            for model in models:
                if str(getattr(model, "_id", "") or "") != str(bearer_id):
                    continue
                if not getattr(model, "is_alive", True):
                    continue
                bearer_model = model
                break
            if bearer_model is None:
                continue
            candidates = self._enemy_candidates_within_range_of_model(
                model=bearer_model,
                enemy_roots=enemy_roots,
                range_value=6.0,
            )
            if not candidates:
                continue
            self._queue_maggot_maws(
                player=player,
                source_unit=unit,
                model=bearer_model,
                candidates=candidates,
                spec={"source": "Maggot Maws", "range": 6},
            )

    def _on_phase_end_gate_of_infinity(self, player=None, phase=None, **_kwargs) -> None:
        """Grey Knights: Gate of Infinity at the end of the opponent's Fight phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        if player is None:
            raise RuntimeError("Gate of Infinity prompt requires a player.")
        opponents = [p for p in (self.players or []) if p is not None and p is not player]
        if not opponents:
            return
        for opp in opponents:
            if opp is None:
                continue
            army = opp.get_army()
            if army is None:
                raise RuntimeError(f"Gate of Infinity requires an army for {opp.name}.")
            mgr = getattr(army, "gate_of_infinity", None)
            if mgr is None or not mgr._army_has_gate():
                continue
            max_units = int(mgr.get_max_units_for_battlefield(self))
            if max_units <= 0:
                continue
            eligible = list(mgr.get_eligible_units(game=self, player=opp) or [])
            if not eligible:
                continue
            if opp.has_control():
                es = getattr(self, "event_system", None)
                if es is None or not hasattr(es, "subscribers"):
                    raise RuntimeError("Event system missing for Gate of Infinity prompt.")
                subs = getattr(es, "subscribers", None)
                if not isinstance(subs, dict):
                    raise RuntimeError("Event system subscribers not configured.")
                if subs.get("gate_of_infinity_prompt"):
                    es.publish(
                        "gate_of_infinity_prompt",
                        player=opp,
                        game=self,
                        max_units=max_units,
                    )
                continue
            continue

    def _on_phase_end_for_the_greater_good(self, player=None, phase=None, **_kwargs) -> None:
        """Clear For the Greater Good state at the end of the Shooting phase."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "SHOOTING_PHASE":
            return
        if player is None:
            raise RuntimeError("For the Greater Good requires an active player.")
        army = player.get_army()
        if army is None:
            raise RuntimeError(f"For the Greater Good requires an army for {player.name}.")
        mgr = getattr(army, "for_the_greater_good", None)
        if mgr is None:
            return
        mgr.on_shooting_phase_end(game=self, player=player)

    def _on_phase_end_cleanup(self, player=None, phase=None, **_kwargs) -> None:
        """Best-effort cleanup for model-level temporary effects that expire at end of a phase."""
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Phase-end cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Phase-end cleanup requires an army for {p.name}.")
            for u in list(army.units):
                for m in list(u.models):
                    fn = getattr(m, "on_phase_end", None)
                    if callable(fn):
                        fn(phase)
        # Unit-level temporary effects (e.g. detachment abilities that last until end of turn)
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        active_name = str(getattr(player, "id", "") or "") if player is not None else ""
        if not pname:
            return
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Phase-end cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Phase-end cleanup requires an army for {p.name}.")
            if pname == "SHOOTING_PHASE":
                deathstrike_mgr = getattr(army, "deathstrike", None)
                if deathstrike_mgr is not None:
                    deathstrike_mgr.clear_phase_usage()
            for u in list(army.units):
                sr = getattr(u, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                exp = str(sr.get("relentless_rage_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "relentless_rage_melee_attacks_bonus",
                        "relentless_rage_melee_strength_bonus",
                        "relentless_rage_expires_phase",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("maddened_ferocity_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "maddened_ferocity_melee_attacks_bonus",
                        "maddened_ferocity_expires_phase",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("fight_selected_enemy_melee_hit_penalty_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "fight_selected_enemy_melee_hit_penalty_active",
                        "fight_selected_enemy_melee_hit_penalty_expires_phase",
                        "fight_selected_enemy_melee_hit_penalty_sources",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("dark_pacts_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in ("dark_pacts_active", "dark_pacts_choice", "dark_pacts_expires_phase"):
                        sr.pop(k, None)
                exp = str(sr.get("despoilers_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in ("despoilers_active", "despoilers_expires_phase", "despoilers_source"):
                        sr.pop(k, None)
                exp = str(sr.get("unholy_bloodshed_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in ("unholy_bloodshed_active", "unholy_bloodshed_expires_phase", "unholy_bloodshed_source"):
                        sr.pop(k, None)
                exp = str(sr.get("exquisite_swordsmanship_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in ("exquisite_swordsmanship_choice", "exquisite_swordsmanship_expires_phase"):
                        sr.pop(k, None)
                exp = str(sr.get("path_of_warrior_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in ("path_of_warrior_choice", "path_of_warrior_expires_phase"):
                        sr.pop(k, None)
                exp = str(sr.get("post_shoot_no_cover_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "post_shoot_no_cover_active",
                        "post_shoot_no_cover_expires_phase",
                        "post_shoot_no_cover_source",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("unleash_hell_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "unleash_hell_active",
                        "unleash_hell_owner",
                        "unleash_hell_turn",
                        "unleash_hell_source",
                        "unleash_hell_source_unit_id",
                        "unleash_hell_expires_phase",
                        "unleash_hell_consumed",
                        "unleash_hell_exclude_monster_vehicle",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("guiding_presence_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "guiding_presence_active",
                        "guiding_presence_bonus",
                        "guiding_presence_expires_phase",
                        "guiding_presence_source",
                        "guiding_presence_owner",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("post_shoot_ap_bonus_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "post_shoot_ap_bonus_active",
                        "post_shoot_ap_bonus_expires_phase",
                        "post_shoot_ap_bonus_source",
                        "post_shoot_ap_bonus_value",
                        "post_shoot_ap_bonus_keyword",
                        "post_shoot_ap_bonus_attack_type",
                        "post_shoot_ap_bonus_owner",
                        "post_shoot_ap_bonus_turn",
                    ):
                        sr.pop(k, None)
                    selected_scope = str(sr.get("post_shoot_ap_bonus_selected_scope", "") or "").strip().lower()
                    if selected_scope == "phase":
                        selected_phase = str(sr.get("post_shoot_ap_bonus_selected_phase", "") or "").strip().upper()
                        if not selected_phase or selected_phase == pname:
                            for k in (
                                "post_shoot_ap_bonus_selected_owner",
                                "post_shoot_ap_bonus_selected_turn",
                                "post_shoot_ap_bonus_selected_scope",
                                "post_shoot_ap_bonus_selected_phase",
                            ):
                                sr.pop(k, None)
                exp = str(sr.get("post_shoot_disembark_wound_reroll_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "post_shoot_disembark_wound_reroll_active",
                        "post_shoot_disembark_wound_reroll_expires_phase",
                        "post_shoot_disembark_wound_reroll_source",
                        "post_shoot_disembark_wound_reroll_target_id",
                        "post_shoot_disembark_wound_reroll_owner",
                        "post_shoot_disembark_wound_reroll_turn",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("reorder_reality_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "reorder_reality_active",
                        "reorder_reality_source",
                        "reorder_reality_expires_phase",
                        "reorder_reality_turn",
                        "reorder_reality_owner",
                        "reorder_reality_target_ids",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("herald_of_ynnead_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "herald_of_ynnead_active",
                        "herald_of_ynnead_expires_phase",
                        "herald_of_ynnead_source",
                        "herald_of_ynnead_keyword",
                        "herald_of_ynnead_owner",
                        "herald_of_ynnead_turn",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("hysterical_frenzy_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "hysterical_frenzy_active",
                        "hysterical_frenzy_expires_phase",
                        "hysterical_frenzy_source",
                        "hysterical_frenzy_threshold",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("fury_of_titan_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in ("fury_of_titan_active", "fury_of_titan_expires_phase"):
                        sr.pop(k, None)
                exp = str(sr.get("sensational_performance_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "sensational_performance_active",
                        "sensational_performance_expires_phase",
                        "sensational_performance_strength_bonus",
                        "sensational_performance_ap_bonus",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("daemonic_patrons_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "daemonic_patrons_active",
                        "daemonic_patrons_called",
                        "daemonic_patrons_expires_phase",
                        "daemonic_patrons_crit_wound_threshold",
                        "daemonic_patrons_source",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("malefic_surge_diabolic_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "malefic_surge_diabolic_active",
                        "malefic_surge_diabolic_choice",
                        "malefic_surge_diabolic_attack_type",
                        "malefic_surge_diabolic_expires_phase",
                        "malefic_surge_diabolic_source",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("malefic_surge_unholy_hunger_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "malefic_surge_unholy_hunger_active",
                        "malefic_surge_unholy_hunger_expires_phase",
                        "malefic_surge_unholy_hunger_source",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("malefic_surge_unnatural_fortitude_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "malefic_surge_unnatural_fortitude_active",
                        "malefic_surge_unnatural_fortitude_expires_phase",
                        "malefic_surge_unnatural_fortitude_source",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("fleshmetal_fusion_fortitude_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "fleshmetal_fusion_fortitude_active",
                        "fleshmetal_fusion_fortitude_expires_phase",
                        "fleshmetal_fusion_fortitude_source",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("enhancement_fight_first_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "enhancement_fight_first_active",
                        "enhancement_fight_first_expires_phase",
                        "enhancement_fight_first_source",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("empowered_by_death_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "empowered_by_death_active",
                        "empowered_by_death_expires_phase",
                        "empowered_by_death_source",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("enhancement_bearer_melee_attacks_bonus_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "enhancement_bearer_melee_attacks_bonus",
                        "enhancement_bearer_melee_attacks_bonus_expires_phase",
                        "enhancement_fierce_conqueror_enemy_models",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("seductive_gambit_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in ("seductive_gambit_active", "seductive_gambit_expires_phase"):
                        sr.pop(k, None)
                effects = sr.get("advance_no_roll_effects")
                if isinstance(effects, list) and effects:
                    kept = []
                    for eff in effects:
                        if not isinstance(eff, dict):
                            kept.append(eff)
                            continue
                        exp = str(eff.get("expires_phase", "") or "").strip().upper()
                        if exp and exp == pname:
                            continue
                        kept.append(eff)
                    if kept:
                        sr["advance_no_roll_effects"] = kept
                    else:
                        sr.pop("advance_no_roll_effects", None)
                exp = str(sr.get("pain_empowered_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in (
                        "pain_empowered",
                        "pain_empowered_expires_phase",
                        "pain_empowered_sources",
                        "pain_reroll_hit",
                        "pain_reroll_hit_ranged",
                        "pain_reroll_advance",
                        "pain_reroll_charge",
                        "pain_melee_strength_bonus",
                        "pain_melee_strength_set",
                        "pain_melee_ap_bonus",
                        "pain_melee_wound_bonus",
                        "pain_melee_attacks_bonus",
                        "pain_melee_attacks_set_non_character",
                        "pain_melee_hazardous_non_character",
                        "pain_experimental_enhancements_choice",
                        "pain_charge_after_advance",
                        "pain_charge_after_fall_back",
                        "pain_lethal_hits",
                        "pain_lethal_hits_melee",
                        "pain_sustained_hits_value",
                        "pain_archon_poisoned_tongue_choice",
                        "pain_assassins_poisons_active",
                        "pain_ignores_cover_ranged",
                        "pain_melee_wound_roll_defense_mod",
                        "pain_sustained_hits_ranged_vs_vehicle",
                        "pain_sustained_hits_ranged_vs_non_vehicle",
                        "pain_rapid_fire_weapon_bonus",
                        "pain_beast_reroll_hit",
                        "pain_beast_reroll_wound",
                        "pain_advance_no_roll",
                        "pain_advance_fixed_bonus",
                        "pain_fight_on_death_2plus",
                        "pain_shoot_pin",
                        "pain_shoot_no_cover",
                        "pain_shoot_suppress",
                        "pain_on_kill_heal",
                        "pain_rapid_deployment_active",
                        "pain_reroll_wound_ones",
                        "pain_reroll_wound_full_if_objective",
                        "pain_ranged_ap_bonus",
                        "pain_splinter_racks_active",
                        "pain_deep_strike_min_distance",
                    ):
                        sr.pop(k, None)
                exp = str(sr.get("pain_no_cover_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in ("pain_no_cover_active", "pain_no_cover_expires_phase"):
                        sr.pop(k, None)
                exp = str(sr.get("cabal_destinys_ruin_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in ("cabal_destinys_ruin_mode", "cabal_destinys_ruin_owner", "cabal_destinys_ruin_expires_phase"):
                        sr.pop(k, None)
                exp = str(sr.get("cabal_twist_of_fate_expires_phase", "") or "").strip().upper()
                if exp and exp == pname:
                    for k in ("cabal_twist_of_fate_ap_bonus", "cabal_twist_of_fate_owner", "cabal_twist_of_fate_expires_phase"):
                        sr.pop(k, None)
                if pname == "SHOOTING_PHASE":
                    sr.pop("cabal_temporal_surge_move_max", None)
                if pname == "FIGHT_PHASE" and active_name:
                    owner = str(sr.get("wargear_charge_keyword_hits_turn_owner", "") or "")
                    if owner and owner == active_name:
                        for k in (
                            "wargear_charge_keyword_hits",
                            "wargear_charge_keyword_hits_turn_owner",
                            "wargear_charge_keyword_hits_turn",
                        ):
                            sr.pop(k, None)
                    owner = str(sr.get("post_shoot_crit_hit_threshold_owner", "") or "")
                    try:
                        turn = int(sr.get("post_shoot_crit_hit_threshold_turn", 0) or 0)
                    except Exception:
                        turn = 0
                    if owner and owner == active_name:
                        if int(turn or 0) == int(getattr(self, "turn", 0) or 0):
                            for k in (
                                "post_shoot_crit_hit_threshold_active",
                                "post_shoot_crit_hit_threshold_owner",
                                "post_shoot_crit_hit_threshold_turn",
                                "post_shoot_crit_hit_threshold_source",
                                "post_shoot_crit_hit_threshold_keyword",
                                "post_shoot_crit_hit_threshold_value",
                                "post_shoot_crit_hit_threshold_expires_phase",
                            ):
                                sr.pop(k, None)
                    owner = str(sr.get("tactical_acumen_no_charge_turn_owner", "") or "")
                    try:
                        turn = int(sr.get("tactical_acumen_no_charge_turn", 0) or 0)
                    except Exception:
                        turn = 0
                    if owner and owner == active_name:
                        if int(turn or 0) == int(getattr(self, "turn", 0) or 0):
                            for k in (
                                "tactical_acumen_no_charge_turn_owner",
                                "tactical_acumen_no_charge_turn",
                            ):
                                sr.pop(k, None)
                    owner = str(sr.get("symphony_of_pain_owner", "") or "")
                    try:
                        turn = int(sr.get("symphony_of_pain_turn", 0) or 0)
                    except Exception:
                        turn = 0
                    if owner and owner == active_name:
                        if int(turn or 0) == int(getattr(self, "turn", 0) or 0):
                            for k in (
                                "symphony_of_pain_active",
                                "symphony_of_pain_owner",
                                "symphony_of_pain_turn",
                                "symphony_of_pain_source",
                                "symphony_of_pain_keywords",
                            ):
                                sr.pop(k, None)
        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Phase-end cleanup requires players.")
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Phase-end cleanup requires an army for {p.name}.")
            mgr = getattr(army, "battle_focus", None)
            if mgr is not None:
                mgr.cleanup_on_phase_end(phase, p)

        # Templar Vows: Uphold the Honour of the Emperor sticky objectives at end of your Command phase.
        if pname == "COMMAND_PHASE":
            if player is None:
                raise RuntimeError("Templar Vows cleanup requires an active player.")
            army = player.get_army()
            if army is None:
                raise RuntimeError(f"Templar Vows cleanup requires an army for {player.name}.")
            mgr = getattr(army, "templar_vows", None)
            if mgr is not None:
                mgr.on_command_phase_end(game=self, player=player)
            # Datasheet abilities: sticky objectives at end of your Command phase.
            game_map = getattr(self, "map", None)
            if game_map is None:
                raise RuntimeError("Command-phase sticky objectives require a game map.")
            objectives = list(getattr(game_map, "objectives", []) or [])
            if objectives:
                for obj in objectives:
                    loc = getattr(obj, "location", None)
                    if loc is None or getattr(loc, "removed", False):
                        continue
                    if hasattr(loc, "update_control"):
                        loc.update_control(self)
                dg_mgr = getattr(army, "death_guard_detachments", None)
                if dg_mgr is not None:
                    dg_mgr.on_command_phase_end(game=self, player=player)
                seen = set()
                for unit in list(army.units):
                    root = unit.get_attached_unit_root()
                    uid = get_entity_id(root)
                    if uid in seen:
                        continue
                    seen.add(uid)
                    if not root.attached_unit_has_command_phase_sticky_objective():
                        continue
                    for obj in objectives:
                        loc = getattr(obj, "location", None)
                        if loc is None or getattr(loc, "removed", False):
                            continue
                        if getattr(loc, "controlling_player", None) is not player:
                            continue
                        if not root.is_within_objective_range(loc):
                            sr = getattr(root, "special_rules", None)
                            allow_transport = bool(isinstance(sr, dict) and sr.get("sticky_objectives_allow_embarked_transport"))
                            if not allow_transport:
                                continue
                            transport = getattr(root, "embarked_in", None)
                            if transport is None or not transport.is_within_objective_range(loc):
                                continue
                        if hasattr(loc, "set_sticky_control"):
                            loc.set_sticky_control(player, source="unit_sticky_objective")
                        else:
                            loc.sticky_controller = player
                            loc.sticky_source = "unit_sticky_objective"
                            loc.controlling_player = player

        # Cabal of Sorcerers: Temporal Surge charge restriction ends at the end of the turn.
        if pname == "FIGHT_PHASE":
            if player is None:
                raise RuntimeError("Phase-end cleanup requires an active player.")
            owner_id = player.id
            for p in list(self.players or []):
                if p is None:
                    raise RuntimeError("Phase-end cleanup requires players.")
                army = p.get_army()
                if army is None:
                    raise RuntimeError(f"Phase-end cleanup requires an army for {p.name}.")
                for u in list(army.units):
                    sr = getattr(u, "special_rules", None)
                    if not isinstance(sr, dict):
                        continue
                    exp = str(sr.get("dance_of_death_expires_phase", "") or "").strip().upper()
                    if exp == pname:
                        for k in ("dance_of_death_choice", "dance_of_death_expires_phase"):
                            sr.pop(k, None)
                    if str(sr.get("cabal_temporal_surge_no_charge_turn_owner", "") or "") == owner_id:
                        for k in ("cabal_temporal_surge_no_charge_turn_owner", "cabal_temporal_surge_no_charge_turn"):
                            sr.pop(k, None)
                    if str(sr.get("pain_swooping_descent_no_charge_turn_owner", "") or "") == owner_id:
                        for k in ("pain_swooping_descent_no_charge_turn_owner", "pain_swooping_descent_no_charge_turn"):
                            sr.pop(k, None)
                    if str(sr.get("cloudstrider_no_charge_turn_owner", "") or "") == owner_id:
                        for k in (
                            "cloudstrider_no_charge_turn_owner",
                            "cloudstrider_no_charge_turn",
                            "cloudstrider_choice_turn_owner",
                            "cloudstrider_choice_turn",
                            "cloudstrider_deep_strike_min_distance",
                            "cloudstrider_source",
                        ):
                            sr.pop(k, None)
                    if str(sr.get("feigned_retreat_turn_owner", "") or "") == owner_id:
                        for k in ("feigned_retreat_active", "feigned_retreat_turn_owner", "feigned_retreat_turn"):
                            sr.pop(k, None)
                    if str(sr.get("manoeuvre_and_fire_turn_owner", "") or "") == owner_id:
                        for k in (
                            "manoeuvre_and_fire_active",
                            "manoeuvre_and_fire_turn_owner",
                            "manoeuvre_and_fire_turn",
                            "manoeuvre_and_fire_source",
                        ):
                            sr.pop(k, None)
                    if str(sr.get("fire_and_fade_no_charge_turn_owner", "") or "") == owner_id:
                        for k in ("fire_and_fade_no_charge_turn_owner", "fire_and_fade_no_charge_turn"):
                            sr.pop(k, None)
                    if str(sr.get("fire_and_fade_no_embark_turn_owner", "") or "") == owner_id:
                        for k in ("fire_and_fade_no_embark_turn_owner", "fire_and_fade_no_embark_turn"):
                            sr.pop(k, None)
                    if str(sr.get("grenade_pack_flyover_used_turn_owner", "") or "") == owner_id:
                        for k in (
                            "grenade_pack_flyover_used_turn_owner",
                            "grenade_pack_flyover_used_turn",
                            "grenade_pack_flyover_source",
                        ):
                            sr.pop(k, None)
                    if str(sr.get("dark_ritual_turn_owner", "") or "") == owner_id:
                        try:
                            turn = int(sr.get("dark_ritual_turn", 0) or 0)
                        except Exception:
                            turn = 0
                        if not turn or int(turn) == int(getattr(self, "turn", 0) or 0):
                            for k in (
                                "dark_ritual_active",
                                "dark_ritual_turn_owner",
                                "dark_ritual_turn",
                                "dark_ritual_expires_phase",
                                "dark_ritual_hit_bonus",
                                "dark_ritual_wound_bonus",
                                "dark_ritual_charge_after_advance",
                                "dark_ritual_source",
                            ):
                                sr.pop(k, None)
                    if str(sr.get("grenade_pack_flyover_no_grenade_turn_owner", "") or "") == owner_id:
                        for k in ("grenade_pack_flyover_no_grenade_turn_owner", "grenade_pack_flyover_no_grenade_turn"):
                            sr.pop(k, None)
                    if str(sr.get("flickerjump_no_charge_turn_owner", "") or "") == owner_id:
                        for k in ("flickerjump_no_charge_turn_owner", "flickerjump_no_charge_turn"):
                            sr.pop(k, None)
                    if str(sr.get("flickerjump_move_set_turn_owner", "") or "") == owner_id:
                        for k in ("flickerjump_move_set_turn_owner", "flickerjump_move_set_turn", "flickerjump_move_set_value"):
                            sr.pop(k, None)
                    if str(sr.get("flickerjump_pending_uses_owner", "") or "") == owner_id:
                        for k in (
                            "flickerjump_pending_uses_owner",
                            "flickerjump_pending_uses_turn",
                            "flickerjump_pending_uses",
                            "flickerjump_source",
                        ):
                            sr.pop(k, None)
                    if str(sr.get("goretrack_onslaught_turn_owner", "") or "") == owner_id:
                        for k in ("goretrack_onslaught_active", "goretrack_onslaught_turn_owner", "goretrack_onslaught_turn"):
                            sr.pop(k, None)
                    if str(sr.get("ere_we_go_turn_owner", "") or "") == owner_id:
                        for k in ("ere_we_go_active", "ere_we_go_turn_owner", "ere_we_go_turn", "ere_we_go_source"):
                            sr.pop(k, None)

        # Snapshot objective control at end of each phase for "previous phase" rules.
        game_map = self.map
        if game_map is None:
            raise RuntimeError("Objective control snapshot requires a game map.")
        snapshot = {}
        for obj in list(getattr(game_map, "objectives", []) or []):
            loc = getattr(obj, "location", None)
            if loc is None or getattr(loc, "removed", False):
                continue
            if hasattr(loc, "update_control"):
                loc.update_control(self)
            snapshot[loc] = getattr(loc, "controlling_player", None)
        self._objective_control_snapshot = snapshot

        # Phoenix Gem: resolve pending returns at end of the phase they were destroyed in.
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname:
            pending = list(getattr(self, "_phoenix_gem_pending", []) or [])
            if pending:
                remaining = []
                for payload in pending:
                    if str(payload.get("phase_name", "") or "").strip().upper() != pname:
                        remaining.append(payload)
                        continue
                    self._resolve_phoenix_gem_return(payload)
                self._phoenix_gem_pending = remaining

    def _on_phase_end_movement_phase_visible_bonus(
        self,
        *,
        player=None,
        phase=None,
        bonus_kind: str,
        spec_method: str,
    ) -> None:
        """Movement phase end: select a visible enemy unit to receive a temporary hit/wound bonus."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "MOVEMENT_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        kind_key = str(bonus_kind or "").strip().lower()
        if kind_key not in ("hit", "wound"):
            return
        army = self._get_player_army(player)
        if army is None:
            return
        game_map = self.map
        if game_map is None:
            return

        from ...utility.entity_ids import get_entity_id

        enemy_roots = self._collect_enemy_unit_roots(player)

        def _enemy_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        enemy_roots.sort(key=_enemy_sort_key)
        if not enemy_roots:
            return

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        queue_fn = self._queue_movement_phase_visible_hit_bonus if kind_key == "hit" else self._queue_movement_phase_visible_wound_bonus

        for unit in sorted(list(army.units or []), key=_unit_sort_key):
            if unit is None:
                continue
            if not getattr(unit, "is_alive", lambda: False)():
                continue
            if not getattr(unit, "deployed", True):
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            if not models:
                continue

            def _model_sort_key(m):
                try:
                    return str(get_entity_id(m))
                except Exception:
                    return str(getattr(m, "name", "") or "")

            for model in sorted([m for m in models if getattr(m, "is_alive", True)], key=_model_sort_key):
                spec_fn = getattr(root, spec_method, None)
                if not callable(spec_fn):
                    continue
                specs = spec_fn(model) or []
                if not specs:
                    continue
                source_unit = getattr(model, "parent_unit", None) or root
                for spec in specs:
                    try:
                        range_value = int(spec.get("range", 0) or 0)
                    except Exception:
                        range_value = 0
                    if range_value <= 0:
                        continue
                    candidates = self._visible_enemy_candidates_for_model(
                        source_unit=source_unit,
                        model=model,
                        enemy_roots=enemy_roots,
                        range_value=float(range_value),
                        game_map=game_map,
                    )
                    if not candidates:
                        continue
                    queue_fn(
                        player=player,
                        source_unit=source_unit,
                        model=model,
                        candidates=candidates,
                        spec=spec,
                    )

    def _on_phase_end_movement_phase_visible_wound_bonus(self, player=None, phase=None, **_kwargs) -> None:
        """Movement phase end: select a visible enemy unit to receive a temporary wound bonus vs friendly keyword attacks."""
        self._on_phase_end_movement_phase_visible_bonus(
            player=player,
            phase=phase,
            bonus_kind="wound",
            spec_method="model_movement_phase_end_visible_wound_bonus_specs",
        )

    def _on_phase_end_movement_phase_visible_hit_bonus(self, player=None, phase=None, **_kwargs) -> None:
        """Movement phase end: select a visible enemy unit to receive a temporary hit bonus vs friendly keyword attacks."""
        self._on_phase_end_movement_phase_visible_bonus(
            player=player,
            phase=phase,
            bonus_kind="hit",
            spec_method="model_movement_phase_end_visible_hit_bonus_specs",
        )

    def _on_phase_end_misfortune(self, player=None, phase=None, **_kwargs) -> None:
        """Movement phase end: select a visible enemy unit to suffer -1 to wound rolls (Misfortune)."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "MOVEMENT_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        army = self._get_player_army(player)
        if army is None:
            return
        game_map = self.map
        if game_map is None:
            return

        from ...utility.entity_ids import get_entity_id

        enemy_roots = self._collect_enemy_unit_roots(player)

        if not enemy_roots:
            return

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        enemy_roots.sort(key=_unit_sort_key)

        for unit in sorted(list(army.units or []), key=_unit_sort_key):
            if unit is None:
                continue
            if not getattr(unit, "is_alive", lambda: False)():
                continue
            if not getattr(unit, "deployed", True):
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            if not models:
                continue

            def _model_sort_key(m):
                try:
                    return str(get_entity_id(m))
                except Exception:
                    return str(getattr(m, "name", "") or "")

            for model in sorted([m for m in models if getattr(m, "is_alive", True)], key=_model_sort_key):
                spec_fn = getattr(root, "model_movement_phase_end_misfortune_specs", None)
                if not callable(spec_fn):
                    continue
                specs = spec_fn(model) or []
                if not specs:
                    continue
                source_unit = getattr(model, "parent_unit", None) or root
                for spec in specs:
                    try:
                        range_value = int(spec.get("range", 0) or 0)
                    except Exception:
                        range_value = 0
                    if range_value <= 0:
                        continue
                    candidates = self._visible_enemy_candidates_for_model(
                        source_unit=source_unit,
                        model=model,
                        enemy_roots=enemy_roots,
                        range_value=float(range_value),
                        game_map=game_map,
                    )
                    if not candidates:
                        continue
                    self._queue_movement_phase_end_misfortune(
                        player=player,
                        source_unit=source_unit,
                        model=model,
                        candidates=candidates,
                        spec=spec,
                    )

    def _on_phase_end_nurgles_rot(self, player=None, phase=None, **_kwargs) -> None:
        """Movement phase end: select an enemy unit within range for -1 Toughness (Nurgle's Rot)."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "MOVEMENT_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        army = self._get_player_army(player)
        if army is None:
            return
        game_map = self.map
        if game_map is None:
            return

        from ...utility.entity_ids import get_entity_id

        enemy_roots = self._collect_enemy_unit_roots(player)
        if not enemy_roots:
            return

        for unit in list(army.units):
            if unit is None:
                continue
            try:
                if not getattr(unit, "is_alive", lambda: False)():
                    continue
            except Exception:
                continue
            if not getattr(unit, "deployed", True):
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            if not models:
                continue

            def _model_sort_key(m):
                try:
                    return str(get_entity_id(m))
                except Exception:
                    return str(getattr(m, "name", "") or "")

            for model in sorted([m for m in models if getattr(m, "is_alive", True)], key=_model_sort_key):
                spec_fn = getattr(root, "model_movement_phase_end_toughness_penalty_specs", None)
                if not callable(spec_fn):
                    continue
                specs = spec_fn(model) or []
                if not specs:
                    continue
                source_unit = getattr(model, "parent_unit", None) or root
                for spec in specs:
                    try:
                        range_value = int(spec.get("range", 0) or 0)
                    except Exception:
                        range_value = 0
                    if range_value <= 0:
                        continue
                    candidates = self._enemy_candidates_within_range_of_model(
                        model=model,
                        enemy_roots=enemy_roots,
                        range_value=float(range_value),
                    )
                    if not candidates:
                        continue
                    self._queue_movement_phase_end_nurgles_rot(
                        player=player,
                        source_unit=source_unit,
                        model=model,
                        candidates=candidates,
                        spec=spec,
                    )

    def _on_phase_end_seed_the_garden_of_nurgle(self, player=None, phase=None, **_kwargs) -> None:
        """Movement phase end: if within Area Terrain, mark terrain as within Shadow of Chaos (Seed the Garden)."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "MOVEMENT_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        army = self._get_player_army(player)
        if army is None:
            return
        game_map = self.map
        if game_map is None:
            return
        try:
            from ...battlefield.map import TerrainType
        except Exception:
            TerrainType = None

        area_types = set()
        if TerrainType is not None:
            area_types = {
                TerrainType.CRATER_AND_RUBBLE,
                TerrainType.DEBRIS_AND_STATUARY,
                TerrainType.HILLS_AND_SEALED_BUILDINGS,
                TerrainType.WOODS,
                TerrainType.RUINS,
            }

        def _model_in_area_terrain(model):
            if model is None:
                return []
            base = getattr(model, "model_base", None)
            if base is None:
                return []
            try:
                base_shape = base.get_base_shape()
            except Exception:
                return []
            matches = []
            for terrain in list(getattr(game_map, "terrain_features", []) or []):
                if TerrainType is not None and getattr(terrain, "terrain_type", None) not in area_types:
                    continue
                footprint = getattr(terrain, "footprint", None)
                if footprint is None:
                    continue
                try:
                    if footprint.intersects(base_shape):
                        matches.append(terrain)
                except Exception:
                    continue
            return matches

        owner_id = str(getattr(player, "id", "") or "")
        if not owner_id:
            return
        from ...utility.entity_ids import get_entity_id
        for unit in list(army.units):
            if unit is None:
                continue
            try:
                if not getattr(unit, "is_alive", lambda: False)():
                    continue
            except Exception:
                continue
            if not getattr(unit, "deployed", True):
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            if not models:
                continue
            for model in list(models or []):
                if not getattr(model, "is_alive", True):
                    continue
                spec_fn = getattr(root, "model_movement_phase_end_shadow_of_chaos_terrain_specs", None)
                if not callable(spec_fn):
                    continue
                specs = spec_fn(model) or []
                if not specs:
                    continue
                terrain_matches = _model_in_area_terrain(model)
                if not terrain_matches:
                    continue
                terrain_matches.sort(key=lambda t: str(get_entity_id(t)))
                terrain = terrain_matches[0]
                try:
                    owners = getattr(terrain, "shadow_of_chaos_owner_ids", None)
                    if not isinstance(owners, set):
                        owners = set(owners or [])
                    if owner_id in owners:
                        continue
                    owners.add(owner_id)
                    terrain.shadow_of_chaos_owner_ids = owners
                except Exception:
                    continue
                try:
                    from ...utility.event_bus import append_action
                    ability_name = str(specs[0].get("source", "") or "Seed the Garden of Nurgle").strip()
                    append_action(
                        player,
                        f"{ability_name}: area terrain seeded with Shadow of Chaos.",
                    )
                except Exception:
                    pass

    def _on_phase_end_movement_phase_symphony_of_pain(self, player=None, phase=None, **_kwargs) -> None:
        """Movement phase end: select a Battle-shocked enemy within range for full hit/wound rerolls (Symphony of Pain)."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "MOVEMENT_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        army = self._get_player_army(player)
        if army is None:
            return
        game_map = self.map
        if game_map is None:
            return

        from ...utility.entity_ids import get_entity_id

        enemy_roots = self._collect_enemy_unit_roots(player)
        if not enemy_roots:
            return

        owner_id = str(getattr(player, "id", "") or "")
        try:
            turn = int(getattr(self, "turn", 0) or 0)
        except Exception:
            turn = 0

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        enemy_roots.sort(key=_unit_sort_key)

        for unit in sorted(list(army.units or []), key=_unit_sort_key):
            if unit is None:
                continue
            if not getattr(unit, "is_alive", lambda: False)():
                continue
            if not getattr(unit, "deployed", True):
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            if not models:
                continue

            def _model_sort_key(m):
                try:
                    return str(get_entity_id(m))
                except Exception:
                    return str(getattr(m, "name", "") or "")

            for model in sorted([m for m in models if getattr(m, "is_alive", True)], key=_model_sort_key):
                spec_fn = getattr(root, "model_movement_phase_end_battleshock_reroll_specs", None)
                if not callable(spec_fn):
                    continue
                specs = spec_fn(model) or []
                if not specs:
                    continue
                source_unit = getattr(model, "parent_unit", None) or root
                for spec in specs:
                    try:
                        range_value = int(spec.get("range", 0) or 0)
                    except Exception:
                        range_value = 0
                    if range_value <= 0:
                        continue
                    candidates = []
                    for enemy in list(enemy_roots or []):
                        if enemy is None:
                            continue
                        try:
                            if not enemy.is_battle_shocked():
                                continue
                        except Exception:
                            continue
                        try:
                            sr = getattr(enemy, "special_rules", None)
                        except Exception:
                            sr = None
                        if isinstance(sr, dict):
                            if bool(sr.get("symphony_of_pain_active")):
                                if str(sr.get("symphony_of_pain_owner", "") or "") == owner_id and int(sr.get("symphony_of_pain_turn", 0) or 0) == int(turn or 0):
                                    continue
                        if enemy in self._enemy_candidates_within_range_of_model(
                            model=model,
                            enemy_roots=[enemy],
                            range_value=float(range_value),
                        ):
                            candidates.append(enemy)
                    if not candidates:
                        continue
                    self._queue_symphony_of_pain(
                        player=player,
                        source_unit=source_unit,
                        model=model,
                        candidates=candidates,
                        spec=spec,
                    )

    def _on_phase_end_grotesque_regeneration(self, player=None, phase=None, **_kwargs) -> None:
        """End of each phase: Beasts of Nurgle models regain all lost wounds."""
        if not bool(getattr(self, "is_authoritative", True)):
            return

        from ...utility.entity_ids import get_entity_id
        from ...utility.event_bus import append_action

        def _unit_has_regen(unit) -> bool:
            for ab in unit._iter_active_possible_abilities():
                if isinstance(ab, str):
                    name = ab
                else:
                    name = getattr(ab, "name", "")
                if str(name or "").strip().lower() == "grotesque regeneration":
                    return True
            return False

        for owner in list(getattr(self, "players", []) or []):
            if owner is None:
                continue
            army = self._get_player_army(owner)
            if army is None:
                continue
            seen: set[str] = set()
            for unit in list(getattr(army, "units", []) or []):
                if unit is None:
                    continue
                root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
                uid = get_entity_id(root)
                if uid in seen:
                    continue
                seen.add(uid)
                if not getattr(root, "is_alive", lambda: False)():
                    continue
                if not bool(getattr(root, "deployed", True)):
                    continue
                if str(getattr(root, "reserve_status", "deployed")) != "deployed":
                    continue
                in_reserves = False
                fn = getattr(root, "is_in_reserves", None)
                if callable(fn):
                    in_reserves = bool(fn())
                else:
                    in_reserves = str(getattr(root, "reserve_status", "deployed")) in ("reserves", "strategic_reserves")
                if in_reserves:
                    continue
                if bool(getattr(root, "embarked_in", None)) or bool(getattr(root, "is_embarked", False)):
                    continue
                if not _unit_has_regen(root):
                    continue

                models = list(getattr(root, "models", []) or [])
                healed = 0
                for model in models:
                    if not bool(getattr(model, "is_alive", True)):
                        continue
                    base_wounds = int(getattr(model, "_base_wounds", getattr(model, "wounds", 0)) or 0)
                    if base_wounds <= 0:
                        continue
                    current = int(getattr(model, "wounds", 0) or 0)
                    if current < base_wounds:
                        model.wounds = base_wounds
                        healed += 1
                if healed > 0:
                    append_action(owner, f"Grotesque Regeneration: {getattr(root, 'name', 'Unit')} fully healed ({healed} model(s)).")

    def _on_phase_end_movement_phase_mortal_table(self, player=None, phase=None, **_kwargs) -> None:
        """Movement phase end: roll a D6 for each enemy unit within range of this model; apply mortal wound table."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "MOVEMENT_PHASE":
            return
        if player is None or player is not self.get_current_player():
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        army = self._get_player_army(player)
        if army is None:
            return
        enemy_roots = self._collect_enemy_unit_roots(player)
        if not enemy_roots:
            return
        game_map = getattr(self, "map", None)

        from ...utility.entity_ids import get_entity_id
        from ...utility.dice import get_roll
        from ...utility.event_bus import append_action, append_dice

        def _unit_sort_key(u):
            try:
                return str(get_entity_id(u))
            except Exception:
                return str(getattr(u, "name", "") or "")

        def _resolve_mortal_roll(spec: dict, roll: int) -> tuple[int, str]:
            d3_roll = None
            d6_roll = None
            total_mw = 0
            threshold = spec.get("threshold")
            if threshold is not None:
                try:
                    threshold = int(threshold or 0)
                except Exception:
                    threshold = 0
                if roll >= int(threshold or 0):
                    mw = spec.get("mortal_wounds")
                    mw_norm = str(mw).strip().lower()
                    if mw_norm == "d3":
                        d3_roll = int(get_roll("D3") or 0)
                        total_mw = int(d3_roll or 0)
                    elif mw_norm == "d6":
                        d6_roll = int(get_roll("D6") or 0)
                        total_mw = int(d6_roll or 0)
                    else:
                        try:
                            total_mw = int(mw or 0)
                        except Exception:
                            total_mw = 0
            else:
                if 2 <= roll <= 3:
                    total_mw = 1
                elif 4 <= roll <= 5:
                    d3_roll = int(get_roll("D3") or 0)
                    total_mw = int(d3_roll or 0)
                elif roll >= 6:
                    d6_roll = int(get_roll("D6") or 0)
                    total_mw = int(d6_roll or 0)
            roll_note = f"roll={int(roll)}"
            if d3_roll is not None:
                roll_note += f", d3={int(d3_roll)}"
            if d6_roll is not None:
                roll_note += f", d6={int(d6_roll)}"
            return int(total_mw), roll_note

        def _apply_mortal_rolls(source_unit, targets: list, spec: dict, ability_name: str) -> None:
            if not targets:
                return
            for target_unit in targets:
                roll = int(get_roll("D6") or 0)
                total_mw, roll_note = _resolve_mortal_roll(spec, roll)
                if total_mw > 0 and hasattr(source_unit, "_apply_mortal_wounds_to_unit"):
                    source_unit._apply_mortal_wounds_to_unit(target_unit, int(total_mw), game_map=game_map)
                append_dice(
                    player,
                    f"{ability_name}: {getattr(target_unit, 'name', 'Target')} ({roll_note}) => {int(total_mw)} mortal wounds.",
                )
                append_action(
                    player,
                    f"{ability_name}: {getattr(target_unit, 'name', 'Target')} suffered {int(total_mw)} mortal wounds.",
                )

            if bool(spec.get("battle_shock")):
                for target_unit in targets:
                    try:
                        target_unit.take_battle_shock_test(int(getattr(self, "turn", 0) or 1))
                    except Exception:
                        continue

        enemy_roots.sort(key=_unit_sort_key)
        processed_unit_roots: set[str] = set()

        for unit in sorted(list(army.units or []), key=_unit_sort_key):
            if unit is None:
                continue
            if not getattr(unit, "is_alive", lambda: False)():
                continue
            if not getattr(unit, "deployed", True):
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            try:
                models = list(root.get_attached_unit_models() or [])
            except Exception:
                models = list(getattr(root, "models", []) or [])
            alive_models = [m for m in models if getattr(m, "is_alive", True)]
            if not alive_models:
                continue

            def _model_sort_key(m):
                try:
                    return str(get_entity_id(m))
                except Exception:
                    return str(getattr(m, "name", "") or "")

            root_id = str(get_entity_id(root) or "")
            if root_id and root_id not in processed_unit_roots:
                processed_unit_roots.add(root_id)
                unit_specs = []
                try:
                    unit_specs = list(root.unit_movement_phase_end_enemy_within_range_mortal_threshold_specs() or [])
                except Exception:
                    unit_specs = []
                if unit_specs:
                    for spec in unit_specs:
                        try:
                            range_value = int(spec.get("range", 0) or 0)
                        except Exception:
                            range_value = 0
                        if range_value <= 0:
                            continue
                        candidates = []
                        seen_enemy = set()
                        for enemy_root in enemy_roots:
                            if enemy_root is None:
                                continue
                            eid = str(get_entity_id(enemy_root) or "")
                            if not eid or eid in seen_enemy:
                                continue
                            seen_enemy.add(eid)
                            in_range = False
                            for model in alive_models:
                                if self._unit_within_range_of_model(model, enemy_root, range_value=float(range_value)):
                                    in_range = True
                                    break
                            if not in_range:
                                continue
                            candidates.append(enemy_root)
                        if not candidates:
                            continue
                        candidates.sort(key=_unit_sort_key)
                        ability_name = str(spec.get("source", "") or "Movement phase mortals").strip() or "Movement phase mortals"
                        _apply_mortal_rolls(root, candidates, spec, ability_name)

            for model in sorted(alive_models, key=_model_sort_key):
                spec_fn = getattr(root, "model_movement_phase_end_enemy_within_range_mortal_table_specs", None)
                if not callable(spec_fn):
                    continue
                specs = spec_fn(model) or []
                if not specs:
                    continue
                source_unit = getattr(model, "parent_unit", None) or root
                for spec in specs:
                    try:
                        range_value = int(spec.get("range", 0) or 0)
                    except Exception:
                        range_value = 0
                    if range_value <= 0:
                        continue
                    candidates = []
                    for enemy_root in enemy_roots:
                        if enemy_root is None:
                            continue
                        if not self._unit_within_range_of_model(model, enemy_root, range_value=float(range_value)):
                            continue
                        candidates.append(enemy_root)
                    if not candidates:
                        continue
                    candidates.sort(key=_unit_sort_key)
                    ability_name = str(spec.get("source", "") or "Movement phase mortals").strip() or "Movement phase mortals"
                    _apply_mortal_rolls(source_unit, candidates, spec, ability_name)

    def _on_phase_end_transport_end_of_fight_embark(self, player=None, phase=None, **_kwargs) -> None:
        """Fight phase end: optional embark for empty transports with datasheet abilities."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        game_map = self.map
        if game_map is None:
            return
        try:
            from ...utility.aura_utils import unit_wholly_within_range_of_unit
        except Exception:
            return

        for p in list(self.players or []):
            if p is None:
                continue
            army = self._get_player_army(p)
            if army is None:
                continue
            for transport in list(army.units or []):
                if transport is None:
                    continue
                if not transport.is_alive() or not getattr(transport, "deployed", True):
                    continue
                try:
                    if transport.is_in_reserves() or transport.is_embarked:
                        continue
                except Exception:
                    pass
                if list(getattr(transport, "transport_passengers", []) or []):
                    continue
                try:
                    specs = list(transport.unit_end_of_fight_embark_specs() or [])
                except Exception:
                    specs = []
                if not specs:
                    continue
                for spec in specs:
                    try:
                        max_models = int(spec.get("max_models", 0) or 0)
                    except Exception:
                        max_models = 0
                    try:
                        range_value = float(spec.get("range", 0) or 0)
                    except Exception:
                        range_value = 0.0
                    if range_value <= 0:
                        continue
                    keyword = str(spec.get("keyword", "") or "").strip()
                    candidates = []
                    for unit in list(army.units or []):
                        if unit is None or unit is transport:
                            continue
                        if not unit.is_alive() or not getattr(unit, "deployed", True):
                            continue
                        try:
                            if unit.is_in_reserves() or unit.is_embarked:
                                continue
                        except Exception:
                            pass
                        if not getattr(unit, "is_infantry", False):
                            continue
                        if keyword and not unit.has_any_keyword(keyword):
                            continue
                        if max_models > 0:
                            try:
                                models = list(unit.get_attached_unit_models() or [])
                            except Exception:
                                models = list(getattr(unit, "models", []) or [])
                            alive = [m for m in models if getattr(m, "is_alive", True)]
                            if len(alive) > max_models:
                                continue
                        if getattr(unit.round_state, "disembarked_this_round", False):
                            continue
                        sr = getattr(unit, "special_rules", None)
                        if isinstance(sr, dict) and sr.get("fire_and_fade_no_embark_turn_owner"):
                            owner = str(sr.get("fire_and_fade_no_embark_turn_owner") or "")
                            turn = int(sr.get("fire_and_fade_no_embark_turn", 0) or 0)
                            if owner and owner == str(getattr(p, "id", "") or "") and int(getattr(self, "turn", 0) or 0) == turn:
                                continue
                        try:
                            if not transport.can_transport(unit):
                                continue
                        except Exception:
                            continue
                        if not unit_wholly_within_range_of_unit(transport, unit, range_value):
                            continue
                        # Must not be within Engagement Range of any enemy units.
                        enemies = list(game_map.get_enemy_units(unit) or [])
                        engaged = False
                        for enemy in enemies:
                            if enemy is None or not enemy.is_alive():
                                continue
                            if game_map.is_within_engagement_range(unit, enemy):
                                engaged = True
                                break
                        if engaged:
                            continue
                        candidates.append(unit)
                    if not candidates:
                        continue
                    self._queue_end_of_fight_embark_decision(
                        player=p,
                        transport=transport,
                        candidates=candidates,
                        spec=spec,
                    )

    def _on_phase_end_sweeping_advance(self, player=None, phase=None, **_kwargs) -> None:
        """Fight phase end: optional Sweeping Advance move for eligible models."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        if not bool(getattr(self, "is_authoritative", True)):
            return
        game_map = self.map
        if game_map is None:
            return

        for p in list(self.players or []):
            if p is None:
                continue
            army = self._get_player_army(p)
            if army is None:
                continue
            for unit in list(army.units or []):
                if unit is None:
                    continue
                if not unit.is_alive() or not getattr(unit, "deployed", True):
                    continue
                try:
                    if unit.is_in_reserves() or unit.is_embarked:
                        continue
                except Exception:
                    pass
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                if root is None or not root.is_alive():
                    continue
                try:
                    if not bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                        continue
                except Exception:
                    continue
                try:
                    models = list(getattr(unit, "models", []) or [])
                except Exception:
                    models = []
                for model in list(models or []):
                    if not getattr(model, "is_alive", True):
                        continue
                    try:
                        specs = list(unit.model_end_of_fight_sweeping_advance_specs(model) or [])
                    except Exception:
                        specs = []
                    if not specs:
                        continue
                    for spec in specs:
                        key = str(spec.get("key") or "sweeping_advance").strip().lower()
                        if not key:
                            key = "sweeping_advance"
                        if getattr(model, "has_used_once_per_battle", lambda _k: False)(key):
                            continue
                        unit_id = maybe_entity_id(root)
                        model_id = maybe_entity_id(model)
                        if not unit_id or not model_id:
                            continue
                        ability_name = str(spec.get("source", "") or "Sweeping Advance").strip() or "Sweeping Advance"
                        message = f"Use {ability_name} for {getattr(unit, 'name', 'Unit')}?"
                        ctx = {
                            "ability_name": ability_name,
                            "phase": "Fight phase",
                            "unit": getattr(unit, "name", "") or "",
                            "model": getattr(model, "name", "") or "",
                            "unit_id": unit_id,
                            "model_id": model_id,
                            "ability_key": key,
                        }
                        self._queue_optional_ability_confirmation(
                            player=p,
                            ability_key="sweeping_advance",
                            ability_name=ability_name,
                            message=message,
                            context=ctx,
                            payload={
                                "unit_id": unit_id,
                                "model_id": model_id,
                                "ability_key": key,
                            },
                            instance_key=f"{unit_id}:{model_id}",
                        )
        return

    def _on_phase_end_charge_phase_bodyguard_loss(self, player=None, phase=None, **_kwargs) -> None:
        """Charge phase end: failed Leadership test can destroy a Bodyguard model while leading."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "CHARGE_PHASE":
            return
        if player is None:
            return
        if player is not self.get_current_player():
            return

        army = self._get_player_army(player)
        if army is None:
            return
        game_map = self.map
        if game_map is None:
            return

        for unit in list(army.units):
            if unit is None:
                continue
            if not unit.is_alive() or not getattr(unit, "deployed", True):
                continue
            if not unit.is_attached_leader:
                continue
            ability = unit.get_charge_phase_bodyguard_loss_ability()
            if not ability:
                continue
            bodyguard = unit.get_attached_unit_root()
            if bodyguard is None or bodyguard is unit:
                continue
            if not getattr(bodyguard, "deployed", True):
                continue
            if str(getattr(bodyguard, "reserve_status", "deployed")) != "deployed":
                continue
            if bodyguard.is_in_reserves():
                continue
            if bool(getattr(bodyguard, "embarked_in", None)) or bodyguard.is_embarked:
                continue
            if len(bodyguard.models or []) <= 0:
                continue

            engaged = False
            enemies = list(game_map.get_enemy_units(bodyguard) or [])
            for enemy in enemies:
                if enemy is None:
                    continue
                if not getattr(enemy, "deployed", True):
                    continue
                if not enemy.is_alive():
                    continue
                if not game_map.is_within_engagement_range(bodyguard, enemy):
                    continue
                engaged = True
                break
            if engaged:
                continue

            leader_model = None
            for m in list(unit.models or []):
                if not getattr(m, "is_alive", True):
                    continue
                leader_model = m
                break
            if leader_model is None:
                continue

            passed = bool(unit.pass_leadership_check_for_model(leader_model))
            if passed:
                continue

            candidates = [m for m in (bodyguard.models or []) if getattr(m, "is_alive", True)]
            if not candidates:
                continue

            ability_name = str((ability or {}).get("name", "") or "Leadership Test").strip() or "Leadership Test"
            self.queue_bodyguard_loss(
                leader_unit=unit,
                bodyguard_unit=bodyguard,
                ability_name=ability_name,
                player=player,
            )

    def _on_phase_end_flickerjump_mortal_wounds(self, player=None, phase=None, **_kwargs) -> None:
        """Movement phase end: Flickerjump mortal wound rolls for units that used the ability."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "MOVEMENT_PHASE":
            return
        if player is None:
            return
        army = player.get_army() if player is not None else None
        if army is None:
            return
        from ...utility.dice import get_roll
        from ...utility.event_bus import append_action, append_dice

        for unit in list(getattr(army, "units", []) or []):
            if unit is None:
                continue
            if not unit.is_alive() or not getattr(unit, "deployed", True):
                continue
            try:
                if unit.is_in_reserves() or unit.is_embarked:
                    continue
            except Exception:
                pass
            sr = getattr(unit, "special_rules", None)
            if not isinstance(sr, dict):
                continue
            owner = str(sr.get("flickerjump_pending_uses_owner", "") or "")
            turn = int(sr.get("flickerjump_pending_uses_turn", 0) or 0)
            if owner and owner != str(getattr(player, "id", "") or ""):
                continue
            if int(getattr(self, "turn", 0) or 0) != turn:
                continue
            uses = int(sr.get("flickerjump_pending_uses", 0) or 0)
            if uses <= 0:
                continue
            ability_name = str(sr.get("flickerjump_source", "") or "Flickerjump").strip() or "Flickerjump"

            for _ in range(int(uses)):
                models = [m for m in list(getattr(unit, "models", []) or []) if getattr(m, "is_alive", True)]
                if not models:
                    break
                rolls = []
                ones = 0
                for _m in models:
                    r = int(get_roll("D6") or 0)
                    rolls.append(r)
                    if r == 1:
                        ones += 1
                if ones > 0:
                    unit._apply_mortal_wounds_to_unit(unit, int(ones), game_map=getattr(self, "map", None))
                append_dice(
                    player,
                    f"{ability_name}: rolls {rolls} => {int(ones)} mortal wounds to {getattr(unit, 'name', 'Unit')}.",
                )
                append_action(
                    player,
                    f"{ability_name}: {getattr(unit, 'name', 'Unit')} suffered {int(ones)} mortal wounds.",
                )

            for k in (
                "flickerjump_pending_uses",
                "flickerjump_pending_uses_turn",
                "flickerjump_pending_uses_owner",
                "flickerjump_source",
            ):
                sr.pop(k, None)
            unit.special_rules = sr

    def _on_phase_end_fight_phase_mortal_wounds(self, player=None, phase=None, **_kwargs) -> None:
        """Fight phase end: optional mortal wounds against an engaged enemy unit."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        game_map = self.map
        if game_map is None:
            return
        from ...utility.aura_utils import horizontal_distance_between_bases_2d, vertical_distance_between_bases

        def _model_in_engagement_with_unit(model, target_unit) -> bool:
            if not getattr(model, "is_alive", False):
                return False
            get_collision = getattr(target_unit, "get_models_for_collision", None)
            if callable(get_collision):
                t_models = list(get_collision() or [])
            else:
                t_models = list(target_unit.models or [])
            for t_model in t_models:
                if not getattr(t_model, "is_alive", False):
                    continue
                horizontal = float(horizontal_distance_between_bases_2d(model.model_base, t_model.model_base))
                vertical = float(vertical_distance_between_bases(model.model_base, t_model.model_base))
                if horizontal <= ENGAGEMENT_RANGE_HORIZONTAL and vertical <= ENGAGEMENT_RANGE_VERTICAL:
                    return True
            return False

        for p in list(self.players or []):
            if p is None:
                continue
            army = self._get_player_army(p)
            if army is None:
                continue
            for unit in list(army.units):
                if unit is None:
                    continue
                if not unit.is_alive() or not getattr(unit, "deployed", True):
                    continue
                if unit.is_in_reserves():
                    continue
                if unit.is_embarked:
                    continue

                enemies = list(game_map.get_enemy_units(unit) or [])
                if not enemies:
                    continue

                for model in list(unit.models or []):
                    if not getattr(model, "is_alive", False):
                        continue
                    specs = unit.model_end_fight_phase_engagement_mortal_wounds_specs(model) or []
                    if not specs:
                        continue

                    candidates = []
                    seen_enemy = set()
                    for enemy in enemies:
                        if enemy is None:
                            continue
                        root = enemy.get_attached_unit_root()
                        key = get_entity_id(root)
                        if key in seen_enemy:
                            continue
                        seen_enemy.add(key)
                        if not root.is_alive() or not getattr(root, "deployed", True):
                            continue
                        if root.is_in_reserves():
                            continue
                        if root.is_embarked:
                            continue
                        if _model_in_engagement_with_unit(model, root):
                            candidates.append(root)

                    if not candidates:
                        continue

                    for spec in specs:
                        self._queue_mortal_wounds_target_decision(
                            player=p,
                            unit=unit,
                            model=model,
                            candidates=list(candidates),
                            spec=spec,
                            kind="fight_phase_end",
                            allow_skip=True,
                            phase="Fight phase",
                        )

    def _on_phase_end_fight_phase_destroyed_strategic_reserves(self, player=None, phase=None, **_kwargs) -> None:
        """Fight phase end: units that destroyed enemies can enter Strategic Reserves (Warp Strike)."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        game_map = self.map
        if game_map is None:
            return
        tracked = set(self._phase_enemy_unit_destroyers.get(pname, set()) or set())
        if not tracked:
            return

        for p in list(self.players or []):
            if p is None:
                continue
            army = self._get_player_army(p)
            if army is None:
                continue
            seen = set()
            for unit in list(getattr(army, "units", []) or []):
                if unit is None:
                    continue
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                uid = get_entity_id(root)
                if not uid or uid in seen:
                    continue
                seen.add(uid)
                if uid not in tracked:
                    continue
                if not root.is_alive() or not getattr(root, "deployed", True):
                    continue
                if root.is_in_reserves() or root.is_embarked:
                    continue
                ability = root.get_end_of_fight_phase_destroyed_strategic_reserves_ability()
                if not ability:
                    continue
                engaged = False
                for enemy in list(game_map.get_enemy_units(root) or []):
                    if not enemy.is_alive() or not getattr(enemy, "deployed", True):
                        continue
                    if game_map.is_within_engagement_range(root, enemy):
                        engaged = True
                        break
                if engaged:
                    continue
                unit_id = get_entity_id(root)
                ability_name = str(ability.get("name", "") or "Strategic Reserves").strip() or "Strategic Reserves"
                ctx = {
                    "ability_name": ability_name,
                    "unit": getattr(root, "name", "") or "",
                    "phase": "End of Fight phase",
                    "unit_id": unit_id,
                }
                message = (
                    f"{getattr(root, 'name', 'Unit')} can enter Strategic Reserves at the end of the Fight phase.\n\n"
                    "Use this ability?"
                )
                self._queue_optional_ability_confirmation(
                    player=p,
                    ability_key="fight_phase_destroyed_strategic_reserves",
                    ability_name=ability_name,
                    message=message,
                    context=ctx,
                    payload={"unit_id": unit_id},
                    instance_key=str(unit_id or ""),
                )

    def _on_phase_end_plough_through_the_enemy(self, player=None, phase=None, **_kwargs) -> None:
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        game_map = self.map
        if game_map is None:
            return
        tracked = set(self._phase_enemy_unit_destroyers.get(pname, set()) or set())
        if not tracked:
            return
        from ...utility.aura_utils import unit_within_range_of_unit
        from ...utility.event_bus import append_action
        turn = int(getattr(self, "turn", 0) or 0)

        seen: set[str] = set()
        for p in list(self.players or []):
            if p is None:
                continue
            army = self._get_player_army(p)
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                if unit is None:
                    continue
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                uid = str(get_entity_id(root) or "")
                if not uid or uid in seen:
                    continue
                seen.add(uid)
                if uid not in tracked:
                    continue
                if not root.is_alive() or not getattr(root, "deployed", True):
                    continue
                try:
                    if root.is_in_reserves() or root.is_embarked:
                        continue
                except Exception:
                    pass
                if not bool(getattr(root, "has_plough_through_the_enemy", lambda: False)()):
                    continue
                hit_any = False
                tested_targets: set[str] = set()
                for enemy in list(game_map.get_enemy_units(root) or []):
                    if enemy is None:
                        continue
                    try:
                        enemy_root = enemy.get_attached_unit_root()
                    except Exception:
                        enemy_root = enemy
                    enemy_id = str(get_entity_id(enemy_root) or "")
                    if not enemy_id or enemy_id in tested_targets:
                        continue
                    tested_targets.add(enemy_id)
                    if not enemy_root.is_alive() or not getattr(enemy_root, "deployed", True):
                        continue
                    try:
                        if enemy_root.is_in_reserves() or enemy_root.is_embarked:
                            continue
                    except Exception:
                        pass
                    if not unit_within_range_of_unit(root, enemy_root, 6.0, use_attached_aggregate=True):
                        continue
                    enemy_root.take_battle_shock_test(turn)
                    hit_any = True
                if hit_any:
                    append_action(
                        p,
                        f"Plough Through the Enemy: enemy units within 6\" of {getattr(root, 'name', 'Unit')} take Battle-shock tests.",
                    )

    def _on_phase_end_soul_eater(self, player=None, phase=None, **_kwargs) -> None:
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        tracked = set(self._phase_enemy_unit_destroyers.get(pname, set()) or set())
        if not tracked:
            return
        from ...utility.event_bus import append_action

        seen: set[str] = set()
        for p in list(self.players or []):
            if p is None:
                continue
            army = self._get_player_army(p)
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                if unit is None:
                    continue
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                uid = str(get_entity_id(root) or "")
                if not uid or uid in seen:
                    continue
                seen.add(uid)
                if uid not in tracked:
                    continue
                if not root.is_alive() or not getattr(root, "deployed", True):
                    continue
                try:
                    if root.is_in_reserves() or root.is_embarked:
                        continue
                except Exception:
                    pass
                if not bool(getattr(root, "has_soul_eater", lambda: False)()):
                    continue
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                current_bonus = int(sr.get("soul_eater_attacks_bonus", 0) or 0)
                new_bonus = current_bonus + 1
                sr["soul_eater_attacks_bonus"] = int(new_bonus)
                sr["soul_eater_source"] = "Soul Eater"
                root.special_rules = sr
                append_action(
                    p,
                    f"Soul Eater: {getattr(root, 'name', 'Unit')} gains +1 Attacks to its weapons (total +{int(new_bonus)}).",
                )

    def _on_phase_end_leadership_cp_gain(self, player=None, phase=None, **_kwargs) -> None:
        """End of Shooting/Fight phase: Leadership test to gain CP after destroying enemy units."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname == "COMMAND_PHASE":
            if player is None:
                return
            if player is not self.get_current_player():
                return
            army = self._get_player_army(player)
            if army is None:
                return

            def _unit_sort_key(u):
                try:
                    return str(get_entity_id(u))
                except Exception:
                    return str(getattr(u, "name", "") or "")

            processed_models: set[str] = set()
            for unit in sorted(list(army.units or []), key=_unit_sort_key):
                if unit is None:
                    continue
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                if root is None:
                    continue
                if not root.is_alive() or not getattr(root, "deployed", True):
                    continue
                if root.is_in_reserves() or root.is_embarked:
                    continue
                try:
                    models = list(getattr(unit, "models", []) or [])
                except Exception:
                    models = []
                if not models:
                    continue

                def _model_sort_key(m):
                    try:
                        return str(get_entity_id(m))
                    except Exception:
                        return str(getattr(m, "name", "") or "")

                spec_fn = getattr(unit, "model_command_phase_end_leadership_cp_gain_specs", None)
                if not callable(spec_fn):
                    continue
                for model in sorted([m for m in models if getattr(m, "is_alive", True)], key=_model_sort_key):
                    mid = str(get_entity_id(model) or "")
                    if not mid or mid in processed_models:
                        continue
                    processed_models.add(mid)
                    specs = spec_fn(model) or []
                    for spec in specs:
                        if spec.get("type") != "command_phase_end_leadership_cp_gain":
                            continue
                        cp = int(spec.get("cp", 1) or 1)
                        if cp <= 0:
                            continue
                        if not bool(unit.pass_leadership_check_for_model(model)):
                            continue
                        gained = int(player.gain_command_points(cp, reason=spec.get("source_ability", "")) or 0)
                        self.event_system.publish(
                            "command_points_gained",
                            player=player,
                            amount=gained,
                            reason=spec.get("source_ability", ""),
                            unit=unit,
                        )
            return
        if pname not in ("SHOOTING_PHASE", "FIGHT_PHASE"):
            return
        if player is None:
            return
        if player is not self.get_current_player():
            return
        army = self._get_player_army(player)
        if army is None:
            return
        tracked = set(self._phase_enemy_unit_destroyers.get(pname, set()) or set())
        if not tracked:
            return

        processed: set[str] = set()
        for unit in list(army.units):
            if unit is None:
                continue
            try:
                root = unit.get_attached_unit_root()
            except Exception:
                root = unit
            uid = get_entity_id(root)
            if not uid or uid in processed:
                continue
            processed.add(uid)
            if uid not in tracked:
                continue
            if not root.is_alive() or not getattr(root, "deployed", True):
                continue
            if root.is_in_reserves() or root.is_embarked:
                continue

            specs = root.get_phase_end_leadership_cp_gain_specs() or []
            for spec in specs:
                if spec.get("type") != "phase_end_leadership_cp_gain":
                    continue
                cp = int(spec.get("cp", 1) or 1)
                if cp <= 0:
                    continue
                if not bool(root.pass_leadership_check()):
                    continue
                gained = int(player.gain_command_points(cp, reason=spec.get("source_ability", "")) or 0)
                self.event_system.publish(
                    "command_points_gained",
                    player=player,
                    amount=gained,
                    reason=spec.get("source_ability", ""),
                    unit=root,
                )

        self._phase_enemy_unit_destroyers[pname] = set()

    def _on_phase_end_daemonic_patrons(self, player=None, phase=None, **_kwargs) -> None:
        """End of Fight phase: destroy one model if Daemonic Patrons was called and no enemy models were destroyed."""
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "FIGHT_PHASE":
            return
        tracked = set(self._phase_enemy_model_destroyers.get(pname, set()) or set())
        seen: set[str] = set()

        for p in list(self.players or []):
            if p is None:
                continue
            army = self._get_player_army(p)
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                if unit is None:
                    continue
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                if root is None:
                    continue
                uid = get_entity_id(root)
                if not uid or uid in seen:
                    continue
                seen.add(uid)
                if not root.is_alive() or not getattr(root, "deployed", True):
                    continue
                if root.is_in_reserves() or root.is_embarked:
                    continue
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict) or not sr.get("daemonic_patrons_active"):
                    continue
                if uid in tracked:
                    continue

                ability_name = str(sr.get("daemonic_patrons_source", "") or "Daemonic Patrons").strip() or "Daemonic Patrons"
                owner = getattr(root.get_parent_army(), "player", None)
                if owner is None:
                    continue

                existing = [
                    req
                    for req in list(self.decision_queue.list() or [])
                    if getattr(req, "decision_type", None) == DECISION_ALLOCATE_DAMAGE
                    and str(getattr(req, "context", {}).get("selection_kind", "") or "") == "daemonic_patrons_loss"
                    and str(getattr(req, "context", {}).get("unit_id", "") or "") == uid
                ]
                if existing:
                    continue

                try:
                    models = list(root.get_attached_unit_models() or [])
                except Exception:
                    models = list(getattr(root, "models", []) or [])
                alive_models = []
                for m in models:
                    try:
                        alive = getattr(m, "is_alive", True)
                        alive = alive() if callable(alive) else bool(alive)
                    except Exception:
                        alive = True
                    if alive:
                        alive_models.append(m)
                if not alive_models:
                    continue
                try:
                    alive_models.sort(key=lambda m: str(get_entity_id(m) or ""))
                except Exception:
                    alive_models = list(alive_models)

                options = []
                used_labels = set()
                for model in alive_models:
                    label = str(getattr(model, "name", "") or "Model")
                    base = label
                    idx = 2
                    while label in used_labels:
                        label = f"{base} ({idx})"
                        idx += 1
                    used_labels.add(label)
                    options.append(DecisionOption.create(label, payload={"model_id": get_entity_id(model)}))
                allowed_ids = [get_entity_id(m) for m in alive_models if get_entity_id(m)]
                ctx = {
                    "selection_kind": "daemonic_patrons_loss",
                    "ability_name": ability_name,
                    "phase": "Fight phase",
                    "unit_id": uid,
                    "allowed_model_ids": allowed_ids,
                    "reason": f"{ability_name}: Destroy one model",
                }
                request = DecisionRequest.create(
                    DECISION_ALLOCATE_DAMAGE,
                    f"{ability_name}: Select model to destroy",
                    player_id=getattr(owner, "id", None),
                    options=options,
                    context=ctx,
                )
                self.request_decision(request)

        self._phase_enemy_model_destroyers[pname] = set()

    def _on_phase_end_setup_reactive_shoot_or_charge(self, player=None, phase=None, **_kwargs) -> None:
        pname = str(getattr(phase, "name", "") or "").strip().upper()
        if pname != "MOVEMENT_PHASE":
            return
        current_player = self.get_current_player()
        if current_player is None:
            return
        game_map = getattr(self, "map", None)
        if game_map is None:
            return

        for p in list(self.players or []):
            if p is None:
                raise RuntimeError("Setup reactive shoot/charge requires players.")
            if p is current_player:
                continue
            army = p.get_army()
            if army is None:
                raise RuntimeError(f"Setup reactive shoot/charge requires an army for {p.name}.")
            seen = set()
            for unit in list(army.units):
                if unit is None:
                    continue
                root = unit.get_attached_unit_root()
                if root is None:
                    continue
                rid = get_entity_id(root)
                if rid in seen:
                    continue
                seen.add(rid)
                rule = root.get_setup_reactive_shoot_or_charge_rule()
                if not rule:
                    continue
                if root.setup_reactive_shoot_or_charge_used_this_phase(self):
                    continue
                if not root.can_setup_reactive_shoot_or_charge(game=self, game_map=game_map):
                    root.clear_setup_reactive_shoot_or_charge_candidates(self)
                    continue
                candidate_ids = root.get_setup_reactive_shoot_or_charge_candidates(self)
                if not candidate_ids:
                    continue
                candidates = []
                for cid in candidate_ids:
                    enemy = self._resolve_unit_by_id(str(cid))
                    if enemy is None:
                        continue
                    if not enemy.is_alive():
                        continue
                    if not getattr(enemy, "deployed", True):
                        continue
                    if enemy.get_parent_army() == root.get_parent_army():
                        continue
                    candidates.append(enemy)
                if not candidates:
                    root.clear_setup_reactive_shoot_or_charge_candidates(self)
                    continue
                actionable = []
                for enemy in candidates:
                    if self._setup_reactive_available_actions(root, enemy):
                        actionable.append(enemy)
                if not actionable:
                    root.clear_setup_reactive_shoot_or_charge_candidates(self)
                    continue
                if p.has_control():
                    es = getattr(self, "event_system", None)
                    if es is None or not hasattr(es, "subscribers"):
                        raise RuntimeError("Event system missing for setup reactive prompt.")
                    subs = getattr(es, "subscribers", None)
                    if not isinstance(subs, dict):
                        raise RuntimeError("Event system subscribers not configured.")
                    if subs.get("setup_reactive_shoot_charge_prompt"):
                        es.publish(
                            "setup_reactive_shoot_charge_prompt",
                            player=p,
                            unit=root,
                            candidates=list(actionable),
                            rule=rule,
                            game=self,
                        )
                else:
                    self._queue_setup_reactive_target_decision(
                        player=p,
                        unit=root,
                        candidates=list(actionable),
                        rule=rule,
                    )
                root.clear_setup_reactive_shoot_or_charge_candidates(self)
