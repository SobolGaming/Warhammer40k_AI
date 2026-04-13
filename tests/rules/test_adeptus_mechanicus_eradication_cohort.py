from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.adeptus_mechanicus_thulia_ghuld import apply_the_fires_of_mars
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


DOCTRINA_IMPERATIVES_TEXT = "Doctrina Imperatives."


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Adeptus Mechanicus",
        keywords=None,
        faction_keywords=None,
        abilities=None,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
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
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_ability(name: str, description: str) -> dict:
    return {"name": name, "description": description, "type": "Datasheet", "parameter": ""}


def _make_unit(
    name: str,
    *,
    faction_name: str = "Adeptus Mechanicus",
    keywords=None,
    faction_keywords=None,
    abilities=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    admech_army = Army.with_detachment("Adeptus Mechanicus", detachment_type="Eradication Cohort")
    admech_army.faction_id = "ADM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"
    admech_player = Player("P1", PlayerControl.REMOTE, army=admech_army)
    enemy_player = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(admech_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, admech_army, enemy_army


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


def _ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def _melee_profile() -> WargearProfile:
    parent = SimpleNamespace(name="Test Blade", is_melee=lambda: True, is_ranged=lambda: False)
    return WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_murderous_imperative_rerolls_hit_rolls_of_one_while_protector_is_active():
    game, admech_army, enemy_army = _build_game()
    skitarii = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        abilities=[_make_ability("Doctrina Imperatives", DOCTRINA_IMPERATIVES_TEXT)],
    )
    target = _make_unit(
        "Enemy Intercessors",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    admech_army.add_unit(skitarii)
    enemy_army.add_unit(target)
    game.map.units = [skitarii, target]
    game.rebuild_entity_registry()

    assert admech_army.doctrina_imperatives.select_imperative("PROTECTOR", battle_round=1) is True

    from warhammer40k_ai.units import wargear as wargear_mod

    seq = iter([1, 5])
    old_get_roll = wargear_mod.get_roll
    wargear_mod.get_roll = lambda _spec: next(seq)
    try:
        hit_result = _ranged_profile()._hit_target_with_tracking(
            target,
            skitarii.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )
    finally:
        wargear_mod.get_roll = old_get_roll

    assert hit_result.get("reroll") == 5
    assert any(
        "Murderous Imperative" in str(reason or "")
        for reason in list(hit_result.get("reroll_value_reasons", []) or [])
    )


def test_murderous_imperative_rerolls_wound_rolls_of_one_while_conqueror_is_active():
    game, admech_army, enemy_army = _build_game()
    skitarii = _make_unit(
        "Skitarii Rangers",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        abilities=[_make_ability("Doctrina Imperatives", DOCTRINA_IMPERATIVES_TEXT)],
    )
    target = _make_unit(
        "Enemy Intercessors",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    admech_army.add_unit(skitarii)
    enemy_army.add_unit(target)
    game.map.units = [skitarii, target]
    game.rebuild_entity_registry()

    assert admech_army.doctrina_imperatives.select_imperative("CONQUEROR", battle_round=1) is True

    from warhammer40k_ai.units import wargear as wargear_mod

    seq = iter([1, 4])
    old_get_roll = wargear_mod.get_roll
    wargear_mod.get_roll = lambda _spec: next(seq)
    try:
        wound_result = _melee_profile()._wound_target_with_tracking(
            target,
            skitarii.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )
    finally:
        wargear_mod.get_roll = old_get_roll

    assert wound_result.get("reroll") == 4
    assert any(
        "Murderous Imperative" in str(reason or "")
        for reason in list(wound_result.get("reroll_value_reasons", []) or [])
    )


def test_murderous_imperative_honours_temporary_both_imperatives_effects():
    game, admech_army, enemy_army = _build_game()
    thulia = _make_unit(
        "Thulia Ghuld",
        keywords=["INFANTRY", "CHARACTER", "THULIA GHULD"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    skitarii = _make_unit(
        "Skitarii Vanguard",
        keywords=["INFANTRY", "SKITARII", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        abilities=[_make_ability("Doctrina Imperatives", DOCTRINA_IMPERATIVES_TEXT)],
    )
    target = _make_unit(
        "Enemy Intercessors",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    admech_army.add_unit(thulia)
    admech_army.add_unit(skitarii)
    enemy_army.add_unit(target)
    game.map.units = [thulia, skitarii, target]
    game.rebuild_entity_registry()

    apply_the_fires_of_mars(thulia, skitarii)

    from warhammer40k_ai.units import wargear as wargear_mod

    hit_seq = iter([1, 5])
    old_get_roll = wargear_mod.get_roll
    wargear_mod.get_roll = lambda _spec: next(hit_seq)
    try:
        hit_result = _ranged_profile()._hit_target_with_tracking(
            target,
            skitarii.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )
    finally:
        wargear_mod.get_roll = old_get_roll

    wound_seq = iter([1, 4])
    wargear_mod.get_roll = lambda _spec: next(wound_seq)
    try:
        wound_result = _melee_profile()._wound_target_with_tracking(
            target,
            skitarii.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )
    finally:
        wargear_mod.get_roll = old_get_roll

    assert hit_result.get("reroll") == 5
    assert wound_result.get("reroll") == 4
    assert any(
        "Murderous Imperative" in str(reason or "")
        for reason in list(hit_result.get("reroll_value_reasons", []) or [])
    )
    assert any(
        "Murderous Imperative" in str(reason or "")
        for reason in list(wound_result.get("reroll_value_reasons", []) or [])
    )


def test_murderous_imperative_does_not_apply_to_non_skitarii_units():
    game, admech_army, enemy_army = _build_game()
    destroyers = _make_unit(
        "Kataphron Destroyers",
        keywords=["INFANTRY", "CULT MECHANICUS"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        abilities=[_make_ability("Doctrina Imperatives", DOCTRINA_IMPERATIVES_TEXT)],
    )
    target = _make_unit(
        "Enemy Intercessors",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    admech_army.add_unit(destroyers)
    enemy_army.add_unit(target)
    game.map.units = [destroyers, target]
    game.rebuild_entity_registry()

    assert admech_army.doctrina_imperatives.select_imperative("PROTECTOR", battle_round=1) is True

    from warhammer40k_ai.units import wargear as wargear_mod

    seq = iter([1])
    old_get_roll = wargear_mod.get_roll
    wargear_mod.get_roll = lambda _spec: next(seq)
    try:
        hit_result = _ranged_profile()._hit_target_with_tracking(
            target,
            destroyers.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )
    finally:
        wargear_mod.get_roll = old_get_roll

    assert hit_result.get("reroll") is None
    assert not any(
        "Murderous Imperative" in str(reason or "")
        for reason in list(hit_result.get("reroll_value_reasons", []) or [])
    )
