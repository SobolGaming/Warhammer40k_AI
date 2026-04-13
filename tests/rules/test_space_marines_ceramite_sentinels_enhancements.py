from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


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
    game.auto_resolve_dice_rolls = False

    sm_army = Army.with_detachment("Space Marines", "Ceramite Sentinels")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.actions_enabled = True
    game.mission_actions_enabled = True
    game.mission_has_actions = True

    sm_player.command_points = 10
    enemy_player.command_points = 10

    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    return game, sm_player, enemy_player, sm_army, enemy_army


def _activate_unit(unit: Unit, x: float = 0.0, y: float = 0.0) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(index) * 1.5, float(y), 0.0, 0.0)


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    player.stratagems._current_phase_name = phase_name.replace("_", " ").title().replace(" Phase", " phase")


def _first_request(game: Game, decision_type: str, *, ability: str = ""):
    expected_ability = str(ability or "").strip()
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        if expected_ability and str((request.context or {}).get("ability", "") or "").strip() != expected_ability:
            continue
        return request
    return None


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="SM",
        detachment="Ceramite Sentinels",
        points=20,
        description="",
    ).apply_to_unit(unit)


def _ranged_profile(name: str = "Bolt Rifle") -> WargearProfile:
    parent = SimpleNamespace(name=str(name), is_ranged=lambda: True, is_melee=lambda: False)
    return WargearProfile(
        profile_name="Default",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_ceramite_sentinels_enhancement_descriptors_registered():
    expected = {
        "000010759002": ("Honour Indefatigable", "return_bearer_on_2plus_with_fixed_wounds"),
        "000010759003": ("Castellum Omnivox", "choose_action_or_shoot_and_charge_after_fall_back"),
        "000010759004": ("Spy-skull Data Link", "grant_ignores_cover_to_bearer_led_unit_ranged_weapons"),
        "000010759005": ("Defensive Mastery", "redeploy_units"),
    }
    for enhancement_id, (expected_name, expected_effect) in expected.items():
        by_id = get_enhancement_tool_descriptor(enhancement_id=enhancement_id, name=expected_name)
        by_name = get_enhancement_tool_descriptor(name=expected_name)
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_honour_indefatigable_registers_return_on_death_spec():
    game, _sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    captain = _make_unit(
        "Captain in Gravis Armour",
        keywords=["CHARACTER", "INFANTRY", "GRAVIS"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=6,
    )
    sm_army.add_unit(captain)
    _activate_unit(captain, 10.0, 10.0)
    game.rebuild_entity_registry()

    _apply_enhancement(
        captain,
        enhancement_id="000010759002",
        enhancement_name="Honour Indefatigable",
    )

    specs = list(captain._get_return_on_death_specs() or [])
    matching = [spec for spec in specs if str(spec.get("key", "") or "") == "honour_indefatigable"]
    assert len(matching) == 1
    spec = matching[0]
    assert int(spec.get("roll_min", 0) or 0) == 2
    assert str(spec.get("wounds", "") or "") == "full"
    assert str(spec.get("name", "") or "") == "Honour Indefatigable"


def test_castellum_omnivox_choice_action_allows_action_after_fall_back():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(intercessors)
    _activate_unit(intercessors, 10.0, 10.0)
    game.rebuild_entity_registry()

    _apply_enhancement(
        intercessors,
        enhancement_id="000010759003",
        enhancement_name="Castellum Omnivox",
    )

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    intercessors.round_state.fell_back_this_round = True
    game._on_unit_move_ended_detachment_rules(unit=intercessors, action="fall_back")

    request = _first_request(game, DECISION_CHOOSE_QUARRY, ability="space_marines_castellum_omnivox_choice")
    assert request is not None
    option = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("choice_key", "") or "").strip().upper() == "ACTION"
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=sm_player.id)
    assert bool(getattr(getattr(result, "value", None), "ok", False))

    eligibility = game._is_unit_eligible_to_start_action(intercessors)
    assert bool(eligibility.get("valid", False)) is True


def test_castellum_omnivox_choice_shoot_and_charge_allows_both_after_fall_back():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(intercessors)
    _activate_unit(intercessors, 10.0, 10.0)
    game.rebuild_entity_registry()

    _apply_enhancement(
        intercessors,
        enhancement_id="000010759003",
        enhancement_name="Castellum Omnivox",
    )

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    intercessors.round_state.fell_back_this_round = True
    game._on_unit_move_ended_detachment_rules(unit=intercessors, action="fall_back")

    request = _first_request(game, DECISION_CHOOSE_QUARRY, ability="space_marines_castellum_omnivox_choice")
    assert request is not None
    option = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("choice_key", "") or "").strip().upper() == "SHOOT_AND_CHARGE"
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=sm_player.id)
    assert bool(getattr(getattr(result, "value", None), "ok", False))

    profile = _ranged_profile()
    assert intercessors.can_shoot_after_fall_back(profile, model=intercessors.models[0]) is True
    assert intercessors.can_charge_after_fall_back() is True


def test_spy_skull_data_link_grants_ignores_cover_for_ranged_weapons():
    game, _sm_player, _enemy_player, sm_army, enemy_army = _build_game()
    intercessors = _make_unit(
        "Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(intercessors)
    enemy_army.add_unit(enemy)
    _activate_unit(intercessors, 10.0, 10.0)
    _activate_unit(enemy, 18.0, 10.0)
    game.rebuild_entity_registry()

    _apply_enhancement(
        intercessors,
        enhancement_id="000010759004",
        enhancement_name="Spy-skull Data Link",
    )

    rules = list(intercessors._enhancement_weapon_keyword_rules(model=intercessors.models[0]) or [])
    assert any(
        str(rule.get("attack_type", "") or "").strip().lower() == "ranged"
        and str(rule.get("keyword", "") or "").strip().upper() == "IGNORES COVER"
        for rule in rules
        if isinstance(rule, dict)
    )


def test_defensive_mastery_registers_redeploy_with_reserves_override():
    game, _sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    captain = _make_unit(
        "Captain",
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(captain)
    _activate_unit(captain, 10.0, 10.0)
    game.rebuild_entity_registry()

    _apply_enhancement(
        captain,
        enhancement_id="000010759005",
        enhancement_name="Defensive Mastery",
    )

    assert captain.has_redeploy() == (True, 3, True)
    specs = list(getattr(captain, "special_rules", {}).get("enhancement_redeploy_specs", []) or [])
    matching = [spec for spec in specs if str(spec.get("source", "") or "") == "Defensive Mastery"]
    assert len(matching) == 1
    spec = matching[0]
    assert "ADEPTUS ASTARTES" in list(spec.get("filters", []) or [])
    assert bool(spec.get("strategic_reserves_ignore_current_unit_count_limit", False)) is True
