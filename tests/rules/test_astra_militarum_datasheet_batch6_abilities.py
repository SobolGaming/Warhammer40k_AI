from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


LINE_BREAKER_TEXT = (
    "When making ranged attacks with its demolisher battle cannon, this model can target enemy units within "
    "Engagement Range of it (provided no other friendly units are also within Engagement Range of that enemy "
    "unit). In addition, when making ranged attacks, this model does not suffer the penalty to its Hit rolls "
    "for being within Engagement Range of one or more enemy units."
)
URBAN_WARFARE_TEXT = (
    "Each time a ranged attack targets this model, if this model has the Benefit of Cover against that attack, "
    "subtract 1 from the Damage characteristic of that attack."
)
GUNG_HO_EXECUTIONERS_TEXT = (
    "Each time this model makes an attack with its executioner plasma cannon that targets a unit that is Below "
    "Half-strength, add 1 to the Hit roll."
)
WITHERING_HAIL_TEXT = (
    "In your Shooting phase, after this model has shot, select one enemy unit hit by one or more of those "
    "attacks made with its exterminator autocannon. Until the end of the phase, each time a friendly ASTRA "
    "MILITARUM unit makes an attack that targets that enemy unit, improve the Armour Penetration characteristic "
    "of that attack by 1. The same enemy unit can only be affected by this ability once per phase."
)
MOW_DOWN_THE_ENEMY_TEXT = (
    "Each time this model makes an attack with its punisher gatling cannon that targets an enemy unit (excluding "
    "MONSTERS and VEHICLES), that attack has the [DEVASTATING WOUNDS] ability."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        datasheet_id: str | None = None,
        model_count: int = 1,
        wounds: int = 12,
        save: int = 3,
    ):
        self.id = datasheet_id or name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "11",
                "Sv": str(int(save)),
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "3",
                "base_size": "80mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.attached_to = []
        self.attached_to_names = []
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""


def _make_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    datasheet_id: str | None = None,
    model_count: int = 1,
    wounds: int = 12,
    save: int = 3,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            datasheet_id=datasheet_id,
            model_count=model_count,
            wounds=wounds,
            save=save,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game() -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    am_army = Army.with_detachment("Astra Militarum", detachment_type="Combined Regiment")
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    am_player = Player("AM", PlayerControl.REMOTE, army=am_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 2
    return game, am_army, enemy_army, am_player, enemy_player


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _find_quarry_request(game: Game, ability: str):
    return next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == ability
        ),
        None,
    )


def test_line_breaker_allows_demolisher_into_own_engagement_and_ignores_bgnt_penalty():
    game, am_army, enemy_army, _am_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    demolisher = _make_unit(
        "Leman Russ Demolisher",
        abilities=[{"name": "Line-breaker", "description": LINE_BREAKER_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["VEHICLE", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="leman-russ-demolisher",
    )
    target = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], datasheet_id="enemy-unit")
    other_friendly = _make_unit(
        "Friendly Squad",
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="friendly-squad",
        wounds=2,
        save=4,
    )

    am_army.add_unit(demolisher)
    am_army.add_unit(other_friendly)
    enemy_army.add_unit(target)
    _deploy(demolisher, 0.0, 0.0)
    _deploy(target, 0.4, 0.0)
    _deploy(other_friendly, 20.0, 20.0)
    _register_units(game, demolisher, other_friendly, target)

    profile = WargearProfile(
        "default",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "10",
            "AP": "-2",
            "D": "3",
            "description": "Blast",
        },
        parent_wargear=SimpleNamespace(name="Demolisher Battle Cannon", is_ranged=lambda: True, is_melee=lambda: False),
    )

    assert demolisher.has_siege_shield() is True
    assert demolisher.ignores_big_guns_never_tire_hit_penalty() is True
    assert demolisher._can_model_shoot_weapon_at_target(demolisher.models[0], profile, target, game.map) is True

    _deploy(other_friendly, 0.5, 0.0)
    assert demolisher._can_model_shoot_weapon_at_target(demolisher.models[0], profile, target, game.map) is False


def test_urban_warfare_reduces_ranged_damage_only_while_in_cover():
    eradicator = _make_unit(
        "Leman Russ Eradicator",
        abilities=[{"name": "Urban Warfare", "description": URBAN_WARFARE_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["VEHICLE", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="leman-russ-eradicator",
    )
    attacker = _make_unit("Enemy Tank", keywords=["VEHICLE"], faction_keywords=["ENEMY"], datasheet_id="enemy-tank")

    profile = WargearProfile(
        "default",
        {
            "range": "48",
            "A": "1",
            "BS_WS": "4+",
            "S": "10",
            "AP": "-1",
            "D": "2",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Nova Cannon", is_ranged=lambda: True, is_melee=lambda: False),
    )

    covered = profile._damage_target_with_tracking(
        eradicator.models[0],
        attacker.models[0],
        {"mortal_wound": False, "mortal_wound_in_addition": False, "benefit_of_cover": True},
    )
    uncovered = profile._damage_target_with_tracking(
        eradicator.models[0],
        attacker.models[0],
        {"mortal_wound": False, "mortal_wound_in_addition": False},
    )
    ignored_cover = profile._damage_target_with_tracking(
        eradicator.models[0],
        attacker.models[0],
        {"mortal_wound": False, "mortal_wound_in_addition": False, "benefit_of_cover": True, "ignores_cover": True},
    )

    assert covered["damage_applied"] == 1
    assert uncovered["damage_applied"] == 2
    assert ignored_cover["damage_applied"] == 2


def test_gung_ho_executioners_hit_bonus_applies_only_to_executioner_plasma_cannon_vs_below_half_strength(monkeypatch):
    game, am_army, enemy_army, _am_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    executioner = _make_unit(
        "Leman Russ Executioner",
        abilities=[
            {
                "name": "Gung-ho Executioners",
                "description": GUNG_HO_EXECUTIONERS_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["VEHICLE", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="leman-russ-executioner",
    )
    below_half_target = _make_unit("Below Half", keywords=["INFANTRY"], faction_keywords=["ENEMY"], datasheet_id="below-half")
    full_target = _make_unit("Full Strength", keywords=["INFANTRY"], faction_keywords=["ENEMY"], datasheet_id="full-target")
    below_half_target.is_below_half_strength = lambda: True
    full_target.is_below_half_strength = lambda: False

    am_army.add_unit(executioner)
    enemy_army.add_unit(below_half_target)
    enemy_army.add_unit(full_target)
    _deploy(executioner, 0.0, 0.0)
    _deploy(below_half_target, 10.0, 0.0)
    _deploy(full_target, 12.0, 0.0)
    _register_units(game, executioner, below_half_target, full_target)

    executioner_profile = WargearProfile(
        "default",
        {
            "range": "36",
            "A": "1",
            "BS_WS": "4+",
            "S": "8",
            "AP": "-2",
            "D": "2",
            "description": "",
        },
        parent_wargear=SimpleNamespace(
            name="Executioner Plasma Cannon",
            is_ranged=lambda: True,
            is_melee=lambda: False,
            is_ignores_cover=lambda: False,
        ),
    )
    other_profile = WargearProfile(
        "default",
        {
            "range": "36",
            "A": "1",
            "BS_WS": "4+",
            "S": "8",
            "AP": "-1",
            "D": "2",
            "description": "",
        },
        parent_wargear=SimpleNamespace(
            name="Hull Lascannon",
            is_ranged=lambda: True,
            is_melee=lambda: False,
            is_ignores_cover=lambda: False,
        ),
    )

    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda _expr: 3)

    below_half_result = executioner_profile.attack(below_half_target, executioner.models[0], game_map=game.map)
    full_result = executioner_profile.attack(full_target, executioner.models[0], game_map=game.map)
    other_weapon_result = other_profile.attack(below_half_target, executioner.models[0], game_map=game.map)

    assert below_half_result is not None
    assert full_result is not None
    assert other_weapon_result is not None
    assert int(below_half_result.total_hits or 0) == 1
    assert int(full_result.total_hits or 0) == 0
    assert int(other_weapon_result.total_hits or 0) == 0


def test_withering_hail_requires_exterminator_autocannon_hit_and_applies_after_selection():
    game, am_army, enemy_army, am_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    exterminator = _make_unit(
        "Leman Russ Exterminator",
        abilities=[{"name": "Withering Hail", "description": WITHERING_HAIL_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["VEHICLE", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="leman-russ-exterminator",
    )
    ally = _make_unit(
        "Friendly Infantry",
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="friendly-infantry",
        wounds=2,
        save=4,
    )
    valid_target = _make_unit("Marked Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"], datasheet_id="marked-target")
    wrong_weapon_target = _make_unit("Wrong Weapon", keywords=["INFANTRY"], faction_keywords=["ENEMY"], datasheet_id="wrong-weapon")

    am_army.add_unit(exterminator)
    am_army.add_unit(ally)
    enemy_army.add_unit(valid_target)
    enemy_army.add_unit(wrong_weapon_target)
    _deploy(exterminator, 0.0, 0.0)
    _deploy(ally, 2.0, 0.0)
    _deploy(valid_target, 12.0, 0.0)
    _deploy(wrong_weapon_target, 14.0, 0.0)
    _register_units(game, exterminator, ally, valid_target, wrong_weapon_target)

    autocannon_key = exterminator._normalize_keyword_phrase("Exterminator Autocannon") or "exterminator autocannon"
    heavy_bolter_key = exterminator._normalize_keyword_phrase("Heavy Bolter") or "heavy bolter"

    game._on_unit_shooting_resolved_post_shoot_ap_bonus(
        attacker_unit=exterminator,
        hits_by_target={valid_target: 1, wrong_weapon_target: 1},
        hit_models_by_target_weapon={
            valid_target: {autocannon_key: [exterminator.models[0]]},
            wrong_weapon_target: {heavy_bolter_key: [exterminator.models[0]]},
        },
    )

    request = _find_quarry_request(game, "post_shoot_ap_bonus")
    assert request is not None
    option_ids = {str((opt.payload or {}).get("target_unit_id", "") or "") for opt in list(request.options or [])}
    assert str(get_entity_id(valid_target) or "") in option_ids
    assert str(get_entity_id(wrong_weapon_target) or "") not in option_ids

    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(valid_target) or "")
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=am_player.id)
    assert bool(getattr(result, "ok", False)) is True

    profile = WargearProfile(
        "default",
        {
            "range": "36",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Battle Cannon", is_ranged=lambda: True, is_melee=lambda: False),
    )

    assert profile.get_effective_ap(ally.models[0], valid_target) == -1
    assert profile.get_effective_ap(ally.models[0], wrong_weapon_target) == 0


def test_mow_down_the_enemy_grants_devastating_wounds_only_to_punisher_gatling_cannon_vs_non_monster_vehicle():
    punisher = _make_unit(
        "Leman Russ Punisher",
        abilities=[{"name": "Mow Down the Enemy", "description": MOW_DOWN_THE_ENEMY_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["VEHICLE", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        datasheet_id="leman-russ-punisher",
    )
    infantry_target = _make_unit("Infantry", keywords=["INFANTRY"], faction_keywords=["ENEMY"], datasheet_id="infantry-target")
    monster_target = _make_unit("Monster", keywords=["MONSTER"], faction_keywords=["ENEMY"], datasheet_id="monster-target")

    punisher_profile = WargearProfile(
        "default",
        {
            "range": "24",
            "A": "20",
            "BS_WS": "4+",
            "S": "6",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Punisher Gatling Cannon", is_ranged=lambda: True, is_melee=lambda: False),
    )
    other_profile = WargearProfile(
        "default",
        {
            "range": "36",
            "A": "3",
            "BS_WS": "4+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Heavy Bolter", is_ranged=lambda: True, is_melee=lambda: False),
    )

    infantry_bonus = punisher.get_attack_keyword_bonuses(
        target=infantry_target,
        attack_type="ranged",
        model=punisher.models[0],
        weapon_profile=punisher_profile,
    )
    monster_bonus = punisher.get_attack_keyword_bonuses(
        target=monster_target,
        attack_type="ranged",
        model=punisher.models[0],
        weapon_profile=punisher_profile,
    )
    other_weapon_bonus = punisher.get_attack_keyword_bonuses(
        target=infantry_target,
        attack_type="ranged",
        model=punisher.models[0],
        weapon_profile=other_profile,
    )

    assert bool(infantry_bonus.get("devastating_wounds", False)) is True
    assert bool(monster_bonus.get("devastating_wounds", False)) is False
    assert bool(other_weapon_bonus.get("devastating_wounds", False)) is False
