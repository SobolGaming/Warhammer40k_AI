from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile
from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_NEGATIVE
from warhammer40k_ai.utility.modifiers import Modifier, ModifierOp


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Adepta Sororitas",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        movement: int = 6,
        toughness: int = 4,
        wounds: int = 4,
        leadership: int = 7,
        objective_control: int = 2,
        save: int = 3,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTA SORORITAS"] if faction_name == "Adepta Sororitas" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(movement)),
                "T": str(int(toughness)),
                "Sv": str(int(save)),
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Adepta Sororitas",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    movement: int = 6,
    toughness: int = 4,
    wounds: int = 4,
    leadership: int = 7,
    objective_control: int = 2,
    save: int = 3,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
            leadership=leadership,
            objective_control=objective_control,
            save=save,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sororitas_army = Army("Adepta Sororitas", "Army of Faith")
    sororitas_army.faction_id = "AS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sororitas_player = Player("Sororitas", control=PlayerControl.LOCAL, army=sororitas_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sororitas_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    sororitas_player.command_points = 10
    enemy_player.command_points = 10

    sororitas_army.configure_rule_managers(force=True)
    sororitas_player.stratagems.refresh_available()
    return game, sororitas_player, enemy_player, sororitas_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 1.5, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _pending_names(stratagems) -> set[str]:
    return {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in list(stratagems.get_pending_reactions(clear=True) or [])
    }


def _ranged_wargear(
    name: str = "Holy Boltgun",
    *,
    attacks: str = "1",
    skill: str = "3+",
    strength: str = "4",
    ap: str = "0",
    damage: str = "1",
    description: str = "",
) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": str(attacks),
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": str(description),
        }
    )


def _melee_wargear(
    name: str = "Blessed Blade",
    *,
    attacks: str = "2",
    skill: str = "3+",
    strength: str = "4",
    ap: str = "-1",
    damage: str = "1",
    description: str = "",
) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": str(attacks),
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": str(description),
        }
    )


def _make_profile(*, is_melee: bool, strength: str = "4", skill: str = "3+", damage: str = "1") -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Weapon",
        is_melee=lambda: bool(is_melee),
        is_ranged=lambda: not bool(is_melee),
    )
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": "Melee" if is_melee else "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": str(damage),
            "description": "",
        },
        parent_wargear=parent,
    )


def test_army_of_faith_stratagem_descriptors_registered():
    expected = {
        "000009038005": ("Blinding Radiance", "hit_penalty_with_jump_pack_aura"),
        "000009038006": ("Divine Guidance", "ap_bonus_and_miracle_die_on_destroyed_model"),
        "000009038004": ("Faith and Fury", "grant_lance_and_miracle_die_on_destroyed_model"),
        "000009038003": ("Light of the Emperor", "ignore_modifiers_with_jump_pack_blessed_aura"),
        "000009038002": ("Shield of Faith", "mortal_wound_fnp_with_jump_pack_aura"),
        "000009038007": ("Angelic Descent", "enter_strategic_reserves"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect
        assert by_name.effect == expected_effect


def test_army_of_faith_phase_reactions_queue_expected_stratagems():
    game, sororitas_player, enemy_player, sororitas_army, enemy_army = _build_game()
    sisters = _make_unit(
        "Battle Sisters Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    seraphim = _make_unit(
        "Seraphim Squad",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTA SORORITAS"],
        movement=12,
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sisters.models[0].wargear = [_ranged_wargear()]
    seraphim.models[0].wargear = [_melee_wargear()]

    sororitas_army.add_unit(sisters)
    sororitas_army.add_unit(seraphim)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, sisters, 10.0, 10.0)
    _deploy_unit(game, seraphim, 14.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sororitas_player, "COMMAND_PHASE", 0)
    assert _pending_names(sororitas_player.stratagems) == {"LIGHT OF THE EMPEROR"}

    _set_phase(game, sororitas_player, "SHOOTING_PHASE", 0)
    assert _pending_names(sororitas_player.stratagems) == {"DIVINE GUIDANCE"}

    _set_phase(game, sororitas_player, "FIGHT_PHASE", 0)
    assert _pending_names(sororitas_player.stratagems) == {"DIVINE GUIDANCE", "FAITH AND FURY"}

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    assert _pending_names(sororitas_player.stratagems) == set()
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[sisters])
    assert _pending_by_name(sororitas_player.stratagems, "BLINDING RADIANCE") is not None
    sororitas_player.stratagems.get_pending_reactions(clear=True)

    game.event_system.publish(
        "mortal_wound_allocated",
        target_unit=sisters,
        attacker_unit=enemy,
        target_model=sisters.models[0],
        phase_name="Shooting phase",
    )
    assert _pending_by_name(sororitas_player.stratagems, "SHIELD OF FAITH") is not None
    sororitas_player.stratagems.get_pending_reactions(clear=True)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert _pending_by_name(sororitas_player.stratagems, "ANGELIC DESCENT") is not None


def test_divine_guidance_applies_ap_bonus_and_grants_miracle_die_on_destroyed_model():
    game, sororitas_player, _enemy_player, sororitas_army, enemy_army = _build_game()
    sisters = _make_unit(
        "Battle Sisters Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sisters.models[0].wargear = [_ranged_wargear("Blessed Bolter", ap="0")]

    sororitas_army.add_unit(sisters)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, sisters, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sororitas_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(sororitas_player.stratagems, "DIVINE GUIDANCE")
    assert pending is not None

    ok = sororitas_player.stratagems.use(
        "DIVINE GUIDANCE",
        unit=sisters,
        phase_name="Shooting phase",
        candidates=list(pending.get("candidates") or []),
        dequeue=True,
    )
    assert ok is True
    assert int(sororitas_player.command_points or 0) == 9

    profile = sisters.models[0].wargear[0].profiles["default"]
    assert int(profile.get_effective_ap(sisters.models[0], enemy) or 0) == -1
    assert list(getattr(sororitas_army.acts_of_faith, "miracle_dice", []) or []) == []

    game.event_system.publish(
        "model_destroyed",
        attacker_model=sisters.models[0],
        attacker_unit=sisters,
        target_model=enemy.models[0],
        target_unit=enemy,
        weapon_profile=profile,
        game_map=game.map,
    )
    assert len(list(getattr(sororitas_army.acts_of_faith, "miracle_dice", []) or [])) == 1

    game.event_system.publish(
        "model_destroyed",
        attacker_model=sisters.models[0],
        attacker_unit=sisters,
        target_model=enemy.models[0],
        target_unit=enemy,
        weapon_profile=profile,
        game_map=game.map,
    )
    assert len(list(getattr(sororitas_army.acts_of_faith, "miracle_dice", []) or [])) == 1

    game.event_system.publish("phase_end", player=sororitas_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert int(profile.get_effective_ap(sisters.models[0], enemy) or 0) == 0


def test_faith_and_fury_grants_lance_and_miracle_die_on_destroyed_model():
    game, sororitas_player, _enemy_player, sororitas_army, enemy_army = _build_game()
    zephyrim = _make_unit(
        "Zephyrim Squad",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTA SORORITAS"],
        movement=12,
    )
    enemy = _make_unit(
        "Enemy Elite",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness=4,
        wounds=6,
    )
    zephyrim.models[0].wargear = [_melee_wargear("Power Sword", strength="4")]

    sororitas_army.add_unit(zephyrim)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, zephyrim, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sororitas_player, "FIGHT_PHASE", 0)
    pending = _pending_by_name(sororitas_player.stratagems, "FAITH AND FURY")
    assert pending is not None

    ok = sororitas_player.stratagems.use(
        "FAITH AND FURY",
        unit=zephyrim,
        phase_name="Fight phase",
        candidates=list(pending.get("candidates") or []),
        dequeue=True,
    )
    assert ok is True
    assert int(sororitas_player.command_points or 0) == 9

    bonuses = list(zephyrim.models[0].get_temporary_weapon_keyword_bonuses("Power Sword") or [])
    assert any(
        str(entry.get("keyword", "") or "").strip().upper() == "LANCE"
        and str(entry.get("attack_type", "") or "").strip().lower() == "melee"
        for entry in bonuses
    )

    zephyrim.round_state.charged_this_round = True
    profile = zephyrim.models[0].wargear[0].profiles["default"]
    attack_instance: dict = {}
    hit_result = profile._hit_target_with_tracking(
        enemy,
        zephyrim.models[0],
        attack_instance,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_result.get("hit")) is True

    wound_result = profile._wound_target_with_tracking(
        enemy,
        zephyrim.models[0],
        attack_instance,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(wound_result.get("wound")) is True

    game.event_system.publish(
        "model_destroyed",
        attacker_model=zephyrim.models[0],
        attacker_unit=zephyrim,
        target_model=enemy.models[0],
        target_unit=enemy,
        weapon_profile=profile,
        game_map=game.map,
    )
    assert len(list(getattr(sororitas_army.acts_of_faith, "miracle_dice", []) or [])) == 1

    game.event_system.publish("phase_end", player=sororitas_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert list(zephyrim.models[0].get_temporary_weapon_keyword_bonuses("Power Sword") or []) == []


def test_light_of_the_emperor_blesses_jump_pack_aura_units_and_ignores_negative_modifiers():
    game, sororitas_player, enemy_player, sororitas_army, enemy_army = _build_game()
    seraphim = _make_unit(
        "Seraphim Squad",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTA SORORITAS"],
        movement=12,
    )
    sisters = _make_unit(
        "Battle Sisters Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTA SORORITAS"],
        movement=6,
        objective_control=2,
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    sororitas_army.add_unit(seraphim)
    sororitas_army.add_unit(sisters)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, seraphim, 10.0, 10.0)
    _deploy_unit(game, sisters, 14.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sororitas_player, "COMMAND_PHASE", 0)
    pending = _pending_by_name(sororitas_player.stratagems, "LIGHT OF THE EMPEROR")
    assert pending is not None

    ok = sororitas_player.stratagems.use(
        "LIGHT OF THE EMPEROR",
        unit=seraphim,
        phase_name="Command phase",
        candidates=list(pending.get("candidates") or []),
        dequeue=True,
    )
    assert ok is True
    assert int(sororitas_player.command_points or 0) == 9

    expected_rule = {
        "source": "LIGHT OF THE EMPEROR",
        "default_choice": "ignore_negative",
    }
    assert seraphim.get_move_advance_charge_modifier_ignore_rule() == expected_rule
    assert sisters.get_move_advance_charge_modifier_ignore_rule() == expected_rule

    sisters.add_characteristic_modifier("movement", Modifier(ModifierOp.SUB, 2, source="test:move"))
    sisters.add_characteristic_modifier("objective_control", Modifier(ModifierOp.SUB, 1, source="test:oc"))

    model = sisters.models[0]
    assert int(sisters.get_effective_model_characteristic(model, "movement", game_map=game.map) or 0) == 6
    assert int(sisters.get_effective_model_characteristic(model, "objective_control", game_map=game.map) or 0) == 2

    attack_instance = {"hit_roll_modifiers": [(-1, "Test penalty")]}
    hit_result = _make_profile(is_melee=False)._hit_target_with_tracking(
        enemy,
        model,
        attack_instance,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_result.get("hit")) is True
    assert attack_instance.get("hit_modifier_choice") == CHOICE_IGNORE_NEGATIVE

    sisters.models[0].set_location(18.0, 10.0, 0.0, 0.0)
    assert sisters.get_move_advance_charge_modifier_ignore_rule() is None
    assert int(sisters.get_effective_model_characteristic(model, "movement", game_map=game.map) or 0) == 4

    game.turn = 2
    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
    assert seraphim.get_move_advance_charge_modifier_ignore_rule() is None


def test_blinding_radiance_applies_jump_pack_aura_and_cleans_up():
    game, sororitas_player, enemy_player, sororitas_army, enemy_army = _build_game()
    sisters = _make_unit(
        "Battle Sisters Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    seraphim = _make_unit(
        "Seraphim Squad",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTA SORORITAS"],
        movement=12,
    )
    enemy = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_weapon = _ranged_wargear("Enemy Rifle", skill="4+", strength="4")
    enemy.models[0].wargear = [enemy_weapon]

    sororitas_army.add_unit(sisters)
    sororitas_army.add_unit(seraphim)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, sisters, 10.0, 10.0)
    _deploy_unit(game, seraphim, 14.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    profile = enemy_weapon.profiles["default"]

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[sisters])
    pending = _pending_by_name(sororitas_player.stratagems, "BLINDING RADIANCE")
    assert pending is not None

    ok = sororitas_player.stratagems.use(
        "BLINDING RADIANCE",
        unit=seraphim,
        attacking_unit=enemy,
        target_units=[sisters],
        phase_name="Shooting phase",
        candidates=list(pending.get("candidates") or []),
        dequeue=True,
    )
    assert ok is True
    assert int(sororitas_player.command_points or 0) == 9

    sisters_hit_mods = list(sisters.special_rules.get("defensive_hit_mods", []) or [])
    seraphim_hit_mods = list(seraphim.special_rules.get("defensive_hit_mods", []) or [])
    assert any(int(entry.get("value", 0) or 0) == 1 for entry in sisters_hit_mods if isinstance(entry, dict))
    assert any(int(entry.get("value", 0) or 0) == 1 for entry in seraphim_hit_mods if isinstance(entry, dict))

    during_hit = profile._hit_target_with_tracking(
        sisters,
        enemy.models[0],
        {"distance_to_target": 8.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(during_hit.get("hit")) is False

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(sisters.special_rules.get("defensive_hit_mods", []) or []) == []
    assert list(seraphim.special_rules.get("defensive_hit_mods", []) or []) == []


def test_shield_of_faith_applies_jump_pack_aura_and_cleans_up():
    game, sororitas_player, enemy_player, sororitas_army, enemy_army = _build_game()
    sisters = _make_unit(
        "Battle Sisters Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    seraphim = _make_unit(
        "Seraphim Squad",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTA SORORITAS"],
        movement=12,
    )
    enemy = _make_unit(
        "Enemy Psyker",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    sororitas_army.add_unit(sisters)
    sororitas_army.add_unit(seraphim)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, sisters, 10.0, 10.0)
    _deploy_unit(game, seraphim, 14.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish(
        "mortal_wound_allocated",
        target_unit=sisters,
        attacker_unit=enemy,
        target_model=sisters.models[0],
        phase_name="Shooting phase",
    )
    pending = _pending_by_name(sororitas_player.stratagems, "SHIELD OF FAITH")
    assert pending is not None

    ok = sororitas_player.stratagems.use(
        "SHIELD OF FAITH",
        unit=seraphim,
        source_unit=sisters,
        phase_name="Shooting phase",
        candidates=list(pending.get("candidates") or []),
        dequeue=True,
    )
    assert ok is True
    assert int(sororitas_player.command_points or 0) == 9

    assert (5, "against mortal wounds") in list(sisters.models[0].get_temporary_fnp_entries() or [])
    assert (5, "against mortal wounds") in list(seraphim.models[0].get_temporary_fnp_entries() or [])

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(sisters.models[0].get_temporary_fnp_entries() or []) == []
    assert list(seraphim.models[0].get_temporary_fnp_entries() or []) == []


def test_angelic_descent_queues_at_end_of_opponent_fight_phase_and_enters_strategic_reserves():
    game, sororitas_player, enemy_player, sororitas_army, enemy_army = _build_game()
    seraphim = _make_unit(
        "Seraphim Squad",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTA SORORITAS"],
        movement=12,
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    sororitas_army.add_unit(seraphim)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, seraphim, 10.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    pending = _pending_by_name(sororitas_player.stratagems, "ANGELIC DESCENT")
    assert pending is not None

    ok = sororitas_player.stratagems.use(
        "ANGELIC DESCENT",
        unit=seraphim,
        phase_name="Fight phase",
        candidates=list(pending.get("candidates") or []),
        dequeue=True,
    )
    assert ok is True
    assert int(sororitas_player.command_points or 0) == 9
    assert str(getattr(seraphim, "reserve_status", "") or "").strip().lower() == "strategic_reserves"
