import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decision_requests import build_ethereal_pathway_requests
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import AttackResult, WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 3,
        objective_control: int = 1,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Aeldari"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["AELDARI"])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "7",
                "T": "3",
                "Sv": "4",
                "W": str(int(wounds)),
                "Ld": "6",
                "OC": str(int(objective_control)),
                "base_size": "28mm",
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
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 3,
    objective_control: int = 1,
):
    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        model_count=model_count,
        wounds=wounds,
        objective_control=objective_control,
    )
    return Unit(datasheet)


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army1 = Army.with_detachment("Aeldari", detachment_type="Guardian Battlehost")
    army1.faction_id = "AE"
    army2 = Army.with_detachment("Enemy", detachment_type="Other")
    army2.faction_id = "EN"
    p1 = Player("P1", control=PlayerControl.REMOTE, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)
    return game, army1, army2, p1, p2


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    bodyguard._ability_cache = {}
    leader._ability_cache = {}


def _first_option_with(request, predicate):
    for opt in list(request.options or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if predicate(payload):
            return opt
    return None


def _make_ranged_profile(*, weapon_name: str, attacks: str, damage: str) -> WargearProfile:
    parent = SimpleNamespace(name=weapon_name, is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="default",
        wargear_data={
            "range": "12",
            "A": attacks,
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": damage,
            "description": "",
        },
        parent_wargear=parent,
    )


def _empty_attack_result(profile: WargearProfile, attacker_model, target_unit) -> AttackResult:
    weapon_name = str(getattr(getattr(profile, "parent_wargear", None), "name", "") or getattr(profile, "name", "Weapon"))
    return AttackResult(
        weapon_name=weapon_name,
        attacker_name=str(getattr(attacker_model, "name", "Attacker") or "Attacker"),
        target_unit_name=str(getattr(target_unit, "name", "Target Unit") or "Target Unit"),
        attacks_rolled=0,
        attacks_dice_expression=str(getattr(profile, "attacks", "") or ""),
        attacks_dice_rolls=[],
        attacks_special_modifiers=[],
        hit_results=[],
        wound_results=[],
        save_results=[],
        damage_results=[],
        hazardous_roll=None,
        hazardous_damage=0,
        total_hits=0,
        total_wounds=0,
        total_saves_failed=0,
        total_damage_dealt=0,
        models_killed=0,
    )


class TestAeldariGuardianBattlehostEnhancements(unittest.TestCase):
    def test_craftworlds_champion_sets_bearer_objective_control_to_five_only(self):
        _game, army, _enemy_army, _player, _enemy_player = _build_game()
        unit = _make_unit("Autarch", faction_keywords=["AELDARI", "CHARACTER"], model_count=2, objective_control=1)
        army.add_unit(unit)

        Enhancement(
            id="000009911002",
            name="Craftworld's Champion",
            faction_id="AE",
            detachment="Guardian Battlehost",
            points=25,
            description="",
        ).apply_to_unit(unit)

        first_model = unit.models[0]
        second_model = unit.models[1]

        self.assertEqual(int(unit.get_effective_model_characteristic(first_model, "objective_control") or 0), 5)
        self.assertEqual(int(unit.get_effective_model_characteristic(second_model, "objective_control") or 0), 1)

    def test_ethereal_pathway_builds_request_and_applies_infiltrators(self):
        game, army, _enemy_army, player, _enemy_player = _build_game()
        source = _make_unit("Autarch", faction_keywords=["AELDARI", "CHARACTER"])
        guardians_a = _make_unit("Guardian Defenders", keywords=["GUARDIANS"], faction_keywords=["AELDARI"])
        guardians_b = _make_unit("Storm Guardians", keywords=["STORM GUARDIANS", "GUARDIANS"], faction_keywords=["AELDARI"])
        non_guardians = _make_unit("Dire Avengers", keywords=["DIRE AVENGERS"], faction_keywords=["AELDARI"])
        for unit in (source, guardians_a, guardians_b, non_guardians):
            army.add_unit(unit)
            unit.deployed = True

        Enhancement(
            id="000009911003",
            name="Ethereal Pathway",
            faction_id="AE",
            detachment="Guardian Battlehost",
            points=30,
            description="",
        ).apply_to_unit(source)
        game.rebuild_entity_registry()

        requests = build_ethereal_pathway_requests(game, army.units, queue_requests=True)
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(request.decision_type, DECISION_CHOOSE_QUARRY)
        self.assertEqual(str((request.context or {}).get("ability") or ""), "ethereal_pathway")

        source_id = str(get_entity_id(source) or "")
        guardians_ids = {str(get_entity_id(guardians_a) or ""), str(get_entity_id(guardians_b) or "")}
        pick_two = _first_option_with(
            request,
            lambda payload: (
                str(payload.get("source_unit_id") or "") == source_id
                and len(list(payload.get("selected_unit_ids") or [])) == 2
                and set(str(v or "") for v in list(payload.get("selected_unit_ids") or [])) == guardians_ids
            ),
        )
        self.assertIsNotNone(pick_two)

        resolve_decision_command(game, request, pick_two.option_id, player_id=player.id)

        self.assertTrue(bool(guardians_a.special_rules.get("ethereal_pathway_infiltrators")))
        self.assertTrue(bool(guardians_b.special_rules.get("ethereal_pathway_infiltrators")))
        self.assertFalse(bool(non_guardians.special_rules.get("ethereal_pathway_infiltrators")))
        self.assertTrue(bool(guardians_a.has_infiltrate()))
        self.assertTrue(bool(guardians_b.has_infiltrate()))
        self.assertTrue(bool(source.special_rules.get("enhancement_ethereal_pathway_used")))

    def test_ethereal_pathway_rejects_invalid_selection_payload(self):
        game, army, _enemy_army, player, _enemy_player = _build_game()
        source = _make_unit("Autarch", faction_keywords=["AELDARI", "CHARACTER"])
        g1 = _make_unit("Guardian Defenders", keywords=["GUARDIANS"], faction_keywords=["AELDARI"])
        g2 = _make_unit("Storm Guardians", keywords=["STORM GUARDIANS", "GUARDIANS"], faction_keywords=["AELDARI"])
        g3 = _make_unit("Guardian Squad", keywords=["GUARDIANS"], faction_keywords=["AELDARI"])
        for unit in (source, g1, g2, g3):
            army.add_unit(unit)
            unit.deployed = True

        Enhancement(
            id="000009911003",
            name="Ethereal Pathway",
            faction_id="AE",
            detachment="Guardian Battlehost",
            points=30,
            description="",
        ).apply_to_unit(source)
        game.rebuild_entity_registry()

        request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Ethereal Pathway invalid selection test",
            player_id=player.id,
            options=[
                DecisionOption.create(
                    "Invalid three units",
                    payload={
                        "source_unit_id": str(get_entity_id(source) or ""),
                        "selected_unit_ids": [
                            str(get_entity_id(g1) or ""),
                            str(get_entity_id(g2) or ""),
                            str(get_entity_id(g3) or ""),
                        ],
                    },
                )
            ],
            context={
                "ability": "ethereal_pathway",
                "ability_name": "Ethereal Pathway",
                "source_unit_id": str(get_entity_id(source) or ""),
                "enhancement_id": "000009911003",
            },
        )
        game.request_decision(request)
        option = request.options[0]
        resolve_decision_command(game, request, option.option_id, player_id=player.id)

        self.assertFalse(bool(g1.special_rules.get("ethereal_pathway_infiltrators")))
        self.assertFalse(bool(g2.special_rules.get("ethereal_pathway_infiltrators")))
        self.assertFalse(bool(g3.special_rules.get("ethereal_pathway_infiltrators")))
        self.assertFalse(bool(source.special_rules.get("enhancement_ethereal_pathway_used")))

    def test_protector_of_paths_overwatch_discount_threshold_and_battle_round_limit(self):
        game, army, _enemy_army, player, _enemy_player = _build_game()
        bodyguard = _make_unit("Guardian Defenders", keywords=["GUARDIANS"], faction_keywords=["AELDARI"])
        leader = _make_unit("Autarch", faction_keywords=["AELDARI", "CHARACTER"])
        army.add_unit(bodyguard)
        army.add_unit(leader)
        bodyguard.deployed = True
        leader.deployed = True
        _attach_leader(bodyguard, leader)

        Enhancement(
            id="000009911004",
            name="Protector of the Paths",
            faction_id="AE",
            detachment="Guardian Battlehost",
            points=20,
            description="",
        ).apply_to_unit(leader)

        rule = bodyguard.get_protector_of_paths_overwatch_rule()
        self.assertIsNotNone(rule)
        self.assertEqual(int((rule or {}).get("base_threshold", 0) or 0), 5)
        self.assertEqual(int((rule or {}).get("controlled_threshold", 0) or 0), 4)
        self.assertTrue(bool(bodyguard.can_use_protector_of_paths_overwatch(game, stratagem_name="OVERWATCH")))

        bodyguard._within_controlled_objective_range = lambda game_map=None: False
        self.assertEqual(
            int(bodyguard.get_protector_of_paths_overwatch_hit_threshold(enemy_unit=None, game=game) or 0),
            5,
        )
        bodyguard._within_controlled_objective_range = lambda game_map=None: True
        self.assertEqual(
            int(bodyguard.get_protector_of_paths_overwatch_hit_threshold(enemy_unit=None, game=game) or 0),
            4,
        )

        if getattr(player, "stratagems", None) is not None:
            player.stratagems._used_this_turn = {"OVERWATCH": False}

        strat = SimpleNamespace(name="Fire Overwatch", cp_cost=1)
        player.set_next_optional_decision("PROTECTOR_OF_PATHS_OVERWATCH", True)
        applied = player.apply_stratagem_cp_cost(strat, target_unit=bodyguard)
        self.assertEqual(int(applied.get("cost", -1)), 0)
        self.assertTrue(bool(applied.get("protector_of_paths_overwatch_use", False)))

        bodyguard.mark_protector_of_paths_used(game, source="Protector of the Paths", stratagem_name="Fire Overwatch")
        self.assertFalse(bool(bodyguard.can_use_protector_of_paths_overwatch(game, stratagem_name="OVERWATCH")))
        game.turn += 1
        self.assertTrue(bool(bodyguard.can_use_protector_of_paths_overwatch(game, stratagem_name="OVERWATCH")))

    def test_breath_of_vaul_rerolls_flamer_attacks_and_fusion_damage(self):
        _game, army, enemy_army, _player, _enemy_player = _build_game()
        storm_guardians = _make_unit(
            "Storm Guardians",
            keywords=["STORM GUARDIANS", "GUARDIANS"],
            faction_keywords=["AELDARI"],
            model_count=2,
        )
        leader = _make_unit("Autarch", faction_keywords=["AELDARI", "CHARACTER"])
        target = _make_unit("Enemy Unit", faction_keywords=["ENEMY"], wounds=10)
        army.add_unit(storm_guardians)
        army.add_unit(leader)
        enemy_army.add_unit(target)
        storm_guardians.deployed = True
        leader.deployed = True
        _attach_leader(storm_guardians, leader)

        Enhancement(
            id="000009911005",
            name="Breath of Vaul",
            faction_id="AE",
            detachment="Guardian Battlehost",
            points=10,
            description="",
        ).apply_to_unit(leader)

        attacker = storm_guardians.models[0]
        self.assertTrue(
            bool(storm_guardians.can_use_breath_of_vaul_flamer_attacks_reroll(model=attacker, weapon_name="Flamer"))
        )
        self.assertTrue(
            bool(storm_guardians.can_use_breath_of_vaul_fusion_damage_reroll(model=attacker, weapon_name="Fusion Gun"))
        )

        flamer = _make_ranged_profile(weapon_name="Flamer", attacks="D6", damage="1")
        attack_rolls = iter([(1, [1]), (6, [6])])
        flamer.attacks.resolve_detailed = lambda: next(attack_rolls)
        attack_result = _empty_attack_result(flamer, attacker, target)
        attack_info = flamer._resolve_attack_count(
            target,
            attacker,
            attack_result,
            publish_roll_event=False,
        )
        self.assertEqual(int(attack_info.num_attacks or 0), 6)
        self.assertTrue(any("Breath of Vaul" in str(text or "") for text in list(attack_info.special_modifiers or [])))

        fusion = _make_ranged_profile(weapon_name="Fusion Gun", attacks="1", damage="D6")
        damage_rolls = iter([(1, [1]), (6, [6])])
        fusion.damage.roll_detailed = lambda: next(damage_rolls)
        damage_result = fusion._damage_target_with_tracking(
            target.models[0],
            attacker,
            {"below_half_distance": False, "mortal_wound": False},
            game_map=None,
        )
        self.assertEqual(int(damage_result.get("damage_rolled", 0) or 0), 6)
        self.assertTrue(any("Breath of Vaul" in str(text or "") for text in list(damage_result.get("special_effects", []) or [])))


if __name__ == "__main__":
    unittest.main()
