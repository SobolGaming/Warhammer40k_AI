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
                "name": "Test Model",
                "M": str(int(move)),
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


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness: int = 4, move: int = 6, save: str = "3"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
        move=move,
        save=save,
    )
    return Unit(datasheet)


def _build_game(detachment_type: str = "Wrathful Procession"):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE

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


def _make_melee_profile(*, strength: int = 4, ap: int = 0):
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Power Sword", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": str(int(ap)),
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _make_ranged_profile(*, strength: int = 4, ap: int = 0):
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Bolt Rifle", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": str(int(ap)),
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _queue_zealous_litany_request(game, army_sm):
    army_sm.on_battle_round_start(game.turn)
    return next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "zealous_litanies"
    )


def _select_litany(game, sm_player, army_sm, *, key: str):
    request = _queue_zealous_litany_request(game, army_sm)
    option = next(
        opt
        for opt in list(getattr(request, "options", []) or [])
        if str((getattr(opt, "payload", {}) or {}).get("choice_key", "") or "").strip().upper() == str(key).strip().upper()
    )
    return resolve_decision_value(game, request, option.option_id, player_id=sm_player.id)


class TestSpaceMarinesWrathfulProcession(unittest.TestCase):
    def test_zealous_litanies_queues_selection_and_applies_choice(self):
        game, sm_player, _enemy_player, army_sm, _army_enemy = _build_game("Wrathful Procession")
        infantry = _make_unit(
            "Crusader Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(infantry)
        game.rebuild_entity_registry()

        value, apply_result = _select_litany(
            game,
            sm_player,
            army_sm,
            key="CHORUS_OF_RELENTLESS_HATE",
        )
        self.assertIsNotNone(apply_result)
        self.assertTrue(bool(getattr(apply_result, "ok", False)))
        self.assertEqual(str((value or {}).get("choice_key", "")).upper(), "CHORUS_OF_RELENTLESS_HATE")
        mgr = army_sm.space_marines_detachments
        self.assertEqual(str(getattr(mgr, "wrathful_procession_active_litany_key", "")).upper(), "CHORUS_OF_RELENTLESS_HATE")
        self.assertEqual(int(getattr(mgr, "wrathful_procession_active_litany_round", 0) or 0), 1)

    def test_chorus_of_relentless_hate_applies_move_and_advance_bonuses(self):
        game, sm_player, _enemy_player, army_sm, _army_enemy = _build_game("Wrathful Procession")
        infantry = _make_unit(
            "Crusader Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            move=6,
        )
        mounted = _make_unit(
            "Outrider Squad",
            keywords=["MOUNTED"],
            faction_keywords=["ADEPTUS ASTARTES"],
            move=12,
        )
        vehicle = _make_unit(
            "Predator Tank",
            keywords=["VEHICLE"],
            faction_keywords=["ADEPTUS ASTARTES"],
            move=10,
        )
        army_sm.add_unit(infantry)
        army_sm.add_unit(mounted)
        army_sm.add_unit(vehicle)
        game.rebuild_entity_registry()

        _value, apply_result = _select_litany(
            game,
            sm_player,
            army_sm,
            key="CHORUS_OF_RELENTLESS_HATE",
        )
        self.assertTrue(bool(getattr(apply_result, "ok", False)))

        infantry_move = int(infantry.get_effective_model_characteristic(infantry.models[0], "movement"))
        mounted_move = int(mounted.get_effective_model_characteristic(mounted.models[0], "movement"))
        vehicle_move = int(vehicle.get_effective_model_characteristic(vehicle.models[0], "movement"))
        self.assertEqual(infantry_move, 8)
        self.assertEqual(mounted_move, 14)
        self.assertEqual(vehicle_move, 10)

        mods = list(infantry._collect_advance_roll_modifiers() or [])
        self.assertTrue(any(int(val or 0) == 1 and "Zealous Litanies" in str(source or "") for val, source in mods))

    def test_rite_of_perfervid_wrath_adds_melee_strength(self):
        game, sm_player, _enemy_player, army_sm, army_enemy = _build_game("Wrathful Procession")
        attacker = _make_unit(
            "Crusader Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        target = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            toughness=5,
        )
        attacker.deployed = True
        target.deployed = True
        army_sm.add_unit(attacker)
        army_enemy.add_unit(target)
        game.rebuild_entity_registry()

        _value, apply_result = _select_litany(
            game,
            sm_player,
            army_sm,
            key="RITE_OF_PERFERVID_WRATH",
        )
        self.assertTrue(bool(getattr(apply_result, "ok", False)))

        profile = _make_melee_profile(strength=4)
        result = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"distance_to_target": 1.0},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(result.get("wound", False)))
        modifiers = [str(item or "") for item in list(result.get("modifiers", []) or [])]
        self.assertTrue(any("Rite of Perfervid Wrath" in value for value in modifiers))

    def test_chant_of_deathless_devotion_grants_ranged_only_invulnerable_save(self):
        game, sm_player, _enemy_player, army_sm, army_enemy = _build_game("Wrathful Procession")
        defender = _make_unit(
            "Crusader Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
            save="6",
        )
        attacker = _make_unit(
            "Enemy Unit",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            save="3",
        )
        defender.deployed = True
        attacker.deployed = True
        army_sm.add_unit(defender)
        army_enemy.add_unit(attacker)
        game.rebuild_entity_registry()

        _value, apply_result = _select_litany(
            game,
            sm_player,
            army_sm,
            key="CHANT_OF_DEATHLESS_DEVOTION",
        )
        self.assertTrue(bool(getattr(apply_result, "ok", False)))

        ranged_profile = _make_ranged_profile(ap=3)
        ranged_attack = {"mortal_wound": False, "attacker_unit": attacker}
        ranged_save = ranged_profile._save_with_tracking(
            defender.models[0],
            ranged_attack,
            ap=-3,
            roll_value=5,
            allow_rerolls=False,
        )
        self.assertEqual(ranged_save.get("save_type"), "invulnerable")
        self.assertTrue(bool(ranged_save.get("saved", False)))

        melee_profile = _make_melee_profile(ap=3)
        melee_attack = {"mortal_wound": False, "attacker_unit": attacker}
        melee_save = melee_profile._save_with_tracking(
            defender.models[0],
            melee_attack,
            ap=-3,
            roll_value=5,
            allow_rerolls=False,
        )
        self.assertIsNone(melee_attack.get("inv_save_override"))
        self.assertFalse(bool(melee_save.get("saved", False)))

    def test_zealous_litanies_none_option_leaves_no_active_litany(self):
        game, sm_player, _enemy_player, army_sm, _army_enemy = _build_game("Wrathful Procession")
        infantry = _make_unit(
            "Crusader Squad",
            keywords=["INFANTRY"],
            faction_keywords=["ADEPTUS ASTARTES"],
        )
        army_sm.add_unit(infantry)
        game.rebuild_entity_registry()

        request = _queue_zealous_litany_request(game, army_sm)
        none_option = next(
            opt
            for opt in list(getattr(request, "options", []) or [])
            if bool((getattr(opt, "payload", {}) or {}).get("skip", False))
        )
        value, apply_result = resolve_decision_value(game, request, none_option.option_id, player_id=sm_player.id)

        self.assertIsNotNone(apply_result)
        self.assertTrue(bool(getattr(apply_result, "ok", False)))
        self.assertEqual(str((value or {}).get("choice_key", "")), "")
        mgr = army_sm.space_marines_detachments
        self.assertEqual(str(getattr(mgr, "wrathful_procession_active_litany_key", "")), "")
        self.assertFalse(mgr.can_select_zealous_litany(game=game))


if __name__ == "__main__":
    unittest.main()
