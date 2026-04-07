from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: str = "4",
        wounds: str = "3",
        movement: str = "6",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Adeptus Custodes"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(movement),
                "T": str(toughness),
                "Sv": "2",
                "W": str(wounds),
                "Ld": "6",
                "OC": "2",
                "base_size": "40mm",
                "inv_sv": "4",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def create_unit(
    name: str,
    x: float,
    y: float,
    *,
    keywords=None,
    faction_keywords=None,
    toughness: str = "4",
    wounds: str = "3",
    movement: str = "6",
) -> Unit:
    unit = Unit(
        MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            toughness=toughness,
            wounds=wounds,
            movement=movement,
        )
    )
    for model in list(unit.models or []):
        model.set_location(x, y, 0.0, 0.0)
    unit.deployed = True
    return unit


def _make_profile(*, skill: str = "4+", strength: str = "4") -> WargearProfile:
    parent = SimpleNamespace(name="Executioner Greatblade", is_melee=lambda: True, is_ranged=lambda: False)
    data = {
        "range": "Melee",
        "A": "1",
        "BS_WS": str(skill),
        "S": str(strength),
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Melee", wargear_data=data, parent_wargear=parent)


def _aura_stub():
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


def _make_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    custodes_army = Army.with_detachment("Adeptus Custodes", "Talons Of The Emperor")
    custodes_army.faction_id = "AC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    custodes_player = Player("Custodes", PlayerControl.REMOTE, army=custodes_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(custodes_player)
    game.add_player(enemy_player)
    return game, custodes_player, enemy_player


def test_revered_companions_null_aegis_grants_conditional_fnp_within_range():
    _game, player, _enemy = _make_game()
    anathema = create_unit(
        "Prosecutors",
        10.0,
        10.0,
        keywords=["ANATHEMA PSYKANA", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    near_unit = create_unit(
        "Custodian Guard",
        14.0,
        10.0,
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    far_unit = create_unit(
        "Custodian Guard Far",
        40.0,
        10.0,
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )

    player.army.add_unit(anathema)
    player.army.add_unit(near_unit)
    player.army.add_unit(far_unit)

    near_model = near_unit.models[0]
    near_entries = list(near_unit.has_feel_no_pain(target_model=near_model) or [])
    assert (5, "against psychic attacks and mortal wounds") in near_entries
    assert near_model._get_best_applicable_fnp(
        near_entries,
        weapon_profile=None,
        is_mortal=True,
        is_psychic_attack=False,
    ) == (5, "against psychic attacks and mortal wounds")
    assert near_model._get_best_applicable_fnp(
        near_entries,
        weapon_profile=None,
        is_mortal=False,
        is_psychic_attack=True,
    ) == (5, "against psychic attacks and mortal wounds")
    assert (
        near_model._get_best_applicable_fnp(
            near_entries,
            weapon_profile=None,
            is_mortal=False,
            is_psychic_attack=False,
        )
        is None
    )

    far_entries = list(far_unit.has_feel_no_pain(target_model=far_unit.models[0]) or [])
    assert (5, "against psychic attacks and mortal wounds") not in far_entries


def test_revered_companions_deadly_unity_adds_hit_bonus_for_anathema_attacks():
    game, player, enemy = _make_game()
    anathema_attacker = create_unit(
        "Witchseekers",
        10.0,
        10.0,
        keywords=["ANATHEMA PSYKANA", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    supporting_custodes = create_unit(
        "Custodian Guard",
        14.0,
        10.0,
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    target = create_unit(
        "Enemy Target",
        20.0,
        10.0,
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    player.army.add_unit(anathema_attacker)
    player.army.add_unit(supporting_custodes)
    enemy.army.add_unit(target)
    game.map.units = [anathema_attacker, supporting_custodes, target]

    profile = _make_profile(skill="4+", strength="4")
    hit_result = profile._hit_target_with_tracking(
        target,
        anathema_attacker.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit_result["hit"] is True
    assert any("Revered Companions" in str(entry or "") for entry in list(hit_result.get("modifiers", []) or []))


def test_revered_companions_deadly_unity_requires_in_range_non_anathema_source():
    game, player, enemy = _make_game()
    anathema_attacker = create_unit(
        "Vigilators",
        10.0,
        10.0,
        keywords=["ANATHEMA PSYKANA", "INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    far_supporting_custodes = create_unit(
        "Custodian Guard",
        40.0,
        10.0,
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS CUSTODES"],
    )
    target = create_unit(
        "Enemy Target",
        20.0,
        10.0,
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    player.army.add_unit(anathema_attacker)
    player.army.add_unit(far_supporting_custodes)
    enemy.army.add_unit(target)
    game.map.units = [anathema_attacker, far_supporting_custodes, target]

    profile = _make_profile(skill="4+", strength="4")
    hit_result = profile._hit_target_with_tracking(
        target,
        anathema_attacker.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert hit_result["hit"] is False
    assert not any("Revered Companions" in str(entry or "") for entry in list(hit_result.get("modifiers", []) or []))
