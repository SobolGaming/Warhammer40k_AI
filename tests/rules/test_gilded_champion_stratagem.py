from __future__ import annotations

from dataclasses import dataclass

from warhammer40k_ai.engine.decision_kinds import DECISION_USE_GILDED_CHAMPION
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, BattleRoundPhases, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


@dataclass
class _MockDatasheet:
    name: str
    keywords: list[str]
    faction_keywords: list[str]

    def __post_init__(self) -> None:
        self.faction_data = {"name": "Adeptus Custodes" if "ADEPTUS CUSTODES" in [k.upper() for k in self.keywords] else "Enemy"}
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
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


def _build_game(*, authoritative: bool) -> tuple[Game, Player, Unit]:
    custodes_army = Army("Adeptus Custodes", "Lions of the Emperor")
    enemy_army = Army("Orks", "Other")

    custodes_player = Player("Custodes", PlayerControl.LOCAL, army=custodes_army)
    enemy_player = Player("Enemy", PlayerControl.LOCAL, army=enemy_army)
    custodes_army.set_player(custodes_player)
    enemy_army.set_player(enemy_player)

    custodes_unit = Unit(
        _MockDatasheet(
            name="Shield-Captain",
            keywords=["Character", "Adeptus Custodes", "Infantry"],
            faction_keywords=["Adeptus Custodes"],
        )
    )
    custodes_unit.faction_id = "AC"
    custodes_unit.deployed = True
    custodes_army.add_unit(custodes_unit)

    enemy_unit = Unit(
        _MockDatasheet(
            name="Enemy",
            keywords=["Infantry"],
            faction_keywords=["Enemy"],
        )
    )
    enemy_unit.deployed = True
    enemy_army.add_unit(enemy_unit)

    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[custodes_player, enemy_player])
    game.is_authoritative = authoritative
    game.current_player_index = 0
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.setup_complete = True
    custodes_player.command_points = 3
    enemy_player.command_points = 3
    custodes_army.configure_rule_managers(force=True)
    custodes_player.stratagems.refresh_available()
    game.rebuild_entity_registry()

    assert custodes_player.stratagems.get_by_name("GILDED CHAMPION") is not None
    return game, custodes_player, custodes_unit


def _use_option_id(request) -> str:
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("action", "")) == "use":
            return opt.option_id
    raise AssertionError("No 'use' option found for Gilded Champion.")


def test_gilded_champion_local_prompt_and_phase_restriction():
    game, player, unit = _build_game(authoritative=True)
    model = unit.models[0]

    assert model.mark_used_once_per_battle("test_once", ability_name="Test Once", source="datasheet")
    decisions = [req for req in game.decision_queue.list() if req.decision_type == DECISION_USE_GILDED_CHAMPION]
    assert len(decisions) == 1
    request = decisions[0]

    resolve_decision_command(game, request, _use_option_id(request), player_id=player.id)
    assert player.command_points == 2
    # Extra use exists, but cannot be used again in the same phase.
    assert model.has_used_once_per_battle("test_once", phase_name="FIGHT_PHASE")
    # In a different phase, the extra use becomes available.
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    assert not model.has_used_once_per_battle("test_once", phase_name="SHOOTING_PHASE")
    assert model.mark_used_once_per_battle("test_once", ability_name="Test Once", source="datasheet")
    assert model.has_used_once_per_battle("test_once", phase_name="SHOOTING_PHASE")


def test_gilded_champion_remote_decision_and_once_per_model():
    game, player, unit = _build_game(authoritative=False)
    model = unit.models[0]

    assert model.mark_used_once_per_battle("test_once", ability_name="Test Once", source="datasheet")
    decisions = [req for req in game.decision_queue.list() if req.decision_type == DECISION_USE_GILDED_CHAMPION]
    assert len(decisions) == 1
    request = decisions[0]

    resolve_decision_command(game, request, _use_option_id(request), player_id=player.id)
    assert player.command_points == 2

    # The stratagem cannot be used on the same model again.
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    assert model.mark_used_once_per_battle("test_once", ability_name="Test Once", source="datasheet")
    new_decisions = [req for req in game.decision_queue.list() if req.decision_type == DECISION_USE_GILDED_CHAMPION]
    assert not new_decisions
