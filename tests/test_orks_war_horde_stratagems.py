import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        keywords=None,
        faction_keywords=None,
        movement="5",
        toughness="5",
        wounds="4",
        abilities=None,
    ):
        self.name = name
        self.faction_data = {"name": "Orks" if "ORKS" in [k.upper() for k in list(faction_keywords or [])] else "Enemy"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": movement,
                "T": toughness,
                "Sv": "4",
                "W": wounds,
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        for ability in list(abilities or []):
            if isinstance(ability, dict):
                self.datasheets_abilities.append(ability)
            else:
                text = str(ability)
                self.datasheets_abilities.append(
                    {
                        "name": text,
                        "description": text,
                        "type": "",
                        "parameter": "",
                    }
                )
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, keywords=None, faction_keywords=None, toughness="5", abilities=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
        abilities=abilities,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("Orks", "War Horde")
    army1.faction_id = "ORK"
    army2 = Army("Enemy", "Other")
    army2.faction_id = "EN"

    p1 = Player("Orks", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 5
    p2.command_points = 5
    army1.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, p1, p2, army1, army2


def _place_unit(game, unit, x, y):
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.models[0].set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


class _MeleeWargear:
    name = "Choppa"

    @staticmethod
    def is_melee():
        return True

    @staticmethod
    def is_ranged():
        return False


def _melee_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    return WargearProfile(
        "Choppa",
        {
            "range": "Melee",
            "A": "3",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=_MeleeWargear(),
    )


class TestOrksWarHordeStratagems(unittest.TestCase):
    def test_unbridled_carnage_sets_crit_hits_on_5_plus(self):
        game, p1, _p2, army1, army2 = _build_game()
        unit = _make_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)
        _place_unit(game, unit, 10.0, 10.0)
        _place_unit(game, enemy, 14.0, 10.0)

        unit.round_state.fought_this_phase = False
        game.phase = SimpleNamespace(name="FIGHT_PHASE")

        ok = p1.stratagems.use("UNBRIDLED CARNAGE", unit=unit, phase_name="Fight phase")
        self.assertTrue(ok)

        profile = _melee_profile()
        attack_instance = {"_aura_attack_mods": _aura_stub()}
        profile._hit_target_with_tracking(
            enemy,
            unit.models[0],
            attack_instance,
            roll_value=5,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(attack_instance.get("crit_hit"))

    def test_ard_as_nails_applies_wound_penalty(self):
        from warhammer40k_ai.units.wargear import Wargear

        game, p1, p2, army1, army2 = _build_game()
        unit = _make_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"], toughness="5")
        enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)
        _place_unit(game, unit, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        game.phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.current_player_index = 1

        ok = p1.stratagems.use(
            "'ARD AS NAILS",
            unit=unit,
            attacker_unit=enemy,
            candidates=[unit],
            phase_name="Shooting phase",
        )
        self.assertTrue(ok)

        data = {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "6",
            "AP": "0",
            "D": "1",
            "description": "",
            "type": "Ranged",
            "name": "Test Gun",
        }
        profile = Wargear(data).profiles["default"]
        attack_instance = {
            "crit_hit": False,
            "crit_wound": False,
            "mortal_wound": False,
            "below_half_distance": False,
            "damage": 0,
            "target_toughness_override": None,
        }
        result = profile._wound_target_with_tracking(unit, enemy.models[0], dict(attack_instance))
        self.assertTrue(any("ARD AS NAILS" in str(m).upper() for m in result.get("modifiers", [])))

    def test_ard_as_nails_rejects_grots(self):
        game, p1, p2, army1, army2 = _build_game()
        grots = _make_unit("Gretchin", keywords=["INFANTRY", "GROTS"], faction_keywords=["ORKS"])
        enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(grots)
        army2.add_unit(enemy)
        _place_unit(game, grots, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        game.phase = SimpleNamespace(name="SHOOTING_PHASE")
        game.current_player_index = 1

        ok = p1.stratagems.use(
            "'ARD AS NAILS",
            unit=grots,
            attacker_unit=enemy,
            candidates=[grots],
            phase_name="Shooting phase",
        )
        self.assertFalse(ok)

    def test_ere_we_go_adds_advance_and_charge_bonus_until_end_of_turn(self):
        game, p1, _p2, army1, army2 = _build_game()
        unit = _make_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)
        _place_unit(game, unit, 10.0, 10.0)
        _place_unit(game, enemy, 16.0, 10.0)

        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.current_player_index = 0

        ok = p1.stratagems.use("ERE WE GO", unit=unit, phase_name="Movement phase")
        self.assertTrue(ok)

        advance_mods = unit._collect_advance_roll_modifiers()
        self.assertTrue(any(val == 2 and "ERE WE GO" in str(source).upper() for val, source in advance_mods))

        charge_mods = game.get_charge_roll_modifiers(unit, target_unit=enemy)
        self.assertTrue(any(val == 2 and "ERE WE GO" in str(source).upper() for val, source in charge_mods))

        game._on_phase_end_cleanup(player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))

        advance_mods_after = unit._collect_advance_roll_modifiers()
        self.assertFalse(any(val == 2 and "ERE WE GO" in str(source).upper() for val, source in advance_mods_after))

        charge_mods_after = game.get_charge_roll_modifiers(unit, target_unit=enemy)
        self.assertFalse(any(val == 2 and "ERE WE GO" in str(source).upper() for val, source in charge_mods_after))

    def test_orks_is_never_beaten_defers_fight_on_death(self):
        game, p1, p2, army1, army2 = _build_game()
        unit = _make_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
        enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
        army1.add_unit(unit)
        army2.add_unit(enemy)
        _place_unit(game, unit, 10.0, 10.0)
        _place_unit(game, enemy, 14.0, 10.0)

        unit.round_state.fought_this_phase = False
        game.phase = SimpleNamespace(name="FIGHT_PHASE")
        game.current_player_index = 1

        ok = p1.stratagems.use(
            "ORKS IS NEVER BEATEN",
            unit=unit,
            attacking_unit=enemy,
            candidates=[unit],
            phase_name="Fight phase",
        )
        self.assertTrue(ok)
        self.assertTrue(unit.special_rules.get("orks_is_never_beaten_active"))

        model = unit.models[0]
        model._wounds = 0
        unit._handle_model_destroyed(model, game.map)
        pending = getattr(unit, "_orks_is_never_beaten_pending_models", [])
        self.assertIn(model, pending)

        with patch.object(unit, "_try_fight_on_death") as mocked:
            unit.end_attack_resolution(game_map=game.map)
        self.assertEqual(mocked.call_count, 1)
        self.assertFalse(getattr(unit, "_orks_is_never_beaten_pending_models", []))

    def test_mob_rule_clears_battle_shock(self):
        from warhammer40k_ai.units.status_effects import BattleShockEffect

        game, p1, _p2, army1, _army2 = _build_game()
        mob_unit = _make_unit("Boyz Mob", keywords=["INFANTRY", "MOB"], faction_keywords=["ORKS"])
        mob_unit.unit_composition = {"Test Model": (10, 10)}
        mob_unit.unit_composition_options = [mob_unit.unit_composition]
        mob_unit.models = mob_unit._create_models(mob_unit._datasheet, quantity=10)
        bs_unit = _make_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
        army1.add_unit(mob_unit)
        army1.add_unit(bs_unit)
        mob_unit.deployed = True
        mob_unit.reserve_status = "deployed"
        for idx, model in enumerate(mob_unit.models):
            model.set_location(10.0 + (idx * 0.5), 10.0, 0.0, 0.0)
        if mob_unit not in game.map.units:
            game.map.units.append(mob_unit)
        bs_unit.deployed = True
        bs_unit.reserve_status = "deployed"
        bs_unit.models[0].set_location(12.0, 10.0, 0.0, 0.0)
        if bs_unit not in game.map.units:
            game.map.units.append(bs_unit)

        bs_unit.apply_status_effect(BattleShockEffect(current_turn=1))
        self.assertTrue(bs_unit.is_battle_shocked())

        game.phase = SimpleNamespace(name="COMMAND_PHASE")
        game.current_player_index = 0

        ok = p1.stratagems.use(
            "MOB RULE",
            mob_unit=mob_unit,
            battle_shocked_unit=bs_unit,
            phase_name="Command phase",
            event="phase_end",
        )
        self.assertTrue(ok)
        self.assertFalse(bs_unit.is_battle_shocked())

    def test_mob_rule_requires_end_of_command_phase_context(self):
        from warhammer40k_ai.units.status_effects import BattleShockEffect

        game, p1, _p2, army1, _army2 = _build_game()
        mob_unit = _make_unit("Boyz Mob", keywords=["INFANTRY", "MOB"], faction_keywords=["ORKS"])
        mob_unit.unit_composition = {"Test Model": (10, 10)}
        mob_unit.unit_composition_options = [mob_unit.unit_composition]
        mob_unit.models = mob_unit._create_models(mob_unit._datasheet, quantity=10)
        bs_unit = _make_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
        army1.add_unit(mob_unit)
        army1.add_unit(bs_unit)
        mob_unit.deployed = True
        mob_unit.reserve_status = "deployed"
        for idx, model in enumerate(mob_unit.models):
            model.set_location(20.0 + (idx * 0.5), 10.0, 0.0, 0.0)
        if mob_unit not in game.map.units:
            game.map.units.append(mob_unit)
        bs_unit.deployed = True
        bs_unit.reserve_status = "deployed"
        bs_unit.models[0].set_location(22.0, 10.0, 0.0, 0.0)
        if bs_unit not in game.map.units:
            game.map.units.append(bs_unit)

        bs_unit.apply_status_effect(BattleShockEffect(current_turn=1))
        self.assertTrue(bs_unit.is_battle_shocked())

        game.phase = SimpleNamespace(name="COMMAND_PHASE")
        game.current_player_index = 0

        ok = p1.stratagems.use("MOB RULE", mob_unit=mob_unit, battle_shocked_unit=bs_unit, phase_name="Command phase")
        self.assertFalse(ok)
        self.assertTrue(bs_unit.is_battle_shocked())

    def test_mob_rule_is_queued_at_end_of_command_phase(self):
        from warhammer40k_ai.units.status_effects import BattleShockEffect

        game, p1, _p2, army1, _army2 = _build_game()
        mob_unit = _make_unit("Boyz Mob", keywords=["INFANTRY", "MOB"], faction_keywords=["ORKS"])
        mob_unit.unit_composition = {"Test Model": (10, 10)}
        mob_unit.unit_composition_options = [mob_unit.unit_composition]
        mob_unit.models = mob_unit._create_models(mob_unit._datasheet, quantity=10)
        bs_unit = _make_unit("Boyz", keywords=["INFANTRY"], faction_keywords=["ORKS"])
        army1.add_unit(mob_unit)
        army1.add_unit(bs_unit)
        mob_unit.deployed = True
        mob_unit.reserve_status = "deployed"
        for idx, model in enumerate(mob_unit.models):
            model.set_location(30.0 + (idx * 0.5), 10.0, 0.0, 0.0)
        if mob_unit not in game.map.units:
            game.map.units.append(mob_unit)
        bs_unit.deployed = True
        bs_unit.reserve_status = "deployed"
        bs_unit.models[0].set_location(32.0, 10.0, 0.0, 0.0)
        if bs_unit not in game.map.units:
            game.map.units.append(bs_unit)
        bs_unit.apply_status_effect(BattleShockEffect(current_turn=1))

        game.phase = SimpleNamespace(name="COMMAND_PHASE")
        game.current_player_index = 0
        p1.stratagems._current_phase_name = "Command phase"
        p1.stratagems._on_phase_end(player=p1, phase=game.phase)

        queued = [
            r for r in list(getattr(p1.stratagems, "_pending_reactions", []) or [])
            if str(r.get("event", "") or "") == "phase_end"
            and str(r.get("phase", "") or "") == "Command phase"
            and str(r.get("stratagem", "") or "").upper() == "MOB RULE"
        ]
        self.assertTrue(queued)

    def test_careen_queues_move_and_resolves_skip(self):
        from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT, DECISION_USE_CAREEN
        from warhammer40k_ai.engine.decisions import DecisionResult
        from warhammer40k_ai.roster.player import PlayerControl

        game, p1, _p2, army1, _army2 = _build_game()
        p1.control = PlayerControl.REMOTE

        deadly = {
            "name": "Deadly Demise",
            "description": "",
            "type": "Ability",
            "parameter": "D3",
        }
        vehicle = _make_unit(
            "Trukk",
            keywords=["VEHICLE"],
            faction_keywords=["ORKS"],
            abilities=[deadly],
        )
        army1.add_unit(vehicle)
        _place_unit(game, vehicle, 10.0, 10.0)
        game.rebuild_entity_registry()

        model = vehicle.models[0]
        with patch("warhammer40k_ai.units.unit.get_roll", return_value=6):
            model._wounds = 0
            model.die(game_map=game.map)

        careen_reqs = [r for r in game.decision_queue.list() if r.decision_type == DECISION_USE_CAREEN]
        self.assertTrue(careen_reqs)
        careen_req = careen_reqs[0]
        normal_opt = next(opt for opt in careen_req.options if opt.payload.get("choice") == "normal")
        game.resolve_decision(
            DecisionResult(
                decision_id=careen_req.decision_id,
                player_id=careen_req.player_id,
                option_id=normal_opt.option_id,
                payload={},
            )
        )

        move_reqs = [r for r in game.decision_queue.list() if r.decision_type == DECISION_MOVE_UNIT]
        self.assertTrue(move_reqs)
        move_req = move_reqs[0]
        self.assertEqual(move_req.context.get("reactive_move_kind"), "careen")
        skip_opt = next(opt for opt in move_req.options if opt.payload.get("action") == "skip")
        game.resolve_decision(
            DecisionResult(
                decision_id=move_req.decision_id,
                player_id=move_req.player_id,
                option_id=skip_opt.option_id,
                payload={"skipped": True},
            )
        )

        self.assertFalse(getattr(vehicle, "_careen_pending_destroyed", False))
        self.assertFalse(vehicle.is_alive())


if __name__ == "__main__":
    unittest.main()
