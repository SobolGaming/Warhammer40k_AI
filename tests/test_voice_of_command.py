import unittest
from types import SimpleNamespace


class _Ability:
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description


class _PlayerStub:
    def __init__(self, name="Player", *, is_human=True):
        self.name = name
        self.type = SimpleNamespace(name="HUMAN" if is_human else "AI")
        self.game = None


class _ArmyStub:
    def __init__(self, units=None, *, faction_id="AM"):
        self.units = list(units or [])
        self.faction_id = faction_id
        self.player = _PlayerStub()
        self.player.game = None


class _UnitStub:
    def __init__(self, name="Unit", *, keywords=None, abilities=None, army=None):
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = ["ASTRA MILITARUM"]
        self.possible_abilities = list(abilities or [])
        self.abilities = []
        self.models = []
        self.special_rules = {}
        self._characteristic_modifiers = {}
        self.attached_leaders = []
        self.deployed = True
        self.reserve_status = "deployed"
        self.embarked_in = None
        self.round_state = SimpleNamespace(remained_stationary_this_round=False)
        self.toughness = 4
        self._army = army

    def get_parent_army(self):
        return self._army

    def set_parent_army(self, army):
        self._army = army

    def has_any_keyword(self, keyword: str) -> bool:
        kw = str(keyword or "").strip().lower()
        return kw in [str(k or "").strip().lower() for k in (self.keywords or []) + (self.faction_keywords or [])]

    def is_alive(self) -> bool:
        return True

    def is_battle_shocked(self) -> bool:
        return False

    def is_embarked(self) -> bool:
        return False

    def get_attached_unit_root(self):
        return self

    def add_characteristic_modifier(self, characteristic: str, modifier) -> None:
        key = str(characteristic or "").strip().lower()
        self._characteristic_modifiers.setdefault(key, []).append(modifier)

    def remove_characteristic_modifiers_by_source(self, source_prefix: str) -> None:
        p = str(source_prefix or "")
        for k, mods in list(self._characteristic_modifiers.items()):
            kept = []
            for m in (mods or []):
                try:
                    if str(getattr(m, "source", "") or "").startswith(p):
                        continue
                except Exception:
                    pass
                kept.append(m)
            self._characteristic_modifiers[k] = kept

    def get_attached_unit_models(self):
        return self.models

    def get_models_for_wound_allocation(self):
        return self.models


class _MapStub:
    def __init__(self, friendlies=None, *, distance=3.0):
        self._friendlies = list(friendlies or [])
        self._distance = float(distance)

    def get_friendly_units(self, _unit):
        return list(self._friendlies)

    def get_distance_between_units(self, _unit1, _unit2):
        return float(self._distance)


class _ModelStub:
    def __init__(self, name: str, parent_unit: _UnitStub, *, distance=10.0):
        self.name = name
        self.parent_unit = parent_unit
        self._distance = float(distance)
        self.is_alive = True
        self.z = 0.0

    def return_closest_model_in_unit(self, _unit):
        return self, self._distance


class TestVoiceOfCommand(unittest.TestCase):
    def _make_profile(self, *, weapon_type="Ranged", skill="4+", description=""):
        from warhammer40k_ai.classes.wargear import WargearProfile

        parent = SimpleNamespace(
            name="Test Weapon",
            is_melee=lambda: weapon_type.lower() == "melee",
            is_ranged=lambda: weapon_type.lower() == "ranged",
        )
        data = {
            "range": "Melee" if weapon_type.lower() == "melee" else "24",
            "A": "1",
            "BS_WS": skill,
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": description,
        }
        return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)

    def test_orders_profile_parsing(self):
        from warhammer40k_ai.classes.voice_of_command import VoiceOfCommandManager

        officer = _UnitStub(
            "Officer",
            abilities=[_Ability("Orders", "This model can issue 2 orders to REGIMENT or SQUADRON units within 6\".")],
        )
        mgr = VoiceOfCommandManager()
        count, keywords, allowed = mgr._parse_orders_profile(officer)
        self.assertEqual(count, 2)
        self.assertEqual(keywords, ["REGIMENT", "SQUADRON"])
        self.assertEqual(allowed, [])

    def test_orders_profile_parsing_variants(self):
        from warhammer40k_ai.classes.voice_of_command import VoiceOfCommandManager

        cases = [
            (
                "This OFFICER can issue up to 2 Orders to REGIMENT or GAUNT\u2019S GHOSTS units.",
                2,
                ["REGIMENT", "GAUNT'S GHOSTS"],
            ),
            (
                "This OFFICER can issue up to 3 Orders to: REGIMENT units SQUADRON units TITANIC units",
                3,
                ["REGIMENT", "SQUADRON", "TITANIC"],
            ),
            ("This Officer can issue 1 Order to a CATACHAN JUNGLE FIGHTERS unit.", 1, ["CATACHAN JUNGLE FIGHTERS"]),
            ("This unit\u2019s OFFICER can issue 2 Orders to REGIMENT units.", 2, ["REGIMENT"]),
        ]
        mgr = VoiceOfCommandManager()
        for text, expected_count, expected_keywords in cases:
            officer = _UnitStub("Officer", abilities=[_Ability("ORDERS", text)])
            count, keywords, allowed = mgr._parse_orders_profile(officer)
            self.assertEqual(count, expected_count)
            self.assertEqual(keywords, expected_keywords)
            self.assertEqual(allowed, [])

    def test_orders_profile_restricted_orders(self):
        from warhammer40k_ai.classes.voice_of_command import VoiceOfCommandManager, ORDER_DUTY_HONOUR, ORDER_FIX_BAYONETS, ORDER_TAKE_AIM

        orders_text = (
            "This OFFICER can issue 1 Order to a REGIMENT unit. "
            "This OFFICER can only issue the Duty and Honour! and Fix Bayonets! Orders."
        )
        army = _ArmyStub()
        mgr = VoiceOfCommandManager(army)
        mgr._army_has_voice = lambda: True
        army.voice_of_command = mgr

        officer = _UnitStub(
            "Officer",
            keywords=["OFFICER", "ASTRA MILITARUM"],
            abilities=[_Ability("Voice of Command"), _Ability("Orders", orders_text)],
            army=army,
        )
        target = _UnitStub(
            "Infantry",
            keywords=["REGIMENT", "ASTRA MILITARUM"],
            abilities=[],
            army=army,
        )
        army.units = [officer, target]
        officer.set_parent_army(army)
        target.set_parent_army(army)

        game = SimpleNamespace(turn=1, map=_MapStub([officer, target]))
        army.player.game = game

        self.assertEqual(
            [o.key for o in mgr.get_available_orders(officer)],
            [ORDER_FIX_BAYONETS.key, ORDER_DUTY_HONOUR.key],
        )
        self.assertFalse(mgr.issue_order(game, officer, target, ORDER_TAKE_AIM.key, phase_name="COMMAND_PHASE"))
        self.assertTrue(mgr.issue_order(game, officer, target, ORDER_DUTY_HONOUR.key, phase_name="COMMAND_PHASE"))

    def test_move_order_increases_movement_and_consumes_order(self):
        from warhammer40k_ai.classes.voice_of_command import VoiceOfCommandManager, ORDER_MOVE
        from warhammer40k_ai.classes.unit import Unit

        orders_text = "This model can issue 2 orders to REGIMENT units within 6\"."
        army = _ArmyStub()
        mgr = VoiceOfCommandManager(army)
        mgr._army_has_voice = lambda: True
        army.voice_of_command = mgr

        officer = _UnitStub(
            "Officer",
            keywords=["OFFICER", "ASTRA MILITARUM"],
            abilities=[_Ability("Voice of Command"), _Ability("Orders", orders_text)],
            army=army,
        )
        target = _UnitStub(
            "Infantry",
            keywords=["REGIMENT", "ASTRA MILITARUM"],
            abilities=[],
            army=army,
        )
        army.units = [officer, target]
        officer.set_parent_army(army)
        target.set_parent_army(army)

        game = SimpleNamespace(turn=1, map=_MapStub([officer, target]))
        army.player.game = game

        ok = mgr.issue_order(game, officer, target, ORDER_MOVE.key, phase_name="COMMAND_PHASE")
        self.assertTrue(ok)
        self.assertEqual(target.special_rules.get("voice_of_command_order_key"), ORDER_MOVE.key)
        self.assertEqual(mgr.orders_remaining(officer, 1), 1)

        model = SimpleNamespace(
            _movement=6,
            _movement_raw="6",
            is_alive=True,
            parent_unit=target,
        )
        target.models = [model]
        move_val = Unit.get_effective_model_characteristic(target, model, "movement")
        self.assertEqual(int(move_val), 9)

    def test_take_cover_caps_save(self):
        from warhammer40k_ai.classes.voice_of_command import VoiceOfCommandManager, ORDER_TAKE_COVER
        from warhammer40k_ai.classes.unit import Unit

        orders_text = "This model can issue 1 order to REGIMENT units within 6\"."
        army = _ArmyStub()
        mgr = VoiceOfCommandManager(army)
        mgr._army_has_voice = lambda: True
        army.voice_of_command = mgr

        officer = _UnitStub(
            "Officer",
            keywords=["OFFICER", "ASTRA MILITARUM"],
            abilities=[_Ability("Voice of Command"), _Ability("Orders", orders_text)],
            army=army,
        )
        target = _UnitStub(
            "Infantry",
            keywords=["REGIMENT", "ASTRA MILITARUM"],
            abilities=[],
            army=army,
        )
        army.units = [officer, target]
        officer.set_parent_army(army)
        target.set_parent_army(army)

        game = SimpleNamespace(turn=1, map=_MapStub([officer, target]))
        army.player.game = game

        ok = mgr.issue_order(game, officer, target, ORDER_TAKE_COVER.key, phase_name="COMMAND_PHASE")
        self.assertTrue(ok)

        model_worse = SimpleNamespace(_save=4, _save_raw="4+", is_alive=True, parent_unit=target)
        model_better = SimpleNamespace(_save=2, _save_raw="2+", is_alive=True, parent_unit=target)
        target.models = [model_worse, model_better]

        save_worse = Unit.get_effective_model_characteristic(target, model_worse, "save")
        save_better = Unit.get_effective_model_characteristic(target, model_better, "save")
        self.assertEqual(int(save_worse), 3)
        self.assertEqual(int(save_better), 2)

    def test_duty_and_honour_improves_leadership_and_oc(self):
        from warhammer40k_ai.classes.voice_of_command import VoiceOfCommandManager, ORDER_DUTY_HONOUR
        from warhammer40k_ai.classes.unit import Unit

        orders_text = "This model can issue 1 order to REGIMENT units within 6\"."
        army = _ArmyStub()
        mgr = VoiceOfCommandManager(army)
        mgr._army_has_voice = lambda: True
        army.voice_of_command = mgr

        officer = _UnitStub(
            "Officer",
            keywords=["OFFICER", "ASTRA MILITARUM"],
            abilities=[_Ability("Voice of Command"), _Ability("Orders", orders_text)],
            army=army,
        )
        target = _UnitStub(
            "Infantry",
            keywords=["REGIMENT", "ASTRA MILITARUM"],
            abilities=[],
            army=army,
        )
        army.units = [officer, target]
        officer.set_parent_army(army)
        target.set_parent_army(army)

        game = SimpleNamespace(turn=1, map=_MapStub([officer, target]))
        army.player.game = game

        ok = mgr.issue_order(game, officer, target, ORDER_DUTY_HONOUR.key, phase_name="COMMAND_PHASE")
        self.assertTrue(ok)

        model = SimpleNamespace(
            _leadership=7,
            _leadership_raw="7+",
            _objective_control=2,
            _objective_control_raw="2",
            is_alive=True,
            parent_unit=target,
        )
        target.models = [model]
        ld_val = Unit.get_effective_model_characteristic(target, model, "leadership")
        oc_val = Unit.get_effective_model_characteristic(target, model, "objective_control")
        self.assertEqual(int(ld_val), 6)
        self.assertEqual(int(oc_val), 3)

    def test_take_aim_and_fix_bayonets_modify_hit_skill(self):
        from warhammer40k_ai.classes.voice_of_command import VoiceOfCommandManager, ORDER_TAKE_AIM, ORDER_FIX_BAYONETS

        orders_text = "This model can issue 2 orders to REGIMENT units within 6\"."
        army = _ArmyStub()
        mgr = VoiceOfCommandManager(army)
        mgr._army_has_voice = lambda: True
        army.voice_of_command = mgr

        officer = _UnitStub(
            "Officer",
            keywords=["OFFICER", "ASTRA MILITARUM"],
            abilities=[_Ability("Voice of Command"), _Ability("Orders", orders_text)],
            army=army,
        )
        shooter = _UnitStub(
            "Infantry",
            keywords=["REGIMENT", "ASTRA MILITARUM"],
            abilities=[],
            army=army,
        )
        army.units = [officer, shooter]
        officer.set_parent_army(army)
        shooter.set_parent_army(army)

        game = SimpleNamespace(turn=1, map=_MapStub([officer, shooter]))
        army.player.game = game

        self.assertTrue(mgr.issue_order(game, officer, shooter, ORDER_TAKE_AIM.key, phase_name="COMMAND_PHASE"))
        attacker = SimpleNamespace(name="Shooter", parent_unit=shooter)
        target = SimpleNamespace(has_stealth=lambda: False, has_first_prince_tzeentch_defense=lambda: False)
        ranged = self._make_profile(weapon_type="Ranged", skill="4+")
        hit = ranged._hit_target_with_tracking(target, attacker, {})
        self.assertEqual(hit.get("base_skill"), 3)

        self.assertTrue(mgr.issue_order(game, officer, shooter, ORDER_FIX_BAYONETS.key, phase_name="COMMAND_PHASE"))
        melee = self._make_profile(weapon_type="Melee", skill="4+")
        hit = melee._hit_target_with_tracking(target, attacker, {})
        self.assertEqual(hit.get("base_skill"), 3)

    def test_first_rank_fire_adds_attack(self):
        from warhammer40k_ai.classes.voice_of_command import VoiceOfCommandManager, ORDER_FRFSRF

        orders_text = "This model can issue 1 order to REGIMENT units within 6\"."
        army = _ArmyStub()
        mgr = VoiceOfCommandManager(army)
        mgr._army_has_voice = lambda: True
        army.voice_of_command = mgr

        officer = _UnitStub(
            "Officer",
            keywords=["OFFICER", "ASTRA MILITARUM"],
            abilities=[_Ability("Voice of Command"), _Ability("Orders", orders_text)],
            army=army,
        )
        shooter = _UnitStub(
            "Infantry",
            keywords=["REGIMENT", "ASTRA MILITARUM"],
            abilities=[],
            army=army,
        )
        target = _UnitStub(
            "Target",
            keywords=["INFANTRY"],
            abilities=[],
            army=_ArmyStub(faction_id="SM"),
        )
        target.models = [
            SimpleNamespace(
                name="Target Model",
                is_alive=True,
                z=0.0,
                save=4,
                inv_save=(None, ""),
                parent_unit=target,
            )
        ]
        army.units = [officer, shooter]
        officer.set_parent_army(army)
        shooter.set_parent_army(army)

        game = SimpleNamespace(turn=1, map=_MapStub([officer, shooter]), event_system=SimpleNamespace(publish=lambda *_a, **_k: None))
        army.player.game = game

        self.assertTrue(mgr.issue_order(game, officer, shooter, ORDER_FRFSRF.key, phase_name="COMMAND_PHASE"))

        model = _ModelStub("Shooter", shooter, distance=10.0)
        ranged = self._make_profile(weapon_type="Ranged", skill="4+", description="Rapid Fire 1")
        result = ranged.attack(target, model, game_map=None)
        self.assertIsNotNone(result)
        self.assertEqual(int(result.attacks_rolled), 3)
        self.assertTrue(any("First Rank, Fire! Second Rank, Fire! +1A" in s for s in result.attacks_special_modifiers))


if __name__ == "__main__":
    unittest.main()
