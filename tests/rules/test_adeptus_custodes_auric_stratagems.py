from __future__ import annotations

import unittest
from types import SimpleNamespace

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
        datasheet_id: str = "",
        keywords=None,
        faction_keywords=None,
        attached_to=None,
        attached_to_names=None,
    ):
        self.id = str(datasheet_id or name.lower().replace(" ", "_"))
        self.name = name
        self.faction_data = {
            "name": "Adeptus Custodes"
            if "ADEPTUS CUSTODES" in [str(keyword or "").upper() for keyword in list(keywords or [])]
            else "Enemy"
        }
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "2",
                "W": "4",
                "Ld": "6",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "4",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = list(attached_to or [])
        self.attached_to_names = list(attached_to_names or [])


def _make_unit(
    name: str,
    *,
    datasheet_id: str = "",
    keywords=None,
    faction_keywords=None,
    attached_to=None,
    attached_to_names=None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to=attached_to,
            attached_to_names=attached_to_names,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    army1 = Army.with_detachment("Adeptus Custodes", "Auric Champions")
    army1.faction_id = "AC"
    army2 = Army.with_detachment("Enemy", "Other")
    army2.faction_id = "EN"

    p1 = Player("Custodes", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=army2)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 10
    p2.command_points = 10
    army1.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, p1, p2, army1, army2


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
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name_substring: str):
    wanted = str(name_substring or "").strip().upper().replace("\u2019", "'")
    for reaction in list(stratagems.get_pending_reactions() or []):
        current = str(reaction.get("stratagem", "") or "").strip().upper().replace("\u2019", "'")
        if wanted in current:
            return reaction
    return None


def _melee_profile(*, strength: int = 6, ap: int = 1, damage: int = 2, name: str = "Enemy Blade"):
    weapon = Wargear(
        {
            "name": name,
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": str(int(ap)),
            "D": str(int(damage)),
            "description": "",
        }
    )
    return weapon.profiles["default"]


class TestAdeptusCustodesAuricStratagems(unittest.TestCase):
    def test_auric_champions_descriptors_resolve_by_id_and_name(self):
        expected = {
            "000008931002": "SLAYER OF CHAMPIONS",
            "000008931003": "SUPERHUMAN RESERVES",
            "000008931004": "THE EMPEROR'S AUSPICE",
            "000008931005": "EARNING OF A NAME",
            "000008931006": "VIGIL UNENDING",
            "000008931007": "SHOULDER THE MANTLE",
        }
        for stratagem_id, name in expected.items():
            desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
            self.assertIsNotNone(desc)
            self.assertEqual(str(getattr(desc, "name", "") or ""), name)
            by_name = get_stratagem_tool_descriptor(name=name)
            self.assertIsNotNone(by_name)
            self.assertEqual(str(getattr(by_name, "stratagem_id", "") or ""), stratagem_id)

    def test_earning_of_a_name_grants_full_melee_rerolls_vs_monster_or_vehicle(self):
        game, p1, _p2, army1, army2 = _build_game()
        unit = _make_unit(
            "Shield-Captain",
            keywords=["ADEPTUS CUSTODES", "CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS CUSTODES"],
        )
        monster = _make_unit(
            "Carnifex",
            keywords=["MONSTER"],
            faction_keywords=["ENEMY"],
        )
        infantry = _make_unit(
            "Enemy Infantry",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army1.add_unit(unit)
        army2.add_unit(monster)
        army2.add_unit(infantry)
        unit.deployed = True
        unit.reserve_status = "deployed"

        game.phase = SimpleNamespace(name="FIGHT_PHASE")
        game.current_player_index = 0

        ok = p1.stratagems.use(
            "EARNING OF A NAME",
            unit=unit,
            target_units=[unit],
            phase_name="Fight phase",
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        hit_mods = unit.get_model_hit_reroll_modifiers(unit.models[0], attack_type="melee", target=monster)
        wound_mods = unit.get_model_wound_reroll_modifiers(unit.models[0], attack_type="melee", target=monster)
        self.assertTrue(bool(hit_mods.get("reroll_hit_full")))
        self.assertTrue(bool(wound_mods.get("reroll_wound_full")))
        self.assertTrue(any("EARNING OF A NAME" in reason.upper() for reason in hit_mods.get("reroll_hit_full_reasons", ())))
        self.assertTrue(
            any("EARNING OF A NAME" in reason.upper() for reason in wound_mods.get("reroll_wound_full_reasons", ()))
        )

        hit_vs_infantry = unit.get_model_hit_reroll_modifiers(unit.models[0], attack_type="melee", target=infantry)
        wound_vs_infantry = unit.get_model_wound_reroll_modifiers(unit.models[0], attack_type="melee", target=infantry)
        self.assertFalse(bool(hit_vs_infantry.get("reroll_hit_full")))
        self.assertFalse(bool(wound_vs_infantry.get("reroll_wound_full")))

    def test_shoulder_the_mantle_attaches_leader_to_nearby_bodyguard(self):
        game, p1, _p2, army1, _army2 = _build_game()
        bodyguard = _make_unit(
            "Custodian Guard",
            datasheet_id="custodian_guard",
            keywords=["ADEPTUS CUSTODES", "INFANTRY"],
            faction_keywords=["ADEPTUS CUSTODES"],
        )
        leader = _make_unit(
            "Shield-Captain",
            datasheet_id="shield_captain",
            keywords=["ADEPTUS CUSTODES", "CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS CUSTODES"],
            attached_to=["custodian_guard"],
            attached_to_names=["Custodian Guard"],
        )
        army1.add_unit(bodyguard)
        army1.add_unit(leader)
        _place_unit(game, bodyguard, 10.0, 10.0)
        leader.deployed = True
        leader.reserve_status = "deployed"
        leader.models[0].set_location(13.0, 10.0, 0.0, 0.0)

        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        game.current_player_index = 0

        ok = p1.stratagems.use(
            "SHOULDER THE MANTLE",
            unit=leader,
            bodyguard_unit=bodyguard,
            phase_name="Movement phase",
        )
        self.assertTrue(ok)
        self.assertEqual(leader.attached_to, bodyguard)
        self.assertIn(leader, list(getattr(bodyguard, "attached_leaders", []) or []))
        self.assertEqual(int(p1.command_points or 0), 9)

    def test_slayer_of_champions_marks_new_target_and_refunds_cp_after_character_kill(self):
        game, p1, _p2, army1, army2 = _build_game()
        attacker = _make_unit(
            "Blade Champion",
            keywords=["ADEPTUS CUSTODES", "CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS CUSTODES"],
        )
        assemblage_target = _make_unit(
            "Enemy Hero",
            keywords=["CHARACTER", "INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        new_target = _make_unit(
            "Enemy Monster",
            keywords=["MONSTER"],
            faction_keywords=["ENEMY"],
        )
        other_target = _make_unit(
            "Enemy Infantry",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army1.add_unit(attacker)
        army2.add_unit(assemblage_target)
        army2.add_unit(new_target)
        army2.add_unit(other_target)
        _place_unit(game, attacker, 10.0, 10.0)
        _place_unit(game, assemblage_target, 14.0, 10.0)
        _place_unit(game, new_target, 18.0, 10.0)
        _place_unit(game, other_target, 22.0, 10.0)

        mgr = army1.adeptus_custodes_detachments
        self.assertTrue(mgr.set_assemblage_of_might_target(assemblage_target))

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        game.event_system.publish("unit_destroyed", unit=assemblage_target, destroyed_by_unit=attacker)
        pending = _pending_by_name(p1.stratagems, "SLAYER OF CHAMPIONS")
        self.assertIsNotNone(pending)

        start_cp = int(p1.command_points or 0)
        ok = p1.stratagems.use(
            "SLAYER OF CHAMPIONS",
            unit=attacker,
            enemy_unit=new_target,
            phase_name="Shooting phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), start_cp)
        self.assertEqual(int(mgr.slayer_of_champions_wound_bonus(attacker.models[0], new_target) or 0), 1)
        self.assertEqual(int(mgr.slayer_of_champions_wound_bonus(attacker.models[0], other_target) or 0), 0)

    def test_superhuman_reserves_grants_one_later_extra_use_and_does_not_requeue_same_pair(self):
        game, p1, _p2, army1, _army2 = _build_game()
        warlord = _make_unit(
            "Trajann Valoris",
            keywords=["ADEPTUS CUSTODES", "CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS CUSTODES"],
        )
        army1.add_unit(warlord)
        warlord.deployed = True
        warlord.reserve_status = "deployed"
        warlord.is_warlord = True
        army1.warlord = warlord

        game.phase = SimpleNamespace(name="FIGHT_PHASE")
        game.current_player_index = 0

        model = warlord.models[0]
        self.assertTrue(model.mark_used_once_per_battle("test_once", ability_name="Test Once", source="datasheet"))
        pending = _pending_by_name(p1.stratagems, "SUPERHUMAN RESERVES")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            "SUPERHUMAN RESERVES",
            unit=warlord,
            model=model,
            ability_key="test_once",
            phase_name="Fight phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 8)
        self.assertTrue(model.has_used_once_per_battle("test_once", phase_name="FIGHT_PHASE"))

        game.phase = SimpleNamespace(name="SHOOTING_PHASE")
        self.assertEqual(int(model.remaining_once_per_battle_uses("test_once", phase_name="SHOOTING_PHASE") or 0), 1)
        self.assertTrue(model.mark_used_once_per_battle("test_once", ability_name="Test Once", source="datasheet"))
        self.assertIsNone(_pending_by_name(p1.stratagems, "SUPERHUMAN RESERVES"))

    def test_the_emperors_auspice_only_grants_fnp_to_character_models_in_targeted_unit(self):
        game, p1, p2, army1, army2 = _build_game()
        bodyguard = _make_unit(
            "Custodian Guard",
            datasheet_id="custodian_guard",
            keywords=["ADEPTUS CUSTODES", "INFANTRY"],
            faction_keywords=["ADEPTUS CUSTODES"],
        )
        leader = _make_unit(
            "Shield-Captain",
            datasheet_id="shield_captain",
            keywords=["ADEPTUS CUSTODES", "CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS CUSTODES"],
            attached_to=["custodian_guard"],
            attached_to_names=["Custodian Guard"],
        )
        enemy = _make_unit(
            "Enemy Shooters",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army1.add_unit(bodyguard)
        army1.add_unit(leader)
        army2.add_unit(enemy)
        _place_unit(game, bodyguard, 10.0, 10.0)
        _place_unit(game, enemy, 18.0, 10.0)
        leader.deployed = True
        leader.reserve_status = "deployed"
        leader.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        leader.attach_to_unit(bodyguard)

        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[bodyguard])
        pending = _pending_by_name(p1.stratagems, "THE EMPEROR'S AUSPICE")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            "THE EMPEROR'S AUSPICE",
            unit=bodyguard,
            phase_name="Shooting phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        self.assertIn((4, None), list(leader.models[0].get_temporary_fnp_entries() or []))
        self.assertEqual(list(bodyguard.models[0].get_temporary_fnp_entries() or []), [])

    def test_vigil_unending_queues_and_grants_automatic_fight_on_death(self):
        game, p1, p2, army1, army2 = _build_game()
        unit = _make_unit(
            "Blade Champion",
            keywords=["ADEPTUS CUSTODES", "CHARACTER", "INFANTRY"],
            faction_keywords=["ADEPTUS CUSTODES"],
        )
        enemy = _make_unit(
            "Enemy Fighters",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        army1.add_unit(unit)
        army2.add_unit(enemy)
        _place_unit(game, unit, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)

        model = unit.models[0]
        unit.round_state.fought_this_phase = False

        _set_phase(game, p2, "FIGHT_PHASE", 1)
        game.event_system.publish("model_destroyed_before_removal", unit=unit, model=model)
        pending = _pending_by_name(p1.stratagems, "VIGIL UNENDING")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            "VIGIL UNENDING",
            unit=unit,
            model=model,
            phase_name="Fight phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 8)

        rule = unit.get_melee_fight_on_death_after_attacks_rule(model=model)
        self.assertIsNotNone(rule)
        self.assertTrue(bool(rule.get("automatic")))

        unit._last_destroyed_by_weapon_profile = _melee_profile()
        model._wounds = 0
        unit._handle_model_destroyed(model, game.map)
        pending_models = list(getattr(unit, "_melee_fight_on_death_pending_models", []) or [])
        self.assertIn(model, pending_models)


if __name__ == "__main__":
    unittest.main()
