import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        datasheet_id="TEST",
        faction_name="Space Marines",
        keywords=None,
        faction_keywords=None,
        leadership="6",
        attached_to=None,
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
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": leadership,
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
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


class _StubRng:
    def __init__(self, values):
        self._it = iter(values)

    def randint(self, _a, _b):
        return next(self._it)


class TestRageCursedOnslaughtEnhancements(unittest.TestCase):
    def _make_unit(
        self,
        name,
        *,
        datasheet_id,
        attached_to=None,
        keywords=None,
        faction_keywords=None,
        leadership="6",
    ):
        from warhammer40k_ai.units.unit import Unit

        datasheet = _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            keywords=keywords,
            faction_keywords=faction_keywords,
            leadership=leadership,
            attached_to=attached_to,
        )
        return Unit(datasheet)

    def _make_game(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
        from warhammer40k_ai.roster.player import Player, PlayerControl

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
        army = Army("Space Marines", detachment_type="Rage-cursed Onslaught")
        army.faction_id = "SM"
        player = Player("P1", control=PlayerControl.LOCAL, army=army)
        game.add_player(player)
        return game, army, player

    def _set_unit_location(self, unit, x, y):
        for model in list(getattr(unit, "models", []) or []):
            model.set_location(float(x), float(y), 0.0, 0.0)

    def test_carmine_reliquary_grants_scouts_to_attached_unit(self):
        from warhammer40k_ai.rules.enhancement import Enhancement

        _game, army, _player = self._make_game()
        bodyguard = self._make_unit(
            "Bodyguard",
            datasheet_id="BG1",
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        leader = self._make_unit(
            "Chaplain",
            datasheet_id="L1",
            attached_to=["BG1"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army.add_unit(bodyguard)
        army.add_unit(leader)
        leader.attach_to_unit(bodyguard)

        Enhancement(
            id="000010645002",
            name="Carmine Reliquary",
            faction_id="SM",
            detachment="Rage-cursed Onslaught",
            points=30,
            description="",
        ).apply_to_unit(leader)

        has_scout, distance = bodyguard.has_scout()
        self.assertTrue(has_scout)
        self.assertEqual(int(distance), 6)

    def test_carmine_reliquary_battle_shock_reroll(self):
        from warhammer40k_ai.rules.enhancement import Enhancement

        game, army, _player = self._make_game()
        bearer = self._make_unit(
            "Chaplain",
            datasheet_id="B1",
            keywords=["CHARACTER"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = self._make_unit(
            "Intercessors",
            datasheet_id="T1",
            faction_keywords=["ADEPTUS ASTARTES"],
            leadership="6",
        )
        army.add_unit(bearer)
        army.add_unit(target)

        Enhancement(
            id="000010645002",
            name="Carmine Reliquary",
            faction_id="SM",
            detachment="Rage-cursed Onslaught",
            points=30,
            description="",
        ).apply_to_unit(bearer)

        bearer.deployed = True
        target.deployed = True
        self._set_unit_location(bearer, 0.0, 0.0)
        self._set_unit_location(target, 5.0, 0.0)

        calls = {"count": 0}

        def _provider(**_kwargs):
            calls["count"] += 1
            return True

        game.map.roll_reroll_provider = _provider
        game.random_source = _StubRng([6, 3, 2, 3])
        target.take_battle_shock_test(current_turn=1)

        self.assertEqual(calls["count"], 1)
        self.assertFalse(target.is_battle_shocked())

    def test_sanguinary_tear_aura_strength_bonus(self):
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.units.wargear import Wargear

        enhancement = Enhancement(
            id="000010645004",
            name="Sanguinary Tear (Aura)",
            faction_id="SM",
            detachment="Rage-cursed Onslaught",
            description=(
                "ADEPTUS ASTARTES model only. While a friendly Death Company unit is within 6\" of the bearer, "
                "add 1 to the Strength characteristic of weapons equipped by models in that unit."
            ),
        )

        class _Unit:
            def __init__(self, *, keywords=None, enhancement=None):
                self.possible_abilities = []
                self.enhancement = enhancement
                self.special_rules = {}
                self.round_state = SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False)
                self._army = None
                self._keywords = [str(k or "") for k in (keywords or [])]

            def get_parent_army(self):
                return self._army

            def has_any_keyword(self, kw: str) -> bool:
                key = str(kw or "").strip().lower()
                return key in [k.lower() for k in self._keywords]

        class _Map:
            def __init__(self, units):
                self.units = list(units)

            def get_friendly_units(self, unit):
                return list(self.units)

        attacker_unit = _Unit(keywords=["DEATH COMPANY"])
        aura_source = _Unit(keywords=["ADEPTUS ASTARTES"], enhancement=enhancement)
        target = SimpleNamespace(
            toughness=5,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda _k: False,
        )

        game_map = _Map([attacker_unit, aura_source])
        game = SimpleNamespace(map=game_map, event_system=SimpleNamespace(publish=lambda *_a, **_k: None), turn=1)
        player = SimpleNamespace(game=game, name="P1", id="P1")
        army = SimpleNamespace(player=player)
        attacker_unit._army = army
        aura_source._army = army

        melee_parent = Wargear({"name": "Test Blade", "type": "Melee", "range": "Melee", "A": "1", "BS_WS": "3+", "S": "4", "AP": "0", "D": "1"})
        profile = melee_parent.profiles["default"]

        attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)

        with patch("warhammer40k_ai.utility.aura_effects.unit_within_range_of_unit", return_value=True):
            with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
                res = profile._wound_target_with_tracking(target, attacker_model, {})

        self.assertTrue(res["wound"])
        self.assertTrue(any("Sanguinary Tear" in m for m in res.get("modifiers", [])))

    def test_angels_fang_grants_sustained_hits_two_vs_character(self):
        from warhammer40k_ai.rules.enhancement import Enhancement
        from warhammer40k_ai.units.wargear import Wargear

        class _Unit:
            def __init__(self):
                self.special_rules = {}
                self.round_state = SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False)

            def get_parent_army(self):
                return None

        unit = _Unit()

        Enhancement(
            id="000010645005",
            name="Angel's Fang",
            faction_id="SM",
            detachment="Rage-cursed Onslaught",
            description="",
        ).apply_to_unit(unit)

        melee_parent = Wargear({"name": "Test Blade", "type": "Melee", "range": "Melee", "A": "1", "BS_WS": "3+", "S": "4", "AP": "0", "D": "1"})
        profile = melee_parent.profiles["default"]

        attacker_model = SimpleNamespace(name="Attacker", parent_unit=unit)
        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda kw: str(kw).strip().lower() == "character",
        )

        attack_instance = {}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            res = profile._hit_target_with_tracking(target, attacker_model, attack_instance)

        self.assertTrue(res["hit"])
        self.assertEqual(int(attack_instance.get("sustained_hit", 0)), 2)
        self.assertTrue(any("Angel's Fang" in s for s in res.get("special_effects", [])))


if __name__ == "__main__":
    unittest.main()
