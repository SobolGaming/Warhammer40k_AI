from __future__ import annotations

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
    ) -> None:
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "4",
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
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _mock_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    return game, sm_army, enemy_army


def _deploy(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def test_librarian_in_phobos_armour_shrouding_grants_stealth_and_targeting_cap_while_leading():
    game, sm_army, enemy_army = _build_game()

    librarian = _actual_unit("Librarian In Phobos Armour", datasheet_id="000000119")
    bodyguard = _mock_unit(
        "Phobos Bodyguard",
        keywords=["ADEPTUS ASTARTES", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _mock_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    sm_army.add_unit(librarian)
    sm_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _deploy(librarian, 0.0, 0.0)
    _deploy(bodyguard, 0.0, 1.0)
    _deploy(enemy, 18.0, 0.0)
    game.map.units = [librarian, bodyguard, enemy]
    game.rebuild_entity_registry()

    assert bodyguard.has_stealth() is False
    dist_before, _sources_before = bodyguard.get_ranged_targeting_restriction(game_map=game.map)
    assert dist_before is None

    librarian.attached_to = bodyguard
    bodyguard.attached_leaders = [librarian]
    bodyguard._ability_cache = {}
    librarian._ability_cache = {}

    assert bodyguard.has_stealth() is True
    dist_after, sources_after = bodyguard.get_ranged_targeting_restriction(game_map=game.map)
    assert float(dist_after or 0.0) == 12.0
    assert any("Shrouding" in str(source or "") for source in list(sources_after or []))
