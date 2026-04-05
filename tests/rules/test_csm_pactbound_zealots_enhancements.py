from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id


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
        toughness: str = "4",
        leadership: str = "8",
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
                "T": str(toughness),
                "Sv": "3",
                "W": "4",
                "Ld": str(leadership),
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
    toughness: str = "4",
    leadership: str = "8",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            toughness=toughness,
            leadership=leadership,
        )
    )
    unit.possible_abilities = ["Dark Pacts"]
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _make_profile(*, melee: bool, attacks: str = "2", strength: str = "5"):
    weapon = Wargear(
        {
            "name": "Test Weapon",
            "type": "Melee" if melee else "Ranged",
            "range": "Melee" if melee else "24",
            "A": str(attacks),
            "BS_WS": "3+",
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str, description: str = "") -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(enhancement_name),
        faction_id="CSM",
        detachment="Pactbound Zealots",
        points=20,
        description=str(description or enhancement_name),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _build_game(*, phase: BattleRoundPhases):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    csm_army = Army("Chaos Space Marines", "Pactbound Zealots")
    csm_army.faction_id = "CSM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    csm_player = Player("CSM", control=PlayerControl.REMOTE, army=csm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = phase
    return game, csm_army, enemy_army, csm_player, enemy_player


def _bearer_model(unit: Unit, *, bearer_key: str) -> object:
    sr = dict(getattr(unit, "special_rules", {}) or {})
    bearer_id = str(sr.get(bearer_key, "") or sr.get("enhancement_bearer_model_id", "") or "")
    for model in list(getattr(unit, "models", []) or []):
        model_id = str(get_entity_id(model) or "")
        model_local_id = str(getattr(model, "id", getattr(model, "_id", "")) or "")
        if bearer_id and (model_id == bearer_id or (model_local_id and model_local_id == bearer_id)):
            return model
    return list(getattr(unit, "models", []) or [None])[0]


def test_pactbound_zealots_enhancement_descriptors_registered():
    expected = {
        "000008357002": ("Eye of Tzeentch", "gain_cp_on_dark_pact_passed_modified_roll_threshold"),
        "000008357003": (
            "Intoxicating Elixir",
            "bearer_gains_fnp_and_post_attack_select_hit_enemy_battleshock_test_on_passed_dark_pact",
        ),
        "000008357004": ("Orbs of Unlife", "roll_for_each_enemy_within_range_mortal_wounds_with_dark_pact_threshold_bonus"),
        "000008357005": ("Talisman of Burning Blood", "bearer_melee_attacks_strength_bonus_replaced_by_dark_pact_roll"),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_eye_of_tzeentch_gains_cp_on_passed_dark_pact_modified_roll_8_plus():
    game, csm_army, enemy_army, csm_player, _enemy_player = _build_game(phase=BattleRoundPhases.SHOOTING_PHASE)
    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        leadership="8",
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()
    _apply_enhancement(source, enhancement_id="000008357002", enhancement_name="Eye of Tzeentch")

    before_cp = int(csm_player.command_points or 0)
    with patch("warhammer40k_ai.units.unit_mixins.state_attachment_mixin.get_roll", return_value=8):
        applied = source.apply_dark_pacts_choice(
            game,
            choice="LETHAL HITS",
            phase_name="SHOOTING_PHASE",
            trigger="shooting",
        )
    after_cp = int(csm_player.command_points or 0)

    assert bool(applied)
    assert after_cp == before_cp + 1


def test_eye_of_tzeentch_does_not_gain_cp_below_threshold():
    game, csm_army, enemy_army, csm_player, _enemy_player = _build_game(phase=BattleRoundPhases.SHOOTING_PHASE)
    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        leadership="8",
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()
    _apply_enhancement(source, enhancement_id="000008357002", enhancement_name="Eye of Tzeentch")

    before_cp = int(csm_player.command_points or 0)
    with patch("warhammer40k_ai.units.unit_mixins.state_attachment_mixin.get_roll", return_value=7):
        applied = source.apply_dark_pacts_choice(
            game,
            choice="LETHAL HITS",
            phase_name="SHOOTING_PHASE",
            trigger="shooting",
        )
    after_cp = int(csm_player.command_points or 0)

    assert bool(applied)
    assert after_cp == before_cp


def test_intoxicating_elixir_grants_fnp_and_queues_post_shoot_battleshock_after_passed_dark_pact():
    game, csm_army, enemy_army, _csm_player, _enemy_player = _build_game(phase=BattleRoundPhases.SHOOTING_PHASE)
    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
        leadership="8",
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()
    _apply_enhancement(source, enhancement_id="000008357003", enhancement_name="Intoxicating Elixir")

    bearer = _bearer_model(source, bearer_key="enhancement_intoxicating_elixir_bearer_model_id")
    fnp_entries = list(source.has_feel_no_pain(bearer) or [])
    assert any(int(value) == 5 for value, _cond in fnp_entries)

    with patch("warhammer40k_ai.units.unit_mixins.state_attachment_mixin.get_roll", return_value=8):
        applied = source.apply_dark_pacts_choice(
            game,
            choice="LETHAL HITS",
            phase_name="SHOOTING_PHASE",
            trigger="shooting",
        )
    assert bool(applied)

    game._on_unit_shooting_resolved_post_shoot_battleshock(
        attacker_unit=source,
        hits_by_target={enemy: 1},
        hit_models_by_target={enemy: {bearer}},
    )
    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET
    ]
    assert len(pending) == 1
    context = dict(getattr(pending[0], "context", {}) or {})
    assert str(context.get("ability_name", "") or "") == "Intoxicating Elixir"
    options = list(getattr(pending[0], "options", []) or [])
    assert len(options) == 1
    assert str((options[0].payload or {}).get("unit_id", "") or "") == str(get_entity_id(enemy) or "")


def test_intoxicating_elixir_requires_passed_dark_pact_to_queue_battleshock():
    game, csm_army, enemy_army, _csm_player, _enemy_player = _build_game(phase=BattleRoundPhases.SHOOTING_PHASE)
    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()
    _apply_enhancement(source, enhancement_id="000008357003", enhancement_name="Intoxicating Elixir")

    source.special_rules["dark_pacts_active"] = True
    source.special_rules["dark_pacts_test_passed"] = False
    source.special_rules["dark_pacts_expires_phase"] = "SHOOTING_PHASE"
    bearer = _bearer_model(source, bearer_key="enhancement_intoxicating_elixir_bearer_model_id")
    game._on_unit_shooting_resolved_post_shoot_battleshock(
        attacker_unit=source,
        hits_by_target={enemy: 1},
        hit_models_by_target={enemy: {bearer}},
    )
    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET
    ]
    assert len(pending) == 0


def test_orbs_of_unlife_uses_dark_pact_threshold_bonus_for_bearer_only():
    game, csm_army, enemy_army, _csm_player, _enemy_player = _build_game(phase=BattleRoundPhases.FIGHT_PHASE)
    source = _make_unit(
        "Dark Apostle",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
    )
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    csm_army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()
    _apply_enhancement(source, enhancement_id="000008357004", enhancement_name="Orbs of Unlife")

    bearer = _bearer_model(source, bearer_key="enhancement_orbs_of_unlife_bearer_model_id")
    non_bearer = next(model for model in list(source.models or []) if model is not bearer)

    source.special_rules["dark_pacts_active"] = True
    source.special_rules["dark_pacts_test_passed"] = True
    source.special_rules["dark_pacts_expires_phase"] = "FIGHT_PHASE"
    specs_with_bonus = source.model_fight_phase_end_enemy_within_range_mortal_threshold_specs(bearer)
    assert len(specs_with_bonus) == 1
    assert int(specs_with_bonus[0].get("threshold", 0) or 0) == 3
    assert str(specs_with_bonus[0].get("mortal_wounds", "") or "").strip().lower() == "d3"

    non_bearer_specs = source.model_fight_phase_end_enemy_within_range_mortal_threshold_specs(non_bearer)
    assert non_bearer_specs == []

    source.special_rules["dark_pacts_test_passed"] = False
    specs_without_bonus = source.model_fight_phase_end_enemy_within_range_mortal_threshold_specs(bearer)
    assert len(specs_without_bonus) == 1
    assert int(specs_without_bonus[0].get("threshold", 0) or 0) == 4


def test_talisman_of_burning_blood_applies_base_bonus_and_replaces_with_d3_on_passed_dark_pact():
    game, csm_army, enemy_army, _csm_player, _enemy_player = _build_game(phase=BattleRoundPhases.FIGHT_PHASE)
    source = _make_unit(
        "Chaos Lord",
        keywords=["CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        leadership="8",
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="6",
    )
    csm_army.add_unit(source)
    enemy_army.add_unit(enemy)
    game.map.units = [source, enemy]
    game.rebuild_entity_registry()
    _apply_enhancement(source, enhancement_id="000008357005", enhancement_name="Talisman of Burning Blood")

    bearer = _bearer_model(source, bearer_key="enhancement_talisman_of_burning_blood_bearer_model_id")
    profile = _make_profile(melee=True, attacks="2", strength="5")

    preview_base = profile.preview_attack_count(enemy, bearer, publish_roll_event=False)
    assert int(preview_base.num_attacks) == 3
    wound_base = profile._wound_target_with_tracking(
        enemy,
        bearer,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    base_mods = list(wound_base.get("modifiers", []) or [])
    assert any("+1S from Talisman of Burning Blood" in str(mod) for mod in base_mods)

    with (
        patch("warhammer40k_ai.units.unit_mixins.state_attachment_mixin.get_roll", return_value=8),
        patch("warhammer40k_ai.rules.chaos_space_marines_detachments.get_roll", return_value=3),
    ):
        applied = source.apply_dark_pacts_choice(
            game,
            choice="LETHAL HITS",
            phase_name="FIGHT_PHASE",
            trigger="fight",
        )
    assert bool(applied)

    preview_dark_pact = profile.preview_attack_count(enemy, bearer, publish_roll_event=False)
    assert int(preview_dark_pact.num_attacks) == 5
    wound_dark_pact = profile._wound_target_with_tracking(
        enemy,
        bearer,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    dark_mods = list(wound_dark_pact.get("modifiers", []) or [])
    assert any("+3S from Talisman of Burning Blood" in str(mod) for mod in dark_mods)
    assert not any("+1S from Talisman of Burning Blood" in str(mod) for mod in dark_mods)
