from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagems import StratagemManager
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit


_POUNCING_LEAP_DESCRIPTION = (
    "You can target this unit with the Heroic Intervention Stratagem for 0CP, and can do so even if "
    "you have already used that Stratagem on a different unit this phase."
)


class _MockDatasheet:
    def __init__(self, name: str, *, faction_name="Tyranids", keywords=None, faction_keywords=None):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "4",
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
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


def _make_unit(name: str, *, faction_name="Tyranids", keywords=None, faction_keywords=None) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army.with_detachment("Tyranids", "Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    tyr_player = Player("Tyr", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    return game, tyr_army, enemy_army, tyr_player, enemy_player


def _set_deployed(unit: Unit, *, deployed: bool, in_reserves: bool) -> None:
    unit.deployed = bool(deployed)
    unit.reserve_status = "reserves" if in_reserves else "deployed"
    unit.embarked_in = None


def test_pouncing_leap_heroic_intervention_discount_is_available():
    game, tyr_army, _enemy_army, tyr_player, _enemy_player = _build_game()
    leapers = _make_unit("Von Ryan's Leapers", keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
    leapers.possible_abilities = [
        Ability("Pouncing Leap", "TYR", _POUNCING_LEAP_DESCRIPTION, "Datasheet", "")
    ]
    tyr_army.add_unit(leapers)
    _set_deployed(leapers, deployed=True, in_reserves=False)
    game.turn = 1

    rule = leapers.get_snarling_protector_heroic_intervention_rule()
    assert isinstance(rule, dict)

    tyr_player.stratagems = SimpleNamespace(_used_this_turn={})
    strat = SimpleNamespace(name="Heroic Intervention", cp_cost=1)
    tyr_player.set_next_optional_decision("SNARLING_PROTECTOR_HEROIC_INTERVENTION", True)
    applied = tyr_player.apply_stratagem_cp_cost(strat, target_unit=leapers)
    assert int(applied.get("cost", -1)) == 0
    assert bool(applied.get("snarling_protector_heroic_intervention_use", False))


def test_pouncing_leap_allows_heroic_intervention_repeat_bypass():
    game, tyr_army, _enemy_army, tyr_player, _enemy_player = _build_game()
    leapers = _make_unit("Von Ryan's Leapers", keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
    other = _make_unit("Other Unit", keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
    leapers.possible_abilities = [
        Ability("Pouncing Leap", "TYR", _POUNCING_LEAP_DESCRIPTION, "Datasheet", "")
    ]
    tyr_army.add_unit(leapers)
    tyr_army.add_unit(other)
    _set_deployed(leapers, deployed=True, in_reserves=False)
    _set_deployed(other, deployed=True, in_reserves=False)
    game.turn = 1

    manager = StratagemManager(tyr_player)
    manager._used_stratagems_this_phase.add("HEROIC INTERVENTION")
    manager._record_heroic_intervention_use(other)
    assert bool(manager._heroic_intervention_repeat_allowed(target_unit=leapers))
    assert not bool(manager._heroic_intervention_repeat_allowed(target_unit=other))
