from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        movement: int = 8,
        toughness: int = 6,
        save: int = 4,
        wounds: int = 8,
        objective_control: int = 2,
        model_count: int = 1,
        keywords=None,
        faction_keywords=None,
        faction_name: str = "Chaos Daemons",
    ):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": str(toughness),
                "Sv": str(save),
                "W": str(wounds),
                "Ld": "7",
                "OC": str(objective_control),
                "base_size": "32mm",
                "inv_sv": "5",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


class _Wargear:
    def __init__(self, *, melee: bool = False, ranged: bool = False):
        self._melee = bool(melee)
        self._ranged = bool(ranged)

    def is_melee(self) -> bool:
        return self._melee

    def is_ranged(self) -> bool:
        return self._ranged


class _WeaponProfile:
    def __init__(self, *, melee: bool = False, ranged: bool = False):
        self.parent_wargear = _Wargear(melee=melee, ranged=ranged)


def _make_unit(
    name: str,
    army: Army,
    *,
    movement: int = 8,
    toughness: int = 6,
    wounds: int = 8,
    keywords=None,
    faction_keywords=None,
    faction_name: str = "Chaos Daemons",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            movement=movement,
            toughness=toughness,
            wounds=wounds,
            keywords=keywords,
            faction_keywords=faction_keywords,
            faction_name=faction_name,
        )
    )
    unit.deployed = True
    army.add_unit(unit)
    return unit


def _build_game():
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE))

    legion_army = Army.with_detachment("Chaos Daemons", detachment_type="Blood Legion")
    legion_army.faction_id = "CD"
    enemy_army = Army.with_detachment("Enemies", detachment_type="Other")
    enemy_army.faction_id = "SM"

    legion_player = Player("Legion", PlayerControl.REMOTE, legion_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, enemy_army)
    game.add_player(legion_player)
    game.add_player(enemy_player)

    return game, legion_player, enemy_player


def _apply_blood_legion_enhancement(unit: Unit, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="CD",
        detachment="Blood Legion",
    ).apply_to_unit(unit)


def _melee_profile() -> WargearProfile:
    return WargearProfile(
        profile_name="Claws",
        wargear_data={
            "range": "Melee",
            "A": "3",
            "BS_WS": "3+",
            "S": "6",
            "AP": "-2",
            "D": "2",
            "description": "",
        },
        parent_wargear=_Wargear(melee=True, ranged=False),
    )


def test_blood_legion_enhancement_descriptors_registered():
    ids_to_names = {
        "000009815002": "Slaughterthirst (Aura)",
        "000009815003": "Fury's Cage",
        "000009815004": "Brazenmaw",
        "000009815005": "Gateway Unto Damnation",
    }
    for enhancement_id, expected_name in ids_to_names.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(desc.name) == expected_name


def test_slaughterthirst_aura_grants_lance_only_to_eligible_non_monsters():
    from warhammer40k_ai.utility.aura_effects import get_aura_weapon_keyword_bonuses

    game, legion_player, _enemy_player = _build_game()
    source = _make_unit(
        "Slaughterthirst Source",
        legion_player.army,
        keywords=["KHORNE", "MONSTER"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    eligible = _make_unit(
        "Eligible",
        legion_player.army,
        keywords=["KHORNE", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    excluded_monster = _make_unit(
        "Excluded Monster",
        legion_player.army,
        keywords=["KHORNE", "MONSTER"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )

    _apply_blood_legion_enhancement(source, "000009815002", "Slaughterthirst (Aura)")

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    eligible.models[0].set_location(3.0, 0.0, 0.0, 0.0)
    excluded_monster.models[0].set_location(3.0, 1.0, 0.0, 0.0)

    game.map.units = [source, eligible, excluded_monster]
    game.rebuild_entity_registry()

    eligible_rules = get_aura_weapon_keyword_bonuses(
        eligible,
        _WeaponProfile(melee=True),
        game_map=game.map,
    )
    assert any(str(rule.get("keyword", "") or "") == "LANCE" for rule in list(eligible_rules or []))

    excluded_rules = get_aura_weapon_keyword_bonuses(
        excluded_monster,
        _WeaponProfile(melee=True),
        game_map=game.map,
    )
    assert not any(str(rule.get("keyword", "") or "") == "LANCE" for rule in list(excluded_rules or []))


def test_brazenmaw_adds_single_charge_modifier_entry():
    game, legion_player, _enemy_player = _build_game()
    bearer = _make_unit(
        "Brazen Bearer",
        legion_player.army,
        keywords=["KHORNE", "INFANTRY"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )

    _apply_blood_legion_enhancement(bearer, "000009815004", "Brazenmaw")
    _apply_blood_legion_enhancement(bearer, "000009815004", "Brazenmaw")

    mods = list(bearer.special_rules.get("charge_roll_modifiers", []) or [])
    tagged = [entry for entry in mods if isinstance(entry, dict) and str(entry.get("tag", "") or "") == "enhancement:brazenmaw"]
    assert len(tagged) == 1
    assert int(tagged[0].get("value", 0) or 0) == 2


def test_furys_cage_queues_and_activates_with_self_mortal_wounds():
    game, legion_player, enemy_player = _build_game()
    bearer_unit = _make_unit(
        "Fury Bearer",
        legion_player.army,
        keywords=["KHORNE", "MONSTER"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy = _make_unit("Enemy", enemy_player.army, faction_name="Enemies")

    _apply_blood_legion_enhancement(bearer_unit, "000009815003", "Fury's Cage")

    bearer_model = bearer_unit.models[0]
    base_wounds = int(getattr(bearer_model, "_base_wounds", 8) or 8)
    bearer_model.wounds = int(base_wounds)

    bearer_model.set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(1.0, 0.0, 0.0, 0.0)
    game.map.units = [bearer_unit, enemy]
    game.rebuild_entity_registry()

    game.turn = 2
    game.current_player_index = 0
    game.phase = BattleRoundPhases.FIGHT_PHASE

    game._on_fight_unit_selected_furys_cage(unit=bearer_unit, selecting_player=legion_player)
    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO
        and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "furys_cage"
    )

    use_option = next(opt for opt in list(request.options or []) if bool((opt.payload or {}).get("choice", False)))
    with patch("warhammer40k_ai.engine.game.get_roll", return_value=2):
        result = resolve_decision_command(game, request, use_option.option_id, player_id=legion_player.id)

    assert bool(getattr(result, "ok", False)) is True
    assert bool(bearer_unit.special_rules.get("enhancement_furys_cage_active")) is True
    assert str(bearer_unit.special_rules.get("enhancement_furys_cage_active_model_id", "") or "") == str(
        get_entity_id(bearer_model) or ""
    )
    assert int(bearer_model.wounds) == int(base_wounds - 3)


def test_furys_cage_active_grants_melee_hit_and_wound_rerolls_for_bearer():
    game, legion_player, enemy_player = _build_game()
    bearer_unit = _make_unit(
        "Fury Bearer",
        legion_player.army,
        keywords=["KHORNE", "MONSTER"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    enemy = _make_unit(
        "Enemy",
        enemy_player.army,
        toughness=6,
        faction_name="Enemies",
    )

    _apply_blood_legion_enhancement(bearer_unit, "000009815003", "Fury's Cage")

    game.turn = 2
    game.current_player_index = 0
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.map.units = [bearer_unit, enemy]
    game.rebuild_entity_registry()

    bearer_model = bearer_unit.models[0]
    sr = dict(bearer_unit.special_rules)
    sr["enhancement_furys_cage_active"] = True
    sr["enhancement_furys_cage_turn"] = int(game.turn)
    sr["enhancement_furys_cage_turn_owner"] = str(legion_player.id)
    sr["enhancement_furys_cage_expires_phase"] = "FIGHT_PHASE"
    sr["enhancement_furys_cage_active_model_id"] = str(get_entity_id(bearer_model) or "")
    sr["enhancement_furys_cage_source"] = "Fury's Cage"
    bearer_unit.special_rules = sr

    profile = _melee_profile()

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
        hit_result = profile._hit_target_with_tracking(
            enemy,
            bearer_model,
            attack_instance={},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    assert int(hit_result.get("reroll", 0) or 0) == 6
    assert any("Fury's Cage" in str(text or "") for text in list(hit_result.get("special_effects", []) or []))

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
        wound_result = profile._wound_target_with_tracking(
            enemy,
            bearer_model,
            attack_instance={},
            roll_value=1,
            allow_rerolls=True,
            log_roll=False,
        )
    assert int(wound_result.get("reroll", 0) or 0) == 6
    assert any("Fury's Cage" in str(text or "") for text in list(wound_result.get("special_effects", []) or []))


def test_gateway_unto_damnation_kill_tracking_and_deadly_demise_upgrade():
    game, legion_player, enemy_player = _build_game()
    bearer = _make_unit(
        "Gateway Bearer",
        legion_player.army,
        keywords=["KHORNE", "MONSTER"],
        faction_keywords=["LEGIONES DAEMONICA"],
    )
    bearer.possible_abilities = [
        SimpleNamespace(name="Deadly Demise", description="", type="Ability", parameter="D3")
    ]
    destroyed = _make_unit("Destroyed Enemy", enemy_player.army, faction_name="Enemies")

    _apply_blood_legion_enhancement(bearer, "000009815005", "Gateway Unto Damnation")

    bearer.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    destroyed.models[0].set_location(1.0, 0.0, 0.0, 0.0)
    game.map.units = [bearer, destroyed]
    game.rebuild_entity_registry()

    has_dd, base_damage = bearer.has_deadly_demise()
    assert bool(has_dd) is True
    assert str(base_damage) == "1D3"

    game.turn = 1
    game.current_player_index = 0
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game._on_unit_destroyed_phase_kill_tracking(
        unit=destroyed,
        destroyed_by_unit=bearer,
        destroyed_by_model=bearer.models[0],
    )

    assert int(
        bearer.special_rules.get("enhancement_gateway_unto_damnation_destroyed_enemy_units_this_battle", 0) or 0
    ) == 1

    has_dd_after, upgraded_damage = bearer.has_deadly_demise()
    assert bool(has_dd_after) is True
    assert str(upgraded_damage) == "1D3+3"

    with patch.object(bearer, "_apply_deadly_demise_explosion") as explode:
        with patch("warhammer40k_ai.units.unit.get_roll", return_value=1):
            bearer._trigger_deadly_demise(bearer.models[0], game.map)
        explode.assert_not_called()

        with patch("warhammer40k_ai.units.unit.get_roll", return_value=2):
            bearer._trigger_deadly_demise(bearer.models[0], game.map)
        explode.assert_called_once()
