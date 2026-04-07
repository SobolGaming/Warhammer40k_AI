import unittest

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
        toughness: int = 4,
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
    toughness: int = 4,
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
    am_army = Army.with_detachment("Astra Militarum", "Combined Arms")
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    am_player = Player("Astra Militarum", control=PlayerControl.REMOTE, army=am_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, am_army, enemy_army, am_player, enemy_player


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        if not bool(getattr(model, "is_alive", False)):
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)
    unit.position = (float(x), float(y), 0.0)
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    bodyguard._ability_cache = {}
    leader._ability_cache = {}


def _make_ranged_profile(skill: str = "4+") -> WargearProfile:
    parent = type(
        "_ParentWargear",
        (),
        {
            "name": "Test Rifle",
            "is_melee": lambda self: False,
            "is_ranged": lambda self: True,
        },
    )()
    data = {
        "range": "24",
        "A": "1",
        "BS_WS": str(skill),
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            return model
    for model in list(getattr(unit, "models", []) or []):
        if bool(getattr(model, "is_alive", False)):
            return model
    return None


class TestAstraMilitarumCombinedArmsEnhancements(unittest.TestCase):
    def test_combined_arms_enhancement_descriptors_exist(self):
        expected = {
            "000008380002": ("Death Mask of Ollanius", "battleshock_objective_control_subtract_instead_of_zero"),
            "000008380003": ("Drill Commander", "ranged_critical_hits_on_5plus"),
            "000008380004": ("Grand Strategist", "additional_orders"),
            "000008380005": ("Reactive Command", "issue_order_without_consuming_order_count"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_death_mask_of_ollanius_replaces_battleshock_zero_oc_with_minus_one(self):
        game, am_army, _enemy_army, _am_player, _enemy_player = _build_game()
        bodyguard = _make_unit(
            "Infantry Squad",
            keywords=["INFANTRY", "REGIMENT"],
            faction_keywords=["ASTRA MILITARUM"],
            model_count=2,
            objective_control=2,
            wounds=2,
        )
        leader = _make_unit(
            "Cadian Castellan",
            keywords=["CHARACTER", "OFFICER", "INFANTRY", "REGIMENT"],
            faction_keywords=["ASTRA MILITARUM"],
            model_count=1,
            objective_control=1,
            wounds=4,
        )
        am_army.add_unit(bodyguard)
        am_army.add_unit(leader)
        _attach_leader(bodyguard, leader)
        _set_unit_position(bodyguard, 10.0, 10.0)
        _set_unit_position(leader, 10.1, 10.0)
        game.map.units = [bodyguard, leader]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008380002",
            name="Death Mask of Ollanius",
            faction_id="AM",
            detachment="Combined Arms",
            points=10,
            description="",
        ).apply_to_unit(leader)

        model = bodyguard.models[0]
        bodyguard._apply_battle_shock_outcome(
            passed=False,
            current_turn=int(getattr(game, "turn", 1) or 1),
            was_battle_shocked=False,
            shadow_ctx=None,
            game=game,
            event_system=getattr(game, "event_system", None),
        )
        oc_while_bearer_alive = int(bodyguard.get_effective_model_characteristic(model, "objective_control") or 0)
        self.assertEqual(oc_while_bearer_alive, 1)

        bearer = _bearer_model(leader)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        oc_after_bearer_destroyed = int(bodyguard.get_effective_model_characteristic(model, "objective_control") or 0)
        self.assertEqual(oc_after_bearer_destroyed, 0)

    def test_drill_commander_sets_ranged_critical_hit_threshold_while_stationary(self):
        game, am_army, enemy_army, _am_player, _enemy_player = _build_game()
        bodyguard = _make_unit(
            "Infantry Squad",
            keywords=["INFANTRY", "REGIMENT"],
            faction_keywords=["ASTRA MILITARUM"],
            model_count=2,
            objective_control=2,
            wounds=2,
        )
        leader = _make_unit(
            "Platoon Commander",
            keywords=["CHARACTER", "OFFICER", "INFANTRY", "REGIMENT"],
            faction_keywords=["ASTRA MILITARUM"],
            model_count=1,
            objective_control=1,
            wounds=4,
        )
        target = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            objective_control=1,
            wounds=3,
        )
        am_army.add_unit(bodyguard)
        am_army.add_unit(leader)
        enemy_army.add_unit(target)
        _attach_leader(bodyguard, leader)
        _set_unit_position(bodyguard, 0.0, 0.0)
        _set_unit_position(leader, 0.1, 0.0)
        _set_unit_position(target, 12.0, 0.0)
        game.map.units = [bodyguard, leader, target]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008380003",
            name="Drill Commander",
            faction_id="AM",
            detachment="Combined Arms",
            points=20,
            description="",
        ).apply_to_unit(leader)

        profile = _make_ranged_profile(skill="4+")
        bodyguard.round_state.remained_stationary_this_round = True
        stationary_attack = {"damage_characteristic": 1}
        stationary_hit = profile._hit_target_with_tracking(
            target,
            bodyguard.models[0],
            stationary_attack,
            roll_value=5,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertEqual(int(stationary_hit.get("crit_threshold", 0) or 0), 5)
        self.assertTrue(bool(stationary_attack.get("crit_hit", False)))

        bodyguard.round_state.remained_stationary_this_round = False
        moving_attack = {"damage_characteristic": 1}
        moving_hit = profile._hit_target_with_tracking(
            target,
            bodyguard.models[0],
            moving_attack,
            roll_value=5,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertEqual(int(moving_hit.get("crit_threshold", 0) or 0), 6)
        self.assertFalse(bool(moving_attack.get("crit_hit", False)))

    def test_grand_strategist_adds_one_order(self):
        game, am_army, _enemy_army, _am_player, _enemy_player = _build_game()
        officer = _make_unit(
            "Company Commander",
            keywords=["CHARACTER", "OFFICER", "INFANTRY", "REGIMENT"],
            faction_keywords=["ASTRA MILITARUM"],
            model_count=1,
            objective_control=1,
            wounds=4,
        )
        officer.possible_abilities = [
            _Ability("Voice of Command"),
            _Ability("Orders", "This model can issue 1 order to REGIMENT units within 6\"."),
        ]
        am_army.add_unit(officer)
        _set_unit_position(officer, 0.0, 0.0)
        game.map.units = [officer]
        game.rebuild_entity_registry()

        mgr = VoiceOfCommandManager(am_army)
        mgr._army_has_voice = lambda: True
        am_army.voice_of_command = mgr

        Enhancement(
            id="000008380004",
            name="Grand Strategist",
            faction_id="AM",
            detachment="Combined Arms",
            points=15,
            description="",
        ).apply_to_unit(officer)

        self.assertEqual(mgr.orders_remaining(officer, int(getattr(game, "turn", 1) or 1)), 2)

    def test_reactive_command_order_does_not_consume_base_order(self):
        game, am_army, enemy_army, _am_player, _enemy_player = _build_game()
        officer = _make_unit(
            "Company Commander",
            keywords=["CHARACTER", "OFFICER", "INFANTRY", "REGIMENT"],
            faction_keywords=["ASTRA MILITARUM"],
            model_count=1,
            objective_control=1,
            wounds=4,
        )
        officer.possible_abilities = [
            _Ability("Voice of Command"),
            _Ability("Orders", "This model can issue 1 order to REGIMENT units within 6\"."),
        ]
        target_a = _make_unit(
            "Infantry Squad A",
            keywords=["INFANTRY", "REGIMENT"],
            faction_keywords=["ASTRA MILITARUM"],
            model_count=1,
            objective_control=1,
            wounds=2,
        )
        target_b = _make_unit(
            "Infantry Squad B",
            keywords=["INFANTRY", "REGIMENT"],
            faction_keywords=["ASTRA MILITARUM"],
            model_count=1,
            objective_control=1,
            wounds=2,
        )
        enemy = _make_unit(
            "Enemy Reserves Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            objective_control=1,
            wounds=2,
        )
        am_army.add_unit(officer)
        am_army.add_unit(target_a)
        am_army.add_unit(target_b)
        enemy_army.add_unit(enemy)
        _set_unit_position(officer, 0.0, 0.0)
        _set_unit_position(target_a, 3.0, 0.0)
        _set_unit_position(target_b, 4.0, 0.0)
        _set_unit_position(enemy, 8.0, 0.0)
        game.map.units = [officer, target_a, target_b, enemy]
        game.rebuild_entity_registry()

        mgr = VoiceOfCommandManager(am_army)
        mgr._army_has_voice = lambda: True
        am_army.voice_of_command = mgr

        Enhancement(
            id="000008380005",
            name="Reactive Command",
            faction_id="AM",
            detachment="Combined Arms",
            points=15,
            description="",
        ).apply_to_unit(officer)

        triggered = mgr.register_reactive_command_enemy_set_up(enemy, game=game)
        self.assertIn(officer, triggered)

        reactive_ok = mgr.issue_order(
            game,
            officer,
            target_a,
            ORDER_MOVE.key,
            phase_name="MOVEMENT_PHASE",
            trigger="reactive_command_setup",
        )
        self.assertTrue(reactive_ok)
        self.assertEqual(str(target_a.special_rules.get("voice_of_command_order_key", "") or ""), ORDER_MOVE.key)
        self.assertEqual(mgr.orders_remaining(officer, int(getattr(game, "turn", 1) or 1)), 1)

        command_ok = mgr.issue_order(
            game,
            officer,
            target_b,
            ORDER_MOVE.key,
            phase_name="COMMAND_PHASE",
            trigger="command_phase_start",
        )
        self.assertTrue(command_ok)
        self.assertEqual(mgr.orders_remaining(officer, int(getattr(game, "turn", 1) or 1)), 0)


if __name__ == "__main__":
    unittest.main()
