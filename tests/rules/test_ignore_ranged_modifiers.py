import unittest
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        bs="4+",
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
                "BS_WS": bs,
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, abilities=None, bs="4+"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        abilities=abilities,
        bs=bs,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army.with_detachment("Adeptus Mechanicus", "Data-Psalm")
    army1.faction_id = "ADM"
    army2 = Army.with_detachment("Enemy", "Other")
    army2.faction_id = "EN"

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    return game, army1, army2, p1, p2


def _make_profile():
    from warhammer40k_ai.units.wargear import Wargear

    data = {
        "range": "24",
        "A": "1",
        "BS_WS": "4+",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
        "type": "Ranged",
        "name": "Test Gun",
    }
    return Wargear(data).profiles["default"]


def _make_melee_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(id="test_blade", name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


class TestIgnoreRangedModifiers(unittest.TestCase):
    def _assert_ignore_negative_hit_modifiers_for_description(self, description: str):
        from warhammer40k_ai.engine.game import BattleRoundPhases
        from warhammer40k_ai.utility import dice as dice_mod
        from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_NEGATIVE

        ignore_mods = {
            "name": "Weapon Support System",
            "description": description,
            "type": "Datasheet",
            "parameter": "",
        }
        stealth = {"name": "Stealth", "description": "Stealth.", "type": "Datasheet", "parameter": ""}

        game, army1, army2, _p1, _p2 = _build_game()
        game.turn = 1
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        attacker = _make_unit("Shooter", abilities=[ignore_mods])
        target = _make_unit("Target", abilities=[stealth])
        army1.add_unit(attacker)
        army2.add_unit(target)

        attacker.models[0].set_location(0, 0, 0, 0)
        target.models[0].set_location(1, 0, 0, 0)
        game.map.units = [attacker, target]

        game.install_decision_providers(hit_modifier_choice_provider=lambda **_kwargs: CHOICE_IGNORE_NEGATIVE)

        rolls = iter([4, 4, 4])
        original_get_dice_roll = dice_mod.get_dice_roll
        dice_mod.get_dice_roll = lambda _size=6: next(rolls)
        try:
            profile = _make_profile()
            result = profile.attack(target, attacker.models[0], game.map)
        finally:
            dice_mod.get_dice_roll = original_get_dice_roll

        self.assertIsNotNone(result)
        self.assertTrue(result.hit_results)
        self.assertTrue(result.hit_results[0]["hit"], "Ignoring negative hit modifiers should let a 4 hit on 4+.")

    def _assert_hit_only_rule_keeps_bs_modifiers(self, description: str):
        from warhammer40k_ai.engine.game import BattleRoundPhases
        from warhammer40k_ai.rules.doctrina_imperatives import DoctrinaImperativesManager, PROTECTOR_IMPERATIVE
        from warhammer40k_ai.utility import dice as dice_mod
        from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_POSITIVE

        ignore_mods = {
            "name": "Weapon Support System",
            "description": description,
            "type": "Datasheet",
            "parameter": "",
        }
        doctrina = {"name": "Doctrina Imperatives", "description": "Doctrina Imperatives", "type": "Datasheet", "parameter": ""}

        game, army1, army2, _p1, _p2 = _build_game()
        game.turn = 1
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        mgr = DoctrinaImperativesManager(army1)
        mgr.active_imperative_key = PROTECTOR_IMPERATIVE.key
        mgr.active_round = 1
        army1.doctrina_imperatives = mgr

        attacker = _make_unit("Shooter", abilities=[ignore_mods, doctrina])
        target = _make_unit("Target")
        army1.add_unit(attacker)
        army2.add_unit(target)

        attacker.models[0].set_location(0, 0, 0, 0)
        target.models[0].set_location(1, 0, 0, 0)
        game.map.units = [attacker, target]

        game.install_decision_providers(hit_modifier_choice_provider=lambda **_kwargs: CHOICE_IGNORE_POSITIVE)

        rolls = iter([3, 4, 4])
        original_get_dice_roll = dice_mod.get_dice_roll
        dice_mod.get_dice_roll = lambda _size=6: next(rolls)
        try:
            profile = _make_profile()
            result = profile.attack(target, attacker.models[0], game.map)
        finally:
            dice_mod.get_dice_roll = original_get_dice_roll

        self.assertIsNotNone(result)
        self.assertTrue(result.hit_results)
        self.assertTrue(
            result.hit_results[0]["hit"],
            "Weapon Support System should not ignore Ballistic Skill modifiers when it only references Hit-roll modifiers.",
        )

    def test_ignore_positive_bs_modifiers(self):
        from warhammer40k_ai.engine.game import BattleRoundPhases
        from warhammer40k_ai.rules.doctrina_imperatives import DoctrinaImperativesManager, PROTECTOR_IMPERATIVE
        from warhammer40k_ai.utility import dice as dice_mod
        from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_POSITIVE

        ignore_mods = {
            "name": "Ignore Ranged Modifiers",
            "description": (
                "Each time a model in this unit makes a ranged attack, you can ignore any or all modifiers to "
                "that attack's Ballistic Skill characteristic and any or all modifiers to the Hit roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        doctrina = {"name": "Doctrina Imperatives", "description": "Doctrina Imperatives", "type": "Datasheet", "parameter": ""}

        game, army1, army2, _p1, _p2 = _build_game()
        game.turn = 1
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        mgr = DoctrinaImperativesManager(army1)
        mgr.active_imperative_key = PROTECTOR_IMPERATIVE.key
        mgr.active_round = 1
        army1.doctrina_imperatives = mgr

        attacker = _make_unit("Shooter", abilities=[ignore_mods, doctrina])
        target = _make_unit("Target")
        army1.add_unit(attacker)
        army2.add_unit(target)

        attacker.models[0].set_location(0, 0, 0, 0)
        target.models[0].set_location(1, 0, 0, 0)
        game.map.units = [attacker, target]

        game.install_decision_providers(
            hit_modifier_choice_provider=lambda **_kwargs: CHOICE_IGNORE_POSITIVE,
            skill_modifier_choice_provider=lambda **_kwargs: CHOICE_IGNORE_POSITIVE,
        )

        rolls = iter([3, 4, 4])
        original_get_dice_roll = dice_mod.get_dice_roll
        dice_mod.get_dice_roll = lambda _size=6: next(rolls)
        try:
            profile = _make_profile()
            result = profile.attack(target, attacker.models[0], game.map)
        finally:
            dice_mod.get_dice_roll = original_get_dice_roll

        self.assertIsNotNone(result)
        self.assertTrue(result.hit_results)
        self.assertFalse(result.hit_results[0]["hit"], "Ignoring positive BS modifiers should make a 3 miss on 4+.")

    def test_ignore_negative_hit_modifiers(self):
        from warhammer40k_ai.engine.game import BattleRoundPhases
        from warhammer40k_ai.utility import dice as dice_mod
        from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_NEGATIVE

        ignore_mods = {
            "name": "Ignore Ranged Modifiers",
            "description": (
                "Each time a model in this unit makes a ranged attack, you can ignore any or all modifiers to "
                "that attack's Ballistic Skill characteristic and any or all modifiers to the Hit roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        stealth = {"name": "Stealth", "description": "Stealth.", "type": "Datasheet", "parameter": ""}

        game, army1, army2, _p1, _p2 = _build_game()
        game.turn = 1
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        attacker = _make_unit("Shooter", abilities=[ignore_mods])
        target = _make_unit("Target", abilities=[stealth])
        army1.add_unit(attacker)
        army2.add_unit(target)

        attacker.models[0].set_location(0, 0, 0, 0)
        target.models[0].set_location(1, 0, 0, 0)
        game.map.units = [attacker, target]

        game.install_decision_providers(hit_modifier_choice_provider=lambda **_kwargs: CHOICE_IGNORE_NEGATIVE)

        rolls = iter([4, 4, 4])
        original_get_dice_roll = dice_mod.get_dice_roll
        dice_mod.get_dice_roll = lambda _size=6: next(rolls)
        try:
            profile = _make_profile()
            result = profile.attack(target, attacker.models[0], game.map)
        finally:
            dice_mod.get_dice_roll = original_get_dice_roll

        self.assertIsNotNone(result)
        self.assertTrue(result.hit_results)
        self.assertTrue(result.hit_results[0]["hit"], "Ignoring negative hit modifiers should let a 4 hit on 4+.")

    def test_weapon_support_system_bearer_wording_ignore_negative_hit_modifiers(self):
        self._assert_ignore_negative_hit_modifiers_for_description(
            "Each time the bearer makes a ranged attack, you can ignore any or all modifiers to the Hit roll."
        )

    def test_weapon_support_system_unit_wording_ignore_negative_hit_modifiers(self):
        self._assert_ignore_negative_hit_modifiers_for_description(
            "Each time a model in this unit makes a ranged attack, you can ignore any or all modifiers to the Hit roll."
        )

    def test_weapon_support_system_bearer_wording_does_not_ignore_bs_modifiers(self):
        self._assert_hit_only_rule_keeps_bs_modifiers(
            "Each time the bearer makes a ranged attack, you can ignore any or all modifiers to the Hit roll."
        )

    def test_weapon_support_system_unit_wording_does_not_ignore_bs_modifiers(self):
        self._assert_hit_only_rule_keeps_bs_modifiers(
            "Each time a model in this unit makes a ranged attack, you can ignore any or all modifiers to the Hit roll."
        )

    def test_hit_modifier_choice_reuses_immediately_resolved_decision_request(self):
        from warhammer40k_ai.engine.game import BattleRoundPhases
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_HIT_MODIFIER_IGNORES
        from warhammer40k_ai.utility import dice as dice_mod
        from warhammer40k_ai.utility.decision_utils import resolve_decision_command
        from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_NEGATIVE

        ignore_mods = {
            "name": "Ignore Ranged Modifiers",
            "description": (
                "Each time a model in this unit makes a ranged attack, you can ignore any or all modifiers to "
                "that attack's Ballistic Skill characteristic and any or all modifiers to the Hit roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        stealth = {"name": "Stealth", "description": "Stealth.", "type": "Datasheet", "parameter": ""}

        game, army1, army2, p1, _p2 = _build_game()
        game.turn = 1
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        attacker = _make_unit("Shooter", abilities=[ignore_mods])
        target = _make_unit("Target", abilities=[stealth])
        army1.add_unit(attacker)
        army2.add_unit(target)
        attacker.models[0].set_location(0, 0, 0, 0)
        target.models[0].set_location(1, 0, 0, 0)
        game.map.units = [attacker, target]

        seen_decisions = []
        original_request_decision = game.request_decision

        def _auto_resolve(request):
            seen_decisions.append(str(getattr(request, "decision_type", "") or ""))
            original_request_decision(request)
            use_option = next(
                opt
                for opt in list(request.options or [])
                if (getattr(opt, "payload", {}) or {}).get("choice") == CHOICE_IGNORE_NEGATIVE
            )
            resolve_decision_command(game, request, use_option.option_id, player_id=p1.id)

        game.request_decision = _auto_resolve

        rolls = iter([4, 4, 4])
        original_get_dice_roll = dice_mod.get_dice_roll
        dice_mod.get_dice_roll = lambda _size=6: next(rolls)
        try:
            profile = _make_profile()
            result = profile.attack(target, attacker.models[0], game.map)
        finally:
            dice_mod.get_dice_roll = original_get_dice_roll

        self.assertIn(DECISION_CHOOSE_HIT_MODIFIER_IGNORES, seen_decisions)
        self.assertIsNotNone(result)
        self.assertTrue(result.hit_results)
        self.assertTrue(result.hit_results[0]["hit"])

    def test_skill_modifier_choice_reuses_immediately_resolved_decision_request(self):
        from warhammer40k_ai.engine.game import BattleRoundPhases
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_SKILL_MODIFIER_IGNORES
        from warhammer40k_ai.rules.doctrina_imperatives import DoctrinaImperativesManager, PROTECTOR_IMPERATIVE
        from warhammer40k_ai.utility import dice as dice_mod
        from warhammer40k_ai.utility.decision_utils import resolve_decision_command
        from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_POSITIVE

        ignore_mods = {
            "name": "Ignore Ranged Modifiers",
            "description": (
                "Each time a model in this unit makes a ranged attack, you can ignore any or all modifiers to "
                "that attack's Ballistic Skill characteristic and any or all modifiers to the Hit roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        doctrina = {"name": "Doctrina Imperatives", "description": "Doctrina Imperatives", "type": "Datasheet", "parameter": ""}

        game, army1, army2, p1, _p2 = _build_game()
        game.turn = 1
        game.phase = BattleRoundPhases.SHOOTING_PHASE
        game.current_player_index = 0

        mgr = DoctrinaImperativesManager(army1)
        mgr.active_imperative_key = PROTECTOR_IMPERATIVE.key
        mgr.active_round = 1
        army1.doctrina_imperatives = mgr

        attacker = _make_unit("Shooter", abilities=[ignore_mods, doctrina])
        target = _make_unit("Target")
        army1.add_unit(attacker)
        army2.add_unit(target)
        attacker.models[0].set_location(0, 0, 0, 0)
        target.models[0].set_location(1, 0, 0, 0)
        game.map.units = [attacker, target]

        seen_decisions = []
        original_request_decision = game.request_decision

        def _auto_resolve(request):
            seen_decisions.append(str(getattr(request, "decision_type", "") or ""))
            original_request_decision(request)
            use_option = next(
                opt
                for opt in list(request.options or [])
                if (getattr(opt, "payload", {}) or {}).get("choice") == CHOICE_IGNORE_POSITIVE
            )
            resolve_decision_command(game, request, use_option.option_id, player_id=p1.id)

        game.request_decision = _auto_resolve

        rolls = iter([3, 4, 4])
        original_get_dice_roll = dice_mod.get_dice_roll
        dice_mod.get_dice_roll = lambda _size=6: next(rolls)
        try:
            profile = _make_profile()
            result = profile.attack(target, attacker.models[0], game.map)
        finally:
            dice_mod.get_dice_roll = original_get_dice_roll

        self.assertIn(DECISION_CHOOSE_SKILL_MODIFIER_IGNORES, seen_decisions)
        self.assertIsNotNone(result)
        self.assertTrue(result.hit_results)
        self.assertFalse(result.hit_results[0]["hit"])

    def test_wound_modifier_choice_reuses_immediately_resolved_decision_request(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_HIT_MODIFIER_IGNORES
        from warhammer40k_ai.utility.decision_utils import resolve_decision_command
        from warhammer40k_ai.utility.modifier_choice import CHOICE_IGNORE_NEGATIVE
        from warhammer40k_ai.units import wargear as wargear_mod

        ignore_mods = {
            "name": "Ignore Wound Modifiers",
            "description": (
                "Each time this model makes a melee attack, you can ignore any or all modifiers to the Wound roll."
            ),
            "type": "Datasheet",
            "parameter": "",
        }

        game, army1, army2, _p1, _p2 = _build_game()
        attacker = _make_unit("Fighter", abilities=[ignore_mods])
        target = _make_unit("Target")
        army1.add_unit(attacker)
        army2.add_unit(target)
        attacker.models[0].set_location(0, 0, 0, 0)
        target.models[0].set_location(1, 0, 0, 0)
        target.special_rules["pain_melee_wound_roll_defense_mod"] = -1
        game.map.units = [attacker, target]

        seen_decisions = []
        original_request_decision = game.request_decision

        def _auto_resolve(request):
            seen_decisions.append(str(getattr(request, "decision_type", "") or ""))
            original_request_decision(request)
            use_option = next(
                opt
                for opt in list(request.options or [])
                if (getattr(opt, "payload", {}) or {}).get("choice") == CHOICE_IGNORE_NEGATIVE
            )
            resolve_decision_command(game, request, use_option.option_id, player_id=attacker.get_parent_army().player.id)

        profile = _make_melee_profile()
        game.request_decision = _auto_resolve

        original_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _size="D6": 4
        try:
            result = profile._wound_target_with_tracking(
                target,
                attacker.models[0],
                {},
                roll_value=None,
                allow_rerolls=False,
                log_roll=False,
            )
        finally:
            wargear_mod.get_roll = original_get_roll

        self.assertIn(DECISION_CHOOSE_HIT_MODIFIER_IGNORES, seen_decisions)
        self.assertTrue(bool(result.get("wound")))


if __name__ == "__main__":
    unittest.main()
