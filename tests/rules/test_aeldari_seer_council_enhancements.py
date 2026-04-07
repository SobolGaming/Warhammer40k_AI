from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.name = name
        self.faction_data = {"name": "Aeldari"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _make_unit(name: str, army: Army, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    army.add_unit(unit)
    return unit


def _make_ranged_profile(*, name: str, range_val: str, keywords: str):
    weapon = Wargear(
        {
            "name": name,
            "type": "Ranged",
            "range": str(range_val),
            "A": "1",
            "BS_WS": "3",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": keywords,
        }
    )
    return weapon.profiles["default"]


def test_seer_council_enhancements_have_tool_descriptors():
    lucid = get_enhancement_tool_descriptor(enhancement_id="000009923002")
    assert lucid is not None
    assert lucid.name == "Lucid Eye"
    assert lucid.effect == "adjust_fate_die_value"

    runes = get_enhancement_tool_descriptor(enhancement_id="000009923003")
    assert runes is not None
    assert runes.name == "Runes of Warding"
    assert runes.effect == "bearer_unit_fnp_conditional"

    stone = get_enhancement_tool_descriptor(enhancement_id="000009923004")
    assert stone is not None
    assert stone.name == "Stone of Eldritch Fury"
    assert stone.effect == "bearer_psychic_ranged_range_bonus"


def test_lucid_eye_queues_and_applies_fate_die_adjustment():
    army = Army.with_detachment("Aeldari", detachment_type="Seer Council")
    army.faction_id = "AE"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"

    player = Player("Player", PlayerControl.REMOTE, army=army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player, enemy_player])
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0

    bearer = _make_unit(
        "Farseer",
        army,
        keywords=["INFANTRY", "CHARACTER", "PSYKER"],
        faction_keywords=["AELDARI"],
    )
    enhancement = Enhancement(
        id="000009923002",
        name="Lucid Eye",
        faction_id="AE",
        detachment="Seer Council",
    )
    bearer.enhancement = enhancement
    enhancement.apply_to_unit(bearer)

    army.aeldari_detachments.seer_council_fate_dice = [2, 5]
    game.map.units = [bearer]
    game.rebuild_entity_registry()

    game._on_phase_start_aeldari_enhancements(player=player, phase=game.phase)
    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_CHOOSE_QUARRY
    assert str((request.context or {}).get("ability", "") or "") == "aeldari_lucid_eye_fate_die"
    assert any(str((opt.payload or {}).get("action", "") or "") == "skip" for opt in list(request.options or []))

    pick = next(
        opt
        for opt in list(request.options or [])
        if int((opt.payload or {}).get("die_index", -1)) == 0 and int((opt.payload or {}).get("delta", 0)) == 1
    )
    result = resolve_decision_command(game, request, pick.option_id, player_id=player.id)
    assert bool(getattr(result, "ok", False))
    assert list(army.aeldari_detachments.seer_council_fate_dice) == [3, 5]


def test_lucid_eye_rejects_invalid_adjustment_payload():
    army = Army.with_detachment("Aeldari", detachment_type="Seer Council")
    army.faction_id = "AE"
    player = Player("Player", PlayerControl.REMOTE, army=army)
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[player])
    game.phase = BattleRoundPhases.COMMAND_PHASE
    game.current_player_index = 0

    bearer = _make_unit(
        "Farseer",
        army,
        keywords=["INFANTRY", "CHARACTER", "PSYKER"],
        faction_keywords=["AELDARI"],
    )
    enhancement = Enhancement(
        id="000009923002",
        name="Lucid Eye",
        faction_id="AE",
        detachment="Seer Council",
    )
    bearer.enhancement = enhancement
    enhancement.apply_to_unit(bearer)
    game.map.units = [bearer]
    game.rebuild_entity_registry()

    army.aeldari_detachments.seer_council_fate_dice = [6]
    request = DecisionRequest.create(
        DECISION_CHOOSE_QUARRY,
        "Lucid Eye: select one Fate die adjustment (or None).",
        player_id=getattr(player, "id", None),
        options=[DecisionOption.create("Invalid", payload={"die_index": 0, "delta": 1})],
        context={
            "ability": "aeldari_lucid_eye_fate_die",
            "ability_name": "Lucid Eye",
            "source_unit_id": str(bearer.id),
            "unit_id": str(bearer.id),
            "optional": True,
        },
    )
    decision_result = DecisionResult(
        decision_id=request.decision_id,
        player_id=getattr(player, "id", None),
        option_id=str(request.options[0].option_id),
        payload={},
    )
    apply_result = dispatch_decision(game, request, decision_result)

    assert apply_result.ok is False
    assert any("legal fate die adjustment" in str(err).lower() for err in list(apply_result.errors or []))
    assert list(army.aeldari_detachments.seer_council_fate_dice) == [6]


def test_stone_of_eldritch_fury_applies_only_to_bearer_ranged_psychic_weapons():
    army = Army.with_detachment("Aeldari", detachment_type="Seer Council")
    army.faction_id = "AE"

    bearer = _make_unit(
        "Warlock",
        army,
        keywords=["INFANTRY", "CHARACTER", "PSYKER"],
        faction_keywords=["AELDARI"],
    )
    ally = _make_unit(
        "Guardian",
        army,
        keywords=["INFANTRY"],
        faction_keywords=["AELDARI"],
    )
    enhancement = Enhancement(
        id="000009923004",
        name="Stone of Eldritch Fury",
        faction_id="AE",
        detachment="Seer Council",
    )
    bearer.enhancement = enhancement
    enhancement.apply_to_unit(bearer)

    bearer_model = bearer.models[0]
    ally_model = ally.models[0]
    psychic_profile = _make_ranged_profile(name="Singing Spear", range_val="24", keywords="Psychic")
    normal_profile = _make_ranged_profile(name="Shuriken Pistol", range_val="24", keywords="")

    assert int(psychic_profile._effective_range_max(bearer_model) or 0) == 36
    assert int(normal_profile._effective_range_max(bearer_model) or 0) == 24
    assert int(psychic_profile._effective_range_max(ally_model) or 0) == 24


def test_runes_of_warding_applies_fnp_conditions():
    army = Army.with_detachment("Aeldari", detachment_type="Seer Council")
    army.faction_id = "AE"

    bearer = _make_unit(
        "Farseer",
        army,
        keywords=["INFANTRY", "CHARACTER", "PSYKER"],
        faction_keywords=["AELDARI"],
    )

    enhancement = Enhancement(
        id="000009923003",
        name="Runes of Warding",
        faction_id="AE",
        detachment="Seer Council",
        description=(
            "Farseer model only. Models in the bearer's unit have the "
            "Feel No Pain 4+ ability against mortal wounds, Psychic Attacks and each attack made as the result "
            "of a Critical Wound where the attacking weapon had [DEVASTATING WOUNDS]."
        ),
    )
    bearer.enhancement = enhancement
    enhancement.apply_to_unit(bearer)
    refresh = getattr(bearer, "_refresh_bearer_unit_common_modifiers", None)
    assert callable(refresh)
    refresh()

    fnp_entries = list((bearer.special_rules or {}).get("bearer_unit_fnp", []) or [])
    assert any(int(entry.get("value", 0) or 0) == 4 for entry in fnp_entries if isinstance(entry, dict))

    target_model = bearer.models[0]
    fnp_abilities = list(bearer.has_feel_no_pain(target_model=target_model) or [])
    assert any(int(val) == 4 for val, _cond in fnp_abilities)

    psychic_profile = _make_ranged_profile(name="Mind Blast", range_val="18", keywords="Psychic")
    normal_profile = _make_ranged_profile(name="Boltgun", range_val="24", keywords="")
    devastating_profile = _make_ranged_profile(name="D-Cannon", range_val="24", keywords="Devastating Wounds")

    best_mortal = target_model._get_best_applicable_fnp(
        fnp_abilities,
        weapon_profile=None,
        is_mortal=True,
        attack_context={},
    )
    assert best_mortal is not None and int(best_mortal[0]) == 4

    best_psychic = target_model._get_best_applicable_fnp(
        fnp_abilities,
        weapon_profile=psychic_profile,
        is_mortal=False,
        is_psychic_attack=True,
        attack_context={},
    )
    assert best_psychic is not None and int(best_psychic[0]) == 4

    best_dev_crit = target_model._get_best_applicable_fnp(
        fnp_abilities,
        weapon_profile=devastating_profile,
        is_mortal=False,
        attack_context={"attack_instance": {"crit_wound": True}},
    )
    assert best_dev_crit is not None and int(best_dev_crit[0]) == 4

    best_normal = target_model._get_best_applicable_fnp(
        fnp_abilities,
        weapon_profile=normal_profile,
        is_mortal=False,
        attack_context={"attack_instance": {"crit_wound": False}},
    )
    assert best_normal is None
