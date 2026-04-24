from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_port import DecisionPort
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.cabal_of_sorcerers import RITUAL_DESTINYS_RUIN
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units import wargear as wargear_mod
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.unit_mixins import damage_death_mixin as death_mod
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility import dice as dice_mod
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.dice import DiceCollection
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Thousand Sons",
        keywords=None,
        faction_keywords=None,
        toughness: str = "4",
        wounds: str = "8",
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": "7",
                "OC": "3",
                "base_size": "60mm",
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
    keywords=None,
    faction_keywords=None,
    faction_name: str = "Thousand Sons",
    toughness: str = "4",
    wounds: str = "8",
) -> Unit:
    datasheet = _MockDatasheet(
        name,
        faction_name=faction_name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        toughness=toughness,
        wounds=wounds,
    )
    unit = Unit(datasheet)
    unit.deployed = True
    return unit


def _set_location(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _make_profile(*, ranged: bool, damage: str = "D6") -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Weapon",
        is_melee=lambda: not ranged,
        is_ranged=lambda: ranged,
    )
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": "24" if ranged else "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": str(damage),
            "description": "",
        },
        parent_wargear=parent,
    )


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
        crit_wound_threshold=None,
        crit_wound_reasons=(),
    )


def _build_game(*, army: Army, enemy_army: Army, phase_name: str = "SHOOTING_PHASE"):
    game_map = SimpleNamespace()
    player = SimpleNamespace(
        id="P1",
        name="P1",
        has_control=lambda: False,
        game=None,
        stratagems=None,
        get_army=lambda: army,
    )
    enemy_player = SimpleNamespace(
        id="P2",
        name="P2",
        has_control=lambda: False,
        game=None,
        stratagems=None,
        get_army=lambda: enemy_army,
    )
    game = SimpleNamespace(
        turn=1,
        phase=SimpleNamespace(name=str(phase_name)),
        players=[player, enemy_player],
        map=game_map,
        decision_port=DecisionPort(),
        get_current_player=lambda: player,
    )
    game.install_decision_providers = lambda **providers: game.decision_port.install(providers)
    game_map.game = game
    player.game = game
    enemy_player.game = game
    army.player = player
    enemy_army.player = enemy_player
    return game


def _build_real_game():
    army = Army.with_detachment("Thousand Sons", "Warpforged Cabal")
    army.faction_id = "TS"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    player = Player("Player", PlayerControl.REMOTE, army=army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
    return game, army, enemy_army, player, enemy_player


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="TS",
        detachment="Warpforged Cabal",
        points=25,
        description="",
    ).apply_to_unit(unit)


def _find_master_request(game: Game):
    return next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "master_of_mechanisms"
    )


def _option_for_model(request, model):
    model_id = str(get_entity_id(model) or "")
    return next(
        option
        for option in list(getattr(request, "options", []) or [])
        if str((getattr(option, "payload", {}) or {}).get("target_model_id", "") or "") == model_id
    )


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]


def test_warpfire_infusion_nearby_psyker_grants_one_hit_wound_and_damage_reroll():
    army = Army.with_detachment("Thousand Sons", "Warpforged Cabal")
    army.faction_id = "TS"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    vehicle = _make_unit(
        "Thousand Sons Tank",
        keywords=["THOUSAND SONS", "VEHICLE"],
        faction_keywords=["THOUSAND SONS"],
    )
    psyker = _make_unit(
        "Thousand Sons Psyker",
        keywords=["THOUSAND SONS", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
    )
    army.add_unit(vehicle)
    army.add_unit(psyker)
    _set_location(vehicle, 0.0, 0.0)
    _set_location(psyker, 4.0, 0.0)
    game = _build_game(army=army, enemy_army=enemy_army, phase_name="SHOOTING_PHASE")

    mgr = army.thousand_sons_detachments
    assert mgr.warpfire_infusion_start_selection(vehicle, action="shoot", game=game)

    assert mgr.warpfire_infusion_reroll_is_available(vehicle, "hit", action="shoot", game=game)
    assert mgr.consume_warpfire_infusion_reroll(vehicle, "hit", action="shoot", game=game)
    assert not mgr.warpfire_infusion_reroll_is_available(vehicle, "hit", action="shoot", game=game)

    assert mgr.warpfire_infusion_reroll_is_available(vehicle, "wound", action="shoot", game=game)
    assert mgr.consume_warpfire_infusion_reroll(vehicle, "wound", action="shoot", game=game)
    assert not mgr.warpfire_infusion_reroll_is_available(vehicle, "wound", action="shoot", game=game)

    assert mgr.warpfire_infusion_reroll_is_available(vehicle, "damage", action="shoot", game=game)
    assert mgr.consume_warpfire_infusion_reroll(vehicle, "damage", action="shoot", game=game)
    assert not mgr.warpfire_infusion_reroll_is_available(vehicle, "damage", action="shoot", game=game)


def test_warpfire_infusion_without_nearby_psyker_allows_only_one_total_reroll():
    army = Army.with_detachment("Thousand Sons", "Warpforged Cabal")
    army.faction_id = "TS"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    vehicle = _make_unit(
        "Thousand Sons Tank",
        keywords=["THOUSAND SONS", "VEHICLE"],
        faction_keywords=["THOUSAND SONS"],
    )
    psyker = _make_unit(
        "Thousand Sons Psyker",
        keywords=["THOUSAND SONS", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
    )
    army.add_unit(vehicle)
    army.add_unit(psyker)
    _set_location(vehicle, 0.0, 0.0)
    _set_location(psyker, 20.0, 0.0)
    game = _build_game(army=army, enemy_army=enemy_army, phase_name="SHOOTING_PHASE")

    mgr = army.thousand_sons_detachments
    assert mgr.warpfire_infusion_start_selection(vehicle, action="shoot", game=game)
    assert mgr.consume_warpfire_infusion_reroll(vehicle, "hit", action="shoot", game=game)
    assert not mgr.warpfire_infusion_reroll_is_available(vehicle, "hit", action="shoot", game=game)
    assert not mgr.warpfire_infusion_reroll_is_available(vehicle, "wound", action="shoot", game=game)
    assert not mgr.warpfire_infusion_reroll_is_available(vehicle, "damage", action="shoot", game=game)


def test_warpfire_infusion_rerolls_hit_wound_and_damage_in_attack_resolution(monkeypatch):
    army = Army.with_detachment("Thousand Sons", "Warpforged Cabal")
    army.faction_id = "TS"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    vehicle = _make_unit(
        "Thousand Sons Tank",
        keywords=["THOUSAND SONS", "VEHICLE"],
        faction_keywords=["THOUSAND SONS"],
        wounds="12",
    )
    psyker = _make_unit(
        "Thousand Sons Psyker",
        keywords=["THOUSAND SONS", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
        wounds="4",
    )
    target = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="4",
        wounds="12",
    )
    army.add_unit(vehicle)
    army.add_unit(psyker)
    enemy_army.add_unit(target)
    _set_location(vehicle, 0.0, 0.0)
    _set_location(psyker, 4.0, 0.0)
    _set_location(target, 8.0, 0.0)
    game = _build_game(army=army, enemy_army=enemy_army, phase_name="SHOOTING_PHASE")
    army.player.has_control = lambda: True
    game.install_decision_providers(roll_reroll_provider=lambda **_kwargs: True)

    mgr = army.thousand_sons_detachments
    assert mgr.warpfire_infusion_start_selection(vehicle, action="shoot", game=game)

    rolls = iter([5, 4])
    monkeypatch.setattr(wargear_mod, "get_roll", lambda _expr: next(rolls))
    monkeypatch.setattr(dice_mod, "get_dice_roll", lambda _faces=6: 6)

    profile = _make_profile(ranged=True, damage="D6")
    attack_instance = {"_aura_attack_mods": _aura_stub()}

    hit = profile._hit_target_with_tracking(
        target,
        vehicle.models[0],
        attack_instance,
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )
    assert int(hit.get("reroll", 0) or 0) == 5
    assert any("Warpfire Infusion" in str(entry) for entry in hit.get("special_effects", []))

    wound = profile._wound_target_with_tracking(
        target,
        vehicle.models[0],
        attack_instance,
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )
    assert int(wound.get("reroll", 0) or 0) == 4
    assert any("Warpfire Infusion" in str(entry) for entry in wound.get("special_effects", []))

    damage = profile._damage_target_with_tracking(
        target.models[0],
        vehicle.models[0],
        {"below_half_distance": False, "mortal_wound": False},
        roll_value=1,
        roll_values=[1],
        allow_rerolls=True,
    )
    assert int(damage.get("reroll", 0) or 0) == 6
    assert any("Warpfire Infusion" in str(entry) for entry in damage.get("special_effects", []))


def test_warpfire_infusion_deadly_demise_triggers_on_five_when_near_psyker(monkeypatch):
    army = Army.with_detachment("Thousand Sons", "Warpforged Cabal")
    army.faction_id = "TS"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    vehicle = _make_unit(
        "Thousand Sons Tank",
        keywords=["THOUSAND SONS", "VEHICLE"],
        faction_keywords=["THOUSAND SONS"],
    )
    psyker = _make_unit(
        "Thousand Sons Psyker",
        keywords=["THOUSAND SONS", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
    )
    army.add_unit(vehicle)
    army.add_unit(psyker)
    _set_location(vehicle, 0.0, 0.0)
    _set_location(psyker, 4.0, 0.0)
    _build_game(army=army, enemy_army=enemy_army, phase_name="SHOOTING_PHASE")

    vehicle.has_deadly_demise = lambda: (True, DiceCollection.from_string("D3"))
    explosions = {"count": 0}

    def _record_explosion(*, damage_dice, position, game_map):
        _ = damage_dice
        _ = position
        _ = game_map
        explosions["count"] += 1

    vehicle._apply_deadly_demise_explosion = _record_explosion
    monkeypatch.setattr(death_mod, "get_roll", lambda _expr: 5)

    vehicle._trigger_deadly_demise(vehicle.models[0], game_map=SimpleNamespace())
    assert int(explosions["count"]) == 1

    explosions["count"] = 0
    _set_location(psyker, 20.0, 0.0)
    vehicle._trigger_deadly_demise(vehicle.models[0], game_map=SimpleNamespace())
    assert int(explosions["count"]) == 0


def test_warpforged_perplexing_cloak_grants_lone_operative_when_nearby_vehicle():
    game, army, _enemy_army, _player, _enemy_player = _build_real_game()

    bearer = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "INFANTRY", "CHARACTER", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
    )
    vehicle = _make_unit(
        "Forgefiend",
        keywords=["THOUSAND SONS", "VEHICLE"],
        faction_keywords=["THOUSAND SONS"],
        wounds="12",
    )
    army.add_unit(bearer)
    army.add_unit(vehicle)
    _apply_enhancement(
        bearer,
        enhancement_id="000010209003",
        enhancement_name="The Perplexing Cloak",
    )
    _set_location(bearer, 0.0, 0.0)
    _set_location(vehicle, 2.0, 0.0)
    game.map.units = [bearer, vehicle]
    game.rebuild_entity_registry()

    assert bearer.has_lone_operative() is True

    _set_location(vehicle, 10.0, 0.0)
    assert bearer.has_lone_operative() is False


def test_warpforged_perplexing_cloak_does_not_grant_lone_operative_to_attached_root():
    game, army, _enemy_army, _player, _enemy_player = _build_real_game()

    bodyguard = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    leader = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "INFANTRY", "CHARACTER", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
    )
    vehicle = _make_unit(
        "Forgefiend",
        keywords=["THOUSAND SONS", "VEHICLE"],
        faction_keywords=["THOUSAND SONS"],
        wounds="12",
    )
    army.add_unit(bodyguard)
    army.add_unit(leader)
    army.add_unit(vehicle)
    _apply_enhancement(
        leader,
        enhancement_id="000010209003",
        enhancement_name="The Perplexing Cloak",
    )
    _attach_leader(bodyguard, leader)
    _set_location(bodyguard, 0.0, 0.0)
    _set_location(leader, 0.0, 0.0)
    _set_location(vehicle, 2.0, 0.0)
    game.map.units = [bodyguard, leader, vehicle]
    game.rebuild_entity_registry()

    assert bodyguard.has_lone_operative() is False
    assert leader.has_lone_operative() is False


def test_warpforged_biomechanical_mutation_queues_and_applies_vehicle_model_repair(monkeypatch):
    game, army, _enemy_army, player, _enemy_player = _build_real_game()
    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0

    bearer = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "INFANTRY", "CHARACTER", "PSYKER"],
        faction_keywords=["THOUSAND SONS"],
    )
    vehicle = _make_unit(
        "Forgefiend",
        keywords=["THOUSAND SONS", "VEHICLE"],
        faction_keywords=["THOUSAND SONS"],
        wounds="12",
    )
    army.add_unit(bearer)
    army.add_unit(vehicle)
    _apply_enhancement(
        bearer,
        enhancement_id="000010209004",
        enhancement_name="Biomechanical Mutation",
    )
    _set_location(bearer, 0.0, 0.0)
    _set_location(vehicle, 2.0, 0.0)
    game.map.units = [bearer, vehicle]
    game.rebuild_entity_registry()

    vehicle_model = vehicle.models[0]
    vehicle_model.wounds = int(vehicle_model.wounds) - 3
    before_wounds = int(vehicle_model.wounds)

    game._on_phase_start_master_of_mechanisms(player=player, phase=game.phase)
    request = _find_master_request(game)
    assert str((request.context or {}).get("ability_name", "") or "") == "Biomechanical Mutation"
    assert str((request.context or {}).get("selection_kind", "") or "") == "model"
    assert bool((request.context or {}).get("target_requires_vehicle", False)) is True
    assert int((request.context or {}).get("range", 0) or 0) == 6

    option = _option_for_model(request, vehicle_model)
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _expr: 2)
    result = resolve_decision_command(game, request, option.option_id, player_id=player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert int(vehicle_model.wounds) == before_wounds + 2


def test_warpforged_runemaster_adds_ritual_range_when_nearby_vehicle(monkeypatch):
    game, army, enemy_army, _player, _enemy_player = _build_real_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    caster = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    caster.possible_abilities = ["Cabal of Sorcerers"]
    vehicle = _make_unit(
        "Forgefiend",
        keywords=["THOUSAND SONS", "VEHICLE"],
        faction_keywords=["THOUSAND SONS"],
        wounds="12",
    )
    target = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army.add_unit(caster)
    army.add_unit(vehicle)
    enemy_army.add_unit(target)
    _apply_enhancement(
        caster,
        enhancement_id="000010209005",
        enhancement_name="Warp-cursed Runemaster",
    )
    _set_location(caster, 0.0, 0.0)
    _set_location(vehicle, 4.0, 0.0)
    _set_location(target, 10.0, 0.0)
    game.map.units = [caster, vehicle, target]
    game.rebuild_entity_registry()

    mgr = army.cabal_of_sorcerers
    monkeypatch.setattr(mgr, "_model_can_see_unit", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(mgr, "_distance_model_to_unit", lambda *_args, **_kwargs: 30.0)
    result = mgr.attempt_ritual(
        game,
        caster_model=caster.models[0],
        ritual_key=RITUAL_DESTINYS_RUIN.key,
        target_unit=target,
        rolls=[1, 2, 3],
        channel_decision=True,
        mortal_roll=0,
    )
    assert bool(result.get("success")) is True
    assert int(result.get("total", 0) or 0) == 6

    _set_location(vehicle, 20.0, 0.0)
    army.cabal_of_sorcerers = type(mgr)(army)
    mgr = army.cabal_of_sorcerers
    monkeypatch.setattr(mgr, "_model_can_see_unit", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(mgr, "_distance_model_to_unit", lambda *_args, **_kwargs: 30.0)
    result = mgr.attempt_ritual(
        game,
        caster_model=caster.models[0],
        ritual_key=RITUAL_DESTINYS_RUIN.key,
        target_unit=target,
        rolls=[1, 2, 3],
        channel_decision=True,
        mortal_roll=0,
    )
    assert bool(result.get("success")) is False
    assert str(result.get("reason", "") or "") == "invalid target"


def test_warpforged_warp_syphon_rerolls_channel_die_and_damages_selected_vehicle(monkeypatch):
    game, army, enemy_army, _player, _enemy_player = _build_real_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.current_player_index = 0

    caster = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    caster.possible_abilities = ["Cabal of Sorcerers"]
    vehicle = _make_unit(
        "Forgefiend",
        keywords=["THOUSAND SONS", "VEHICLE"],
        faction_keywords=["THOUSAND SONS"],
        wounds="12",
    )
    target = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army.add_unit(caster)
    army.add_unit(vehicle)
    enemy_army.add_unit(target)
    _apply_enhancement(
        caster,
        enhancement_id="000010209002",
        enhancement_name="Warp Syphon",
    )
    _set_location(caster, 0.0, 0.0)
    _set_location(vehicle, 4.0, 0.0)
    _set_location(target, 10.0, 0.0)
    game.map.units = [caster, vehicle, target]
    game.rebuild_entity_registry()

    before_wounds = int(vehicle.models[0].wounds)
    mgr = army.cabal_of_sorcerers
    monkeypatch.setattr(mgr, "_model_can_see_unit", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(mgr, "_distance_model_to_unit", lambda *_args, **_kwargs: 10.0)
    result = mgr.attempt_ritual(
        game,
        caster_model=caster.models[0],
        ritual_key=RITUAL_DESTINYS_RUIN.key,
        target_unit=target,
        rolls=[1, 2, 2, 3],
        channel_decision=True,
        mortal_roll=0,
        warp_syphon_target_unit=vehicle,
    )
    assert bool(result.get("success")) is True
    assert bool(result.get("warp_syphon_used")) is True
    assert list(result.get("rolls") or []) == [1, 2, 3]
    assert int(result.get("total", 0) or 0) == 6
    assert int(result.get("warp_syphon_target_mortal_wounds", 0) or 0) == 1
    assert int(vehicle.models[0].wounds) == before_wounds - 1
