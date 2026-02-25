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
                "M": "8",
                "T": "4",
                "Sv": "5",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "5",
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

    legion_army = Army("Chaos Daemons", "Legion of Excess")
    legion_army.faction_id = "CD"
    legion_army.detachment_type = "Legion of Excess"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    legion_player = Player("P1", control=PlayerControl.LOCAL, army=legion_army)
    enemy_player = Player("P2", control=PlayerControl.LOCAL, army=enemy_army)

    game.add_player(legion_player)
    game.add_player(enemy_player)

    legion_player.command_points = 5
    enemy_player.command_points = 5
    return game, legion_player, enemy_player, legion_army, enemy_army


def test_legion_of_excess_step1_stratagem_descriptors_registered():
    phantasmal = get_stratagem_tool_descriptor(stratagem_id="000009807005")
    assert phantasmal is not None
    assert phantasmal.name == "Phantasmal Longing"
    assert phantasmal.effect == "move_through_terrain"
    assert int(phantasmal.cp_cost) == 1

    cavalry = get_stratagem_tool_descriptor(stratagem_id="000009807006")
    assert cavalry is not None
    assert cavalry.name == "Cavalcade of Blades"
    assert cavalry.effect == "engagement_mortal_wound_burst"
    assert int(cavalry.cp_cost) == 1

    by_name_phantasmal = get_stratagem_tool_descriptor(name="PHANTASMAL LONGING")
    assert by_name_phantasmal is not None
    assert str(by_name_phantasmal.stratagem_id) == "000009807005"

    by_name_cavalcade = get_stratagem_tool_descriptor(name="CAVALCADE OF BLADES")
    assert by_name_cavalcade is not None
    assert str(by_name_cavalcade.stratagem_id) == "000009807006"


def test_phantasmal_longing_applies_movement_phase_move_types_and_cleans_up():
    game, legion_player, enemy_player, legion_army, enemy_army = _build_game()
    legion_unit = _make_unit(
        "Daemonettes",
        keywords=["SLAANESH", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Unit")
    legion_army.add_unit(legion_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([legion_unit, enemy_unit])
    _deploy_unit(legion_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 9.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=legion_player, phase=BattleRoundPhases.MOVEMENT_PHASE)

    strat_name = _find_stratagem_name(legion_player, "PHANTASMAL LONGING")
    ok = legion_player.stratagems.use(
        strat_name,
        unit=legion_unit,
        phase_name="Movement phase",
    )
    assert ok is True
    assert legion_player.command_points == 4

    rules = dict(getattr(legion_unit, "special_rules", {}) or {})
    assert bool(rules.get("legion_of_excess_phantasmal_longing_active", False)) is True
    assert set(rules.get("bearer_unit_phase_move_terrain_only_types", [])) >= {"move", "advance", "fall_back"}

    game.event_system.publish("phase_end", player=legion_player, phase=BattleRoundPhases.MOVEMENT_PHASE)
    rules = dict(getattr(legion_unit, "special_rules", {}) or {})
    assert "legion_of_excess_phantasmal_longing_active" not in rules
    assert "legion_of_excess_phantasmal_longing_expires_phase" not in rules
    assert "bearer_unit_phase_move_terrain_only_types" not in rules


def test_phantasmal_longing_applies_charge_move_type_and_cleans_up():
    game, legion_player, enemy_player, legion_army, enemy_army = _build_game()
    legion_unit = _make_unit(
        "Seekers",
        keywords=["SLAANESH", "MOUNTED"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Unit")
    legion_army.add_unit(legion_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([legion_unit, enemy_unit])
    _deploy_unit(legion_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 8.0, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=legion_player, phase=BattleRoundPhases.CHARGE_PHASE)

    strat_name = _find_stratagem_name(legion_player, "PHANTASMAL LONGING")
    ok = legion_player.stratagems.use(
        strat_name,
        unit=legion_unit,
        phase_name="Charge phase",
    )
    assert ok is True
    assert legion_player.command_points == 4

    rules = dict(getattr(legion_unit, "special_rules", {}) or {})
    assert bool(rules.get("legion_of_excess_phantasmal_longing_active", False)) is True
    assert set(rules.get("bearer_unit_phase_move_terrain_only_types", [])) >= {"charge"}

    game.event_system.publish("phase_end", player=legion_player, phase=BattleRoundPhases.CHARGE_PHASE)
    rules = dict(getattr(legion_unit, "special_rules", {}) or {})
    assert "legion_of_excess_phantasmal_longing_active" not in rules
    assert "legion_of_excess_phantasmal_longing_expires_phase" not in rules
    assert "bearer_unit_phase_move_terrain_only_types" not in rules


def test_cavalcade_of_blades_queues_on_charge_end_and_applies_mortal_wounds(monkeypatch):
    game, legion_player, enemy_player, legion_army, enemy_army = _build_game()
    legion_unit = _make_unit(
        "Daemonettes",
        keywords=["SLAANESH", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy_unit = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    legion_army.add_unit(legion_unit)
    enemy_army.add_unit(enemy_unit)
    game.map.units.extend([legion_unit, enemy_unit])
    _deploy_unit(legion_unit, 0.0, 0.0)
    _deploy_unit(enemy_unit, 0.5, 0.0)

    game.turn = 2
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game.current_player_index = 0
    game.event_system.publish("phase_start", player=legion_player, phase=BattleRoundPhases.CHARGE_PHASE)

    game.event_system.publish("unit_move_ended", unit=legion_unit, action="charge")
    pending = legion_player.stratagems.get_pending_reactions()
    reactions = [
        reaction
        for reaction in list(pending or [])
        if _normalize_name(str(reaction.get("stratagem", "") or "")) == "CAVALCADE OF BLADES"
    ]
    assert len(reactions) == 1
    assert legion_unit in list(reactions[0].get("candidates", []) or [])
    assert enemy_unit in list(reactions[0].get("enemy_candidates", []) or [])

    monkeypatch.setattr("warhammer40k_ai.rules.stratagems_chaos_daemons.dice_module.get_roll", lambda _expr: 4)
    applied = {}

    def _fake_apply_mortal_wounds(target_unit, amount, game_map=None):
        applied["target"] = target_unit
        applied["amount"] = int(amount)

    monkeypatch.setattr(legion_unit, "_apply_mortal_wounds_to_unit", _fake_apply_mortal_wounds)

    strat_name = _find_stratagem_name(legion_player, "CAVALCADE OF BLADES")
    ok = legion_player.stratagems.use(
        strat_name,
        unit=legion_unit,
        enemy_unit=enemy_unit,
        phase_name="Charge phase",
        dequeue=True,
    )
    assert ok is True
    assert legion_player.command_points == 4
    assert applied == {"target": enemy_unit, "amount": 1}

