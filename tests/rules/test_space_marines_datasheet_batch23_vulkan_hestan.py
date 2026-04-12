from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        datasheet_id: str,
        keywords=None,
        faction_keywords=None,
    ) -> None:
        self.id = datasheet_id
        self.name = name
        self.faction_data = {"name": "Space Marines"}
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
                "W": "2",
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
        self.attached_to_names = []


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _mock_unit(name: str, *, datasheet_id: str, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            datasheet_id=datasheet_id,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, sm_army, enemy_army, sm_player, enemy_player


def _deploy(unit: Unit, x: float, y: float) -> None:
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(index) * 0.1), float(y), 0.0, 0.0)


def _find_request(game: Game, ability_key: str):
    return next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == ability_key
        ),
        None,
    )


def _find_option_for_unit(request, unit: Unit) -> str | None:
    unit_id = str(get_entity_id(unit) or "")
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") == unit_id:
            return str(option.option_id)
    return None


def _find_option_for_objective(request, objective_id: str) -> str | None:
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("objective_id", "") or "") == str(objective_id):
            return str(option.option_id)
    return None


def _profile(name: str, description: str) -> WargearProfile:
    return WargearProfile(
        "default",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": description,
        },
        parent_wargear=SimpleNamespace(name=name, is_ranged=lambda: True, is_melee=lambda: False),
    )


def test_vulkan_hestan_forgefather_marks_visible_target_for_torrent_and_melta_wound_rerolls() -> None:
    game, sm_army, enemy_army, sm_player, _enemy_player = _build_game()

    vulkan = _actual_unit("Vulkan He'stan", datasheet_id="000002726")
    adeptus_astartes = _mock_unit(
        "Infernus Squad",
        datasheet_id="infernus-squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    non_astartes = _mock_unit(
        "Imperial Servitors",
        datasheet_id="imperial-servitors",
        keywords=["INFANTRY"],
        faction_keywords=["IMPERIUM"],
    )
    target = _mock_unit(
        "Enemy Target",
        datasheet_id="enemy-target",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    other_target = _mock_unit(
        "Other Enemy",
        datasheet_id="other-enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    sm_army.add_unit(vulkan)
    sm_army.add_unit(adeptus_astartes)
    sm_army.add_unit(non_astartes)
    enemy_army.add_unit(target)
    enemy_army.add_unit(other_target)

    _deploy(vulkan, 0.0, 0.0)
    _deploy(adeptus_astartes, 2.0, 0.0)
    _deploy(non_astartes, 4.0, 0.0)
    _deploy(target, 10.0, 0.0)
    _deploy(other_target, 12.0, 2.0)
    game.map.units = [vulkan, adeptus_astartes, non_astartes, target, other_target]
    game.rebuild_entity_registry()

    game._on_phase_start_forgefather(player=sm_player, phase=BattleRoundPhases.SHOOTING_PHASE)
    request = _find_request(game, "forgefather")
    assert request is not None

    option_id = _find_option_for_unit(request, target)
    assert option_id is not None
    result = resolve_decision_command(game, request, option_id, player_id=sm_player.id)
    assert bool(getattr(result, "ok", False)) is True

    target_rules = dict(getattr(target, "special_rules", {}) or {})
    assert bool(target_rules.get("forgefather_active", False)) is True
    assert str(target_rules.get("forgefather_source", "") or "") == "Forgefather"
    assert set(target_rules.get("forgefather_weapon_keywords", []) or []) == {"MELTA", "TORRENT"}

    torrent_profile = _profile("Pyreblaster", "Torrent")
    melta_profile = _profile("Melta Rifle", "Melta 2")
    bolt_profile = _profile("Bolt Rifle", "Assault")

    torrent_mods = adeptus_astartes.get_unit_wound_reroll_modifiers(
        "ranged",
        target=target,
        attacker_model=adeptus_astartes.models[0],
        weapon_profile=torrent_profile,
    )
    melta_mods = adeptus_astartes.get_unit_wound_reroll_modifiers(
        "ranged",
        target=target,
        attacker_model=adeptus_astartes.models[0],
        weapon_profile=melta_profile,
    )
    bolt_mods = adeptus_astartes.get_unit_wound_reroll_modifiers(
        "ranged",
        target=target,
        attacker_model=adeptus_astartes.models[0],
        weapon_profile=bolt_profile,
    )
    non_astartes_mods = non_astartes.get_unit_wound_reroll_modifiers(
        "ranged",
        target=target,
        attacker_model=non_astartes.models[0],
        weapon_profile=torrent_profile,
    )
    other_target_mods = adeptus_astartes.get_unit_wound_reroll_modifiers(
        "ranged",
        target=other_target,
        attacker_model=adeptus_astartes.models[0],
        weapon_profile=torrent_profile,
    )

    assert bool(torrent_mods.get("reroll_wound_full", False)) is True
    assert any("Forgefather" in str(reason or "") for reason in list(torrent_mods.get("reroll_wound_full_reasons", ()) or ()))
    assert bool(melta_mods.get("reroll_wound_full", False)) is True
    assert bool(bolt_mods.get("reroll_wound_full", False)) is False
    assert bool(non_astartes_mods.get("reroll_wound_full", False)) is False
    assert bool(other_target_mods.get("reroll_wound_full", False)) is False

    game.phase = BattleRoundPhases.FIGHT_PHASE
    off_phase_mods = adeptus_astartes.get_unit_wound_reroll_modifiers(
        "ranged",
        target=target,
        attacker_model=adeptus_astartes.models[0],
        weapon_profile=torrent_profile,
    )
    assert bool(off_phase_mods.get("reroll_wound_full", False)) is False


def test_vulkan_hestan_seeker_of_lost_relics_selects_objective_and_applies_conditional_buffs() -> None:
    game, sm_army, _enemy_army, sm_player, _enemy_player = _build_game()

    vulkan = _actual_unit("Vulkan He'stan", datasheet_id="000002726")
    sm_army.add_unit(vulkan)
    _deploy(vulkan, 0.0, 0.0)

    objective_alpha = SimpleNamespace(
        id="obj-alpha",
        name="Alpha Objective",
        location=SimpleNamespace(id="obj-alpha-loc", x=0.0, y=0.0, z=0.0, control_radius=3.0, removed=False),
    )
    objective_beta = SimpleNamespace(
        id="obj-beta",
        name="Beta Objective",
        location=SimpleNamespace(id="obj-beta-loc", x=18.0, y=0.0, z=0.0, control_radius=3.0, removed=False),
    )
    game.objectives = [objective_alpha, objective_beta]
    game.map.objectives = [objective_alpha, objective_beta]
    game.map.units = [vulkan]
    game.rebuild_entity_registry()

    vulkan_model = vulkan.models[0]
    baseline_oc = vulkan.get_effective_model_characteristic(vulkan_model, "objective_control", game_map=game.map)
    baseline_ld = vulkan.get_effective_model_characteristic(vulkan_model, "leadership", game_map=game.map)
    baseline_fnp = list(vulkan.has_feel_no_pain(target_model=vulkan_model) or [])

    game._on_unit_set_up_seeker_of_lost_relics(unit=vulkan)
    request = _find_request(game, "seeker_of_lost_relics")
    assert request is not None

    option_id = _find_option_for_objective(request, "obj-alpha")
    assert option_id is not None
    result = resolve_decision_command(game, request, option_id, player_id=sm_player.id)
    assert bool(getattr(result, "ok", False)) is True

    special_rules = dict(getattr(vulkan, "special_rules", {}) or {})
    assert str(special_rules.get("seeker_of_lost_relics_objective_id", "") or "") == "obj-alpha"
    assert str(special_rules.get("seeker_of_lost_relics_source", "") or "") == "Seeker of the Unfound"
    assert str(special_rules.get("seeker_of_lost_relics_source_model_id", "") or "") == str(get_entity_id(vulkan_model) or "")

    assert vulkan.get_effective_model_characteristic(vulkan_model, "objective_control", game_map=game.map) == 10
    assert vulkan.get_effective_model_characteristic(vulkan_model, "leadership", game_map=game.map) == 5
    assert (4, None) in list(vulkan.has_feel_no_pain(target_model=vulkan_model) or [])

    vulkan_model.set_location(10.0, 0.0, 0.0, 0.0)
    assert vulkan.get_effective_model_characteristic(vulkan_model, "objective_control", game_map=game.map) == baseline_oc
    assert vulkan.get_effective_model_characteristic(vulkan_model, "leadership", game_map=game.map) == baseline_ld
    assert (4, None) not in list(vulkan.has_feel_no_pain(target_model=vulkan_model) or [])
    assert list(vulkan.has_feel_no_pain(target_model=vulkan_model) or []) == baseline_fnp

    game._on_unit_set_up_seeker_of_lost_relics(unit=vulkan)
    assert _find_request(game, "seeker_of_lost_relics") is None
