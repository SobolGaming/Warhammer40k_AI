from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _RectZone:
    def __init__(self, x_min: float, x_max: float, y_min: float, y_max: float) -> None:
        self.x_min = float(x_min)
        self.x_max = float(x_max)
        self.y_min = float(y_min)
        self.y_max = float(y_max)
        self.vertices = [
            (self.x_min, self.y_min),
            (self.x_max, self.y_min),
            (self.x_max, self.y_max),
            (self.x_min, self.y_max),
        ]

    def contains_point(self, x: float, y: float) -> bool:
        return self.x_min <= float(x) <= self.x_max and self.y_min <= float(y) <= self.y_max


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str | None = None,
        faction_name: str = "Chaos Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
    ):
        self.id = str(datasheet_id or f"ds_{name.lower().replace(' ', '_')}")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "4",
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
    datasheet_id: str | None = None,
    faction_name: str = "Chaos Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_unit_location(unit: Unit, *, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str, description: str = "") -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(enhancement_name),
        faction_id="CSM",
        detachment="Renegade Raiders",
        points=20,
        description=str(description or enhancement_name),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _make_profile(*, melee: bool) -> WargearProfile:
    return WargearProfile(
        profile_name="Test Profile",
        wargear_data={
            "range": "Melee" if melee else "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    csm_army = Army.with_detachment("Chaos Space Marines", "Renegade Raiders")
    csm_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    csm_player = Player("CSM", control=PlayerControl.REMOTE, army=csm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.deployment_zones = {
        csm_player.id: {"mission_zones": [_RectZone(0.0, 20.0, 0.0, 20.0)]},
        enemy_player.id: {"mission_zones": [_RectZone(80.0, 100.0, 0.0, 20.0)]},
    }
    game.map.deployment_zones = dict(game.deployment_zones)
    return game, csm_army, enemy_army, csm_player, enemy_player


def test_renegade_raiders_enhancement_descriptors_registered():
    expected = {
        "000008968002": ("Despot's Claim", "command_phase_cp_roll_with_enemy_deployment_zone_bonus"),
        "000008968003": ("Dread Reaver", "bearer_melee_hit_wound_reroll_within_enemy_deployment_zone_distance"),
        "000008968004": ("Mark of the Hound", "bearer_unit_gains_scouts"),
        "000008968005": ("Tyrant's Lash", "reroll_advance_and_shoot_after_fall_back_for_bearer_unit"),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_despots_claim_adds_enemy_deployment_zone_bonus_before_cp_gain_check():
    game, csm_army, _enemy_army, csm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0
    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(source)
    _apply_enhancement(source, enhancement_id="000008968002", enhancement_name="Despot's Claim")
    _set_unit_location(source, x=70.0, y=10.0)
    game.map.units = [source]
    game.rebuild_entity_registry()

    before_cp = int(csm_player.command_points or 0)
    with patch("warhammer40k_ai.rules.chaos_space_marines_detachments.get_roll", return_value=4):
        outcomes = csm_army.chaos_space_marines_detachments.renegade_raiders_despots_claim_on_command_phase_start(game=game)
    after_cp = int(csm_player.command_points or 0)

    assert len(outcomes) == 1
    assert int(outcomes[0].get("roll_modifier", 0) or 0) == 1
    assert int(outcomes[0].get("total", 0) or 0) == 5
    assert after_cp == before_cp + 1

    _set_unit_location(source, x=55.0, y=10.0)
    with patch("warhammer40k_ai.rules.chaos_space_marines_detachments.get_roll", return_value=4):
        outcomes = csm_army.chaos_space_marines_detachments.renegade_raiders_despots_claim_on_command_phase_start(game=game)
    assert int(outcomes[0].get("roll_modifier", 0) or 0) == 0


def test_dread_reaver_grants_melee_hit_and_wound_rerolls_when_bearer_is_within_enemy_zone_distance():
    game, csm_army, enemy_army, _csm_player, _enemy_player = _build_game()
    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    enemy = _make_unit("Enemy", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(source)
    enemy_army.add_unit(enemy)
    _apply_enhancement(source, enhancement_id="000008968003", enhancement_name="Dread Reaver")
    _set_unit_location(source, x=70.0, y=10.0)
    _set_unit_location(enemy, x=72.0, y=10.0)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()

    attacker_model = source.models[0]
    melee_profile = _make_profile(melee=True)
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
        hit_result = melee_profile._hit_target_with_tracking(
            enemy,
            attacker_model,
            attack_instance={},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    assert int(hit_result.get("reroll", 0) or 0) == 6
    assert any("Dread Reaver" in str(reason or "") for reason in list(hit_result.get("special_effects", []) or []))

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
        wound_result = melee_profile._wound_target_with_tracking(
            enemy,
            attacker_model,
            attack_instance={},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    assert int(wound_result.get("reroll", 0) or 0) == 6
    assert any("Dread Reaver" in str(reason or "") for reason in list(wound_result.get("special_effects", []) or []))


def test_mark_of_the_hound_grants_scouts_while_bearer_is_alive():
    csm_army = Army.with_detachment("Chaos Space Marines", "Renegade Raiders")
    csm_army.faction_id = "CSM"
    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(source)
    _apply_enhancement(source, enhancement_id="000008968004", enhancement_name="Mark of the Hound")

    has_scout, distance = source.has_scout()
    assert bool(has_scout)
    assert float(distance) == 6.0

    source.models[0].wounds = 0
    source._invalidate_ability_cache()
    has_scout_after, distance_after = source.has_scout()
    assert not bool(has_scout_after)
    assert float(distance_after) == 0.0


def test_tyrants_lash_grants_advance_reroll_and_shoot_after_fall_back():
    csm_army = Army.with_detachment("Chaos Space Marines", "Renegade Raiders")
    csm_army.faction_id = "CSM"
    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(source)
    _apply_enhancement(source, enhancement_id="000008968005", enhancement_name="Tyrant's Lash")
    source.round_state.fell_back_this_round = True

    ranged_profile = _make_profile(melee=False)
    assert bool(source.can_reroll_advance_roll())
    assert bool(source.can_shoot_after_fall_back(ranged_profile))

    source.models[0].wounds = 0
    source._invalidate_ability_cache()
    assert not bool(source.can_reroll_advance_roll())
    assert not bool(source.can_shoot_after_fall_back(ranged_profile))
