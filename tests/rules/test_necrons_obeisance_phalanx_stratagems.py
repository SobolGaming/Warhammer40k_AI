from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

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
        faction_name: str = "Necrons",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 3,
        leadership: int = 7,
        objective_control: int = 1,
        base_size: str = "32mm",
    ) -> None:
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["NECRONS"] if faction_name == "Necrons" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "8" if "VEHICLE" in set(self.keywords) else "5",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
                "base_size": str(base_size),
                "inv_sv": "7",
                "inv_sv_descr": "",
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
    faction_name: str = "Necrons",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 3,
    leadership: int = 7,
    objective_control: int = 1,
    base_size: str = "32mm",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            leadership=leadership,
            objective_control=objective_control,
            base_size=base_size,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _weapon(name: str, *, melee: bool, damage: str = "1") -> Wargear:
    return Wargear(
        {
            "name": str(name),
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "-1",
            "D": str(damage),
            "description": "",
        }
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2

    necron_army = Army.with_detachment("Necrons", "Obeisance Phalanx")
    necron_army.faction_id = "NEC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    necron_player = Player("Necrons", control=PlayerControl.LOCAL, army=necron_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(necron_player)
    game.add_player(enemy_player)

    necron_player.command_points = 10
    enemy_player.command_points = 10
    return game, necron_player, enemy_player, necron_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (idx * 1.5), float(y), 0.0, 0.0)
    if not game.map.place_unit(unit):
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _finalize_game(game: Game, *armies: Army, players: list[Player]) -> None:
    game.rebuild_entity_registry()
    for army in armies:
        army.configure_rule_managers(force=True)
    refresh = getattr(game, "refresh_rule_subscribers", None)
    if callable(refresh):
        refresh()
    for player in players:
        player.stratagems.refresh_available()


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> SimpleNamespace:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)
    return phase


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def test_obeisance_phalanx_stratagem_descriptors_registered():
    expected = {
        "000008551002": ("Your Time Is Nigh", "enemy_battleshock_and_leadership_tests_minus_one_until_end_of_battle"),
        "000008551003": ("Enslaved Artifice", "critical_hits_on_5plus"),
        "000008551004": ("Nanoassembly Protocols", "defensive_damage_reduction"),
        "000008551005": ("Sentinels of Eternity", "fight_on_death_on_4_plus"),
        "000008551006": ("Suffer No Rival", "grant_precision_to_melee_weapons"),
        "000008551007": ("Territorial Obsession", "objective_control_bonus_until_next_command_phase"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name) == expected_name
        assert str(by_name.name) == expected_name
        assert str(by_id.effect) == expected_effect


def test_enslaved_artifice_queues_in_shooting_phase_and_grants_critical_hits_until_phase_end():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    destroyers = _make_unit(
        "Lokhust Destroyers",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    destroyers.models[0].wargear = [_weapon("Gauss Cannon", melee=False)]
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(destroyers)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, destroyers, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, necron_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(necron_player.stratagems, "ENSLAVED ARTIFICE")
    assert pending is not None
    assert destroyers in list(pending.get("candidates") or [])

    ok = necron_player.stratagems.use(
        "ENSLAVED ARTIFICE",
        unit=destroyers,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9

    profile = destroyers.models[0].wargear[0].profiles["default"]
    hit = profile._hit_target_with_tracking(
        enemy,
        destroyers.models[0],
        {},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(hit.get("crit_threshold", 0) or 0) == 5

    game.event_system.publish("phase_end", player=necron_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    expired_hit = profile._hit_target_with_tracking(
        enemy,
        destroyers.models[0],
        {},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(expired_hit.get("crit_threshold", 0) or 0) == 6


def test_nanoassembly_protocols_queues_and_reduces_damage_until_phase_end():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    stalker = _make_unit(
        "Triarch Stalker",
        keywords=["VEHICLE", "TRIARCH"],
        faction_keywords=["NECRONS"],
        wounds=12,
        base_size="100mm",
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(stalker)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, stalker, 10.0, 10.0)
    _deploy_unit(game, attacker, 18.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[stalker])

    pending = _pending_by_name(necron_player.stratagems, "NANOASSEMBLY PROTOCOLS")
    assert pending is not None
    assert stalker in list(pending.get("candidates") or [])

    ok = necron_player.stratagems.use(
        "NANOASSEMBLY PROTOCOLS",
        unit=stalker,
        attacking_unit=attacker,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9

    entries = list(stalker.special_rules.get("defensive_damage_reductions", []) or [])
    assert any(
        int(entry.get("value", 0) or 0) == 1
        and str(entry.get("expires_phase", "") or "").strip().upper() == "SHOOTING_PHASE"
        for entry in entries
        if isinstance(entry, dict)
    )

    profile = _weapon("Enemy Rifle", melee=False, damage="2").profiles["default"]
    target_model = stalker.models[0]
    target_model.wounds = 12
    reduced = profile._damage_target_with_tracking(
        target_model,
        attacker.models[0],
        {},
        allow_rerolls=False,
    )
    assert int(reduced.get("damage_applied", 0) or 0) == 1

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert not list(stalker.special_rules.get("defensive_damage_reductions", []) or [])

    target_model.wounds = 12
    normal = profile._damage_target_with_tracking(
        target_model,
        attacker.models[0],
        {},
        allow_rerolls=False,
    )
    assert int(normal.get("damage_applied", 0) or 0) == 2


def test_sentinels_of_eternity_queues_and_grants_fight_on_death_until_phase_end():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    praetorians = _make_unit(
        "Triarch Praetorians",
        keywords=["INFANTRY", "TRIARCH PRAETORIANS"],
        faction_keywords=["NECRONS"],
    )
    enemy = _make_unit(
        "Enemy Bruisers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(praetorians)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, praetorians, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.5, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_targets_selected", attacking_unit=enemy, target_units=[praetorians])

    pending = _pending_by_name(necron_player.stratagems, "SENTINELS OF ETERNITY")
    assert pending is not None
    assert praetorians in list(pending.get("candidates") or [])

    ok = necron_player.stratagems.use(
        "SENTINELS OF ETERNITY",
        unit=praetorians,
        attacking_unit=enemy,
        target_units=[praetorians],
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9

    rule = praetorians.get_melee_fight_on_death_after_attacks_rule(model=praetorians.models[0])
    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 4
    assert "SENTINELS OF ETERNITY" in str(rule.get("source", "") or "").upper()

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert praetorians.get_melee_fight_on_death_after_attacks_rule(model=praetorians.models[0]) is None


def test_suffer_no_rival_queues_and_grants_melee_precision_until_phase_end():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    lychguard = _make_unit(
        "Lychguard",
        keywords=["INFANTRY", "LYCHGUARD"],
        faction_keywords=["NECRONS"],
    )
    lychguard.models[0].wargear = [_weapon("Hyperphase Sword", melee=True)]
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(lychguard)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, lychguard, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.5, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, necron_player, "FIGHT_PHASE", 0)
    pending = _pending_by_name(necron_player.stratagems, "SUFFER NO RIVAL")
    assert pending is not None
    assert lychguard in list(pending.get("candidates") or [])

    ok = necron_player.stratagems.use(
        "SUFFER NO RIVAL",
        unit=lychguard,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9

    bonuses = list(lychguard.models[0].get_temporary_weapon_keyword_bonuses("Hyperphase Sword") or [])
    assert any(
        str(entry.get("keyword", "") or "").strip().upper() == "PRECISION"
        and str(entry.get("attack_type", "") or "").strip().lower() == "melee"
        for entry in bonuses
        if isinstance(entry, dict)
    )

    game.event_system.publish("phase_end", player=necron_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    assert list(lychguard.models[0].get_temporary_weapon_keyword_bonuses("Hyperphase Sword") or []) == []


def test_territorial_obsession_queues_and_grants_vehicle_objective_control_until_next_command_phase():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    stalker = _make_unit(
        "Triarch Stalker",
        keywords=["VEHICLE", "TRIARCH"],
        faction_keywords=["NECRONS"],
        objective_control=1,
        wounds=12,
        base_size="100mm",
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(stalker)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, stalker, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    model = stalker.models[0]
    baseline_oc = int(stalker.get_effective_model_characteristic(model, "objective_control") or 0)
    assert baseline_oc == 1

    _set_phase(game, necron_player, "COMMAND_PHASE", 0)
    pending = _pending_by_name(necron_player.stratagems, "TERRITORIAL OBSESSION")
    assert pending is not None
    assert stalker in list(pending.get("candidates") or [])

    ok = necron_player.stratagems.use(
        "TERRITORIAL OBSESSION",
        unit=stalker,
        phase_name="Command phase",
        dequeue=True,
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9
    boosted_oc = int(stalker.get_effective_model_characteristic(model, "objective_control") or 0)
    assert boosted_oc == 4

    game.turn = 3
    _set_phase(game, necron_player, "COMMAND_PHASE", 0)
    after_oc = int(stalker.get_effective_model_characteristic(model, "objective_control") or 0)
    assert after_oc == 1


def test_your_time_is_nigh_queues_after_enemy_warlord_destroyed_and_applies_persistent_test_penalties():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    necron_warlord = _make_unit(
        "Overlord",
        keywords=["CHARACTER", "INFANTRY", "OVERLORD"],
        faction_keywords=["NECRONS"],
        wounds=6,
    )
    enemy_warlord = _make_unit(
        "Enemy Warlord",
        faction_name="Enemy",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=6,
        leadership=7,
    )
    enemy_support = _make_unit(
        "Enemy Support",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        leadership=7,
    )
    necron_warlord.is_warlord = True
    enemy_warlord.is_warlord = True
    necron_army.warlord = necron_warlord
    enemy_army.warlord = enemy_warlord
    necron_army.add_unit(necron_warlord)
    enemy_army.add_unit(enemy_warlord)
    enemy_army.add_unit(enemy_support)
    _deploy_unit(game, necron_warlord, 10.0, 10.0)
    _deploy_unit(game, enemy_warlord, 18.0, 10.0)
    _deploy_unit(game, enemy_support, 21.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish(
        "unit_destroyed",
        unit=enemy_warlord,
        destroyed_by_unit=necron_warlord,
        destroyed_by_model=necron_warlord.models[0],
    )

    pending = _pending_by_name(necron_player.stratagems, "YOUR TIME IS NIGH")
    assert pending is not None
    assert list(pending.get("candidates") or []) == [necron_warlord]

    ok = necron_player.stratagems.use(
        "YOUR TIME IS NIGH",
        unit=necron_warlord,
        destroyed_unit=enemy_warlord,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9

    for enemy_unit in (enemy_warlord, enemy_support):
        sr = dict(getattr(enemy_unit, "special_rules", {}) or {})
        assert int(sr.get("obeisance_your_time_is_nigh_battle_shock_test_modifier", 0) or 0) == -1
        assert int(sr.get("obeisance_your_time_is_nigh_leadership_test_modifier", 0) or 0) == -1
        assert "YOUR TIME IS NIGH" in str(sr.get("obeisance_your_time_is_nigh_source", "") or "").upper()

    with patch("warhammer40k_ai.units.unit_mixins.state_attachment_mixin.get_roll", return_value=8):
        enemy_support.pass_leadership_check()
    assert int(getattr(enemy_support, "_last_leadership_test_roll", 0) or 0) == 8
    assert int(getattr(enemy_support, "_last_leadership_test_modified_roll", 0) or 0) == 7
