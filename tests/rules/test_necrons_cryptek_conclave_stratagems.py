from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import ObjectivePoint
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
        abilities=None,
        model_count: int = 1,
        wounds: int = 3,
        movement: int = 6,
    ):
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
                "M": str(int(movement)),
                "T": "5",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        normalized_abilities = []
        for ability in list(abilities or []):
            entry = dict(ability)
            entry.setdefault("type", "")
            entry.setdefault("parameter", "")
            normalized_abilities.append(entry)
        self.datasheets_abilities = normalized_abilities
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
    abilities=None,
    model_count: int = 1,
    wounds: int = 3,
    movement: int = 6,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            model_count=model_count,
            wounds=wounds,
            movement=movement,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _reanimation_ability():
    return [{"name": "Reanimation Protocols", "description": "", "type": "Datasheet", "parameter": ""}]


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    necron_army = Army.with_detachment("Necrons", "Cryptek Conclave")
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
    placed = game.map.place_unit(unit)
    if not placed:
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


def _make_objective(name: str, x: float, y: float, *, control_radius: float = 3.0):
    return SimpleNamespace(
        id=f"objective-{name.lower().replace(' ', '-')}",
        name=name,
        location=ObjectivePoint(float(x), float(y), 0.0, control_radius=float(control_radius)),
    )


def _equip_weapon(
    unit: Unit,
    *,
    name: str,
    melee: bool = False,
    range_value: str = "24",
    strength: str = "4",
    ap: str = "0",
    damage: str = "1",
):
    profile = None
    for model in list(getattr(unit, "models", []) or []):
        weapon = Wargear(
            {
                "name": name,
                "type": "Melee" if melee else "Ranged",
                "range": "Melee" if melee else str(range_value),
                "A": "1",
                "BS_WS": "3+",
                "S": str(strength),
                "AP": str(ap),
                "D": str(damage),
                "description": "",
            }
        )
        model.wargear = [weapon]
        if profile is None:
            profile = weapon.profiles["default"]
    return profile


def test_cryptek_conclave_stratagem_descriptors_registered():
    expected = {
        "000010665004": ("ANIMUS CURSE", "mark_enemy_for_necrons_hit_rerolls"),
        "000010665003": ("MICROSCARAB SWARM", "conditional_unit_invulnerable_save_by_keyword"),
        "000010665002": ("MOLECULAR TARGETING", "ignore_skill_hit_and_conditional_wound_modifiers"),
        "000010665007": ("POTENTIALITY SYPHON", "trigger_reanimation_protocols_with_conditional_bonus"),
        "000010665005": ("SYNERGISTIC EMPOWERMENT", "temporary_model_cryptek_keyword"),
        "000010665006": ("UNTAPPED POWER", "additional_technosorcerous_augmentation_choice"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        by_name = get_stratagem_tool_descriptor(name=expected_name)
        assert by_id is not None
        assert by_name is not None
        assert str(by_id.name) == expected_name
        assert str(by_name.name) == expected_name
        assert str(by_id.effect) == expected_effect


def test_synergistic_empowerment_and_molecular_targeting_grant_temporary_cryptek_modifier_ignores():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    technomancer = _make_unit(
        "Technomancer",
        keywords=["INFANTRY", "CRYPTEK", "CHARACTER"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    warriors = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY", "BATTLELINE", "NECRON WARRIORS"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
        model_count=2,
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    profile = _equip_weapon(warriors, name="Gauss Flayer", range_value="24")
    necron_army.add_unit(technomancer)
    necron_army.add_unit(warriors)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, technomancer, 10.0, 10.0)
    _deploy_unit(game, warriors, 16.0, 10.0)
    _deploy_unit(game, enemy, 28.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    phase = _set_phase(game, necron_player, "SHOOTING_PHASE", 0)
    ok_synergy = necron_player.stratagems.use(
        "SYNERGISTIC EMPOWERMENT",
        unit=technomancer,
        target_model=warriors.models[0],
        phase_name="Shooting phase",
    )
    assert ok_synergy is True

    mgr = necron_army.necrons_detachments
    assert bool(mgr.cryptek_conclave_unit_has_cryptek_keyword(warriors)) is True

    ok_molecular = necron_player.stratagems.use(
        "MOLECULAR TARGETING",
        unit=warriors,
        phase_name="Shooting phase",
    )
    assert ok_molecular is True
    assert int(necron_player.command_points or 0) == 8

    hit_rule = profile._ignore_hit_modifier_rule(warriors.models[0], target_unit=enemy)
    wound_rule = profile._ignore_wound_modifier_rule(warriors.models[0])
    assert isinstance(hit_rule, dict)
    assert isinstance(wound_rule, dict)
    assert "MOLECULAR TARGETING" in str(hit_rule.get("name", "")).upper()
    assert "MOLECULAR TARGETING" in str(wound_rule.get("name", "")).upper()

    game.event_system.publish("phase_end", player=necron_player, phase=phase)

    assert bool(mgr.cryptek_conclave_unit_has_cryptek_keyword(warriors)) is False
    assert profile._ignore_hit_modifier_rule(warriors.models[0], target_unit=enemy) is None
    assert profile._ignore_wound_modifier_rule(warriors.models[0]) is None


def test_untapped_power_extends_technosorcerous_choices_until_phase_end():
    game, necron_player, _enemy_player, necron_army, enemy_army = _build_game()
    cryptek = _make_unit(
        "Chronomancer",
        keywords=["INFANTRY", "CRYPTEK", "CHARACTER"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    _equip_weapon(cryptek, name="Entropic Lance", range_value="18")
    necron_army.add_unit(cryptek)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, cryptek, 10.0, 10.0)
    _deploy_unit(game, enemy, 22.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player])

    phase = _set_phase(game, necron_player, "SHOOTING_PHASE", 0)
    base_options = necron_army.necrons_detachments.technosorcerous_choice_options(cryptek)
    assert len(base_options) == 5

    ok = necron_player.stratagems.use(
        "UNTAPPED POWER",
        unit=cryptek,
        phase_name="Shooting phase",
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9

    empowered_options = necron_army.necrons_detachments.technosorcerous_choice_options(cryptek)
    assert len(empowered_options) == 10
    assert any(str(option.get("choice", "")) == "ASSAULT+HEAVY" for option in empowered_options)
    assert bool(necron_army.necrons_detachments.technosorcerous_choice_is_valid(cryptek, "ASSAULT+HEAVY")) is True

    game.event_system.publish("phase_end", player=necron_player, phase=phase)
    cleared_options = necron_army.necrons_detachments.technosorcerous_choice_options(cryptek)
    assert len(cleared_options) == 5
    assert bool(necron_army.necrons_detachments.technosorcerous_choice_is_valid(cryptek, "ASSAULT+HEAVY")) is False


def test_potentiality_syphon_triggers_reanimation_with_cryptek_bonus(monkeypatch):
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    cryptek_unit = _make_unit(
        "Immortals",
        keywords=["INFANTRY", "CRYPTEK", "IMMORTALS"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
        model_count=2,
    )
    objective = _make_objective("Center", 10.5, 10.0)
    game.map.objectives = [objective]
    necron_army.add_unit(cryptek_unit)
    _deploy_unit(game, cryptek_unit, 10.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    phase = _set_phase(game, enemy_player, "COMMAND_PHASE", 1)
    calls = {}

    def _capture_reanimation(*args, **kwargs):
        calls["args"] = args
        calls["kwargs"] = kwargs
        return {"healed": 0, "returned": 0}

    monkeypatch.setattr(cryptek_unit, "apply_reanimation_protocols", _capture_reanimation)
    monkeypatch.setattr("warhammer40k_ai.rules.stratagems_necrons.dice_module.get_roll", lambda _expr: 2)

    ok = necron_player.stratagems.use(
        "POTENTIALITY SYPHON",
        unit=cryptek_unit,
        phase_name="Command phase",
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9
    assert calls["args"] == (3,)
    assert str(calls["kwargs"]["roll_expr"]) == "D3"
    assert calls["kwargs"]["game_map"] is game.map

    game.event_system.publish("phase_end", player=enemy_player, phase=phase)


def test_microscarab_swarm_queues_and_grants_immortals_invulnerable_save_until_phase_end():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    immortals = _make_unit(
        "Immortals",
        keywords=["INFANTRY", "CRYPTEK", "IMMORTALS"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
        model_count=2,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(immortals)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, immortals, 10.0, 10.0)
    _deploy_unit(game, attacker, 20.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    phase = _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[immortals])
    assert _pending_by_name(necron_player.stratagems, "MICROSCARAB SWARM") is not None

    ok = necron_player.stratagems.use(
        "MICROSCARAB SWARM",
        unit=immortals,
        attacking_unit=attacker,
        target_units=[immortals],
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9

    inv_value, inv_source = immortals.get_model_invulnerable_save_override(immortals.models[0])
    assert int(inv_value or 0) == 4
    assert "MICROSCARAB SWARM" in str(inv_source or "").upper()

    game.event_system.publish("phase_end", player=enemy_player, phase=phase)
    cleared_value, _ = immortals.get_model_invulnerable_save_override(immortals.models[0])
    assert int(cleared_value or 0) == 0


def test_animus_curse_queues_and_grants_battlelong_necron_hit_rerolls():
    game, necron_player, enemy_player, necron_army, enemy_army = _build_game()
    cryptek = _make_unit(
        "Plasmancer",
        keywords=["INFANTRY", "CRYPTEK", "CHARACTER"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
    )
    warriors = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY", "BATTLELINE", "NECRON WARRIORS"],
        faction_keywords=["NECRONS"],
        abilities=_reanimation_ability(),
        model_count=2,
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    profile = _equip_weapon(warriors, name="Gauss Flayer", range_value="24")
    necron_army.add_unit(cryptek)
    necron_army.add_unit(warriors)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, cryptek, 10.0, 10.0)
    _deploy_unit(game, warriors, 12.0, 10.0)
    _deploy_unit(game, attacker, 24.0, 10.0)
    _finalize_game(game, necron_army, enemy_army, players=[necron_player, enemy_player])

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    necron_player.stratagems._on_unit_shooting_resolved_annihilation_legion(
        attacker_unit=attacker,
        killing_models_by_target={cryptek: [cryptek.models[0]]},
    )
    pending = _pending_by_name(necron_player.stratagems, "ANIMUS CURSE")
    assert pending is not None

    ok = necron_player.stratagems.use(
        "ANIMUS CURSE",
        unit=cryptek,
        destroyed_model=cryptek.models[0],
        enemy_unit=attacker,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok is True
    assert int(necron_player.command_points or 0) == 9

    rerolls = warriors.get_unit_hit_reroll_modifiers(
        "ranged",
        target=attacker,
        attacker_model=warriors.models[0],
        weapon_profile=profile,
        closest_dist=12.0,
    )
    assert bool(rerolls.get("reroll_hit_full")) is True
