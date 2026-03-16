import os
from types import SimpleNamespace

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


SIGNUM_ABILITY = {
    "name": "Signum",
    "description": (
        "Each time this unit Remains Stationary, until the start of your next Movement phase, "
        "ranged weapons equipped by models in this unit have the [IGNORES COVER] ability."
    ),
    "type": "Datasheet",
    "parameter": "",
}

ARMORIUM_CHERUB_ABILITY = {
    "name": "Armorium Cherub",
    "description": (
        "Once per battle, after making a Hit roll for a model in this unit, you can change that roll "
        "to an unmodified 6. Designer's Note: Place an Armorium Cherub token next to the unit, "
        "removing it once this ability has been used."
    ),
    "type": "Datasheet",
    "parameter": "",
}

DESIGNER_NOTE_ABILITY = {
    "name": "Designer's Note",
    "description": "Place an Armorium Cherub token next to the unit, removing it once this ability has been used.",
    "type": "Datasheet",
    "parameter": "",
}

TARGETER_OPTICS_DESCRIPTION = (
    "Each time this unit Remains Stationary, until the start of your next Movement phase, "
    "ranged weapons equipped by models in this unit have the [IGNORES COVER] ability."
)


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, faction_name="Space Marines", faction_keywords=None, keywords=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or ["INFANTRY"])
        self.faction_keywords = list(faction_keywords or ["ADEPTUS ASTARTES"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
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
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(name, *, abilities=None, faction_name="Space Marines", faction_keywords=None, keywords=None):
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            faction_name=faction_name,
            faction_keywords=faction_keywords,
            keywords=keywords,
        )
    )
    unit.name = name
    return unit


def _make_profile():
    parent = SimpleNamespace(name="Lascannon", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="default",
        wargear_data={
            "range": "48",
            "A": "1",
            "BS_WS": "3+",
            "S": "12",
            "AP": "-3",
            "D": "D6+1",
            "description": "",
        },
        parent_wargear=parent,
    )


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


def _build_game():
    sm_army = Army("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[sm_player, enemy_player])
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.turn = 1
    return game, sm_army, enemy_army, sm_player, enemy_player


def _seed_support_maps():
    import scripts.generate_ability_support_matrix as gsm

    abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json"))
    detachment_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json"))
    gsm.DETACHMENT_ABILITY_IDS = {
        str(row.get("id", "") or "").strip()
        for row in detachment_abilities
        if str(row.get("id", "") or "").strip()
    }
    gsm._seed_ability_support_maps(abilities, detachment_abilities)
    return gsm


def test_signum_grants_ignores_cover_while_stationary_through_opponent_turn():
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game()
    attacker = _make_unit("Devastator Squad", abilities=[SIGNUM_ABILITY])
    target = _make_unit("Enemy Unit", faction_name="Enemy", faction_keywords=["ENEMY"])

    sm_army.add_unit(attacker)
    enemy_army.add_unit(target)
    attacker.deployed = True
    target.deployed = True
    attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(12.0, 0.0, 0.0, 0.0)
    attacker.round_state.remained_stationary_this_round = True
    game.map.units = [attacker, target]
    game.current_player_index = 1

    bonuses = attacker.get_model_weapon_keyword_bonuses(
        target=target,
        attack_type="ranged",
        model=attacker.models[0],
        weapon_profile=_make_profile(),
    )

    assert bonuses.get("ignores_cover") is True

    attacker.round_state.remained_stationary_this_round = False
    cleared = attacker.get_model_weapon_keyword_bonuses(
        target=target,
        attack_type="ranged",
        model=attacker.models[0],
        weapon_profile=_make_profile(),
    )

    assert cleared.get("ignores_cover") is not True


def test_armorium_cherub_sets_hit_roll_to_six_once_per_battle():
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()
    attacker = _make_unit("Devastator Squad", abilities=[ARMORIUM_CHERUB_ABILITY])
    target = _make_unit("Enemy Unit", faction_name="Enemy", faction_keywords=["ENEMY"])

    sm_army.add_unit(attacker)
    enemy_army.add_unit(target)
    attacker.deployed = True
    target.deployed = True
    attacker.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    target.models[0].set_location(10.0, 0.0, 0.0, 0.0)
    game.map.units = [attacker, target]
    game.rebuild_entity_registry()
    game.current_player_index = 0

    specs = list(attacker.unit_once_per_battle_unmodified_six_specs() or [])
    assert len(specs) == 1
    assert tuple(specs[0].get("allowed_roll_types", ())) == ("hit",)

    sm_player.set_next_optional_selection("MODEL_UNMODIFIED_SIX", "use")
    profile = _make_profile()
    first = profile._hit_target_with_tracking(
        target,
        attacker.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )

    assert int(first.get("roll", 0) or 0) == 6
    assert attacker.has_used_unit_once_per_battle(str(specs[0].get("key", "") or ""))

    sm_player.set_next_optional_selection("MODEL_UNMODIFIED_SIX", "use")
    second = profile._hit_target_with_tracking(
        target,
        attacker.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=2,
        allow_rerolls=False,
        log_roll=False,
    )

    assert int(second.get("roll", 0) or 0) == 2


def test_support_matrix_classifies_devastator_abilities_as_supported():
    gsm = _seed_support_maps()

    status, notes = gsm._classify_ability("Signum", SIGNUM_ABILITY["description"], faction_id="SM")
    assert status == "Supported"
    assert "ignores cover" in str(notes or "").lower()

    status, notes = gsm._classify_ability("Armorium Cherub", ARMORIUM_CHERUB_ABILITY["description"], faction_id="SM")
    assert status == "Supported"
    assert "unmodified 6" in str(notes or "").lower()

    status, notes = gsm._classify_ability("Designer's Note", DESIGNER_NOTE_ABILITY["description"], faction_id="SM")
    assert status == "Supported"
    assert "tracked by the engine" in str(notes or "").lower()

    status, notes = gsm._classify_ability("Targeter Optics", TARGETER_OPTICS_DESCRIPTION, faction_id="SM")
    assert status == "Supported"
    assert "ignores cover" in str(notes or "").lower()
