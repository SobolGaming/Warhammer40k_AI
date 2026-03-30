from __future__ import annotations

from types import SimpleNamespace
import unittest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        faction_keywords=None,
        keywords=None,
        model_count: int = 1,
        wounds: str = "4",
        toughness: str = "5",
        movement: str = "6",
        base_size: str = "32mm",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_').replace('-', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(movement),
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "1",
                "base_size": base_size,
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


class _DummyRangedWeapon:
    def __init__(self, name: str):
        self.name = name

    def is_ranged(self) -> bool:
        return True


def _make_unit(
    name: str,
    *,
    faction_name: str = "Leagues of Votann",
    faction_keywords=None,
    keywords=None,
    model_count: int = 1,
    wounds: str = "4",
    toughness: str = "5",
    movement: str = "6",
    base_size: str = "32mm",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            faction_keywords=faction_keywords or ["LEAGUES OF VOTANN"],
            keywords=keywords,
            model_count=model_count,
            wounds=wounds,
            toughness=toughness,
            movement=movement,
            base_size=base_size,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    lov_army = Army("Leagues of Votann", "Hearthband")
    lov_army.faction_id = "LOV"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    p1 = Player("Votann", control=PlayerControl.LOCAL, army=lov_army)
    p2 = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)

    p1.command_points = 12
    p2.command_points = 12
    lov_army.configure_rule_managers(force=True)
    p1.stratagems.refresh_available()
    _inject_hearthband_stratagems(p1)
    p1.stratagems.enable_event_subscriptions()
    return game, p1, p2, lov_army, enemy_army


def _inject_hearthband_stratagems(player: Player) -> None:
    existing = {
        _norm_name(getattr(s, "name", "") or ""): s
        for s in list(getattr(player.stratagems, "available", []) or [])
    }
    specs = (
        ("000009824007", "FURY OF THE HEARTH", 1, "Your turn", "Shooting phase", "Hearthband - Battle Tactic Stratagem"),
        ("000009824006", "MATERIALISATION MATRICES", 1, "Your turn", "Movement phase", "Hearthband - Strategic Ploy Stratagem"),
        ("000009824004", "SUPERIOR CRAFTSMANSHIP", 2, "Either player's turn", "Fight phase", "Hearthband - Battle Tactic Stratagem"),
        ("000009824003", "SURE OF PURPOSE", 1, "Either player's turn", "Fight phase", "Hearthband - Strategic Ploy Stratagem"),
        ("000009824005", "UNYIELDING AGGRESSION", 1, "Your turn", "Movement phase", "Hearthband - Strategic Ploy Stratagem"),
    )
    for sid, name, cp, turn, phase, stype in specs:
        if _norm_name(name) in existing:
            continue
        player.stratagems.available.append(
            Stratagem(
                id=sid,
                name=name,
                type=stype,
                description="",
                cp_cost=int(cp),
                turn=turn,
                phase=phase,
                detachment="Hearthband",
                faction_id="LOV",
            )
        )


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _norm_name(name: str) -> str:
    text = str(name or "").strip().upper()
    return (
        text.replace("\u2010", "-")
        .replace("\u2011", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2019", "'")
    )


def _pending_by_name(stratagems, name_substring: str):
    wanted = _norm_name(name_substring)
    for reaction in list(stratagems.get_pending_reactions() or []):
        if wanted in _norm_name(reaction.get("stratagem", "")):
            return reaction
    return None


def _attach_ranged_weapons(unit: Unit, *, weapon_name: str) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.wargear = [_DummyRangedWeapon(weapon_name)]


def _ranged_profile():
    weapon = Wargear(
        {
            "name": "Test Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


class TestHearthbandStratagems(unittest.TestCase):
    def test_hearthband_stratagem_descriptors_registered(self):
        expected = {
            "000009824007": ("Fury of the Hearth", "ranged_strength_bonus_with_optional_sustained_hits"),
            "000009824006": ("Materialisation Matrices", "deep_strike_min_distance_override"),
            "000009824004": ("Superior Craftsmanship", "melee_damage_bonus_against_monsters_and_vehicles"),
            "000009824003": ("Sure of Purpose", "extend_pile_in_and_consolidate_to_six"),
            "000009824005": ("Unyielding Aggression", "eligible_to_shoot_and_charge_after_fall_back"),
        }
        for stratagem_id, (expected_name, expected_effect) in expected.items():
            by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
            by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
            self.assertIsNotNone(by_id)
            self.assertIsNotNone(by_name)
            self.assertEqual(str(by_id.name or ""), expected_name)
            self.assertEqual(str(by_name.name or ""), expected_name)
            self.assertEqual(str(by_id.effect or ""), expected_effect)

    def test_fury_of_the_hearth_grants_strength_and_optional_sustained_hits_until_phase_end(self):
        game, p1, _p2, lov_army, _enemy_army = _build_game()
        hearthguard = _make_unit(
            "Einhyr Hearthguard",
            keywords=["INFANTRY", "EINHYR HEARTHGUARD"],
            model_count=2,
        )
        _attach_ranged_weapons(hearthguard, weapon_name="EtaCarn Plasma Gun")
        lov_army.add_unit(hearthguard)
        _place_unit(game, hearthguard, 10.0, 10.0)
        lov_army.prioritised_efficiency.add_yield_points(1, game=game)

        _set_phase(game, p1, "SHOOTING_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "FURY OF THE HEARTH")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("FURY OF THE HEARTH", unit=hearthguard, spend_yield_points=True, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(lov_army.prioritised_efficiency.yield_points or 0), 0)
        for model in list(hearthguard.models or []):
            self.assertEqual(model.get_temporary_weapon_strength_bonus("EtaCarn Plasma Gun")[0], 1)
        self.assertEqual(int(hearthguard.special_rules.get("bearer_unit_sustained_hits_value_ranged", 0) or 0), 1)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="SHOOTING_PHASE"))
        for model in list(hearthguard.models or []):
            model.on_phase_end(SimpleNamespace(name="SHOOTING_PHASE"))
            self.assertEqual(model.get_temporary_weapon_strength_bonus("EtaCarn Plasma Gun")[0], 0)
        self.assertNotIn("hearthband_fury_of_the_hearth_active", dict(hearthguard.special_rules or {}))
        self.assertNotIn("bearer_unit_sustained_hits_value_ranged", dict(hearthguard.special_rules or {}))

    def test_materialisation_matrices_sets_deep_strike_override_until_movement_phase_end(self):
        game, p1, _p2, lov_army, _enemy_army = _build_game()
        reserve_unit = _make_unit(
            "Hearthguard Reserves",
            keywords=["INFANTRY", "DEEP STRIKE"],
        )
        reserve_unit.deployed = False
        reserve_unit.reserve_status = "reserves"
        lov_army.add_unit(reserve_unit)

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "MATERIALISATION MATRICES")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("MATERIALISATION MATRICES", unit=reserve_unit, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(float(reserve_unit.get_deep_strike_min_distance_override() or 0.0), 6.0)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
        self.assertIsNone(reserve_unit.get_deep_strike_min_distance_override())

    def test_superior_craftsmanship_grants_melee_damage_bonus_only_into_monsters_and_vehicles(self):
        game, p1, _p2, lov_army, enemy_army = _build_game()
        fighters = _make_unit("Hearthkyn Warriors", keywords=["INFANTRY"])
        monster = _make_unit(
            "Enemy Monster",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["MONSTER"],
        )
        infantry = _make_unit(
            "Enemy Infantry",
            faction_name="Enemy",
            faction_keywords=["ENEMY"],
            keywords=["INFANTRY"],
        )
        lov_army.add_unit(fighters)
        enemy_army.add_unit(monster)
        enemy_army.add_unit(infantry)
        _place_unit(game, fighters, 10.0, 10.0)

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "SUPERIOR CRAFTSMANSHIP")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("SUPERIOR CRAFTSMANSHIP", unit=fighters, dequeue=True)
        self.assertTrue(ok)
        self.assertEqual(int(fighters.get_melee_damage_bonus_for_target(monster) or 0), 1)
        self.assertEqual(int(fighters.get_melee_damage_bonus_for_target(infantry) or 0), 0)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertEqual(int(fighters.get_melee_damage_bonus_for_target(monster) or 0), 0)

    def test_sure_of_purpose_sets_pile_in_and_consolidate_overrides_until_phase_end(self):
        game, p1, _p2, lov_army, _enemy_army = _build_game()
        fighters = _make_unit("Einhyr Champion Escort", keywords=["INFANTRY"])
        lov_army.add_unit(fighters)
        _place_unit(game, fighters, 12.0, 12.0)

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        pending = _pending_by_name(p1.stratagems, "SURE OF PURPOSE")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("SURE OF PURPOSE", unit=fighters, dequeue=True)
        self.assertTrue(ok)
        pile_in_rules = get_validation_rules(MovementType.PILE_IN, moving_unit=fighters)
        consolidate_rules = get_validation_rules(MovementType.CONSOLIDATE, moving_unit=fighters)
        self.assertEqual(float(pile_in_rules.get("max_distance_override", 0.0) or 0.0), 6.0)
        self.assertEqual(float(consolidate_rules.get("max_distance_override", 0.0) or 0.0), 6.0)

        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        pile_in_after = get_validation_rules(MovementType.PILE_IN, moving_unit=fighters)
        consolidate_after = get_validation_rules(MovementType.CONSOLIDATE, moving_unit=fighters)
        self.assertEqual(float(pile_in_after.get("max_distance_override", 0.0) or 0.0), 3.0)
        self.assertEqual(float(consolidate_after.get("max_distance_override", 0.0) or 0.0), 3.0)

    def test_unyielding_aggression_queues_after_fall_back_and_grants_shoot_and_charge(self):
        game, p1, _p2, lov_army, _enemy_army = _build_game()
        infantry = _make_unit("Hearthkyn Warriors", keywords=["INFANTRY"])
        lov_army.add_unit(infantry)
        _place_unit(game, infantry, 14.0, 14.0)
        infantry.round_state.fell_back_this_round = True
        profile = _ranged_profile()

        _set_phase(game, p1, "MOVEMENT_PHASE", 0)
        self.assertFalse(bool(infantry.can_shoot_after_fall_back(profile)))
        self.assertFalse(bool(infantry.can_charge_after_fall_back()))

        game.event_system.publish("unit_move_ended", unit=infantry, action="fall_back")
        pending = _pending_by_name(p1.stratagems, "UNYIELDING AGGRESSION")
        self.assertIsNotNone(pending)

        ok = p1.stratagems.use("UNYIELDING AGGRESSION", unit=infantry, action="fall_back", dequeue=True)
        self.assertTrue(ok)
        self.assertTrue(bool(infantry.can_shoot_after_fall_back(profile)))
        self.assertTrue(bool(infantry.can_charge_after_fall_back()))

        _set_phase(game, p1, "FIGHT_PHASE", 0)
        game.event_system.publish("phase_end", player=p1, phase=SimpleNamespace(name="FIGHT_PHASE"))
        self.assertNotIn("hearthband_unyielding_aggression_active", dict(infantry.special_rules or {}))


if __name__ == "__main__":
    unittest.main()
