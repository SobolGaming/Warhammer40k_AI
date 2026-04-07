from __future__ import annotations

import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_MURDEROUS_AGENDA
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


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
        model_count: int = 1,
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
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
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
    model_count: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            wounds=wounds,
            model_count=model_count,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    drukhari_army = Army.with_detachment("Drukhari", "Kabalite Cartel")
    drukhari_army.faction_id = "DRU"
    enemy_army = Army.with_detachment("Enemy", "Other")
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
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 2.0, float(y), 0.0, 0.0)
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


def _find_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == str(decision_type):
            return request
    return None


def _ranged_profile(*, name: str = "Splinter Rifle", skill: str = "4+", ap: str = "-1", damage: str = "1"):
    weapon = Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": "4",
            "AP": str(ap),
            "D": str(damage),
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _melee_profile(*, name: str = "Blade", skill: str = "4+", damage: str = "1"):
    weapon = Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": str(skill),
            "S": "4",
            "AP": "0",
            "D": str(damage),
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _living_models(unit: Unit) -> int:
    return sum(
        1
        for model in list(getattr(unit, "models", []) or [])
        if bool(model.is_alive() if callable(getattr(model, "is_alive", None)) else getattr(model, "is_alive", False))
    )


class TestDrukhariKabaliteCartelStratagems(unittest.TestCase):
    def test_all_kabalite_cartel_descriptors_registered(self):
        expected = {
            "000010589007": ("Deadly Deceivers", "ranged_targeting_range_restriction"),
            "000010589002": ("Double-Cross", "redirect_pre_save_damage_to_support_unit_as_mortal_wounds"),
            "000010589005": ("Enemies Without Number", "reselect_murderous_agenda_contract"),
            "000010589006": ("Making a Point", "ranged_ballistic_skill_and_ap_bonus"),
            "000010589004": ("Tailored Toxins", "contract_target_crit_hits_on_five_plus"),
            "000010589003": ("Taken Alive", "melee_hit_bonus_and_enemy_battleshock_if_contract_destroyed"),
        }

        for stratagem_id, (name, effect) in expected.items():
            with self.subTest(stratagem_id=stratagem_id):
                desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
                self.assertIsNotNone(desc)
                self.assertEqual(str(getattr(desc, "name", "") or ""), name)
                self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_making_a_point_improves_ranged_skill_and_ap_until_phase_end(self):
        game, p1, _p2, drukhari_army, enemy_army = _build_game()
        kabalites = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "KABAL", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(kabalites)
        enemy_army.add_unit(enemy)
        _place_unit(game, kabalites, 10.0, 10.0)
        _place_unit(game, enemy, 18.0, 10.0)
        game.rebuild_entity_registry()

        profile = _ranged_profile(skill="4+", ap="-1")
        _set_phase(game, p1, "SHOOTING_PHASE", 0)

        before = profile._hit_target_with_tracking(
            enemy,
            kabalites.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(before.get("hit")))
        self.assertEqual(int(profile.get_effective_ap(kabalites.models[0], enemy) or 0), -1)

        ok = p1.stratagems.use("MAKING A POINT", unit=kabalites, phase_name="Shooting phase")
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        during = profile._hit_target_with_tracking(
            enemy,
            kabalites.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(during.get("hit")))
        self.assertEqual(int(profile.get_effective_ap(kabalites.models[0], enemy) or 0), -2)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        after = profile._hit_target_with_tracking(
            enemy,
            kabalites.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(after.get("hit")))
        self.assertEqual(int(profile.get_effective_ap(kabalites.models[0], enemy) or 0), -1)

    def test_tailored_toxins_sets_critical_hits_on_five_plus_against_contract_only(self):
        game, p1, _p2, drukhari_army, enemy_army = _build_game()
        kabalites = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "KABAL", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        contract = _make_unit(
            "Enemy Captain",
            faction_name="Enemy",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        other_enemy = _make_unit(
            "Enemy Troops",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(kabalites)
        enemy_army.add_unit(contract)
        enemy_army.add_unit(other_enemy)
        _place_unit(game, kabalites, 10.0, 10.0)
        _place_unit(game, contract, 18.0, 10.0)
        _place_unit(game, other_enemy, 22.0, 10.0)
        game.rebuild_entity_registry()

        mgr = drukhari_army.drukhari_detachments
        self.assertTrue(mgr.select_murderous_agenda("TROPHY_HUNTERS", contract._id, game=game, player=p1))

        profile = _ranged_profile(skill="4+", ap="0")
        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        ok = p1.stratagems.use("TAILORED TOXINS", unit=kabalites, phase_name="Shooting phase")
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        crit_hit = profile._hit_target_with_tracking(
            contract,
            kabalites.models[0],
            {},
            roll_value=5,
            allow_rerolls=False,
            log_roll=False,
        )
        other_hit = profile._hit_target_with_tracking(
            other_enemy,
            kabalites.models[0],
            {},
            roll_value=5,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertEqual(int(crit_hit.get("crit_threshold", 0) or 0), 5)
        self.assertTrue(any("critical hit (5+)" in str(effect).lower() for effect in list(crit_hit.get("special_effects", []) or [])))
        self.assertNotEqual(int(other_hit.get("crit_threshold", 0) or 0), 5)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        after = profile._hit_target_with_tracking(
            contract,
            kabalites.models[0],
            {},
            roll_value=5,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertNotEqual(int(after.get("crit_threshold", 0) or 0), 5)

    def test_taken_alive_grants_hit_bonus_until_phase_end(self):
        game, p1, _p2, drukhari_army, enemy_army = _build_game()
        wyches = _make_unit(
            "Wyches",
            keywords=["INFANTRY", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(wyches)
        enemy_army.add_unit(enemy)
        _place_unit(game, wyches, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)
        game.rebuild_entity_registry()

        profile = _melee_profile(skill="4+")
        _set_phase(game, p1, "FIGHT_PHASE", 0)

        before = profile._hit_target_with_tracking(
            enemy,
            wyches.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(before.get("hit")))

        ok = p1.stratagems.use("TAKEN ALIVE", unit=wyches, phase_name="Fight phase")
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        during = profile._hit_target_with_tracking(
            enemy,
            wyches.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(during.get("hit")))

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        after = profile._hit_target_with_tracking(
            enemy,
            wyches.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(after.get("hit")))

    def test_taken_alive_forces_enemy_battleshock_and_caps_pain_tokens_at_three(self):
        game, p1, _p2, drukhari_army, enemy_army = _build_game()
        incubi = _make_unit(
            "Incubi",
            keywords=["INFANTRY", "BLADES FOR HIRE", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        contract = _make_unit(
            "Enemy Captain",
            faction_name="Enemy",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy_a = _make_unit("Enemy A", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_b = _make_unit("Enemy B", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_c = _make_unit("Enemy C", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        enemy_d = _make_unit("Enemy D", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        drukhari_army.add_unit(incubi)
        for unit in [contract, enemy_a, enemy_b, enemy_c, enemy_d]:
            enemy_army.add_unit(unit)
        _place_unit(game, incubi, 10.0, 10.0)
        _place_unit(game, contract, 12.0, 10.0)
        _place_unit(game, enemy_a, 20.0, 10.0)
        _place_unit(game, enemy_b, 22.0, 10.0)
        _place_unit(game, enemy_c, 24.0, 10.0)
        _place_unit(game, enemy_d, 26.0, 10.0)
        game.rebuild_entity_registry()

        mgr = drukhari_army.drukhari_detachments
        self.assertTrue(mgr.select_murderous_agenda("TROPHY_HUNTERS", contract._id, game=game, player=p1))

        forced = []
        for unit in [enemy_a, enemy_b, enemy_c, enemy_d]:
            unit.force_battle_shock_test = (
                lambda unit_name: (
                    lambda *, current_turn, modifier=0, source="": forced.append(
                        (unit_name, int(current_turn), int(modifier), str(source or ""))
                    )
                )
            )(unit.name)

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        ok = p1.stratagems.use("TAKEN ALIVE", unit=incubi, phase_name="Fight phase")
        self.assertTrue(ok)

        contract.models[0].die(game_map=game.map)
        p1.stratagems._on_fight_attacks_resolved(unit=incubi, target_unit=contract)
        self.assertEqual(
            sorted(forced),
            sorted(
                [
                    ("Enemy A", 1, 0, "TAKEN ALIVE"),
                    ("Enemy B", 1, 0, "TAKEN ALIVE"),
                    ("Enemy C", 1, 0, "TAKEN ALIVE"),
                    ("Enemy D", 1, 0, "TAKEN ALIVE"),
                ]
            ),
        )

        pfp = drukhari_army.power_from_pain
        pfp.tokens = 0
        for unit in [enemy_a, enemy_b, enemy_c, enemy_d]:
            pfp.tokens = int(getattr(pfp, "tokens", 0) or 0) + 1
            mgr.on_battle_shock_test_resolved(unit, passed=False, game=game)
        self.assertEqual(int(getattr(pfp, "tokens", 0) or 0), 3)
        self.assertEqual(int(mgr.kabalite_taken_alive_failed_test_count or 0), 4)

    def test_deadly_deceivers_queues_applies_targeting_cap_and_cleans_up(self):
        game, p1, p2, drukhari_army, enemy_army = _build_game()
        target = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "KABAL", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        attacker = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(target)
        enemy_army.add_unit(attacker)
        _place_unit(game, target, 10.0, 10.0)
        _place_unit(game, attacker, 30.0, 10.0)
        game.map.can_model_see_model = lambda _source, _target: True
        game.rebuild_entity_registry()

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[target])
        pending = _pending_by_name(p1.stratagems, "DEADLY DECEIVERS")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            "DEADLY DECEIVERS",
            unit=target,
            attacking_unit=attacker,
            phase_name="Shooting phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        profile = _ranged_profile(skill="4+", ap="0")
        limit, sources = target.get_ranged_targeting_restriction(game_map=game.map)
        self.assertEqual(float(limit or 0.0), 18.0)
        self.assertTrue(any("DEADLY DECEIVERS" in str(source).upper() for source in list(sources or [])))
        self.assertFalse(attacker._can_model_shoot_weapon_at_target(attacker.models[0], profile, target, game.map))

        attacker.models[0].set_location(24.0, 10.0, 0.0, 0.0)
        self.assertTrue(attacker._can_model_shoot_weapon_at_target(attacker.models[0], profile, target, game.map))

        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        limit_after, sources_after = target.get_ranged_targeting_restriction(game_map=game.map)
        self.assertNotEqual(float(limit_after or 0.0), 18.0)
        self.assertFalse(any("DEADLY DECEIVERS" in str(source).upper() for source in list(sources_after or [])))

    def test_double_cross_queues_and_redirects_damage_to_support_unit(self):
        game, p1, p2, drukhari_army, enemy_army = _build_game()
        protected = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "KABAL", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        support = _make_unit(
            "Wracks",
            keywords=["INFANTRY", "HAEMONCULUS COVENS", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
            wounds=3,
        )
        attacker = _make_unit(
            "Enemy Fighters",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(protected)
        drukhari_army.add_unit(support)
        enemy_army.add_unit(attacker)
        _place_unit(game, protected, 10.0, 10.0)
        _place_unit(game, support, 20.0, 10.0)
        _place_unit(game, attacker, 30.0, 10.0)
        game.rebuild_entity_registry()

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("fight_targets_selected", attacking_unit=attacker, target_units=[protected])
        pending = _pending_by_name(p1.stratagems, "DOUBLE-CROSS")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            "DOUBLE-CROSS",
            unit=protected,
            support_unit=support,
            attacking_unit=attacker,
            phase_name="Fight phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        attacker.models[0].set_location(20.0, 10.0, 0.0, 0.0)
        support_before = int(support.models[0].wounds or 0)
        protected_before = int(protected.models[0].wounds or 0)
        redirect_result = protected._apply_drukhari_kabalite_double_cross_redirect(
            attacker_model=attacker.models[0],
            attacker_unit=attacker,
            weapon_profile=_melee_profile(damage="2"),
            attack_instance={},
            game_map=game.map,
        )
        self.assertIsNotNone(redirect_result)
        self.assertEqual(int(redirect_result.get("damage", 0) or 0), 2)
        self.assertEqual(int(protected.models[0].wounds or 0), protected_before)
        self.assertEqual(int(support.models[0].wounds or 0), support_before - 2)

        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertIsNone(
            protected._apply_drukhari_kabalite_double_cross_redirect(
                attacker_model=attacker.models[0],
                attacker_unit=attacker,
                weapon_profile=_melee_profile(damage="2"),
                attack_instance={},
                game_map=game.map,
            )
        )

    def test_enemies_without_number_queues_reselect_request_and_applies_new_contract(self):
        game, p1, _p2, drukhari_army, enemy_army = _build_game()
        archon = _make_unit(
            "Archon",
            keywords=["INFANTRY", "CHARACTER", "ARCHON", "KABAL", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        old_target = _make_unit(
            "Enemy Captain",
            faction_name="Enemy",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        new_target = _make_unit(
            "Enemy Tank",
            faction_name="Enemy",
            keywords=["VEHICLE"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(archon)
        enemy_army.add_unit(old_target)
        enemy_army.add_unit(new_target)
        drukhari_army.warlord = archon
        archon.is_warlord = True
        _place_unit(game, archon, 10.0, 10.0)
        _place_unit(game, old_target, 18.0, 10.0)
        _place_unit(game, new_target, 22.0, 10.0)
        game.rebuild_entity_registry()

        mgr = drukhari_army.drukhari_detachments
        self.assertTrue(mgr.select_murderous_agenda("TROPHY_HUNTERS", old_target._id, game=game, player=p1))
        mgr.murderous_agenda_contract_completed = True
        mgr.murderous_agenda_reward_paid = True
        mgr.murderous_agenda_completion_turn = 1
        mgr.murderous_agenda_completion_phase = "COMMAND_PHASE"

        _set_phase(game, p1, "COMMAND_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "ENEMIES WITHOUT NUMBER")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("ENEMIES WITHOUT NUMBER", unit=archon, phase_name="Command phase", dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        request = _find_request(game, DECISION_CHOOSE_MURDEROUS_AGENDA)
        self.assertIsNotNone(request)
        context = dict(getattr(request, "context", {}) or {})
        self.assertTrue(bool(context.get("allow_reselect")))
        self.assertEqual(str(context.get("ability_name", "") or ""), "ENEMIES WITHOUT NUMBER")

        option = next(
            opt
            for opt in list(request.options or [])
            if str((getattr(opt, "payload", {}) or {}).get("contract_key", "") or "") == "SHOW_OF_STRENGTH"
            and str((getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "") == str(new_target._id)
        )
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=p1.id,
            option_id=option.option_id,
            payload={},
        )
        apply_result = dispatch_decision(game, request, result)
        self.assertTrue(bool(getattr(apply_result, "ok", False)))
        self.assertEqual(str(mgr.murderous_agenda_contract_key or ""), "SHOW_OF_STRENGTH")
        self.assertEqual(str(mgr.murderous_agenda_contract_target_unit_id or ""), str(new_target._id))
        self.assertFalse(bool(mgr.murderous_agenda_contract_completed))


if __name__ == "__main__":
    unittest.main()
