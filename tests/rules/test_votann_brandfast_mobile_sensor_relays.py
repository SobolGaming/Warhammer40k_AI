from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Leagues of Votann"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "5",
                "Sv": "3",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _build_army(detachment: str) -> Army:
    army = Army.with_detachment("Leagues of Votann", detachment)
    army.faction_id = "LOV"
    return army


def _make_profile(*, name: str, weapon_type: str):
    weapon = Wargear(
        {
            "name": name,
            "type": weapon_type,
            "range": "24" if str(weapon_type).strip().lower() == "ranged" else "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def test_mobile_sensor_relays_grants_sustained_hits_to_infantry_wholly_within_transport():
    army = _build_army("Brandfast Oathband")
    transport = _make_unit(
        "Sagitaur",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["LEAGUES OF VOTANN"],
    )
    infantry = _make_unit(
        "Hearthkyn Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["LEAGUES OF VOTANN"],
    )
    _set_unit_position(transport, 10.0, 10.0)
    _set_unit_position(infantry, 15.0, 10.0)
    army.add_unit(transport)
    army.add_unit(infantry)

    bonus = infantry.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=infantry.models[0],
        weapon_profile=_make_profile(name="EtaCarn plasma beamer", weapon_type="Ranged"),
        weapon_name="EtaCarn plasma beamer",
    )

    assert int(bonus.get("sustained_hits_value", 0) or 0) == 1


def test_mobile_sensor_relays_requires_wholly_within_six_of_transport():
    army = _build_army("Brandfast Oathband")
    transport = _make_unit(
        "Sagitaur",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["LEAGUES OF VOTANN"],
    )
    infantry = _make_unit(
        "Hearthkyn Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["LEAGUES OF VOTANN"],
    )
    _set_unit_position(transport, 10.0, 10.0)
    _set_unit_position(infantry, 18.0, 10.0)
    army.add_unit(transport)
    army.add_unit(infantry)

    bonus = infantry.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=infantry.models[0],
        weapon_profile=_make_profile(name="EtaCarn plasma beamer", weapon_type="Ranged"),
        weapon_name="EtaCarn plasma beamer",
    )

    assert int(bonus.get("sustained_hits_value", 0) or 0) == 0


def test_mobile_sensor_relays_requires_brandfast_oathband():
    army = _build_army("Hearthband")
    transport = _make_unit(
        "Sagitaur",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["LEAGUES OF VOTANN"],
    )
    infantry = _make_unit(
        "Hearthkyn Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["LEAGUES OF VOTANN"],
    )
    _set_unit_position(transport, 10.0, 10.0)
    _set_unit_position(infantry, 15.0, 10.0)
    army.add_unit(transport)
    army.add_unit(infantry)

    bonus = infantry.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=infantry.models[0],
        weapon_profile=_make_profile(name="EtaCarn plasma beamer", weapon_type="Ranged"),
        weapon_name="EtaCarn plasma beamer",
    )

    assert int(bonus.get("sustained_hits_value", 0) or 0) == 0


def test_mobile_sensor_relays_applies_only_to_infantry_units():
    army = _build_army("Brandfast Oathband")
    source_transport = _make_unit(
        "Sagitaur",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["LEAGUES OF VOTANN"],
    )
    shooting_vehicle = _make_unit(
        "Hekaton Land Fortress",
        keywords=["VEHICLE"],
        faction_keywords=["LEAGUES OF VOTANN"],
    )
    _set_unit_position(source_transport, 10.0, 10.0)
    _set_unit_position(shooting_vehicle, 15.0, 10.0)
    army.add_unit(source_transport)
    army.add_unit(shooting_vehicle)

    bonus = shooting_vehicle.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=shooting_vehicle.models[0],
        weapon_profile=_make_profile(name="Heavy magna-rail cannon", weapon_type="Ranged"),
        weapon_name="Heavy magna-rail cannon",
    )

    assert int(bonus.get("sustained_hits_value", 0) or 0) == 0
