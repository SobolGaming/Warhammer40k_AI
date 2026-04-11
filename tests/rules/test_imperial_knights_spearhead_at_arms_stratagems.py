from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Imperial Knights"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "10",
                "Sv": "3",
                "W": "12",
                "Ld": "7",
                "OC": "8",
                "base_size": "100mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army_ik = Army.with_detachment("Imperial Knights", "Spearhead-At-Arms")
    army_ik.faction_id = "QI"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    ik_player = Player("IK", control=PlayerControl.LOCAL, army=army_ik)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(ik_player)
    game.add_player(enemy_player)
    ik_player.command_points = 5
    enemy_player.command_points = 5
    army_ik.configure_rule_managers(force=True)
    ik_player.stratagems.refresh_available()
    return game, ik_player, enemy_player, army_ik, army_enemy


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").replace("\u2019", "'").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        reaction_name = str(reaction.get("stratagem", "") or "").replace("\u2019", "'").strip().upper()
        if reaction_name == target:
            return reaction
    return None


def _equip_test_weapon(model, weapon_name: str, *, is_ranged: bool) -> WargearProfile:
    wargear = SimpleNamespace(name=weapon_name)
    wargear.is_melee = (lambda: False) if is_ranged else (lambda: True)
    wargear.is_ranged = (lambda: True) if is_ranged else (lambda: False)
    profile = WargearProfile(
        profile_name="Default",
        wargear_data={
            "range": "30" if is_ranged else "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "9",
            "AP": "0",
            "D": "3",
            "description": "",
        },
        parent_wargear=wargear,
    )
    wargear.profiles = {"default": profile}
    model.wargear = [wargear]
    return profile


def test_let_duty_be_your_shield_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000010507006")
    assert desc is not None
    assert desc.name == "Let Duty Be Your Shield"
    assert desc.effect == "worsen_incoming_ap"
    assert int(desc.cp_cost or 0) == 1


def test_exemplars_wisdom_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000010507003")
    assert desc is not None
    assert desc.name == "Exemplar's Wisdom"
    assert desc.effect == "selected_bondsman_armigers_gain_ap_against_selected_hit_enemy"
    assert int(desc.cp_cost or 0) == 1


def test_additional_spearhead_stratagem_descriptors_registered():
    expected = {
        "000010507002": ("Virtue of Courage", "selected_bondsman_armigers_gain_hit_bonus_against_selected_enemy"),
        "000010507004": ("Mantle of the Mentor", "eligible_to_shoot_after_fall_back"),
        "000010507005": ("Thin Their Ranks", "grant_ranged_keywords"),
        "000010507007": ("Squires Ofthe Hunt", "enter_strategic_reserves"),
    }
    for stratagem_id, (name, effect) in expected.items():
        desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert desc is not None
        assert desc.name == name
        assert desc.effect == effect
        assert int(desc.cp_cost or 0) == 1


def test_let_duty_be_your_shield_queues_and_worsens_ap_for_selected_attacker():
    game, ik_player, enemy_player, army_ik, army_enemy = _build_game()
    armiger = _make_unit(
        "Armiger Helverin",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_ik.add_unit(armiger)
    army_enemy.add_unit(enemy)
    for unit, x, y in ((armiger, 0.0, 0.0), (enemy, 18.0, 0.0)):
        for model in list(getattr(unit, "models", []) or []):
            model.set_location(float(x), float(y), 0.0, 0.0)
    game.map.units = [armiger, enemy]
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[armiger])
    pending = _pending_by_name(ik_player.stratagems, "LET DUTY BE YOUR SHIELD")
    assert pending is not None

    ok = ik_player.stratagems.use(
        "LET DUTY BE YOUR SHIELD",
        unit=armiger,
        attacker_unit=enemy,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok
    assert int(ik_player.command_points or 0) == 4

    parent = SimpleNamespace(name="Autocannon", is_melee=lambda: False, is_ranged=lambda: True)
    profile = WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "48",
            "A": "1",
            "BS_WS": "3+",
            "S": "9",
            "AP": "-2",
            "D": "3",
            "description": "",
        },
        parent_wargear=parent,
    )

    assert profile.get_effective_ap(enemy.models[0], armiger) == -1

    game.event_system.publish("unit_shooting_resolved", attacker_unit=enemy)
    assert profile.get_effective_ap(enemy.models[0], armiger) == -2


def test_exemplars_wisdom_queues_after_titanic_shooting_and_marks_selected_armigers():
    game, ik_player, _enemy_player, army_ik, army_enemy = _build_game()
    source = _make_unit(
        "Knight Paladin",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "TITANIC"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    armiger_a = _make_unit(
        "Armiger Warglaive A",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    armiger_b = _make_unit(
        "Armiger Warglaive B",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy_a = _make_unit(
        "Enemy Alpha",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_b = _make_unit(
        "Enemy Beta",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_ik.add_unit(source)
    army_ik.add_unit(armiger_a)
    army_ik.add_unit(armiger_b)
    army_enemy.add_unit(enemy_a)
    army_enemy.add_unit(enemy_b)
    for unit, x, y in (
        (source, 0.0, 0.0),
        (armiger_a, 4.0, 0.0),
        (armiger_b, 8.0, 0.0),
        (enemy_a, 16.0, 0.0),
        (enemy_b, 20.0, 0.0),
    ):
        for model in list(getattr(unit, "models", []) or []):
            model.set_location(float(x), float(y), 0.0, 0.0)
    game.map.units = [source, armiger_a, armiger_b, enemy_a, enemy_b]
    game.rebuild_entity_registry()

    source_id = str(get_entity_id(source) or "")
    armiger_a.special_rules.update(
        {
            "bondsman_active": True,
            "bondsman_source_unit_id": source_id,
        }
    )
    armiger_b.special_rules.update(
        {
            "bondsman_active": True,
            "bondsman_source_unit_id": source_id,
        }
    )
    source.round_state.shot_this_round = True

    _set_phase(game, ik_player, "SHOOTING_PHASE", 0)
    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=source,
        hits_by_target={enemy_a: 1},
    )
    pending = _pending_by_name(ik_player.stratagems, "EXEMPLAR'S WISDOM")
    assert pending is not None

    use_name = str(pending.get("stratagem", "") or "EXEMPLAR'S WISDOM")
    ok = ik_player.stratagems.use(
        use_name,
        source_unit=source,
        selected_units=[armiger_a],
        enemy_unit=enemy_a,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok
    assert int(ik_player.command_points or 0) == 4

    parent = SimpleNamespace(name="Thermal Spear", is_melee=lambda: False, is_ranged=lambda: True)
    profile = WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "30",
            "A": "1",
            "BS_WS": "3+",
            "S": "9",
            "AP": "0",
            "D": "3",
            "description": "",
        },
        parent_wargear=parent,
    )

    assert profile.get_effective_ap(armiger_a.models[0], enemy_a) == -1
    assert profile.get_effective_ap(armiger_a.models[0], enemy_b) == 0
    assert profile.get_effective_ap(armiger_b.models[0], enemy_a) == 0

    game.event_system.publish("phase_end", player=ik_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert profile.get_effective_ap(armiger_a.models[0], enemy_a) == 0


def test_mantle_of_the_mentor_allows_selected_armiger_to_shoot_after_fall_back_until_phase_end():
    game, ik_player, _enemy_player, army_ik, _army_enemy = _build_game()
    armiger = _make_unit(
        "Armiger Helverin",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    army_ik.add_unit(armiger)
    _deploy_unit(game, armiger, 10.0, 10.0)
    game.rebuild_entity_registry()

    armiger.round_state.fell_back_this_round = True
    profile = _equip_test_weapon(armiger.models[0], "Thermal Spear", is_ranged=True)

    _set_phase(game, ik_player, "SHOOTING_PHASE", 0)
    assert armiger.can_shoot_after_fall_back(profile) is False

    ok = ik_player.stratagems.use("MANTLE OF THE MENTOR", unit=armiger, phase_name="Shooting phase")
    assert ok is True
    assert int(ik_player.command_points or 0) == 4
    assert armiger.can_shoot_after_fall_back(profile) is True

    game.event_system.publish("phase_end", player=ik_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert armiger.can_shoot_after_fall_back(profile) is False


def test_thin_their_ranks_grants_rapid_fire_to_selected_armiger_ranged_weapons_until_phase_end():
    game, ik_player, _enemy_player, army_ik, _army_enemy = _build_game()
    armiger = _make_unit(
        "Armiger Warglaive",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    army_ik.add_unit(armiger)
    _deploy_unit(game, armiger, 10.0, 10.0)
    game.rebuild_entity_registry()

    _equip_test_weapon(armiger.models[0], "Thermal Spear", is_ranged=True)
    _set_phase(game, ik_player, "SHOOTING_PHASE", 0)

    ok = ik_player.stratagems.use("THIN THEIR RANKS", unit=armiger, phase_name="Shooting phase")
    assert ok is True
    assert int(ik_player.command_points or 0) == 4

    bonuses = list(armiger.models[0].get_temporary_weapon_keyword_bonuses("Thermal Spear") or [])
    assert any(
        str(entry.get("keyword", "") or "").strip().upper() == "RAPID FIRE 1"
        and str(entry.get("attack_type", "") or "").strip().lower() == "ranged"
        for entry in bonuses
    )

    game.event_system.publish("phase_end", player=ik_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(armiger.models[0].get_temporary_weapon_keyword_bonuses("Thermal Spear") or []) == []


def test_virtue_of_courage_grants_selected_bonded_armiger_plus_one_to_hit_against_selected_enemy():
    game, ik_player, enemy_player, army_ik, army_enemy = _build_game()
    source = _make_unit(
        "Knight Paladin",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "TITANIC"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    armiger = _make_unit(
        "Armiger Warglaive",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy_a = _make_unit(
        "Enemy Alpha",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_b = _make_unit(
        "Enemy Beta",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_ik.add_unit(source)
    army_ik.add_unit(armiger)
    army_enemy.add_unit(enemy_a)
    army_enemy.add_unit(enemy_b)
    for unit, x, y in (
        (source, 10.0, 10.0),
        (armiger, 22.0, 10.0),
        (enemy_a, 34.0, 10.0),
        (enemy_b, 46.0, 10.0),
    ):
        _deploy_unit(game, unit, x, y)
    game.rebuild_entity_registry()

    source_id = str(get_entity_id(source) or "")
    armiger.special_rules.update({"bondsman_active": True, "bondsman_source_unit_id": source_id})
    profile = WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "10",
            "AP": "-2",
            "D": "3",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Reaper Chain-cleaver", is_melee=lambda: True, is_ranged=lambda: False),
    )

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    ok = ik_player.stratagems.use(
        "VIRTUE OF COURAGE",
        source_unit=source,
        selected_units=[armiger],
        enemy_unit=enemy_a,
        phase_name="Fight phase",
    )
    assert ok is True
    assert int(ik_player.command_points or 0) == 4

    hit_targeted = profile._hit_target_with_tracking(
        enemy_a,
        armiger.models[0],
        {},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_targeted.get("hit")) is True
    assert "+1 to hit from VIRTUE OF COURAGE" in list(hit_targeted.get("modifiers", []) or [])

    hit_other = profile._hit_target_with_tracking(
        enemy_b,
        armiger.models[0],
        {},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_other.get("hit")) is False
    assert "+1 to hit from VIRTUE OF COURAGE" not in list(hit_other.get("modifiers", []) or [])

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    hit_after = profile._hit_target_with_tracking(
        enemy_a,
        armiger.models[0],
        {},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(hit_after.get("hit")) is False
    assert "+1 to hit from VIRTUE OF COURAGE" not in list(hit_after.get("modifiers", []) or [])


def test_squires_ofthe_hunt_queues_at_opponent_fight_phase_end_and_moves_selected_armiger_into_reserves():
    game, ik_player, enemy_player, army_ik, army_enemy = _build_game()
    source = _make_unit(
        "Knight Paladin",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "TITANIC"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    armiger = _make_unit(
        "Armiger Warglaive",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE", "ARMIGER"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_ik.add_unit(source)
    army_ik.add_unit(armiger)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, source, 20.0, 20.0)
    _deploy_unit(game, armiger, 4.0, 10.0)
    _deploy_unit(game, enemy, 25.0, 25.0)
    game.rebuild_entity_registry()

    source_id = str(get_entity_id(source) or "")
    armiger.special_rules.update({"bondsman_active": True, "bondsman_source_unit_id": source_id})

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    pending = _pending_by_name(ik_player.stratagems, "SQUIRES OFTHE HUNT")
    assert pending is not None

    ok = ik_player.stratagems.use(
        "SQUIRES OFTHE HUNT",
        source_unit=source,
        selected_units=[armiger],
        dequeue=True,
    )
    assert ok is True
    assert int(ik_player.command_points or 0) == 4
    assert str(getattr(armiger, "reserve_status", "") or "") == "strategic_reserves"
    assert armiger not in list(getattr(game.map, "units", []) or [])
