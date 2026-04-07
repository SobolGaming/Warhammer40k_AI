from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.space_marines_primarch_of_the_first_legion import (
    KEY_MARTIAL_EXEMPLAR,
    KEY_MIST_WREATHED_SHADOW_REALMS,
    KEY_NO_HIDING_FROM_THE_WATCHERS,
    get_active_primarch_of_the_first_legion_keys,
    set_active_primarch_of_the_first_legion,
)
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.aura_effects import get_aura_attack_modifiers
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


PRIMARCH_OF_THE_FIRST_LEGION_TEXT = (
    "At the start of your Command phase, select two Primarch of the First Legion abilities. "
    "Until the start of your next Command phase, this model has those abilities."
)
MIST_WREATHED_SHADOW_REALMS_TEXT = (
    "In your Command phase, if this unit is not within Engagement Range of one or more enemy units, "
    "you can remove it from the battlefield and place it into Strategic Reserves."
)
MARTIAL_EXEMPLAR_TEXT = (
    "While a friendly ADEPTUS ASTARTES unit is within 6\" of this model, each time a model in that unit "
    "makes a melee attack, re-roll a Hit roll of 1 and re-roll a Wound roll of 1."
)
NO_HIDING_FROM_THE_WATCHERS_TEXT = (
    "While a friendly ADEPTUS ASTARTES unit is within 6\" of this model, models in that unit have the Feel "
    "No Pain 4+ ability against mortal wounds."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        abilities=None,
        wounds: int = 10,
    ) -> None:
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 300}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": "8",
                "Sv": "2",
                "W": str(int(wounds)),
                "Ld": "5",
                "OC": "4",
                "base_size": "60mm",
                "inv_sv": "4",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _ability(name: str, description: str) -> dict:
    return {"name": name, "description": description, "type": "Datasheet", "parameter": ""}


def _make_unit(
    name: str,
    *,
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    abilities=None,
    wounds: int = 10,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            wounds=wounds,
        )
    )


def _lion_abilities() -> list[dict]:
    return [
        _ability("Primarch of the First Legion", PRIMARCH_OF_THE_FIRST_LEGION_TEXT),
        _ability("Mist-wreathed Shadow Realms", MIST_WREATHED_SHADOW_REALMS_TEXT),
        _ability("Martial Exemplar (Aura)", MARTIAL_EXEMPLAR_TEXT),
        _ability("No Hiding From the Watchers (Aura)", NO_HIDING_FROM_THE_WATCHERS_TEXT),
    ]


def _build_game() -> tuple[Game, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    sm_army = Army.with_detachment("Space Marines", "Detachment")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Detachment")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, sm_player, enemy_player


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _find_request(game: Game, decision_type: str, *, ability: str | None = None):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != decision_type:
            continue
        if ability is None:
            return request
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == ability:
            return request
    return None


def _find_option_id_for_choice_keys(request, keys: tuple[str, str]) -> str:
    expected = list(keys)
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if list(payload.get("choice_keys", []) or []) == expected:
            return str(getattr(option, "option_id", "") or "")
    raise AssertionError(f"Unable to find option for choice keys: {expected}")


def _find_yes_no_option_id(request, *, choice: bool) -> str:
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if bool(payload.get("choice", False)) is bool(choice):
            return str(getattr(option, "option_id", "") or "")
    raise AssertionError(f"Unable to find yes/no option for choice={choice}")


def test_primarch_of_the_first_legion_manager_requests_pair_choice_in_command_phase() -> None:
    game, player, _enemy = _build_game()
    game.turn = 2
    lion = _make_unit(
        "Lion El'Jonson",
        keywords=["CHARACTER", "MONSTER"],
        faction_keywords=["ADEPTUS ASTARTES", "DARK ANGELS"],
        abilities=_lion_abilities(),
    )
    player.army.add_unit(lion)
    _deploy_unit(game, lion, 10.0, 10.0)

    mgr = getattr(player.army, "primarch_of_the_first_legion", None)
    assert mgr is not None

    mgr.on_command_phase_start(player, game=game)

    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="primarch_of_the_first_legion")
    assert request is not None
    assert len(list(request.options or [])) == 3
    assert int((request.context or {}).get("battle_round", 0) or 0) == 2


def test_only_selected_primarch_sub_abilities_are_active_after_decision() -> None:
    game, player, _enemy = _build_game()
    lion = _make_unit(
        "Lion El'Jonson",
        keywords=["CHARACTER", "MONSTER"],
        faction_keywords=["ADEPTUS ASTARTES", "DARK ANGELS"],
        abilities=_lion_abilities(),
    )
    player.army.add_unit(lion)
    _deploy_unit(game, lion, 10.0, 10.0)

    mgr = getattr(player.army, "primarch_of_the_first_legion", None)
    mgr.on_command_phase_start(player, game=game)
    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="primarch_of_the_first_legion")
    assert request is not None

    mist = next(ab for ab in list(lion.possible_abilities or []) if getattr(ab, "name", "") == "Mist-wreathed Shadow Realms")
    martial = next(ab for ab in list(lion.possible_abilities or []) if getattr(ab, "name", "") == "Martial Exemplar (Aura)")
    watchers = next(
        ab for ab in list(lion.possible_abilities or []) if getattr(ab, "name", "") == "No Hiding From the Watchers (Aura)"
    )
    assert lion._ability_is_active(mist) is False
    assert lion._ability_is_active(martial) is False
    assert lion._ability_is_active(watchers) is False

    option_id = _find_option_id_for_choice_keys(
        request,
        (KEY_MIST_WREATHED_SHADOW_REALMS, KEY_MARTIAL_EXEMPLAR),
    )
    resolve_decision_command(game, request, option_id, player_id=player.id)

    assert get_active_primarch_of_the_first_legion_keys(lion, game=game) == (
        KEY_MIST_WREATHED_SHADOW_REALMS,
        KEY_MARTIAL_EXEMPLAR,
    )
    assert lion._ability_is_active(mist) is True
    assert lion._ability_is_active(martial) is True
    assert lion._ability_is_active(watchers) is False


def test_martial_exemplar_aura_requires_selection() -> None:
    game, player, enemy_player = _build_game()
    lion = _make_unit(
        "Lion El'Jonson",
        keywords=["CHARACTER", "MONSTER"],
        faction_keywords=["ADEPTUS ASTARTES", "DARK ANGELS"],
        abilities=_lion_abilities(),
    )
    nearby = _make_unit(
        "Bladeguard Veterans",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    player.army.add_unit(lion)
    player.army.add_unit(nearby)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(game, lion, 10.0, 10.0)
    _deploy_unit(game, nearby, 13.0, 10.0)
    _deploy_unit(game, enemy, 20.0, 10.0)

    profile = SimpleNamespace(parent_wargear=SimpleNamespace(is_ranged=lambda: False, is_melee=lambda: True))

    baseline = get_aura_attack_modifiers(nearby, enemy, profile, game_map=game.map)
    assert bool(baseline.reroll_hit_ones) is False
    assert bool(baseline.reroll_wound_ones) is False

    set_active_primarch_of_the_first_legion(
        lion,
        [KEY_MARTIAL_EXEMPLAR, KEY_NO_HIDING_FROM_THE_WATCHERS],
        start_round=1,
        expires_round=2,
        player_id=player.id,
    )

    active = get_aura_attack_modifiers(nearby, enemy, profile, game_map=game.map)
    assert bool(active.reroll_hit_ones) is True
    assert bool(active.reroll_wound_ones) is True


def test_no_hiding_from_the_watchers_aura_requires_selection() -> None:
    game, player, _enemy_player = _build_game()
    lion = _make_unit(
        "Lion El'Jonson",
        keywords=["CHARACTER", "MONSTER"],
        faction_keywords=["ADEPTUS ASTARTES", "DARK ANGELS"],
        abilities=_lion_abilities(),
    )
    nearby = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    distant = _make_unit(
        "Hellblasters",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    player.army.add_unit(lion)
    player.army.add_unit(nearby)
    player.army.add_unit(distant)
    _deploy_unit(game, lion, 10.0, 10.0)
    _deploy_unit(game, nearby, 13.0, 10.0)
    _deploy_unit(game, distant, 25.0, 10.0)

    assert (4, "against mortal wounds") not in list(nearby.has_feel_no_pain(target_model=nearby.models[0]) or [])

    set_active_primarch_of_the_first_legion(
        lion,
        [KEY_MARTIAL_EXEMPLAR, KEY_NO_HIDING_FROM_THE_WATCHERS],
        start_round=1,
        expires_round=2,
        player_id=player.id,
    )

    assert (4, "against mortal wounds") in list(nearby.has_feel_no_pain(target_model=nearby.models[0]) or [])
    assert (4, "against mortal wounds") not in list(distant.has_feel_no_pain(target_model=distant.models[0]) or [])


def test_mist_wreathed_shadow_realms_queues_and_places_lion_into_strategic_reserves() -> None:
    game, player, enemy_player = _build_game()
    lion = _make_unit(
        "Lion El'Jonson",
        keywords=["CHARACTER", "MONSTER"],
        faction_keywords=["ADEPTUS ASTARTES", "DARK ANGELS"],
        abilities=_lion_abilities(),
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    player.army.add_unit(lion)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(game, lion, 10.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)

    mgr = getattr(player.army, "primarch_of_the_first_legion", None)
    mgr.on_command_phase_start(player, game=game)
    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="primarch_of_the_first_legion")
    assert request is not None

    option_id = _find_option_id_for_choice_keys(
        request,
        (KEY_MIST_WREATHED_SHADOW_REALMS, KEY_NO_HIDING_FROM_THE_WATCHERS),
    )
    resolve_decision_command(game, request, option_id, player_id=player.id)

    confirm_request = _find_request(game, DECISION_CONFIRM_YES_NO, ability="mist_wreathed_shadow_realms")
    assert confirm_request is not None
    use_id = _find_yes_no_option_id(confirm_request, choice=True)
    resolve_decision_command(game, confirm_request, use_id, player_id=player.id)

    assert lion.is_in_strategic_reserves() is True
    assert lion not in list(game.map.units or [])


def test_mist_wreathed_shadow_realms_does_not_queue_while_in_engagement_range() -> None:
    game, player, enemy_player = _build_game()
    lion = _make_unit(
        "Lion El'Jonson",
        keywords=["CHARACTER", "MONSTER"],
        faction_keywords=["ADEPTUS ASTARTES", "DARK ANGELS"],
        abilities=_lion_abilities(),
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    player.army.add_unit(lion)
    enemy_player.army.add_unit(enemy)
    _deploy_unit(game, lion, 10.0, 10.0)
    _deploy_unit(game, enemy, 13.0, 10.0)

    mgr = getattr(player.army, "primarch_of_the_first_legion", None)
    mgr.on_command_phase_start(player, game=game)
    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="primarch_of_the_first_legion")
    assert request is not None

    option_id = _find_option_id_for_choice_keys(
        request,
        (KEY_MIST_WREATHED_SHADOW_REALMS, KEY_NO_HIDING_FROM_THE_WATCHERS),
    )
    resolve_decision_command(game, request, option_id, player_id=player.id)

    assert _find_request(game, DECISION_CONFIRM_YES_NO, ability="mist_wreathed_shadow_realms") is None
