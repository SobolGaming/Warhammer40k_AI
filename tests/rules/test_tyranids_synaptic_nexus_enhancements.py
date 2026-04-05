from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_handlers.abilities import _apply_choose_quarry, _validate_choose_quarry
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT, DECISION_SELECT_UNIT
from warhammer40k_ai.engine.decision_requests import build_select_unit_request
from warhammer40k_ai.engine.decisions import DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game_mixins.setup_deployment_reserves_mixin import GameSetupDeploymentReservesMixin
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.aura_effects import get_enemy_aura_leadership_characteristic_penalty
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Tyranids",
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        wounds: int = 4,
        model_count: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["TYRANIDS"] if faction_name == "Tyranids" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": str(int(toughness)),
                "Sv": "4",
                "W": str(int(wounds)),
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
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Tyranids",
    keywords=None,
    faction_keywords=None,
    toughness: int = 4,
    wounds: int = 4,
    model_count: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            wounds=wounds,
            model_count=model_count,
        )
    )


def _apply_enhancement(unit: Unit, *, enhancement_id: str, name: str) -> None:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(name),
        faction_id="TYR",
        detachment="Synaptic Nexus",
        points=20,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _make_ranged_profile(*, strength: int = 4, ap: int = 0, psychic: bool = False) -> WargearProfile:
    parent = type(
        "_ParentWargear",
        (),
        {
            "name": "Psychic Bio-weapon" if psychic else "Bio-weapon",
            "is_melee": staticmethod(lambda: False),
            "is_ranged": staticmethod(lambda: True),
        },
    )()
    return WargearProfile(
        "default",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": str(int(ap)),
            "D": "1",
            "description": "[PSYCHIC]" if psychic else "",
        },
        parent_wargear=parent,
    )


def _bearer_and_other_models(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    bearer = None
    other = None
    for model in list(getattr(unit, "models", []) or []):
        model_ids = {
            str(get_entity_id(model) or "").strip(),
            str(getattr(model, "id", getattr(model, "_id", "")) or "").strip(),
        }
        if bearer_id and bearer_id in model_ids:
            bearer = model
        elif other is None:
            other = model
    return bearer, other


class _AuraMap:
    def __init__(self, *, enemy_units):
        self._enemy_units = list(enemy_units or [])

    def get_enemy_units(self, _unit):
        return list(self._enemy_units)


class _DecisionQueueStub:
    def __init__(self) -> None:
        self._requests: list[DecisionRequest] = []

    def list(self):
        return list(self._requests)

    def append(self, request: DecisionRequest) -> None:
        self._requests.append(request)


class _ReinforcementsGame(GameSetupDeploymentReservesMixin):
    def __init__(self, *, players, current_player) -> None:
        self.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        self.turn = 2
        self.is_authoritative = True
        self.decision_queue = _DecisionQueueStub()
        self.queued_requests: list[DecisionRequest] = []
        self.players = list(players)
        self.reinforcements_step_active = True
        self.reinforcements_step_player_id = str(getattr(current_player, "id", "") or "")
        self.reinforcements_step_turn = 2
        self._reinforcements_step_skipped_ids = set()
        self._current_player = current_player
        for player in self.players:
            player.game = self

    def get_current_player(self):
        return self._current_player

    def request_decision(self, request: DecisionRequest) -> None:
        self.queued_requests.append(request)
        self.decision_queue.append(request)

    def get_units_in_reserves(self, player):
        return [
            unit
            for unit in list(getattr(getattr(player, "army", None), "units", []) or [])
            if str(getattr(unit, "reserve_status", "") or "").strip().lower() in {"reserves", "strategic_reserves"}
        ]

    def get_units_that_can_arrive_from_reserves(self, player):
        units = []
        for unit in list(self.get_units_in_reserves(player) or []):
            can_arrive = getattr(unit, "can_arrive_from_reserves", None)
            if callable(can_arrive) and not bool(can_arrive(self.turn)):
                continue
            units.append(unit)
        return units

    def get_units_that_must_arrive_from_reserves(self, player):
        units = []
        for unit in list(self.get_units_in_reserves(player) or []):
            must_arrive = getattr(unit, "must_arrive_from_reserves", None)
            if callable(must_arrive) and bool(must_arrive(self.turn)):
                units.append(unit)
        return units

    def get_enemy_units(self, player):
        units = []
        for candidate in list(self.players or []):
            if candidate is None or candidate is player:
                continue
            units.extend(list(getattr(getattr(candidate, "army", None), "units", []) or []))
        return units


def _build_reinforcements_game():
    tyr_army = Army("Tyranids", "Synaptic Nexus")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    tyr_player = Player("Tyranids", control=PlayerControl.REMOTE, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)

    source = _make_unit(
        "Hive Tyrant",
        keywords=["TYRANIDS", "MONSTER", "CHARACTER", "PSYKER", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
    )
    first_arrival = _make_unit(
        "Termagants",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    second_arrival = _make_unit(
        "Hormagaunts",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(source)
    enemy_army.add_unit(first_arrival)
    enemy_army.add_unit(second_arrival)

    source.deployed = True
    source.reserve_status = "deployed"
    source.embarked_in = None
    first_arrival.deployed = True
    first_arrival.reserve_status = "strategic_reserves"
    first_arrival.embarked_in = None
    second_arrival.deployed = True
    second_arrival.reserve_status = "reserves"
    second_arrival.embarked_in = None

    _apply_enhancement(source, enhancement_id="000008421003", name="Psychostatic Disruption")
    game = _ReinforcementsGame(players=[tyr_player, enemy_player], current_player=enemy_player)
    return game, tyr_player, enemy_player, source, first_arrival, second_arrival


def _find_choice_request(game: _ReinforcementsGame) -> DecisionRequest:
    for request in list(game.queued_requests or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") == "psychostatic_disruption":
            return request
    raise AssertionError("Psychostatic Disruption request was not queued.")


def _skip_option(request: DecisionRequest):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "") == "skip":
            return option
    raise AssertionError("Skip option not found.")


def _source_option(request: DecisionRequest, *, source_member_unit_id: str):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("source_member_unit_id", "") or "") == str(source_member_unit_id):
            return option
    raise AssertionError("Source option not found.")


def test_synaptic_nexus_enhancement_descriptors_exist():
    expected = {
        "000008421002": ("Power of the Hive Mind", "bearer_psychic_strength_and_ap_bonus"),
        "000008421003": (
            "Psychostatic Disruption",
            "reserves_denial_aura_and_once_per_battle_strategic_reserves_arrival_cancel",
        ),
        "000008421004": ("Synaptic Control", "bearer_incoming_damage_modifier"),
        "000008421005": ("The Dirgeheart of Kharis (Aura)", "enemy_leadership_characteristic_penalty_aura"),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
        assert str(getattr(desc, "effect", "") or "") == effect


def test_power_of_the_hive_mind_applies_only_to_bearers_psychic_weapons():
    army = Army("Tyranids", "Synaptic Nexus")
    army.faction_id = "TYR"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    source = _make_unit(
        "Neurotyrant",
        keywords=["TYRANIDS", "INFANTRY", "CHARACTER", "PSYKER", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
        toughness=5,
        model_count=2,
    )
    target = _make_unit(
        "Enemy Target",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness=5,
    )
    army.add_unit(source)
    enemy_army.add_unit(target)

    _apply_enhancement(source, enhancement_id="000008421002", name="Power of the Hive Mind")

    bearer, other = _bearer_and_other_models(source)
    assert bearer is not None
    assert other is not None

    psychic_profile = _make_ranged_profile(strength=4, ap=0, psychic=True)
    mundane_profile = _make_ranged_profile(strength=4, ap=0, psychic=False)

    assert int(psychic_profile.get_effective_ap(bearer, target)) == -1
    assert int(psychic_profile.get_effective_ap(other, target)) == 0
    assert int(mundane_profile.get_effective_ap(bearer, target)) == 0

    bearer_wound = psychic_profile._wound_target_with_tracking(
        target,
        bearer,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    other_wound = psychic_profile._wound_target_with_tracking(
        target,
        other,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(bearer_wound["needed"]) == 4
    assert int(other_wound["needed"]) == 5


def test_dirgeheart_of_kharis_applies_enemy_leadership_penalty_within_range_only():
    army = Army("Tyranids", "Synaptic Nexus")
    army.faction_id = "TYR"
    source = _make_unit(
        "Neurotyrant",
        keywords=["TYRANIDS", "INFANTRY", "CHARACTER", "SYNAPSE"],
        faction_keywords=["TYRANIDS"],
    )
    target = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    army.add_unit(source)
    _apply_enhancement(source, enhancement_id="000008421005", name="The Dirgeheart of Kharis (Aura)")
    game_map = _AuraMap(enemy_units=[source])

    with patch("warhammer40k_ai.utility.aura_effects.model_within_range_of_unit", return_value=True):
        assert get_enemy_aura_leadership_characteristic_penalty(target, game_map=game_map) == 1
    with patch("warhammer40k_ai.utility.aura_effects.model_within_range_of_unit", return_value=False):
        assert get_enemy_aura_leadership_characteristic_penalty(target, game_map=game_map) == 0


def test_psychostatic_disruption_registers_reserves_denial_range_only_while_bearer_alive():
    game, _tyr_player, _enemy_player, source, _first_arrival, _second_arrival = _build_reinforcements_game()

    ranges = game._reserves_denial_ranges_for_unit(source)
    psychostatic = [entry for entry in list(ranges or []) if str(entry.get("source", "") or "") == "Psychostatic Disruption"]
    assert len(psychostatic) == 1
    assert float(psychostatic[0]["range"]) == 12.0

    bearer, _other = _bearer_and_other_models(source)
    assert bearer is not None
    bearer.wounds = 0

    ranges_after_death = game._reserves_denial_ranges_for_unit(source)
    psychostatic_after_death = [
        entry for entry in list(ranges_after_death or []) if str(entry.get("source", "") or "") == "Psychostatic Disruption"
    ]
    assert psychostatic_after_death == []


def test_psychostatic_disruption_queues_choose_quarry_before_arrival_move():
    game, tyr_player, _enemy_player, source, first_arrival, _second_arrival = _build_reinforcements_game()
    request = build_select_unit_request(
        [first_arrival],
        player_id=game.get_current_player().id,
        phase_name="MOVEMENT_PHASE",
        phase_step="REINFORCEMENTS",
        selection_purpose="ACTIVATE_REINFORCEMENT_UNIT",
        allow_pass=True,
    )
    assert request is not None

    game.on_select_unit_resolved(
        request=request,
        selected_unit_id=str(get_entity_id(first_arrival) or ""),
        selected_unit=first_arrival,
        payload={"unit_id": str(get_entity_id(first_arrival) or "")},
        pass_selected=False,
    )

    assert len(game.queued_requests) == 1
    queued = game.queued_requests[0]
    assert str(queued.decision_type) == DECISION_CHOOSE_QUARRY
    assert str(queued.player_id) == str(tyr_player.id)
    assert str(queued.context.get("ability", "") or "") == "psychostatic_disruption"

    source_option = _source_option(queued, source_member_unit_id=str(get_entity_id(source) or ""))
    assert str((source_option.payload or {}).get("arriving_unit_id", "") or "") == str(get_entity_id(first_arrival) or "")


def test_psychostatic_disruption_skip_continues_with_reserves_arrival_request():
    game, _tyr_player, _enemy_player, _source, first_arrival, _second_arrival = _build_reinforcements_game()
    initial_request = build_select_unit_request(
        [first_arrival],
        player_id=game.get_current_player().id,
        phase_name="MOVEMENT_PHASE",
        phase_step="REINFORCEMENTS",
        selection_purpose="ACTIVATE_REINFORCEMENT_UNIT",
        allow_pass=True,
    )
    assert initial_request is not None
    game.on_select_unit_resolved(
        request=initial_request,
        selected_unit_id=str(get_entity_id(first_arrival) or ""),
        selected_unit=first_arrival,
        payload={"unit_id": str(get_entity_id(first_arrival) or "")},
        pass_selected=False,
    )
    request = _find_choice_request(game)
    option = _skip_option(request)
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=request.player_id,
        option_id=option.option_id,
    )

    assert _validate_choose_quarry(game, request, result) == ()
    outcome = _apply_choose_quarry(game, request, result)

    assert bool(outcome.get("queued_arrival_request", False))
    assert str(game.queued_requests[-1].decision_type) == DECISION_MOVE_UNIT
    assert str(game.queued_requests[-1].context.get("placement_kind", "") or "") == "reserves_arrival"


def test_psychostatic_disruption_success_prevents_arrival_and_requeues_selection():
    game, _tyr_player, _enemy_player, source, first_arrival, second_arrival = _build_reinforcements_game()
    initial_request = build_select_unit_request(
        [first_arrival],
        player_id=game.get_current_player().id,
        phase_name="MOVEMENT_PHASE",
        phase_step="REINFORCEMENTS",
        selection_purpose="ACTIVATE_REINFORCEMENT_UNIT",
        allow_pass=True,
    )
    assert initial_request is not None
    game.on_select_unit_resolved(
        request=initial_request,
        selected_unit_id=str(get_entity_id(first_arrival) or ""),
        selected_unit=first_arrival,
        payload={"unit_id": str(get_entity_id(first_arrival) or "")},
        pass_selected=False,
    )
    request = _find_choice_request(game)
    option = _source_option(request, source_member_unit_id=str(get_entity_id(source) or ""))
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=request.player_id,
        option_id=option.option_id,
    )

    assert _validate_choose_quarry(game, request, result) == ()
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
        outcome = _apply_choose_quarry(game, request, result)

    assert bool(outcome.get("prevented", False))
    assert bool(source.has_used_unit_once_per_battle("psychostatic_disruption"))
    assert str(game.queued_requests[-1].decision_type) == DECISION_SELECT_UNIT
    assert game.queued_requests[-1].context["allowed_unit_ids"] == [str(get_entity_id(second_arrival) or "")]


def test_psychostatic_disruption_failed_roll_allows_arrival_request():
    game, _tyr_player, _enemy_player, source, first_arrival, _second_arrival = _build_reinforcements_game()
    initial_request = build_select_unit_request(
        [first_arrival],
        player_id=game.get_current_player().id,
        phase_name="MOVEMENT_PHASE",
        phase_step="REINFORCEMENTS",
        selection_purpose="ACTIVATE_REINFORCEMENT_UNIT",
        allow_pass=True,
    )
    assert initial_request is not None
    game.on_select_unit_resolved(
        request=initial_request,
        selected_unit_id=str(get_entity_id(first_arrival) or ""),
        selected_unit=first_arrival,
        payload={"unit_id": str(get_entity_id(first_arrival) or "")},
        pass_selected=False,
    )
    request = _find_choice_request(game)
    option = _source_option(request, source_member_unit_id=str(get_entity_id(source) or ""))
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=request.player_id,
        option_id=option.option_id,
    )

    assert _validate_choose_quarry(game, request, result) == ()
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
        outcome = _apply_choose_quarry(game, request, result)

    assert bool(outcome.get("used", False))
    assert not bool(outcome.get("prevented", False))
    assert bool(source.has_used_unit_once_per_battle("psychostatic_disruption"))
    assert str(game.queued_requests[-1].decision_type) == DECISION_MOVE_UNIT
    assert str(game.queued_requests[-1].context.get("placement_kind", "") or "") == "reserves_arrival"
