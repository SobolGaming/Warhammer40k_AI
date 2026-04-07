import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.utility.decision_utils import resolve_decision_value


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        move: int = 6,
    ):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": "3",
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


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4, move: int = 6):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
        move=move,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Librarius Conclave"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    army_sm = Army.with_detachment("Space Marines", detachment_type)
    army_sm.faction_id = "SM"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=army_sm)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    return game, sm_player, enemy_player, army_sm, army_enemy


def _make_ranged_profile(*, strength: str = "4", ap: str = "0"):
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Force Bolt", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": str(ap),
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _queue_and_select_discipline(game, sm_player, army_sm, *, key: str):
    army_sm.on_battle_round_start(game.turn)
    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "librarius_psychic_disciplines"
    )
    option = next(
        opt
        for opt in list(getattr(request, "options", []) or [])
        if str((getattr(opt, "payload", {}) or {}).get("choice_key", "") or "").strip().upper() == str(key).strip().upper()
    )
    value, apply_result = resolve_decision_value(game, request, option.option_id, player_id=sm_player.id)
    return value, apply_result


class TestSpaceMarinesLibrariusConclave(unittest.TestCase):
    def test_psychic_disciplines_queues_selection_and_applies_choice(self):
        game, sm_player, _enemy_player, army_sm, _army_enemy = _build_game("Librarius Conclave")
        psyker = _make_unit(
            "Librarian Squad",
            keywords=["INFANTRY", "PSYKER"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(psyker)
        game.rebuild_entity_registry()

        value, apply_result = _queue_and_select_discipline(
            game,
            sm_player,
            army_sm,
            key="BIOMANCY",
        )

        self.assertIsNotNone(apply_result)
        self.assertTrue(bool(getattr(apply_result, "ok", False)))
        self.assertEqual(str((value or {}).get("choice_key", "")).upper(), "BIOMANCY")
        mgr = army_sm.space_marines_detachments
        self.assertEqual(str(getattr(mgr, "librarius_psychic_discipline_key", "")).upper(), "BIOMANCY")
        self.assertEqual(int(getattr(mgr, "librarius_psychic_discipline_round", 0) or 0), 1)

    def test_biomancy_adds_movement_to_adeptus_astartes_psykers_only(self):
        game, sm_player, _enemy_player, army_sm, _army_enemy = _build_game("Librarius Conclave")
        psyker = _make_unit(
            "Librarian Squad",
            keywords=["INFANTRY", "PSYKER"],
            faction_keywords=["ADEPTUS ASTARTES"],
            move=6,
        )
        non_psyker = _make_unit(
            "Intercessor Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            move=6,
        )
        army_sm.add_unit(psyker)
        army_sm.add_unit(non_psyker)
        game.rebuild_entity_registry()

        _value, apply_result = _queue_and_select_discipline(
            game,
            sm_player,
            army_sm,
            key="BIOMANCY",
        )
        self.assertTrue(bool(getattr(apply_result, "ok", False)))

        psyker_move = int(psyker.get_effective_model_characteristic(psyker.models[0], "movement"))
        non_psyker_move = int(non_psyker.get_effective_model_characteristic(non_psyker.models[0], "movement"))
        self.assertEqual(psyker_move, 8)
        self.assertEqual(non_psyker_move, 6)

    def test_divination_rerolls_hit_and_wound_rolls_of_one(self):
        game, sm_player, _enemy_player, army_sm, army_enemy = _build_game("Librarius Conclave")
        attacker = _make_unit(
            "Librarian Squad",
            keywords=["INFANTRY", "PSYKER"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness=4,
        )
        attacker.deployed = True
        target.deployed = True
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        game.rebuild_entity_registry()

        _value, apply_result = _queue_and_select_discipline(
            game,
            sm_player,
            army_sm,
            key="DIVINATION",
        )
        self.assertTrue(bool(getattr(apply_result, "ok", False)))

        profile = _make_ranged_profile(strength="4")
        hit_result = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 10.0},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
        wound_result = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 10.0},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )

        self.assertIn(1, list(hit_result.get("reroll_values", []) or []))
        self.assertTrue(
            any("Divination" in str(reason) for reason in list(hit_result.get("reroll_value_reasons", []) or []))
        )
        self.assertIn(1, list(wound_result.get("reroll_values", []) or []))
        self.assertTrue(
            any("Divination" in str(reason) for reason in list(wound_result.get("reroll_value_reasons", []) or []))
        )

    def test_pyromancy_improves_ranged_ap_within_12(self):
        game, sm_player, _enemy_player, army_sm, army_enemy = _build_game("Librarius Conclave")
        attacker = _make_unit(
            "Librarian Squad",
            keywords=["INFANTRY", "PSYKER"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        attacker.deployed = True
        target.deployed = True
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        game.map.units = [attacker, target]
        game.rebuild_entity_registry()

        _value, apply_result = _queue_and_select_discipline(
            game,
            sm_player,
            army_sm,
            key="PYROMANCY",
        )
        self.assertTrue(bool(getattr(apply_result, "ok", False)))

        attacker.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        target.models[0].set_location(20.0, 10.0, 0.0, 0.0)
        profile = _make_ranged_profile(ap="0")
        self.assertEqual(int(profile.get_effective_ap(attacker.models[0], target)), -1)

        target.models[0].set_location(25.0, 10.0, 0.0, 0.0)
        self.assertEqual(int(profile.get_effective_ap(attacker.models[0], target)), 0)

    def test_telekinesis_reduces_incoming_ranged_strength_against_psyker_units(self):
        game, sm_player, _enemy_player, army_sm, army_enemy = _build_game("Librarius Conclave")
        defender = _make_unit(
            "Librarian Squad",
            keywords=["INFANTRY", "PSYKER"],
            faction_keywords=["ADEPTUS ASTARTES"],
            toughness=4,
        )
        attacker = _make_unit(
            "Enemy Shooters",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        defender.deployed = True
        attacker.deployed = True
        army_sm.add_unit(defender)
        army_enemy.add_unit(attacker)
        game.rebuild_entity_registry()

        _value, apply_result = _queue_and_select_discipline(
            game,
            sm_player,
            army_sm,
            key="TELEKINESIS",
        )
        self.assertTrue(bool(getattr(apply_result, "ok", False)))

        profile = _make_ranged_profile(strength="4")
        wound_result = profile._wound_target_with_tracking(
            defender,
            attacker.models[0],
            {"distance_to_target": 10.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(wound_result.get("success", False)))
        self.assertTrue(any("Telekinesis" in str(mod) for mod in list(wound_result.get("modifiers", []) or [])))

    def test_telepathy_can_ignore_negative_hit_modifiers(self):
        game, sm_player, _enemy_player, army_sm, army_enemy = _build_game("Librarius Conclave")
        attacker = _make_unit(
            "Librarian Squad",
            keywords=["INFANTRY", "PSYKER"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        attacker.deployed = True
        target.deployed = True
        target.has_stealth = lambda: True
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        game.rebuild_entity_registry()

        _value, apply_result = _queue_and_select_discipline(
            game,
            sm_player,
            army_sm,
            key="TELEPATHY",
        )
        self.assertTrue(bool(getattr(apply_result, "ok", False)))

        profile = _make_ranged_profile()
        attack_instance = {}
        hit_result = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            attack_instance,
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(hit_result.get("hit", False)))


if __name__ == "__main__":
    unittest.main()
