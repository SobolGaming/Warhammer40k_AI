from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        model_count: int = 1,
        wounds: int = 6,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Grey Knights"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _deep_strike_ability() -> dict:
    return {
        "name": "Deep Strike",
        "description": "Deep Strike",
        "type": "Core",
        "parameter": "",
    }


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    abilities=None,
    model_count: int = 1,
    wounds: int = 6,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            model_count=model_count,
            wounds=wounds,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _ranged_wargear(name: str = "Storm Bolter", *, psychic: bool = False) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "[PSYCHIC]" if psychic else "",
        }
    )


def _melee_wargear(name: str = "Nemesis Force Weapon", *, psychic: bool = False) -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "6",
            "AP": "-2",
            "D": "2",
            "description": "[PSYCHIC]" if psychic else "",
        }
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2
    army_gk = Army.with_detachment("Grey Knights", "Brotherhood Strike")
    army_gk.faction_id = "GK"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    p1 = Player("GK", control=PlayerControl.LOCAL, army=army_gk)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(p1)
    game.add_player(p2)
    p1.command_points = 6
    p2.command_points = 6
    army_gk.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, p1, p2, army_gk, army_enemy


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _note_deep_strike_arrival(game: Game, player: Player, unit: Unit) -> None:
    _set_phase(game, player, "MOVEMENT_PHASE", 0)
    game.event_system.publish(
        "unit_set_up",
        unit=unit,
        set_up_as_reinforcements=True,
        used_deep_strike=True,
    )


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _pending_names(stratagems, *, clear: bool = False) -> set[str]:
    return {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in list(stratagems.get_pending_reactions(clear=clear) or [])
    }


def test_brotherhood_strike_stratagem_descriptors_registered():
    expected = {
        "000010349002": ("Truesilver Channelling", "grant_psychic_weapon_keywords"),
        "000010349003": ("Combat Manifestation", "deep_strike_min_distance_override_with_no_charge"),
        "000010349004": ("Purgation Pattern", "grant_ranged_weapon_keywords"),
        "000010349005": ("Duty Unending", "enter_strategic_reserves_if_deep_strike"),
        "000010349006": ("Shining Veil", "grant_stealth"),
        "000010349007": ("Expeditious Exit", "enter_strategic_reserves_if_deep_strike"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_brotherhood_phase_start_reactions_queue_purgation_and_truesilver():
    game, p1, _p2, army_gk, _army_enemy = _build_game()
    deep_strike_unit = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY"],
        faction_keywords=["GREY KNIGHTS"],
        abilities=[_deep_strike_ability()],
    )
    fight_unit = _make_unit(
        "Purifier Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
    )
    army_gk.add_unit(deep_strike_unit)
    army_gk.add_unit(fight_unit)
    _deploy_unit(game, deep_strike_unit, 10.0, 10.0)
    _deploy_unit(game, fight_unit, 14.0, 10.0)
    game.rebuild_entity_registry()

    _note_deep_strike_arrival(game, p1, deep_strike_unit)
    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    assert _pending_names(p1.stratagems, clear=True) == {"PURGATION PATTERN"}

    _set_phase(game, p1, "FIGHT_PHASE", 0)
    assert _pending_names(p1.stratagems, clear=True) == {"TRUESILVER CHANNELLING"}


def test_purgation_pattern_grants_sustained_hits_to_ranged_weapons_until_phase_end():
    game, p1, _p2, army_gk, _army_enemy = _build_game()
    shooters = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY"],
        faction_keywords=["GREY KNIGHTS"],
        abilities=[_deep_strike_ability()],
    )
    shooters.models[0].wargear = [_ranged_wargear()]
    army_gk.add_unit(shooters)
    _deploy_unit(game, shooters, 10.0, 10.0)
    game.rebuild_entity_registry()

    _note_deep_strike_arrival(game, p1, shooters)
    _set_phase(game, p1, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(p1.stratagems, "PURGATION PATTERN")
    assert pending is not None

    ok = p1.stratagems.use(
        "PURGATION PATTERN",
        unit=shooters,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok
    bonuses = list(shooters.models[0].get_temporary_weapon_keyword_bonuses("Storm Bolter") or [])
    assert any(str(item.get("keyword", "") or "") == "SUSTAINED HITS 1" for item in bonuses)

    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(shooters.models[0].get_temporary_weapon_keyword_bonuses("Storm Bolter") or []) == []


def test_duty_unending_queues_after_enemy_falls_back_and_enters_strategic_reserves():
    game, p1, p2, army_gk, army_enemy = _build_game()
    target = _make_unit(
        "Terminator Squad",
        keywords=["INFANTRY"],
        faction_keywords=["GREY KNIGHTS"],
        abilities=[_deep_strike_ability()],
    )
    enemy = _make_unit(
        "Enemy Raiders",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_gk.add_unit(target)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    assert bool(game.map.is_within_engagement_range(enemy, target))
    _set_phase(game, p2, "MOVEMENT_PHASE", 1)
    game.event_system.publish("unit_move_started", unit=enemy, action="fall_back")
    enemy.models[0].set_location(18.0, 10.0, 0.0, 0.0)
    game.event_system.publish("unit_move_ended", unit=enemy, action="fall_back")

    pending = _pending_by_name(p1.stratagems, "DUTY UNENDING")
    assert pending is not None
    assert target in list(pending.get("candidates") or [])

    ok = p1.stratagems.use(
        "DUTY UNENDING",
        unit=target,
        enemy_unit=enemy,
        action="fall_back",
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok
    assert str(getattr(target, "reserve_status", "") or "") == "strategic_reserves"
    assert target not in list(getattr(game.map, "units", []) or [])


def test_shining_veil_queues_on_enemy_targets_and_grants_stealth_until_phase_end():
    game, p1, p2, army_gk, army_enemy = _build_game()
    target = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY"],
        faction_keywords=["GREY KNIGHTS"],
    )
    enemy = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy.models[0].wargear = [_ranged_wargear("Enemy Rifle")]
    army_gk.add_unit(target)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[target])
    pending = _pending_by_name(p1.stratagems, "SHINING VEIL")
    assert pending is not None

    ok = p1.stratagems.use(
        "SHINING VEIL",
        unit=target,
        attacking_unit=enemy,
        target_units=[target],
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok
    assert bool(target.has_stealth()) is True

    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert bool(target.has_stealth()) is False


def test_truesilver_channelling_grants_devastating_wounds_to_psychic_weapons_until_phase_end():
    game, p1, _p2, army_gk, _army_enemy = _build_game()
    fighters = _make_unit(
        "Purifier Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
    )
    fighters.models[0].wargear = [
        _melee_wargear("Nemesis Force Weapon", psychic=True),
        _ranged_wargear("Storm Bolter"),
    ]
    army_gk.add_unit(fighters)
    _deploy_unit(game, fighters, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p1, "FIGHT_PHASE", 0)
    pending = _pending_by_name(p1.stratagems, "TRUESILVER CHANNELLING")
    assert pending is not None

    ok = p1.stratagems.use(
        "TRUESILVER CHANNELLING",
        unit=fighters,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok
    psychic_bonuses = list(fighters.models[0].get_temporary_weapon_keyword_bonuses("Nemesis Force Weapon") or [])
    ranged_bonuses = list(fighters.models[0].get_temporary_weapon_keyword_bonuses("Storm Bolter") or [])
    assert any(str(item.get("keyword", "") or "") == "DEVASTATING WOUNDS" for item in psychic_bonuses)
    assert ranged_bonuses == []

    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert list(fighters.models[0].get_temporary_weapon_keyword_bonuses("Nemesis Force Weapon") or []) == []


def test_expeditious_exit_queues_at_enemy_fight_phase_end_and_enters_strategic_reserves():
    game, p1, p2, army_gk, army_enemy = _build_game()
    target = _make_unit(
        "Purifier Squad",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["GREY KNIGHTS"],
        abilities=[_deep_strike_ability()],
    )
    enemy = _make_unit(
        "Enemy Fighters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_gk.add_unit(target)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, target, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, p2, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
    pending = _pending_by_name(p1.stratagems, "EXPEDITIOUS EXIT")
    assert pending is not None

    ok = p1.stratagems.use(
        "EXPEDITIOUS EXIT",
        unit=target,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok
    assert str(getattr(target, "reserve_status", "") or "") == "strategic_reserves"
    assert target not in list(getattr(game.map, "units", []) or [])


def test_combat_manifestation_sets_override_blocks_charge_and_cleans_up():
    game, p1, _p2, army_gk, army_enemy = _build_game()
    strike = _make_unit(
        "Strike Squad",
        keywords=["INFANTRY"],
        faction_keywords=["GREY KNIGHTS"],
        abilities=[_deep_strike_ability()],
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army_gk.add_unit(strike)
    army_enemy.add_unit(enemy)
    _deploy_unit(game, enemy, 14.0, 10.0)

    strike.deployed = False
    strike.reserve_status = "reserves"

    _set_phase(game, p1, "MOVEMENT_PHASE", 0)
    ok = p1.stratagems.use("COMBAT MANIFESTATION", unit=strike, phase_name="Movement phase")
    assert ok
    assert int(p1.command_points or 0) == 5
    assert float(strike.get_deep_strike_min_distance_override() or 0.0) == 6.0

    strike.deployed = True
    strike.reserve_status = "deployed"
    strike.arrived_from_reserves_this_turn = True
    strike.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    if strike not in list(getattr(game.map, "units", []) or []):
        game.map.place_unit(strike)
    assert not strike.can_declare_charge_against(enemy, game)

    game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    assert "combat_manifestation_deep_strike_min_distance" not in strike.special_rules
