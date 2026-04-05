from __future__ import annotations

from dataclasses import dataclass, field

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, BattleRoundPhases, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.utility.unit_split import split_unit_into_single_model_units


@dataclass
class _MockDatasheet:
    name: str
    keywords: list[str]
    faction_keywords: list[str]
    attached_to: list[str] = field(default_factory=list)
    attached_to_names: list[str] = field(default_factory=list)
    id: str = "mock"

    def __post_init__(self) -> None:
        self.faction_data = {"name": "Adeptus Custodes" if "ADEPTUS CUSTODES" in [k.upper() for k in self.keywords] else "Enemy"}
        self.datasheets_unit_composition = [{"description": "1-3 Test Models"}]
        self.datasheets_models_cost = [{"description": "1-3 models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "2",
                "W": "5",
                "Ld": "6",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "4",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _build_game() -> tuple[Game, Player, Army]:
    custodes_army = Army("Adeptus Custodes", "Lions of the Emperor")
    enemy_army = Army("Orks", "Other")

    custodes_player = Player("Custodes", PlayerControl.LOCAL, army=custodes_army)
    enemy_player = Player("Enemy", PlayerControl.LOCAL, army=enemy_army)
    custodes_army.set_player(custodes_player)
    enemy_army.set_player(enemy_player)

    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[custodes_player, enemy_player])
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.setup_complete = True

    custodes_player.command_points = 3
    custodes_army.configure_rule_managers(force=True)
    custodes_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, custodes_player, custodes_army


def test_unleash_the_lions_splits_bodyguard_unit_and_carries_state():
    game, player, army = _build_game()

    unit = Unit(
        _MockDatasheet(
            name="Allarus Custodians",
            keywords=["Adeptus Custodes", "Infantry"],
            faction_keywords=["Adeptus Custodes"],
        ),
        quantity=2,
    )
    unit.faction_id = "AC"
    unit.deployed = True
    army.add_unit(unit)

    # Tag persistent state that should carry over.
    sr = dict(unit.special_rules or {})
    sr["test_expires_phase"] = "COMMAND_PHASE"
    sr["test_active"] = True
    unit.special_rules = sr

    original_models = list(unit.models)
    ok = player.stratagems.use("UNLEASH THE LIONS", unit=unit, phase_name="Command phase")
    assert ok
    assert player.command_points == 2
    assert unit not in army.units

    new_units = [u for u in army.units if getattr(u, "name", "") == "Allarus Custodians"]
    assert len(new_units) == 2
    for new_unit in new_units:
        assert len(new_unit.models) == 1
        assert new_unit.models[0] in original_models
        assert new_unit.starting_model_count == 1
        assert new_unit.starting_total_wounds == new_unit.models[0]._base_wounds
        assert new_unit.special_rules.get("test_expires_phase") == "COMMAND_PHASE"
        assert new_unit.special_rules.get("test_active") is True


def test_unleash_the_lions_detaches_leader_models():
    game, player, army = _build_game()

    bodyguard = Unit(
        _MockDatasheet(
            name="Aquilon Custodians",
            keywords=["Adeptus Custodes", "Infantry"],
            faction_keywords=["Adeptus Custodes"],
        ),
        quantity=1,
    )
    bodyguard.faction_id = "AC"
    bodyguard.deployed = True
    army.add_unit(bodyguard)

    leader = Unit(
        _MockDatasheet(
            name="Shield-Captain",
            keywords=["Adeptus Custodes", "Infantry", "Character"],
            faction_keywords=["Adeptus Custodes"],
            attached_to=["mock_bodyguard"],
        ),
        quantity=1,
    )
    leader.faction_id = "AC"
    leader.deployed = True
    army.add_unit(leader)

    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]

    ok = player.stratagems.use("UNLEASH THE LIONS", unit=bodyguard, phase_name="Command phase")
    assert ok
    assert player.command_points == 2

    assert leader.attached_to is None
    assert bodyguard not in army.units
    assert leader in army.units
    assert leader.starting_model_count == 1
    assert len(leader.models) == 1
    aquilon_units = [u for u in army.units if getattr(u, "name", "") == "Aquilon Custodians"]
    assert len(aquilon_units) == 1
    assert len(aquilon_units[0].models) == 1


def test_split_helper_copies_battleshock_effect():
    game, _player, army = _build_game()

    unit = Unit(
        _MockDatasheet(
            name="Allarus Custodians",
            keywords=["Adeptus Custodes", "Infantry"],
            faction_keywords=["Adeptus Custodes"],
        ),
        quantity=2,
    )
    unit.faction_id = "AC"
    unit.deployed = True
    army.add_unit(unit)
    unit.apply_status_effect(BattleShockEffect(current_turn=1))

    new_units = split_unit_into_single_model_units(unit, game=game)
    assert len(new_units) == 2
    for new_unit in new_units:
        assert new_unit.is_battle_shocked()
