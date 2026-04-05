import pytest

from warhammer40k_ai.units.unit import Unit


class _DaemonPrinceDatasheet:
    def __init__(self):
        self.name = "Daemon Prince of Chaos"
        self.faction_data = {"name": "Chaos Daemons"}
        self.keywords = ["Monster", "Character"]
        self.faction_keywords = ["LEGIONES DAEMONICA"]
        self.datasheets_unit_composition = [{"description": "1 Daemon Prince"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 200}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "7",
                "Sv": "3",
                "W": "10",
                "Ld": "7",
                "OC": "3",
                "base_size": "90mm",
                "inv_sv": "5",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = [
            {
                "name": "Hellforged weapons - strike",
                "type": "Melee",
                "range": "Melee",
                "A": "4",
                "BS_WS": "3+",
                "S": "4",
                "AP": "-2",
                "D": "2",
                "description": "",
            },
            {
                "name": "Hellforged weapons - sweep",
                "type": "Melee",
                "range": "Melee",
                "A": "8",
                "BS_WS": "3+",
                "S": "4",
                "AP": "-1",
                "D": "1",
                "description": "",
            },
            {
                "name": "Infernal cannon",
                "type": "Ranged",
                "range": "24",
                "A": "2",
                "BS_WS": "3+",
                "S": "6",
                "AP": "-1",
                "D": "1",
                "description": "",
            },
        ]
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [
            {
                "name": "DAEMONIC ALLEGIANCE",
                "description": (
                    "When you select this model to include in your army, you must select one of the following "
                    "keywords for it to gain: KHORNE TZEENTCH NURGLE SLAANESH. "
                    "The keyword you select will also affect some of this model's characteristics, as stated overleaf."
                ),
                "type": "Datasheet",
                "parameter": "",
            },
            {
                "name": "Daemon Prince of Khorne",
                "description": (
                    "If this model has the KHORNE keyword, add 2 to the Strength characteristic of this model's "
                    "hellforged weapons."
                ),
                "type": "Datasheet",
                "parameter": "",
            },
            {
                "name": "Daemon Prince of Tzeentch",
                "description": (
                    "If this model has the TZEENTCH keyword, add 3 to the Attacks characteristic of this model's "
                    "infernal cannon."
                ),
                "type": "Datasheet",
                "parameter": "",
            },
            {
                "name": "Daemon Prince of Nurgle",
                "description": "If this model has the NURGLE keyword, add 1 to this model's Toughness characteristic.",
                "type": "Datasheet",
                "parameter": "",
            },
            {
                "name": "Daemon Prince of Slaanesh",
                "description": "If this model has the SLAANESH keyword, add 2\" to this model's Move characteristic.",
                "type": "Datasheet",
                "parameter": "",
            },
        ]
        self.loadout = "This model is equipped with: hellforged weapons; infernal cannon."
        self.transport = ""


class _TargetDatasheet:
    def __init__(self):
        self.name = "Target"
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Target"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
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
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""


def _make_daemon_prince_unit() -> Unit:
    return Unit(_DaemonPrinceDatasheet())


def _make_target_unit() -> Unit:
    return Unit(_TargetDatasheet())


def test_daemonic_allegiance_keyword_only_options():
    unit = _make_daemon_prince_unit()
    options = unit.get_daemonic_allegiance_options()
    assert options == [
        ("KHORNE", ""),
        ("TZEENTCH", ""),
        ("NURGLE", ""),
        ("SLAANESH", ""),
    ]


def test_daemon_prince_khorne_strength_bonus():
    unit = _make_daemon_prince_unit()
    unit.daemonic_allegiance = "KHORNE"
    assert unit.apply_daemonic_allegiance_selection() is True

    model = unit.models[0]
    hellforged = next(wg for wg in model.wargear if wg.name == "Hellforged weapons")
    profile = next(iter(hellforged.profiles.values()))
    target = _make_target_unit()
    attack_instance = {}
    wound_result = profile._wound_target_with_tracking(
        target,
        model,
        attack_instance,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert wound_result["needed"] == 3


def test_daemon_prince_tzeentch_attacks_bonus():
    unit = _make_daemon_prince_unit()
    unit.daemonic_allegiance = "TZEENTCH"
    assert unit.apply_daemonic_allegiance_selection() is True

    model = unit.models[0]
    infernal = next(wg for wg in model.wargear if wg.name == "Infernal cannon")
    profile = next(iter(infernal.profiles.values()))
    target = _make_target_unit()
    info = profile.preview_attack_count(target, model, publish_roll_event=False)
    assert info.num_attacks == 5


@pytest.mark.parametrize(
    ("keyword", "expected_toughness", "expected_movement"),
    [
        ("NURGLE", 8, 8),
        ("SLAANESH", 7, 10),
    ],
)
def test_daemon_prince_characteristic_bonuses(keyword, expected_toughness, expected_movement):
    unit = _make_daemon_prince_unit()
    unit.daemonic_allegiance = keyword
    assert unit.apply_daemonic_allegiance_selection() is True

    model = unit.models[0]
    assert model.toughness == expected_toughness
    assert model.movement == expected_movement
