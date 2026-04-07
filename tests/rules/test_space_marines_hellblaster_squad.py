from __future__ import annotations

import os

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


FOR_THE_CHAPTER_TEXT = (
    "Each time a model in this unit is destroyed, roll one D6: on a 3+, do not remove it from play. "
    "The destroyed model can shoot after the attacking model's unit has finished making its attacks, and is then removed "
    "from play. When resolving these attacks, any Hazardous tests taken for that attack are automatically passed."
)
HELLBLASTER_DESIGNER_NOTE_TEXT = (
    "This ability is triggered even when a model in this unit is destroyed as the result of failing a Hazardous test, "
    "meaning such a model may be able to shoot twice in the same phase."
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
        wounds: int = 2,
        save: int = 3,
    ):
        self.id = datasheet_id or name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": str(int(save)),
                "W": str(int(wounds)),
                "Ld": "6",
                "OC": "1",
                "base_size": "32mm",
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
    wounds: int = 2,
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


def _build_game() -> tuple[Game, Army, Army]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type="Gladius Task Force")
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army.faction_id = "EN"
    sm_player = Player("SM", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    return game, sm_army, enemy_army


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _install_rolls(monkeypatch, rolls: list[int]) -> None:
    import warhammer40k_ai.utility.dice as dice_mod
    import warhammer40k_ai.units.unit_mixins.damage_death_mixin as damage_death_mod
    import warhammer40k_ai.units.wargear as wargear_mod

    values = iter(list(rolls))

    def _rigged(_expr: str):
        try:
            return next(values)
        except StopIteration:
            return 6

    monkeypatch.setattr(dice_mod, "get_roll", _rigged)
    monkeypatch.setattr(wargear_mod, "get_roll", _rigged)
    monkeypatch.setattr(damage_death_mod, "get_roll", _rigged)


def _add_ranged_weapon(model, *, name: str = "Plasma Incinerator", description: str = ""):
    gun = Wargear(
        {
            "name": name,
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "2",
            "S": "8",
            "AP": "-3",
            "D": "1",
            "description": description,
        }
    )
    model.wargear.append(gun)
    return gun.profiles.get("default") or next(iter(gun.profiles.values()))


def _seed_support_maps():
    import scripts.generate_ability_support_matrix as gsm

    abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json"))
    detachment_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json"))
    gsm.DETACHMENT_ABILITY_IDS = {
        str(row.get("id", "") or "").strip()
        for row in detachment_abilities
        if str(row.get("id", "") or "").strip()
    }
    gsm._seed_ability_support_maps(abilities, detachment_abilities)
    return gsm


def test_for_the_chapter_rule_parses_hazardous_and_damage_source_limits():
    hellblasters = _make_unit(
        "Hellblaster Squad",
        datasheet_id="hellblaster-squad",
        abilities=[{"name": "For the Chapter!", "description": FOR_THE_CHAPTER_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "ADEPTUS ASTARTES"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )

    rule = hellblasters.get_shoot_on_death_after_attacks_rule(model=hellblasters.models[0])

    assert isinstance(rule, dict)
    assert int(rule.get("threshold", 0) or 0) == 3
    assert str(rule.get("attack_type", "") or "") == "any"
    assert bool(rule.get("auto_pass_hazardous")) is True
    assert tuple(rule.get("allowed_damage_sources", ()) or ()) == ("attack", "hazardous")


def test_for_the_chapter_does_not_trigger_on_non_attack_destruction():
    from unittest.mock import patch

    game, sm_army, _enemy_army = _build_game()
    hellblasters = _make_unit(
        "Hellblaster Squad",
        datasheet_id="hellblaster-squad",
        abilities=[{"name": "For the Chapter!", "description": FOR_THE_CHAPTER_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "ADEPTUS ASTARTES"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    sm_army.add_unit(hellblasters)
    game.map.units = [hellblasters]
    game.rebuild_entity_registry()
    _deploy(hellblasters, 10.0, 10.0)

    model = hellblasters.models[0]
    model._last_damage_source_kind = "non_attack"
    model._wounds = 0

    with patch.object(hellblasters, "_try_shoot_on_death", return_value=True) as mocked:
        hellblasters._handle_model_destroyed(model, game.map)

    assert mocked.call_count == 0
    assert list(getattr(hellblasters, "_shoot_on_death_pending_models", []) or []) == []


def test_for_the_chapter_triggers_immediately_on_hazardous_and_auto_passes_hazardous(monkeypatch):
    from unittest.mock import patch

    _install_rolls(monkeypatch, [3, 6, 6, 1])

    game, sm_army, enemy_army = _build_game()
    hellblasters = _make_unit(
        "Hellblaster Squad",
        datasheet_id="hellblaster-squad",
        abilities=[{"name": "For the Chapter!", "description": FOR_THE_CHAPTER_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "ADEPTUS ASTARTES"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=2,
    )
    target = _make_unit(
        "Enemy Target",
        datasheet_id="enemy-target",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=1,
        save=7,
    )
    sm_army.add_unit(hellblasters)
    enemy_army.add_unit(target)
    game.map.units = [hellblasters, target]
    game.rebuild_entity_registry()
    _deploy(hellblasters, 10.0, 10.0)
    _deploy(target, 20.0, 10.0)

    model = hellblasters.models[0]
    hazardous_profile = _add_ranged_weapon(model, description="Hazardous")
    model._last_damage_source_kind = "hazardous"
    model._last_damage_weapon_profile = hazardous_profile
    model._wounds = 0

    with patch.object(model, "take_damage", wraps=model.take_damage) as mocked_take_damage:
        model.die(game_map=game.map)

    assert mocked_take_damage.call_count == 0
    assert target.is_alive() is False
    assert list(getattr(hellblasters, "_shoot_on_death_pending_models", []) or []) == []


def test_for_the_chapter_support_matrix_classifies_supported():
    gsm = _seed_support_maps()

    status, notes = gsm._classify_ability(
        "For the Chapter!",
        FOR_THE_CHAPTER_TEXT,
        ability_id="",
        faction_id="SM",
        datasheet_id="hellblaster-squad",
    )

    assert status == "Supported"
    note_text = str(notes or "")
    assert "Shoot-on-death" in note_text
    assert "Hazardous" in note_text
    assert "attack or Hazardous test" in note_text


def test_hellblaster_designer_note_support_matrix_classifies_supported():
    gsm = _seed_support_maps()

    status, notes = gsm._classify_ability(
        "Designer's Note",
        HELLBLASTER_DESIGNER_NOTE_TEXT,
        ability_id="",
        faction_id="SM",
        datasheet_id="hellblaster-squad",
    )

    assert status == "Supported"
    assert "Rules note only" in str(notes or "")
