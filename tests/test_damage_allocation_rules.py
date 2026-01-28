import unittest


class _Unit:
    def __init__(self, *, is_character: bool = False):
        self.is_character = is_character
        self.name = "U"


class _Model:
    def __init__(self, name: str, wounds: int, base_wounds: int, *, is_character: bool = False):
        self.name = name
        self.wounds = wounds
        self._base_wounds = base_wounds
        self.parent_unit = _Unit(is_character=is_character)

    @property
    def is_alive(self) -> bool:
        return self.wounds > 0

    @property
    def is_max_health(self) -> bool:
        return self.wounds == self._base_wounds


class TestDamageAllocationRules(unittest.TestCase):
    def test_damage_allocation_must_stick_to_wounded(self):
        from warhammer40k_ai.utility.damage_allocation import choose_damage_allocation_model

        wounded = _Model("wounded", wounds=1, base_wounds=2)
        fresh = _Model("fresh", wounds=2, base_wounds=2)

        chosen = choose_damage_allocation_model(
            target_unit=object(),
            candidates=[fresh, wounded],
        )
        self.assertIs(chosen, wounded)

    def test_damage_allocation_human_can_choose_when_no_wounded(self):
        from warhammer40k_ai.utility.damage_allocation import choose_damage_allocation_model

        a = _Model("a", wounds=2, base_wounds=2)
        b = _Model("b", wounds=2, base_wounds=2)

        chosen = choose_damage_allocation_model(
            target_unit=object(),
            candidates=[a, b],
        )
        self.assertIs(chosen, a)

    def test_hazardous_priority_wounded_first(self):
        from warhammer40k_ai.utility.damage_allocation import choose_hazardous_failure_model

        wounded = _Model("wounded", wounds=1, base_wounds=2, is_character=False)
        fresh_nonchar = _Model("fresh_nonchar", wounds=2, base_wounds=2, is_character=False)
        fresh_char = _Model("fresh_char", wounds=2, base_wounds=2, is_character=True)

        chosen = choose_hazardous_failure_model(
            attacker_unit_root=object(),
            eligible_models=[fresh_char, fresh_nonchar, wounded],
        )
        self.assertIs(chosen, wounded)

    def test_hazardous_priority_non_character_when_no_wounded(self):
        from warhammer40k_ai.utility.damage_allocation import choose_hazardous_failure_model

        fresh_nonchar = _Model("fresh_nonchar", wounds=2, base_wounds=2, is_character=False)
        fresh_char = _Model("fresh_char", wounds=2, base_wounds=2, is_character=True)

        chosen = choose_hazardous_failure_model(
            attacker_unit_root=object(),
            eligible_models=[fresh_char, fresh_nonchar],
        )
        self.assertIs(chosen, fresh_nonchar)

