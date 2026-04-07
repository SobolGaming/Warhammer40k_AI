import unittest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


_CHAMELEONIC_DESCRIPTION = (
    "Vanguard Invader model only. The bearer has the Stealth ability and each time a ranged attack "
    "targets the bearer's unit, models in that unit have the Benefit of Cover against that attack."
)
_STALKER_DESCRIPTION = (
    "Vanguard Invader model only. At the start of the battle, select one enemy unit. "
    "Each time the bearer makes an attack that targets that enemy unit, add 1 to the Hit roll and "
    "add 1 to the Wound roll."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Tyranids",
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
            faction_keywords = ["TYRANIDS"] if faction_name == "Tyranids" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": "5",
                "Sv": "4",
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
    faction_name: str = "Tyranids",
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


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army.with_detachment("Tyranids", "Vanguard Onslaught")
    tyr_army.faction_id = "TYR"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    tyr_player = Player("Tyranids", control=PlayerControl.REMOTE, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, tyr_army, enemy_army, tyr_player, enemy_player


def _set_model_location(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        if not bool(getattr(model, "is_alive", False)):
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.position = (float(x), float(y), 0.0)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str, description: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="TYR",
        detachment="Vanguard Onslaught",
        points=20,
        description=description,
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    for unit in (bodyguard, leader):
        invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate_cache):
            invalidate_cache()


def _invalidate_unit_cache(unit: Unit) -> None:
    invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
    if callable(invalidate_cache):
        invalidate_cache()


def _bearer_model(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    if bearer_id:
        for model in list(getattr(unit, "models", []) or []):
            if str(get_entity_id(model) or "") == bearer_id:
                return model
    for model in list(getattr(unit, "models", []) or []):
        if bool(getattr(model, "is_alive", False)):
            return model
    return None


def _make_ranged_profile(skill: str = "4+") -> WargearProfile:
    parent = type(
        "_ParentWargear",
        (),
        {
            "name": "Test Gun",
            "is_melee": staticmethod(lambda: False),
            "is_ranged": staticmethod(lambda: True),
        },
    )()
    return WargearProfile(
        "Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_melee_profile(skill: str = "4+") -> WargearProfile:
    parent = type(
        "_ParentWargear",
        (),
        {
            "name": "Test Claws",
            "is_melee": staticmethod(lambda: True),
            "is_ranged": staticmethod(lambda: False),
        },
    )()
    return WargearProfile(
        "Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": str(skill),
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _find_prey_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") != "prey_selection":
            continue
        return request
    return None


def _select_target_option(request, *, target_unit_id: str):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == str(target_unit_id):
            return option
    return None


class TestTyranidsVanguardOnslaughtEnhancements(unittest.TestCase):
    def test_vanguard_onslaught_enhancement_descriptors_exist(self):
        expected = {
            "000008417003": ("Chameleonic", "grant_stealth_and_ranged_benefit_of_cover_to_bearer_unit"),
            "000008417004": ("Stalker", "select_enemy_unit_for_bearer_hit_and_wound_bonus"),
            "000008417005": ("Neuronode", "redeploy_units"),
        }
        for enhancement_id, (name, effect) in expected.items():
            desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_chameleonic_grants_attached_unit_stealth_and_ranged_cover_only_while_bearer_is_alive(self):
        game, tyr_army, enemy_army, _tyr_player, _enemy_player = _build_game()
        leader = _make_unit(
            "Winged Tyranid Prime",
            keywords=["TYRANIDS", "INFANTRY", "CHARACTER", "VANGUARD INVADER"],
            faction_keywords=["TYRANIDS"],
            model_count=1,
            wounds=6,
            attached_to=["TYRANIDS_BODYGUARD"],
        )
        bodyguard = _make_unit(
            "Tyrant Guard",
            keywords=["TYRANIDS", "INFANTRY"],
            faction_keywords=["TYRANIDS"],
            model_count=2,
            wounds=3,
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=2,
        )
        tyr_army.add_unit(leader)
        tyr_army.add_unit(bodyguard)
        enemy_army.add_unit(enemy)
        _set_model_location(leader, 0.0, 0.0)
        _set_model_location(bodyguard, 0.0, 2.0)
        _set_model_location(enemy, 12.0, 0.0)
        game.map.units = [leader, bodyguard, enemy]
        game.rebuild_entity_registry()

        _apply_enhancement(
            leader,
            enhancement_id="000008417003",
            enhancement_name="Chameleonic",
            description=_CHAMELEONIC_DESCRIPTION,
        )
        _attach_leader(bodyguard, leader)

        self.assertTrue(bool(bodyguard.has_stealth()))

        ranged_attack = {
            "mortal_wound": False,
            "attacker_model": enemy.models[0],
            "attacker_unit": enemy,
        }
        _make_ranged_profile()._save_with_tracking(
            bodyguard.models[0],
            ranged_attack,
            ap=0,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(ranged_attack.get("benefit_of_cover", False)))
        self.assertIn("Chameleonic", str(ranged_attack.get("benefit_of_cover_source", "") or ""))

        melee_attack = {
            "mortal_wound": False,
            "attacker_model": enemy.models[0],
            "attacker_unit": enemy,
        }
        _make_melee_profile()._save_with_tracking(
            bodyguard.models[0],
            melee_attack,
            ap=0,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(melee_attack.get("benefit_of_cover", False)))

        bearer = _bearer_model(leader)
        self.assertIsNotNone(bearer)
        bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)
        _invalidate_unit_cache(leader)
        _invalidate_unit_cache(bodyguard)

        self.assertFalse(bool(bodyguard.has_stealth()))

        ranged_attack_after_death = {
            "mortal_wound": False,
            "attacker_model": enemy.models[0],
            "attacker_unit": enemy,
        }
        _make_ranged_profile()._save_with_tracking(
            bodyguard.models[0],
            ranged_attack_after_death,
            ap=0,
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(ranged_attack_after_death.get("benefit_of_cover", False)))

    def test_stalker_queues_prey_selection_and_applies_bearer_only_hit_and_wound_bonus(self):
        game, tyr_army, enemy_army, tyr_player, _enemy_player = _build_game()
        hunter = _make_unit(
            "Winged Tyranid Prime",
            keywords=["TYRANIDS", "INFANTRY", "CHARACTER", "VANGUARD INVADER"],
            faction_keywords=["TYRANIDS"],
            model_count=2,
            wounds=6,
        )
        target = _make_unit(
            "Marked Target",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=3,
        )
        other_target = _make_unit(
            "Other Target",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            model_count=1,
            wounds=3,
        )
        tyr_army.add_unit(hunter)
        enemy_army.add_unit(target)
        enemy_army.add_unit(other_target)
        _set_model_location(hunter, 0.0, 0.0)
        _set_model_location(target, 12.0, 0.0)
        _set_model_location(other_target, 18.0, 0.0)
        game.map.units = [hunter, target, other_target]
        game.rebuild_entity_registry()

        _apply_enhancement(
            hunter,
            enhancement_id="000008417004",
            enhancement_name="Stalker",
            description=_STALKER_DESCRIPTION,
        )

        rule = hunter.get_prey_selection_rule()
        self.assertIsNotNone(rule)
        self.assertEqual(int(rule.get("hit_bonus", 0) or 0), 1)
        self.assertEqual(int(rule.get("wound_bonus", 0) or 0), 1)
        self.assertEqual(str(rule.get("source", "") or ""), "Stalker")
        self.assertEqual(str(rule.get("source_unit_id", "") or ""), str(get_entity_id(hunter) or ""))

        tyr_army.on_battle_round_start(1)
        request = _find_prey_request(game)
        self.assertIsNotNone(request)
        self.assertEqual(int(getattr(request, "context", {}).get("prey_hit_bonus", 0) or 0), 1)
        self.assertEqual(int(getattr(request, "context", {}).get("prey_wound_bonus", 0) or 0), 1)
        prey_source_model_id = str(getattr(request, "context", {}).get("prey_source_model_id", "") or "")
        self.assertTrue(bool(prey_source_model_id))

        option = _select_target_option(request, target_unit_id=str(get_entity_id(target) or ""))
        self.assertIsNotNone(option)
        resolve_decision_command(game, request, option.option_id, player_id=tyr_player.id)

        bearer = hunter.models[0]
        non_bearer = hunter.models[1]
        self.assertEqual(str(getattr(hunter, "_prey_selection_source_model_id", "") or ""), prey_source_model_id)

        hit_mods = hunter.get_unit_hit_reroll_modifiers("ranged", target=target, attacker_model=bearer)
        self.assertEqual(int(hit_mods.get("hit", 0) or 0), 1)
        self.assertTrue(any("Stalker" in reason for reason in list(hit_mods.get("hit_reasons", ()) or ())))

        wound_mods = hunter.get_unit_wound_reroll_modifiers(
            "ranged",
            target=target,
            attacker_model=bearer,
            weapon_profile=_make_ranged_profile(),
        )
        self.assertEqual(int(wound_mods.get("wound", 0) or 0), 1)
        self.assertTrue(any("Stalker" in reason for reason in list(wound_mods.get("wound_reasons", ()) or ())))

        other_hit_mods = hunter.get_unit_hit_reroll_modifiers("ranged", target=target, attacker_model=non_bearer)
        self.assertEqual(int(other_hit_mods.get("hit", 0) or 0), 0)

        other_wound_mods = hunter.get_unit_wound_reroll_modifiers(
            "ranged",
            target=target,
            attacker_model=non_bearer,
            weapon_profile=_make_ranged_profile(),
        )
        self.assertEqual(int(other_wound_mods.get("wound", 0) or 0), 0)

        off_target_hit_mods = hunter.get_unit_hit_reroll_modifiers("ranged", target=other_target, attacker_model=bearer)
        self.assertEqual(int(off_target_hit_mods.get("hit", 0) or 0), 0)

        off_target_wound_mods = hunter.get_unit_wound_reroll_modifiers(
            "ranged",
            target=other_target,
            attacker_model=bearer,
            weapon_profile=_make_ranged_profile(),
        )
        self.assertEqual(int(off_target_wound_mods.get("wound", 0) or 0), 0)


if __name__ == "__main__":
    unittest.main()
