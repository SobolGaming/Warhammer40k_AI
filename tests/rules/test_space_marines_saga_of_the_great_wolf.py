import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.phase import BattleRoundPhases


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        save: str = "3",
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
                "T": str(int(toughness)),
                "Sv": str(save),
                "W": "3",
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


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4, save: str = "3"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
        save=save,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Saga of the Great Wolf"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE

    army_sm = Army("Space Marines", detachment_type)
    army_sm.faction_id = "SM"
    army_enemy = Army("Enemy", "Other")
    army_enemy.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=army_sm)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    return game, sm_player, enemy_player, army_sm, army_enemy


def _make_ranged_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

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


def _make_melee_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Frost Blade", is_melee=lambda: True, is_ranged=lambda: False)
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


class TestSpaceMarinesSagaOfTheGreatWolf(unittest.TestCase):
    def test_command_phase_queues_master_of_wolves_selection(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY

        game, sm_player, _enemy_player, army_sm, _army_enemy = _build_game()
        unit = _make_unit(
            "Grey Hunters",
            keywords=["INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        )
        army_sm.add_unit(unit)
        unit.deployed = True

        game.event_system.publish("phase_start", player=sm_player, phase=BattleRoundPhases.COMMAND_PHASE)
        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "master_of_wolves_selection"
        ]
        self.assertEqual(len(pending), 1)
        labels = [str(getattr(opt, "label", "") or "") for opt in list(getattr(pending[0], "options", []) or [])]
        self.assertIn("None", labels)
        self.assertTrue(any("Encircling Jaws" in label for label in labels))
        self.assertTrue(any("Hunter's Eye" in label for label in labels))
        self.assertTrue(any("Ferocious Strike" in label for label in labels))

    def test_encircling_jaws_grants_advance_and_charge_rerolls(self):
        game, _sm_player, _enemy_player, army_sm, _army_enemy = _build_game()
        manager = army_sm.space_marines_detachments
        unit = _make_unit(
            "Grey Hunters",
            keywords=["INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        )
        army_sm.add_unit(unit)
        unit.deployed = True

        self.assertTrue(manager.select_master_of_wolves_pack("ENCIRCLING_JAWS", battle_round=1, game=game))
        self.assertTrue(unit.can_reroll_advance_roll())
        self.assertTrue(unit.can_reroll_charge_roll(game=game))

    def test_hunters_eye_adds_one_to_ranged_hit_roll(self):
        game, _sm_player, _enemy_player, army_sm, army_enemy = _build_game()
        manager = army_sm.space_marines_detachments
        attacker = _make_unit(
            "Grey Hunters",
            keywords=["INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        attacker.deployed = True
        target.deployed = True
        game.rebuild_entity_registry()

        self.assertTrue(manager.select_master_of_wolves_pack("HUNTERS_EYE", battle_round=1, game=game))

        profile = _make_ranged_profile()
        hit = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {},
            roll_value=2,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(hit.get("hit", False)))
        self.assertTrue(any("Hunter's Eye" in str(m) for m in list(hit.get("modifiers", []) or [])))

    def test_ferocious_strike_choice_grants_selected_keyword(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from warhammer40k_ai.utility.decision_utils import resolve_decision_value

        game, sm_player, _enemy_player, army_sm, army_enemy = _build_game()
        manager = army_sm.space_marines_detachments
        attacker = _make_unit(
            "Wolf Guard",
            keywords=["INFANTRY", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        attacker.deployed = True
        target.deployed = True
        game.rebuild_entity_registry()

        self.assertTrue(manager.select_master_of_wolves_pack("FEROCIOUS_STRIKE", battle_round=1, game=game))
        game.phase = BattleRoundPhases.FIGHT_PHASE

        game.event_system.publish("fight_unit_selected", unit=attacker, selecting_player=sm_player)
        request = next(
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "master_of_wolves_ferocious_strike"
        )
        target_option = next(
            opt
            for opt in list(getattr(request, "options", []) or [])
            if str((getattr(opt, "payload", {}) or {}).get("choice", "") or "") == "LETHAL_HITS"
        )
        _value, apply_result = resolve_decision_value(game, request, target_option.option_id, player_id=sm_player.id)
        self.assertTrue(bool(getattr(apply_result, "ok", False)))

        profile = _make_melee_profile()
        attack_instance = {}
        hit = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            attack_instance,
            roll_value=6,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(attack_instance.get("lethal_hit", False)))
        self.assertTrue(any("Lethal Hits" in str(s) for s in list(hit.get("special_effects", []) or [])))

    def test_howling_onslaught_allows_one_reuse_with_logan_grimnar(self):
        game, _sm_player, _enemy_player, army_sm, _army_enemy = _build_game()
        manager = army_sm.space_marines_detachments
        logan = _make_unit(
            "Logan Grimnar",
            keywords=["INFANTRY", "CHARACTER", "SPACE WOLVES"],
            faction_keywords=["ADEPTUS ASTARTES", "SPACE WOLVES"],
        )
        army_sm.add_unit(logan)
        logan.deployed = True

        self.assertTrue(manager.select_master_of_wolves_pack("ENCIRCLING_JAWS", battle_round=1, game=game))
        manager.master_of_wolves_begin_command_phase(battle_round=2)
        self.assertTrue(manager.select_master_of_wolves_pack("HUNTERS_EYE", battle_round=2, game=game))
        manager.master_of_wolves_begin_command_phase(battle_round=3)
        self.assertTrue(manager.select_master_of_wolves_pack("ENCIRCLING_JAWS", battle_round=3, game=game))
        self.assertTrue(bool(manager.master_of_wolves_howling_onslaught_used))
        manager.master_of_wolves_begin_command_phase(battle_round=4)
        self.assertFalse(manager.select_master_of_wolves_pack("HUNTERS_EYE", battle_round=4, game=game))


if __name__ == "__main__":
    unittest.main()
