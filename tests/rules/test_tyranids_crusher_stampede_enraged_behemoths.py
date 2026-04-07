import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile

from tests.rules.detachment_stub_helpers import attach_detachment_helpers


class _DummyPlayer:
    def __init__(self, name: str = "Player"):
        self.name = name
        self.control = SimpleNamespace(name="LOCAL")
        self.has_control = lambda: True
        self.game = None


class _DummyArmy:
    def __init__(self, *, faction_id: str = "TYR", detachment_type: str = "Crusher Stampede"):
        self.faction_id = faction_id
        self.detachment_type = detachment_type
        self.units = []
        self.player = _DummyPlayer()
        self.tyranids_detachments = None
        attach_detachment_helpers(self)


class _DummyModel:
    def __init__(self, unit, *, keywords=None, faction_keywords=None, name: str = "Model"):
        self.name = name
        self.parent_unit = unit
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.wounds = 1
        self.is_alive = True

    def has_any_keyword(self, keyword: str) -> bool:
        kw = str(keyword or "").strip().lower()
        if not kw:
            return False
        pool = [str(k or "").strip().lower() for k in (self.keywords or []) + (self.faction_keywords or [])]
        return kw in pool


class _DummyUnit:
    def __init__(
        self,
        name: str,
        army: _DummyArmy,
        *,
        keywords=None,
        faction_keywords=None,
        toughness: int = 4,
        starting_model_count: int = 1,
        current_model_count: int | None = None,
    ):
        self.name = name
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.possible_abilities = []
        self.abilities = []
        self.models = []
        self.special_rules = {}
        self.round_state = SimpleNamespace(remained_stationary_this_round=False)
        self._army = army
        self.parent_army = army
        self.toughness = int(toughness)
        self.starting_model_count = int(starting_model_count)
        self.starting_total_wounds = int(starting_model_count)

        current = int(current_model_count if current_model_count is not None else starting_model_count)
        for i in range(max(current, 0)):
            model = _DummyModel(
                self,
                name=f"{name} #{i + 1}",
                keywords=self.keywords,
                faction_keywords=self.faction_keywords,
            )
            self.models.append(model)

    def get_parent_army(self):
        return self._army

    def set_parent_army(self, army):
        self._army = army
        self.parent_army = army

    def has_any_keyword(self, keyword: str) -> bool:
        kw = str(keyword or "").strip().lower()
        if not kw:
            return False
        pool = [str(k or "").strip().lower() for k in (self.keywords or []) + (self.faction_keywords or [])]
        return kw in pool

    def has_keyword(self, keyword: str) -> bool:
        return self.has_any_keyword(keyword)

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_members(self):
        return [self]

    def get_attached_unit_models(self):
        return list(self.models)

    def get_models_for_collision(self):
        return list(self.models)

    def get_models_for_wound_allocation(self):
        return list(self.models)

    def is_battle_shocked(self):
        return False

    def is_in_reserves(self):
        return False

    def is_alive(self):
        return True

    def has_stealth(self):
        return False

    def has_first_prince_tzeentch_defense(self):
        return False

    def has_advance_and_shoot(self):
        return False

    def is_below_starting_strength(self) -> bool:
        alive = [m for m in (self.models or []) if getattr(m, "is_alive", True)]
        return len(alive) < int(self.starting_model_count)

    def is_below_half_strength(self) -> bool:
        alive = [m for m in (self.models or []) if getattr(m, "is_alive", True)]
        return len(alive) < (int(self.starting_model_count) / 2.0)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        objective_control: int = 2,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "8",
                "T": "10",
                "Sv": "3",
                "W": "12",
                "Ld": "7",
                "OC": str(int(objective_control)),
                "base_size": "100mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_real_unit(name: str, *, keywords=None, faction_keywords=None, objective_control: int = 2) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            objective_control=objective_control,
        )
    )


def _make_profile(
    *,
    is_melee: bool,
    strength: str = "4",
    skill: str = "4+",
    description: str = "",
) -> WargearProfile:
    weapon_name = "Monstrous Talons" if is_melee else "Warp Blast"
    parent = SimpleNamespace(
        name=weapon_name,
        is_melee=lambda: bool(is_melee),
        is_ranged=lambda: not bool(is_melee),
    )
    return WargearProfile(
        "Profile",
        wargear_data={
            "range": "Melee" if is_melee else "24",
            "A": "1",
            "BS_WS": skill,
            "S": strength,
            "AP": "0",
            "D": "1",
            "description": description,
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


def _apply_crusher_enhancement(unit: Unit, *, enhancement_id: str, name: str, description: str = "") -> Enhancement:
    enhancement = Enhancement(
        id=str(enhancement_id),
        name=name,
        faction_id="TYR",
        detachment="Crusher Stampede",
        points=25,
        description=description,
    )
    unit.enhancement = enhancement
    enhancement.apply_to_unit(unit)
    return enhancement


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


def _build_game(*, tyr_control=PlayerControl.REMOTE, enemy_control=PlayerControl.REMOTE):
    tyr_army = Army.with_detachment("Tyranids", "Crusher Stampede")
    tyr_army.faction_id = "TYR"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyranids", tyr_control, army=tyr_army)
    enemy_player = Player("Enemy", enemy_control, army=enemy_army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[tyr_player, enemy_player])
    game.phase = SimpleNamespace(name="SHOOTING_PHASE")
    game.current_player_index = 1
    return game, tyr_player, enemy_player


class TestCrusherStampedeEnragedBehemoths(unittest.TestCase):
    def _make_profile(self):
        from warhammer40k_ai.units.wargear import WargearProfile

        parent = SimpleNamespace(
            name="Bio-cannon",
            is_melee=lambda: False,
            is_ranged=lambda: True,
        )
        data = {
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
        return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)

    def _aura_stub(self):
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

    def test_enraged_behemoths_hit_bonus_below_starting_strength(self):
        from warhammer40k_ai.rules.tyranids_detachments import TyranidsDetachmentManager

        army = _DummyArmy(faction_id="TYR", detachment_type="Crusher Stampede")
        army.tyranids_detachments = TyranidsDetachmentManager(army)

        attacker_unit = _DummyUnit(
            "Screamer-Killer",
            army,
            keywords=["MONSTER", "TYRANIDS"],
            faction_keywords=["TYRANIDS"],
            starting_model_count=10,
            current_model_count=9,
        )
        target_army = _DummyArmy(faction_id="ENEMY", detachment_type="Other")
        target_unit = _DummyUnit("Target", target_army, toughness=4)

        attacker_model = attacker_unit.models[0]
        profile = self._make_profile()
        attack_ctx = {"_aura_attack_mods": self._aura_stub()}

        hit = profile._hit_target_with_tracking(
            target_unit,
            attacker_model,
            dict(attack_ctx),
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(hit["hit"])
        self.assertTrue(any("Enraged Behemoths" in m for m in hit.get("modifiers", [])))

        wound = profile._wound_target_with_tracking(
            target_unit,
            attacker_model,
            dict(attack_ctx),
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(wound["wound"])
        self.assertFalse(any("Enraged Behemoths" in m for m in wound.get("modifiers", [])))

    def test_enraged_behemoths_wound_bonus_below_half_strength(self):
        from warhammer40k_ai.rules.tyranids_detachments import TyranidsDetachmentManager

        army = _DummyArmy(faction_id="TYR", detachment_type="Crusher Stampede")
        army.tyranids_detachments = TyranidsDetachmentManager(army)

        attacker_unit = _DummyUnit(
            "Screamer-Killer",
            army,
            keywords=["MONSTER", "TYRANIDS"],
            faction_keywords=["TYRANIDS"],
            starting_model_count=10,
            current_model_count=4,
        )
        target_army = _DummyArmy(faction_id="ENEMY", detachment_type="Other")
        target_unit = _DummyUnit("Target", target_army, toughness=4)

        attacker_model = attacker_unit.models[0]
        profile = self._make_profile()
        attack_ctx = {"_aura_attack_mods": self._aura_stub()}

        hit = profile._hit_target_with_tracking(
            target_unit,
            attacker_model,
            dict(attack_ctx),
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(hit["hit"])
        self.assertTrue(any("Enraged Behemoths" in m for m in hit.get("modifiers", [])))

        wound = profile._wound_target_with_tracking(
            target_unit,
            attacker_model,
            dict(attack_ctx),
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertTrue(wound["wound"])
        self.assertTrue(any("Enraged Behemoths" in m for m in wound.get("modifiers", [])))

    def test_enraged_behemoths_does_not_apply_outside_crusher_stampede(self):
        from warhammer40k_ai.rules.tyranids_detachments import TyranidsDetachmentManager

        army = _DummyArmy(faction_id="TYR", detachment_type="Invasion Fleet")
        army.tyranids_detachments = TyranidsDetachmentManager(army)

        attacker_unit = _DummyUnit(
            "Screamer-Killer",
            army,
            keywords=["MONSTER", "TYRANIDS"],
            faction_keywords=["TYRANIDS"],
            starting_model_count=10,
            current_model_count=4,
        )
        target_army = _DummyArmy(faction_id="ENEMY", detachment_type="Other")
        target_unit = _DummyUnit("Target", target_army, toughness=4)

        attacker_model = attacker_unit.models[0]
        profile = self._make_profile()
        attack_ctx = {"_aura_attack_mods": self._aura_stub()}

        hit = profile._hit_target_with_tracking(
            target_unit,
            attacker_model,
            dict(attack_ctx),
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(hit["hit"])
        self.assertFalse(any("Enraged Behemoths" in m for m in hit.get("modifiers", [])))

        wound = profile._wound_target_with_tracking(
            target_unit,
            attacker_model,
            dict(attack_ctx),
            roll_value=3,
            allow_rerolls=False,
            log_roll=False,
        )
        self.assertFalse(wound["wound"])
        self.assertFalse(any("Enraged Behemoths" in m for m in wound.get("modifiers", [])))


def test_enraged_behemoths_objective_control_bonus_at_starting_strength():
    army = Army.with_detachment("Tyranids", "Crusher Stampede")
    army.faction_id = "TYR"

    monster = _make_real_unit(
        "Carnifex",
        keywords=["MONSTER"],
        faction_keywords=["TYRANIDS"],
        objective_control=2,
    )
    non_monster = _make_real_unit(
        "Termagants",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
        objective_control=2,
    )

    army.add_unit(monster)
    army.add_unit(non_monster)

    monster_model = monster.models[0]
    non_monster_model = non_monster.models[0]

    assert int(monster_model.objective_control) == 4
    assert int(non_monster_model.objective_control) == 2

    monster_model.wounds = max(1, int(monster_model._base_wounds) - 1)
    assert bool(monster.is_below_starting_strength()) is True
    assert int(monster_model.objective_control) == 2

    monster_model.wounds = int(monster_model._base_wounds)
    assert int(monster_model.objective_control) == 4

    monster.apply_status_effect(BattleShockEffect(current_turn=1))
    assert int(monster_model.objective_control) == 0


def test_crusher_stampede_enhancement_descriptors_registered():
    expected = {
        "000008404002": ("Ominous Presence", "objective_control_bonus"),
        "000008404003": ("Enraged Reserves", "melee_fight_on_death_after_attacks"),
        "000008404004": ("Null Nodules", "conditional_feel_no_pain"),
        "000008404005": ("Monstrous Nemesis", "melee_wound_bonus"),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(descriptor.name or "") == name
        assert str(descriptor.effect or "") == effect


def test_ominous_presence_adds_bearer_objective_control():
    army = Army.with_detachment("Tyranids", "Crusher Stampede")
    army.faction_id = "TYR"
    bearer_unit = _make_real_unit(
        "Hive Tyrant",
        keywords=["MONSTER", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
        objective_control=2,
    )
    army.add_unit(bearer_unit)
    _apply_crusher_enhancement(
        bearer_unit,
        enhancement_id="000008404002",
        name="Ominous Presence",
    )

    bearer = bearer_unit.models[0]
    assert int(bearer.objective_control) == 7

    bearer.wounds = max(1, int(bearer._base_wounds) - 1)
    assert bool(bearer_unit.is_below_starting_strength()) is True
    assert int(bearer.objective_control) == 5


def test_monstrous_nemesis_adds_melee_wound_bonus_only_against_monsters_and_vehicles():
    tyr_army = Army.with_detachment("Tyranids", "Crusher Stampede")
    tyr_army.faction_id = "TYR"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"

    bearer_unit = _make_real_unit(
        "Hive Tyrant",
        keywords=["MONSTER", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
    )
    vehicle_target = _make_real_unit(
        "Enemy Tank",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
    )
    infantry_target = _make_real_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tyr_army.add_unit(bearer_unit)
    enemy_army.add_unit(vehicle_target)
    enemy_army.add_unit(infantry_target)
    _apply_crusher_enhancement(
        bearer_unit,
        enhancement_id="000008404005",
        name="Monstrous Nemesis",
    )

    profile = _make_profile(is_melee=True, strength="5")
    attacker = bearer_unit.models[0]

    wound_vs_vehicle = profile._wound_target_with_tracking(
        vehicle_target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )
    wound_vs_infantry = profile._wound_target_with_tracking(
        infantry_target,
        attacker,
        {"_aura_attack_mods": _aura_stub()},
        roll_value=5,
        allow_rerolls=False,
        log_roll=False,
    )

    assert bool(wound_vs_vehicle.get("wound")) is True
    assert any("Monstrous Nemesis" in str(reason or "") for reason in list(wound_vs_vehicle.get("modifiers") or []))
    assert bool(wound_vs_infantry.get("wound")) is False
    assert not any("Monstrous Nemesis" in str(reason or "") for reason in list(wound_vs_infantry.get("modifiers") or []))


def test_enraged_reserves_grants_bearer_fight_on_death_rule():
    army = Army.with_detachment("Tyranids", "Crusher Stampede")
    army.faction_id = "TYR"
    bearer_unit = _make_real_unit(
        "Screamer-Killer",
        keywords=["MONSTER", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
    )
    army.add_unit(bearer_unit)
    _apply_crusher_enhancement(
        bearer_unit,
        enhancement_id="000008404003",
        name="Enraged Reserves",
    )

    rule = bearer_unit.get_melee_fight_on_death_after_attacks_rule(model=bearer_unit.models[0])
    assert rule is not None
    assert int(rule.get("threshold", 0) or 0) == 3
    assert str(rule.get("source", "") or "") == "Enraged Reserves"


def test_null_nodules_is_not_a_static_fnp_before_activation():
    army = Army.with_detachment("Tyranids", "Crusher Stampede")
    army.faction_id = "TYR"
    bearer_unit = _make_real_unit(
        "Neurotyrant",
        keywords=["MONSTER", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
    )
    army.add_unit(bearer_unit)
    _apply_crusher_enhancement(
        bearer_unit,
        enhancement_id="000008404004",
        name="Null Nodules",
    )

    assert list(bearer_unit.has_feel_no_pain(target_model=bearer_unit.models[0]) or []) == []


def test_null_nodules_can_be_skipped_then_used_on_later_psychic_attack():
    game, tyr_player, enemy_player = _build_game()
    target_unit = _make_real_unit(
        "Neurotyrant",
        keywords=["MONSTER", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
    )
    attacker_unit = _make_real_unit(
        "Enemy Psyker",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
    )

    tyr_player.army.add_unit(target_unit)
    enemy_player.army.add_unit(attacker_unit)
    game.map.units = [target_unit, attacker_unit]
    game.rebuild_entity_registry()

    _apply_crusher_enhancement(
        target_unit,
        enhancement_id="000008404004",
        name="Null Nodules",
    )

    profile = _make_profile(is_melee=False, description="[PSYCHIC]")
    target_model = target_unit.models[0]
    attacker_model = attacker_unit.models[0]

    tyr_player.set_next_optional_decision("NULL_NODULES", False)
    first = profile._apply_damage_with_tracking(
        target_model,
        attacker_model,
        1,
        False,
        attack_instance={},
        game_map=game.map,
    )
    assert int(first.get("damage_applied", 0) or 0) == 1
    assert int(target_model.wounds or 0) == int(target_model._base_wounds) - 1
    assert not target_model.has_used_once_per_battle("null_nodules")

    tyr_player.set_next_optional_decision("NULL_NODULES", True)
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=5):
        second = profile._apply_damage_with_tracking(
            target_model,
            attacker_model,
            1,
            False,
            attack_instance={},
            game_map=game.map,
        )

    assert int(second.get("fnp_saves", 0) or 0) == 1
    assert int(second.get("damage_applied", 0) or 0) == 0
    assert int(target_model.wounds or 0) == int(target_model._base_wounds) - 1
    assert target_model.has_used_once_per_battle("null_nodules")


def test_null_nodules_local_provider_consumes_queued_confirmation():
    from warhammer40k_ai.utility.decision_utils import resolve_decision_value

    game, tyr_player, enemy_player = _build_game(tyr_control=PlayerControl.LOCAL)
    target_unit = _make_real_unit(
        "Neurotyrant",
        keywords=["MONSTER", "CHARACTER"],
        faction_keywords=["TYRANIDS"],
    )
    attacker_unit = _make_real_unit(
        "Enemy Psyker",
        keywords=["INFANTRY", "PSYKER"],
        faction_keywords=["ENEMY"],
    )

    tyr_player.army.add_unit(target_unit)
    enemy_player.army.add_unit(attacker_unit)
    game.map.units = [target_unit, attacker_unit]
    game.rebuild_entity_registry()

    _apply_crusher_enhancement(
        target_unit,
        enhancement_id="000008404004",
        name="Null Nodules",
    )

    seen = {"pending": 0}

    def _provider(**_kwargs):
        pending = [
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "context", {}).get("ability", "") or "") == "null_nodules"
        ]
        assert pending
        req = pending[0]
        seen["pending"] = len(pending)
        option_id = next(
            opt.option_id
            for opt in list(getattr(req, "options", []) or [])
            if bool(getattr(opt, "payload", {}).get("choice", False))
        )
        _, apply_result = resolve_decision_value(game, req, option_id, player_id=getattr(tyr_player, "id", None))
        assert apply_result is not None and getattr(apply_result, "ok", False)
        return "use"

    game.map.unit_psychic_attack_fnp_provider = _provider
    profile = _make_profile(is_melee=False, description="[PSYCHIC]")

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=5):
        result = profile._apply_damage_with_tracking(
            target_unit.models[0],
            attacker_unit.models[0],
            1,
            False,
            attack_instance={},
            game_map=game.map,
        )

    assert int(result.get("damage_applied", 0) or 0) == 0
    assert int(seen["pending"] or 0) == 1
    assert list(game.decision_queue.list() or []) == []
    assert target_unit.models[0].has_used_once_per_battle("null_nodules")


def test_crusher_enhancement_support_matrix_entries_are_supported():
    gsm = _seed_support_maps()
    expected = {
        "000008404002": ("Ominous Presence", "+3 objective control"),
        "000008404003": ("Enraged Reserves", "fights after the attacking unit finishes"),
        "000008404004": ("Null Nodules", "feel no pain 5+"),
        "000008404005": ("Monstrous Nemesis", "+1 to wound"),
    }
    for enhancement_id, (name, note_fragment) in expected.items():
        status, notes = gsm._enhancement_support(name, enhancement_id, "")
        assert status == "Supported"
        assert note_fragment.lower() in str(notes or "").lower()
