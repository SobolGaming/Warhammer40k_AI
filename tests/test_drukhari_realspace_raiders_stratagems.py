import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
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
    drukhari_army = Army("Drukhari", "Realspace Raiders")
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


def _move_request_for_kind(game: Game, kind: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_MOVE_UNIT:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("reactive_move_kind", "") or "").strip() != str(kind):
            continue
        return request
    return None


def _ranged_profile(*, name: str = "Splinter Rifle", skill: str = "4+", ap: str = "0", damage: str = "1"):
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


class TestDrukhariRealspaceRaidersStratagems(unittest.TestCase):
    def test_all_realspace_raiders_descriptors_registered(self):
        expected = {
            "000010575003": ("Fighting Shadows", "hit_roll_penalty"),
            "000010575004": ("Instinctive Spite", "hit_bonus_vs_targets_below_half_strength_with_optional_wound_bonus"),
            "000010575005": ("Dark Harvest", "grant_keywords_to_melee_weapons"),
            "000010575006": ("Eager for the Kill", "advance_no_roll_fixed_distance"),
            "000010575007": ("Raid and Fade", "post_shoot_reactive_normal_move_no_charge"),
        }

        for stratagem_id, (name, effect) in expected.items():
            with self.subTest(stratagem_id=stratagem_id):
                desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
                self.assertIsNotNone(desc)
                self.assertEqual(str(getattr(desc, "name", "") or ""), name)
                self.assertEqual(str(getattr(desc, "effect", "") or ""), effect)

    def test_instinctive_spite_grants_hit_and_optional_wound_bonus_vs_below_half_strength(self):
        game, p1, _p2, drukhari_army, enemy_army = _build_game()
        kabalites = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "KABAL", "BATTLELINE", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        enemy.is_below_half_strength = lambda: True
        drukhari_army.add_unit(kabalites)
        enemy_army.add_unit(enemy)
        _place_unit(game, kabalites, 10.0, 10.0)
        _place_unit(game, enemy, 18.0, 10.0)
        game.rebuild_entity_registry()

        drukhari_army.power_from_pain.tokens = 2
        profile = _ranged_profile(skill="4+")
        _set_phase(game, p1, "SHOOTING_PHASE", 0)

        before_hit = profile._hit_target_with_tracking(
            enemy,
            kabalites.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        before_wound = profile._wound_target_with_tracking(
            enemy,
            kabalites.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(before_hit.get("hit", False)))
        self.assertFalse(bool(before_wound.get("wound", False)))

        ok = p1.stratagems.use(
            "INSTINCTIVE SPITE",
            unit=kabalites,
            phase_name="Shooting phase",
            spend_pain_token=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)
        self.assertEqual(int(drukhari_army.power_from_pain.tokens or 0), 1)

        during_hit = profile._hit_target_with_tracking(
            enemy,
            kabalites.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        during_wound = profile._wound_target_with_tracking(
            enemy,
            kabalites.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(during_hit.get("hit", False)))
        self.assertTrue(bool(during_wound.get("wound", False)))

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        after_hit = profile._hit_target_with_tracking(
            enemy,
            kabalites.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        after_wound = profile._wound_target_with_tracking(
            enemy,
            kabalites.models[0],
            {},
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(after_hit.get("hit", False)))
        self.assertFalse(bool(after_wound.get("wound", False)))

    def test_dark_harvest_grants_lethal_hits_to_melee_weapons_until_phase_end(self):
        game, p1, _p2, drukhari_army, enemy_army = _build_game()
        wracks = _make_unit(
            "Wracks",
            keywords=["INFANTRY", "WRACKS", "HAEMONCULUS COVENS", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(wracks)
        enemy_army.add_unit(enemy)
        _place_unit(game, wracks, 10.0, 10.0)
        _place_unit(game, enemy, 12.0, 10.0)
        game.rebuild_entity_registry()

        profile = _melee_profile(name="Wrack Blade")
        _set_phase(game, p1, "FIGHT_PHASE", 0)

        before = wracks.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=wracks.models[0],
            weapon_profile=profile,
            weapon_name="Wrack Blade",
            target=enemy,
        )
        self.assertFalse(bool(before.get("lethal_hits", False)))

        ok = p1.stratagems.use("DARK HARVEST", unit=wracks, phase_name="Fight phase")
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        during = wracks.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=wracks.models[0],
            weapon_profile=profile,
            weapon_name="Wrack Blade",
            target=enemy,
        )
        self.assertTrue(bool(during.get("lethal_hits", False)))

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        after = wracks.get_model_weapon_keyword_bonuses(
            attack_type="melee",
            model=wracks.models[0],
            weapon_profile=profile,
            weapon_name="Wrack Blade",
            target=enemy,
        )
        self.assertFalse(bool(after.get("lethal_hits", False)))

    def test_eager_for_the_kill_adds_fixed_advance_six_until_phase_end(self):
        game, p1, _p2, drukhari_army, _enemy_army = _build_game()
        wyches = _make_unit(
            "Wyches",
            keywords=["INFANTRY", "WYCHES", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(wyches)
        _place_unit(game, wyches, 10.0, 10.0)
        game.rebuild_entity_registry()

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        self.assertIsNone(wyches._get_advance_no_roll_effect())

        ok = p1.stratagems.use("EAGER FOR THE KILL", unit=wyches, phase_name="Movement phase")
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        effect = wyches._get_advance_no_roll_effect()
        self.assertIsNotNone(effect)
        self.assertEqual(int(effect.get("distance", 0) or 0), 6)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
        self.assertIsNone(wyches._get_advance_no_roll_effect())

    def test_fighting_shadows_queues_and_applies_hit_penalty_until_phase_end(self):
        game, p1, p2, drukhari_army, enemy_army = _build_game()
        wyches = _make_unit(
            "Wyches",
            keywords=["INFANTRY", "WYCHES", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        enemy = _make_unit(
            "Enemy Shooters",
            faction_name="Enemy",
            keywords=["INFANTRY"],
            faction_keywords=["ENEMY"],
        )
        drukhari_army.add_unit(wyches)
        enemy_army.add_unit(enemy)
        _place_unit(game, wyches, 10.0, 10.0)
        _place_unit(game, enemy, 18.0, 10.0)
        game.rebuild_entity_registry()

        profile = _ranged_profile(skill="4+")
        _set_phase(game, p2, "SHOOTING_PHASE", 1)
        game.event_system.publish("shooting_targets_selected", attacking_unit=enemy, target_units=[wyches])
        pending = _pending_by_name(p1.stratagems, "FIGHTING SHADOWS")
        self.assertIsNotNone(pending)

        before = profile._hit_target_with_tracking(
            wyches,
            enemy.models[0],
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(before.get("hit", False)))

        ok = p1.stratagems.use(
            "FIGHTING SHADOWS",
            unit=wyches,
            attacking_unit=enemy,
            phase_name="Shooting phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 9)

        during = profile._hit_target_with_tracking(
            wyches,
            enemy.models[0],
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(bool(during.get("hit", False)))

        game.event_system.publish("phase_end", player=p2, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        after = profile._hit_target_with_tracking(
            wyches,
            enemy.models[0],
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(bool(after.get("hit", False)))

    def test_raid_and_fade_queues_post_shoot_reactive_move(self):
        game, p1, _p2, drukhari_army, _enemy_army = _build_game()
        kabalites = _make_unit(
            "Kabalite Warriors",
            keywords=["INFANTRY", "KABAL", "BATTLELINE", "DRUKHARI"],
            faction_keywords=["DRUKHARI"],
        )
        drukhari_army.add_unit(kabalites)
        _place_unit(game, kabalites, 10.0, 10.0)
        game.rebuild_entity_registry()

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        pending = _pending_by_name(p1.stratagems, "RAID AND FADE")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use(
            "RAID AND FADE",
            unit=kabalites,
            phase_name="Shooting phase",
            dequeue=True,
        )
        self.assertTrue(ok)
        self.assertEqual(int(p1.command_points or 0), 8)

        request = _move_request_for_kind(game, "post_shoot_no_charge")
        self.assertIsNotNone(request)
        context = dict(getattr(request, "context", {}) or {})
        self.assertEqual(int(context.get("max_distance", 0) or 0), 6)
        self.assertEqual(str(context.get("movement_type", "") or ""), "reactive")
        self.assertEqual(str(context.get("reactive_move_kind", "") or ""), "post_shoot_no_charge")
        self.assertTrue(bool(context.get("allow_skip", False)))


if __name__ == "__main__":
    unittest.main()
