from types import SimpleNamespace


class _MockDatasheet:
    def __init__(self, name, *, unit_comp="1 Test Model", abilities=None, keywords=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Aeldari"}
        self.keywords = list(keywords or [])
        self.faction_keywords = ["AELDARI"]
        self.datasheets_unit_composition = [{"description": unit_comp}]
        self.datasheets_models_cost = [{"description": unit_comp, "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "3",
                "Sv": "5",
                "W": "4",
                "Ld": "7",
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
        self.attached_to = []


def _make_unit(name, *, ability_desc=None):
    from warhammer40k_ai.units.unit import Unit

    abilities = []
    if ability_desc:
        abilities.append(
            {
                "name": name,
                "description": ability_desc,
                "type": "Datasheet",
                "parameter": "",
            }
        )
    datasheet = _MockDatasheet(name, abilities=abilities)
    return Unit(datasheet)


def test_first_failed_save_sets_damage_zero_once_per_turn():
    from warhammer40k_ai.units.wargear import WargearProfile

    ability = (
        "Once per turn, the first time a saving throw is failed for the bearer's unit, "
        "change the Damage characteristic of that attack to 0."
    )
    unit = _make_unit("Harlequin", ability_desc=ability)
    attacker_unit = _make_unit("Attacker")

    game = SimpleNamespace(turn=1)
    player = SimpleNamespace(id="P1", game=game)
    enemy_player = SimpleNamespace(id="P2", game=game)
    army = SimpleNamespace(player=player, units=[unit])
    enemy_army = SimpleNamespace(player=enemy_player, units=[attacker_unit])
    player.get_army = lambda: army
    enemy_player.get_army = lambda: enemy_army
    unit.set_parent_army(army)
    attacker_unit.set_parent_army(enemy_army)

    class _WargearStub:
        name = "Test Gun"

        def is_ranged(self):
            return True

        def is_melee(self):
            return False

    profile = WargearProfile(
        "Test Gun",
        {"range": "24", "A": "1", "BS_WS": "3+", "S": "4", "AP": "0", "D": "2", "description": ""},
        parent_wargear=_WargearStub(),
    )

    target_model = unit.models[0]
    attacker_model = attacker_unit.models[0]

    attack_instance = {}
    save_result = profile._save_with_tracking(
        target_model,
        attack_instance,
        ap=0,
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )
    assert save_result["saved"] is False
    assert attack_instance.get("force_damage_zero") is True

    damage_result = profile._damage_target_with_tracking(
        target_model,
        attacker_model,
        attack_instance,
        roll_value=2,
        allow_rerolls=False,
    )
    assert damage_result["damage_applied"] == 0

    # Second failed save in same turn should not set damage to 0 again.
    attack_instance_2 = {}
    save_result_2 = profile._save_with_tracking(
        target_model,
        attack_instance_2,
        ap=0,
        roll_value=1,
        allow_rerolls=False,
        log_roll=False,
    )
    assert save_result_2["saved"] is False
    assert attack_instance_2.get("force_damage_zero") is not True
