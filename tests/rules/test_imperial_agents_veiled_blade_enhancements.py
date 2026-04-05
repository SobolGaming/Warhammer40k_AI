from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.rules.stratagems import Stratagem
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Imperial Agents",
        keywords=None,
        faction_keywords=None,
        cost: int = 100,
        wounds: int = 4,
        movement: int = 7,
        toughness: int = 4,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(cost)}]
        self.datasheets_models = [
            {
                "M": str(int(movement)),
                "T": str(int(toughness)),
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
    faction_name: str = "Imperial Agents",
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
    return unit


def _make_extra_model(name: str, unit: Unit) -> Model:
    model = Model(
        name=name,
        movement=7,
        toughness=4,
        save=3,
        wounds=4,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    model.set_location(0.0, 0.0, 0.0, 0.0)
    return model


def _apply_veiled_blade_enhancement(unit: Unit, *, enhancement_id: str, name: str, description: str) -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(name),
        faction_id="AOI",
        detachment="Veiled Blade Elimination Force",
        detachment_id="000009757",
        points=0,
        description=str(description),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    ia_army = Army("Imperial Agents", "Veiled Blade Elimination Force")
    ia_army.faction_id = "AOI"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "SM"

    ia_player = Player("IA", control=PlayerControl.LOCAL, army=ia_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ia_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, ia_player, enemy_player


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _find_decoy_targets_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "") == "decoy_targets":
            return request
    return None


def _find_option_id_for_target_model(request, model) -> str:
    model_id = str(get_entity_id(model) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_model_id", "") or "") == model_id:
            return str(option.option_id)
    return ""


def _counter_offensive_stratagem() -> Stratagem:
    return Stratagem(
        id="core_counter_offensive",
        name="Counter-offensive",
        type="Core",
        description="",
        cp_cost=2,
        turn="Either",
        phase="Fight phase",
        detachment="",
        faction_id="",
    )


def test_veiled_blade_enhancement_descriptors_registered():
    decoy = get_enhancement_tool_descriptor(enhancement_id="000009757002")
    assert decoy is not None
    assert decoy.name == "Decoy Targets"
    assert decoy.effect == "destroy_selected_model_and_redeploy_bearer"
    assert int(decoy.effect_params.get("max_uses", 0) or 0) == 2
    assert int(decoy.effect_params.get("per_battle_round_limit", 0) or 0) == 1

    esoteric = get_enhancement_tool_descriptor(enhancement_id="000009757003")
    assert esoteric is not None
    assert esoteric.name == "Esoteric Explosives"
    assert int(esoteric.effect_params.get("grenade_mortal_threshold", 0) or 0) == 3

    intraneural = get_enhancement_tool_descriptor(enhancement_id="000009757004")
    assert intraneural is not None
    assert intraneural.name == "Intraneural Biotech"
    assert tuple(intraneural.effect_params.get("stratagems", ()) or ()) == (
        "HEROIC INTERVENTION",
        "COUNTER-OFFENSIVE",
    )

    micromelta = get_enhancement_tool_descriptor(enhancement_id="000009757005")
    assert micromelta is not None
    assert micromelta.name == "Micromelta Rounds"
    assert str(micromelta.effect_params.get("weapon_name", "") or "") == "exitus rifle"
    assert int(micromelta.effect_params.get("anti_monster", 0) or 0) == 4
    assert int(micromelta.effect_params.get("anti_vehicle", 0) or 0) == 4


def test_micromelta_rounds_grants_anti_keywords_to_bearer_exitus_rifle_only():
    army = Army("Imperial Agents", "Veiled Blade Elimination Force")
    army.faction_id = "AOI"

    vindicare = _make_unit(
        "Vindicare Assassin",
        keywords=["OFFICIO ASSASSINORUM", "INFANTRY", "CHARACTER"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    vindicare.models.append(_make_extra_model("Vindicare Spotter", vindicare))
    army.add_unit(vindicare)

    _apply_veiled_blade_enhancement(
        vindicare,
        enhancement_id="000009757005",
        name="Micromelta Rounds",
        description="This model's exitus rifle has [ANTI-MONSTER 4+] and [ANTI-VEHICLE 4+].",
    )

    bearer_id = str(vindicare.special_rules.get("enhancement_bearer_model_id", "") or "")
    assert bearer_id
    bearer_model = next(
        model
        for model in list(vindicare.models or [])
        if str(getattr(model, "id", getattr(model, "_id", "")) or "") == bearer_id
    )
    non_bearer_model = next(model for model in list(vindicare.models or []) if model is not bearer_model)

    bearer_ranged = vindicare.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=bearer_model,
        weapon_name="Exitus Rifle",
    )
    anti_specs = {tuple(spec) for spec in list(bearer_ranged.get("anti_specs") or [])}
    assert ("MONSTER", 4) in anti_specs
    assert ("VEHICLE", 4) in anti_specs

    bearer_other_weapon = vindicare.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=bearer_model,
        weapon_name="Bolt Pistol",
    )
    assert list(bearer_other_weapon.get("anti_specs") or []) == []

    non_bearer_ranged = vindicare.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=non_bearer_model,
        weapon_name="Exitus Rifle",
    )
    assert list(non_bearer_ranged.get("anti_specs") or []) == []


def test_esoteric_explosives_reduces_grenade_mortal_wound_threshold():
    game, ia_player, enemy_player = _build_game()

    culexus = _make_unit(
        "Culexus Assassin",
        keywords=["OFFICIO ASSASSINORUM", "INFANTRY", "CHARACTER"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ia_player.army.add_unit(culexus)
    enemy_player.army.add_unit(enemy)

    _apply_veiled_blade_enhancement(
        culexus,
        enhancement_id="000009757003",
        name="Esoteric Explosives",
        description="Each time this model is targeted with the Grenades Stratagem, 1 mortal wound is inflicted for each D6 roll of 3+ instead of for each 4+.",
    )

    assert int(ia_player.stratagems._grenade_mortal_wound_threshold(culexus)) == 3
    assert int(ia_player.stratagems._grenade_mortal_wound_threshold(enemy)) == 4
    assert int(enemy_player.stratagems._grenade_mortal_wound_threshold(culexus)) == 3


def test_intraneural_biotech_allows_counter_offensive_repeat_for_zero_cp_once_per_battle_round():
    game, ia_player, enemy_player = _build_game()

    eversor = _make_unit(
        "Eversor Assassin",
        keywords=["OFFICIO ASSASSINORUM", "INFANTRY", "CHARACTER"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ia_player.army.add_unit(eversor)
    enemy_player.army.add_unit(enemy)

    _apply_veiled_blade_enhancement(
        eversor,
        enhancement_id="000009757004",
        name="Intraneural Biotech",
        description="Once per battle round, you can target this model with the Heroic Intervention or Counter-offensive Stratagem for 0CP, even if already used this phase.",
    )

    ia_player.command_points = 0
    stratagem = _counter_offensive_stratagem()
    ia_player.stratagems._used_stratagems_this_phase.add("COUNTER-OFFENSIVE")

    ia_player.set_next_optional_decision("INTRANEURAL_BIOTECH_STRATAGEM_DISCOUNT", True)
    first = ia_player.apply_stratagem_cp_cost(stratagem, target_unit=eversor)
    assert not bool(first.get("denied", False))
    assert int(first.get("cost", -1)) == 0
    assert bool(first.get("intraneural_biotech_use", False))
    assert str(eversor.special_rules.get("intraneural_biotech_used_battle_round", "") or "") == "1"

    ia_player.set_next_optional_decision("INTRANEURAL_BIOTECH_STRATAGEM_DISCOUNT", True)
    second = ia_player.apply_stratagem_cp_cost(stratagem, target_unit=eversor)
    assert bool(second.get("denied", False))
    assert "already used this phase" in str(second.get("reason", "") or "").lower()

    game.turn = 2
    ia_player.set_next_optional_decision("INTRANEURAL_BIOTECH_STRATAGEM_DISCOUNT", True)
    third = ia_player.apply_stratagem_cp_cost(stratagem, target_unit=eversor)
    assert not bool(third.get("denied", False))
    assert int(third.get("cost", -1)) == 0
    assert bool(third.get("intraneural_biotech_use", False))
    assert str(eversor.special_rules.get("intraneural_biotech_used_battle_round", "") or "") == "2"


def test_decoy_targets_queues_single_dialog_applies_effect_and_enforces_usage_limits():
    game, ia_player, enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.turn = 1

    callidus = _make_unit(
        "Callidus Assassin",
        keywords=["OFFICIO ASSASSINORUM", "INFANTRY", "CHARACTER"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    target_a = _make_unit(
        "Friendly Operative A",
        keywords=["INFANTRY"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    target_b = _make_unit(
        "Friendly Operative B",
        keywords=["INFANTRY"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    non_infantry = _make_unit(
        "Friendly Walker",
        keywords=["VEHICLE"],
        faction_keywords=["AGENTS OF THE IMPERIUM", "IMPERIUM"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    ia_player.army.add_unit(callidus)
    ia_player.army.add_unit(target_a)
    ia_player.army.add_unit(target_b)
    ia_player.army.add_unit(non_infantry)
    enemy_player.army.add_unit(enemy)

    _apply_veiled_blade_enhancement(
        callidus,
        enhancement_id="000009757002",
        name="Decoy Targets",
        description=(
            "Twice per battle, in your Movement phase, select one other friendly Infantry model on the battlefield "
            "and not within Engagement Range of one or more enemy units. That model is destroyed and this model is "
            "set up again as close as possible to where that model was."
        ),
    )

    _deploy_unit(game, callidus, 0.0, 0.0)
    _deploy_unit(game, target_a, 6.0, 0.0)
    _deploy_unit(game, target_b, 8.0, 0.0)
    _deploy_unit(game, non_infantry, 10.0, 0.0)
    _deploy_unit(game, enemy, 40.0, 0.0)
    game.map.units = [callidus, target_a, target_b, non_infantry, enemy]
    game.rebuild_entity_registry()
    target_a_model = target_a.models[0]
    target_b_model = target_b.models[0]
    non_infantry_model = non_infantry.models[0]

    game._find_closest_valid_reposition_position = lambda *_args, **_kwargs: (12.0, 1.0, 0.0, 0.0)

    game._on_phase_start_optional_abilities(player=ia_player, phase=BattleRoundPhases.MOVEMENT_PHASE)

    request = _find_decoy_targets_request(game)
    assert request is not None
    assert any(bool(dict(getattr(opt, "payload", {}) or {}).get("action") == "skip") for opt in list(request.options or []))
    option_target_a = _find_option_id_for_target_model(request, target_a_model)
    assert option_target_a
    assert not _find_option_id_for_target_model(request, non_infantry_model)

    invalid = resolve_decision_command(game, request, "invalid-option-id", player_id=ia_player.id)
    assert not bool(getattr(invalid, "ok", False))

    applied = resolve_decision_command(game, request, option_target_a, player_id=ia_player.id)
    assert bool(getattr(applied, "ok", False))
    assert target_a_model not in list(target_a.models or [])
    sx, sy, sz, _ = callidus.models[0].get_location()
    assert round(float(sx), 3) == 12.0
    assert round(float(sy), 3) == 1.0
    assert round(float(sz), 3) == 0.0
    assert int(callidus.special_rules.get("enhancement_decoy_targets_used_count", 0) or 0) == 1
    assert int(callidus.special_rules.get("enhancement_decoy_targets_used_battle_round", 0) or 0) == 1
    assert int(callidus.special_rules.get("enhancement_decoy_targets_used_this_battle_round_count", 0) or 0) == 1

    game._on_phase_start_optional_abilities(player=ia_player, phase=BattleRoundPhases.MOVEMENT_PHASE)
    assert _find_decoy_targets_request(game) is None

    game.turn = 2
    game._on_phase_start_optional_abilities(player=ia_player, phase=BattleRoundPhases.MOVEMENT_PHASE)
    second_request = _find_decoy_targets_request(game)
    assert second_request is not None
    option_target_b = _find_option_id_for_target_model(second_request, target_b_model)
    assert option_target_b
    second_applied = resolve_decision_command(game, second_request, option_target_b, player_id=ia_player.id)
    assert bool(getattr(second_applied, "ok", False))
    assert int(callidus.special_rules.get("enhancement_decoy_targets_used_count", 0) or 0) == 2

    game.turn = 3
    game._on_phase_start_optional_abilities(player=ia_player, phase=BattleRoundPhases.MOVEMENT_PHASE)
    assert _find_decoy_targets_request(game) is None
