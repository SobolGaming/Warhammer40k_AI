from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        unit_comp: str,
        toughness: str = "4",
        wounds: str = "3",
        abilities=None,
        attached_to=None,
    ):
        self.id = str(datasheet_id)
        self.name = name
        self.faction_data = {"name": "Chaos Space Marines"}
        self.keywords = []
        self.faction_keywords = ["HERETIC ASTARTES"]
        self.datasheets_unit_composition = [{"description": unit_comp}]
        self.datasheets_models_cost = [{"description": unit_comp, "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(toughness),
                "Sv": "3",
                "W": str(wounds),
                "Ld": "6",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []
        self.transport = ""


def _make_unit(ds):
    from warhammer40k_ai.units.unit import Unit

    return Unit(ds)


def _make_aura_stub():
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


def test_enhanced_warriors_bodyguard_toughness_and_melee_strength():
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.units.wargear import WargearProfile

    ability_text = (
        "If this unit is attached to a unit at the start of the battle, add 1 to the Strength characteristic of "
        "melee weapons equipped by Bodyguard models in that unit and add 1 to the Toughness characteristic of "
        "Bodyguard models in that unit."
    )
    leader_ds = _MockDatasheet(
        "Fabius Bile",
        datasheet_id="CSM_LEADER",
        unit_comp="1 Fabius Bile",
        toughness="5",
        wounds="5",
        abilities=[{"name": "Enhanced Warriors", "description": ability_text, "type": "Datasheet", "parameter": ""}],
        attached_to=["CSM_BODYGUARD"],
    )
    bodyguard_ds = _MockDatasheet(
        "Chosen",
        datasheet_id="CSM_BODYGUARD",
        unit_comp="1 Chosen",
        toughness="4",
        wounds="2",
    )
    target_ds = _MockDatasheet(
        "Target",
        datasheet_id="TARGET",
        unit_comp="1 Target",
        toughness="5",
        wounds="3",
    )

    leader = _make_unit(leader_ds)
    bodyguard = _make_unit(bodyguard_ds)
    target = _make_unit(target_ds)

    army = Army.with_detachment("CSM", "Chaos")
    enemy_army = Army.with_detachment("Enemy", "Enemy")
    leader.set_parent_army(army)
    bodyguard.set_parent_army(army)
    target.set_parent_army(enemy_army)

    leader.attach_to_unit(bodyguard)
    bodyguard.deployed = True
    leader.deployed = True
    target.deployed = True
    bodyguard.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(1.0, 0.0, 0.0, 0.0)

    # Bodyguard model gets +1 Toughness while the leader is attached.
    tough_attached = bodyguard.get_effective_model_characteristic(bodyguard.models[0], "toughness")
    assert int(tough_attached) == 5

    melee_parent = SimpleNamespace(
        name="Chainblade",
        is_melee=lambda: True,
        is_ranged=lambda: False,
    )
    melee_profile = WargearProfile(
        profile_name="Chainblade",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=melee_parent,
    )

    wound_result = melee_profile._wound_target_with_tracking(
        target,
        bodyguard.models[0],
        {"_aura_attack_mods": _make_aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert wound_result.get("wound") is True
    assert any("Enhanced Warriors" in str(mod) for mod in list(wound_result.get("modifiers", []) or []))

    # Once detached, bonuses no longer apply.
    leader.detach_from_unit()
    tough_detached = bodyguard.get_effective_model_characteristic(bodyguard.models[0], "toughness")
    assert int(tough_detached) == 4

    wound_result_no_bonus = melee_profile._wound_target_with_tracking(
        target,
        bodyguard.models[0],
        {"_aura_attack_mods": _make_aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert wound_result_no_bonus.get("wound") is False


def test_enhanced_warriors_applies_while_fabius_starts_embarked_in_transport():
    from warhammer40k_ai.roster.army import Army

    ability_text = (
        "If this unit is attached to a unit at the start of the battle, add 1 to the Strength characteristic of "
        "melee weapons equipped by Bodyguard models in that unit and add 1 to the Toughness characteristic of "
        "Bodyguard models in that unit."
    )
    leader_ds = _MockDatasheet(
        "Fabius Bile",
        datasheet_id="CSM_LEADER_TRANSPORT",
        unit_comp="1 Fabius Bile",
        toughness="5",
        wounds="5",
        abilities=[{"name": "Enhanced Warriors", "description": ability_text, "type": "Datasheet", "parameter": ""}],
        attached_to=["CSM_BODYGUARD_TRANSPORT"],
    )
    bodyguard_ds = _MockDatasheet(
        "Chosen",
        datasheet_id="CSM_BODYGUARD_TRANSPORT",
        unit_comp="1 Chosen",
        toughness="4",
        wounds="2",
    )
    transport_ds = _MockDatasheet(
        "Chaos Rhino",
        datasheet_id="CSM_TRANSPORT",
        unit_comp="1 Chaos Rhino",
        toughness="9",
        wounds="10",
    )

    leader = _make_unit(leader_ds)
    bodyguard = _make_unit(bodyguard_ds)
    transport = _make_unit(transport_ds)

    army = Army.with_detachment("CSM", "Chaos")
    leader.set_parent_army(army)
    bodyguard.set_parent_army(army)
    transport.set_parent_army(army)

    leader.attach_to_unit(bodyguard)
    transport.deployed = True
    bodyguard.deployed = True
    leader.deployed = True
    bodyguard.embarked_in = transport
    leader.embarked_in = transport

    tough_embarked = bodyguard.get_effective_model_characteristic(bodyguard.models[0], "toughness")
    assert int(tough_embarked) == 5
