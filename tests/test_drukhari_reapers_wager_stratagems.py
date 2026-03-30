from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Drukhari",
        keywords=None,
        faction_keywords=None,
        movement: int = 8,
        wounds: int = 3,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            if faction_name == "Drukhari":
                faction_keywords = ["DRUKHARI"]
            else:
                faction_keywords = [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(movement)),
                "T": "4",
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
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Drukhari",
    keywords=None,
    faction_keywords=None,
    movement: int = 8,
    wounds: int = 3,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    drukhari_army = Army("Drukhari", "Reaper's Wager")
    drukhari_army.faction_id = "DRU"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("Drukhari", control=PlayerControl.LOCAL, army=drukhari_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    p1.command_points = 10
    p2.command_points = 10
    game.turn = 1
    game.current_player_index = 0

    drukhari_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    return game, p1, p2, drukhari_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _first_request(game: Game, decision_type: str, *, ability: str = "", kind: str = ""):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if ability and str(ctx.get("ability", "") or "") != str(ability):
            continue
        request_kind = str(ctx.get("kind", "") or ctx.get("reactive_move_kind", "") or "")
        if kind and request_kind != str(kind):
            continue
        return request
    return None


def _find_option(request, *, choice_key: str):
    target = str(choice_key or "").strip().upper()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("choice_key", "") or "").strip().upper() == target:
            return option
    return None


def _make_wargear(
    name: str,
    *,
    melee: bool,
    attacks: str = "2",
    skill: str = "4+",
    range_value: str = "24",
    strength: str = "4",
    ap: str = "0",
    damage: str = "1",
):
    return Wargear(
        {
            "name": name,
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else str(range_value),
            "A": str(attacks),
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": str(ap),
            "D": str(damage),
            "description": "",
        }
    )


class TestDrukhariReapersWagerStratagems(unittest.TestCase):
    def test_reapers_wager_descriptors_registered(self):
        expected = {
            "000009782002": ("MALICIOUS FRENZY", "keyword"),
            "000009782003": ("FATEFUL ROLE", "fight_on_death"),
            "000009782005": ("SHORTEN THE ODDS", "advance"),
            "000009782006": ("SCINTILLATING TEMPO", "overwatch"),
            "000009782007": ("DANCE MACABRE", "reactive"),
        }
        for stratagem_id, (name, effect_hint) in expected.items():
            with self.subTest(stratagem_id=stratagem_id):
                desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
                self.assertIsNotNone(desc)
                self.assertEqual(str(getattr(desc, "name", "") or ""), name)
                self.assertIn(effect_hint, str(getattr(desc, "effect", "") or "").lower())

    def test_scintillating_tempo_queues_on_move_start_and_blocks_overwatch_until_end_of_turn(self):
        game, p1, _p2, drukhari_army, enemy_army = _build_game()
        source = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(source)
        enemy_army.add_unit(enemy)
        _place_unit(game, source, 10.0, 10.0)
        _place_unit(game, enemy, 18.0, 10.0)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        game.event_system.publish("unit_move_started", unit=source, action="move")
        pending = _pending_by_name(p1.stratagems, "SCINTILLATING TEMPO")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            "SCINTILLATING TEMPO",
            unit=source,
            phase_name="Movement phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        self.assertTrue(source.is_overwatch_prevented_against(enemy, game=game))

        game.current_player_index = 1
        self.assertFalse(source.is_overwatch_prevented_against(enemy, game=game))

        game.current_player_index = 0
        game.turn = 2
        self.assertFalse(source.is_overwatch_prevented_against(enemy, game=game))

    def test_scintillating_tempo_queues_on_set_up(self):
        game, p1, _p2, drukhari_army, _enemy_army = _build_game()
        source = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(source)
        _place_unit(game, source, 10.0, 10.0)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        game.event_system.publish("unit_set_up", unit=source)
        pending = _pending_by_name(p1.stratagems, "SCINTILLATING TEMPO")
        self.assertIsNotNone(pending)

    def test_scintillating_tempo_applies_to_harlequins_units(self):
        game, p1, _p2, drukhari_army, enemy_army = _build_game()
        harlequin = _make_unit(
            "Troupe",
            faction_name="Aeldari",
            keywords=["INFANTRY", "HARLEQUINS"],
            faction_keywords=["HARLEQUINS"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(harlequin)
        enemy_army.add_unit(enemy)
        _place_unit(game, harlequin, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)

        _set_phase(game, p1, "CHARGE_PHASE", 0)
        game.event_system.publish("charge_declared", unit=harlequin, target_units=[enemy])
        pending = _pending_by_name(p1.stratagems, "SCINTILLATING TEMPO")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            "SCINTILLATING TEMPO",
            unit=harlequin,
            phase_name="Charge phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertTrue(harlequin.is_overwatch_prevented_against(enemy, game=game))

    def test_malicious_frenzy_prompts_for_choice_and_applies_ranged_keyword_only(self):
        game, p1, _p2, drukhari_army, enemy_army = _build_game()
        kabalites = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        kabalites.models[0].wargear = [
            _make_wargear("Splinter Rifle", melee=False),
            _make_wargear("Hekatarii Blade", melee=True),
        ]
        drukhari_army.add_unit(kabalites)
        enemy_army.add_unit(enemy)
        _place_unit(game, kabalites, 10.0, 10.0)
        _place_unit(game, enemy, 14.0, 10.0)

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        ok = p1.stratagems.use("MALICIOUS FRENZY", unit=kabalites, phase_name="Shooting phase")
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        request = _first_request(
            game,
            DECISION_CHOOSE_QUARRY,
            ability="drukhari_reapers_wager_malicious_frenzy_choice",
        )
        self.assertIsNotNone(request)
        option = _find_option(request, choice_key="LETHAL_HITS")
        self.assertIsNotNone(option)
        result = resolve_decision_command(game, request, option.option_id, player_id=p1.id)
        self.assertTrue(bool(getattr(result, "ok", False)))

        ranged_bonuses = list(kabalites.models[0].get_temporary_weapon_keyword_bonuses("Splinter Rifle") or [])
        melee_bonuses = list(kabalites.models[0].get_temporary_weapon_keyword_bonuses("Hekatarii Blade") or [])
        self.assertTrue(
            any(
                str(entry.get("keyword", "") or "").strip().upper() == "LETHAL HITS"
                and str(entry.get("attack_type", "") or "").strip().lower() == "ranged"
                for entry in ranged_bonuses
            )
        )
        self.assertEqual(melee_bonuses, [])

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        self.assertEqual(list(kabalites.models[0].get_temporary_weapon_keyword_bonuses("Splinter Rifle") or []), [])

    def test_malicious_frenzy_fight_choice_applies_melee_keyword_only(self):
        game, p1, p2, drukhari_army, enemy_army = _build_game()
        troupe = _make_unit(
            "Troupe",
            faction_name="Aeldari",
            keywords=["INFANTRY", "HARLEQUINS"],
            faction_keywords=["HARLEQUINS"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        troupe.models[0].wargear = [
            _make_wargear("Shuriken Pistol", melee=False),
            _make_wargear("Harlequin Blade", melee=True),
        ]
        drukhari_army.add_unit(troupe)
        enemy_army.add_unit(enemy)
        _place_unit(game, troupe, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        ok = p1.stratagems.use(
            "MALICIOUS FRENZY",
            unit=troupe,
            phase_name="Fight phase",
            choice_key="SUSTAINED_HITS_1",
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        ranged_bonuses = list(troupe.models[0].get_temporary_weapon_keyword_bonuses("Shuriken Pistol") or [])
        melee_bonuses = list(troupe.models[0].get_temporary_weapon_keyword_bonuses("Harlequin Blade") or [])
        self.assertEqual(ranged_bonuses, [])
        self.assertTrue(
            any(
                str(entry.get("keyword", "") or "").strip().upper() == "SUSTAINED HITS 1"
                and str(entry.get("attack_type", "") or "").strip().lower() == "melee"
                for entry in melee_bonuses
            )
        )

    def test_shorten_the_odds_queues_on_advance_and_grants_shoot_and_charge(self):
        game, p1, _p2, drukhari_army, _enemy_army = _build_game()
        wyches = _make_unit(
            "Wyches",
            keywords=["INFANTRY", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(wyches)
        _place_unit(game, wyches, 10.0, 10.0)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        wyches.round_state.advanced_this_round = True
        game.event_system.publish("unit_move_ended", unit=wyches, action="advance")
        pending = _pending_by_name(p1.stratagems, "SHORTEN THE ODDS")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("SHORTEN THE ODDS", unit=wyches, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        self.assertTrue(wyches.has_advance_and_shoot())
        self.assertTrue(wyches.has_advance_and_charge())

        game.turn = 2
        if hasattr(wyches, "_invalidate_ability_cache"):
            wyches._invalidate_ability_cache()
        self.assertFalse(wyches.has_advance_and_shoot())
        self.assertFalse(wyches.has_advance_and_charge())

    def test_dance_macabre_queues_on_enemy_move_and_uses_d6_when_not_losing(self):
        game, p1, p2, drukhari_army, enemy_army = _build_game()
        kabalites = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(kabalites)
        enemy_army.add_unit(enemy)
        _place_unit(game, kabalites, 10.0, 10.0)
        _place_unit(game, enemy, 14.0, 10.0)

        _set_phase(game, p2, "MOVEMENT_PHASE", 1)
        game.event_system.publish("unit_move_ended", unit=enemy, action="move")
        pending = _pending_by_name(p1.stratagems, "DANCE MACABRE")
        self.assertIsNotNone(pending)

        with patch("warhammer40k_ai.rules.stratagems_drukhari.dice_module.get_roll", return_value=4):
            ok = p1.stratagems.use("DANCE MACABRE", unit=kabalites, enemy_unit=enemy, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 8)
        request = _first_request(game, DECISION_MOVE_UNIT, kind="drukhari_reapers_wager_dance_macabre")
        self.assertIsNotNone(request)
        self.assertEqual(int(request.context.get("max_distance", 0) or 0), 4)

    def test_dance_macabre_uses_fixed_six_when_target_is_losing_the_wager(self):
        game, p1, p2, drukhari_army, enemy_army = _build_game()
        troupe = _make_unit(
            "Troupe",
            faction_name="Aeldari",
            keywords=["INFANTRY", "HARLEQUINS"],
            faction_keywords=["HARLEQUINS"],
        )
        enemy = _make_unit(
            "Enemy Unit",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(troupe)
        enemy_army.add_unit(enemy)
        _place_unit(game, troupe, 10.0, 10.0)
        _place_unit(game, enemy, 14.0, 10.0)
        mgr = drukhari_army.drukhari_detachments
        mgr.initialize_callous_competition(battle_round=1, player=p1)
        mgr.set_callous_competition_winning_side("DRUKHARI")

        _set_phase(game, p2, "MOVEMENT_PHASE", 1)
        game.event_system.publish("unit_move_ended", unit=enemy, action="advance")
        pending = _pending_by_name(p1.stratagems, "DANCE MACABRE")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("DANCE MACABRE", unit=troupe, enemy_unit=enemy, dequeue=True)
        self.assertTrue(ok)
        request = _first_request(game, DECISION_MOVE_UNIT, kind="drukhari_reapers_wager_dance_macabre")
        self.assertIsNotNone(request)
        self.assertEqual(int(request.context.get("max_distance", 0) or 0), 6)

    def test_fateful_role_reacts_to_enemy_fight_and_grants_fight_on_death_with_losing_bonus(self):
        game, p1, p2, drukhari_army, enemy_army = _build_game()
        troupe = _make_unit(
            "Troupe",
            faction_name="Aeldari",
            keywords=["INFANTRY", "HARLEQUINS"],
            faction_keywords=["HARLEQUINS"],
            wounds=4,
        )
        enemy = _make_unit(
            "Enemy Fighters",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
            wounds=4,
        )
        drukhari_army.add_unit(troupe)
        enemy_army.add_unit(enemy)
        _place_unit(game, troupe, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)
        mgr = drukhari_army.drukhari_detachments
        mgr.initialize_callous_competition(battle_round=1, player=p1)
        mgr.set_callous_competition_winning_side("DRUKHARI")

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[troupe])
        self.assertIsNotNone(_pending_by_name(p1.stratagems, "FATEFUL ROLE"))

        ok = p1.stratagems.use(
            "FATEFUL ROLE",
            unit=troupe,
            attacking_unit=enemy,
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        model = troupe.models[0]
        rule = troupe.get_melee_fight_on_death_after_attacks_rule(model=model)
        self.assertIsInstance(rule, dict)
        self.assertEqual(int(rule.get("threshold", 0) or 0), 4)
        self.assertEqual(int(rule.get("roll_modifier", 0) or 0), 1)
        self.assertIn("FATEFUL ROLE", str(rule.get("source", "")).upper())

        troupe.round_state.fought_this_phase = False
        troupe._last_destroyed_by_weapon_profile = _make_wargear("Enemy Blade", melee=True).profiles["default"]
        with patch("warhammer40k_ai.units.unit_mixins.damage_death_mixin.get_roll", return_value=3):
            model._wounds = 0
            troupe._handle_model_destroyed(model, game.map)
        pending_models = list(getattr(troupe, "_melee_fight_on_death_pending_models", []) or [])
        self.assertIn(model, pending_models)

        _set_phase(game, p2, "COMMAND_PHASE", 1)
        self.assertIsNone(troupe.get_melee_fight_on_death_after_attacks_rule(model=model))


if __name__ == "__main__":
    unittest.main()
