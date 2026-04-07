from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.fight_phase_manager import FightPhaseManager
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
        move: int = 12,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(int(move)),
                "T": "4",
                "Sv": "3",
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


class _MeleeWargear:
    def __init__(self, name: str):
        self.name = name

    @staticmethod
    def is_melee() -> bool:
        return True

    @staticmethod
    def is_ranged() -> bool:
        return False


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
    move: int = 12,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            move=move,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army.with_detachment("Space Marines", "The Angelic Host")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0

    sm_player.command_points = 10
    enemy_player.command_points = 10

    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 1.5, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _destroy_unit(unit: Unit, game_map) -> object:
    model = unit.models[0]
    model.wounds = 0
    model.die(game_map=game_map)
    return model


def _pending_names(stratagems) -> set[str]:
    return {
        str(item.get("stratagem", "") or "").strip().upper()
        for item in list(stratagems.get_pending_reactions(clear=True) or [])
    }


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _melee_wargear(name: str = "Encarmine Blade") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "5",
            "AP": "-2",
            "D": "1",
            "description": "",
        }
    )


def _melee_profile(name: str = "Encarmine Blade") -> WargearProfile:
    return WargearProfile(
        str(name),
        {
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "5",
            "AP": "-2",
            "D": "1",
            "description": "",
        },
        parent_wargear=_MeleeWargear(name),
    )


def test_angelic_host_stratagem_descriptors_registered():
    expected = {
        "000009191004": ("Angel's Sacrifice", "engaged_enemy_target_lock"),
        "000009191007": ("Death from the Skies", "shoot_and_charge_after_advance_or_fall_back"),
        "000009191006": ("Descent of Angels", "deep_strike_min_distance_override"),
        "000009191005": ("Martial Exemplars", "grant_keywords_to_melee_weapons"),
        "000009191002": ("Unbridled Ardour", "battlelong_sanguinary_guard_hit_and_wound_rerolls_vs_marked_destroyer"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        assert by_id is not None
        assert by_id.name == expected_name
        assert by_id.effect == expected_effect
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_name is not None
        assert by_name.name == expected_name
        assert by_name.effect == expected_effect


def test_angelic_host_phase_start_reactions_queue_expected_stratagems():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    engaged_jump = _make_unit(
        "Sanguinary Guard",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    reserve_jump = _make_unit(
        "Reserve Guard",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    reserve_jump.has_deep_strike = lambda: True
    reserve_jump.can_arrive_from_reserves = lambda current_turn: True
    reserve_jump.deployed = False
    reserve_jump.reserve_status = "reserves"
    reserve_jump.embarked_in = None

    sm_army.add_unit(engaged_jump)
    sm_army.add_unit(reserve_jump)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, engaged_jump, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.75, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    assert _pending_names(sm_player.stratagems) == {"DESCENT OF ANGELS"}

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    assert _pending_names(sm_player.stratagems) == {"ANGEL'S SACRIFICE", "MARTIAL EXEMPLARS"}


def test_death_from_the_skies_and_unbridled_ardour_reactions_queue_when_triggered():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    jump = _make_unit(
        "Jump Pack Squad",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    destroyed = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Destroyer",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(jump)
    sm_army.add_unit(destroyed)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, jump, 10.0, 10.0)
    _deploy_unit(game, destroyed, 14.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    game.event_system.publish("unit_move_ended", unit=jump, action="advance")
    assert _pending_names(sm_player.stratagems) == {"DEATH FROM THE SKIES"}

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    dead_model = _destroy_unit(destroyed, game.map)
    sm_player.stratagems._on_unit_destroyed(unit=destroyed, last_model=dead_model, destroyed_by_unit=enemy)
    assert _pending_names(sm_player.stratagems) == {"UNBRIDLED ARDOUR"}


def test_angels_sacrifice_restricts_fight_targets():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    marked = _make_unit(
        "Sanguinary Guard",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    other = _make_unit(
        "Other Jump Pack Unit",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Fighter",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(marked)
    sm_army.add_unit(other)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, marked, 10.0, 10.0)
    _deploy_unit(game, other, 13.5, 10.0)
    _deploy_unit(game, enemy, 11.75, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    ok = sm_player.stratagems.use("ANGEL'S SACRIFICE", unit=marked, phase_name="Fight phase")
    assert ok

    fight_manager = FightPhaseManager(game)
    eligible = fight_manager._get_eligible_targets(enemy)
    assert marked in eligible
    assert other not in eligible
    assert len(eligible) == 1


def test_martial_exemplars_grants_melee_lethal_hits_and_precision():
    game, sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    jump = _make_unit(
        "Sanguinary Guard",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    jump.models[0].wargear = [_melee_wargear()]
    sm_army.add_unit(jump)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, jump, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.75, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "MARTIAL EXEMPLARS")
    assert pending is not None

    ok = sm_player.stratagems.use("MARTIAL EXEMPLARS", unit=jump, phase_name="Fight phase", dequeue=True)
    assert ok
    bonus = jump.get_model_weapon_keyword_bonuses(
        attack_type="melee",
        model=jump.models[0],
        weapon_profile=_melee_profile(),
        target=enemy,
    )
    assert bool(bonus.get("lethal_hits"))
    assert bool(bonus.get("precision"))


def test_descent_of_angels_sets_six_inch_deep_strike_override():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    reserve_jump = _make_unit(
        "Reserve Guard",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    reserve_jump.has_deep_strike = lambda: True
    reserve_jump.can_arrive_from_reserves = lambda current_turn: True
    reserve_jump.deployed = False
    reserve_jump.reserve_status = "reserves"
    reserve_jump.embarked_in = None
    sm_army.add_unit(reserve_jump)

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    ok = sm_player.stratagems.use("DESCENT OF ANGELS", unit=reserve_jump, phase_name="Movement phase")
    assert ok
    assert float(reserve_jump.get_deep_strike_min_distance_override() or 0.0) == 6.0


def test_death_from_the_skies_grants_shoot_and_charge_permissions_after_use():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    jump = _make_unit(
        "Jump Pack Squad",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(jump)
    _deploy_unit(game, jump, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    assert jump.has_advance_and_shoot() is False
    assert jump.can_charge_after_fall_back() is False

    game.event_system.publish("unit_move_ended", unit=jump, action="advance")
    ok = sm_player.stratagems.use(
        "DEATH FROM THE SKIES",
        unit=jump,
        moving_unit=jump,
        action="advance",
        phase_name="Movement phase",
    )
    assert ok
    assert jump.has_advance_and_shoot() is True
    assert jump.has_advance_and_charge() is True
    assert jump.has_fell_back_and_shoot() is True
    assert jump.can_charge_after_fall_back() is True


def test_unbridled_ardour_grants_sanguinary_guard_hit_and_wound_rerolls_vs_destroyer():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    destroyed = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sanguinary_guard = _make_unit(
        "Sanguinary Guard",
        keywords=["INFANTRY", "JUMP PACK"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Destroyer",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    other_enemy = _make_unit(
        "Other Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(destroyed)
    sm_army.add_unit(sanguinary_guard)
    enemy_army.add_unit(enemy)
    enemy_army.add_unit(other_enemy)
    _deploy_unit(game, destroyed, 10.0, 10.0)
    _deploy_unit(game, sanguinary_guard, 12.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _deploy_unit(game, other_enemy, 24.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    dead_model = _destroy_unit(destroyed, game.map)
    sm_player.stratagems._on_unit_destroyed(unit=destroyed, last_model=dead_model, destroyed_by_unit=enemy)

    ok = sm_player.stratagems.use(
        "UNBRIDLED ARDOUR",
        unit=destroyed,
        enemy_unit=enemy,
        phase_name="Shooting phase",
    )
    assert ok

    profile = _melee_profile()
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
        hit = profile._hit_target_with_tracking(enemy, sanguinary_guard.models[0], {}, roll_value=1)
    assert int(hit.get("reroll", 0) or 0) == 5
    assert "Unbridled Ardour" in list(hit.get("reroll_full_reasons", []) or [])

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
        wound = profile._wound_target_with_tracking(enemy, sanguinary_guard.models[0], {}, roll_value=1)
    assert int(wound.get("reroll", 0) or 0) == 5
    assert "Unbridled Ardour" in list(wound.get("reroll_full_reasons", []) or [])

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
        other_hit = profile._hit_target_with_tracking(other_enemy, sanguinary_guard.models[0], {}, roll_value=1)
    assert int(other_hit.get("reroll", 0) or 0) == 0
