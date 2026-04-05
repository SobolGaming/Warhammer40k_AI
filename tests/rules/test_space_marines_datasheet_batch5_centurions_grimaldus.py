import pytest

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


ANNIHILATOR_PROTOCOLS_TEXT = (
    "Melee weapons equipped by models in this unit have the [SUSTAINED HITS 2] ability when targeting "
    "MONSTER, VEHICLE or FORTIFICATION units."
)
DECIMATOR_PROTOCOLS_TEXT = (
    "Each time a model in this unit makes a ranged attack, re-roll a Hit roll of 1. If the target of that "
    "attack is an enemy unit within range of an objective marker, you can re-roll the Hit roll instead."
)
TEMPLE_RELICS_TEXT = (
    "At the start of your Command phase, if this unit contains one or more Cenobyte Servitor models, select "
    "one of the abilities listed below. Until the start of your next Command phase, this model has that ability."
)
BANNER_TEXT = "Add 1 to Advance and Charge rolls made for this unit."
COLUMN_TEXT = "Add 1 to the Toughness characteristic of models in this unit."
WATER_TEXT = "Improve the Armour Penetration characteristic of melee weapons equipped by models in this unit by 1."


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count=1,
        wounds=4,
        toughness=4,
        base_size="32mm",
    ):
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "6",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _ability(name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "type": "Datasheet",
        "parameter": "",
    }


def _make_unit(
    name,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    model_count=1,
    wounds=4,
    toughness=4,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            toughness=toughness,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(*, sm_control=PlayerControl.REMOTE, enemy_control=PlayerControl.REMOTE):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army("Space Marines", "Test")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=sm_control, army=sm_army)
    enemy_player = Player("Enemy", control=enemy_control, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.COMMAND_PHASE
    return game, sm_army, enemy_army, sm_player, enemy_player


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    try:
        leader.attach_to_unit(bodyguard)
    except Exception:
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]
        for unit in (leader, bodyguard):
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()


def _find_request(game: Game, ability_key: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") == str(ability_key):
            return request
    return None


def _rename_models(unit: Unit, names: list[str]) -> None:
    for model, name in zip(list(getattr(unit, "models", []) or []), names):
        model.name = str(name)


def _make_melee_profile():
    weapon = Wargear(
        {
            "name": "Test Blade",
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _make_grimaldus_attached_unit():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    bodyguard = _make_unit(
        "Crusader Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=2,
        toughness=4,
        wounds=2,
    )
    grimaldus = _make_unit(
        "Chaplain Grimaldus",
        abilities=[
            _ability("Temple Relics", TEMPLE_RELICS_TEXT),
            _ability("Banner of the Emperor Victorious", BANNER_TEXT),
            _ability("Column from the Major Altar", COLUMN_TEXT),
            _ability("Water from the Stoup of Elucidation", WATER_TEXT),
        ],
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=3,
        toughness=5,
        wounds=5,
    )
    _rename_models(grimaldus, ["Grimaldus", "Cenobyte Servitor", "Cenobyte Servitor"])
    enemy = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=1,
    )

    sm_army.add_unit(bodyguard)
    sm_army.add_unit(grimaldus)
    enemy_army.add_unit(enemy)
    _attach_leader(bodyguard, grimaldus)
    bodyguard._refresh_bearer_unit_common_modifiers()
    game.map.units = [bodyguard, grimaldus, enemy]
    game.rebuild_entity_registry()
    return game, bodyguard, grimaldus, enemy, sm_player


def test_centurion_assault_annihilator_protocols_grants_sustained_hits_two_vs_monster_vehicle_and_fortification():
    unit = _make_unit(
        "Centurion Assault Squad",
        abilities=[_ability("Annihilator Protocols", ANNIHILATOR_PROTOCOLS_TEXT)],
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    monster = _make_unit("Monster Target", keywords=["MONSTER"], faction_keywords=["ENEMY"])
    vehicle = _make_unit("Vehicle Target", keywords=["VEHICLE"], faction_keywords=["ENEMY"])
    fortification = _make_unit("Fortification Target", keywords=["FORTIFICATION"], faction_keywords=["ENEMY"])
    infantry = _make_unit("Infantry Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    monster_bonus = unit.get_attack_keyword_bonuses(
        target=monster,
        attack_type="melee",
        model=unit.models[0],
    )
    vehicle_bonus = unit.get_attack_keyword_bonuses(
        target=vehicle,
        attack_type="melee",
        model=unit.models[0],
    )
    fortification_bonus = unit.get_attack_keyword_bonuses(
        target=fortification,
        attack_type="melee",
        model=unit.models[0],
    )
    infantry_bonus = unit.get_attack_keyword_bonuses(
        target=infantry,
        attack_type="melee",
        model=unit.models[0],
    )

    assert int(monster_bonus.get("sustained_hits_value", 0) or 0) == 2
    assert int(vehicle_bonus.get("sustained_hits_value", 0) or 0) == 2
    assert int(fortification_bonus.get("sustained_hits_value", 0) or 0) == 2
    assert int(infantry_bonus.get("sustained_hits_value", 0) or 0) == 0


def test_centurion_devastator_decimator_protocols_grants_full_rerolls_only_vs_objective_targets():
    attacker = _make_unit(
        "Centurion Devastator Squad",
        abilities=[_ability("Decimator Protocols", DECIMATOR_PROTOCOLS_TEXT)],
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    target = _make_unit("Enemy Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    baseline = attacker.get_unit_hit_reroll_modifiers(
        "ranged",
        target=target,
        attacker_model=attacker.models[0],
    )
    assert bool(baseline.get("reroll_hit_ones", False)) is True
    assert bool(baseline.get("reroll_hit_full", False)) is False

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(attacker, "_target_within_objective_range", lambda *_args, **_kwargs: True)
        objective_target = attacker.get_unit_hit_reroll_modifiers(
            "ranged",
            target=target,
            attacker_model=attacker.models[0],
        )

    assert bool(objective_target.get("reroll_hit_ones", False)) is True
    assert bool(objective_target.get("reroll_hit_full", False)) is True


@pytest.mark.parametrize(
    ("mode", "expected_advance", "expected_charge", "expected_toughness", "expected_ap"),
    [
        ("banner_of_the_emperor_victorious", 1, 1, 0, 0),
        ("column_from_the_major_altar", 0, 0, 1, 0),
        ("water_from_the_stoup_of_elucidation", 0, 0, 0, -1),
    ],
)
def test_chaplain_grimaldus_temple_relics_selection_activates_only_selected_mode(
    mode: str,
    expected_advance: int,
    expected_charge: int,
    expected_toughness: int,
    expected_ap: int,
):
    game, bodyguard, _grimaldus, enemy, sm_player = _make_grimaldus_attached_unit()
    melee_profile = _make_melee_profile()

    assert bodyguard._apply_advance_roll_modifiers(4) == 4
    assert game._apply_charge_modifiers(bodyguard, 7) == 7
    assert bodyguard.get_effective_model_characteristic(bodyguard.models[0], "toughness") == 4
    assert melee_profile.get_effective_ap(bodyguard.models[0], enemy) == 0

    game._on_phase_start_optional_abilities(player=sm_player, phase=BattleRoundPhases.COMMAND_PHASE)
    request = _find_request(game, "space_marines_temple_relics")
    assert request is not None

    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("temple_relics_mode", "") or "") == mode
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=sm_player.id)
    assert bool(getattr(result, "ok", False)) is True

    assert bodyguard._apply_advance_roll_modifiers(4) == 4 + expected_advance
    assert game._apply_charge_modifiers(bodyguard, 7) == 7 + expected_charge
    assert bodyguard.get_effective_model_characteristic(bodyguard.models[0], "toughness") == 4 + expected_toughness
    assert melee_profile.get_effective_ap(bodyguard.models[0], enemy) == expected_ap


def test_chaplain_grimaldus_temple_relics_does_not_queue_without_live_cenobyte_servitor():
    game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
    grimaldus = _make_unit(
        "Chaplain Grimaldus",
        abilities=[
            _ability("Temple Relics", TEMPLE_RELICS_TEXT),
            _ability("Banner of the Emperor Victorious", BANNER_TEXT),
            _ability("Column from the Major Altar", COLUMN_TEXT),
            _ability("Water from the Stoup of Elucidation", WATER_TEXT),
        ],
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=2,
        toughness=5,
        wounds=5,
    )
    _rename_models(grimaldus, ["Grimaldus", "Attendant"])
    sm_army.add_unit(grimaldus)
    game.map.units = [grimaldus]
    game.rebuild_entity_registry()

    game._on_phase_start_optional_abilities(player=sm_player, phase=BattleRoundPhases.COMMAND_PHASE)

    assert _find_request(game, "space_marines_temple_relics") is None
