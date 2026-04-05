from types import SimpleNamespace

from warhammer40k_ai.units.unit import Unit


class _DatasheetStub:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        transport_text: str = "",
    ):
        self.name = name
        self.id = datasheet_id
        self.faction_data = {"name": "Adeptus Astartes"}
        self.keywords = list(keywords or ["Infantry"])
        self.faction_keywords = list(faction_keywords or ["ADEPTUS ASTARTES", "IMPERIUM"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "2+",
                "W": "6",
                "Ld": "6+",
                "OC": "1",
                "base_size": "40mm",
                "inv_sv": "4+",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = transport_text
        self.attached_to = []
        self.attached_to_names = []
        self.damaged_w = ""
        self.damaged_description = ""


def _mk_logan_grimnar() -> Unit:
    ability = {
        "name": "EMBARKING WITHIN TRANSPORTS",
        "description": (
            "This model can embark within friendly Adeptus Astartes Transport models that can transport "
            "Terminator models. When doing so, it takes up the space of 4 Infantry models."
        ),
        "type": "Datasheet",
        "parameter": "",
    }
    return Unit(
        _DatasheetStub(
            "Logan Grimnar",
            datasheet_id="LG1",
            keywords=["Character", "Infantry", "Terminator", "Adeptus Astartes"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES", "IMPERIUM"],
            abilities=[ability],
        )
    )


def _mk_transport(name: str, *, datasheet_id: str, transport_text: str) -> Unit:
    return Unit(
        _DatasheetStub(
            name,
            datasheet_id=datasheet_id,
            keywords=["Vehicle", "Transport", "Adeptus Astartes"],
            faction_keywords=["ADEPTUS ASTARTES", "IMPERIUM"],
            transport_text=transport_text,
        )
    )


def _set_same_army(*units: Unit) -> None:
    army = SimpleNamespace(chaos_space_marines_detachments=None)
    for unit in units:
        unit.parent_army = army


def test_logan_grimnar_embarking_within_transports_counts_as_four_slots():
    logan = _mk_logan_grimnar()
    assert logan.get_transport_slots_required() == 4
    assert logan.get_transport_slot_cost_for_model(logan.models[0]) == 4


def test_logan_grimnar_embarking_within_transports_applies_to_transport_capacity_checks():
    logan = _mk_logan_grimnar()
    small_transport = _mk_transport(
        "Small Astartes Transport",
        datasheet_id="TR1",
        transport_text=(
            "This model has a transport capacity of 3 Adeptus Astartes Infantry models. "
            "Each Terminator model takes up the space of 2 models."
        ),
    )
    exact_transport = _mk_transport(
        "Exact Astartes Transport",
        datasheet_id="TR2",
        transport_text=(
            "This model has a transport capacity of 4 Adeptus Astartes Infantry models. "
            "Each Terminator model takes up the space of 2 models."
        ),
    )
    _set_same_army(logan, small_transport, exact_transport)

    assert small_transport.can_transport(logan) is False
    assert exact_transport.can_transport(logan) is True


def test_logan_grimnar_embarking_within_transports_requires_terminator_capable_transport():
    logan = _mk_logan_grimnar()
    land_raider = _mk_transport(
        "Land Raider",
        datasheet_id="TR3",
        transport_text=(
            "This model has a transport capacity of 12 Adeptus Astartes Infantry models. "
            "Each Jump Pack, Wulfen, Gravis or Terminator model takes up the space of 2 models and "
            "each Centurion model takes up the space of 3 models."
        ),
    )
    rhino = _mk_transport(
        "Rhino",
        datasheet_id="TR4",
        transport_text=(
            "This model has a transport capacity of 12 ADEPTUS ASTARTES INFANTRY models. "
            "It cannot transport JUMP PACK, WULFEN, PHOBOS, GRAVIS, CENTURION, TERMINATOR or TACTICUS models."
        ),
    )
    _set_same_army(logan, land_raider, rhino)

    assert land_raider.can_transport(logan) is True
    assert rhino.can_transport(logan) is False
