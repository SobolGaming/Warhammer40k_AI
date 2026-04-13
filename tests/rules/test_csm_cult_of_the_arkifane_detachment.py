from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
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
        wounds: str = "10",
        leadership: str = "7",
        abilities=None,
    ) -> None:
        self.id = str(datasheet_id or f"ds_{name.lower().replace(' ', '_')}")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": str(leadership),
                "OC": "3",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
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
    wounds: str = "10",
    leadership: str = "7",
    abilities=None,
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
            wounds=wounds,
            leadership=leadership,
            abilities=abilities,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _deploy_unit(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    unit.deployed = True
    unit.reserve_status = "deployed"


def _make_profile(*, weapon_type: str, strength: str = "4", attacks: str = "1"):
    weapon = Wargear(
        {
            "name": "Test Weapon",
            "type": "Melee" if str(weapon_type).lower() == "melee" else "Ranged",
            "range": "Melee" if str(weapon_type).lower() == "melee" else "24",
            "A": str(attacks),
            "BS_WS": "3+",
            "S": str(strength),
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _make_ability(name: str, description: str) -> dict:
    return {
        "name": str(name),
        "description": str(description),
        "type": "Datasheet",
        "parameter": "",
    }


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    csm_army = Army.with_detachment("Chaos Space Marines", "Cult of the Arkifane")
    csm_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    csm_player = Player("CSM", control=PlayerControl.REMOTE, army=csm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)
    game.turn = 1
    game.current_player_index = 0
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, csm_army, enemy_army, csm_player, enemy_player


def _apply_enhancement(
    unit: Unit,
    *,
    enhancement_id: str,
    enhancement_name: str,
    description: str = "",
) -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=str(enhancement_name),
        faction_id="CSM",
        detachment="Cult of the Arkifane",
        points=20,
        description=str(description or enhancement_name),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _make_objective(*, x: float, y: float, controlling_player) -> Objective:
    location = ObjectivePoint(x=float(x), y=float(y), z=0.0, control_radius=3.0)
    location.controlling_player = controlling_player
    return Objective(
        "Test Objective",
        ObjectiveCategory.PRIMARY,
        0,
        "Test objective",
        lambda _game: False,
        location=location,
    )


def _find_bearer_and_other(unit: Unit):
    bearer_id = str(getattr(unit, "special_rules", {}).get("enhancement_bearer_model_id", "") or "")
    bearer = None
    for model in list(getattr(unit, "models", []) or []):
        if bearer_id and str(get_entity_id(model) or "") == bearer_id:
            bearer = model
            break
    if bearer is None:
        for model in list(getattr(unit, "models", []) or []):
            alive_attr = getattr(model, "is_alive", False)
            if bool(alive_attr() if callable(alive_attr) else alive_attr):
                bearer = model
                break
    other = next(
        (
            model
            for model in list(getattr(unit, "models", []) or [])
            if model is not bearer
            and bool(
                getattr(model, "is_alive", False)()
                if callable(getattr(model, "is_alive", False))
                else getattr(model, "is_alive", False)
            )
        ),
        None,
    )
    return bearer, other


def _find_choose_quarry_request(game: Game, *, ability: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(req, "context", {}) or {})
        if str(context.get("ability", "") or "") == str(ability):
            return req
    return None


def _find_target_option(request, *, target_unit_id: str):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == str(target_unit_id):
            return option
    return None


def test_cult_of_the_arkifane_enhancement_descriptors_registered():
    expected = {
        "000010743002": ("Wyredjinn", "command_phase_cp_roll_with_controlled_objective_bonus"),
        "000010743003": ("Cybinfernal Font", "grant_soul_forge_keyword_to_bearer_unit"),
        "000010743004": ("Mark of the Soul Forges", "critical_hit_threshold_bonus"),
        "000010743005": ("Crown of Worms", "increase_warpsmith_ability_range"),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_soul_forge_boons_assigns_keywords_to_eligible_units():
    army = Army.with_detachment("Chaos Space Marines", "Cult of the Arkifane")
    army.faction_id = "CSM"

    forgefiend = _make_unit(
        "Forgefiend",
        keywords=["HERETIC ASTARTES", "VEHICLE"],
        faction_keywords=["HERETIC ASTARTES"],
        toughness="10",
    )
    lord_discordant = _make_unit(
        "Lord Discordant On Helstalker",
        keywords=["HERETIC ASTARTES", "CHARACTER", "MOUNTED"],
        faction_keywords=["HERETIC ASTARTES"],
        toughness="7",
    )
    vashtorr = _make_unit(
        "Vashtorr The Arkifane",
        keywords=["HERETIC ASTARTES", "CHARACTER", "EPIC HERO", "MONSTER"],
        faction_keywords=["HERETIC ASTARTES"],
        toughness="9",
    )
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )

    for unit in (forgefiend, lord_discordant, vashtorr, legionaries):
        army.add_unit(unit)

    army.validate_detachment_rules()

    assert forgefiend.has_keyword("DAEMON")
    assert forgefiend.has_keyword("SOUL FORGE")
    assert not lord_discordant.has_keyword("DAEMON")
    assert lord_discordant.has_keyword("SOUL FORGE")
    assert not vashtorr.has_keyword("DAEMON")
    assert vashtorr.has_keyword("SOUL FORGE")
    assert not legionaries.has_keyword("DAEMON")
    assert not legionaries.has_keyword("SOUL FORGE")

    forgefiend_keywords = list(forgefiend.special_rules.get("ability_added_keywords", []) or [])
    assert forgefiend_keywords.count("DAEMON") == 1
    assert forgefiend_keywords.count("SOUL FORGE") == 1


def test_soul_forge_boons_grants_five_plus_invulnerable_save():
    army = Army.with_detachment("Chaos Space Marines", "Cult of the Arkifane")
    army.faction_id = "CSM"

    forgefiend = _make_unit(
        "Forgefiend",
        keywords=["HERETIC ASTARTES", "VEHICLE"],
        faction_keywords=["HERETIC ASTARTES"],
        toughness="10",
    )
    legionaries = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )

    army.add_unit(forgefiend)
    army.add_unit(legionaries)

    inv_value, inv_source = forgefiend.get_model_invulnerable_save_override(forgefiend.models[0])
    other_value, other_source = legionaries.get_model_invulnerable_save_override(legionaries.models[0])

    assert inv_value == 5
    assert inv_source == "Soul Forge Boons"
    assert other_value is None
    assert other_source is None


def test_wyredjinn_command_phase_cp_roll_gains_cp_with_controlled_objective_bonus():
    game, csm_army, _enemy_army, csm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0

    source = _make_unit(
        "Chaos Lord",
        keywords=["CHAOS LORD", "CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(source)
    _deploy_unit(source, 0.0, 0.0)
    game.map.units = [source]
    game.map.add_objective(_make_objective(x=0.0, y=0.0, controlling_player=csm_player))
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000010743002", enhancement_name="Wyredjinn")

    before_cp = int(csm_player.command_points or 0)
    with patch("warhammer40k_ai.rules.enhancement.get_roll", return_value=3):
        game._on_phase_start_command_phase_cp_rolls(player=csm_player, phase=game.phase)
    after_cp = int(csm_player.command_points or 0)

    assert after_cp == before_cp + 1


def test_wyredjinn_requires_controlled_objective_bonus_for_three_to_succeed():
    game, csm_army, _enemy_army, csm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0

    source = _make_unit(
        "Chaos Lord",
        keywords=["CHAOS LORD", "CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(source)
    _deploy_unit(source, 0.0, 0.0)
    game.map.units = [source]
    game.map.add_objective(_make_objective(x=10.0, y=10.0, controlling_player=csm_player))
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000010743002", enhancement_name="Wyredjinn")

    before_cp = int(csm_player.command_points or 0)
    with patch("warhammer40k_ai.rules.enhancement.get_roll", return_value=3):
        game._on_phase_start_command_phase_cp_rolls(player=csm_player, phase=game.phase)
    after_cp = int(csm_player.command_points or 0)

    assert after_cp == before_cp


def test_cybinfernal_font_grants_soul_forge_and_detachment_invulnerable_save():
    game, csm_army, _enemy_army, _csm_player, _enemy_player = _build_game()
    source = _make_unit(
        "Legionaries",
        keywords=["HERETIC ASTARTES", "INFANTRY"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    csm_army.add_unit(source)
    game.map.units = [source]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000010743003", enhancement_name="Cybinfernal Font")

    assert source.has_keyword("SOUL FORGE")
    inv_value, inv_source = source.get_model_invulnerable_save_override(source.models[0])
    assert inv_value == 5
    assert inv_source == "Soul Forge Boons"


def test_mark_of_the_soul_forges_applies_only_to_bearer_attacks():
    game, csm_army, enemy_army, _csm_player, _enemy_player = _build_game()
    source = _make_unit(
        "Chaos Lord",
        keywords=["CHAOS LORD", "CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        model_count=2,
    )
    target = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness="5",
    )
    csm_army.add_unit(source)
    enemy_army.add_unit(target)
    game.map.units = [source, target]
    game.rebuild_entity_registry()

    _apply_enhancement(
        source,
        enhancement_id="000010743004",
        enhancement_name="Mark of the Soul Forges",
    )
    bearer, other = _find_bearer_and_other(source)
    assert bearer is not None
    assert other is not None

    profile = _make_profile(weapon_type="ranged")
    bearer_attack: dict = {}
    bearer_hit = profile._hit_target_with_tracking(
        target,
        bearer,
        bearer_attack,
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(bearer_attack.get("crit_hit")) is True
    assert int(bearer_hit.get("crit_threshold") or 0) == 5
    assert any("Mark of the Soul Forges" in str(effect or "") for effect in list(bearer_hit.get("special_effects", []) or []))

    other_attack: dict = {}
    other_hit = profile._hit_target_with_tracking(
        target,
        other,
        other_attack,
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(other_attack.get("crit_hit")) is False
    assert int(other_hit.get("crit_threshold") or 0) == 6


def test_crown_of_worms_extends_master_of_mechanisms_selection_range():
    game, csm_army, _enemy_army, csm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0

    ability = _make_ability(
        "Master of Mechanisms",
        'In your Command phase, select one friendly VEHICLE unit within 3"; it regains D3 wounds and gets +1 to hit.',
    )
    source = _make_unit(
        "Warpsmith",
        keywords=["WARPSMITH", "CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        abilities=[ability],
    )
    target_vehicle = _make_unit(
        "Forgefiend",
        keywords=["HERETIC ASTARTES", "VEHICLE"],
        faction_keywords=["HERETIC ASTARTES"],
        toughness="10",
    )
    csm_army.add_unit(source)
    csm_army.add_unit(target_vehicle)
    _deploy_unit(source, 0.0, 0.0)
    _deploy_unit(target_vehicle, 5.0, 0.0)
    game.map.units = [source, target_vehicle]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000010743005", enhancement_name="Crown of Worms")

    game._on_phase_start_master_of_mechanisms(player=csm_player, phase=game.phase)
    request = _find_choose_quarry_request(game, ability="master_of_mechanisms")
    assert request is not None
    assert int((request.context or {}).get("range", 0) or 0) == 6
    assert _find_target_option(request, target_unit_id=str(get_entity_id(target_vehicle) or "")) is not None


def test_crown_of_worms_extends_enrage_machine_spirits_selection_range():
    game, csm_army, enemy_army, csm_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0

    ability = _make_ability(
        "Enrage Machine Spirits",
        'At the end of your Movement phase, you can select one enemy VEHICLE unit within 3" of this model. That enemy unit must take a Battle-shock test.',
    )
    source = _make_unit(
        "Warpsmith",
        keywords=["WARPSMITH", "CHARACTER", "INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
        abilities=[ability],
    )
    enemy_vehicle = _make_unit(
        "Enemy Tank",
        faction_name="Enemy",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
        toughness="10",
    )
    csm_army.add_unit(source)
    enemy_army.add_unit(enemy_vehicle)
    _deploy_unit(source, 0.0, 0.0)
    _deploy_unit(enemy_vehicle, 5.0, 0.0)
    game.map.units = [source, enemy_vehicle]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000010743005", enhancement_name="Crown of Worms")

    game._on_phase_end_enrage_machine_spirits(player=csm_player, phase=game.phase)
    request = _find_choose_quarry_request(game, ability="enrage_machine_spirits")
    assert request is not None
    assert int((request.context or {}).get("range", 0) or 0) == 6
    assert _find_target_option(request, target_unit_id=str(get_entity_id(enemy_vehicle) or "")) is not None
