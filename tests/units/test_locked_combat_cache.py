from types import SimpleNamespace

from warhammer40k_ai.units.unit import Unit


def test_unit_locked_in_combat_reuses_engagement_result_until_map_generation_changes() -> None:
    unit = SimpleNamespace(id="unit:target")
    enemy = SimpleNamespace(id="unit:enemy", is_alive=lambda: True)

    class CountedMap:
        state_generation = 3

        def __init__(self) -> None:
            self.engagement_checks = 0
            self.locked = True

        def get_enemy_units(self, _unit):
            return [enemy]

        def is_within_engagement_range(self, _unit, _enemy):
            self.engagement_checks += 1
            return self.locked

    game_map = CountedMap()

    assert Unit._is_unit_locked_in_combat(unit, game_map) is True
    assert Unit._is_unit_locked_in_combat(unit, game_map) is True
    assert game_map.engagement_checks == 1

    game_map.locked = False
    assert Unit._is_unit_locked_in_combat(unit, game_map) is True
    assert game_map.engagement_checks == 1

    game_map.state_generation += 1
    assert Unit._is_unit_locked_in_combat(unit, game_map) is False
    assert game_map.engagement_checks == 2

