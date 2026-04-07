from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


ACCELERATOR_MANDIBLE_TEXT = (
    "At the start of the Fight phase, select one friendly Canoptek unit within 3\" of the bearer's unit. "
    "Until the end of the phase, improve the Weapon Skill characteristic of weapons equipped by models in that unit by 1."
)

HARASSMENT_SWARM_AURA_TEXT = (
    "While an enemy unit (excluding MONSTERS and VEHICLES) is within 3\" of this unit, each time a model in that unit "
    "makes an attack, subtract 1 from the Hit roll."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "3",
                "W": "4",
                "Ld": "7",
                "OC": "1",
                "base_size": "40mm",
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


def _make_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    necron_army = Army.with_detachment("Necrons", detachment_type="Other")
    necron_army.faction_id = "NEC"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    p1 = Player("P1", PlayerControl.REMOTE, army=necron_army)
    p2 = Player("P2", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(p1)
    game.add_player(p2)
    return game, necron_army, enemy_army, p1, p2


def _make_accelerator_mandible_ability():
    return {
        "name": "Accelerator Mandible",
        "description": ACCELERATOR_MANDIBLE_TEXT,
        "type": "Datasheet",
        "parameter": "",
    }


def _find_accelerator_mandible_request(game: Game):
    return next(
        req
        for req in list(game.decision_queue.list() or [])
        if str((getattr(req, "context", {}) or {}).get("ability", "")) == "accelerator_mandible"
    )


def test_accelerator_mandible_spec_parsing():
    source = _make_unit(
        "Canoptek Macrocytes",
        abilities=[_make_accelerator_mandible_ability()],
        keywords=["CANOPTEK", "BEASTS"],
        faction_keywords=["NECRONS"],
    )
    specs = source.model_start_fight_phase_friendly_melee_ws_bonus_specs(source.models[0])
    assert len(specs) == 1
    spec = specs[0]
    assert int(spec.get("range", 0) or 0) == 3
    assert str(spec.get("keyword", "") or "").lower() == "canoptek"
    assert int(spec.get("ws_bonus", 0) or 0) == 1


def test_accelerator_mandible_queues_and_applies_ws_bonus():
    source = _make_unit(
        "Canoptek Macrocytes",
        abilities=[_make_accelerator_mandible_ability()],
        keywords=["CANOPTEK", "BEASTS"],
        faction_keywords=["NECRONS"],
    )
    friendly_canoptek = _make_unit(
        "Canoptek Wraiths",
        keywords=["CANOPTEK", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy_unit = _make_unit("Enemy Infantry", keywords=["INFANTRY"])

    game, necron_army, enemy_army, p1, _p2 = _build_game()
    necron_army.add_unit(source)
    necron_army.add_unit(friendly_canoptek)
    enemy_army.add_unit(enemy_unit)
    game.map.units = [source, friendly_canoptek, enemy_unit]
    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    friendly_canoptek.models[0].set_location(2.0, 0.0, 0.0, 0.0)
    enemy_unit.models[0].set_location(6.0, 0.0, 0.0, 0.0)

    game._on_phase_start_accelerator_mandible(player=p1, phase=game.phase)
    req = _find_accelerator_mandible_request(game)
    assert req.decision_type == DECISION_CHOOSE_QUARRY
    assert str((req.options or [])[0].label) == "None"

    target_id = str(get_entity_id(friendly_canoptek))
    option_id = None
    for opt in list(req.options or []):
        if str((opt.payload or {}).get("target_unit_id", "")) == target_id:
            option_id = opt.option_id
            break
    assert option_id is not None

    result = resolve_decision_command(game, req, option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is True

    sr = friendly_canoptek.special_rules
    assert bool(sr.get("accelerator_mandible_ws_bonus_active")) is True
    assert int(sr.get("accelerator_mandible_ws_bonus", 0) or 0) == 1
    assert str(sr.get("accelerator_mandible_ws_bonus_expires_phase", "")).upper() == "FIGHT_PHASE"

    melee_profile = WargearProfile(
        "default",
        {
            "range": "Melee",
            "A": "1",
            "BS_WS": "4+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name="Wraithclaws", is_ranged=lambda: False, is_melee=lambda: True),
    )
    hit_result = melee_profile._hit_target_with_tracking(
        enemy_unit,
        friendly_canoptek.models[0],
        {"target_model": enemy_unit.models[0]},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(hit_result.get("base_skill", 0) or 0) == 3
    assert bool(hit_result.get("hit")) is True
    assert any("Accelerator Mandible" in str(effect) for effect in list(hit_result.get("special_effects", []) or []))

    game._on_phase_end_cleanup(player=p1, phase=game.phase)
    assert "accelerator_mandible_ws_bonus_active" not in friendly_canoptek.special_rules


def test_accelerator_mandible_invalid_non_canoptek_choice_is_rejected():
    source = _make_unit(
        "Canoptek Macrocytes",
        abilities=[_make_accelerator_mandible_ability()],
        keywords=["CANOPTEK", "BEASTS"],
        faction_keywords=["NECRONS"],
    )
    friendly_canoptek = _make_unit("Canoptek Wraiths", keywords=["CANOPTEK", "INFANTRY"], faction_keywords=["NECRONS"])
    friendly_non_canoptek = _make_unit("Necron Warriors", keywords=["INFANTRY"], faction_keywords=["NECRONS"])

    game, necron_army, _enemy_army, p1, _p2 = _build_game()
    necron_army.add_unit(source)
    necron_army.add_unit(friendly_canoptek)
    necron_army.add_unit(friendly_non_canoptek)
    game.map.units = [source, friendly_canoptek, friendly_non_canoptek]
    game.turn = 2
    game.phase = BattleRoundPhases.FIGHT_PHASE
    game.current_player_index = 0
    game.rebuild_entity_registry()

    source.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    friendly_canoptek.models[0].set_location(2.0, 0.0, 0.0, 0.0)
    friendly_non_canoptek.models[0].set_location(2.0, 1.0, 0.0, 0.0)

    game._on_phase_start_accelerator_mandible(player=p1, phase=game.phase)
    req = _find_accelerator_mandible_request(game)
    canoptek_option = next(
        opt
        for opt in list(req.options or [])
        if str((opt.payload or {}).get("target_unit_id", "")) == str(get_entity_id(friendly_canoptek))
    )
    canoptek_option.payload["target_unit_id"] = str(get_entity_id(friendly_non_canoptek))

    result = resolve_decision_command(game, req, canoptek_option.option_id, player_id=p1.id)
    assert bool(getattr(result, "ok", False)) is False


def _make_profile(*, melee: bool):
    data = {
        "range": "Melee" if melee else "24",
        "A": "1",
        "BS_WS": "4",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    parent = Wargear({"name": "Test Weapon", "type": "Melee" if melee else "Ranged", **data})
    return parent.profiles["default"]


class _AuraUnit:
    def __init__(self, *, abilities=None, keywords=None):
        self.possible_abilities = list(abilities or [])
        self._keywords = {str(k or "").strip().upper() for k in list(keywords or []) if str(k or "").strip()}
        self.round_state = SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False)
        self._army = None

    def get_parent_army(self):
        return self._army

    def has_keyword(self, kw: str) -> bool:
        return str(kw or "").strip().upper() in self._keywords

    def has_any_keyword(self, kw: str) -> bool:
        parts = [p for p in str(kw or "").strip().upper().split() if p]
        if not parts:
            return False
        return all(part in self._keywords for part in parts)


class _AuraMap:
    def __init__(self, units):
        self.units = list(units)

    def get_friendly_units(self, unit):
        army = getattr(unit, "_army", None)
        return [u for u in list(self.units or []) if getattr(u, "_army", None) is army]

    def get_enemy_units(self, unit):
        army = getattr(unit, "_army", None)
        return [u for u in list(self.units or []) if getattr(u, "_army", None) is not army]


def _make_harassment_swarm_aura():
    return Ability(
        name="Harassment Swarm (Aura)",
        faction_id="NEC",
        description=HARASSMENT_SWARM_AURA_TEXT,
        type="Datasheet",
        parameter="",
        legend=None,
    )


def _make_simple_target():
    return SimpleNamespace(
        toughness=4,
        models=[SimpleNamespace(is_alive=True)],
        has_keyword=lambda _k: False,
        has_stealth=lambda: False,
    )


def test_harassment_swarm_aura_applies_minus_one_to_hit():
    profile = _make_profile(melee=False)
    attacker_unit = _AuraUnit(keywords=["INFANTRY"])
    aura_source = _AuraUnit(abilities=[_make_harassment_swarm_aura()], keywords=["CANOPTEK"])
    target = _make_simple_target()

    game_map = _AuraMap([attacker_unit, aura_source])
    game = SimpleNamespace(map=game_map, event_system=SimpleNamespace(publish=lambda *_a, **_k: None), turn=1)
    attacker_army = SimpleNamespace(player=SimpleNamespace(game=game, id="A"))
    enemy_army = SimpleNamespace(player=SimpleNamespace(game=game, id="B"))
    attacker_unit._army = attacker_army
    aura_source._army = enemy_army
    attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)

    import warhammer40k_ai.utility.aura_effects as aura_mod
    from unittest.mock import patch

    with patch.object(aura_mod, "unit_within_range_of_unit", return_value=True):
        res = profile._hit_target_with_tracking(
            target,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )

    assert bool(res.get("hit")) is False
    assert any("Harassment Swarm (Aura)" in str(effect) for effect in list(res.get("modifiers", []) or []))


def test_harassment_swarm_aura_excludes_vehicle_attackers():
    profile = _make_profile(melee=False)
    attacker_unit = _AuraUnit(keywords=["INFANTRY", "VEHICLE"])
    aura_source = _AuraUnit(abilities=[_make_harassment_swarm_aura()], keywords=["CANOPTEK"])
    target = _make_simple_target()

    game_map = _AuraMap([attacker_unit, aura_source])
    game = SimpleNamespace(map=game_map, event_system=SimpleNamespace(publish=lambda *_a, **_k: None), turn=1)
    attacker_army = SimpleNamespace(player=SimpleNamespace(game=game, id="A"))
    enemy_army = SimpleNamespace(player=SimpleNamespace(game=game, id="B"))
    attacker_unit._army = attacker_army
    aura_source._army = enemy_army
    attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)

    import warhammer40k_ai.utility.aura_effects as aura_mod
    from unittest.mock import patch

    with patch.object(aura_mod, "unit_within_range_of_unit", return_value=True):
        res = profile._hit_target_with_tracking(
            target,
            attacker_model,
            {},
            roll_value=4,
            allow_rerolls=False,
            log_roll=False,
        )

    assert bool(res.get("hit")) is True
    assert not any("Harassment Swarm (Aura)" in str(effect) for effect in list(res.get("modifiers", []) or []))
