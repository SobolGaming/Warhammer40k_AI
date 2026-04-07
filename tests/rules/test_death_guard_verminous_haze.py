from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
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
                "M": "5",
                "T": "5",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "2",
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
    faction_name: str,
    keywords=None,
    faction_keywords=None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )


def _build_game(detachment: str):
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)
    dg_army = Army.with_detachment("Death Guard", detachment)
    dg_army.faction_id = "DG"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    dg_player = Player("DG", control=PlayerControl.LOCAL, army=dg_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(dg_player)
    game.add_player(enemy_player)
    return game, dg_player, enemy_player


def test_verminous_haze_grants_stealth_and_scouts_to_eligible_infantry():
    _game, dg_player, _enemy_player = _build_game("Flyblown Host")
    unit = _make_unit(
        "Plague Marines",
        faction_name="Death Guard",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_player.army.add_unit(unit)

    has_scout, scout_distance = unit.has_scout()
    assert has_scout is True
    assert scout_distance == 5.0
    assert unit.has_stealth() is True


def test_verminous_haze_excludes_poxwalkers():
    _game, dg_player, _enemy_player = _build_game("Flyblown Host")
    unit = _make_unit(
        "Poxwalkers",
        faction_name="Death Guard",
        keywords=["INFANTRY", "POXWALKERS"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_player.army.add_unit(unit)

    assert unit.has_scout() == (False, 0.0)
    assert unit.has_stealth() is False


def test_verminous_haze_excludes_embarked_units():
    _game, dg_player, _enemy_player = _build_game("Flyblown Host")
    unit = _make_unit(
        "Plague Marines",
        faction_name="Death Guard",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_player.army.add_unit(unit)

    assert unit.has_scout() == (True, 5.0)
    assert unit.has_stealth() is True

    unit.embarked_in = object()

    assert unit.has_scout() == (False, 0.0)
    assert unit.has_stealth() is False


def test_verminous_haze_excludes_non_infantry_units():
    _game, dg_player, _enemy_player = _build_game("Flyblown Host")
    unit = _make_unit(
        "Plagueburst Crawler",
        faction_name="Death Guard",
        keywords=["VEHICLE"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_player.army.add_unit(unit)

    assert unit.has_scout() == (False, 0.0)
    assert unit.has_stealth() is False


def test_verminous_haze_not_active_outside_flyblown_host():
    _game, dg_player, _enemy_player = _build_game("Virulent Vectorium")
    unit = _make_unit(
        "Plague Marines",
        faction_name="Death Guard",
        keywords=["INFANTRY"],
        faction_keywords=["DEATH GUARD"],
    )
    dg_player.army.add_unit(unit)

    assert unit.has_scout() == (False, 0.0)
    assert unit.has_stealth() is False
