from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id


DEATH_KORPS_MEDI_PACK_TEXT = (
    "At the start of your Command phase, if the bearer's unit is below its Starting Strength, you can return up to "
    "D3 destroyed Death Korps Troopers to this unit (if this unit contains two models equipped with a Death Korps "
    "medi-pack, return up to D3+1 destroyed Death Korps Troopers to this unit instead)."
)

CLOSE_RANGE_TITAN_KILLER_TEXT = (
    "Each time this model's magma cannon targets a MONSTER or VEHICLE unit, that target is always considered to be "
    "within half range of that weapon."
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
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "25mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.attached_to = []
        self.attached_to_names = []
        self.loadout = "This model is equipped with: nothing"
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
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game_with_units(units: list[Unit]):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    am_army = Army.with_detachment("Astra Militarum", detachment_type="Combined Regiment")
    am_army.faction_id = "AM"
    player = Player("AM", PlayerControl.REMOTE, army=am_army)
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    for unit in list(units or []):
        am_army.add_unit(unit)
    game.map.units = list(units or [])
    game.rebuild_entity_registry()
    return game, player


def test_death_korps_medi_pack_uses_d3_plus_1_with_two_alive_medics():
    ability = {
        "name": "Death Korps Medi-pack",
        "description": DEATH_KORPS_MEDI_PACK_TEXT,
        "type": "Datasheet",
        "parameter": "",
    }
    unit = _make_unit(
        "Death Korps Of Krieg",
        datasheet_id="death-korps-of-krieg",
        abilities=[ability],
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        model_count=4,
    )
    for model in list(unit.models or []):
        model.name = "Death Korps Trooper"
        model.optional_wargear = []
    unit.models[0].optional_wargear = ["Death Korps medi-pack"]
    unit.models[1].optional_wargear = ["Death Korps medi-pack"]

    removed_models = []
    for model in list(unit.models[2:]):
        removed_models.append(model)
        unit.remove_model(model)

    spec = unit.get_command_phase_unit_return_ability()
    assert spec is not None
    assert int(spec.get("alternate_if_wargear_model_count", 0) or 0) == 2
    assert str(spec.get("alternate_amount_roll", "") or "").upper() == "D3+1"

    game, player = _build_game_with_units([unit])

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3) as mock_roll:
        game.event_system.publish("phase_start", player=player, phase=BattleRoundPhases.COMMAND_PHASE)
    mock_roll.assert_called_once_with("D3+1")

    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_ALLOCATE_DAMAGE
        and str((req.context or {}).get("selection_kind", "") or "") == "bodyguard_return"
    )
    assert int((request.context or {}).get("remaining", 0) or 0) == 3
    returned_option_ids = {
        str((option.payload or {}).get("model_id", "") or "")
        for option in list(request.options or [])
        if (option.payload or {}).get("model_id") not in (None, "")
    }
    expected_ids = {str(get_entity_id(model) or "") for model in removed_models}
    assert returned_option_ids == expected_ids


def test_close_range_titan_killer_counts_vehicle_target_as_half_range():
    ability = {
        "name": "Close-range Titan Killer",
        "description": CLOSE_RANGE_TITAN_KILLER_TEXT,
        "type": "Datasheet",
        "parameter": "",
    }
    doomhammer = _make_unit(
        "Doomhammer",
        datasheet_id="doomhammer",
        abilities=[ability],
        keywords=["VEHICLE", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds=18,
    )
    attacker_model = doomhammer.models[0]

    vehicle_target = _make_unit(
        "Enemy Tank",
        datasheet_id="enemy-tank",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
        wounds=12,
    )
    infantry_target = _make_unit(
        "Enemy Infantry",
        datasheet_id="enemy-infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=2,
    )
    attacker_model.return_closest_model_in_unit = lambda target_unit: (target_unit.models[0], 18.0)

    magma_cannon = Wargear(
        {
            "name": "Magma Cannon",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "12",
            "AP": "-4",
            "D": "4",
            "description": "rapid fire 1; melta 2",
        }
    )
    profile = magma_cannon.profiles["default"]

    vehicle_count = profile.preview_attack_count(vehicle_target, attacker_model, publish_roll_event=False)
    infantry_count = profile.preview_attack_count(infantry_target, attacker_model, publish_roll_event=False)

    assert int(vehicle_count.num_attacks or 0) == 2
    assert int(infantry_count.num_attacks or 0) == 1
    assert bool(doomhammer.weapon_target_counts_as_half_range(model=attacker_model, target=vehicle_target, weapon_profile=profile))
    assert not bool(
        doomhammer.weapon_target_counts_as_half_range(model=attacker_model, target=infantry_target, weapon_profile=profile)
    )

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[6, 6, 1, 6, 6, 1]):
        result = profile.attack(vehicle_target, attacker_model, game_map=None)

    assert result is not None
    damage_effects = [
        str(effect or "")
        for damage_result in list(getattr(result, "damage_results", []) or [])
        for effect in list((damage_result or {}).get("special_effects", []) or [])
    ]
    assert any("Melta +2" in effect for effect in damage_effects)
