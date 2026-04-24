from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(self, name: str, *, faction_name: str = "Adeptus Mechanicus", keywords=None, faction_keywords=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "4",
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


def _make_unit(name: str, *, faction_name: str = "Adeptus Mechanicus", keywords=None, faction_keywords=None) -> Unit:
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


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    leader.can_be_attached_to = [bodyguard.name]
    for unit in (bodyguard, leader):
        invalidate = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate):
            invalidate()


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)


def _make_objective(name: str, x: float, y: float) -> Objective:
    point = ObjectivePoint(x=float(x), y=float(y), z=0.0, control_radius=3.0)
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description=f"Control {name}",
        conditions=lambda _game: False,
        location=point,
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    admech_army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Explorator Maniple")
    admech_army.faction_id = "ADM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    admech_player = Player("AdMech", PlayerControl.REMOTE, army=admech_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(admech_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    objective_a = _make_objective("Alpha", 10.0, 10.0)
    objective_b = _make_objective("Beta", 30.0, 10.0)
    game.objectives = [objective_a, objective_b]
    game.map.objectives = [objective_a, objective_b]
    return game, admech_army, enemy_army, admech_player, enemy_player, objective_a, objective_b


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="ADM",
        detachment="Explorator Maniple",
        points=0,
        description="",
    ).apply_to_unit(unit)


def _select_acquisition_objective(game: Game, objective, *, player, army) -> None:
    mgr = army.adeptus_mechanicus_detachments
    selection = mgr.select_acquisition_objective(
        str(get_entity_id(objective) or ""),
        game=game,
        player=player,
        battle_round=int(getattr(game, "turn", 0) or 0),
    )
    assert isinstance(selection, dict)


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


def _ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
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


def test_explorator_enhancement_descriptors_registered():
    expected = {
        "000008568002": ("Magos", "roll_for_command_point_gain_if_bearer_within_acquisition_objective"),
        "000008568003": ("Genetor", "grant_invulnerable_save_to_bearer_led_unit_within_acquisition_objective"),
        "000008568004": (
            "Logis",
            "add_hit_roll_bonus_for_bearer_led_unit_vs_target_within_acquisition_objective",
        ),
        "000008568005": ("Artisan", "set_one_hit_wound_or_save_roll_to_unmodified_six"),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(getattr(desc, "name", "") or "") == name
        assert str(getattr(desc, "effect", "") or "") == effect


def test_magos_grants_cp_on_4plus_when_bearer_within_acquisition_objective():
    game, admech_army, _enemy_army, admech_player, _enemy_player, obj_a, _obj_b = _build_game()
    source = _make_unit(
        "Tech-priest Manipulus",
        keywords=["CHARACTER", "INFANTRY", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(source)
    _set_unit_position(source, 10.0, 10.0)
    game.map.units = [source]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000008568002", enhancement_name="Magos")
    _select_acquisition_objective(game, obj_a, player=admech_player, army=admech_army)

    before_cp = int(getattr(admech_player, "command_points", 0) or 0)
    mgr = admech_army.adeptus_mechanicus_detachments
    with patch("warhammer40k_ai.rules.adeptus_mechanicus_detachments.get_roll", return_value=4):
        mgr.on_command_phase_end(game=game, player=admech_player)
    assert int(getattr(admech_player, "command_points", 0) or 0) == before_cp + 1


def test_magos_does_not_grant_cp_when_bearer_not_within_acquisition_objective():
    game, admech_army, _enemy_army, admech_player, _enemy_player, obj_a, _obj_b = _build_game()
    source = _make_unit(
        "Tech-priest Manipulus",
        keywords=["CHARACTER", "INFANTRY", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    admech_army.add_unit(source)
    _set_unit_position(source, 24.0, 24.0)
    game.map.units = [source]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000008568002", enhancement_name="Magos")
    _select_acquisition_objective(game, obj_a, player=admech_player, army=admech_army)

    before_cp = int(getattr(admech_player, "command_points", 0) or 0)
    mgr = admech_army.adeptus_mechanicus_detachments
    with patch("warhammer40k_ai.rules.adeptus_mechanicus_detachments.get_roll", return_value=6):
        mgr.on_command_phase_end(game=game, player=admech_player)
    assert int(getattr(admech_player, "command_points", 0) or 0) == before_cp


def test_genetor_grants_invulnerable_save_only_while_leading_and_on_acquisition_objective():
    game, admech_army, enemy_army, admech_player, _enemy_player, obj_a, _obj_b = _build_game()
    leader = _make_unit(
        "Tech-priest Dominus",
        keywords=["CHARACTER", "INFANTRY", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    bodyguard = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(leader)
    admech_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, leader)
    _set_unit_position(bodyguard, 10.0, 10.0)
    _set_unit_position(enemy, 25.0, 10.0)
    game.map.units = [leader, bodyguard, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(leader, enhancement_id="000008568003", enhancement_name="Genetor")
    _select_acquisition_objective(game, obj_a, player=admech_player, army=admech_army)

    profile = _ranged_profile()
    attack_instance = {"attacker_model": enemy.models[0], "attacker_unit": enemy, "target_unit": bodyguard}
    profile._save_with_tracking(
        bodyguard.models[0],
        attack_instance,
        ap=-3,
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(attack_instance.get("inv_save_override", 0) or 0) == 4
    assert "Genetor" in str(attack_instance.get("inv_save_override_reason", "") or "")


def test_logis_grants_hit_bonus_against_targets_within_acquisition_objective():
    game, admech_army, enemy_army, admech_player, _enemy_player, obj_a, _obj_b = _build_game()
    leader = _make_unit(
        "Tech-priest Dominus",
        keywords=["CHARACTER", "INFANTRY", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    bodyguard = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(leader)
    admech_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, leader)
    _set_unit_position(bodyguard, 24.0, 10.0)
    _set_unit_position(enemy, 10.0, 10.0)
    game.map.units = [leader, bodyguard, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(leader, enhancement_id="000008568004", enhancement_name="Logis")
    _select_acquisition_objective(game, obj_a, player=admech_player, army=admech_army)

    profile = _ranged_profile()
    hit = profile._hit_target_with_tracking(
        enemy,
        bodyguard.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("Logis" in str(reason) for reason in list(hit.get("modifiers", []) or []))
    assert int(hit.get("final_needed", 0) or 0) == 2


def test_artisan_sets_hit_roll_to_unmodified_six_once_per_phase_and_requires_objective():
    game, admech_army, enemy_army, admech_player, _enemy_player, obj_a, _obj_b = _build_game()
    admech_player.control = PlayerControl.LOCAL
    leader = _make_unit(
        "Tech-priest Dominus",
        keywords=["CHARACTER", "INFANTRY", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    bodyguard = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(leader)
    admech_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, leader)
    _set_unit_position(bodyguard, 10.0, 10.0)
    _set_unit_position(enemy, 24.0, 10.0)
    game.map.units = [leader, bodyguard, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(leader, enhancement_id="000008568005", enhancement_name="Artisan")
    _select_acquisition_objective(game, obj_a, player=admech_player, army=admech_army)

    specs = list(bodyguard.leading_unmodified_six_specs() or [])
    artisan_specs = [spec for spec in specs if str(spec.get("source", "") or "") == "Artisan"]
    assert len(artisan_specs) == 1
    assert tuple(artisan_specs[0].get("allowed_roll_types", ()) or ()) == ("hit", "save", "wound")

    def _provider(**kwargs):
        options = list(kwargs.get("options", []) or [])
        if not options:
            return "skip"
        return str(options[0].get("ability_key", "") or "")

    game.install_decision_providers(leading_unmodified_six_provider=_provider)
    profile = _ranged_profile()
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
        first = profile._hit_target_with_tracking(enemy, bodyguard.models[0], {"_aura_attack_mods": _aura_stub()})
        second = profile._hit_target_with_tracking(enemy, bodyguard.models[0], {"_aura_attack_mods": _aura_stub()})
    assert int(first.get("roll", 0) or 0) == 6
    assert int(second.get("roll", 0) or 0) == 2

    game.turn = 2
    _set_unit_position(bodyguard, 24.0, 24.0)
    for unit in (leader, bodyguard):
        invalidate = getattr(unit, "_invalidate_ability_cache", None)
        if callable(invalidate):
            invalidate()
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
        third = profile._hit_target_with_tracking(enemy, bodyguard.models[0], {"_aura_attack_mods": _aura_stub()})
    assert int(third.get("roll", 0) or 0) == 2


def test_artisan_sets_save_roll_to_unmodified_six_once_per_phase():
    game, admech_army, enemy_army, admech_player, _enemy_player, obj_a, _obj_b = _build_game()
    admech_player.control = PlayerControl.LOCAL
    leader = _make_unit(
        "Tech-priest Dominus",
        keywords=["CHARACTER", "INFANTRY", "TECH-PRIEST"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    bodyguard = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    admech_army.add_unit(leader)
    admech_army.add_unit(bodyguard)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, leader)
    _set_unit_position(bodyguard, 10.0, 10.0)
    _set_unit_position(enemy, 24.0, 10.0)
    game.map.units = [leader, bodyguard, enemy]
    game.rebuild_entity_registry()

    _apply_enhancement(leader, enhancement_id="000008568005", enhancement_name="Artisan")
    _select_acquisition_objective(game, obj_a, player=admech_player, army=admech_army)

    def _provider(**kwargs):
        options = list(kwargs.get("options", []) or [])
        if not options:
            return "skip"
        return str(options[0].get("ability_key", "") or "")

    game.install_decision_providers(leading_unmodified_six_provider=_provider)
    profile = _ranged_profile()
    attack_context = {"attacker_model": enemy.models[0], "attacker_unit": enemy, "target_unit": bodyguard}
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
        first = profile._save_with_tracking(
            bodyguard.models[0],
            dict(attack_context),
            ap=-1,
            roll_value=2,
            allow_rerolls=False,
            log_roll=False,
        )
        second = profile._save_with_tracking(
            bodyguard.models[0],
            dict(attack_context),
            ap=-1,
            roll_value=2,
            allow_rerolls=False,
            log_roll=False,
        )
    assert int(first.get("roll", 0) or 0) == 6
    assert int(second.get("roll", 0) or 0) == 2
