import unittest

import warhammer40k_ai.units.wargear as wargear_module
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.voice_of_command import ORDER_MOVE, VoiceOfCommandManager
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _Ability:
    def __init__(self, name: str, description: str = "", ability_type: str = ""):
        self.name = name
        self.description = description
        self.type = ability_type


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Astra Militarum",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        objective_control: int = 1,
        wounds: int = 4,
        move: int = 6,
        toughness: int = 8,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ASTRA MILITARUM"] if faction_name == "Astra Militarum" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": str(int(objective_control)),
                "base_size": "60mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Astra Militarum",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    objective_control: int = 1,
    wounds: int = 4,
    move: int = 6,
    toughness: int = 8,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            objective_control=objective_control,
            wounds=wounds,
            move=move,
            toughness=toughness,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    am_army = Army.with_detachment("Astra Militarum", "Hammer of the Emperor")
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    am_player = Player("Astra Militarum", control=PlayerControl.REMOTE, army=am_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, am_army, enemy_army


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        if not bool(getattr(model, "is_alive", False)):
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)
    unit.position = (float(x), float(y), 0.0)
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="AM",
        detachment="Hammer of the Emperor",
        points=20,
        description="",
    ).apply_to_unit(unit)


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            return model
    for model in list(getattr(unit, "models", []) or []):
        if bool(getattr(model, "is_alive", False)):
            return model
    return None


def _make_weapon_profile(*, weapon_type: str = "ranged", skill: str = "4+") -> WargearProfile:
    is_ranged = str(weapon_type or "").strip().lower() != "melee"
    parent = type(
        "_ParentWargear",
        (),
        {
            "name": "Test Weapon",
            "is_melee": (lambda self: not is_ranged),
            "is_ranged": (lambda self: is_ranged),
        },
    )()
    data = {
        "range": "24",
        "A": "1",
        "BS_WS": str(skill),
        "S": "8",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


class TestAstraMilitarumHammerOfTheEmperorEnhancements(unittest.TestCase):
    def test_hammer_of_the_emperor_enhancement_descriptors_exist(self):
        expected = {
            "000009865002": (
                "Calm Under Fire",
                "issue_same_order_once_per_turn_to_additional_squadron_unit",
            ),
            "000009865003": ("Indomitable Steed", "bearer_feel_no_pain"),
            "000009865004": ("Regimental Banner", "bearer_objective_control_bonus"),
            "000009865005": ("Veteran Crew", "ranged_reroll_hit_ones"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_calm_under_fire_issues_same_order_to_one_additional_squadron_once_per_turn(self):
        game, am_army, _enemy_army = _build_game()
        officer = _make_unit(
            "Tank Commander",
            keywords=["CHARACTER", "OFFICER", "VEHICLE", "SQUADRON"],
            faction_keywords=["ASTRA MILITARUM"],
            model_count=1,
            objective_control=2,
            wounds=10,
        )
        officer.possible_abilities = [
            _Ability("Voice of Command"),
            _Ability("Orders", "This model can issue 1 order to SQUADRON units within 6\"."),
        ]
        squadron_a = _make_unit("Squadron A", keywords=["VEHICLE", "SQUADRON"], faction_keywords=["ASTRA MILITARUM"], wounds=8)
        squadron_b = _make_unit("Squadron B", keywords=["VEHICLE", "SQUADRON"], faction_keywords=["ASTRA MILITARUM"], wounds=8)
        squadron_c = _make_unit("Squadron C", keywords=["VEHICLE", "SQUADRON"], faction_keywords=["ASTRA MILITARUM"], wounds=8)
        am_army.add_unit(officer)
        am_army.add_unit(squadron_a)
        am_army.add_unit(squadron_b)
        am_army.add_unit(squadron_c)
        for unit in (officer, squadron_a, squadron_b, squadron_c):
            _set_unit_position(unit, 0.0, float(len(getattr(am_army, "units", [])) or 0))
        game.map.units = [officer, squadron_a, squadron_b, squadron_c]
        game.rebuild_entity_registry()

        mgr = VoiceOfCommandManager(am_army)
        mgr._army_has_voice = lambda: True
        am_army.voice_of_command = mgr

        _apply_enhancement(officer, enhancement_id="000009865002", enhancement_name="Calm Under Fire")

        self.assertTrue(mgr.issue_order(game, officer, squadron_a, ORDER_MOVE.key, phase_name="COMMAND_PHASE"))
        self.assertEqual(mgr.orders_remaining(officer, int(getattr(game, "turn", 1) or 1)), 0)
        self.assertTrue(mgr.issue_order(game, officer, squadron_b, ORDER_MOVE.key, phase_name="COMMAND_PHASE"))
        self.assertFalse(mgr.issue_order(game, officer, squadron_c, ORDER_MOVE.key, phase_name="COMMAND_PHASE"))

        game.turn = 2
        self.assertTrue(mgr.issue_order(game, officer, squadron_c, ORDER_MOVE.key, phase_name="COMMAND_PHASE"))
        self.assertTrue(mgr.issue_order(game, officer, squadron_a, ORDER_MOVE.key, phase_name="COMMAND_PHASE"))

    def test_regimental_banner_adds_three_objective_control_to_bearer_model_only(self):
        game, am_army, _enemy_army = _build_game()
        officer = _make_unit(
            "Tank Commander",
            keywords=["CHARACTER", "OFFICER", "VEHICLE", "SQUADRON"],
            faction_keywords=["ASTRA MILITARUM"],
            model_count=2,
            objective_control=1,
            wounds=10,
        )
        am_army.add_unit(officer)
        _set_unit_position(officer, 0.0, 0.0)
        game.map.units = [officer]
        game.rebuild_entity_registry()

        _apply_enhancement(officer, enhancement_id="000009865004", enhancement_name="Regimental Banner")

        bearer = _bearer_model(officer)
        self.assertIsNotNone(bearer)
        non_bearer = next(model for model in list(officer.models or []) if model is not bearer)
        bearer_oc = int(officer.get_effective_model_characteristic(bearer, "objective_control") or 0)
        non_bearer_oc = int(officer.get_effective_model_characteristic(non_bearer, "objective_control") or 0)
        self.assertEqual(bearer_oc, 4)
        self.assertEqual(non_bearer_oc, 1)

    def test_veteran_crew_rerolls_hit_ones_for_ranged_attacks_only(self):
        game, am_army, enemy_army = _build_game()
        source = _make_unit(
            "Tank Commander",
            keywords=["CHARACTER", "OFFICER", "VEHICLE", "SQUADRON"],
            faction_keywords=["ASTRA MILITARUM"],
            model_count=1,
            wounds=10,
        )
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=3,
            toughness=4,
        )
        am_army.add_unit(source)
        enemy_army.add_unit(target)
        _set_unit_position(source, 0.0, 0.0)
        _set_unit_position(target, 12.0, 0.0)
        game.map.units = [source, target]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000009865005", enhancement_name="Veteran Crew")

        ranged_profile = _make_weapon_profile(weapon_type="ranged", skill="4+")
        melee_profile = _make_weapon_profile(weapon_type="melee", skill="4+")

        original_get_roll = wargear_module.get_roll
        rerolls = iter([4, 4])
        wargear_module.get_roll = lambda *_args, **_kwargs: next(rerolls)
        try:
            ranged_hit = ranged_profile._hit_target_with_tracking(
                target,
                source.models[0],
                {},
                roll_value=1,
                allow_rerolls=True,
                log_roll=False,
            )
            melee_hit = melee_profile._hit_target_with_tracking(
                target,
                source.models[0],
                {},
                roll_value=1,
                allow_rerolls=True,
                log_roll=False,
            )
        finally:
            wargear_module.get_roll = original_get_roll

        self.assertEqual(ranged_hit.get("reroll_of_one"), 1)
        self.assertEqual(ranged_hit.get("reroll"), 4)
        ranged_reasons = [str(v or "") for v in list(ranged_hit.get("reroll_value_reasons", []) or [])]
        self.assertTrue(any("Veteran Crew" in reason for reason in ranged_reasons))
        self.assertIsNone(melee_hit.get("reroll_of_one"))
        self.assertIsNone(melee_hit.get("reroll"))


if __name__ == "__main__":
    unittest.main()
