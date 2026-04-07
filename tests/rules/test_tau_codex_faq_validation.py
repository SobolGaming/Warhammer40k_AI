from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, BattleRoundPhases, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.calcs import get_pivot_cost
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Enemy",
        keywords=None,
        faction_keywords=None,
    ) -> None:
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [str(faction_name or "").upper()])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
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
        self.attached_to_names = []


def _make_tau_unit(name: str) -> Unit:
    datasheet = _WAHA.get_datasheet(name, faction_id="TAU")
    assert datasheet is not None
    unit = Unit(datasheet)
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _make_mock_unit(
    name: str,
    *,
    faction_name: str = "Enemy",
    keywords=None,
    faction_keywords=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _grant_ranged_profile(unit: Unit, *, range_val: str) -> None:
    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    profile = WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": str(range_val),
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )
    wargear = SimpleNamespace(
        id=f"wargear:{getattr(unit, 'id', getattr(unit, '_id', 'unit'))}:test_gun",
        name="Test Gun",
        is_ranged=lambda: True,
        is_melee=lambda: False,
        profiles={"default": profile},
    )
    for model in list(getattr(unit, "models", []) or []):
        model.wargear = [wargear]


def _build_game(*, detachment: str) -> tuple[Game, Player, Player]:
    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    tau_army = Army.with_detachment("T'au Empire", detachment)
    tau_army.faction_id = "TAU"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tau_player = Player("TAU", control=PlayerControl.LOCAL, army=tau_army)
    enemy_player = Player("EN", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tau_player)
    game.add_player(enemy_player)
    game.turn = 1
    tau_player.command_points = 10
    enemy_player.command_points = 10
    tau_army.configure_rule_managers(force=True)
    tau_player.stratagems.refresh_available()
    return game, tau_player, enemy_player


def _set_unit_location(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_reaction_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _find_guns_blazing_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_DECLARE_SHOTS:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if bool(context.get("guns_blazing_flow", False)):
            return request
    return None


def _destroy_bodyguard_unit(bodyguard: Unit, *, game_map, destroyed_by_unit: Unit | None = None) -> None:
    bodyguard._last_destroyed_by_unit = destroyed_by_unit
    if destroyed_by_unit is not None and list(getattr(destroyed_by_unit, "models", []) or []):
        bodyguard._last_destroyed_by_model = destroyed_by_unit.models[0]
    bodyguard.begin_attack_resolution()
    for model in list(getattr(bodyguard, "models", []) or []):
        bodyguard.remove_model(model, game_map=game_map)
    bodyguard.end_attack_resolution(game_map=game_map)


def test_tau_crisis_battlesuit_flying_stem_pivot_value_is_zero():
    crisis = _make_tau_unit("Crisis Fireknife Battlesuits")

    assert get_pivot_cost(crisis) == 0

    for model in list(getattr(crisis, "models", []) or []):
        model.model_base.is_flying_base = True

    assert get_pivot_cost(crisis) == 0


def test_join_the_hunt_queues_for_destroyed_bodyguard_unit():
    game, tau_player, enemy_player = _build_game(detachment="Kroot Hunting Pack")
    tau_army = tau_player.army
    enemy_army = enemy_player.army

    bodyguard = _make_tau_unit("Kroot Carnivores")
    war_shaper = _make_tau_unit("Kroot War Shaper")
    enemy = _make_tau_unit("Strike Team")

    tau_army.add_unit(bodyguard)
    tau_army.add_unit(war_shaper)
    enemy_army.add_unit(enemy)
    war_shaper.attach_to_unit(bodyguard)

    _set_unit_location(bodyguard, 10.0, 10.0)
    _set_unit_location(war_shaper, 10.0, 10.0)
    _set_unit_location(enemy, 18.0, 10.0)
    game.map.units = [bodyguard, enemy]
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    _destroy_bodyguard_unit(bodyguard, game_map=game.map, destroyed_by_unit=enemy)

    pending = _pending_reaction_by_name(tau_player.stratagems, "JOIN THE HUNT")
    assert pending is not None

    join_the_hunt = tau_player.stratagems.get_by_name("JOIN THE HUNT")
    assert join_the_hunt is not None

    existing_ids = {id(unit) for unit in list(tau_army.units or [])}
    before_cp = int(tau_player.command_points or 0)
    assert tau_player.stratagems.use(
        "JOIN THE HUNT",
        destroyed_unit=bodyguard,
        phase_name="Fight phase",
        dequeue=True,
    )

    assert int(tau_player.command_points or 0) == before_cp - int(join_the_hunt.cp_cost or 0)
    replacements = [
        unit
        for unit in list(tau_army.units or [])
        if id(unit) not in existing_ids and str(getattr(unit, "name", "") or "") == str(getattr(bodyguard, "name", "") or "")
    ]
    assert len(replacements) == 1
    replacement = replacements[0]
    assert str(getattr(replacement, "reserve_status", "") or "") == "strategic_reserves"
    assert bool(replacement.is_in_reserves())
    assert int(getattr(replacement, "starting_model_count", 0) or 0) == int(getattr(bodyguard, "starting_model_count", 0) or 0)


def test_join_the_hunt_preview_ignores_war_leader_discount_for_destroyed_attached_bodyguard():
    game, tau_player, _enemy_player = _build_game(detachment="Kroot Hunting Pack")
    tau_army = tau_player.army

    bodyguard = _make_tau_unit("Kroot Carnivores")
    war_shaper = _make_tau_unit("Kroot War Shaper")
    tau_army.add_unit(bodyguard)
    tau_army.add_unit(war_shaper)
    war_shaper.attach_to_unit(bodyguard)
    game.rebuild_entity_registry()

    bodyguard.models = []

    join_the_hunt = tau_player.stratagems.get_by_name("JOIN THE HUNT")
    assert join_the_hunt is not None

    preview = tau_player.preview_stratagem_cp_cost(
        join_the_hunt,
        target_unit=bodyguard,
        assume_optional_discounts=True,
    )

    assert int(preview.get("discount", 0) or 0) == 0
    assert int(preview.get("cost", 0) or 0) == int(join_the_hunt.cp_cost or 0)


def test_hidden_hunters_prevents_kroot_packmates_when_target_becomes_ineligible():
    game, tau_player, enemy_player = _build_game(detachment="Kroot Hunting Pack")
    tau_army = tau_player.army
    enemy_army = enemy_player.army

    defender = _make_tau_unit("Kroot Carnivores")
    riders = _make_tau_unit("Krootox Riders")
    attacker = _make_mock_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    _grant_ranged_profile(attacker, range_val="24")

    tau_army.add_unit(defender)
    tau_army.add_unit(riders)
    enemy_army.add_unit(attacker)

    _set_unit_location(defender, 0.0, 0.0)
    _set_unit_location(riders, -6.0, 0.0)
    _set_unit_location(attacker, 23.0, 0.0)
    game.map.units = [defender, riders, attacker]
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defender])

    pending = _pending_reaction_by_name(tau_player.stratagems, "HIDDEN HUNTERS")
    assert pending is not None
    assert tau_player.stratagems.use("HIDDEN HUNTERS", unit=defender, phase_name="Shooting phase", dequeue=True)

    game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker, hits_by_target={})

    assert _find_guns_blazing_request(game) is None


def test_ethereal_with_marker_drone_cannot_observe_solo_but_attached_bodyguard_can():
    game, tau_player, enemy_player = _build_game(detachment="Kauyon")
    tau_army = tau_player.army
    enemy_army = enemy_player.army
    ftgg = tau_army.for_the_greater_good

    solo_ethereal = _make_tau_unit("Ethereal")
    solo_ethereal.models[0].optional_wargear.append("Marker Drone")
    bodyguard = _make_tau_unit("Breacher Team")
    attached_ethereal = _make_tau_unit("Ethereal")
    attached_ethereal.models[0].optional_wargear.append("Marker Drone")
    bodyguard.attached_leaders = [attached_ethereal]
    attached_ethereal.attached_to = bodyguard
    enemy_a = _make_tau_unit("Strike Team")
    enemy_b = _make_tau_unit("Strike Team")

    tau_army.add_unit(solo_ethereal)
    tau_army.add_unit(bodyguard)
    tau_army.add_unit(attached_ethereal)
    enemy_army.add_unit(enemy_a)
    enemy_army.add_unit(enemy_b)

    bodyguard.deployed = True
    attached_ethereal.deployed = True
    _set_unit_location(solo_ethereal, 0.0, 0.0)
    _set_unit_location(bodyguard, 6.0, 0.0)
    _set_unit_location(attached_ethereal, 6.0, 0.0)
    _set_unit_location(enemy_a, 20.0, 0.0)
    _set_unit_location(enemy_b, 22.0, 4.0)
    game.map.units = [solo_ethereal, bodyguard, enemy_a, enemy_b]
    game.rebuild_entity_registry()

    assert ftgg.mark_spotted(solo_ethereal, enemy_a, game=game, player=tau_player) is False
    assert ftgg.mark_spotted(bodyguard, enemy_b, game=game, player=tau_player) is True


def test_ethereal_coordinated_leadership_does_not_gain_cp_while_embarked():
    game, tau_player, _enemy_player = _build_game(detachment="Kauyon")
    ethereal = _make_tau_unit("Ethereal")
    tau_player.army.add_unit(ethereal)
    game.rebuild_entity_registry()

    ethereal.embarked_in = object()
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0

    before_cp = int(tau_player.command_points or 0)
    with patch("warhammer40k_ai.engine.game_mixins.phase_handlers_mixin.get_roll", return_value=4):
        game._on_phase_end_leadership_cp_gain(player=tau_player, phase=game.phase)

    assert int(tau_player.command_points or 0) == before_cp
