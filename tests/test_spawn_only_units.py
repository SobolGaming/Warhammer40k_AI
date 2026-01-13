import pytest


def _spawn_only_unit(spawned=False):
    from warhammer40k_ai.classes.unit import Unit

    unit = Unit.__new__(Unit)
    unit.name = "Sir Hekhtur"
    unit.special_rules = {"spawn_only": True}
    unit.spawned_in_battle = bool(spawned)
    return unit


def test_spawn_only_unit_blocked_in_muster():
    from warhammer40k_ai.classes.army import Army, ArmyValidationError

    army = Army("Imperial Knights", detachment_type="Some Detachment")
    army.units = [_spawn_only_unit(spawned=False)]

    with pytest.raises(ArmyValidationError):
        army.validate_spawn_only_units()


def test_spawn_only_unit_allowed_when_spawned():
    from warhammer40k_ai.classes.army import Army

    army = Army("Imperial Knights", detachment_type="Some Detachment")
    army.units = [_spawn_only_unit(spawned=True)]

    army.validate_spawn_only_units()
