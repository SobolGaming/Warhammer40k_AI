from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Necrons",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
    ):
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Necrons",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    necron_army = Army("Necrons", "Annihilation Legion")
    necron_army.faction_id = "NEC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    necron_player = Player("Necrons", control=PlayerControl.REMOTE, army=necron_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(necron_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, necron_army, enemy_army, necron_player, enemy_player


def _set_unit_location(unit: Unit, *, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str, description: str = "") -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(enhancement_name),
        faction_id="NEC",
        detachment="Annihilation Legion",
        points=20,
        description=str(description or enhancement_name),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _make_ranged_profile(*, ap: int = 0) -> WargearProfile:
    parent = SimpleNamespace(
        name="Gauss Blaster",
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    data = {
        "range": "24",
        "A": "1",
        "BS_WS": "3+",
        "S": "4",
        "AP": str(int(ap)),
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


class _DummyNonMeleeWargear:
    def is_melee(self):
        return False


class _DummyNonMeleeProfile:
    def __init__(self):
        self.parent_wargear = _DummyNonMeleeWargear()


def test_annihilation_legion_enhancement_descriptors_registered():
    expected = {
        "000008543002": ("Eternal Madness", "melee_fight_on_death_after_attacks"),
        "000008543003": ("Ingrained Superiority", "bearer_unit_critical_wound_ap_bonus"),
        "000008543005": ("Eldritch Nightmare", "start_of_fight_phase_bearer_engagement_range_enemy_battleshock"),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_ingrained_superiority_improves_ap_on_critical_wounds_for_bearers_unit():
    game, necron_army, enemy_army, _necron_player, _enemy_player = _build_game()
    source = _make_unit(
        "Lokhust Lord",
        keywords=["CHARACTER", "INFANTRY", "DESTROYER CULT"],
        faction_keywords=["NECRONS"],
        model_count=2,
    )
    target = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(source)
    enemy_army.add_unit(target)
    game.map.units = [source, target]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000008543003",
        enhancement_name="Ingrained Superiority",
        description=(
            "NECRONS model only. Each time a model in the bearer's unit makes an attack, on a Critical Wound, "
            "improve the Armour Penetration characteristic of that attack by 1."
        ),
    )

    bearer = source.models[0]
    other = source.models[1]
    profile = _make_ranged_profile(ap=0)

    crit_save = profile._save_with_tracking(
        target.models[0],
        {
            "attacker_model": other,
            "attacker_unit": source,
            "target_unit": target,
            "crit_wound": True,
        },
        ap=0,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(crit_save.get("ap_modifier", 0) or 0) == -1
    assert any("Ingrained Superiority" in str(effect) for effect in list(crit_save.get("special_effects", []) or []))

    bearer.wounds = 0

    after_bearer_destroyed = profile._save_with_tracking(
        target.models[0],
        {
            "attacker_model": other,
            "attacker_unit": source,
            "target_unit": target,
            "crit_wound": True,
        },
        ap=0,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(after_bearer_destroyed.get("ap_modifier", 0) or 0) == 0


def test_eternal_madness_queues_fight_on_death_for_other_model_in_bearers_unit():
    game, necron_army, _enemy_army, _necron_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE

    source = _make_unit(
        "Lokhust Lord",
        keywords=["CHARACTER", "INFANTRY", "DESTROYER CULT"],
        faction_keywords=["NECRONS"],
        model_count=2,
    )
    necron_army.add_unit(source)
    game.map.units = [source]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000008543002",
        enhancement_name="Eternal Madness",
        description=(
            "NECRONS model only. In the Fight phase, each time a model in the bearer's unit is destroyed, "
            "if that model has not fought this phase, roll one D6: on a 4+, do not remove the destroyed model "
            "from play; it can fight after the attacking models unit has finished making its attacks, and is then removed from play."
        ),
    )

    other = source.models[1]
    source.round_state.fought_this_phase = False
    source._last_destroyed_by_weapon_profile = _DummyNonMeleeProfile()
    other._wounds = 0

    rule = source.get_melee_fight_on_death_after_attacks_rule(model=other)
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 4
    assert "Eternal Madness" in str(rule.get("source", "") or "")

    with patch("warhammer40k_ai.units.unit.get_roll", return_value=4):
        source._handle_model_destroyed(other, game.map)

    pending = list(getattr(source, "_melee_fight_on_death_pending_models", []) or [])
    assert other in pending

    with patch.object(source, "_try_fight_on_death") as mocked:
        source.end_attack_resolution(game_map=game.map)
    assert mocked.call_count == 1


def test_eldritch_nightmare_triggers_battleshock_for_enemy_in_engagement_range():
    game, necron_army, enemy_army, necron_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.FIGHT_PHASE

    source = _make_unit(
        "Skorpekh Lord",
        keywords=["CHARACTER", "INFANTRY", "DESTROYER CULT"],
        faction_keywords=["NECRONS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _set_unit_location(source, x=0.0, y=0.0)
    _set_unit_location(enemy, x=0.5, y=0.0)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000008543005",
        enhancement_name="Eldritch Nightmare",
        description=(
            "DESTROYER CULT model only. At the start of the Fight phase, each enemy unit within Engagement Range "
            "of the bearer must take a Battle-shock test."
        ),
    )

    calls: list[int] = []
    original_take = enemy.take_battle_shock_test
    enemy.take_battle_shock_test = lambda turn: calls.append(int(turn or 0)) or original_take(turn)

    game._on_phase_start_engagement_battleshock(player=necron_player, phase=BattleRoundPhases.FIGHT_PHASE)
    assert len(calls) == 1

    calls.clear()
    _set_unit_location(enemy, x=20.0, y=0.0)
    game._on_phase_start_engagement_battleshock(player=necron_player, phase=BattleRoundPhases.FIGHT_PHASE)
    assert calls == []
