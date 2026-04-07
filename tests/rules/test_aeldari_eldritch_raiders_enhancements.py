from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Aeldari"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["AELDARI"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "7",
                "T": "3",
                "Sv": "4",
                "W": "2",
                "Ld": "6",
                "OC": "1",
                "base_size": "25mm",
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


def _make_unit(name: str, army: Army, *, keywords=None, faction_keywords=None, abilities=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    if abilities is not None:
        unit.possible_abilities = list(abilities)
    army.add_unit(unit)
    return unit


def _make_profile(*, name: str, weapon_type: str, keywords: str):
    weapon = Wargear(
        {
            "name": name,
            "type": weapon_type,
            "range": "24" if str(weapon_type).strip().lower() == "ranged" else "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": keywords,
        }
    )
    return weapon.profiles["default"]


def _make_game(army: Army, *, phase_name: str):
    player = getattr(army, "player", None)
    if player is None:
        player = SimpleNamespace(id="player-aeldari")
        army.player = player
    return SimpleNamespace(
        turn=1,
        phase=SimpleNamespace(name=str(phase_name)),
        roll_manager=None,
        is_authoritative=False,
        get_current_player=lambda: player,
    )


def test_eldritch_raiders_enhancements_have_tool_descriptors():
    expected = {
        "000010699002": ("Pirate Prince", "battle_focus_token_refund_on_agile_maneuver_spend"),
        "000010699003": ("Alacritous Assault", "grant_weapon_keywords"),
        "000010699004": ("Exotic Munitions", "grant_weapon_keywords"),
        "000010699005": ("Adrenal Infusions", "grant_fade_back_without_battle_focus_token"),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(desc.name) == name
        assert str(desc.effect) == effect


def test_pirate_prince_refunds_battle_focus_tokens_on_successful_roll():
    army = Army.with_detachment("Aeldari", detachment_type="Eldritch Raiders")
    army.faction_id = "AE"
    battle_focus = Ability("Battle Focus", "AE", "", "Datasheet", "")

    bodyguard = _make_unit(
        "Corsair Voidreavers",
        army,
        keywords=["INFANTRY", "ANHRATHE"],
        faction_keywords=["AELDARI", "ASURYANI"],
        abilities=[battle_focus],
    )
    leader = _make_unit(
        "Prince Yriel",
        army,
        keywords=["CHARACTER", "INFANTRY", "ANHRATHE"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    leader.can_be_attached_to = [bodyguard]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]

    enhancement = Enhancement(
        id="000010699002",
        name="Pirate Prince",
        faction_id="AE",
        detachment="Eldritch Raiders",
        description=(
            "Prince Yriel unit only. Each time you spend a Battle Focus token to enable this unit to perform an Agile Manoeuvre, "
            "roll one D6: on a 3+, you gain 1 Battle Focus token."
        ),
    )
    leader.enhancement = enhancement
    enhancement.apply_to_unit(leader)

    specs = list(bodyguard.leading_battle_focus_token_refund_specs() or [])
    assert any(
        str(spec.get("source", "")).strip().lower() == "pirate prince"
        and int(spec.get("threshold", 0) or 0) == 3
        for spec in specs
    )

    mgr = army.battle_focus
    game = _make_game(army, phase_name="MOVEMENT_PHASE")

    mgr.tokens = 1
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=3):
        applied = mgr.apply_maneuver(bodyguard, mgr.MANEUVER_SWIFT, game)
    assert applied is True
    assert int(mgr.tokens or 0) == 1

    game.phase = SimpleNamespace(name="SHOOTING_PHASE")
    mgr.tokens = 1
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        applied = mgr.apply_maneuver(bodyguard, mgr.MANEUVER_SWIFT, game)
    assert applied is True
    assert int(mgr.tokens or 0) == 0


def test_alacritous_assault_grants_lance_to_bearer_unit_melee_weapons():
    army = Army.with_detachment("Aeldari", detachment_type="Eldritch Raiders")
    army.faction_id = "AE"
    unit = _make_unit(
        "Corsair Voidscarred",
        army,
        keywords=["INFANTRY", "ANHRATHE"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    enhancement = Enhancement(
        id="000010699003",
        name="Alacritous Assault",
        faction_id="AE",
        detachment="Eldritch Raiders",
        description="Anhrathe unit only. Melee weapons equipped by models in this unit have the [LANCE] ability.",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)

    bonuses = unit.get_model_weapon_keyword_bonuses(
        attack_type="melee",
        model=unit.models[0],
        weapon_profile=_make_profile(name="Corsair blade", weapon_type="Melee", keywords=""),
        weapon_name="Corsair blade",
    )
    assert bool(bonuses.get("lance")) is True
    assert any("alacritous assault" in str(source).lower() for source in list(bonuses.get("sources", []) or []))


def test_exotic_munitions_grants_anti_monster_and_anti_vehicle_to_ranged_weapons():
    army = Army.with_detachment("Aeldari", detachment_type="Eldritch Raiders")
    army.faction_id = "AE"
    unit = _make_unit(
        "Corsair Voidscarred",
        army,
        keywords=["INFANTRY", "ANHRATHE"],
        faction_keywords=["AELDARI", "ASURYANI"],
    )
    enhancement = Enhancement(
        id="000010699004",
        name="Exotic Munitions",
        faction_id="AE",
        detachment="Eldritch Raiders",
        description=(
            "Anhrathe unit only. Ranged weapons equipped by models in this unit have the [ANTI-MONSTER 5+] and [ANTI-VEHICLE 5+] abilities."
        ),
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)

    model = unit.models[0]
    ranged_bonuses = unit.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=model,
        weapon_profile=_make_profile(name="Shuriken rifle", weapon_type="Ranged", keywords=""),
        weapon_name="Shuriken rifle",
    )
    melee_bonuses = unit.get_model_weapon_keyword_bonuses(
        attack_type="melee",
        model=model,
        weapon_profile=_make_profile(name="Corsair blade", weapon_type="Melee", keywords=""),
        weapon_name="Corsair blade",
    )

    assert ("MONSTER", 5) in list(ranged_bonuses.get("anti_specs", []) or [])
    assert ("VEHICLE", 5) in list(ranged_bonuses.get("anti_specs", []) or [])
    assert ("MONSTER", 5) not in list(melee_bonuses.get("anti_specs", []) or [])
    assert ("VEHICLE", 5) not in list(melee_bonuses.get("anti_specs", []) or [])


def test_adrenal_infusions_grants_fade_back_without_token_and_without_phase_cap_consumption():
    army = Army.with_detachment("Aeldari", detachment_type="Eldritch Raiders")
    army.faction_id = "AE"
    battle_focus = Ability("Battle Focus", "AE", "", "Datasheet", "")
    unit = _make_unit(
        "Corsair Voidreavers",
        army,
        keywords=["INFANTRY", "ANHRATHE"],
        faction_keywords=["AELDARI", "ASURYANI"],
        abilities=[battle_focus],
    )
    enhancement = Enhancement(
        id="000010699005",
        name="Adrenal Infusions",
        faction_id="AE",
        detachment="Eldritch Raiders",
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)

    assert unit.has_fleet_of_foot() is True

    mgr = army.battle_focus
    game = _make_game(army, phase_name="SHOOTING_PHASE")
    mgr.tokens = 0
    mgr._maneuvers_used_this_phase = {mgr.MANEUVER_FADE_BACK}

    candidates = mgr.get_fade_back_candidates([unit], game)
    assert unit in candidates

    mgr._maneuvers_used_this_phase = set()
    mgr._units_used_this_phase = set()
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=1):
        applied = mgr.apply_reactive_maneuver(unit, mgr.MANEUVER_FADE_BACK, game)
    assert applied is True
    assert int(mgr.tokens or 0) == 0
    assert mgr.MANEUVER_FADE_BACK not in mgr._maneuvers_used_this_phase
    assert mgr._unit_id(unit) in mgr._units_used_this_phase
