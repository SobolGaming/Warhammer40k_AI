import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(self, name, *, keywords=None, faction_keywords=None, save=3, wounds=6):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "10",
                "Sv": str(save),
                "W": str(wounds),
                "Ld": "7",
                "OC": "5",
                "base_size": "100mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None, save=3, wounds=6):
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            save=save,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.round_state.shot_this_round = False
    return unit


class _MapStub:
    def get_friendly_units(self, unit):
        army = unit.get_parent_army() if unit is not None else None
        return list(getattr(army, "units", []) or []) if army is not None else []

    def get_enemy_units(self, _unit):
        return []

    def get_distance_between_units(self, _a, _b):
        return 12.0

    def is_within_engagement_range(self, _a, _b):
        return False


class _GameStub:
    def __init__(self, active_player, phase_name: str):
        from warhammer40k_ai.engine.decisions import DecisionQueue
        from warhammer40k_ai.engine.event.system import EventSystem

        self.event_system = EventSystem()
        self.decision_queue = DecisionQueue()
        self._current_player = active_player
        self.turn = 1
        self.phase = SimpleNamespace(name=phase_name)
        self.map = _MapStub()
        self.players = []
        self.is_authoritative = True

    def get_current_player(self):
        return self._current_player

    def request_decision(self, request):
        self.decision_queue.add(request)

    def _queue_reactive_move_movement_decision(
        self,
        *,
        player,
        unit,
        max_distance: int,
        kind: str,
        movement_type: str,
        source: str | None,
        moving_unit=None,
        attacker_unit=None,
        range_value: int | None = None,
        allow_engagement_range: bool | None = None,
        allowed_model_ids: list[str] | None = None,
        allow_skip: bool | None = None,
    ):
        from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
        from warhammer40k_ai.utility.entity_ids import maybe_entity_id

        unit_id = maybe_entity_id(unit)
        moving_unit_id = maybe_entity_id(moving_unit) if moving_unit is not None else None
        attacker_unit_id = maybe_entity_id(attacker_unit) if attacker_unit is not None else None
        ctx = {
            "reactive_move_kind": str(kind or "reactive"),
            "reactive_move_unit_id": unit_id,
            "reactive_move_source": str(source or "Reactive Move"),
            "movement_type": str(movement_type or "reactive"),
            "unit_id": unit_id,
            "max_distance": int(max_distance),
        }
        if moving_unit_id:
            ctx["reactive_move_moving_unit_id"] = moving_unit_id
        if attacker_unit_id:
            ctx["reactive_move_attacker_unit_id"] = attacker_unit_id
        if range_value is not None:
            ctx["reactive_move_range"] = int(range_value)
        if allow_engagement_range is not None:
            ctx["reactive_move_allow_engagement_range"] = bool(allow_engagement_range)
        if allowed_model_ids is not None:
            ctx["allowed_model_ids"] = list(allowed_model_ids)
        if allow_skip is not None:
            ctx["allow_skip"] = bool(allow_skip)

        req = DecisionRequest.create(
            DECISION_MOVE_UNIT,
            f"Move {getattr(unit, 'name', 'Unit')} ({movement_type})",
            player_id=getattr(player, "id", None),
            options=[
                DecisionOption.create("Confirm", payload={"unit_id": unit_id, "action": "confirm"}),
                DecisionOption.create("Skip", payload={"unit_id": unit_id, "action": "skip"}),
            ],
            context=ctx,
        )
        self.request_decision(req)
        return req


class TestImperialKnightsValourstrikeStratagems(unittest.TestCase):
    def _setup_env(self, *, phase_name: str, active_is_player: bool):
        ik_army = Army("Imperial Knights", detachment_type="Valourstrike Lance")
        ik_army.faction_id = "QI"
        enemy_army = Army("Enemy", detachment_type="Other")
        enemy_army.faction_id = "EN"

        ik_player = Player("IK", control=PlayerControl.LOCAL, army=ik_army)
        enemy_player = Player("EN", control=PlayerControl.LOCAL, army=enemy_army)
        active_player = ik_player if active_is_player else enemy_player
        game = _GameStub(active_player=active_player, phase_name=phase_name)
        game.players = [ik_player, enemy_player]

        ik_player.set_game(game)
        enemy_player.set_game(game)
        ik_player.command_points = 5
        enemy_player.command_points = 5

        knight = _make_unit(
            "Knight",
            keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
            faction_keywords=["IMPERIUM"],
            save=3,
            wounds=12,
        )
        enemy = _make_unit(
            "Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            save=3,
            wounds=3,
        )
        ik_army.add_unit(knight)
        enemy_army.add_unit(enemy)
        return ik_player, enemy_player, game, knight, enemy

    def test_vow_of_retribution_grants_ranged_lethal_hits(self):
        ik_player, _enemy_player, _game, knight, enemy = self._setup_env(
            phase_name="SHOOTING_PHASE",
            active_is_player=True,
        )

        before_cp = int(ik_player.command_points)
        ok = ik_player.stratagems.use("VOW OF RETRIBUTION", unit=knight, phase_name="Shooting phase")
        self.assertTrue(ok)
        self.assertEqual(int(ik_player.command_points), before_cp - 1)

        weapon = Wargear(
            {
                "name": "Rapid-Fire Cannon",
                "type": "Ranged",
                "range": "36",
                "A": "1",
                "BS_WS": "3+",
                "S": "9",
                "AP": "-2",
                "D": "3",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        attack_instance = {}
        hit = profile._hit_target_with_tracking(
            enemy,
            knight.models[0],
            attack_instance,
            roll_value=6,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(hit.get("hit"))
        self.assertTrue(bool(attack_instance.get("lethal_hit")))
        self.assertIn("Lethal Hits", list(hit.get("special_effects", []) or []))

    def test_full_tilt_grants_move_and_advance_bonus_until_phase_end(self):
        ik_player, _enemy_player, game, knight, _enemy = self._setup_env(
            phase_name="MOVEMENT_PHASE",
            active_is_player=True,
        )
        base_move = int(knight.movement)

        before_cp = int(ik_player.command_points)
        ok = ik_player.stratagems.use("FULL TILT", unit=knight, phase_name="Movement phase")
        self.assertTrue(ok)
        self.assertEqual(int(ik_player.command_points), before_cp - 2)
        self.assertEqual(int(knight.movement), base_move + 2)

        adv_mods = list(knight._collect_advance_roll_modifiers() or [])
        self.assertTrue(any(int(v or 0) == 2 and "FULL TILT" in str(src or "").upper() for v, src in adv_mods))

        game.event_system.publish("phase_end", player=ik_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
        self.assertEqual(int(knight.movement), base_move)
        adv_mods_after = list(knight._collect_advance_roll_modifiers() or [])
        self.assertFalse(any("FULL TILT" in str(src or "").upper() for _v, src in adv_mods_after))

    def test_full_tilt_rejects_unit_already_selected_to_move(self):
        ik_player, _enemy_player, _game, knight, _enemy = self._setup_env(
            phase_name="MOVEMENT_PHASE",
            active_is_player=True,
        )
        knight.round_state.moved_this_round = True

        before_cp = int(ik_player.command_points)
        ok = ik_player.stratagems.use("FULL TILT", unit=knight, phase_name="Movement phase")
        self.assertFalse(ok)
        self.assertEqual(int(ik_player.command_points), before_cp)

    def test_run_them_through_grants_melee_lance_until_phase_end(self):
        ik_player, _enemy_player, game, knight, enemy = self._setup_env(
            phase_name="FIGHT_PHASE",
            active_is_player=True,
        )
        knight.round_state.charged_this_round = True
        weapon = Wargear(
            {
                "name": "Knight Blade",
                "type": "Melee",
                "range": "Melee",
                "A": "2",
                "BS_WS": "3+",
                "S": "8",
                "AP": "-2",
                "D": "3",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]

        before = profile._wound_target_with_tracking(
            enemy,
            knight.models[0],
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(before.get("wound")))

        before_cp = int(ik_player.command_points)
        ok = ik_player.stratagems.use("RUN THEM THROUGH!", unit=knight, phase_name="Fight phase")
        self.assertTrue(ok)
        self.assertEqual(int(ik_player.command_points), before_cp - 1)

        during = profile._wound_target_with_tracking(
            enemy,
            knight.models[0],
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(during.get("wound")))
        self.assertTrue(any("RUN THEM THROUGH" in str(m or "").upper() for m in list(during.get("modifiers", []) or [])))

        game.event_system.publish("phase_end", player=ik_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
        after = profile._wound_target_with_tracking(
            enemy,
            knight.models[0],
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(after.get("wound")))

    def test_thunderstomp_sets_feet_attacks_and_improves_ap_until_phase_end(self):
        ik_player, _enemy_player, game, knight, enemy = self._setup_env(
            phase_name="FIGHT_PHASE",
            active_is_player=True,
        )
        armoured_feet = Wargear(
            {
                "name": "Armoured Feet",
                "type": "Melee",
                "range": "Melee",
                "A": "4",
                "BS_WS": "3+",
                "S": "8",
                "AP": "-1",
                "D": "2",
                "description": "",
            }
        )
        titanic_feet = Wargear(
            {
                "name": "Titanic Feet",
                "type": "Melee",
                "range": "Melee",
                "A": "6",
                "BS_WS": "3+",
                "S": "10",
                "AP": "-2",
                "D": "3",
                "description": "",
            }
        )
        non_feet = Wargear(
            {
                "name": "Reaper Chainsword",
                "type": "Melee",
                "range": "Melee",
                "A": "3",
                "BS_WS": "3+",
                "S": "14",
                "AP": "-1",
                "D": "6",
                "description": "",
            }
        )
        armoured_profile = armoured_feet.profiles["default"]
        titanic_profile = titanic_feet.profiles["default"]
        non_feet_profile = non_feet.profiles["default"]
        knight.models[0].wargear = [armoured_feet, titanic_feet, non_feet]

        before_armoured_ap = int(armoured_profile.get_effective_ap(knight.models[0], enemy))
        before_titanic_ap = int(titanic_profile.get_effective_ap(knight.models[0], enemy))
        before_non_feet_ap = int(non_feet_profile.get_effective_ap(knight.models[0], enemy))

        before_armoured = armoured_profile.attack(enemy, knight.models[0], game_map=game.map)
        before_titanic = titanic_profile.attack(enemy, knight.models[0], game_map=game.map)
        self.assertIsNotNone(before_armoured)
        self.assertIsNotNone(before_titanic)
        self.assertEqual(int(before_armoured.attacks_rolled), 4)
        self.assertEqual(int(before_titanic.attacks_rolled), 6)
        self.assertEqual(before_armoured_ap, -1)
        self.assertEqual(before_titanic_ap, -2)
        self.assertEqual(before_non_feet_ap, -1)

        before_cp = int(ik_player.command_points)
        ok = ik_player.stratagems.use(
            "THUNDERSTOMP",
            unit=knight,
            model=knight.models[0],
            phase_name="Fight phase",
        )
        self.assertTrue(ok)
        self.assertEqual(int(ik_player.command_points), before_cp - 1)

        during_armoured = armoured_profile.attack(enemy, knight.models[0], game_map=game.map)
        during_titanic = titanic_profile.attack(enemy, knight.models[0], game_map=game.map)
        during_non_feet = non_feet_profile.attack(enemy, knight.models[0], game_map=game.map)
        self.assertIsNotNone(during_armoured)
        self.assertIsNotNone(during_titanic)
        self.assertIsNotNone(during_non_feet)
        self.assertEqual(int(during_armoured.attacks_rolled), 8)
        self.assertEqual(int(during_titanic.attacks_rolled), 12)
        self.assertEqual(int(during_non_feet.attacks_rolled), 3)
        self.assertEqual(int(armoured_profile.get_effective_ap(knight.models[0], enemy)), -2)
        self.assertEqual(int(titanic_profile.get_effective_ap(knight.models[0], enemy)), -3)
        self.assertEqual(int(non_feet_profile.get_effective_ap(knight.models[0], enemy)), -1)

        game.event_system.publish("phase_end", player=ik_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
        after_armoured = armoured_profile.attack(enemy, knight.models[0], game_map=game.map)
        self.assertIsNotNone(after_armoured)
        self.assertEqual(int(after_armoured.attacks_rolled), 4)
        self.assertEqual(int(armoured_profile.get_effective_ap(knight.models[0], enemy)), -1)

    def test_thunderstomp_rejects_unit_already_selected_to_fight(self):
        ik_player, _enemy_player, _game, knight, _enemy = self._setup_env(
            phase_name="FIGHT_PHASE",
            active_is_player=True,
        )
        knight.round_state.fought_this_phase = True

        before_cp = int(ik_player.command_points)
        ok = ik_player.stratagems.use("THUNDERSTOMP", unit=knight, model=knight.models[0], phase_name="Fight phase")
        self.assertFalse(ok)
        self.assertEqual(int(ik_player.command_points), before_cp)

    def test_tactical_foil_queues_reaction_and_creates_reactive_move_decision(self):
        from warhammer40k_ai.utility import dice as dice_module

        ik_player, enemy_player, game, knight, enemy = self._setup_env(
            phase_name="MOVEMENT_PHASE",
            active_is_player=False,
        )
        game.map.get_distance_between_units = lambda _a, _b: 8.0

        phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.phase = phase
        game.event_system.publish("phase_start", player=enemy_player, phase=phase)

        game.event_system.publish("unit_move_ended", unit=enemy, action="move")
        pending = [r for r in list(ik_player.stratagems.get_pending_reactions() or []) if r.get("stratagem") == "TACTICAL FOIL"]
        self.assertTrue(pending)

        before_cp = int(ik_player.command_points)
        original_roll = dice_module.get_roll
        dice_module.get_roll = lambda _d: 4
        try:
            ok = ik_player.stratagems.use("TACTICAL FOIL", phase_name="Movement phase", dequeue=True)
        finally:
            dice_module.get_roll = original_roll
        self.assertTrue(ok)
        self.assertEqual(int(ik_player.command_points), before_cp - 1)

        pending_moves = [
            req
            for req in list(game.decision_queue.list() or [])
            if getattr(req, "decision_type", None) == DECISION_MOVE_UNIT
        ]
        self.assertTrue(pending_moves)
        ctx = dict(getattr(pending_moves[0], "context", {}) or {})
        self.assertEqual(int(ctx.get("max_distance", 0) or 0), 4)
        self.assertEqual(str(ctx.get("movement_type", "") or ""), "reactive")
        self.assertEqual(str(ctx.get("reactive_move_kind", "") or ""), "tactical_foil")

    def test_vow_of_retribution_rejects_unit_that_already_shot(self):
        ik_player, _enemy_player, _game, knight, _enemy = self._setup_env(
            phase_name="SHOOTING_PHASE",
            active_is_player=True,
        )
        knight.round_state.shot_this_round = True

        before_cp = int(ik_player.command_points)
        ok = ik_player.stratagems.use("VOW OF RETRIBUTION", unit=knight, phase_name="Shooting phase")
        self.assertFalse(ok)
        self.assertEqual(int(ik_player.command_points), before_cp)

    def test_rotate_ion_shields_is_supported_by_generic_defensive_reaction(self):
        ik_player, _enemy_player, _game, knight, enemy = self._setup_env(
            phase_name="SHOOTING_PHASE",
            active_is_player=False,
        )

        before_cp = int(ik_player.command_points)
        ok = ik_player.stratagems.use(
            "ROTATE ION SHIELDS",
            unit=knight,
            attacker_unit=enemy,
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)
        self.assertEqual(int(ik_player.command_points), before_cp - 1)

        weapon = Wargear(
            {
                "name": "Anti-Tank Rifle",
                "type": "Ranged",
                "range": "48",
                "A": "1",
                "BS_WS": "3+",
                "S": "12",
                "AP": "-3",
                "D": "3",
                "description": "",
            }
        )
        profile = weapon.profiles["default"]
        save_result = profile._save_with_tracking(knight.models[0], {}, -3)
        self.assertEqual(save_result.get("save_type"), "invulnerable")
        self.assertEqual(int(save_result.get("final_save", 0) or 0), 4)

    def test_valourstrike_stratagem_descriptors_registered(self):
        run_them_through = get_stratagem_tool_descriptor(stratagem_id="000010494002")
        self.assertIsNotNone(run_them_through)
        self.assertEqual(run_them_through.effect, "melee_weapons_gain_lance")
        self.assertEqual(str(run_them_through.effect_params.get("keyword", "") or "").upper(), "LANCE")

        thunderstomp = get_stratagem_tool_descriptor(stratagem_id="000010494003")
        self.assertIsNotNone(thunderstomp)
        self.assertEqual(thunderstomp.effect, "feet_weapon_attacks_set_and_ap_bonus")
        self.assertEqual(int(thunderstomp.effect_params.get("armoured_feet_attacks", 0) or 0), 8)
        self.assertEqual(int(thunderstomp.effect_params.get("titanic_feet_attacks", 0) or 0), 12)
        self.assertEqual(int(thunderstomp.effect_params.get("ap_bonus", 0) or 0), 1)

        full_tilt = get_stratagem_tool_descriptor(stratagem_id="000010494004")
        self.assertIsNotNone(full_tilt)
        self.assertEqual(full_tilt.effect, "movement_and_advance_bonus")
        self.assertEqual(int(full_tilt.effect_params.get("move_bonus", 0) or 0), 2)
        self.assertEqual(int(full_tilt.effect_params.get("advance_roll_bonus", 0) or 0), 2)

        vow = get_stratagem_tool_descriptor(stratagem_id="000010494005")
        self.assertIsNotNone(vow)
        self.assertEqual(vow.effect, "ranged_lethal_hits")
        self.assertEqual(int(vow.cp_cost), 1)

        tactical = get_stratagem_tool_descriptor(stratagem_id="000010494006")
        self.assertIsNotNone(tactical)
        self.assertEqual(tactical.effect, "reactive_normal_move")
        self.assertEqual(str(tactical.effect_params.get("distance_roll", "") or "").upper(), "D6")

        rotate = get_stratagem_tool_descriptor(stratagem_id="000010494007")
        self.assertIsNotNone(rotate)
        self.assertEqual(rotate.effect, "invulnerable_save")
        self.assertEqual(int(rotate.effect_params.get("invulnerable_save", 0) or 0), 4)


if __name__ == "__main__":
    unittest.main()
