from __future__ import annotations

import pytest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities: list[dict] | None = None,
        attached_to: list[str] | None = None,
        wounds: str = "2",
    ) -> None:
        self.id = f"ds-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = ["TEST"]
        self.attached_to = list(attached_to or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(wounds),
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


def _ability(name: str, description: str | None = None, parameter: str = "") -> dict:
    return {
        "name": name,
        "description": description if description is not None else name,
        "type": "Core",
        "parameter": parameter,
    }


def _make_unit(
    name: str,
    *,
    abilities: list[dict] | None = None,
    attached_to: list[str] | None = None,
    wounds: str = "2",
) -> Unit:
    return Unit(_MockDatasheet(name, abilities=abilities, attached_to=attached_to, wounds=wounds))


def _make_headless_game() -> tuple[Game, Player, Player]:
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE))
    player = Player("Headless Player", PlayerControl.REMOTE, Army.with_detachment("Test Faction", "Test Detachment"))
    opponent = Player("Headless Opponent", PlayerControl.REMOTE, Army.with_detachment("Enemy Faction", "Enemy Detachment"))
    game.add_player(player)
    game.add_player(opponent)
    return game, player, opponent


def _install_rolls(monkeypatch: pytest.MonkeyPatch, rolls: list[int]) -> None:
    import warhammer40k_ai.units.unit as unit_module

    values = iter(rolls)

    def rigged_roll(_expr: str) -> int:
        return next(values)

    monkeypatch.setattr(unit_module, "get_roll", rigged_roll)


def test_core_ability_runtime_hooks_available_to_headless_army() -> None:
    game, player, _opponent = _make_headless_game()
    assert player.has_control() is False

    unit = _make_unit(
        "Core Ability Carrier",
        abilities=[
            _ability("Deadly Demise", "Deadly Demise D3", "D3"),
            _ability("Deep Strike"),
            _ability("Feel No Pain", "Feel No Pain 5+", "5+"),
            _ability("Fights First"),
            _ability("Firing Deck", "Firing Deck 2", "2"),
            _ability("Hover"),
            _ability("Infiltrators"),
            _ability("Lone Operative", "This model has the Lone Operative ability."),
            _ability("Scouts", 'Scouts 6"', "6"),
            _ability("Stealth"),
        ],
    )
    player.army.add_unit(unit)
    game.map.units = [unit]

    has_deadly_demise, deadly_demise_damage = unit.has_deadly_demise()
    assert has_deadly_demise is True
    assert str(deadly_demise_damage) == "1D3"
    assert unit.has_deep_strike() is True
    assert unit.has_feel_no_pain() == [(5, None)]
    assert unit.has_fight_first() is True
    assert unit.has_firing_deck() == (True, 2)
    assert unit.has_hover() is True
    assert unit.has_infiltrate() is True
    assert unit.has_lone_operative() is True
    assert unit.has_scout() == (True, 6.0)
    assert unit.has_stealth() is True

    leader = _make_unit(
        "Core Leader",
        abilities=[_ability("Leader")],
        attached_to=["Core Bodyguard"],
    )
    player.army.add_unit(leader)
    assert leader.is_leader is True
    assert leader.can_be_attached_to == ["Core Bodyguard"]


def test_deadly_demise_accepts_fixed_numeric_damage_parameter() -> None:
    unit = _make_unit(
        "Fixed Explosion Carrier",
        abilities=[_ability("Deadly Demise", "Deadly Demise 1", "1")],
    )

    has_deadly_demise, deadly_demise_damage = unit.has_deadly_demise()

    assert has_deadly_demise is True
    assert str(deadly_demise_damage) == "1"
    assert deadly_demise_damage.min() == 1
    assert deadly_demise_damage.max() == 1
    assert deadly_demise_damage.roll() == 1


@pytest.mark.parametrize(
    ("trigger_roll", "expected_explosion"),
    [
        (6, True),
        (5, False),
    ],
)
def test_deadly_demise_rolls_on_model_death_during_headless_play(
    monkeypatch: pytest.MonkeyPatch,
    trigger_roll: int,
    expected_explosion: bool,
) -> None:
    _install_rolls(monkeypatch, [trigger_roll])
    game, player, _opponent = _make_headless_game()
    unit = _make_unit(
        "Exploding Core Ability Carrier",
        abilities=[_ability("Deadly Demise", "Deadly Demise D3", "D3")],
        wounds="1",
    )
    model = unit.models[0]
    model.set_location(10.0, 10.0, 0.0, 0.0)
    player.army.add_unit(unit)
    game.map.units = [unit]

    explosions: list[dict] = []

    def record_explosion(**kwargs) -> None:
        explosions.append(dict(kwargs))

    monkeypatch.setattr(unit, "_apply_deadly_demise_explosion", record_explosion)

    unit.remove_model(model, game_map=game.map)

    assert bool(explosions) is expected_explosion
    if expected_explosion:
        assert str(explosions[0]["damage_dice"]) == "1D3"
        assert explosions[0]["position"] == (10.0, 10.0, 0.0, 0.0)
        assert explosions[0]["game_map"] is game.map
    assert list(game.decision_queue.list()) == []
    assert unit.models == []
