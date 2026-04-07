import unittest
from types import SimpleNamespace


class _StubUnit:
    def __init__(self, name: str, *, keywords=None, specs=None):
        self.name = name
        self.special_rules = {}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.models = []
        self.round_state = SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False)
        self.parent_army = None
        self.deployed = True
        self.is_embarked = False
        self._in_reserves = False
        self._specs = list(specs or [])
        self.is_vehicle = False
        self.is_monster = False

    def set_parent_army(self, army_ptr):
        self.parent_army = army_ptr

    def get_parent_army(self):
        return self.parent_army

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_members(self):
        return [self]

    def get_attached_unit_models(self):
        return list(self.models)

    def get_models_for_wound_allocation(self):
        return list(self.models)

    def is_alive(self):
        return True

    def is_in_reserves(self):
        return bool(self._in_reserves)

    def has_keyword(self, keyword: str) -> bool:
        kw = (keyword or "").strip().lower()
        if not kw:
            return False
        return any(kw == k.lower() for k in (self.keywords or []))

    @property
    def is_titanic(self) -> bool:
        return self.has_keyword("Titanic")

    def unit_fight_selected_enemy_melee_hit_penalty_specs(self):
        return list(self._specs)


class _StubMap:
    def __init__(self, selected_unit, enemy_units):
        self._selected_unit = selected_unit
        self._enemy_units = list(enemy_units)

    def get_enemy_units(self, unit):
        if unit is self._selected_unit:
            return list(self._enemy_units)
        return []

    def is_within_engagement_range(self, unit_a, unit_b):
        return True


class TestMischiefMakers(unittest.TestCase):
    def _build_game(self):
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize, BattleRoundPhases
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.roster.army import Army

        army = Army.with_detachment("Chaos Daemons", detachment_type="Daemonic Incursion")
        army.faction_id = "CD"
        enemy_army = Army.with_detachment("Opponent", detachment_type="Other")
        enemy_army.faction_id = "SM"
        p1 = Player("P1", PlayerControl.LOCAL, army=army)
        p2 = Player("P2", PlayerControl.REMOTE, army=enemy_army)

        bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
        game = Game(bf, players=[p1, p2])
        game.phase = BattleRoundPhases.FIGHT_PHASE
        return game, army, enemy_army, p1, p2

    def _build_melee_profile(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        melee_parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
        return WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=melee_parent,
        )

    def _build_model(self, name: str):
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        return Model(
            name=name,
            movement=6,
            toughness=5,
            save=3,
            wounds=3,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )

    def test_mischief_makers_applies_hit_penalty(self):
        game, army, enemy_army, _p1, p2 = self._build_game()
        ability_specs = [{"source": "Mischief Makers", "exclude_keyword": "TITANIC"}]
        ability_unit = _StubUnit("Nurglings", specs=ability_specs)
        selected_unit = _StubUnit("Target Unit")
        army.add_unit(ability_unit)
        enemy_army.add_unit(selected_unit)
        ability_unit.set_parent_army(army)
        selected_unit.set_parent_army(enemy_army)

        game.map = _StubMap(selected_unit, [ability_unit])

        attacker = self._build_model("Attacker")
        attacker.parent_unit = selected_unit
        selected_unit.models = [attacker]

        target_model = self._build_model("Target")
        target_model.parent_unit = ability_unit
        ability_unit.models = [target_model]

        game.event_system.publish("fight_unit_selected", unit=selected_unit, selecting_player=p2)
        self.assertTrue(selected_unit.special_rules.get("fight_selected_enemy_melee_hit_penalty_active"))

        profile = self._build_melee_profile()
        aura_stub = SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )
        attack_instance = {"_aura_attack_mods": aura_stub}
        hit_res = profile._hit_target_with_tracking(
            ability_unit,
            attacker,
            attack_instance,
            roll_value=4,
            log_roll=False,
        )
        self.assertTrue(any("Mischief Makers" in x for x in hit_res.get("modifiers", [])))

        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertNotIn("fight_selected_enemy_melee_hit_penalty_active", selected_unit.special_rules)

    def test_mischief_makers_excludes_titanic(self):
        game, army, enemy_army, _p1, p2 = self._build_game()
        ability_specs = [{"source": "Mischief Makers", "exclude_keyword": "TITANIC"}]
        ability_unit = _StubUnit("Nurglings", specs=ability_specs)
        selected_unit = _StubUnit("Titanic Target", keywords=["TITANIC"])
        army.add_unit(ability_unit)
        enemy_army.add_unit(selected_unit)
        ability_unit.set_parent_army(army)
        selected_unit.set_parent_army(enemy_army)

        game.map = _StubMap(selected_unit, [ability_unit])

        game.event_system.publish("fight_unit_selected", unit=selected_unit, selecting_player=p2)
        self.assertFalse(selected_unit.special_rules.get("fight_selected_enemy_melee_hit_penalty_active"))


if __name__ == "__main__":
    unittest.main()
