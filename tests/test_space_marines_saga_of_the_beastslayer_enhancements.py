import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
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
        objective_control: int = 1,
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
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    objective_control: int = 1,
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
            objective_control=objective_control,
            toughness=toughness,
            wounds=wounds,
            move=move,
        )
    )


def _build_game(detachment_type: str = "Saga of the Beastslayer"):
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
    return game, sm_army, enemy_army, sm_player, enemy_player


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="SM",
        detachment="Saga of the Beastslayer",
        points=25,
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


def _find_request(game: Game, *, decision_type: str, ability: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability):
            return req
    return None


def _first_yes_option(request):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if bool(payload.get("choice", False)):
            return option
    return None


def _make_melee_profile(*, ap: int = -1):
    parent = SimpleNamespace(name="Chainsword", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "5",
            "AP": str(int(ap)),
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_ranged_profile(*, ap: int = -2):
    parent = SimpleNamespace(name="Bolt Rifle", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": str(int(ap)),
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestSpaceMarinesSagaOfTheBeastslayerEnhancements(unittest.TestCase):
    def test_saga_of_the_beastslayer_enhancement_descriptors_exist(self):
        expected = {
            "000010269002": ("Wolf-touched", "bearer_move_bonus_and_attach_to_wulfen_infantry"),
            "000010269003": ("Hunter's Guile", "redeploy_units"),
            "000010269004": (
                "Elder's Guidance",
                "once_per_battle_start_of_fight_phase_melee_ap_bonus_for_bearer_led_blood_claws_unit",
            ),
            "000010269005": (
                "Helm of the Beastslayer",
                "ap_worsen_against_character_monster_vehicle_attacks_targeting_bearer_unit",
            ),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_wolf_touched_adds_bearer_move_and_allows_attachment_to_wulfen_infantry(self):
        _game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        bearer = _make_unit(
            "Wolf Guard Leader",
            keywords=["CHARACTER", "INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            move=6,
        )
        bearer.can_be_attached_to = ["WULFEN"]
        wulfen = _make_unit(
            "Wulfen",
            keywords=["WULFEN", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=5,
        )
        non_wulfen = _make_unit(
            "Grey Hunters",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=5,
        )
        sm_army.add_unit(bearer)
        sm_army.add_unit(wulfen)
        sm_army.add_unit(non_wulfen)

        _apply_enhancement(bearer, enhancement_id="000010269002", enhancement_name="Wolf-touched")
        bearer_model = _bearer_model(bearer)
        self.assertIsNotNone(bearer_model)
        move = bearer.get_effective_model_characteristic(bearer_model, "movement")
        self.assertEqual(int(move or 0), 8)
        self.assertTrue(bool(bearer.can_attach_to(wulfen)))
        self.assertFalse(bool(bearer.can_attach_to(non_wulfen)))

    def test_hunters_guile_redeploy_filters_to_thunderwolf_wulfen_or_blood_claws(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        source = _make_unit(
            "Wolf Lord",
            keywords=["CHARACTER", "INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
        )
        thunderwolf = _make_unit(
            "Thunderwolf Cavalry",
            keywords=["THUNDERWOLF CAVALRY", "MOUNTED"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=3,
        )
        wulfen = _make_unit(
            "Wulfen",
            keywords=["WULFEN", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=5,
        )
        blood_claws = _make_unit(
            "Blood Claws",
            keywords=["BLOOD CLAWS", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=5,
        )
        other = _make_unit(
            "Intercessors",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=5,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=5,
        )
        for unit in (source, thunderwolf, wulfen, blood_claws, other):
            sm_army.add_unit(unit)
            unit.deployed = True
            unit.reserve_status = "deployed"
        enemy_army.add_unit(enemy)
        enemy.deployed = True
        enemy.reserve_status = "deployed"
        game.map.units = [source, thunderwolf, wulfen, blood_claws, other, enemy]
        game.rebuild_entity_registry()
        game.attacker_index = 0
        game.defender_index = 1

        _apply_enhancement(source, enhancement_id="000010269003", enhancement_name="Hunter's Guile")
        game.execute_redeploy_units_phase()

        requests = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str(getattr(req, "player_id", "") or "") == str(sm_player.id)
            and str((getattr(req, "context", {}) or {}).get("ability_name", "") or "") == "Hunter's Guile"
        ]
        self.assertEqual(len(requests), 1)
        request = requests[0]

        target_ids = {
            str((dict(getattr(option, "payload", {}) or {}).get("target_unit_id", "") or ""))
            for option in list(getattr(request, "options", []) or [])
        }
        self.assertIn(str(get_entity_id(thunderwolf) or ""), target_ids)
        self.assertIn(str(get_entity_id(wulfen) or ""), target_ids)
        self.assertIn(str(get_entity_id(blood_claws) or ""), target_ids)
        self.assertNotIn(str(get_entity_id(other) or ""), target_ids)

        options = list(getattr(request, "options", []) or [])
        for unit in (thunderwolf, wulfen, blood_claws):
            uid = str(get_entity_id(unit) or "")
            self.assertTrue(
                any(
                    str((dict(getattr(option, "payload", {}) or {}).get("target_unit_id", "") or "")) == uid
                    and str((dict(getattr(option, "payload", {}) or {}).get("redeploy_action", "") or "")).lower()
                    == "strategic_reserves"
                    for option in options
                )
            )

    def test_elders_guidance_once_per_battle_fight_phase_activation_applies_and_expires(self):
        game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
        game.phase = BattleRoundPhases.FIGHT_PHASE

        leader = _make_unit(
            "Wolf Guard Battle Leader",
            keywords=["CHARACTER", "INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            move=6,
        )
        leader.can_be_attached_to = ["BLOOD CLAWS"]
        blood_claws = _make_unit(
            "Blood Claws",
            keywords=["BLOOD CLAWS", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            move=6,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            move=6,
        )
        sm_army.add_unit(leader)
        sm_army.add_unit(blood_claws)
        enemy_army.add_unit(enemy)
        leader.deployed = True
        blood_claws.deployed = True
        enemy.deployed = True

        leader.attached_to = blood_claws
        blood_claws.attached_leaders = [leader]

        game.map.units = [blood_claws, leader, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(leader, enhancement_id="000010269004", enhancement_name="Elder's Guidance")

        leader_bearer = _bearer_model(leader)
        self.assertIsNotNone(leader_bearer)
        blood_claw_model = next(model for model in list(getattr(blood_claws, "models", []) or []) if bool(getattr(model, "is_alive", False)))
        profile = _make_melee_profile(ap=-1)

        ap_before_bodyguard = profile.get_effective_ap(blood_claw_model, enemy)
        ap_before_leader = profile.get_effective_ap(leader_bearer, enemy)
        self.assertEqual(int(ap_before_bodyguard or 0), -1)
        self.assertEqual(int(ap_before_leader or 0), -1)

        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        request = _find_request(game, decision_type=DECISION_CONFIRM_YES_NO, ability="elders_guidance")
        self.assertIsNotNone(request)
        yes_option = _first_yes_option(request)
        self.assertIsNotNone(yes_option)
        result = resolve_decision_command(game, request, yes_option.option_id, player_id=sm_player.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        ap_after_bodyguard = profile.get_effective_ap(blood_claw_model, enemy)
        ap_after_leader = profile.get_effective_ap(leader_bearer, enemy)
        self.assertEqual(int(ap_after_bodyguard or 0), -2)
        self.assertEqual(int(ap_after_leader or 0), -2)
        self.assertTrue(bool(blood_claws.has_used_unit_once_per_battle("elders_guidance")))

        game._on_phase_end_cleanup(player=sm_player, phase=game.phase)
        ap_cleared_bodyguard = profile.get_effective_ap(blood_claw_model, enemy)
        ap_cleared_leader = profile.get_effective_ap(leader_bearer, enemy)
        self.assertEqual(int(ap_cleared_bodyguard or 0), -1)
        self.assertEqual(int(ap_cleared_leader or 0), -1)

    def test_helm_of_the_beastslayer_worsens_ap_only_for_character_monster_or_vehicle_attackers(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()

        defender = _make_unit(
            "Wolf Guard",
            keywords=["INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
        )
        character_attacker = _make_unit(
            "Enemy Character",
            faction_name="Enemy",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
        )
        infantry_attacker = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
        )
        for unit in (defender,):
            sm_army.add_unit(unit)
            unit.deployed = True
        for unit in (character_attacker, infantry_attacker):
            enemy_army.add_unit(unit)
            unit.deployed = True
        game.map.units = [defender, character_attacker, infantry_attacker]
        game.rebuild_entity_registry()

        _apply_enhancement(defender, enhancement_id="000010269005", enhancement_name="Helm of the Beastslayer")
        profile = _make_ranged_profile(ap=-2)

        ap_vs_character = profile.get_effective_ap(character_attacker.models[0], defender)
        ap_vs_infantry = profile.get_effective_ap(infantry_attacker.models[0], defender)
        self.assertEqual(int(ap_vs_character or 0), -1)
        self.assertEqual(int(ap_vs_infantry or 0), -2)

        bearer = _bearer_model(defender)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)

        ap_after_bearer_destroyed = profile.get_effective_ap(character_attacker.models[0], defender)
        self.assertEqual(int(ap_after_bearer_destroyed or 0), -2)


if __name__ == "__main__":
    unittest.main()
