from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
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
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
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
                "M": "6",
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


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army("Space Marines", "Champions of Fenris")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
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
        model.set_location(float(x) + float(index) * 2.0, float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _make_objective(name: str, x: float, y: float) -> Objective:
    point = ObjectivePoint(float(x), float(y), 0.0, control_radius=3.0)
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="",
        conditions=lambda _game: False,
        location=point,
    )


def _melee_wargear(name: str = "Frost Blade") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee",
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "5",
            "AP": "-2",
            "D": "2",
            "description": "",
        }
    )


def _ranged_wargear(name: str = "Bolt Rifle") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "-1",
            "D": "1",
            "description": "",
        }
    )


def test_champions_of_fenris_stratagem_descriptors_registered():
    expected = {
        "000009852005": ("Chilling Howl", "force_battleshock_test_with_below_half_modifier"),
        "000009852007": ("Onrushing Storm", "enter_strategic_reserves"),
        "000009852002": ("Preytaker's Eye", "choose_lethal_hits_or_sustained_hits_1_for_weapons"),
        "000009852004": ("Runes of Claiming", "sticky_objective"),
        "000009852006": ("Stalking Wolves", "grant_stealth"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_chilling_howl_queues_and_forces_battleshock_with_below_half_modifier():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    terminators = _make_unit(
        "Wolf Guard Terminators",
        keywords=["INFANTRY", "TERMINATOR"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    nearby_enemy = _make_unit(
        "Enemy Infantry Alpha",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    far_enemy = _make_unit(
        "Enemy Infantry Beta",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    sm_army.add_unit(terminators)
    enemy_army.add_unit(nearby_enemy)
    enemy_army.add_unit(far_enemy)
    _deploy_unit(game, terminators, 10.0, 10.0)
    _deploy_unit(game, nearby_enemy, 15.0, 10.0)
    _deploy_unit(game, far_enemy, 20.5, 10.0)
    game.rebuild_entity_registry()

    calls: list[tuple[str, int, int, str]] = []

    def _record_force_test(name: str):
        def _inner(current_turn, modifier=0, source=""):
            calls.append((name, int(current_turn), int(modifier), str(source)))

        return _inner

    nearby_enemy.force_battle_shock_test = _record_force_test("nearby")
    far_enemy.force_battle_shock_test = _record_force_test("far")
    nearby_enemy.is_below_half_strength = lambda: True
    far_enemy.is_below_half_strength = lambda: False

    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
    assert _pending_by_name(sm_player.stratagems, "CHILLING HOWL") is not None

    ok = sm_player.stratagems.use("CHILLING HOWL", unit=terminators, dequeue=True)
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert calls == [("nearby", 1, -1, "CHILLING HOWL")]


def test_onrushing_storm_queues_and_enters_strategic_reserves():
    game, sm_player, enemy_player, sm_army, _enemy_army = _build_game()
    terminators = _make_unit(
        "Wolf Guard Terminators",
        keywords=["INFANTRY", "TERMINATOR"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(terminators)
    _deploy_unit(game, terminators, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert _pending_by_name(sm_player.stratagems, "ONRUSHING STORM") is not None

    ok = sm_player.stratagems.use("ONRUSHING STORM", unit=terminators, dequeue=True)
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert str(getattr(terminators, "reserve_status", "") or "") == "strategic_reserves"
    assert terminators not in list(getattr(game.map, "units", []) or [])


def test_preytakers_eye_shooting_grants_ranged_lethal_hits_and_cleans_up():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    intercessors = _make_unit(
        "Grey Hunters",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    intercessors.models[0].wargear = [_ranged_wargear()]
    sm_army.add_unit(intercessors)
    _deploy_unit(game, intercessors, 10.0, 10.0)

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "PREYTAKER'S EYE")
    assert pending is not None

    ok = sm_player.stratagems.use(
        "PREYTAKER'S EYE",
        unit=intercessors,
        choice={"label": "[LETHAL HITS]"},
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    bonuses = intercessors.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle")
    assert any(
        str(item.get("keyword", "") or "").strip().upper() == "LETHAL HITS"
        and str(item.get("attack_type", "") or "").strip().lower() == "ranged"
        for item in list(bonuses or [])
    )

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert list(intercessors.models[0].get_temporary_weapon_keyword_bonuses("Bolt Rifle") or []) == []


def test_preytakers_eye_fight_accepts_sustained_hits_alias_and_cleans_up():
    game, sm_player, enemy_player, sm_army, _enemy_army = _build_game()
    blood_claws = _make_unit(
        "Blood Claws",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    blood_claws.models[0].wargear = [_melee_wargear()]
    sm_army.add_unit(blood_claws)
    _deploy_unit(game, blood_claws, 10.0, 10.0)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    pending = _pending_by_name(sm_player.stratagems, "PREYTAKER'S EYE")
    assert pending is not None

    ok = sm_player.stratagems.use("PREYTAKER'S EYE", unit=blood_claws, choice="SUSTAINED_HITS", dequeue=True)
    assert ok is True
    assert int(sm_player.command_points or 0) == 9

    bonuses = blood_claws.models[0].get_temporary_weapon_keyword_bonuses("Frost Blade")
    assert any(
        str(item.get("keyword", "") or "").strip().upper() == "SUSTAINED HITS 1"
        and str(item.get("attack_type", "") or "").strip().lower() == "melee"
        for item in list(bonuses or [])
    )

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert list(blood_claws.models[0].get_temporary_weapon_keyword_bonuses("Frost Blade") or []) == []


def test_runes_of_claiming_queues_and_applies_sticky_objective_control():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    infantry = _make_unit(
        "Grey Hunters",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    objective = _make_objective("Midfield", 10.0, 10.0)
    objective.location.controlling_player = sm_player

    sm_army.add_unit(infantry)
    _deploy_unit(game, infantry, 10.0, 10.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "COMMAND_PHASE", 0)
    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="COMMAND_PHASE"))
    assert _pending_by_name(sm_player.stratagems, "RUNES OF CLAIMING") is not None

    ok = sm_player.stratagems.use("RUNES OF CLAIMING", unit=infantry, objective=objective, dequeue=True)
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert objective.location.sticky_controller is sm_player
    assert objective.location.controlling_player is sm_player


def test_stalking_wolves_queues_applies_stealth_and_cleans_up():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    defenders = _make_unit(
        "Grey Hunters",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(defenders)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defenders, 10.0, 10.0)
    _deploy_unit(game, attacker, 24.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defenders])
    assert _pending_by_name(sm_player.stratagems, "STALKING WOLVES") is not None

    ok = sm_player.stratagems.use(
        "STALKING WOLVES",
        unit=defenders,
        attacking_unit=attacker,
        target_units=[defenders],
        dequeue=True,
    )
    assert ok is True
    assert int(sm_player.command_points or 0) == 9
    assert bool(defenders.special_rules.get("opponent_shooting_phase_stealth_active")) is True
    assert defenders.has_stealth() is True

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert bool(defenders.special_rules.get("opponent_shooting_phase_stealth_active")) is False
    assert defenders.has_stealth() is False
