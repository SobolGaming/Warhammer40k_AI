from __future__ import annotations

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        wounds: str = "2",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
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
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    wounds: str = "2",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _place(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    target_army = Army("Enemy", "Other")
    target_army.faction_id = "EN"
    dread_talons_army = Army("Chaos Space Marines", "Dread Talons")
    dread_talons_army.faction_id = "CSM"
    target_player = Player("Target", control=PlayerControl.REMOTE, army=target_army)
    dread_talons_player = Player("DreadTalons", control=PlayerControl.REMOTE, army=dread_talons_army)
    game.add_player(target_player)
    game.add_player(dread_talons_player)
    game.current_player_index = 0
    return game, target_player, dread_talons_player, target_army, dread_talons_army


def test_terror_descends_source_units_filter_to_eligible_heretic_astartes():
    _game, _target_player, _dt_player, _target_army, dread_talons_army = _build_game()
    source_ok = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    source_not_heretic_astartes = _make_unit(
        "Cultists",
        keywords=["DAMNED", "INFANTRY"],
        faction_keywords=["DAMNED"],
    )
    source_in_reserves = _make_unit(
        "Raptors",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    source_in_reserves.reserve_status = "reserves"
    source_embarked = _make_unit(
        "Chosen",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    source_embarked.embarked_in = object()

    dread_talons_army.add_unit(source_ok)
    dread_talons_army.add_unit(source_not_heretic_astartes)
    dread_talons_army.add_unit(source_in_reserves)
    dread_talons_army.add_unit(source_embarked)

    mgr = dread_talons_army.chaos_space_marines_detachments
    sources = list(mgr.terror_descends_source_units() or [])
    assert sources == [source_ok]


def test_terror_descends_marks_already_tested_targets_to_suppress_other_tests():
    game, target_player, _dt_player, target_army, dread_talons_army = _build_game()
    source = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    target = _make_unit(
        "Target Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    target.models[0].wounds = 1
    _place(source, 10.0, 10.0)
    _place(target, 14.0, 10.0)
    dread_talons_army.add_unit(source)
    target_army.add_unit(target)
    game.map.units = [source, target]
    game.rebuild_entity_registry()

    calls = []
    original_take = target.take_battle_shock_test

    def _counting_take(*args, **kwargs):
        calls.append((args, kwargs))
        return original_take(*args, **kwargs)

    target.take_battle_shock_test = _counting_take
    tested_ids = {str(get_entity_id(target) or "")}
    Game._apply_csm_dread_talons_terror_descends_forced_tests(game, target_player, tested_ids)

    assert calls == []
    sr = dict(getattr(target, "special_rules", {}) or {})
    assert sr.get("battle_shock_suppress_other_tests_phase") == "COMMAND_PHASE"
    assert sr.get("battle_shock_suppress_other_tests_source") == "Terror Descends"
    assert "battle_shock_allow_suppressed_test" not in sr


def test_terror_descends_forces_test_when_target_is_eligible_and_in_range():
    game, target_player, _dt_player, target_army, dread_talons_army = _build_game()
    source = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    target = _make_unit(
        "Target Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    target.models[0].wounds = 1
    _place(source, 10.0, 10.0)
    _place(target, 14.0, 10.0)
    dread_talons_army.add_unit(source)
    target_army.add_unit(target)
    game.map.units = [source, target]
    game.rebuild_entity_registry()

    calls = []
    original_take = target.take_battle_shock_test

    def _counting_take(*args, **kwargs):
        calls.append((args, kwargs))
        return original_take(*args, **kwargs)

    target.take_battle_shock_test = _counting_take
    tested_ids: set[str] = set()
    Game._apply_csm_dread_talons_terror_descends_forced_tests(game, target_player, tested_ids)

    assert len(calls) == 1
    assert str(get_entity_id(target) or "") in tested_ids
    sr = dict(getattr(target, "special_rules", {}) or {})
    assert sr.get("battle_shock_suppress_other_tests_phase") == "COMMAND_PHASE"
    assert sr.get("battle_shock_suppress_other_tests_source") == "Terror Descends"
