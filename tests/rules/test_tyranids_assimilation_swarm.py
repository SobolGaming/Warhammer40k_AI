from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        wounds: str = "6",
        toughness: str = "5",
        model_count: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    wounds: str = "6",
    toughness: str = "5",
    model_count: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
            toughness=toughness,
            model_count=model_count,
        )
    )


def _build_game(detachment_type: str = "Assimilation Swarm"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army("Tyranids", detachment_type)
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyr", control=PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)

    tyr_player.command_points = 10
    enemy_player.command_points = 10
    tyr_army.configure_rule_managers(force=True)
    tyr_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, tyr_player, enemy_player, tyr_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (0.2 * idx), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _make_objective(name: str, x: float, y: float) -> Objective:
    point = ObjectivePoint(x=float(x), y=float(y), z=0.0, control_radius=3.0)
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description=f"Control {name}",
        conditions=lambda _game: False,
        location=point,
    )


def _pending_reaction(player: Player, stratagem_name: str):
    wanted = str(stratagem_name or "").strip().upper()
    for reaction in reversed(list(player.stratagems.get_pending_reactions() or [])):
        if str(reaction.get("stratagem", "") or "").strip().upper() == wanted:
            return reaction
    return None


def _make_melee_profile(*, attacks: int = 1, strength: int = 4):
    weapon = Wargear(
        {
            "name": "Talons",
            "type": "Melee",
            "range": "Melee",
            "A": str(int(attacks)),
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def test_parasitic_biomorphology_grants_strength_and_unlocks_attacks_after_fight_kill():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    bearer_unit = _make_unit(
        "Assimilator Prime",
        keywords=["TYRANIDS", "INFANTRY", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
        wounds="5",
    )
    harvester = _make_unit(
        "Haruspex",
        keywords=["TYRANIDS", "MONSTER", "HARVESTER"],
        faction_keywords=["TYRANIDS"],
        wounds="8",
    )
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="4",
        toughness="4",
    )
    tyr_army.add_unit(bearer_unit)
    tyr_army.add_unit(harvester)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, bearer_unit, 10.0, 10.0)
    _deploy_unit(game, harvester, 14.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    Enhancement(
        id="000008412005",
        name="Parasitic Biomorphology",
        faction_id="TYR",
        detachment="Assimilation Swarm",
        points=25,
        description="",
    ).apply_to_unit(bearer_unit)

    _set_phase(game, tyr_player, "FIGHT_PHASE", 0)
    bearer = bearer_unit.models[0]
    profile = _make_melee_profile(attacks=1, strength=4)

    baseline_attacks = profile.preview_attack_count(enemy, bearer, publish_roll_event=False)
    assert int(baseline_attacks.num_attacks or 0) == 1
    baseline_wound = profile._wound_target_with_tracking(
        enemy,
        bearer,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any(
        "+1S from Parasitic Biomorphology" in str(reason)
        for reason in list(baseline_wound.get("modifiers", []) or [])
    )

    enemy.models[0].wounds = 0
    game.event_system.publish("unit_destroyed", unit=enemy, destroyed_by_unit=bearer_unit)

    assert bool(bearer_unit.special_rules.get("enhancement_parasitic_biomorphology_attacks_unlocked")) is True
    boosted_attacks = profile.preview_attack_count(enemy, bearer, publish_roll_event=False)
    assert int(boosted_attacks.num_attacks or 0) == 2


def test_ablative_carapace_queues_on_shooting_targets_and_grants_fnp_five():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    harvester = _make_unit(
        "Haruspex",
        keywords=["TYRANIDS", "MONSTER", "HARVESTER"],
        faction_keywords=["TYRANIDS"],
        wounds="8",
    )
    attacker = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="4",
    )
    tyr_army.add_unit(harvester)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, harvester, 10.0, 10.0)
    _deploy_unit(game, attacker, 20.0, 10.0)

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[harvester])

    reaction = _pending_reaction(tyr_player, "ABLATIVE CARAPACE")
    assert reaction is not None

    ok = tyr_player.stratagems.use(
        "ABLATIVE CARAPACE",
        unit=harvester,
        attacking_unit=attacker,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok
    assert int(tyr_player.command_points or 0) == 8
    entries = list(harvester.special_rules.get("defensive_fnp_overrides", []) or [])
    assert entries
    assert int(entries[-1].get("value", 0) or 0) == 5


def test_ablative_carapace_grants_fnp_four_while_within_controlled_objective():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    harvester = _make_unit(
        "Psychophage",
        keywords=["TYRANIDS", "MONSTER", "HARVESTER"],
        faction_keywords=["TYRANIDS"],
        wounds="8",
    )
    attacker = _make_unit(
        "Enemy Fighters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="4",
    )
    objective = _make_objective("Center", 10.0, 10.0)
    objective.location.controlling_player = tyr_player
    game.objectives = [objective]
    game.map.objectives = [objective]
    tyr_army.add_unit(harvester)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, harvester, 10.0, 10.0)
    _deploy_unit(game, attacker, 12.0, 10.0)

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    ok = tyr_player.stratagems.use(
        "ABLATIVE CARAPACE",
        unit=harvester,
        attacking_unit=attacker,
        target_units=[harvester],
        phase_name="Fight phase",
    )
    assert ok
    entries = list(harvester.special_rules.get("defensive_fnp_overrides", []) or [])
    assert entries
    assert int(entries[-1].get("value", 0) or 0) == 4


def test_broodguard_impulse_marks_enemy_and_applies_wound_bonus():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    harvester = _make_unit(
        "Harvester",
        keywords=["TYRANIDS", "MONSTER", "HARVESTER"],
        faction_keywords=["TYRANIDS"],
        wounds="8",
    )
    hunter = _make_unit(
        "Warriors",
        keywords=["TYRANIDS", "INFANTRY"],
        faction_keywords=["TYRANIDS"],
        wounds="4",
    )
    enemy = _make_unit(
        "Enemy Killers",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="4",
        toughness="4",
    )
    tyr_army.add_unit(harvester)
    tyr_army.add_unit(hunter)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, harvester, 10.0, 10.0)
    _deploy_unit(game, hunter, 12.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    harvester.models[0].wounds = 0
    tyr_player.stratagems._on_unit_destroyed(unit=harvester, destroyed_by_unit=enemy)

    reaction = _pending_reaction(tyr_player, "BROODGUARD IMPULSE")
    assert reaction is not None

    ok = tyr_player.stratagems.use(
        "BROODGUARD IMPULSE",
        destroyed_unit=harvester,
        destroyed_by_unit=enemy,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok
    assert bool(enemy.special_rules.get("tyranids_broodguard_impulse_active")) is True

    profile = _make_melee_profile(attacks=1, strength=4)
    wound = profile._wound_target_with_tracking(
        enemy,
        hunter.models[0],
        {},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert wound.get("wound") is True
    bonus, source = tyr_army.tyranids_detachments.broodguard_impulse_wound_bonus(
        hunter.models[0],
        target_unit=enemy,
        game=game,
    )
    assert int(bonus or 0) == 1
    assert str(source or "").strip().upper() == "BROODGUARD IMPULSE"


def test_rapacious_hunger_queues_and_harvester_heal_uses_flat_three():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    harvester = _make_unit(
        "Haruspex",
        keywords=["TYRANIDS", "MONSTER", "HARVESTER"],
        faction_keywords=["TYRANIDS"],
        wounds="8",
    )
    enemy = _make_unit(
        "Enemy Victim",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="4",
    )
    tyr_army.add_unit(harvester)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, harvester, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)
    harvester.models[0].wounds = 5

    _set_phase(game, tyr_player, "FIGHT_PHASE", 0)
    enemy.models[0].wounds = 0
    tyr_player.stratagems._on_unit_destroyed(unit=enemy, destroyed_by_unit=harvester)

    reaction = _pending_reaction(tyr_player, "RAPACIOUS HUNGER")
    assert reaction is not None

    ok = tyr_player.stratagems.use(
        "RAPACIOUS HUNGER",
        unit=harvester,
        destroyed_unit=enemy,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok
    assert int(tyr_player.command_points or 0) == 9
    assert int(harvester.models[0].wounds) == int(harvester.models[0]._base_wounds)


def test_reclaim_biomass_queues_before_removal_and_excludes_destroyed_unit():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    harvester = _make_unit(
        "Harvester",
        keywords=["TYRANIDS", "MONSTER", "HARVESTER"],
        faction_keywords=["TYRANIDS"],
        wounds="8",
    )
    doomed = _make_unit(
        "Gaunts",
        keywords=["TYRANIDS", "INFANTRY"],
        faction_keywords=["TYRANIDS"],
        wounds="1",
    )
    target = _make_unit(
        "Warriors",
        keywords=["TYRANIDS", "INFANTRY"],
        faction_keywords=["TYRANIDS"],
        wounds="4",
    )
    tyr_army.add_unit(harvester)
    tyr_army.add_unit(doomed)
    tyr_army.add_unit(target)
    _deploy_unit(game, harvester, 10.0, 10.0)
    _deploy_unit(game, doomed, 14.0, 10.0)
    _deploy_unit(game, target, 16.0, 10.0)
    target.models[0].wounds = 1

    _set_phase(game, tyr_player, "FIGHT_PHASE", 0)
    destroyed_model = doomed.models[0]
    destroyed_model.wounds = 0
    tyr_player.stratagems._on_model_destroyed_before_removal(unit=doomed, model=destroyed_model)

    reaction = _pending_reaction(tyr_player, "RECLAIM BIOMASS")
    assert reaction is not None

    destroyed_id = str(get_entity_id(doomed) or "")
    options = tyr_army.tyranids_detachments.assimilation_regeneration_options_for_harvester(
        harvester,
        game=game,
        player=tyr_player,
        exclude_target_ids=(destroyed_id,),
    )
    assert options
    assert all(str(option.get("target_unit_id", "") or "") != destroyed_id for option in options)

    heal_option = next(
        option for option in options if str(option.get("action", "") or "").strip().lower() == "heal"
    )
    with patch("warhammer40k_ai.rules.tyranids_detachments.get_roll", return_value=2):
        ok = tyr_player.stratagems.use(
            "RECLAIM BIOMASS",
            unit=harvester,
            destroyed_unit=doomed,
            option_key=str(heal_option.get("option_key", "") or ""),
            phase_name="Fight phase",
            dequeue=True,
        )
    assert ok
    assert int(target.models[0].wounds) == int(target.models[0]._base_wounds)


def test_secure_biomass_grants_lethal_hits_and_harvester_crit_five_plus():
    game, tyr_player, _enemy_player, tyr_army, enemy_army = _build_game()
    harvester = _make_unit(
        "Psychophage",
        keywords=["TYRANIDS", "MONSTER", "HARVESTER"],
        faction_keywords=["TYRANIDS"],
        wounds="8",
    )
    enemy = _make_unit(
        "Enemy Target",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds="4",
    )
    tyr_army.add_unit(harvester)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, harvester, 10.0, 10.0)
    _deploy_unit(game, enemy, 12.0, 10.0)

    _set_phase(game, tyr_player, "FIGHT_PHASE", 0)
    ok = tyr_player.stratagems.use("SECURE BIOMASS", unit=harvester, phase_name="Fight phase")
    assert ok

    profile = _make_melee_profile(attacks=1, strength=5)
    attack_state = {}
    hit = profile._hit_target_with_tracking(
        enemy,
        harvester.models[0],
        attack_state,
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit.get("hit") is True
    assert int(hit.get("crit_threshold", 0) or 0) == 5
    assert bool(attack_state.get("lethal_hit", False)) is True
    assert any("Lethal Hits" in str(effect) for effect in list(hit.get("special_effects", []) or []))


def test_tyrannoformed_makes_controlled_objective_sticky():
    game, tyr_player, _enemy_player, tyr_army, _enemy_army = _build_game()
    harvester = _make_unit(
        "Haruspex",
        keywords=["TYRANIDS", "MONSTER", "HARVESTER"],
        faction_keywords=["TYRANIDS"],
        wounds="8",
    )
    objective = _make_objective("Center", 10.0, 10.0)
    objective.location.controlling_player = tyr_player
    game.objectives = [objective]
    game.map.objectives = [objective]
    tyr_army.add_unit(harvester)
    _deploy_unit(game, harvester, 10.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, tyr_player, "COMMAND_PHASE", 0)
    ok = tyr_player.stratagems.use(
        "TYRANNOFORMED",
        unit=harvester,
        objective=str(get_entity_id(objective) or ""),
        phase_name="Command phase",
    )
    assert ok
    assert objective.location.sticky_controller is tyr_player
    assert str(objective.location.sticky_source or "") == "tyrannoformed"
    assert objective.location.controlling_player is tyr_player
