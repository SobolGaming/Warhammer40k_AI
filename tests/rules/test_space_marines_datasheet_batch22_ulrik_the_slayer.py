from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_START_OF_BATTLE_KEYWORD
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        toughness: int = 4,
        wounds: int = 4,
    ) -> None:
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
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
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""
        self.attached_to = []


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _mock_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    toughness: int = 4,
    wounds: int = 4,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            toughness=toughness,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(*, detachment_type: str = "Other"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", detachment_type=detachment_type)
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army, sm_player, enemy_player


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    try:
        leader.attach_to_unit(bodyguard)
    except Exception:
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]
        for unit in (leader, bodyguard):
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()


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


def _make_melee_profile():
    weapon = Wargear(
        {
            "name": "Test Blade",
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def test_ulrik_slayer_oath_queues_start_of_battle_keyword_selection_and_stores_non_reroll_choice():
    game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()
    bodyguard = _mock_unit(
        "Blood Claws",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=5,
    )
    ulrik = _actual_unit("Ulrik The Slayer", datasheet_id="000000297")

    sm_army.add_unit(bodyguard)
    sm_army.add_unit(ulrik)
    _attach_leader(bodyguard, ulrik)
    bodyguard._refresh_bearer_unit_common_modifiers()
    _register_units(game, bodyguard, ulrik)

    game.event_system.publish("battle_round_started", game=game, battle_round=1)

    request = next(
        req
        for req in list(game.decision_queue.list() or [])
        if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_START_OF_BATTLE_KEYWORD
        and str((req.context or {}).get("ability_name", "") or "") == "Slayer's Oath"
    )

    option = next(
        opt
        for opt in list(request.options or [])
        if str(getattr(opt, "label", "") or "").strip().upper() == "CHARACTER"
    )
    resolve_decision_command(game, request, option.option_id, player_id=sm_player.id)

    ability_key = str((request.context or {}).get("ability_key", "") or "")
    choice = ulrik.get_start_of_battle_keyword_reroll_choice(ulrik.models[0], ability_key=ability_key)

    assert choice is not None
    assert str(choice.get("keyword", "") or "").upper() == "CHARACTER"
    assert str(choice.get("selection_kind", "") or "") == "slayers_oath"
    assert bool(choice.get("reroll_hit_ones", True)) is False
    assert bool(choice.get("reroll_wound_ones", True)) is False


def test_ulrik_oathbound_adds_wound_bonus_for_attached_unit_melee_attacks_vs_selected_keyword():
    bodyguard = _mock_unit(
        "Blood Claws",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=5,
    )
    ulrik = _actual_unit("Ulrik The Slayer", datasheet_id="000000297")
    _attach_leader(bodyguard, ulrik)
    bodyguard._refresh_bearer_unit_common_modifiers()

    ulrik.apply_start_of_battle_keyword_reroll_choice(
        ulrik.models[0],
        keyword="CHARACTER",
        source="Slayer's Oath",
        ability_key="slayers_oath",
        selection_kind="slayers_oath",
        reroll_hit_ones=False,
        reroll_wound_ones=False,
    )

    profile = _make_melee_profile()
    character_target = _mock_unit(
        "Enemy Character",
        keywords=["CHARACTER"],
        faction_keywords=["ENEMY"],
        toughness=4,
        wounds=4,
    )
    infantry_target = _mock_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        toughness=4,
        wounds=4,
    )

    character_wound = profile._wound_target_with_tracking(
        character_target,
        bodyguard.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    infantry_wound = profile._wound_target_with_tracking(
        infantry_target,
        bodyguard.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )

    assert character_wound.get("wound") is True
    assert infantry_wound.get("wound") is False
    assert any("Oathbound" in reason for reason in list(character_wound.get("modifiers", []) or []))
    assert not any("Oathbound" in reason for reason in list(infantry_wound.get("modifiers", []) or []))


def test_ulrik_slayer_oath_matching_kill_grants_unit_specific_pack_quarry_completion():
    game, sm_army, enemy_army, _sm_player, _enemy_player = _build_game(detachment_type="Saga of the Hunter")
    bodyguard = _mock_unit(
        "Blood Claws",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=5,
    )
    ulrik = _actual_unit("Ulrik The Slayer", datasheet_id="000000297")
    wrong_target = _mock_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=1,
    )
    slain_target = _mock_unit(
        "Enemy Character",
        keywords=["CHARACTER"],
        faction_keywords=["ENEMY"],
        model_count=1,
    )
    later_target = _mock_unit(
        "Enemy Scouts",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=1,
    )

    sm_army.add_unit(bodyguard)
    sm_army.add_unit(ulrik)
    enemy_army.add_unit(wrong_target)
    enemy_army.add_unit(slain_target)
    enemy_army.add_unit(later_target)
    _attach_leader(bodyguard, ulrik)
    bodyguard._refresh_bearer_unit_common_modifiers()
    _register_units(game, bodyguard, ulrik, wrong_target, slain_target, later_target)

    ulrik.apply_start_of_battle_keyword_reroll_choice(
        ulrik.models[0],
        keyword="CHARACTER",
        source="Slayer's Oath",
        ability_key="slayers_oath",
        selection_kind="slayers_oath",
        reroll_hit_ones=False,
        reroll_wound_ones=False,
    )

    melee_profile = _make_melee_profile()
    sm_mgr = sm_army.space_marines_detachments

    before_bonus, _before_source = sm_mgr.pack_quarry_wound_bonus(
        bodyguard.models[0],
        later_target,
        weapon_profile=melee_profile,
    )
    assert int(before_bonus or 0) == 0

    game._on_unit_destroyed_recalculating(unit=wrong_target, destroyed_by_unit=bodyguard)
    wrong_bonus, _wrong_source = sm_mgr.pack_quarry_wound_bonus(
        bodyguard.models[0],
        later_target,
        weapon_profile=melee_profile,
    )
    assert int(wrong_bonus or 0) == 0

    game._on_unit_destroyed_recalculating(unit=slain_target, destroyed_by_unit=bodyguard)
    after_bonus, after_source = sm_mgr.pack_quarry_wound_bonus(
        bodyguard.models[0],
        later_target,
        weapon_profile=melee_profile,
    )

    assert int(after_bonus or 0) == 1
    assert str(after_source or "") == "Pack's Quarry"
    assert bool(bodyguard.special_rules.get("ulrik_slayers_oath_saga_completed")) is True
