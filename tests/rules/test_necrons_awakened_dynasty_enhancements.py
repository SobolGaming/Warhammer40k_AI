from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Necrons",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
    ):
        self.id = ""
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
                "M": "5",
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
    wounds: int = 4,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_unit_location(unit: Unit, *, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]


def _make_profile(*, melee: bool = False, skill: str = "3+"):
    data = {
        "range": "Melee" if melee else "24",
        "A": "1",
        "BS_WS": skill,
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    parent = Wargear({"name": "Test Weapon", "type": "Melee" if melee else "Ranged", **data})
    return parent.profiles["default"]


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    necron_army = Army.with_detachment("Necrons", "Awakened Dynasty")
    necron_army.faction_id = "NEC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    necron_player = Player("Necrons", control=PlayerControl.REMOTE, army=necron_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(necron_player)
    game.add_player(enemy_player)
    game.current_player_index = 1
    game.battle_round_starting_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.FIGHT_PHASE
    necron_army.configure_rule_managers(force=True)
    return game, necron_army, enemy_army, necron_player, enemy_player


def _apply_enhancement(unit: Unit, *, description: str = "") -> None:
    enhancement = Enhancement(
        id="000008372002",
        name="Veil of Darkness",
        faction_id="NEC",
        detachment="Awakened Dynasty",
        points=20,
        description=description
        or (
            "NECRONS model only. Once per battle, at the end of your opponent's turn, if the bearer's unit is not "
            "within Engagement Range of any enemy units, the bearer can use this Enhancement. If it does, remove "
            "that unit from the battlefield. Then, in the Reinforcements step of your next Movement phase, set up "
            'that unit anywhere on the battlefield that is more than 9" horizontally away from all enemy models.'
        ),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _apply_named_enhancement(
    unit: Unit,
    *,
    enhancement_id: str,
    name: str,
    description: str,
    points: int = 20,
) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=name,
        faction_id="NEC",
        detachment="Awakened Dynasty",
        points=points,
        description=description,
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _find_optional_request(game: Game, *, unit: Unit, ability_key: str):
    target_id = str(get_entity_id(unit) or "")
    expected_key = str(ability_key or "").strip().lower()
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CONFIRM_YES_NO:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability_key", "") or "").strip().lower() != expected_key:
            continue
        req_unit_id = str(context.get("unit_id", "") or "")
        if req_unit_id and target_id and req_unit_id != target_id:
            continue
        return request
    return None


def _resolve_yes_option(game: Game, request, *, player_id: str) -> None:
    yes_option_id = ""
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if bool(payload.get("choice", False)):
            yes_option_id = str(getattr(option, "option_id", "") or "")
            break
    assert yes_option_id
    result = resolve_decision_command(game, request, yes_option_id, player_id=player_id)
    assert bool(getattr(result, "ok", False))


def _bearer_model(unit: Unit):
    getter = getattr(unit, "_get_enhancement_bearer_model", None)
    if callable(getter):
        model = getter()
        if model is not None:
            return model
    models = list(getattr(unit, "models", []) or [])
    return models[0] if models else None


def test_awakened_dynasty_veil_of_darkness_descriptor_registered():
    descriptor = get_enhancement_tool_descriptor(enhancement_id="000008372002")
    assert descriptor is not None
    assert str(getattr(descriptor, "name", "") or "") == "Veil of Darkness"
    assert str(getattr(descriptor, "effect", "") or "") == (
        "once_per_battle_end_of_opponent_turn_enter_strategic_reserves_then_next_movement_phase_deep_strike_return"
    )


def test_awakened_dynasty_other_enhancement_descriptors_registered():
    nether_realm = get_enhancement_tool_descriptor(enhancement_id="000008372003")
    assert nether_realm is not None
    assert str(getattr(nether_realm, "name", "") or "") == "Nether-realm Casket"
    assert str(getattr(nether_realm, "effect", "") or "") == "grant_stealth_while_leading"

    phasal = get_enhancement_tool_descriptor(enhancement_id="000008372004")
    assert phasal is not None
    assert str(getattr(phasal, "name", "") or "") == "Phasal Subjugator (Aura)"
    assert str(getattr(phasal, "effect", "") or "") == "aura_friendly_non_character_unit_hit_bonus"
    assert float(phasal.effect_params.get("range_inches", 0.0) or 0.0) == 6.0
    assert int(phasal.effect_params.get("hit_roll_bonus", 0) or 0) == 1


def test_veil_of_darkness_prompts_enters_reserves_and_sets_next_movement_return_window():
    game, necron_army, enemy_army, necron_player, enemy_player = _build_game()
    source = _make_unit(
        "Necron Overlord",
        keywords=["CHARACTER", "INFANTRY", "NECRONS"],
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
    _set_unit_location(enemy, x=20.0, y=0.0)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(source)
    game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)

    request = _find_optional_request(game, unit=source, ability_key="veil_of_darkness")
    assert request is not None
    _resolve_yes_option(game, request, player_id=necron_player.id)

    assert bool(source.is_in_strategic_reserves())
    assert source not in list(getattr(game.map, "units", []) or [])
    assert bool(source.has_used_unit_once_per_battle("veil_of_darkness"))

    sr = dict(getattr(source, "special_rules", {}) or {})
    assert bool(sr.get("umbralefic_crystal_temp_deep_strike"))
    assert str(sr.get("umbralefic_crystal_must_arrive_turn_owner", "") or "") == str(necron_player.id or "")
    arrival_turn = int(sr.get("umbralefic_crystal_must_arrive_turn", 0) or 0)
    assert arrival_turn >= int(getattr(game, "turn", 0) or 0)

    game.turn = int(arrival_turn)
    game.current_player_index = 0
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    assert bool(source.has_deep_strike())
    assert bool(source.can_arrive_from_reserves(game.turn))

    game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
    assert _find_optional_request(game, unit=source, ability_key="veil_of_darkness") is None


def test_veil_of_darkness_does_not_prompt_when_bearer_destroyed():
    game, necron_army, enemy_army, _necron_player, enemy_player = _build_game()
    source = _make_unit(
        "Necron Overlord with Guard",
        keywords=["CHARACTER", "INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
        model_count=2,
        wounds=4,
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
    _set_unit_location(enemy, x=20.0, y=0.0)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(source)
    bearer = _bearer_model(source)
    assert bearer is not None
    bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)

    game._maybe_prompt_end_of_opponent_turn_strategic_reserves(turn_ending_player=enemy_player)
    assert _find_optional_request(game, unit=source, ability_key="veil_of_darkness") is None


def test_nether_realm_casket_grants_stealth_while_bearer_is_leading_and_alive():
    necron_army = Army.with_detachment("Necrons", "Awakened Dynasty")
    necron_army.faction_id = "NEC"

    bodyguard = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY", "BATTLELINE", "NECRONS"],
        faction_keywords=["NECRONS"],
    )
    leader = _make_unit(
        "Necron Overlord",
        keywords=["CHARACTER", "INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
    )
    necron_army.add_unit(bodyguard)
    necron_army.add_unit(leader)
    _attach_leader(bodyguard, leader)

    _apply_named_enhancement(
        leader,
        enhancement_id="000008372003",
        name="Nether-realm Casket",
        description="NECRONS model only. While the bearer is leading a unit, models in that unit have the Stealth ability.",
    )

    assert bodyguard.has_stealth() is True

    bearer = _bearer_model(leader)
    assert bearer is not None
    bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0))

    assert bodyguard.has_stealth() is False


def test_phasal_subjugator_aura_grants_hit_bonus_only_to_nearby_non_character_necron_units():
    game, necron_army, enemy_army, _necron_player, _enemy_player = _build_game()
    aura_bearer = _make_unit(
        "Necron Overlord",
        keywords=["CHARACTER", "INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
    )
    attacker = _make_unit(
        "Necron Warriors",
        keywords=["INFANTRY", "BATTLELINE", "NECRONS"],
        faction_keywords=["NECRONS"],
    )
    character_attacker = _make_unit(
        "Royal Warden",
        keywords=["CHARACTER", "INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
    )
    far_attacker = _make_unit(
        "Immortals",
        keywords=["INFANTRY", "NECRONS"],
        faction_keywords=["NECRONS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    necron_army.add_unit(aura_bearer)
    necron_army.add_unit(attacker)
    necron_army.add_unit(character_attacker)
    necron_army.add_unit(far_attacker)
    enemy_army.add_unit(enemy)

    _apply_named_enhancement(
        aura_bearer,
        enhancement_id="000008372004",
        name="Phasal Subjugator (Aura)",
        description=(
            'NECRONS model only. While a friendly NECRONS unit (excluding CHARACTER units) is within 6" of the bearer, '
            "each time a model in that unit makes an attack, add 1 to the Hit roll."
        ),
        points=35,
    )

    _set_unit_location(aura_bearer, x=0.0, y=0.0)
    _set_unit_location(attacker, x=5.0, y=0.0)
    _set_unit_location(character_attacker, x=5.0, y=2.0)
    _set_unit_location(far_attacker, x=7.5, y=0.0)
    _set_unit_location(enemy, x=20.0, y=0.0)
    game.map.units = [aura_bearer, attacker, character_attacker, far_attacker, enemy]
    game.rebuild_entity_registry()

    profile = _make_profile(skill="3+")

    buffed_hit = profile._hit_target_with_tracking(
        enemy,
        attacker.models[0],
        {},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(buffed_hit.get("hit"))
    assert int(buffed_hit.get("final_needed", 0) or 0) == 2
    assert any("Phasal Subjugator" in str(reason or "") for reason in list(buffed_hit.get("modifiers", []) or []))

    character_hit = profile._hit_target_with_tracking(
        enemy,
        character_attacker.models[0],
        {},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not bool(character_hit.get("hit"))
    assert int(character_hit.get("final_needed", 0) or 0) == 3

    far_hit = profile._hit_target_with_tracking(
        enemy,
        far_attacker.models[0],
        {},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not bool(far_hit.get("hit"))
    assert int(far_hit.get("final_needed", 0) or 0) == 3

    bearer = _bearer_model(aura_bearer)
    assert bearer is not None
    bearer.take_damage(int(getattr(bearer, "wounds", 0) or 0), game_map=game.map)

    expired_hit = profile._hit_target_with_tracking(
        enemy,
        attacker.models[0],
        {},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not bool(expired_hit.get("hit"))
    assert int(expired_hit.get("final_needed", 0) or 0) == 3
