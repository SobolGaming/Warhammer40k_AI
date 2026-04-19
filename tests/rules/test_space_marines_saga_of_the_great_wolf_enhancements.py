import types
import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagems import StratagemManager
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        toughness: int = 4,
        wounds: int = 4,
        move: int = 6,
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
                "M": str(int(move)),
                "T": str(int(toughness)),
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    toughness: int = 4,
    wounds: int = 4,
    move: int = 6,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            toughness=toughness,
            wounds=wounds,
            move=move,
        )
    )


def _build_game(detachment_type: str = "Saga of the Great Wolf"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type)
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army, sm_player, enemy_player


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="SM",
        detachment="Saga of the Great Wolf",
        points=25,
        description="",
    ).apply_to_unit(unit)


def _find_redeploy_request(game: Game, *, player_id: str, ability_name: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        if str(getattr(req, "player_id", "") or "") != str(player_id):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability_name", "") or "") != str(ability_name):
            continue
        return req
    return None


def _set_unit_position(unit: Unit, x: float, y: float, *, spacing: float = 1.0) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(idx) * float(spacing), float(y), 0.0, 0.0)


def _make_melee_profile() -> WargearProfile:
    parent = types.SimpleNamespace(name="Frost Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "-1",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestSpaceMarinesSagaOfTheGreatWolfEnhancements(unittest.TestCase):
    def test_saga_of_the_great_wolf_enhancement_descriptors_exist(self):
        expected = {
            "000010660002": (
                "Grimnar's Mark",
                "zero_cp_target_bearer_unit_with_rapid_ingress_or_heroic_intervention_and_attach_to_wolf_guard_terminators",
            ),
            "000010660003": (
                "Howlmaw",
                "select_enemy_within_6_of_bearer_take_battleshock_with_minus_1_modifier",
            ),
            "000010660004": ("Chariots of the Storm", "redeploy_units"),
            "000010660005": ("Skjald's Foretelling", "grant_lance_to_weapons_of_models_in_bearer_led_unit"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_grimnars_mark_free_stratagem_from_battle_round_two_and_once_per_round(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Captain in Terminator Armour",
            keywords=["CHARACTER", "INFANTRY", "TERMINATOR", "CAPTAIN", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            model_count=1,
            wounds=6,
        )
        other = _make_unit(
            "Grey Hunters",
            keywords=["INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            model_count=1,
            wounds=4,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        sm_army.add_unit(bearer)
        sm_army.add_unit(other)
        enemy_army.add_unit(enemy)
        for unit in (bearer, other, enemy):
            unit.deployed = True
            unit.reserve_status = "deployed"
        game.map.units = [bearer, other, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(bearer, enhancement_id="000010660002", enhancement_name="Grimnar's Mark")
        rapid_ingress = types.SimpleNamespace(name="RAPID INGRESS", cp_cost=1)
        heroic = types.SimpleNamespace(name="HEROIC INTERVENTION", cp_cost=1)

        game.turn = 1
        before = sm_player.preview_stratagem_cp_cost(rapid_ingress, target_unit=bearer)
        self.assertEqual(int(before.get("cost", 0) or 0), 1)

        game.turn = 2
        preview = sm_player.preview_stratagem_cp_cost(rapid_ingress, target_unit=bearer)
        self.assertEqual(int(preview.get("cost", 0) or 0), 0)
        self.assertTrue(any("Grimnar's Mark" in str(r) for r in list(preview.get("reasons", []) or [])))

        sm_player.set_next_optional_decision("GRIMNARS_MARK_STRATAGEM_DISCOUNT", True)
        applied = sm_player.apply_stratagem_cp_cost(rapid_ingress, target_unit=bearer)
        self.assertEqual(int(applied.get("cost", 0) or 0), 0)
        second_same_round = sm_player.preview_stratagem_cp_cost(heroic, target_unit=bearer)
        self.assertEqual(int(second_same_round.get("cost", 0) or 0), 1)

        game.turn = 3
        preview_next_round = sm_player.preview_stratagem_cp_cost(heroic, target_unit=bearer)
        self.assertEqual(int(preview_next_round.get("cost", 0) or 0), 0)

        manager = StratagemManager(sm_player)
        manager._used_stratagems_this_phase.add("HEROIC INTERVENTION")
        manager._record_heroic_intervention_use(other)
        self.assertTrue(bool(manager._heroic_intervention_repeat_allowed(target_unit=bearer)))
        self.assertFalse(bool(manager._heroic_intervention_repeat_allowed(target_unit=other)))

        manager._used_stratagems_this_phase.add("RAPID INGRESS")
        manager._record_rapid_ingress_use(other)
        self.assertTrue(bool(manager._rapid_ingress_repeat_allowed(target_unit=bearer)))
        self.assertFalse(bool(manager._rapid_ingress_repeat_allowed(target_unit=other)))

    def test_grimnars_mark_bearer_can_attach_to_wolf_guard_terminators(self):
        _game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Captain in Terminator Armour",
            keywords=["CHARACTER", "INFANTRY", "TERMINATOR", "CAPTAIN", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            model_count=1,
            wounds=6,
        )
        wolf_guard_terminators = _make_unit(
            "Wolf Guard Terminators",
            keywords=["INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            model_count=5,
        )
        intercessors = _make_unit(
            "Intercessor Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=5,
        )
        for unit in (bearer, wolf_guard_terminators, intercessors):
            sm_army.add_unit(unit)
        bearer.can_be_attached_to = ["INTERCESSOR-SQUAD"]

        _apply_enhancement(bearer, enhancement_id="000010660002", enhancement_name="Grimnar's Mark")
        self.assertTrue(bool(bearer.can_attach_to(wolf_guard_terminators)))
        self.assertFalse(bool(bearer.can_attach_to(intercessors)))

    def test_howlmaw_queues_start_of_fight_choice_and_applies_minus_one_battleshock(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Wolf Priest",
            keywords=["CHARACTER", "INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            model_count=1,
            wounds=5,
        )
        enemy_near = _make_unit(
            "Enemy Near",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
        )
        enemy_far = _make_unit(
            "Enemy Far",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
        )
        sm_army.add_unit(source)
        enemy_army.add_unit(enemy_near)
        enemy_army.add_unit(enemy_far)
        for unit in (source, enemy_near, enemy_far):
            unit.deployed = True
            unit.reserve_status = "deployed"
        _set_unit_position(source, 10.0, 10.0)
        _set_unit_position(enemy_near, 15.0, 10.0)
        _set_unit_position(enemy_far, 18.0, 10.0)
        game.map.units = [source, enemy_near, enemy_far]
        game.rebuild_entity_registry()

        _apply_enhancement(source, enhancement_id="000010660003", enhancement_name="Howlmaw")
        game.phase = BattleRoundPhases.FIGHT_PHASE
        game.current_player_index = 0

        game.event_system.publish("phase_start", player=sm_player, phase=BattleRoundPhases.FIGHT_PHASE)
        requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "charge_end_select_one_battleshock"
            and str((getattr(req, "context", {}) or {}).get("ability_name", "") or "") == "Howlmaw"
        ]
        self.assertEqual(len(requests), 1)
        request = requests[0]

        option_target_ids = {
            str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
            for opt in list(getattr(request, "options", []) or [])
        }
        self.assertIn(str(get_entity_id(enemy_near) or ""), option_target_ids)
        self.assertNotIn(str(get_entity_id(enemy_far) or ""), option_target_ids)

        called = {"count": 0}

        def _fake_take_battleshock(self, _turn):
            called["count"] += 1
            return False

        enemy_near.take_battle_shock_test = types.MethodType(_fake_take_battleshock, enemy_near)
        target_option_id = next(
            opt.option_id
            for opt in list(getattr(request, "options", []) or [])
            if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
            == str(get_entity_id(enemy_near) or "")
        )
        result = resolve_decision_command(game, request, target_option_id, player_id=sm_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertEqual(int(called["count"]), 1)

        sr = getattr(enemy_near, "special_rules", None)
        self.assertIsInstance(sr, dict)
        self.assertEqual(int(sr.get("battle_shock_test_modifier", 0) or 0), -1)
        reasons = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
        self.assertTrue(any("Howlmaw" in str(reason) for reason in reasons))

    def test_chariots_of_the_storm_redeploy_filters_to_adeptus_astartes(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Wolf Lord",
            keywords=["CHARACTER", "INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        )
        astartes_target = _make_unit(
            "Astartes Target",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        allied_target = _make_unit(
            "Allied Target",
            keywords=["INFANTRY"],
            faction_keywords=["AGENTS OF THE IMPERIUM"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        for unit in (source, astartes_target, allied_target):
            sm_army.add_unit(unit)
        enemy_army.add_unit(enemy)
        for unit in (source, astartes_target, allied_target, enemy):
            unit.deployed = True
            unit.reserve_status = "deployed"
        game.map.units = [source, astartes_target, allied_target, enemy]
        game.rebuild_entity_registry()
        game.attacker_index = 0
        game.defender_index = 1

        _apply_enhancement(source, enhancement_id="000010660004", enhancement_name="Chariots of the Storm")
        game.execute_redeploy_units_phase()

        request = _find_redeploy_request(game, player_id=sm_player.id, ability_name="Chariots of the Storm")
        self.assertIsNotNone(request)
        target_ids = {
            str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
            for opt in list(getattr(request, "options", []) or [])
        }
        self.assertIn(str(get_entity_id(astartes_target) or ""), target_ids)
        self.assertNotIn(str(get_entity_id(allied_target) or ""), target_ids)

        reserve_option_id = next(
            opt.option_id
            for opt in list(getattr(request, "options", []) or [])
            if (
                str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
                == str(get_entity_id(astartes_target) or "")
                and str((dict(getattr(opt, "payload", {}) or {}).get("redeploy_action", "") or "").lower())
                == "strategic_reserves"
            )
        )
        result = resolve_decision_command(game, request, reserve_option_id, player_id=sm_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))
        self.assertTrue(astartes_target.is_in_strategic_reserves())

    def test_skjalds_foretelling_grants_lance_only_while_bearer_is_leading(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        leader = _make_unit(
            "Wolf Guard Battle Leader",
            keywords=["CHARACTER", "INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            model_count=1,
            wounds=5,
        )
        bodyguard = _make_unit(
            "Grey Hunters",
            keywords=["INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
            model_count=2,
            wounds=4,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=6,
        )
        leader._datasheet.id = "WG-BL"
        bodyguard._datasheet.id = "GREY-HUNTERS"
        leader.can_be_attached_to = ["GREY-HUNTERS"]
        sm_army.add_unit(leader)
        sm_army.add_unit(bodyguard)
        enemy_army.add_unit(enemy)
        for unit in (leader, bodyguard, enemy):
            unit.deployed = True
            unit.reserve_status = "deployed"
        game.map.units = [leader, bodyguard, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(leader, enhancement_id="000010660005", enhancement_name="Skjald's Foretelling")
        profile = _make_melee_profile()

        leader.round_state.charged_this_round = True
        attack_instance_no_lead = {}
        profile._hit_target_with_tracking(
            enemy,
            leader.models[0],
            attack_instance_no_lead,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        wound_no_lead = profile._wound_target_with_tracking(
            enemy,
            leader.models[0],
            attack_instance_no_lead,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(any("Skjald's Foretelling" in str(note) for note in list(wound_no_lead.get("modifiers", []) or [])))

        self.assertTrue(bool(leader.can_attach_to(bodyguard)))
        leader.attach_to_unit(bodyguard)
        bodyguard.round_state.charged_this_round = True
        attack_instance_leading = {}
        profile._hit_target_with_tracking(
            enemy,
            bodyguard.models[0],
            attack_instance_leading,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        wound_leading = profile._wound_target_with_tracking(
            enemy,
            bodyguard.models[0],
            attack_instance_leading,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("Skjald's Foretelling" in str(note) for note in list(wound_leading.get("modifiers", []) or [])))


if __name__ == "__main__":
    unittest.main()
