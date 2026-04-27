from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


MEKANIAK_TEXT = (
    "At the end of your Movement phase, you can select one friendly Orks Vehicle model within 3\" of this model. "
    "That VEHICLE model regains up to D3 lost wounds, and, until the start of your next Movement phase, each time that "
    "VEHICLE model makes an attack, add 1 to the Hit roll. Each model can only be selected for this ability once per turn."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        cost: int = 100,
        wounds: str = "4",
        movement: str = "6",
    ) -> None:
        slug = str(name or "unit").lower().replace(" ", "_").replace("'", "")
        self.id = f"mock_{slug}"
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        faction_kw = {str(value or "").upper() for value in list(self.faction_keywords or [])}
        self.faction_data = {"name": "Orks" if "ORKS" in faction_kw else "Enemy"}
        count = max(1, int(model_count or 1))
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": int(cost)}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": "5",
                "Sv": "4",
                "W": str(wounds),
                "Ld": "7",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "0",
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
    abilities=None,
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: str = "4",
    movement: str = "6",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            movement=movement,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _build_game(*, ork_units: list[Unit], enemy_units: list[Unit]):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ork_army = Army.with_detachment("Orks", detachment_type="Speedwaaagh!")
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "ENEMY"
    ork_player = Player("Ork Player", control=PlayerControl.REMOTE, army=ork_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ork_player)
    game.add_player(enemy_player)
    game.turn = 1
    game.current_player_index = 0
    game.current_player_idx = 0
    for unit in list(ork_units or []):
        ork_army.add_unit(unit)
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)
    game.map.units = list(ork_units or []) + list(enemy_units or [])
    game.rebuild_entity_registry()
    return game, ork_player, enemy_player, ork_army


def _set_unit_location(unit: Unit, x: float, y: float, *, spacing: float = 1.0) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _apply_enhancement(unit: Unit, enhancement_id: str, enhancement_name: str) -> None:
    enhancement = Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="ORK",
        detachment="Speedwaaagh!",
        points=10,
        description="",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)


def _find_master_request(game: Game, *, source_unit: Unit):
    source_id = str(get_entity_id(source_unit) or "")
    for request in list(game.decision_queue.list() or []):
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") != "master_of_mechanisms":
            continue
        if str(context.get("source_unit_id", "") or "") == source_id:
            return request
    return None


def _option_for_model(request, model):
    model_id = str(get_entity_id(model) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_model_id", "") or "") == model_id:
            return option
    return None


def _ranged_weapon(name: str, *, attacks: str = "2", skill: str = "5+", description: str = "") -> Wargear:
    return Wargear(
        {
            "name": name,
            "type": "Ranged",
            "range": "24",
            "A": str(attacks),
            "BS_WS": str(skill),
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": str(description or ""),
        }
    )


def test_speedwaaagh_enhancement_descriptors_are_structured():
    expected = {
        "000010795002": ("Kustom Shokk Box", "turbo_move_through_terrain_horizontally"),
        "000010795003": ("Dakkamek", "mekaniak_selected_vehicle_model_ranged_weapons_gain_keywords"),
        "000010795004": ("Supa-burny Fuel", "set_bearer_weapon_attacks_characteristics"),
        "000010795005": ("Master Meknologist", "improve_bearer_ranged_ballistic_skill"),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert descriptor.name == name
        assert descriptor.effect == effect


def test_kustom_shokk_box_adds_turbo_advance_move_through_terrain_and_cleans_up():
    wartrike = _make_unit(
        "Deffkilla Wartrike",
        keywords=["ORKS", "MOUNTED", "CHARACTER", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
        movement="12",
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, army = _build_game(ork_units=[wartrike], enemy_units=[enemy])
    _set_unit_location(wartrike, 0.0, 0.0)
    _set_unit_location(enemy, 20.0, 0.0)
    _apply_enhancement(wartrike, "000010795002", "Kustom Shokk Box")

    assert army.orks_detachments.apply_speedwaaagh_turbo_boostas_choice(
        wartrike,
        use_turbo=True,
        game=game,
        player=ork_player,
    )

    sr = dict(getattr(wartrike, "special_rules", {}) or {})
    assert set(sr.get("bearer_unit_phase_move_terrain_only_types", [])) == {"advance"}
    rules = get_validation_rules(MovementType.ADVANCE, moving_unit=wartrike)
    assert rules["can_move_through_terrain"] is True

    game.event_system.publish("phase_end", player=ork_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    sr_after = dict(getattr(wartrike, "special_rules", {}) or {})
    assert "bearer_unit_phase_move_terrain_only_types" not in sr_after
    assert not bool(sr_after.get("enhancement_speedwaaagh_kustom_shokk_box_turbo_active"))


def test_dakkamek_adds_rapid_fire_to_selected_mekaniak_vehicle_model_until_next_command_phase():
    mek = _make_unit(
        "Mek",
        abilities=[{"name": "Mekaniak", "description": MEKANIAK_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["ORKS", "INFANTRY", "CHARACTER", "MEK"],
        faction_keywords=["ORKS"],
    )
    vehicle = _make_unit(
        "Killa Kans",
        keywords=["ORKS", "VEHICLE", "WALKER"],
        faction_keywords=["ORKS"],
        model_count=2,
        wounds="6",
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    game, ork_player, _enemy_player, army = _build_game(ork_units=[mek, vehicle], enemy_units=[enemy])
    _set_unit_location(mek, 0.0, 0.0)
    _set_unit_location(vehicle, 2.0, 0.0, spacing=0.6)
    _set_unit_location(enemy, 8.0, 0.0)
    weapon = _ranged_weapon("Kan shoota", attacks="2")
    vehicle.models[0].wargear = [weapon]
    _apply_enhancement(mek, "000010795003", "Dakkamek")
    vehicle.models[0].wounds = int(vehicle.models[0].wounds) - 2

    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game._on_phase_start_master_of_mechanisms(player=ork_player, phase=BattleRoundPhases.MOVEMENT_PHASE)
    request = _find_master_request(game, source_unit=mek)
    assert request is not None
    option = _option_for_model(request, vehicle.models[0])
    assert option is not None
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        result = resolve_decision_command(game, request, option.option_id, player_id=ork_player.id)
    assert bool(getattr(result, "ok", False))

    target_model_id = str(get_entity_id(vehicle.models[0]) or "")
    assert vehicle.special_rules.get("enhancement_speedwaaagh_dakkamek_target_model_id") == target_model_id
    bonuses = vehicle.get_attack_keyword_bonuses(
        target=enemy,
        attack_type="ranged",
        model=vehicle.models[0],
        weapon_profile=weapon.profiles["default"],
        game_map=game.map,
    )
    assert int(bonuses.get("rapid_fire_bonus", 0) or 0) == 1
    assert any("Dakkamek" in str(source) for source in list(bonuses.get("sources", []) or []))
    preview = weapon.profiles["default"].preview_attack_count(
        enemy,
        vehicle.models[0],
        game_map=game.map,
        publish_roll_event=False,
    )
    assert preview.num_attacks == 3
    assert any("Dakkamek" in str(item) for item in preview.special_modifiers)

    game.turn = 2
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.event_system.publish("phase_start", player=ork_player, phase=BattleRoundPhases.COMMAND_PHASE)
    assert not bool(vehicle.special_rules.get("enhancement_speedwaaagh_dakkamek_active"))
    expired = vehicle.get_attack_keyword_bonuses(
        target=enemy,
        attack_type="ranged",
        model=vehicle.models[0],
        weapon_profile=weapon.profiles["default"],
        game_map=game.map,
    )
    assert int(expired.get("rapid_fire_bonus", 0) or 0) == 0
    assert army.orks_detachments.is_speedwaaagh() is True


def test_supa_burny_fuel_sets_killa_jet_profile_attacks():
    wartrike = _make_unit(
        "Deffkilla Wartrike",
        keywords=["ORKS", "MOUNTED", "CHARACTER", "SPEED FREEKS"],
        faction_keywords=["ORKS"],
        movement="12",
    )
    killa_jet = Wargear(
        {
            "name": "Killa jet - burna",
            "type": "Ranged",
            "range": "12",
            "A": "D6",
            "BS_WS": "N/A",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "[TORRENT]",
        }
    )
    killa_jet.add_profile(
        "cutta",
        {
            "range": "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "6",
            "AP": "-1",
            "D": "2",
            "description": "",
        },
    )
    wartrike.models[0].wargear = [killa_jet]
    _game, _ork_player, _enemy_player, _army = _build_game(ork_units=[wartrike], enemy_units=[])

    _apply_enhancement(wartrike, "000010795004", "Supa-burny Fuel")

    burna = killa_jet.profiles["burna"]
    cutta = killa_jet.profiles["cutta"]
    assert burna._raw_attacks == "3D6"
    assert burna.attacks.max() == 18
    assert cutta._raw_attacks == "3"
    assert cutta.attacks.resolve() == 3


def test_master_meknologist_improves_bearer_ranged_ballistic_skill_only():
    big_mek = _make_unit(
        "Big Mek",
        keywords=["ORKS", "INFANTRY", "CHARACTER", "MEK", "BIG MEK"],
        faction_keywords=["ORKS"],
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    _game, _ork_player, _enemy_player, _army = _build_game(ork_units=[big_mek], enemy_units=[enemy])
    ranged_weapon = _ranged_weapon("Kustom mega-blasta", attacks="1", skill="5+")
    melee_weapon = Wargear(
        {
            "name": "Big choppa",
            "type": "Melee",
            "range": "Melee",
            "A": "3",
            "BS_WS": "4+",
            "S": "6",
            "AP": "-1",
            "D": "2",
            "description": "",
        }
    )
    big_mek.models[0].wargear = [ranged_weapon, melee_weapon]
    _apply_enhancement(big_mek, "000010795005", "Master Meknologist")

    ranged_hit = ranged_weapon.profiles["default"]._hit_target_with_tracking(
        enemy,
        big_mek.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert ranged_hit["needed"] == 4
    assert ranged_hit["hit"] is True
    assert any("Master Meknologist" in str(item) for item in ranged_hit["special_effects"])

    melee_hit = melee_weapon.profiles["default"]._hit_target_with_tracking(
        enemy,
        big_mek.models[0],
        {},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert melee_hit["needed"] == 4
    assert melee_hit["hit"] is False
    assert not any("Master Meknologist" in str(item) for item in melee_hit["special_effects"])
