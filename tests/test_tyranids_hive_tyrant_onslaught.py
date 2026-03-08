from __future__ import annotations

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


_ONSLAUGHT_AURA_DESCRIPTION = (
    "While a friendly TYRANIDS unit is within 6\" of this model, ranged weapons equipped by models in that unit "
    "have the [ASSAULT] and [LETHAL HITS] abilities."
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
                "Sv": "3",
                "W": "4",
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


def _add_basic_ranged_weapon(unit: Unit, name: str = "Devourer"):
    weapon = Wargear(
        {
            "name": name,
            "type": "Ranged",
            "range": "18",
            "A": "2",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    unit.models[0].wargear = [weapon]
    profile = list(getattr(weapon, "profiles", {}).values())[0]
    return profile


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army("Tyranids", "Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    tyr_player = Player("Tyr", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    return game, tyr_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if not game.map.place_unit(unit):
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def test_onslaught_aura_grants_ranged_assault_and_lethal_hits_within_6():
    game, tyr_army, enemy_army = _build_game()
    hive_tyrant = _make_unit("Hive Tyrant", keywords=["MONSTER"], faction_keywords=["TYRANIDS"])
    hive_tyrant.possible_abilities = [
        Ability("Onslaught (Aura, Psychic)", "TYR", _ONSLAUGHT_AURA_DESCRIPTION, "Datasheet", "")
    ]
    shooter = _make_unit("Termagants", keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    tyr_army.add_unit(hive_tyrant)
    tyr_army.add_unit(shooter)
    enemy_army.add_unit(enemy)

    _deploy_unit(game, hive_tyrant, 10.0, 10.0)
    _deploy_unit(game, shooter, 14.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 30.0)
    game.rebuild_entity_registry()

    profile = _add_basic_ranged_weapon(shooter)
    bonuses = shooter.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=shooter.models[0],
        weapon_profile=profile,
        target=enemy,
    )
    assert bool(bonuses.get("assault", False)) is True
    assert bool(bonuses.get("lethal_hits", False)) is True


def test_onslaught_aura_requires_range_for_bonuses_and_advance_shoot():
    game, tyr_army, enemy_army = _build_game()
    hive_tyrant = _make_unit("Hive Tyrant", keywords=["MONSTER"], faction_keywords=["TYRANIDS"])
    hive_tyrant.possible_abilities = [
        Ability("Onslaught (Aura, Psychic)", "TYR", _ONSLAUGHT_AURA_DESCRIPTION, "Datasheet", "")
    ]
    shooter = _make_unit("Termagants", keywords=["INFANTRY"], faction_keywords=["TYRANIDS"])
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    tyr_army.add_unit(hive_tyrant)
    tyr_army.add_unit(shooter)
    enemy_army.add_unit(enemy)

    _deploy_unit(game, hive_tyrant, 10.0, 10.0)
    _deploy_unit(game, shooter, 25.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 30.0)
    game.rebuild_entity_registry()

    profile = _add_basic_ranged_weapon(shooter)
    assert profile.is_assault() is False

    bonuses = shooter.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=shooter.models[0],
        weapon_profile=profile,
        target=enemy,
    )
    assert bool(bonuses.get("assault", False)) is False
    assert bool(bonuses.get("lethal_hits", False)) is False
    assert shooter.can_shoot_after_advance(profile) is False
