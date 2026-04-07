from __future__ import annotations

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        abilities=None,
        model_count: int = 1,
        wounds: int = 4,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
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
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    abilities=None,
    model_count: int = 1,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", "Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    return game, sm_player, enemy_player


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    bodyguard._ability_cache = {}
    leader._ability_cache = {}


def test_unbreakable_duty_applies_only_while_on_objective_or_near_battlefield_centre():
    game, player, _enemy = _build_game()
    ability = {
        "name": "Unbreakable Duty",
        "description": (
            "While this model is within range of an objective marker and/or within 6\" of the centre of the battlefield, "
            "this model has the Feel No Pain 4+ ability."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    ancient = _make_unit(
        "Ancient",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        abilities=[ability],
    )
    player.army.add_unit(ancient)
    _deploy_unit(game, ancient, 1.0, 1.0)

    model = ancient.models[0]
    ancient.is_within_any_objective_range = lambda game_map=None: False
    assert (4, None) not in list(ancient.has_feel_no_pain(target_model=model) or [])

    ancient.is_within_any_objective_range = lambda game_map=None: True
    assert (4, None) in list(ancient.has_feel_no_pain(target_model=model) or [])

    ancient.is_within_any_objective_range = lambda game_map=None: False
    centre_x = float(getattr(game.map, "width", 0.0) or 0.0) * 0.5
    centre_y = float(getattr(game.map, "height", 0.0) or 0.0) * 0.5
    model.set_location(centre_x, centre_y, 0.0, 0.0)
    assert (4, None) in list(ancient.has_feel_no_pain(target_model=model) or [])


def test_honour_guard_of_macragge_applies_only_to_marneus_calgar():
    ability = {
        "name": "Honour Guard of Macragge",
        "description": (
            "While this unit contains one or more Victrix Honour Guard models, this unit's MARNEUS CALGAR model has the "
            "Feel No Pain 4+ ability."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    supported = _make_unit(
        "Honour Guard",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        abilities=[ability],
        model_count=2,
    )
    supported.models[0].name = "Marneus Calgar"
    supported.models[1].name = "Victrix Honour Guard"
    supported._refresh_bearer_unit_common_modifiers()

    assert (4, None) in list(supported.has_feel_no_pain(target_model=supported.models[0]) or [])
    assert (4, None) not in list(supported.has_feel_no_pain(target_model=supported.models[1]) or [])

    unsupported = _make_unit(
        "Honour Guard Missing Victrix",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        abilities=[ability],
        model_count=2,
    )
    unsupported.models[0].name = "Marneus Calgar"
    unsupported.models[1].name = "Ultramarine Veteran"
    unsupported._refresh_bearer_unit_common_modifiers()

    assert (4, None) not in list(unsupported.has_feel_no_pain(target_model=unsupported.models[0]) or [])


def test_no_hiding_from_the_watchers_aura_applies_to_nearby_adeptus_astartes_units_only():
    game, player, _enemy = _build_game()
    ability = {
        "name": "No Hiding From the Watchers (Aura)",
        "description": (
            "While a friendly ADEPTUS ASTARTES unit is within 6\" of this model, models in that unit have the Feel No Pain "
            "4+ ability against mortal wounds."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    source = _make_unit(
        "Watcher Source",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        abilities=[ability],
    )
    nearby = _make_unit(
        "Nearby Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    distant = _make_unit(
        "Distant Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    non_astartes = _make_unit(
        "Allied Operative",
        faction_name="Agents",
        keywords=["INFANTRY"],
        faction_keywords=["AGENTS OF THE IMPERIUM"],
    )
    for unit in (source, nearby, distant, non_astartes):
        player.army.add_unit(unit)

    _deploy_unit(game, source, 10.0, 10.0)
    _deploy_unit(game, nearby, 14.0, 10.0)
    _deploy_unit(game, distant, 24.0, 10.0)
    _deploy_unit(game, non_astartes, 14.0, 12.0)

    assert (4, "against mortal wounds") in list(nearby.has_feel_no_pain(target_model=nearby.models[0]) or [])
    assert (4, "against mortal wounds") not in list(distant.has_feel_no_pain(target_model=distant.models[0]) or [])
    assert (4, "against mortal wounds") not in list(
        non_astartes.has_feel_no_pain(target_model=non_astartes.models[0]) or []
    )


def test_the_lion_helm_grants_passive_invulnerable_save_without_static_fnp():
    ability = {
        "name": "The Lion Helm",
        "description": (
            "Models in the bearer's unit have a 4+ invulnerable save. In addition, once per battle, in any phase, the "
            "bearer can summon a Watcher in the Dark. When it does, until the end of the phase, models in the bearer's "
            "unit have the Feel No Pain 4+ ability against mortal wounds."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    azrael = _make_unit(
        "Azrael",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        abilities=[ability],
    )
    companions = _make_unit(
        "Inner Circle Companions",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=2,
    )
    _attach_leader(companions, azrael)
    companions._refresh_bearer_unit_common_modifiers()

    invulnerable_save, _source = companions.get_model_invulnerable_save_override(companions.models[0])
    assert int(invulnerable_save or 0) == 4
    fnp_entries = list(companions.has_feel_no_pain(target_model=companions.models[0]) or [])
    assert not any(int(value) == 4 and "mortal" in str(condition or "").lower() for value, condition in fnp_entries)
