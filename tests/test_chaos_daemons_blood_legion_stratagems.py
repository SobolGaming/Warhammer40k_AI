from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
    ) -> None:
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _normalize_name(name: str) -> str:
    text = str(name or "")
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    return text.strip().upper()


def _find_stratagem_name(player: Player, canonical_name: str) -> str:
    target = _normalize_name(canonical_name)
    for stratagem in list(player.stratagems.available or []):
        name = str(getattr(stratagem, "name", "") or "")
        if _normalize_name(name) == target:
            return name
    raise AssertionError(f"Missing stratagem '{canonical_name}' in available list.")


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
) -> Unit:
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


def _deploy_unit(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _build_game():
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    daemon_army = Army("Chaos Daemons", "Blood Legion")
    daemon_army.faction_id = "CD"
    daemon_army.detachment_type = "Blood Legion"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    daemon_player = Player("P1", control=PlayerControl.LOCAL, army=daemon_army)
    enemy_player = Player("P2", control=PlayerControl.LOCAL, army=enemy_army)

    game.add_player(daemon_player)
    game.add_player(enemy_player)

    daemon_player.command_points = 5
    enemy_player.command_points = 5
    return game, daemon_player, enemy_player, daemon_army, enemy_army


def test_blood_legion_step1_stratagem_descriptors_registered():
    gore = get_stratagem_tool_descriptor(stratagem_id="000009816003")
    assert gore is not None
    assert gore.name == "Gore-Hungry Onslaught"
    assert gore.effect == "move_through_terrain"
    assert int(gore.cp_cost) == 1

    fools = get_stratagem_tool_descriptor(stratagem_id="000009816006")
    assert fools is not None
    assert fools.name == "Fools' Flight"
    assert fools.effect == "out_of_turn_charge_without_charge_bonus"
    assert int(fools.cp_cost) == 2

    by_name = get_stratagem_tool_descriptor(name="GORE-HUNGRY ONSLAUGHT")
    assert by_name is not None
    assert str(by_name.stratagem_id) == "000009816003"

    by_name_fools = get_stratagem_tool_descriptor(name="FOOLS' FLIGHT")
    assert by_name_fools is not None
    assert str(by_name_fools.stratagem_id) == "000009816006"


def test_gore_hungry_onslaught_applies_movement_phase_move_types_and_cleans_up():
    game, daemon_player, enemy_player, daemon_army, enemy_army = _build_game()
    daemon_unit = _make_unit(
        "Bloodletters",
        keywords=["KHORNE"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Unit")
    daemon_army.add_unit(daemon_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([daemon_unit, enemy_unit])
    _deploy_unit(daemon_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 9.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=daemon_player, phase=BattleRoundPhases.MOVEMENT_PHASE)

    gore_name = _find_stratagem_name(daemon_player, "GORE-HUNGRY ONSLAUGHT")
    ok = daemon_player.stratagems.use(
        gore_name,
        unit=daemon_unit,
        phase_name="Movement phase",
    )
    assert ok is True
    assert daemon_player.command_points == 4

    rules = dict(getattr(daemon_unit, "special_rules", {}) or {})
    assert bool(rules.get("blood_legion_gore_hungry_onslaught_active", False)) is True
    assert set(rules.get("bearer_unit_phase_move_terrain_only_types", [])) >= {"move", "advance", "fall_back"}

    game.event_system.publish("phase_end", player=daemon_player, phase=BattleRoundPhases.MOVEMENT_PHASE)
    rules = dict(getattr(daemon_unit, "special_rules", {}) or {})
    assert "blood_legion_gore_hungry_onslaught_active" not in rules
    assert "blood_legion_gore_hungry_onslaught_expires_phase" not in rules
    assert "bearer_unit_phase_move_terrain_only_types" not in rules


def test_gore_hungry_onslaught_applies_charge_move_type_and_cleans_up():
    game, daemon_player, enemy_player, daemon_army, enemy_army = _build_game()
    daemon_unit = _make_unit(
        "Bloodcrushers",
        keywords=["KHORNE", "MOUNTED"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Unit")
    daemon_army.add_unit(daemon_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([daemon_unit, enemy_unit])
    _deploy_unit(daemon_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 8.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=daemon_player, phase=BattleRoundPhases.CHARGE_PHASE)

    gore_name = _find_stratagem_name(daemon_player, "GORE-HUNGRY ONSLAUGHT")
    ok = daemon_player.stratagems.use(
        gore_name,
        unit=daemon_unit,
        phase_name="Charge phase",
    )
    assert ok is True
    assert daemon_player.command_points == 4

    rules = dict(getattr(daemon_unit, "special_rules", {}) or {})
    assert bool(rules.get("blood_legion_gore_hungry_onslaught_active", False)) is True
    assert set(rules.get("bearer_unit_phase_move_terrain_only_types", [])) >= {"charge"}

    game.event_system.publish("phase_end", player=daemon_player, phase=BattleRoundPhases.CHARGE_PHASE)
    rules = dict(getattr(daemon_unit, "special_rules", {}) or {})
    assert "blood_legion_gore_hungry_onslaught_active" not in rules
    assert "blood_legion_gore_hungry_onslaught_expires_phase" not in rules
    assert "bearer_unit_phase_move_terrain_only_types" not in rules


def test_fools_flight_queues_on_enemy_fall_back_and_uses_out_of_turn_charge(monkeypatch):
    game, daemon_player, enemy_player, daemon_army, enemy_army = _build_game()
    daemon_unit = _make_unit(
        "Flesh Hounds",
        keywords=["KHORNE", "BEAST"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    daemon_army.add_unit(daemon_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([daemon_unit, enemy_unit])
    _deploy_unit(daemon_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 5.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 1
    game.event_system.publish("phase_start", player=enemy_player, phase=BattleRoundPhases.MOVEMENT_PHASE)

    game.event_system.publish("unit_move_ended", unit=enemy_unit, action="fall_back")
    pending = daemon_player.stratagems.get_pending_reactions()
    fools_reactions = [
        reaction
        for reaction in list(pending or [])
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == "FOOLS' FLIGHT"
    ]
    assert len(fools_reactions) == 1
    assert daemon_unit in list(fools_reactions[0].get("candidates", []) or [])

    called = {}

    def _fake_attempt_charge(unit, target, *, out_of_turn=False, count_as_charged=True):
        called["unit"] = unit
        called["target"] = target
        called["out_of_turn"] = bool(out_of_turn)
        called["count_as_charged"] = bool(count_as_charged)
        return True

    monkeypatch.setattr(game, "attempt_charge", _fake_attempt_charge)

    fools_name = _find_stratagem_name(daemon_player, "FOOLS' FLIGHT")
    ok = daemon_player.stratagems.use(
        fools_name,
        unit=daemon_unit,
        enemy_unit=enemy_unit,
        phase_name="Movement phase",
        dequeue=True,
    )
    assert ok is True
    assert daemon_player.command_points == 3
    assert called == {
        "unit": daemon_unit,
        "target": enemy_unit,
        "out_of_turn": True,
        "count_as_charged": False,
    }

