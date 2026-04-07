import pytest

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper import WahaHelper


pytestmark = pytest.mark.slow

_WAHA = WahaHelper(data_dir="wahapedia_data")


class _DummyPlayer:
    def __init__(self, name: str = "P1"):
        self.name = name
        self.game = None


def _make_unit(name: str, datasheet_id: str) -> Unit:
    datasheet = _WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="TS")
    assert datasheet is not None
    return Unit(datasheet)


def _wire_same_army(*units: Unit) -> Army:
    army = Army.with_detachment(faction="Thousand Sons", detachment_type="Grand Coven", points_limit=2000)
    army.player = _DummyPlayer()
    army.units = list(units)
    for unit in units:
        unit.parent_army = army
    return army


def test_exalted_sorcerer_on_disc_can_lead_enlightened_with_fatecaster_greatbows():
    leader = _make_unit("Exalted Sorcerer on Disc of Tzeentch", "000002755")
    bodyguard = _make_unit("Tzaangor Enlightened with Fatecaster Greatbows", "000004122")
    _wire_same_army(leader, bodyguard)

    assert bodyguard.get_datasheet_id() in set(getattr(leader, "can_be_attached_to", []) or [])
    assert leader.can_attach_to(bodyguard)
    leader.attach_to_unit(bodyguard)
    assert leader.attached_to is bodyguard
    assert leader in list(getattr(bodyguard, "attached_leaders", []) or [])


def test_tzaangor_shaman_can_lead_enlightened_with_fatecaster_greatbows():
    leader = _make_unit("Tzaangor Shaman", "000001472")
    bodyguard = _make_unit("Tzaangor Enlightened with Fatecaster Greatbows", "000004122")
    _wire_same_army(leader, bodyguard)

    assert bodyguard.get_datasheet_id() in set(getattr(leader, "can_be_attached_to", []) or [])
    assert leader.can_attach_to(bodyguard)
    leader.attach_to_unit(bodyguard)
    assert leader.attached_to is bodyguard
    assert leader in list(getattr(bodyguard, "attached_leaders", []) or [])
