from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


TANITH_CAMO_CLOAKS_TEXT = "Models in this unit have the Benefit of Cover."
FLUSH_THEM_OUT_TEXT = (
    "In your Shooting phase, after this model has shot, select one enemy unit that was hit by one or more of those "
    "attacks. Until the start of your next Shooting phase, that unit is scattered. While a unit is scattered, it "
    "cannot have the Benefit of Cover."
)
CLOSE_QUARTERS_WARFARE_TEXT = (
    "This model does not suffer the penalty to its Hit rolls for making ranged attacks while enemy units are within "
    "Engagement Range of it."
)
MELTA_MINE_TEXT = (
    "Once per battle, at the start of any phase, you can select one enemy unit within 3\" of the bearer and roll one "
    "D6: on a 2+, that enemy unit suffers D3 mortal wounds, or 2D3 mortal wounds instead if it is a VEHICLE unit."
)
WARRIOR_ELITE_TEXT = (
    "Once per battle round, at the start of any phase, you can select one Order to affect this unit until the start "
    "of your next Command phase, in addition to any other Orders issued to this unit by an Officer model this battle round."
)


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
        wounds: int = 2,
        save: int = 4,
    ):
        self.id = datasheet_id or name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": str(int(save)),
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "25mm",
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


class _DummyMap:
    def __init__(self, units, engaged_pairs):
        self.units = list(units)
        self._engaged = set(frozenset({id(a), id(b)}) for (a, b) in engaged_pairs)

    def get_enemy_units(self, unit):
        return [u for u in self.units if u.get_parent_army() != unit.get_parent_army()]

    def get_friendly_units(self, unit):
        return [u for u in self.units if u.get_parent_army() == unit.get_parent_army()]

    def is_within_engagement_range(self, a, b) -> bool:
        return frozenset({id(a), id(b)}) in self._engaged


def _make_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    datasheet_id: str | None = None,
    model_count: int = 1,
    wounds: int = 2,
    save: int = 4,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            datasheet_id=datasheet_id,
            model_count=model_count,
            wounds=wounds,
            save=save,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game() -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    am_army = Army.with_detachment("Astra Militarum", detachment_type="Combined Regiment")
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    am_player = Player("AM", PlayerControl.REMOTE, army=am_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 2
    return game, am_army, enemy_army, am_player, enemy_player


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _find_quarry_request(game: Game, ability: str):
    return next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == ability
        ),
        None,
    )


def _option_for_target(request, target: Unit):
    target_id = str(get_entity_id(target) or "")
    return next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("target_unit_id", "") or "") == target_id
    )


def _option_for_order(request, order_key: str):
    expected = str(order_key or "").strip().upper()
    return next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("order_key", "") or "").strip().upper() == expected
    )


def _make_profile(name: str = "Test Rifle") -> WargearProfile:
    return WargearProfile(
        profile_name=name,
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name=name, is_ranged=lambda: True, is_melee=lambda: False),
    )


def _make_model(name: str, unit: Unit, *, wounds: int = 2) -> Model:
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=4,
        wounds=int(wounds),
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    model.set_location(0.0, 0.0, 0.0, 0.0)
    return model


def test_tanith_camo_cloaks_grants_cover_on_ranged_attacks():
    ghosts = _make_unit(
        "Gaunt's Ghosts",
        datasheet_id="gaunts-ghosts",
        abilities=[{"name": "Tanith Camo-cloaks", "description": TANITH_CAMO_CLOAKS_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        model_count=1,
    )
    enemy = _make_unit(
        "Enemy Shooters",
        datasheet_id="enemy-shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=1,
    )
    enemy_model = enemy.models[0]
    enemy_model.parent_unit = enemy

    cover_entries = list((ghosts.special_rules or {}).get("bearer_unit_benefit_of_cover", []) or [])
    assert len(cover_entries) == 1
    assert str(cover_entries[0].get("source", "") or "") == "Tanith Camo-cloaks"

    attack_instance = {
        "attacker_model": enemy_model,
        "attacker_unit": enemy,
        "target_unit": ghosts,
    }
    target_model = ghosts.models[0]
    result = _make_profile()._save_with_tracking(target_model, attack_instance, ap=0, roll_value=4, allow_rerolls=False)

    assert result is not None
    assert bool(attack_instance.get("benefit_of_cover")) is True
    assert "Tanith Camo-cloaks" in str(attack_instance.get("benefit_of_cover_source", "") or "")


def test_flush_them_out_parses_and_applies_no_cover_until_next_shooting_phase():
    game, am_army, enemy_army, am_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    hellhound = _make_unit(
        "Hellhound",
        datasheet_id="hellhound",
        abilities=[{"name": "Flush Them Out", "description": FLUSH_THEM_OUT_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["VEHICLE", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds=11,
    )
    target = _make_unit(
        "Enemy Infantry",
        datasheet_id="enemy-infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    am_army.add_unit(hellhound)
    enemy_army.add_unit(target)
    _deploy(hellhound, 0.0, 0.0)
    _deploy(target, 8.0, 0.0)
    _register_units(game, hellhound, target)

    specs = hellhound.unit_post_shoot_no_cover_specs()
    assert len(specs) == 1
    assert bool(specs[0].get("any_weapon")) is True
    assert str(specs[0].get("duration", "") or "") == "owner_next_shooting_start"

    game._on_unit_shooting_resolved_post_shoot_no_cover(
        attacker_unit=hellhound,
        hits_by_target={target: 1},
        hit_models_by_target_weapon={},
    )
    request = _find_quarry_request(game, "post_shoot_no_cover")
    assert request is not None
    assert str((request.context or {}).get("expires_timing", "") or "") == "OWNER_NEXT_SHOOTING_START"

    option = _option_for_target(request, target)
    result = resolve_decision_command(game, request, option.option_id, player_id=am_player.id)
    assert bool(getattr(result, "ok", False)) is True

    sr = dict(getattr(target, "special_rules", {}) or {})
    assert bool(sr.get("post_shoot_no_cover_active")) is True
    assert str(sr.get("post_shoot_no_cover_expires_timing", "") or "") == "OWNER_NEXT_SHOOTING_START"
    assert str(sr.get("post_shoot_no_cover_source", "") or "") == "Flush Them Out"


def test_close_quarters_warfare_skips_bgnt_hit_penalties():
    game, am_army, enemy_army, am_player, enemy_player = _build_game()

    hellhammer = _make_unit(
        "Hellhammer",
        datasheet_id="hellhammer",
        abilities=[{"name": "Close-quarters Warfare", "description": CLOSE_QUARTERS_WARFARE_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["VEHICLE", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds=24,
    )
    enemy_vehicle = _make_unit(
        "Enemy Tank",
        datasheet_id="enemy-tank",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
        wounds=12,
    )
    friendly_support = _make_unit(
        "Friendly Support",
        datasheet_id="friendly-support",
        keywords=["VEHICLE", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        wounds=10,
    )
    am_army.add_unit(hellhammer)
    am_army.add_unit(friendly_support)
    enemy_army.add_unit(enemy_vehicle)
    _register_units(game, hellhammer, friendly_support, enemy_vehicle)
    game.map = _DummyMap([hellhammer, friendly_support, enemy_vehicle], engaged_pairs=[(hellhammer, enemy_vehicle)])
    am_player.game = game
    enemy_player.game = game

    profile = _make_profile("Battle Cannon")

    hellhammer._bgnt_locked_at_target_selection = True
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        locked_hit = profile._hit_target_with_tracking(enemy_vehicle, hellhammer.models[0], {}, roll_value=4, allow_rerolls=False)
    assert int(locked_hit["final_needed"] or 0) == 3
    assert not any("Big Guns Never Tire" in str(mod or "") for mod in list(locked_hit.get("modifiers", []) or []))

    hellhammer._bgnt_locked_at_target_selection = False
    game.map = _DummyMap([hellhammer, friendly_support, enemy_vehicle], engaged_pairs=[(friendly_support, enemy_vehicle)])
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
        target_hit = profile._hit_target_with_tracking(enemy_vehicle, hellhammer.models[0], {}, roll_value=4, allow_rerolls=False)
    assert int(target_hit["final_needed"] or 0) == 3
    assert not any("Big Guns Never Tire" in str(mod or "") for mod in list(target_hit.get("modifiers", []) or []))


def test_melta_mine_uses_vehicle_alternate_mortal_wounds_roll():
    game, am_army, enemy_army, am_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    kasrkin = _make_unit(
        "Kasrkin",
        datasheet_id="kasrkin",
        abilities=[{"name": "Melta Mine", "description": MELTA_MINE_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        model_count=1,
    )
    target = _make_unit(
        "Enemy Tank",
        datasheet_id="enemy-tank",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
        model_count=1,
        wounds=12,
    )
    am_army.add_unit(kasrkin)
    enemy_army.add_unit(target)
    _deploy(kasrkin, 0.0, 0.0)
    _deploy(target, 2.0, 0.0)
    _register_units(game, kasrkin, target)

    game._on_phase_start_orks_squig_mine(player=am_player, phase=game.phase)
    request = _find_quarry_request(game, "squig_mine")
    assert request is not None
    assert str((request.context or {}).get("alternate_mortal_wounds_roll", "") or "") == "2D3"
    assert list((request.context or {}).get("alternate_target_keywords_any", []) or []) == ["VEHICLE"]

    option = _option_for_target(request, target)
    def _roll(expr: str):
        expr_key = str(expr or "").strip().upper()
        if expr_key == "D6":
            return 2
        if expr_key == "2D3":
            return 5
        raise AssertionError(f"Unexpected roll expression: {expr_key}")

    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=_roll):
        result = resolve_decision_command(game, request, option.option_id, player_id=am_player.id)

    assert bool(getattr(result, "ok", False)) is True
    assert int(getattr(target.models[0], "wounds", 0) or 0) == 7


def test_warrior_elite_applies_additional_order_without_replacing_existing_order():
    game, am_army, enemy_army, am_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    kasrkin = _make_unit(
        "Kasrkin",
        datasheet_id="kasrkin",
        abilities=[{"name": "Warrior Elite", "description": WARRIOR_ELITE_TEXT, "type": "Datasheet", "parameter": ""}],
        keywords=["INFANTRY", "ASTRA MILITARUM"],
        faction_keywords=["ASTRA MILITARUM"],
        model_count=1,
    )
    am_army.add_unit(kasrkin)
    _deploy(kasrkin, 0.0, 0.0)
    _register_units(game, kasrkin)

    mgr = am_army.voice_of_command
    mgr._apply_order_to_unit_and_attached(kasrkin, "TAKE_AIM", owner_id=am_player.id, source_id="officer-1")

    game._on_phase_start_astra_militarum_warrior_elite(player=am_player, phase=game.phase)
    request = _find_quarry_request(game, "warrior_elite_order")
    assert request is not None
    option_order_keys = {
        str((option.payload or {}).get("order_key", "") or "").strip().upper()
        for option in list(request.options or [])
    }
    assert "TAKE_AIM" not in option_order_keys
    assert "TAKE_COVER" in option_order_keys

    option = _option_for_order(request, "TAKE_COVER")
    result = resolve_decision_command(game, request, option.option_id, player_id=am_player.id)
    assert bool(getattr(result, "ok", False)) is True

    sr = dict(getattr(kasrkin, "special_rules", {}) or {})
    assert str(sr.get("voice_of_command_order_key", "") or "") == "TAKE_AIM"
    assert "TAKE_COVER" in list(sr.get("voice_of_command_additional_order_keys", []) or [])
    assert bool(sr.get("voice_of_command_take_cover_cap")) is True
    assert int(sr.get("warrior_elite_used_round", 0) or 0) == int(game.turn)

    game._on_phase_start_astra_militarum_warrior_elite(player=am_player, phase=game.phase)
    assert _find_quarry_request(game, "warrior_elite_order") is None
