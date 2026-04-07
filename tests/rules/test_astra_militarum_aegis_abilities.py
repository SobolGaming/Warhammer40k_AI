from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.pathing.api import PathQuery, plan_model_path
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.calcs import MovementType


AEGIS_REINFORCED_COVER_TEXT = (
    "Each time a ranged attack is allocated to a model, if that model is not fully visible to every model in the "
    "attacking unit because of this FORTIFICATION, that model has the Benefit of Cover against that attack."
)
AEGIS_DEFENCE_LINE_TEXT = (
    "While an ASTRA MILITARUM INFANTRY model has the Benefit of Cover as a result of this terrain feature "
    "(see above), that model has a 4+ invulnerable save."
)
AEGIS_EMPLACEMENT_PLATFORM_TEXT = (
    "Friendly ASTRA MILITARUM INFANTRY models can be set up or end any type of move on top of the platform section "
    "of this FORTIFICATION."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        faction_name: str = "Astra Militarum",
        base_size: str = "32mm",
        abilities=None,
        keywords=None,
        faction_keywords=None,
        movement: str = "6",
        save: str = "4",
        wounds: str = "2",
        inv_sv: str = "7",
    ):
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": movement,
                "T": "4",
                "Sv": save,
                "W": wounds,
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": inv_sv,
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
    datasheet_id: str,
    base_size: str = "32mm",
    abilities=None,
    keywords=None,
    faction_keywords=None,
    faction_name: str = "Astra Militarum",
    save: str = "4",
    wounds: str = "2",
    inv_sv: str = "7",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            base_size=base_size,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            save=save,
            wounds=wounds,
            inv_sv=inv_sv,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _attach_armies(game_map: Map, friendly_units: list[Unit], enemy_units: list[Unit]) -> tuple[Army, Army]:
    friendly_army = Army.with_detachment("Astra Militarum", "Combined Regiment")
    enemy_army = Army.with_detachment("Enemy", "Other")
    for unit in friendly_units:
        friendly_army.add_unit(unit)
    for unit in enemy_units:
        enemy_army.add_unit(unit)
    game = SimpleNamespace(map=game_map)
    friendly_army.player = SimpleNamespace(game=game, id="P1", name="P1")
    enemy_army.player = SimpleNamespace(game=game, id="P2", name="P2")
    game_map.units = list(friendly_units) + list(enemy_units)
    return friendly_army, enemy_army


def _aegis_abilities() -> list[dict]:
    return [
        {"name": "Emplacement Platform", "description": AEGIS_EMPLACEMENT_PLATFORM_TEXT, "type": "Datasheet", "parameter": ""},
        {"name": "Reinforced Cover", "description": AEGIS_REINFORCED_COVER_TEXT, "type": "Datasheet", "parameter": ""},
        {"name": "Defence Line", "description": AEGIS_DEFENCE_LINE_TEXT, "type": "Datasheet", "parameter": ""},
    ]


def test_aegis_defence_line_grants_four_plus_invulnerable_save(monkeypatch):
    import warhammer40k_ai.units.wargear as wargear_mod

    monkeypatch.setattr(wargear_mod, "get_roll", lambda _expr: 4)

    game_map = Map(width=48, height=72)
    attacker = _make_unit(
        "Enemy Squad",
        datasheet_id="enemy-1",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        save="4",
    )
    aegis = _make_unit(
        "Aegis Defence Line",
        datasheet_id="000002619",
        base_size="Hull",
        abilities=_aegis_abilities(),
        keywords=["FORTIFICATION"],
        faction_keywords=["ASTRA MILITARUM"],
        save="2",
        wounds="10",
    )
    target = _make_unit(
        "Shock Troops",
        datasheet_id="am-infantry-1",
        keywords=["INFANTRY"],
        faction_keywords=["ASTRA MILITARUM"],
        save="4",
    )
    _attach_armies(game_map, [aegis, target], [attacker])

    attacker.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    aegis.models[0].set_location(20.0, 10.0, 0.0, 0.0)
    target.models[0].set_location(30.0, 10.0, 0.0, 0.0)

    profile = WargearProfile(
        "Battle Cannon",
        {"range": "24", "A": "1", "BS_WS": "3", "S": "8", "AP": "3", "D": "2", "description": ""},
    )
    attack_instance = {"mortal_wound": False, "attacker_unit": attacker}
    save_result = profile._save_with_tracking(
        target.models[0],
        attack_instance,
        ap=-3,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert int(attack_instance.get("inv_save_override", 0) or 0) == 4
    assert "Defence Line" in str(attack_instance.get("inv_save_override_reason", ""))
    assert save_result.get("save_type") == "invulnerable"
    assert save_result.get("saved") is True


def test_aegis_emplacement_platform_sets_surface_height_and_allows_pathing():
    game_map = Map(width=48, height=72)
    aegis = _make_unit(
        "Aegis Defence Line",
        datasheet_id="000002619",
        base_size="Hull",
        abilities=_aegis_abilities(),
        keywords=["FORTIFICATION"],
        faction_keywords=["ASTRA MILITARUM"],
        save="2",
        wounds="10",
    )
    infantry = _make_unit(
        "Shock Troops",
        datasheet_id="am-infantry-2",
        keywords=["INFANTRY"],
        faction_keywords=["ASTRA MILITARUM"],
    )
    _attach_armies(game_map, [aegis, infantry], [])

    aegis.models[0].set_location(20.0, 20.0, 0.0, 0.0)
    infantry.models[0].set_location(12.0, 20.0, 0.0, 0.0)

    target_z = game_map.get_surface_height_for_model(infantry.models[0], 20.0, 20.0)
    assert target_z > 0.0

    path_result = plan_model_path(
        PathQuery(
            model=infantry.models[0],
            target=(20.0, 20.0, target_z),
            movement_type=MovementType.MOVE,
            max_distance=12.0,
            game_map=game_map,
        )
    )

    assert path_result.valid is True
    assert path_result.poses
    assert abs(float(path_result.poses[-1].z) - float(target_z)) < 1e-4


def test_aegis_emplacement_platform_rejects_non_infantry_top_surface():
    game_map = Map(width=48, height=72)
    aegis = _make_unit(
        "Aegis Defence Line",
        datasheet_id="000002619",
        base_size="Hull",
        abilities=_aegis_abilities(),
        keywords=["FORTIFICATION"],
        faction_keywords=["ASTRA MILITARUM"],
        save="2",
        wounds="10",
    )
    tank = _make_unit(
        "Leman Russ",
        datasheet_id="am-vehicle-1",
        base_size="Hull",
        keywords=["VEHICLE"],
        faction_keywords=["ASTRA MILITARUM"],
        save="2",
        wounds="13",
    )
    _attach_armies(game_map, [aegis, tank], [])

    aegis.models[0].set_location(20.0, 20.0, 0.0, 0.0)
    tank.models[0].set_location(5.0, 5.0, 0.0, 0.0)

    platform_top = float(aegis.models[0].model_base.model_height)
    validation = game_map.validate_model_surface_placement(tank.models[0], (20.0, 20.0, platform_top))

    assert validation.get("valid") is False
    assert "ASTRA MILITARUM INFANTRY" in str(validation.get("reason", ""))
