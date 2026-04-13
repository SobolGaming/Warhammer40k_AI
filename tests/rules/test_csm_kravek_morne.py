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


ARCHITECT_OF_RUIN_TEXT = (
    "At the start of the battle, select one unit in your opponent's army to be this model's hated foe. "
    "Each time this model makes an attack that targets its hated foe, you can re-roll the Wound roll. "
    "Each time this model's hated foe is destroyed, you can select a new unit from your opponent's army to be its hated foe."
)

HEADLONG_DESTRUCTION_TEXT = (
    "Each time a model in this unit makes an attack that targets the closest eligible enemy unit, improve the Armour "
    "Penetration characteristic of that attack by 1."
)


class _DummyWargear:
    def __init__(self, name: str, *, ranged: bool) -> None:
        self.name = name
        self._ranged = bool(ranged)

    def is_ranged(self) -> bool:
        return bool(self._ranged)

    def is_melee(self) -> bool:
        return not bool(self._ranged)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        datasheet_id: str | None = None,
        model_count: int = 1,
        move: int = 6,
        toughness: int = 4,
        save: int = 3,
        wounds: int = 2,
        leadership: int = 7,
        objective_control: int = 1,
        faction_name: str = "Chaos Space Marines",
    ) -> None:
        self.id = datasheet_id or name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(move)),
                "T": str(int(toughness)),
                "Sv": str(int(save)),
                "W": str(int(wounds)),
                "Ld": str(int(leadership)),
                "OC": str(int(objective_control)),
                "base_size": "40mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.attached_to = []
        self.attached_to_names = []
        self.loadout = "This model is equipped with: nothing."
        self.transport = ""


def _make_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    datasheet_id: str | None = None,
    model_count: int = 1,
    move: int = 6,
    toughness: int = 4,
    save: int = 3,
    wounds: int = 2,
    leadership: int = 7,
    objective_control: int = 1,
    faction_name: str = "Chaos Space Marines",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            datasheet_id=datasheet_id,
            model_count=model_count,
            move=move,
            toughness=toughness,
            save=save,
            wounds=wounds,
            leadership=leadership,
            objective_control=objective_control,
            faction_name=faction_name,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game() -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    csm_army = Army.with_detachment("Chaos Space Marines", detachment_type="Other")
    csm_army.faction_id = "CSM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    csm_player = Player("CSM", PlayerControl.REMOTE, army=csm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(csm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    return game, csm_army, enemy_army, csm_player, enemy_player


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _find_prey_request(game: Game):
    return next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "prey_selection"
        ),
        None,
    )


def _select_target_option(request, target_unit: Unit):
    target_id = str(get_entity_id(target_unit) or "")
    return next(
        (
            option
            for option in list(getattr(request, "options", []) or [])
            if str((getattr(option, "payload", {}) or {}).get("target_unit_id", "") or "") == target_id
        ),
        None,
    )


def _aura_stub() -> SimpleNamespace:
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


def _make_profile(*, ranged: bool) -> WargearProfile:
    return WargearProfile(
        profile_name="Test",
        wargear_data={
            "range": "24" if ranged else "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=_DummyWargear("Test Weapon", ranged=ranged),
    )


def test_architect_of_ruin_queues_hated_foe_selection_and_applies_wound_reroll(monkeypatch):
    game, csm_army, enemy_army, csm_player, _enemy_player = _build_game()
    kravek = _make_unit(
        "Kravek Morne",
        abilities=[{"name": "Architect of Ruin", "description": ARCHITECT_OF_RUIN_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["CHAOS", "CHARACTER", "INFANTRY", "LEADER"],
        faction_keywords=["HERETIC ASTARTES"],
        datasheet_id="000004205",
        wounds=8,
        objective_control=3,
    )
    hated_foe = _make_unit("Hated Foe", keywords=["INFANTRY"], faction_keywords=["ENEMY"], faction_name="Enemy", wounds=5)
    other_enemy = _make_unit("Other Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], faction_name="Enemy", wounds=5)

    csm_army.add_unit(kravek)
    enemy_army.add_unit(hated_foe)
    enemy_army.add_unit(other_enemy)
    _deploy(kravek, 0.0, 0.0)
    _deploy(hated_foe, 12.0, 0.0)
    _deploy(other_enemy, 18.0, 0.0)
    _register_units(game, kravek, hated_foe, other_enemy)

    csm_army.on_battle_round_start(1)
    request = _find_prey_request(game)
    assert request is not None
    assert str((request.context or {}).get("ability_name", "") or "") == "Architect of Ruin"
    assert bool((request.context or {}).get("prey_reroll_wound", False)) is True
    assert bool((request.context or {}).get("prey_repick_on_destroyed", False)) is True
    prey_source_model_id = str((request.context or {}).get("prey_source_model_id", "") or "")
    assert prey_source_model_id == str(get_entity_id(kravek.models[0]) or "")

    option = _select_target_option(request, hated_foe)
    assert option is not None
    resolved = resolve_decision_command(game, request, option.option_id, player_id=csm_player.id)
    assert bool(getattr(resolved, "ok", False)) is True
    assert getattr(kravek, "_prey_selection_prey_ids", set()) == {str(get_entity_id(hated_foe) or "")}
    assert str(getattr(kravek, "_prey_selection_source_model_id", "") or "") == prey_source_model_id

    seq = iter([2, 6])
    monkeypatch.setattr("warhammer40k_ai.units.wargear.get_roll", lambda _spec: next(seq))
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    wound_result = _make_profile(ranged=True)._wound_target_with_tracking(hated_foe, kravek.models[0], attack_instance)
    assert int(wound_result.get("roll", 0) or 0) == 6
    assert any("Architect of Ruin" in effect for effect in list(wound_result.get("special_effects", []) or []))


def test_architect_of_ruin_repicks_when_hated_foe_is_destroyed():
    game, csm_army, enemy_army, csm_player, _enemy_player = _build_game()
    kravek = _make_unit(
        "Kravek Morne",
        abilities=[{"name": "Architect of Ruin", "description": ARCHITECT_OF_RUIN_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["CHAOS", "CHARACTER", "INFANTRY", "LEADER"],
        faction_keywords=["HERETIC ASTARTES"],
        datasheet_id="000004205",
        wounds=8,
        objective_control=3,
    )
    hated_foe = _make_unit("Hated Foe", keywords=["INFANTRY"], faction_keywords=["ENEMY"], faction_name="Enemy")
    replacement = _make_unit("Replacement", keywords=["INFANTRY"], faction_keywords=["ENEMY"], faction_name="Enemy")

    csm_army.add_unit(kravek)
    enemy_army.add_unit(hated_foe)
    enemy_army.add_unit(replacement)
    _register_units(game, kravek, hated_foe, replacement)

    csm_army.on_battle_round_start(1)
    initial_request = _find_prey_request(game)
    assert initial_request is not None
    initial_option = _select_target_option(initial_request, hated_foe)
    assert initial_option is not None
    initial_result = resolve_decision_command(game, initial_request, initial_option.option_id, player_id=csm_player.id)
    assert bool(getattr(initial_result, "ok", False)) is True

    hated_foe.is_alive = lambda: False
    game._on_unit_destroyed_monarch_of_the_hunt(unit=hated_foe)

    repick_request = _find_prey_request(game)
    assert repick_request is not None
    repick_option = _select_target_option(repick_request, replacement)
    assert repick_option is not None
    repick_result = resolve_decision_command(game, repick_request, repick_option.option_id, player_id=csm_player.id)
    assert bool(getattr(repick_result, "ok", False)) is True
    assert getattr(kravek, "_prey_selection_prey_ids", set()) == {str(get_entity_id(replacement) or "")}


def test_headlong_destruction_applies_ap_bonus_to_melee_and_ranged_closest_targets():
    game, csm_army, enemy_army, _csm_player, _enemy_player = _build_game()
    kravek = _make_unit(
        "Kravek Morne",
        abilities=[{"name": "Headlong Destruction", "description": HEADLONG_DESTRUCTION_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["CHAOS", "CHARACTER", "INFANTRY", "LEADER"],
        faction_keywords=["HERETIC ASTARTES"],
        datasheet_id="000004205",
        wounds=8,
        objective_control=3,
    )
    close_target = _make_unit("Close Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"], faction_name="Enemy")
    far_target = _make_unit("Far Target", keywords=["INFANTRY"], faction_keywords=["ENEMY"], faction_name="Enemy")

    csm_army.add_unit(kravek)
    enemy_army.add_unit(close_target)
    enemy_army.add_unit(far_target)
    _deploy(kravek, 0.0, 0.0)
    _deploy(close_target, 8.0, 0.0)
    _deploy(far_target, 14.0, 0.0)
    _register_units(game, kravek, close_target, far_target)

    rule = kravek.get_closest_eligible_ap_bonus_rule(kravek.models[0])
    assert rule is not None
    assert str(rule.get("attack_type", "") or "") == "any"
    assert int(rule.get("ap_bonus", 0) or 0) == 1
    assert str(rule.get("source", "") or "") == "Headlong Destruction"

    kravek.is_target_closest_eligible = (
        lambda attacker_model, weapon_profile, target, game_map, **_kwargs: target is close_target
    )

    ranged_profile = _make_profile(ranged=True)
    melee_profile = _make_profile(ranged=False)
    assert ranged_profile.get_effective_ap(kravek.models[0], close_target) == -1
    assert ranged_profile.get_effective_ap(kravek.models[0], far_target) == 0
    assert melee_profile.get_effective_ap(kravek.models[0], close_target) == -1
    assert melee_profile.get_effective_ap(kravek.models[0], far_target) == 0
