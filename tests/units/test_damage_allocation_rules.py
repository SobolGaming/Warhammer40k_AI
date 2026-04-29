import unittest
from types import SimpleNamespace


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


class _AllocModel:
    def __init__(self, model_id: str, name: str, parent_unit: "_AllocUnit" = None):
        self.id = model_id
        self._id = model_id
        self.name = name
        self.wounds = 2
        self._base_wounds = 2
        self.parent_unit = parent_unit

    @property
    def is_alive(self) -> bool:
        return self.wounds > 0

    @property
    def is_max_health(self) -> bool:
        return self.wounds == self._base_wounds


class _AllocUnit:
    def __init__(self, unit_id: str, army: object):
        self.id = unit_id
        self._id = unit_id
        self.name = unit_id
        self.parent_army = army
        self.models = [
            _AllocModel(f"{unit_id}:model-a", "Model A", self),
            _AllocModel(f"{unit_id}:model-b", "Model B", self),
        ]

    def get_parent_army(self):
        return self.parent_army

    def get_models_for_wound_allocation(self):
        return list(self.models)


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

    def test_direct_wound_allocation_records_damage_allocation_decision(self):
        from warhammer40k_ai.battlefield.map import Map
        from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
        from warhammer40k_ai.engine.game import Game
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.units.wargear import WargearProfile

        player = Player("P1", control=PlayerControl.LOCAL)
        game_map = Map(60, 44)
        game = Game(game_map, players=[player])
        player.game = game
        game.map.game = game
        army = SimpleNamespace(id="army:p1", units=[], player=player)
        player.army = army
        target = _AllocUnit("unit:target", army)
        army.units.append(target)
        attacker_unit = SimpleNamespace(id="unit:attacker", get_parent_army=lambda: army)
        attacker = SimpleNamespace(id="model:attacker", name="Attacker", parent_unit=attacker_unit)
        for entity, kind in [
            (army, "army"),
            (target, "unit"),
            (attacker_unit, "unit"),
            (attacker, "model"),
            (target.models[0], "model"),
            (target.models[1], "model"),
        ]:
            game.entity_registry.register(entity, kind=kind)

        profile = WargearProfile(
            "Test Profile",
            {"range": "24", "A": "1", "BS_WS": "3+", "S": "4", "AP": "0", "D": "1", "description": ""},
            parent_wargear=SimpleNamespace(name="Test Rifle"),
        )

        chosen = profile.opponent_wound_allocation(target, attacker=attacker, game_map=game.map)

        self.assertIs(chosen, target.models[0])
        records = [
            record
            for record in game.decision_record_store.records
            if record.get("decision_type") == DECISION_ALLOCATE_DAMAGE
        ]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["valid"], True)
        self.assertEqual(records[0]["chosen_action_id"], f"{DECISION_ALLOCATE_DAMAGE}:unit:target:unit:target:model-a")
        self.assertIs(records[0]["outcome"]["immediate_deltas"]["value"], target.models[0])
