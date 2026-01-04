import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _UnitStub:
    def __init__(self, *, keywords=None, models=None, army=None):
        self.keywords = list(keywords or [])
        self.models = list(models or [])
        self.deployed = True
        self.round_state = SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False)
        self.special_rules = {}
        self.attached_leaders = []
        self._characteristic_modifiers = {}
        self._army = army

    def get_parent_army(self):
        return self._army

    def has_any_keyword(self, kw: str) -> bool:
        kw_l = str(kw or "").strip().lower()
        return kw_l in [str(k or "").strip().lower() for k in self.keywords]

    def is_alive(self) -> bool:
        return True

    def get_attached_unit_models(self):
        return self.models


class _MapStub:
    def __init__(self, units):
        self.units = list(units or [])

    def get_enemy_units(self, unit):
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        return [u for u in self.units if getattr(u, "get_parent_army", lambda: None)() is not army]

    def get_friendly_units(self, unit):
        try:
            army = unit.get_parent_army()
        except Exception:
            army = None
        return [u for u in self.units if getattr(u, "get_parent_army", lambda: None)() is army]


class TestNurglesGift(unittest.TestCase):
    def _make_profile(self, *, melee: bool):
        from warhammer40k_ai.classes.wargear import Wargear

        data = {
            "range": "Melee" if melee else "24",
            "A": "1",
            "BS_WS": "3",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
        parent = Wargear({"name": "Test Weapon", "type": "Melee" if melee else "Ranged", **data})
        return parent.profiles["default"]

    def test_contagion_range_by_battle_round(self):
        from warhammer40k_ai.classes.nurgles_gift import NurglesGiftManager

        mgr = NurglesGiftManager()
        self.assertEqual(mgr.get_contagion_range(1), 3.0)
        self.assertEqual(mgr.get_contagion_range(2), 6.0)
        self.assertEqual(mgr.get_contagion_range(3), 9.0)

    def test_skullsquirm_blight_hit_penalty(self):
        from warhammer40k_ai.classes.nurgles_gift import NurglesGiftManager, PLAGUE_SKULLSQUIRM

        profile = self._make_profile(melee=True)

        player_attacker = SimpleNamespace(name="P1")
        player_dg = SimpleNamespace(name="DG")
        enemy_army = SimpleNamespace(faction_id="SM", units=[], player=player_attacker)
        dg_army = SimpleNamespace(faction_id="DG", units=[], player=player_dg)

        dg_mgr = NurglesGiftManager(dg_army)
        dg_mgr.active_plague_key = PLAGUE_SKULLSQUIRM.key
        dg_army.nurgles_gift = dg_mgr

        source_unit = _UnitStub(keywords=["DEATH GUARD"], models=[SimpleNamespace(is_alive=True)], army=dg_army)
        attacker_unit = _UnitStub(keywords=["INFANTRY"], models=[SimpleNamespace(is_alive=True)], army=enemy_army)
        dg_army.units = [source_unit]
        enemy_army.units = [attacker_unit]

        game_map = _MapStub([source_unit, attacker_unit])
        game = SimpleNamespace(map=game_map, event_system=SimpleNamespace(publish=lambda *_a, **_k: None), turn=1)
        player_attacker.game = game
        player_dg.game = game

        attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)
        target = SimpleNamespace(
            has_stealth=lambda: False,
            has_first_prince_tzeentch_defense=lambda: False,
        )

        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
            with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=3):
                res = profile._hit_target_with_tracking(target, attacker_model, {})

        self.assertFalse(res["hit"])
        self.assertTrue(any("Skullsquirm" in m for m in (res.get("modifiers") or [])))

    def test_rattlejoint_ague_worsens_save(self):
        from warhammer40k_ai.classes.nurgles_gift import NurglesGiftManager, PLAGUE_RATTLEJOINT
        from warhammer40k_ai.classes.unit import Unit

        player_attacker = SimpleNamespace(name="P1")
        player_dg = SimpleNamespace(name="DG")
        enemy_army = SimpleNamespace(faction_id="SM", units=[], player=player_attacker)
        dg_army = SimpleNamespace(faction_id="DG", units=[], player=player_dg)

        dg_mgr = NurglesGiftManager(dg_army)
        dg_mgr.active_plague_key = PLAGUE_RATTLEJOINT.key
        dg_army.nurgles_gift = dg_mgr

        source_unit = _UnitStub(keywords=["DEATH GUARD"], models=[SimpleNamespace(is_alive=True)], army=dg_army)
        afflicted_unit = _UnitStub(keywords=["INFANTRY"], models=[SimpleNamespace(is_alive=True)], army=enemy_army)
        dg_army.units = [source_unit]
        enemy_army.units = [afflicted_unit]

        game_map = _MapStub([source_unit, afflicted_unit])
        game = SimpleNamespace(map=game_map, event_system=SimpleNamespace(publish=lambda *_a, **_k: None), turn=1)
        player_attacker.game = game
        player_dg.game = game

        model = SimpleNamespace(_save=3, _save_raw="3+", is_alive=True, parent_unit=afflicted_unit)

        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
            save_val = Unit.get_effective_model_characteristic(afflicted_unit, model, "save", game_map=game_map)

        self.assertEqual(int(save_val), 4)

    def test_scabrous_soulrot_worsens_move_ld_oc(self):
        from warhammer40k_ai.classes.nurgles_gift import NurglesGiftManager, PLAGUE_SCABROUS
        from warhammer40k_ai.classes.unit import Unit

        player_attacker = SimpleNamespace(name="P1")
        player_dg = SimpleNamespace(name="DG")
        enemy_army = SimpleNamespace(faction_id="SM", units=[], player=player_attacker)
        dg_army = SimpleNamespace(faction_id="DG", units=[], player=player_dg)

        dg_mgr = NurglesGiftManager(dg_army)
        dg_mgr.active_plague_key = PLAGUE_SCABROUS.key
        dg_army.nurgles_gift = dg_mgr

        source_unit = _UnitStub(keywords=["DEATH GUARD"], models=[SimpleNamespace(is_alive=True)], army=dg_army)
        afflicted_unit = _UnitStub(keywords=["INFANTRY"], models=[SimpleNamespace(is_alive=True)], army=enemy_army)
        dg_army.units = [source_unit]
        enemy_army.units = [afflicted_unit]

        game_map = _MapStub([source_unit, afflicted_unit])
        game = SimpleNamespace(map=game_map, event_system=SimpleNamespace(publish=lambda *_a, **_k: None), turn=1)
        player_attacker.game = game
        player_dg.game = game

        model = SimpleNamespace(
            _movement=6,
            _movement_raw="6",
            _leadership=7,
            _leadership_raw="7+",
            _objective_control=2,
            _objective_control_raw="2",
            is_alive=True,
            parent_unit=afflicted_unit,
        )
        low_oc_model = SimpleNamespace(
            _objective_control=1,
            _objective_control_raw="1",
            is_alive=True,
            parent_unit=afflicted_unit,
        )

        with patch("warhammer40k_ai.utility.aura_utils.unit_within_range_of_unit", return_value=True):
            move_val = Unit.get_effective_model_characteristic(afflicted_unit, model, "movement", game_map=game_map)
            ld_val = Unit.get_effective_model_characteristic(afflicted_unit, model, "leadership", game_map=game_map)
            oc_val = Unit.get_effective_model_characteristic(afflicted_unit, model, "objective_control", game_map=game_map)
            oc_low = Unit.get_effective_model_characteristic(afflicted_unit, low_oc_model, "objective_control", game_map=game_map)

        self.assertEqual(int(move_val), 5)
        self.assertEqual(int(ld_val), 8)
        self.assertEqual(int(oc_val), 1)
        self.assertEqual(int(oc_low), 1)


if __name__ == "__main__":
    unittest.main()
