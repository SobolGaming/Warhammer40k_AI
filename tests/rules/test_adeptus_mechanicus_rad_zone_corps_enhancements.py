from unittest.mock import Mock, patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.model_base import Base, BaseType


class _RectZone:
    def __init__(self, x_min: float, x_max: float, y_min: float, y_max: float) -> None:
        self.x_min = float(x_min)
        self.x_max = float(x_max)
        self.y_min = float(y_min)
        self.y_max = float(y_max)

    def contains_point(self, x: float, y: float) -> bool:
        return self.x_min <= float(x) <= self.x_max and self.y_min <= float(y) <= self.y_max


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "3",
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


def _make_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_extra_model(name: str, unit: Unit) -> Model:
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=3,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    model.set_location(0.0, 0.0, 0.0, 0.0)
    return model


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    leader.attached_to = bodyguard
    bodyguard.attached_leaders = [leader]


def _apply_enhancement(unit: Unit, *, enhancement_id: str, name: str, description: str) -> Enhancement:
    enhancement = Enhancement(
        id=enhancement_id,
        name=name,
        faction_id="ADM",
        detachment="Rad-Zone Corps",
        description=description,
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    admech_army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Rad-Zone Corps")
    admech_army.faction_id = "ADM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"
    p1 = Player("P1", PlayerControl.REMOTE, army=admech_army)
    p2 = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    game.deployment_zones = {
        p1.id: {"mission_zones": [_RectZone(0.0, 20.0, 0.0, 20.0)]},
        p2.id: {"mission_zones": [_RectZone(80.0, 100.0, 0.0, 20.0)]},
    }
    game.map.deployment_zones = dict(game.deployment_zones)
    return game, admech_army, enemy_army, p1, p2


def test_rad_zone_corps_enhancement_descriptors_registered():
    radial = get_enhancement_tool_descriptor(enhancement_id="000008385002")
    assert radial is not None
    assert radial.name == "Radial Suffusion"
    assert radial.effect == "extend_rad_bombardment_fallout_targeting"
    assert int(radial.effect_params.get("extra_range_from_enemy_deployment_zone", 0) or 0) == 6

    malphonic = get_enhancement_tool_descriptor(enhancement_id="000008385003")
    assert malphonic is not None
    assert malphonic.name == "Malphonic Susurrus"
    assert malphonic.effect == "grant_stealth_while_leading"

    peerless = get_enhancement_tool_descriptor(enhancement_id="000008385004")
    assert peerless is not None
    assert peerless.name == "Peerless Eradicator"
    assert peerless.effect == "grant_ranged_sustained_hits_while_leading"
    assert int(peerless.effect_params.get("sustained_hits_value", 0) or 0) == 1

    autoclavic = get_enhancement_tool_descriptor(enhancement_id="000008385005")
    assert autoclavic is not None
    assert autoclavic.name == "Autoclavic Denunciation"
    assert autoclavic.effect == "grant_bearer_ranged_anti_keywords"
    assert int(autoclavic.effect_params.get("anti_infantry", 0) or 0) == 2
    assert int(autoclavic.effect_params.get("anti_monster", 0) or 0) == 4


def test_radial_suffusion_extends_fallout_targets_within_6_inches_of_enemy_deployment_zone():
    game, admech_army, enemy_army, _p1, _p2 = _build_game()
    bearer = _make_unit("Tech-priest Manipulus", keywords=["INFANTRY", "CHARACTER"])
    near_enemy = _make_unit("Enemy Near", keywords=["INFANTRY"])

    admech_army.add_unit(bearer)
    enemy_army.add_unit(near_enemy)
    _apply_enhancement(
        bearer,
        enhancement_id="000008385002",
        name="Radial Suffusion",
        description="In Battle Rounds 2-5, include enemy units within 6\" of their deployment zone for Fallout.",
    )

    bearer.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    near_enemy.models[0].set_location(74.0, 10.0, 0.0, 0.0)
    game.map.units = [bearer, near_enemy]
    game.rebuild_entity_registry()

    game.turn = 2
    game.current_player_index = 0

    near_enemy._apply_mortal_wounds_to_unit = Mock()
    near_enemy.take_battle_shock_test = Mock()

    with patch("warhammer40k_ai.rules.adeptus_mechanicus_detachments.get_roll", return_value=3):
        game.start_command_phase()

    near_enemy._apply_mortal_wounds_to_unit.assert_called_once()
    assert near_enemy._apply_mortal_wounds_to_unit.call_args.args[0] is near_enemy
    assert int(near_enemy._apply_mortal_wounds_to_unit.call_args.args[1] or 0) == 1
    near_enemy.take_battle_shock_test.assert_called_once_with(2)


def test_radial_suffusion_requires_an_active_bearer_on_the_battlefield():
    game, admech_army, enemy_army, _p1, _p2 = _build_game()
    bearer = _make_unit("Tech-priest Manipulus", keywords=["INFANTRY", "CHARACTER"])
    near_enemy = _make_unit("Enemy Near", keywords=["INFANTRY"])

    admech_army.add_unit(bearer)
    enemy_army.add_unit(near_enemy)
    _apply_enhancement(
        bearer,
        enhancement_id="000008385002",
        name="Radial Suffusion",
        description="In Battle Rounds 2-5, include enemy units within 6\" of their deployment zone for Fallout.",
    )
    bearer.deployed = False

    near_enemy.models[0].set_location(74.0, 10.0, 0.0, 0.0)
    game.map.units = [near_enemy]
    game.rebuild_entity_registry()

    game.turn = 2
    game.current_player_index = 0

    near_enemy._apply_mortal_wounds_to_unit = Mock()
    near_enemy.take_battle_shock_test = Mock()

    with patch("warhammer40k_ai.rules.adeptus_mechanicus_detachments.get_roll", return_value=3):
        game.start_command_phase()

    near_enemy._apply_mortal_wounds_to_unit.assert_not_called()
    near_enemy.take_battle_shock_test.assert_not_called()


def test_malphonic_susurrus_grants_stealth_while_bearer_is_leading():
    army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Rad-Zone Corps")
    army.faction_id = "ADM"

    bodyguard = _make_unit("Skitarii Rangers", keywords=["INFANTRY"])
    leader = _make_unit("Tech-priest Dominus", keywords=["INFANTRY", "CHARACTER"])
    army.add_unit(bodyguard)
    army.add_unit(leader)
    _attach_leader(bodyguard, leader)

    _apply_enhancement(
        leader,
        enhancement_id="000008385003",
        name="Malphonic Susurrus",
        description="While this model is leading a unit, models in that unit have the Stealth ability.",
    )

    assert bodyguard.has_stealth() is True


def test_peerless_eradicator_grants_sustained_hits_one_to_unit_ranged_attacks_while_leading():
    army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Rad-Zone Corps")
    army.faction_id = "ADM"

    bodyguard = _make_unit("Skitarii Vanguard", keywords=["INFANTRY"])
    leader = _make_unit("Tech-priest Dominus", keywords=["INFANTRY", "CHARACTER"])
    army.add_unit(bodyguard)
    army.add_unit(leader)
    _attach_leader(bodyguard, leader)

    _apply_enhancement(
        leader,
        enhancement_id="000008385004",
        name="Peerless Eradicator",
        description="While this model is leading a unit, ranged weapons equipped by models in that unit have [SUSTAINED HITS 1].",
    )

    bodyguard_ranged = bodyguard.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=bodyguard.models[0],
        weapon_name="Galvanic Rifle",
    )
    assert int(bodyguard_ranged.get("sustained_hits_value", 0) or 0) == 1

    leader_ranged = leader.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=leader.models[0],
        weapon_name="Phosphor Serpenta",
    )
    assert int(leader_ranged.get("sustained_hits_value", 0) or 0) == 1

    bodyguard_melee = bodyguard.get_model_weapon_keyword_bonuses(
        attack_type="melee",
        model=bodyguard.models[0],
        weapon_name="Close Combat Weapon",
    )
    assert int(bodyguard_melee.get("sustained_hits_value", 0) or 0) == 0


def test_autoclavic_denunciation_grants_ranged_anti_keywords_to_bearer_only():
    army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Rad-Zone Corps")
    army.faction_id = "ADM"

    leader = _make_unit("Sydonian Skatros", keywords=["INFANTRY", "CHARACTER"])
    extra_model = _make_extra_model("Sydonian Skatros Acolyte", leader)
    leader.models.append(extra_model)
    army.add_unit(leader)

    _apply_enhancement(
        leader,
        enhancement_id="000008385005",
        name="Autoclavic Denunciation",
        description="Ranged weapons equipped by the bearer have [ANTI-INFANTRY 2+] and [ANTI-MONSTER 4+].",
    )

    bearer_id = str(leader.special_rules.get("enhancement_bearer_model_id", "") or "")
    assert bearer_id
    bearer_model = next(
        model
        for model in list(leader.models or [])
        if str(getattr(model, "id", getattr(model, "_id", "")) or "") == bearer_id
    )
    non_bearer_model = next(model for model in list(leader.models or []) if model is not bearer_model)

    bearer_ranged = leader.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=bearer_model,
        weapon_name="Transuranic Arquebus",
    )
    anti_specs = {tuple(spec) for spec in list(bearer_ranged.get("anti_specs") or [])}
    assert ("INFANTRY", 2) in anti_specs
    assert ("MONSTER", 4) in anti_specs

    bearer_melee = leader.get_model_weapon_keyword_bonuses(
        attack_type="melee",
        model=bearer_model,
        weapon_name="Close Combat Weapon",
    )
    assert list(bearer_melee.get("anti_specs") or []) == []

    non_bearer_ranged = leader.get_model_weapon_keyword_bonuses(
        attack_type="ranged",
        model=non_bearer_model,
        weapon_name="Transuranic Arquebus",
    )
    assert list(non_bearer_ranged.get("anti_specs") or []) == []
