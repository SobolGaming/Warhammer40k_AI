from unittest.mock import patch

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import (
    Enhancement,
    resolve_enhancement_command_phase_cp_gain_roll_specs,
)
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: str = "3",
    ):
        self.id = str(name or "unit").lower().replace(" ", "-")
        self.name = name
        self.faction_data = {
            "name": "Orks" if "ORKS" in [str(k).upper() for k in list(faction_keywords or [])] else "Enemy"
        }
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        count = max(1, int(model_count or 1))
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "4",
                "W": str(wounds),
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


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: str = "3",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
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


def _set_positions(unit: Unit, x: float, y: float, *, spacing: float = 1.0) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(idx) * float(spacing), float(y), 0.0, 0.0)


def _build_game(*, detachment: str, ork_units: list[Unit], enemy_units: list[Unit]):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ork_army = Army.with_detachment("Orks", detachment_type=detachment)
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    ork_player = Player("Ork", PlayerControl.LOCAL, army=ork_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ork_player)
    game.add_player(enemy_player)

    for unit in list(ork_units or []):
        ork_army.add_unit(unit)
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)

    game.map.units = list(ork_units or []) + list(enemy_units or [])
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    return game, ork_player, enemy_player, ork_army


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str, detachment: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="ORK",
        detachment=detachment,
        points=0,
        description="",
    ).apply_to_unit(unit)


def _run_command_phase_cp_rolls(game: Game, player: Player) -> None:
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = game.players.index(player)
    game._on_phase_start_command_phase_cp_rolls(player=player, phase=BattleRoundPhases.COMMAND_PHASE)


def test_orks_command_phase_cp_enhancement_descriptors_registered():
    expected = {
        "000008881003": (
            "Brutal But Kunnin'",
            "command_phase_cp_roll_with_effective_model_count_bonus",
        ),
        "000008872003": (
            "Speed Makes Right",
            "command_phase_cp_roll_if_bearer_or_transport_within_enemy_range",
        ),
    }
    for enhancement_id, (expected_name, expected_effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == expected_name
        assert str(getattr(descriptor, "effect", "") or "") == expected_effect


def test_enhancement_command_phase_cp_gain_helper_applies_effective_model_modifier():
    source = _make_unit(
        "Boyz Mob",
        keywords=["ORKS", "INFANTRY", "BOYZ"],
        faction_keywords=["ORKS"],
        model_count=5,
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["EN"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Green Tide",
        ork_units=[source],
        enemy_units=[enemy],
    )
    _set_positions(source, 0.0, 0.0)
    _set_positions(enemy, 24.0, 0.0)

    source_model_id = str(getattr(source.models[0], "id", getattr(source.models[0], "_id", "")) or "")
    source.special_rules = dict(getattr(source, "special_rules", {}) or {})
    source.special_rules["enhancement_command_phase_cp_gain_roll_specs"] = [
        {
            "type": "enhancement_command_phase_cp_gain_roll",
            "source": "Test CP Gain",
            "source_model_id": source_model_id,
            "success_on": 5,
            "cp_gain": 1,
            "requires_bearer_on_battlefield_or_embarked_transport": True,
            "roll_bonus_if_effective_model_count_at_least": 2,
            "effective_model_count_threshold": 10,
            "effective_model_count_scope": "enhancement",
        }
    ]
    source.special_rules["orks_temp_effects"] = [
        {
            "id": "test:enhancement_floor",
            "source": "test",
            "effect": "effective_model_count_floor",
            "value": 10,
            "effective_model_count_scopes": ["enhancement"],
        }
    ]

    before_cp = int(ork_player.command_points or 0)
    with patch("warhammer40k_ai.rules.enhancement.get_roll", return_value=3):
        outcomes = resolve_enhancement_command_phase_cp_gain_roll_specs(
            source,
            player=ork_player,
            game=game,
        )

    assert len(outcomes) == 1
    assert int(outcomes[0].get("roll", 0) or 0) == 3
    assert int(outcomes[0].get("roll_modifier", 0) or 0) == 2
    assert int(outcomes[0].get("total", 0) or 0) == 5
    assert int(ork_player.command_points or 0) == before_cp + 1


def test_brutal_but_kunnin_effective_ten_branch_grants_cp_on_modified_success():
    source = _make_unit(
        "Boyz Mob",
        keywords=["ORKS", "INFANTRY", "BOYZ"],
        faction_keywords=["ORKS"],
        model_count=10,
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["EN"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Green Tide",
        ork_units=[source],
        enemy_units=[enemy],
    )
    _set_positions(source, 0.0, 0.0)
    _set_positions(enemy, 30.0, 0.0)
    _apply_enhancement(
        source,
        enhancement_id="000008881003",
        enhancement_name="Brutal But Kunnin'",
        detachment="Green Tide",
    )

    before_cp = int(ork_player.command_points or 0)
    with patch("warhammer40k_ai.rules.enhancement.get_roll", return_value=3):
        _run_command_phase_cp_rolls(game, ork_player)
    assert int(ork_player.command_points or 0) == before_cp + 1


def test_command_phase_cp_enhancement_wrong_phase_does_not_trigger():
    source = _make_unit(
        "Boyz Mob",
        keywords=["ORKS", "INFANTRY", "BOYZ"],
        faction_keywords=["ORKS"],
        model_count=10,
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["EN"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Green Tide",
        ork_units=[source],
        enemy_units=[enemy],
    )
    _set_positions(source, 0.0, 0.0)
    _set_positions(enemy, 30.0, 0.0)
    _apply_enhancement(
        source,
        enhancement_id="000008881003",
        enhancement_name="Brutal But Kunnin'",
        detachment="Green Tide",
    )

    before_cp = int(ork_player.command_points or 0)
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = game.players.index(ork_player)
    with patch("warhammer40k_ai.rules.enhancement.get_roll", return_value=6):
        game._on_phase_start_command_phase_cp_rolls(player=ork_player, phase=BattleRoundPhases.MOVEMENT_PHASE)
    assert int(ork_player.command_points or 0) == before_cp


def test_speed_makes_right_requires_enemy_within_range_and_embarked_transport_on_battlefield():
    transport = _make_unit(
        "Trukk",
        keywords=["ORKS", "VEHICLE", "TRANSPORT", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
    )
    bearer_unit = _make_unit(
        "Warboss",
        keywords=["ORKS", "INFANTRY", "CHARACTER"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["EN"])

    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Kult of Speed",
        ork_units=[transport, bearer_unit],
        enemy_units=[enemy],
    )
    _set_positions(transport, 0.0, 0.0)
    _set_positions(enemy, 8.0, 0.0)
    bearer_unit.embarked_in = transport
    _apply_enhancement(
        bearer_unit,
        enhancement_id="000008872003",
        enhancement_name="Speed Makes Right",
        detachment="Kult of Speed",
    )

    before_cp = int(ork_player.command_points or 0)
    with patch("warhammer40k_ai.rules.enhancement.get_roll", return_value=3):
        _run_command_phase_cp_rolls(game, ork_player)
    assert int(ork_player.command_points or 0) == before_cp + 1

    # Out-of-range enemy: no gain even on a passing raw roll.
    _set_positions(enemy, 20.0, 0.0)
    ork_player.cp_gained_this_battle_round_excluding_normal_command_cp = 0
    before_cp = int(ork_player.command_points or 0)
    with patch("warhammer40k_ai.rules.enhancement.get_roll", return_value=6):
        _run_command_phase_cp_rolls(game, ork_player)
    assert int(ork_player.command_points or 0) == before_cp

    # Embarked in a transport that is not on the battlefield: no gain.
    transport.deployed = False
    transport.reserve_status = "strategic_reserves"
    ork_player.cp_gained_this_battle_round_excluding_normal_command_cp = 0
    before_cp = int(ork_player.command_points or 0)
    with patch("warhammer40k_ai.rules.enhancement.get_roll", return_value=6):
        _run_command_phase_cp_rolls(game, ork_player)
    assert int(ork_player.command_points or 0) == before_cp


def test_speed_makes_right_failed_roll_does_not_grant_cp():
    bearer_unit = _make_unit(
        "Warboss",
        keywords=["ORKS", "INFANTRY", "CHARACTER"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["EN"])
    game, ork_player, _enemy_player, _ork_army = _build_game(
        detachment="Kult of Speed",
        ork_units=[bearer_unit],
        enemy_units=[enemy],
    )
    _set_positions(bearer_unit, 0.0, 0.0)
    _set_positions(enemy, 6.0, 0.0)
    _apply_enhancement(
        bearer_unit,
        enhancement_id="000008872003",
        enhancement_name="Speed Makes Right",
        detachment="Kult of Speed",
    )

    before_cp = int(ork_player.command_points or 0)
    with patch("warhammer40k_ai.rules.enhancement.get_roll", return_value=2):
        _run_command_phase_cp_rolls(game, ork_player)
    assert int(ork_player.command_points or 0) == before_cp
