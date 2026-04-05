import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
        attached_to=None,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
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
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
    attached_to=None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            attached_to=attached_to,
        )
    )


def _build_game(detachment_type: str = "Spearpoint Task Force"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army("Space Marines", detachment_type)
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army


def _set_model_location(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="SM",
        detachment="Spearpoint Task Force",
        points=25,
        description="",
    ).apply_to_unit(unit)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    for unit in (bodyguard, leader):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()
        refresh_modifiers = getattr(unit, "_refresh_bearer_unit_common_modifiers", None)
        if callable(refresh_modifiers):
            refresh_modifiers()


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            return model
    for model in list(getattr(unit, "models", []) or []):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if alive:
            return model
    return None


class TestSpaceMarinesSpearpointTaskForceEnhancements(unittest.TestCase):
    def test_spearpoint_task_force_enhancement_descriptors_exist(self):
        expected = {
            "000010629002": ("Spearpoint Paragon", "bearer_melee_strength_and_ap_bonus_with_charge_upgrade"),
            "000010629003": ("Stormseers' Wisdom", "reroll_advance_rolls_for_bearer_led_unit"),
            "000010629004": (
                "Hunter's Eye",
                "grant_sustained_hits_and_ignores_cover_to_bearer_unit_ranged_weapons",
            ),
            "000010629005": ("Chogorian Huntmaster", "add_setup_round_for_bearer_unit_in_strategic_reserves"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_spearpoint_paragon_sets_base_bearer_bonus_and_charge_extra_bonus(self):
        game, sm_army, _enemy_army = _build_game()
        unit = _make_unit(
            "White Scars Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES", "WHITE SCARS"],
            model_count=1,
            wounds=6,
        )
        sm_army.add_unit(unit)
        unit.deployed = True
        _set_model_location(unit, 0.0, 0.0)
        game.map.units = [unit]
        game.rebuild_entity_registry()

        _apply_enhancement(unit, enhancement_id="000010629002", enhancement_name="Spearpoint Paragon")
        sr = getattr(unit, "special_rules", {})
        self.assertTrue(bool(sr.get("enhancement_spearpoint_paragon")))
        self.assertEqual(int(sr.get("enhancement_bearer_melee_strength_bonus", 0) or 0), 1)
        self.assertEqual(int(sr.get("enhancement_bearer_melee_ap_bonus", 0) or 0), 1)
        self.assertEqual(int(sr.get("enhancement_spearpoint_paragon_charge_extra_strength_bonus", 0) or 0), 1)
        self.assertEqual(int(sr.get("enhancement_spearpoint_paragon_charge_extra_ap_bonus", 0) or 0), 1)

        bearer = _bearer_model(unit)
        self.assertIsNotNone(bearer)
        self.assertEqual(int(getattr(bearer, "get_temporary_melee_ap_bonus", lambda: 0)() or 0), 0)
        strength_bonus, _reasons = getattr(bearer, "get_temporary_melee_strength_bonus", lambda: (0, []))()
        self.assertEqual(int(strength_bonus or 0), 0)

        self.assertTrue(bool(unit._apply_charge_end_model_melee_strength_ap_bonuses()))
        self.assertEqual(int(getattr(bearer, "get_temporary_melee_ap_bonus", lambda: 0)() or 0), 1)
        strength_bonus, reasons = getattr(bearer, "get_temporary_melee_strength_bonus", lambda: (0, []))()
        self.assertEqual(int(strength_bonus or 0), 1)
        self.assertTrue(any("Spearpoint Paragon" in str(reason) for reason in list(reasons or [])))

    def test_stormseers_wisdom_requires_bearer_leading_and_alive(self):
        game, sm_army, _enemy_army = _build_game()
        leader = _make_unit(
            "Stormseer",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES", "WHITE SCARS"],
            model_count=1,
            wounds=5,
            attached_to=["INFANTRY_BODYGUARD"],
        )
        bodyguard = _make_unit(
            "Outrider Escort",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES", "WHITE SCARS"],
            model_count=2,
            wounds=2,
        )
        sm_army.add_unit(leader)
        sm_army.add_unit(bodyguard)
        leader.deployed = True
        bodyguard.deployed = True
        _set_model_location(leader, 0.0, 0.0)
        _set_model_location(bodyguard, 0.0, 2.0)
        game.map.units = [leader, bodyguard]
        game.rebuild_entity_registry()

        _apply_enhancement(leader, enhancement_id="000010629003", enhancement_name="Stormseers' Wisdom")
        self.assertFalse(bool(leader.can_reroll_advance_roll()))
        self.assertFalse(bool(bodyguard.can_reroll_advance_roll()))

        _attach_leader(bodyguard, leader)
        self.assertTrue(bool(bodyguard.can_reroll_advance_roll()))

        bearer = _bearer_model(leader)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        self.assertFalse(bool(bodyguard.can_reroll_advance_roll()))

    def test_hunters_eye_grants_ranged_sustained_hits_and_ignores_cover_to_bearers_unit(self):
        game, sm_army, _enemy_army = _build_game()
        leader = _make_unit(
            "White Scars Captain",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES", "WHITE SCARS"],
            model_count=1,
            wounds=6,
            attached_to=["INFANTRY_BODYGUARD"],
        )
        bodyguard = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES", "WHITE SCARS"],
            model_count=2,
            wounds=2,
        )
        sm_army.add_unit(leader)
        sm_army.add_unit(bodyguard)
        leader.deployed = True
        bodyguard.deployed = True
        _set_model_location(leader, 0.0, 0.0)
        _set_model_location(bodyguard, 0.0, 2.0)
        game.map.units = [leader, bodyguard]
        game.rebuild_entity_registry()

        _apply_enhancement(leader, enhancement_id="000010629004", enhancement_name="Hunter's Eye")
        _attach_leader(bodyguard, leader)

        bodyguard_model = list(getattr(bodyguard, "models", []) or [None])[0]
        bonuses = bodyguard.get_model_weapon_keyword_bonuses(model=bodyguard_model, attack_type="ranged")
        self.assertTrue(bool(bonuses.get("ignores_cover")))
        self.assertEqual(int(bonuses.get("sustained_hits_value", 0) or 0), 1)
        self.assertTrue(any("Hunter's Eye" in str(source) for source in list(bonuses.get("sources", []) or [])))

        bearer = _bearer_model(leader)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        bonuses_after = bodyguard.get_model_weapon_keyword_bonuses(model=bodyguard_model, attack_type="ranged")
        self.assertFalse(bool(bonuses_after.get("ignores_cover")))
        self.assertEqual(int(bonuses_after.get("sustained_hits_value", 0) or 0), 0)

    def test_chogorian_huntmaster_advances_strategic_reserves_setup_round_while_bearer_is_alive(self):
        game, sm_army, _enemy_army = _build_game()
        unit = _make_unit(
            "Khan on Bike",
            keywords=["CHARACTER", "MOUNTED"],
            faction_keywords=["ADEPTUS ASTARTES", "WHITE SCARS"],
            model_count=1,
            wounds=6,
        )
        sm_army.add_unit(unit)
        unit.deployed = True
        _set_model_location(unit, 0.0, 0.0)
        game.map.units = [unit]
        game.rebuild_entity_registry()

        _apply_enhancement(unit, enhancement_id="000010629005", enhancement_name="Chogorian Huntmaster")
        unit.reserve_status = "strategic_reserves"
        unit._started_in_reserves = False

        self.assertEqual(int(unit.get_strategic_reserves_setup_turn(current_turn=1) or 0), 2)
        self.assertTrue(bool(unit.can_arrive_from_reserves(1)))

        bearer = _bearer_model(unit)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        self.assertEqual(int(unit.get_strategic_reserves_setup_turn(current_turn=1) or 0), 1)
        self.assertFalse(bool(unit.can_arrive_from_reserves(1)))


if __name__ == "__main__":
    unittest.main()
