from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


EXECUTIONER_OF_HERETICS_TEXT = (
    'While an enemy unit is within 6" of this model, '
    "worsen the Leadership characteristic of models in that unit by 1."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        model_count: int = 1,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        leadership: int = 7,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Adepta Sororitas"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model(s)", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "3",
                "Sv": "3",
                "W": "3",
                "Ld": str(int(leadership)),
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
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    leadership: int = 7,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            leadership=leadership,
        ),
        quantity=1,
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    as_army = Army("Adepta Sororitas", detachment_type="Hallowed Martyrs")
    as_army.faction_id = "AS"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    as_player = Player("AS", PlayerControl.REMOTE, army=as_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(as_player)
    game.add_player(enemy_player)
    return game, as_army, enemy_army


def test_executioner_of_heretics_worsens_enemy_leadership_within_six_inches():
    game, as_army, enemy_army = _build_game()
    dogmata = _make_unit(
        "Dogmata",
        abilities=[
            {
                "name": "Executioner of Heretics (Aura)",
                "description": EXECUTIONER_OF_HERETICS_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["INFANTRY", "CHARACTER"],
        faction_keywords=["ADEPTA SORORITAS"],
    )
    in_range_target = _make_unit(
        "Enemy In Range",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        leadership=7,
    )
    out_of_range_target = _make_unit(
        "Enemy Out Of Range",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        leadership=7,
    )

    as_army.add_unit(dogmata)
    enemy_army.add_unit(in_range_target)
    enemy_army.add_unit(out_of_range_target)

    dogmata.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    in_range_target.models[0].set_location(4.0, 0.0, 0.0, 0.0)
    out_of_range_target.models[0].set_location(12.0, 0.0, 0.0, 0.0)

    game.map.units = [dogmata, in_range_target, out_of_range_target]
    game.rebuild_entity_registry()

    assert int(in_range_target.leadership) == 8
    assert int(out_of_range_target.leadership) == 7
