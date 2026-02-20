from __future__ import annotations

import types
from unittest.mock import patch

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        model_count: int = 1,
        wounds: int = 2,
        keywords=None,
        faction_keywords=None,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Aeldari"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["AELDARI"])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "3",
                "Sv": "4",
                "W": str(int(wounds)),
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


def _make_unit(
    name: str,
    army: Army,
    *,
    model_count: int = 1,
    wounds: int = 2,
    keywords=None,
    faction_keywords=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            model_count=model_count,
            wounds=wounds,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    army.add_unit(unit)
    return unit


def test_ghosts_of_the_webway_enhancements_have_tool_descriptors():
    expected = {
        "000009915002": ("Cegorach's Coil", "charge_end_mortal_wounds_per_model_in_engagement_with_cap"),
        "000009915003": ("Mask of Secrets", "enemy_fall_back_forced_desperate_escape_with_battleshock_penalty"),
        "000009915004": ("Murder's Jest", "successful_hits_become_critical"),
        "000009915005": ("Mistweave", "grant_infiltrators_while_leading"),
    }
    for enhancement_id, (name, effect) in expected.items():
        desc = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert desc is not None
        assert str(desc.name) == name
        assert str(desc.effect) == effect


def test_cegorachs_coil_counts_only_engaged_models_for_rolls():
    army = Army("Aeldari", detachment_type="Ghosts of the Webway")
    army.faction_id = "AE"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    bearer = _make_unit(
        "Troupe Master",
        army,
        model_count=3,
        keywords=["CHARACTER", "INFANTRY", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
    )
    enemy = _make_unit("Enemy Unit", enemy_army, model_count=1, keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    enhancement = Enhancement(
        id="000009915002",
        name="Cegorach's Coil",
        faction_id="AE",
        detachment="Ghosts of the Webway",
        description=(
            "Troupe Master model only. Each time the bearer's unit ends a Charge move, select one enemy unit within "
            "Engagement Range of the bearer's unit, then roll one D6 for each model in the bearer's unit that is "
            "within Engagement Range of that enemy unit: for each 4+, that enemy unit suffers 1 mortal wound "
            "(to a maximum of 6 mortal wounds)."
        ),
    )
    bearer.enhancement = enhancement
    enhancement.apply_to_unit(bearer)
    bearer._refresh_charge_end_mortal_wounds_flags()

    specs = list(getattr(bearer, "special_rules", {}).get("charge_end_mortal_wounds", []) or [])
    spec = next((s for s in specs if str(s.get("kind", "") or "") == "per_model_engagement_flat_cap"), None)
    assert spec is not None

    applied = {"amount": 0}

    def _apply(self, target_unit, amount, game_map=None):
        applied["amount"] += int(amount or 0)
        return 0

    bearer._apply_mortal_wounds_to_unit = types.MethodType(_apply, bearer)
    engaged_models = {bearer.models[0], bearer.models[1]}
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))

    with patch(
        "warhammer40k_ai.utility.aura_utils.model_within_engagement_range_of_unit",
        side_effect=lambda model, _target: model in engaged_models,
    ):
        with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[4, 2]):
            game.resolve_charge_end_mortal_wounds(bearer, enemy, spec)

    assert int(applied["amount"]) == 1


def test_cegorachs_coil_caps_mortal_wounds_at_six():
    army = Army("Aeldari", detachment_type="Ghosts of the Webway")
    army.faction_id = "AE"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    bearer = _make_unit(
        "Troupe Master",
        army,
        model_count=8,
        keywords=["CHARACTER", "INFANTRY", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
    )
    enemy = _make_unit("Enemy Unit", enemy_army, model_count=1, keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    enhancement = Enhancement(
        id="000009915002",
        name="Cegorach's Coil",
        faction_id="AE",
        detachment="Ghosts of the Webway",
        description="",
    )
    bearer.enhancement = enhancement
    enhancement.apply_to_unit(bearer)
    bearer._refresh_charge_end_mortal_wounds_flags()

    spec = next(
        s
        for s in list(getattr(bearer, "special_rules", {}).get("charge_end_mortal_wounds", []) or [])
        if str(s.get("kind", "") or "") == "per_model_engagement_flat_cap"
    )
    applied = {"amount": 0}

    def _apply(self, target_unit, amount, game_map=None):
        applied["amount"] += int(amount or 0)
        return 0

    bearer._apply_mortal_wounds_to_unit = types.MethodType(_apply, bearer)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))

    with patch(
        "warhammer40k_ai.utility.aura_utils.model_within_engagement_range_of_unit",
        return_value=True,
    ):
        with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[4] * 8):
            game.resolve_charge_end_mortal_wounds(bearer, enemy, spec)

    assert int(applied["amount"]) == 6


def test_mask_of_secrets_forces_desperate_escape_and_applies_battleshock_penalty():
    army = Army("Aeldari", detachment_type="Ghosts of the Webway")
    army.faction_id = "AE"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    trapper = _make_unit(
        "Shadowseer",
        army,
        keywords=["CHARACTER", "INFANTRY", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
    )
    runner = _make_unit(
        "Enemy Infantry",
        enemy_army,
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    enhancement = Enhancement(
        id="000009915003",
        name="Mask of Secrets",
        faction_id="AE",
        detachment="Ghosts of the Webway",
        description="",
    )
    trapper.enhancement = enhancement
    enhancement.apply_to_unit(trapper)

    runner.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    trapper.models[0].set_location(10.5, 10.0, 0.0, 0.0)
    runner.apply_status_effect(BattleShockEffect(1))

    game_map = Map(60, 44)
    game_map.units = [runner, trapper]

    called = {"count": 0, "modifier": 0}

    def _fake(self, game_map=None, *, roll_modifier=0, reason=None):
        called["count"] += 1
        called["modifier"] = int(roll_modifier or 0)
        return 0

    runner.take_desperate_escape_test = types.MethodType(_fake, runner)
    result = runner.fall_back((14.0, 10.0, 0.0), [], game_map)

    assert result is True
    assert int(called["count"]) == 1
    assert int(called["modifier"]) == -1


def test_mask_of_secrets_excludes_vehicle_units():
    army = Army("Aeldari", detachment_type="Ghosts of the Webway")
    army.faction_id = "AE"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    trapper = _make_unit(
        "Shadowseer",
        army,
        keywords=["CHARACTER", "INFANTRY", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
    )
    runner = _make_unit(
        "Enemy Vehicle",
        enemy_army,
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
    )

    enhancement = Enhancement(
        id="000009915003",
        name="Mask of Secrets",
        faction_id="AE",
        detachment="Ghosts of the Webway",
        description="",
    )
    trapper.enhancement = enhancement
    enhancement.apply_to_unit(trapper)

    runner.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    trapper.models[0].set_location(10.5, 10.0, 0.0, 0.0)

    game_map = Map(60, 44)
    game_map.units = [runner, trapper]

    called = {"count": 0}

    def _fake(self, game_map=None, *, roll_modifier=0, reason=None):
        called["count"] += 1
        return 0

    runner.take_desperate_escape_test = types.MethodType(_fake, runner)
    result = runner.fall_back((14.0, 10.0, 0.0), [], game_map)

    assert result is True
    assert int(called["count"]) == 0


def test_murders_jest_turns_successful_hits_into_critical_hits_vs_below_half_strength_targets():
    army = Army("Aeldari", detachment_type="Ghosts of the Webway")
    army.faction_id = "AE"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    attacker = _make_unit(
        "Death Jester",
        army,
        keywords=["CHARACTER", "INFANTRY", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
    )
    target_below_half = _make_unit(
        "Enemy Squad",
        enemy_army,
        model_count=3,
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    target_below_half.models = target_below_half.models[:1]

    enhancement = Enhancement(
        id="000009915004",
        name="Murder's Jest",
        faction_id="AE",
        detachment="Ghosts of the Webway",
        description="",
    )
    attacker.enhancement = enhancement
    enhancement.apply_to_unit(attacker)

    weapon = Wargear(
        {
            "name": "Shrieker Cannon",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "5+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    profile = weapon.profiles["default"]

    success_hit = profile._hit_target_with_tracking(
        target_below_half,
        attacker.models[0],
        {},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert success_hit.get("hit") is True
    assert int(success_hit.get("crit_threshold", 0) or 0) == 5
    assert any("murder's jest" in str(effect).lower() for effect in list(success_hit.get("special_effects", []) or []))

    failed_hit = profile._hit_target_with_tracking(
        target_below_half,
        attacker.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert failed_hit.get("hit") is False

    target_not_below_half = _make_unit(
        "Enemy Full Squad",
        enemy_army,
        model_count=3,
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    target_not_below_half.models = target_not_below_half.models[:2]
    non_triggered_hit = profile._hit_target_with_tracking(
        target_not_below_half,
        attacker.models[0],
        {},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(non_triggered_hit.get("crit_threshold", 0) or 0) == 6


def test_mistweave_grants_infiltrators_while_bearer_is_leading():
    army = Army("Aeldari", detachment_type="Ghosts of the Webway")
    army.faction_id = "AE"

    leader = _make_unit(
        "Shadowseer",
        army,
        keywords=["CHARACTER", "INFANTRY", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
    )
    bodyguard = _make_unit(
        "Troupe",
        army,
        keywords=["INFANTRY", "HARLEQUINS"],
        faction_keywords=["AELDARI", "HARLEQUINS"],
    )

    enhancement = Enhancement(
        id="000009915005",
        name="Mistweave",
        faction_id="AE",
        detachment="Ghosts of the Webway",
        description="",
    )
    leader.enhancement = enhancement
    enhancement.apply_to_unit(leader)

    assert leader.has_infiltrate() is False
    assert bodyguard.has_infiltrate() is False

    leader.can_be_attached_to = [bodyguard.get_datasheet_id()]
    leader.attach_to_unit(bodyguard)

    assert leader.has_infiltrate() is True
    assert bodyguard.has_infiltrate() is True
