import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.combat_doctrines import ASSAULT_DOCTRINE, DEVASTATOR_DOCTRINE, TACTICAL_DOCTRINE
from warhammer40k_ai.rules.enhancement import Enhancement
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
        wounds: int = 4,
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game(detachment_type: str = "Gladius Task Force"):
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


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]
    bodyguard._ability_cache = {}
    leader._ability_cache = {}


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        if str(get_entity_id(model) or "") == bearer_id:
            return model
    for model in list(getattr(unit, "models", []) or []):
        if bool(getattr(model, "is_alive", False)):
            return model
    return None


def _make_melee_profile(*, attacks: int = 1, strength: int = 4) -> WargearProfile:
    parent = SimpleNamespace(name="Astartes Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": str(int(attacks)),
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Bolt Rifle", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _find_pending_request(game: Game, *, decision_type: str, ability: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == str(ability):
            return req
    return None


def _first_yes_option(request):
    for option in list(getattr(request, "options", []) or []):
        if bool(dict(getattr(option, "payload", {}) or {}).get("choice")):
            return option
    return None


class TestSpaceMarinesGladiusTaskForceEnhancements(unittest.TestCase):
    def test_artificer_armour_applies_bearer_only_save_and_fnp(self):
        game, sm_army, _enemy_army, _sm_player, _enemy_player = _build_game()
        unit = _make_unit(
            "Captain and Honour Guard",
            keywords=["ADEPTUS ASTARTES", "CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=4,
        )
        sm_army.add_unit(unit)
        unit.deployed = True
        game.map.units = [unit]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008353002",
            name="Artificer Armour",
            faction_id="SM",
            detachment="Gladius Task Force",
            points=10,
            description="",
        ).apply_to_unit(unit)

        bearer = _bearer_model(unit)
        self.assertIsNotNone(bearer)
        non_bearer = next(model for model in list(unit.models or []) if model is not bearer)

        save_value, save_source = unit.get_model_save_characteristic_override(bearer)
        self.assertEqual(int(save_value or 0), 2)
        self.assertIn("Artificer Armour", str(save_source or ""))

        non_bearer_save, _ = unit.get_model_save_characteristic_override(non_bearer)
        self.assertIsNone(non_bearer_save)

        bearer_fnp_values = [int(value) for value, _condition in list(unit.has_feel_no_pain(bearer) or [])]
        self.assertIn(5, bearer_fnp_values)

        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)

    def test_the_honour_vehement_scales_bearer_melee_attacks_and_strength_with_assault_doctrine(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        bearer_unit = _make_unit(
            "Captain",
            keywords=["ADEPTUS ASTARTES", "CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=5,
        )
        sm_army.add_unit(bearer_unit)
        enemy_army.add_unit(enemy)
        bearer_unit.deployed = True
        enemy.deployed = True
        game.map.units = [bearer_unit, enemy]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008353003",
            name="The Honour Vehement",
            faction_id="SM",
            detachment="Gladius Task Force",
            points=15,
            description="",
        ).apply_to_unit(bearer_unit)

        bearer = _bearer_model(bearer_unit)
        self.assertIsNotNone(bearer)
        melee_profile = _make_melee_profile(attacks=1, strength=4)

        self.assertTrue(sm_army.combat_doctrines.select_doctrine(DEVASTATOR_DOCTRINE, battle_round=1))
        game.turn = 1
        dev_attacks = melee_profile.preview_attack_count(enemy, bearer, publish_roll_event=False)
        self.assertEqual(int(dev_attacks.num_attacks or 0), 2)
        dev_wound = melee_profile._wound_target_with_tracking(
            enemy,
            bearer,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("+1S from The Honour Vehement" in str(reason) for reason in list(dev_wound.get("modifiers", []) or [])))

        self.assertTrue(sm_army.combat_doctrines.select_doctrine(ASSAULT_DOCTRINE, battle_round=2))
        game.turn = 2
        assault_attacks = melee_profile.preview_attack_count(enemy, bearer, publish_roll_event=False)
        self.assertEqual(int(assault_attacks.num_attacks or 0), 3)
        assault_wound = melee_profile._wound_target_with_tracking(
            enemy,
            bearer,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(any("+2S from The Honour Vehement" in str(reason) for reason in list(assault_wound.get("modifiers", []) or [])))

    def test_adept_of_the_codex_optional_activation_sets_unit_doctrine_override_until_next_command_phase(self):
        game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
        bodyguard = _make_unit(
            "Intercessors",
            keywords=["ADEPTUS ASTARTES", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=3,
        )
        leader = _make_unit(
            "Captain",
            keywords=["ADEPTUS ASTARTES", "CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        sm_army.add_unit(bodyguard)
        sm_army.add_unit(leader)
        bodyguard.deployed = True
        leader.deployed = True
        _attach_leader(bodyguard, leader)
        game.map.units = [bodyguard, leader]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008353004",
            name="Adept of the Codex",
            faction_id="SM",
            detachment="Gladius Task Force",
            points=20,
            description="",
        ).apply_to_unit(leader)

        self.assertTrue(sm_army.combat_doctrines.select_doctrine(DEVASTATOR_DOCTRINE, battle_round=1))
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.turn = 1
        game.current_player_index = 0

        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)
        request = _find_pending_request(
            game,
            decision_type=DECISION_CONFIRM_YES_NO,
            ability="student_of_the_codex",
        )
        self.assertIsNotNone(request)
        yes_option = _first_yes_option(request)
        self.assertIsNotNone(yes_option)
        resolve_decision_command(game, request, yes_option.option_id, player_id=sm_player.id)

        active = sm_army.combat_doctrines.get_active_doctrine_for_unit(bodyguard, game=game)
        self.assertIsNotNone(active)
        self.assertEqual(str(getattr(active, "key", "") or ""), TACTICAL_DOCTRINE.key)

        self.assertTrue(sm_army.combat_doctrines.select_doctrine(ASSAULT_DOCTRINE, battle_round=2))
        game.turn = 2
        game.phase = BattleRoundPhases.COMMAND_PHASE
        game.current_player_index = 0
        game._on_phase_start_optional_abilities(player=sm_player, phase=game.phase)

        post_expiry = sm_army.combat_doctrines.get_active_doctrine_for_unit(bodyguard, game=game)
        self.assertIsNotNone(post_expiry)
        self.assertEqual(str(getattr(post_expiry, "key", "") or ""), ASSAULT_DOCTRINE.key)

    def test_fire_discipline_grants_ranged_sustained_hits_and_devastator_advance_reroll(self):
        game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
        bodyguard = _make_unit(
            "Intercessors",
            keywords=["ADEPTUS ASTARTES", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=2,
            wounds=3,
        )
        leader = _make_unit(
            "Captain",
            keywords=["ADEPTUS ASTARTES", "CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            model_count=1,
            wounds=6,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=5,
        )
        sm_army.add_unit(bodyguard)
        sm_army.add_unit(leader)
        enemy_army.add_unit(enemy)
        bodyguard.deployed = True
        leader.deployed = True
        enemy.deployed = True
        _attach_leader(bodyguard, leader)
        game.map.units = [bodyguard, leader, enemy]
        game.rebuild_entity_registry()

        Enhancement(
            id="000008353005",
            name="Fire Discipline",
            faction_id="SM",
            detachment="Gladius Task Force",
            points=25,
            description="",
        ).apply_to_unit(leader)

        attacker = bodyguard.models[0]
        ranged_profile = _make_ranged_profile()

        self.assertTrue(sm_army.combat_doctrines.select_doctrine(DEVASTATOR_DOCTRINE, battle_round=1))
        game.turn = 1
        self.assertTrue(bodyguard.can_reroll_advance_roll())

        dev_attack_instance = {}
        dev_hit_result = ranged_profile._hit_target_with_tracking(
            enemy,
            attacker,
            dev_attack_instance,
            roll_value=6,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(dev_hit_result.get("hit")))
        self.assertEqual(int(dev_attack_instance.get("sustained_hit", 0) or 0), 1)
        self.assertTrue(any("Fire Discipline" in str(effect) for effect in list(dev_hit_result.get("special_effects", []) or [])))

        self.assertTrue(sm_army.combat_doctrines.select_doctrine(TACTICAL_DOCTRINE, battle_round=2))
        game.turn = 2
        self.assertFalse(bodyguard.can_reroll_advance_roll())

        tactical_attack_instance = {}
        tactical_hit_result = ranged_profile._hit_target_with_tracking(
            enemy,
            attacker,
            tactical_attack_instance,
            roll_value=6,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(tactical_hit_result.get("hit")))
        self.assertEqual(int(tactical_attack_instance.get("sustained_hit", 0) or 0), 1)


if __name__ == "__main__":
    unittest.main()
