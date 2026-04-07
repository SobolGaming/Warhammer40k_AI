from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit


VANGUARD_PREDATOR_TEXT = (
    "Each time a model in this unit makes an attack, re-roll a Hit roll of 1. "
    "If the target is within range of one or more objective markers, re-roll a Wound roll of 1 as well."
)


class _MockDatasheet:
    def __init__(self, name: str, *, abilities=None):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = ["INFANTRY"]
        self.faction_keywords = ["TYRANIDS"]
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model(s)", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "4",
                "Sv": "5",
                "W": "1",
                "Ld": "7",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name: str, *, abilities=None) -> Unit:
    unit = Unit(_MockDatasheet(name, abilities=abilities), quantity=1)
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def test_vanguard_predator_grants_hit_reroll_ones_and_objective_wound_reroll_ones():
    tyr_army = Army.with_detachment("Tyranids", detachment_type="Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    attacker = _make_unit(
        "Genestealers",
        abilities=[
            {
                "name": "Vanguard Predator",
                "description": VANGUARD_PREDATOR_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
    )
    target = _make_unit("Enemy Unit")
    tyr_army.add_unit(attacker)
    enemy_army.add_unit(target)
    attacker._target_within_objective_range = lambda _target=None, game_map=None: True

    hit_mods = attacker.get_unit_hit_reroll_modifiers("melee", target=target)
    wound_mods = attacker.get_unit_wound_reroll_modifiers("melee", target=target)

    assert 1 in tuple(hit_mods.get("reroll_hit_values", ()) or ())
    assert 1 in tuple(wound_mods.get("reroll_wound_values", ()) or ())


def test_vanguard_predator_objective_wound_reroll_does_not_apply_off_objective():
    attacker = _make_unit(
        "Genestealers",
        abilities=[
            {
                "name": "Vanguard Predator",
                "description": VANGUARD_PREDATOR_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
    )
    target = _make_unit("Enemy Unit")
    attacker._target_within_objective_range = lambda _target=None, game_map=None: False

    hit_mods = attacker.get_unit_hit_reroll_modifiers("melee", target=target)
    wound_mods = attacker.get_unit_wound_reroll_modifiers("melee", target=target)

    assert 1 in tuple(hit_mods.get("reroll_hit_values", ()) or ())
    assert 1 not in tuple(wound_mods.get("reroll_wound_values", ()) or ())
