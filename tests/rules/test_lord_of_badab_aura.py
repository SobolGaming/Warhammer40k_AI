from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Chaos Space Marines"}
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
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"


def _make_unit(name: str, *, keywords=None, faction_keywords=None, abilities=None):
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
        )
    )


def test_lord_of_badab_aura_adds_oc_for_eligible_units_only():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army = Army("CSM", "Renegade Raiders")
    army.faction_id = "CSM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.LOCAL, army=army)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    aura = {
        "name": "Lord of Badab (Aura)",
        "description": (
            'While a friendly Heretic Astartes Infantry unit (excluding Battle-shocked units and Damned units) '
            'is within 6" of this model, add 1 to the Objective Control characteristic of models in that unit.'
        ),
        "type": "Datasheet",
        "parameter": "",
    }

    source = _make_unit(
        "Huron Blackheart",
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["HERETIC ASTARTES"],
        abilities=[aura],
    )
    eligible = _make_unit(
        "Legionaries",
        keywords=["INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    battle_shocked = _make_unit(
        "Chosen",
        keywords=["INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    damned = _make_unit(
        "Accursed Cultists",
        keywords=["INFANTRY", "DAMNED"],
        faction_keywords=["HERETIC ASTARTES"],
    )

    army.add_unit(source)
    army.add_unit(eligible)
    army.add_unit(battle_shocked)
    army.add_unit(damned)
    game.map.units = [source, eligible, battle_shocked, damned]

    battle_shocked.status_effects = [BattleShockEffect()]

    with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
        assert int(eligible.objective_control or 0) == 2
        assert int(battle_shocked.objective_control or 0) == 1
        assert int(damned.objective_control or 0) == 1
