from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(self, name, *, keywords=None, faction_keywords=None, toughness=4):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Chaos Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": "3",
                "W": "2",
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
        self.attached_to = []


def _make_unit(name, army, *, keywords=None, faction_keywords=None, toughness=4):
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords, toughness=toughness))
    unit.set_parent_army(army)
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    return unit


def _set_phase(army: Army, phase_name: str) -> None:
    army.player = SimpleNamespace(
        id="P1",
        game=SimpleNamespace(
            phase=SimpleNamespace(name=phase_name),
            map=None,
        ),
    )


def _make_profile(*, melee: bool, strength: int = 4, ap: int = 0) -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Weapon",
        is_melee=lambda: bool(melee),
        is_ranged=lambda: not bool(melee),
    )
    return WargearProfile(
        profile_name="default",
        wargear_data={
            "range": "Melee" if melee else "24",
            "A": "1",
            "BS_WS": "4+",
            "S": str(strength),
            "AP": str(ap),
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_empyric_wellspring_leaping_warpflame_adds_ranged_strength_within_9():
    army = Army("Chaos Space Marines", detachment_type="Cabal of Chaos")
    army.faction_id = "CSM"
    _set_phase(army, "SHOOTING_PHASE")

    enemy_army = Army("Other", detachment_type="Other")

    attacker = _make_unit("Legionaries", army, keywords=["HERETIC ASTARTES"], faction_keywords=["HERETIC ASTARTES"])
    psyker = _make_unit("Sorcerer", army, keywords=["HERETIC ASTARTES", "PSYKER"], faction_keywords=["HERETIC ASTARTES"])
    target = _make_unit("Target", enemy_army, toughness=4)

    army.units = [attacker, psyker]
    enemy_army.units = [target]

    attacker_model = attacker.models[0]
    psyker_model = psyker.models[0]
    target_model = target.models[0]
    attacker_model.set_location(0.0, 0.0, 0.0, 0.0)
    psyker_model.set_location(8.0, 0.0, 0.0, 0.0)
    target_model.set_location(1.0, 0.0, 0.0, 0.0)

    attacker.special_rules["empyric_wellspring_choice"] = "LEAPING_WARPFLAME"
    attacker.special_rules["empyric_wellspring_expires_phase"] = "SHOOTING_PHASE"

    profile = _make_profile(melee=False, strength=4, ap=0)
    wound_near = profile._wound_target_with_tracking(target, attacker_model, {}, roll_value=4, allow_rerolls=False)
    assert int(wound_near["needed"]) == 3
    assert any("Leaping Warpflame" in reason for reason in list(wound_near.get("modifiers", [])))

    psyker_model.set_location(20.0, 0.0, 0.0, 0.0)
    wound_far = profile._wound_target_with_tracking(target, attacker_model, {}, roll_value=4, allow_rerolls=False)
    assert int(wound_far["needed"]) == 4


def test_empyric_wellspring_monstrous_manifestation_adds_melee_ap_within_9():
    army = Army("Chaos Space Marines", detachment_type="Cabal of Chaos")
    army.faction_id = "CSM"
    _set_phase(army, "FIGHT_PHASE")

    enemy_army = Army("Other", detachment_type="Other")

    attacker = _make_unit("Legionaries", army, keywords=["HERETIC ASTARTES"], faction_keywords=["HERETIC ASTARTES"])
    daemon_prince = _make_unit(
        "Daemon Prince",
        army,
        keywords=["HERETIC ASTARTES", "DAEMON PRINCE"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    target = _make_unit("Target", enemy_army, toughness=4)

    army.units = [attacker, daemon_prince]
    enemy_army.units = [target]

    attacker_model = attacker.models[0]
    daemon_prince_model = daemon_prince.models[0]
    target_model = target.models[0]
    attacker_model.set_location(0.0, 0.0, 0.0, 0.0)
    daemon_prince_model.set_location(8.0, 0.0, 0.0, 0.0)
    target_model.set_location(1.0, 0.0, 0.0, 0.0)

    attacker.special_rules["empyric_wellspring_choice"] = "MONSTROUS_MANIFESTATION"
    attacker.special_rules["empyric_wellspring_expires_phase"] = "FIGHT_PHASE"

    profile = _make_profile(melee=True, strength=4, ap=0)
    assert int(profile.get_effective_ap(attacker_model, target)) == -1

    daemon_prince_model.set_location(20.0, 0.0, 0.0, 0.0)
    assert int(profile.get_effective_ap(attacker_model, target)) == 0
