from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        ds_id: str = "",
        abilities=None,
        faction_name: str = "T'au Empire",
        faction_keywords=None,
        attached_to=None,
        leadership: str = "7",
    ):
        self.id = ds_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = []
        self.faction_keywords = list(faction_keywords or [faction_name.upper()])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": leadership,
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


def _make_unit(name: str, *, abilities=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities)
    return Unit(datasheet)


def test_rites_of_feasting_upgrades_fnp_after_fight_phase_unit_destroy():
    from warhammer40k_ai.engine.game import Game

    rites_of_feasting = {
        "name": "Rites of Feasting",
        "description": (
            "While this model is leading a unit, models in that unit have the Feel No Pain 6+ ability. "
            "If that unit destroys one or more enemy units in the Fight phase, until the end of the battle, "
            "models in that unit have the Feel No Pain 5+ ability instead."
        ),
        "type": "Datasheet",
        "parameter": "",
    }

    leader = _make_unit("Kroot Flesh Shaper", abilities=[rites_of_feasting])
    bodyguard = _make_unit("Kroot Carnivores")
    bodyguard.attached_leaders = [leader]
    leader.attached_to = bodyguard
    leader.can_be_attached_to = ["Kroot Carnivores"]
    bodyguard._refresh_bearer_unit_common_modifiers()

    attacker_player = SimpleNamespace(id="P1")
    defender_player = SimpleNamespace(id="P2")
    attacker_army = SimpleNamespace(player=attacker_player)
    defender_army = SimpleNamespace(player=defender_player)
    bodyguard.set_parent_army(attacker_army)
    leader.set_parent_army(attacker_army)

    enemy_unit = _make_unit("Enemy Unit")
    enemy_unit.set_parent_army(defender_army)

    fnp_before = list(bodyguard.has_feel_no_pain(target_model=bodyguard.models[0]) or [])
    assert any(int(value) == 6 for value, _cond in fnp_before)
    assert not any(int(value) == 5 for value, _cond in fnp_before)

    game_stub = SimpleNamespace(
        phase=SimpleNamespace(name="FIGHT_PHASE"),
        turn=1,
        _phase_enemy_unit_destroyers={},
        get_current_player=lambda: attacker_player,
    )

    Game._on_unit_destroyed_phase_kill_tracking(
        game_stub,
        unit=enemy_unit,
        destroyed_by_unit=bodyguard,
        destroyed_by_model=bodyguard.models[0],
    )

    fnp_after = list(bodyguard.has_feel_no_pain(target_model=bodyguard.models[0]) or [])
    assert any(int(value) == 5 for value, _cond in fnp_after)
    assert bool(bodyguard.special_rules.get("fight_phase_destroy_enemy_fnp_upgrade_active"))
