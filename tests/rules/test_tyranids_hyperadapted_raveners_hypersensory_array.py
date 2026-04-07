from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagems import StratagemManager
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit


_HYPERSENSORY_ARRAY_DESCRIPTION = (
    "Once per battle round, you can target this unit with the Rapid Ingress or Heroic Intervention Stratagem for 0CP, "
    "and can do so even if you have already targeted a different unit with that Stratagem this turn."
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
                "T": "5",
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": "2",
                "base_size": "40mm",
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


def test_hypersensory_array_zero_cp_once_per_battle_round_armywide():
    game, tyr_army, _enemy_army, tyr_player, _enemy_player = _build_game()
    unit_a = _make_unit("Hyperadapted Raveners A", keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
    unit_b = _make_unit("Hyperadapted Raveners B", keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
    ability = Ability("Hypersensory Array", "TYR", _HYPERSENSORY_ARRAY_DESCRIPTION, "Datasheet", "")
    unit_a.possible_abilities = [ability]
    unit_b.possible_abilities = [ability]
    tyr_army.add_unit(unit_a)
    tyr_army.add_unit(unit_b)
    _set_deployed(unit_a, deployed=False, in_reserves=True)
    _set_deployed(unit_b, deployed=False, in_reserves=True)
    game.turn = 1

    strat = SimpleNamespace(name="Rapid Ingress", cp_cost=1)
    first_preview = tyr_player.preview_stratagem_cp_cost(
        strat,
        target_unit=unit_a,
        assume_optional_discounts=True,
    )
    assert int(first_preview.get("cost", -1)) == 0
    assert any("Hypersensory Array" in str(r) for r in list(first_preview.get("reasons", []) or []))

    tyr_player.set_next_optional_decision("HYPERSENSORY_ARRAY_STRATAGEM_DISCOUNT", True)
    first_applied = tyr_player.apply_stratagem_cp_cost(strat, target_unit=unit_a)
    assert int(first_applied.get("cost", -1)) == 0
    assert bool(first_applied.get("hypersensory_array_use", False))

    second_same_round = tyr_player.preview_stratagem_cp_cost(
        strat,
        target_unit=unit_b,
        assume_optional_discounts=True,
    )
    assert int(second_same_round.get("cost", -1)) == 1

    game.turn = 2
    next_round = tyr_player.preview_stratagem_cp_cost(
        strat,
        target_unit=unit_b,
        assume_optional_discounts=True,
    )
    assert int(next_round.get("cost", -1)) == 0


def test_hypersensory_array_repeat_bypass_helpers_for_heroic_and_rapid_ingress():
    game, tyr_army, _enemy_army, tyr_player, _enemy_player = _build_game()
    hypersensory_unit = _make_unit("Hyperadapted Raveners", keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
    other_unit = _make_unit("Other Unit", keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
    hypersensory_unit.possible_abilities = [
        Ability("Hypersensory Array", "TYR", _HYPERSENSORY_ARRAY_DESCRIPTION, "Datasheet", "")
    ]
    tyr_army.add_unit(hypersensory_unit)
    tyr_army.add_unit(other_unit)
    _set_deployed(hypersensory_unit, deployed=True, in_reserves=False)
    _set_deployed(other_unit, deployed=True, in_reserves=False)
    game.turn = 1

    manager = StratagemManager(tyr_player)
    manager._used_stratagems_this_phase.add("HEROIC INTERVENTION")
    manager._record_heroic_intervention_use(other_unit)
    assert bool(manager._heroic_intervention_repeat_allowed(target_unit=hypersensory_unit))
    assert not bool(manager._heroic_intervention_repeat_allowed(target_unit=other_unit))

    _set_deployed(hypersensory_unit, deployed=False, in_reserves=True)
    _set_deployed(other_unit, deployed=False, in_reserves=True)
    manager._used_stratagems_this_phase.add("RAPID INGRESS")
    manager._record_rapid_ingress_use(other_unit)
    assert bool(manager._rapid_ingress_repeat_allowed(target_unit=hypersensory_unit))
    assert not bool(manager._rapid_ingress_repeat_allowed(target_unit=other_unit))
