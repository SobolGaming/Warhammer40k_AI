import pytest
from typing import List
from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Map, TerrainFactory
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.wargear import WargearProfile


class MockDatasheet:
    def __init__(
        self,
        name: str,
        movement=6,
        model_count=1,
        base_size="32mm",
        save="4",
        *,
        datasheet_id: str | None = None,
        attached_to=None,
        abilities=None,
        keywords=None,
        faction_keywords=None,
    ):
        self.name = name
        self.id = datasheet_id or name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [
            {"description": f"{model_count} Test Models"}
        ]
        self.datasheets_models_cost = [
            {"description": f"{model_count} models", "cost": 100}
        ]
        self.datasheets_models = [{
            "M": str(movement), "T": "4", "Sv": str(save), "W": "1",
            "Ld": "7", "OC": "1",
            "base_size": base_size, "inv_sv": "7", "inv_sv_descr": "none"
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []
        self.loadout = "This model is equipped with: nothing"


def create_unit(
    name: str,
    x: float,
    y: float,
    faction: str = "A",
    model_count: int = 1,
    save: str = "4",
    *,
    datasheet_id: str | None = None,
    abilities=None,
    attached_to=None,
) -> Unit:
    ds = MockDatasheet(
        name,
        model_count=model_count,
        save=save,
        datasheet_id=datasheet_id,
        abilities=abilities,
        attached_to=attached_to,
    )
    unit = Unit(ds)
    # Place each model with small spacing along X so bases don't overlap
    for i, m in enumerate(unit.models):
        m.set_location(x + (i * 1.5), y, 0.0, 0.0)
    unit.deployed = True
    unit.faction = faction
    return unit


def attach_to_armies(game_map: Map, units_a: List[Unit], units_b: List[Unit]):
    army_a = Army("Army A", "Detachment A")
    army_b = Army("Army B", "Detachment B")
    for u in units_a:
        army_a.add_unit(u)
    for u in units_b:
        army_b.add_unit(u)
    game_map.units = units_a + units_b
    return army_a, army_b


class TestBenefitOfCover:
    def test_woods_wholly_within_grants_cover(self):
        game_map = Map(width=48, height=72)
        attacker = create_unit("Attackers", 10.0, 10.0, faction="A", model_count=2, save="4")
        target = create_unit("Target", 30.0, 10.0, faction="B", model_count=1, save="4")
        attach_to_armies(game_map, [attacker], [target])

        # Woods footprint covering the target base
        woods = TerrainFactory.create_woods([(28.0, 8.0), (32.0, 8.0), (32.0, 12.0), (28.0, 12.0)], height=6.0, density=0.8)
        game_map.add_terrain_feature(woods)

        info = game_map.get_benefit_of_cover_for_ranged_attack(attacking_unit=attacker, target_model=target.models[0])
        assert info["has_benefit_of_cover"] is True
        assert info["source_terrain_type"] == "WOODS"

    def test_ruins_not_fully_visible_to_every_attacker_grants_cover(self):
        game_map = Map(width=48, height=72)
        attacker = create_unit("Attackers", 10.0, 10.0, faction="A", model_count=2, save="4")
        target = create_unit("Target", 30.0, 10.0, faction="B", model_count=1, save="4")
        attach_to_armies(game_map, [attacker], [target])

        # Move attacker model #1 so that its line crosses the ruins footprint, while model #0 does not.
        attacker.models[0].set_location(10.0, 10.0, 0.0, 0.0)  # clear lane
        attacker.models[1].set_location(10.0, 20.0, 0.0, 0.0)  # crosses ruins

        ruins = TerrainFactory.create_ruins([(15.0, 12.0), (25.0, 12.0), (25.0, 18.0), (15.0, 18.0)], wall_height=4.0, num_floors=1)
        game_map.add_terrain_feature(ruins)

        info = game_map.get_benefit_of_cover_for_ranged_attack(attacking_unit=attacker, target_model=target.models[0])
        assert info["has_benefit_of_cover"] is True
        assert info["source_terrain_type"] == "RUINS"

    def test_benefit_of_cover_adds_plus_one_to_armor_save_roll(self, monkeypatch):
        # Force a deterministic save roll of 3
        import warhammer40k_ai.units.wargear as wargear_mod
        monkeypatch.setattr(wargear_mod, "get_roll", lambda _expr: 3)

        game_map = Map(width=48, height=72)
        target = create_unit("Target", 30.0, 10.0, faction="B", model_count=1, save="4")
        attacker = create_unit("Attacker", 10.0, 10.0, faction="A", model_count=1, save="4")
        attach_to_armies(game_map, [attacker], [target])

        wp = WargearProfile("default", {"range": "24", "A": "1", "BS_WS": "3", "S": "4", "AP": "0", "D": "1", "description": ""})

        # Without cover, a 3 on a 4+ save fails.
        res_no = wp._save_with_tracking(target.models[0], {"mortal_wound": False}, ap=0)
        assert res_no["saved"] is False

        # With cover, +1 makes 3 become 4 -> saved.
        res_cov = wp._save_with_tracking(target.models[0], {"mortal_wound": False, "benefit_of_cover": True, "benefit_of_cover_source": "RUINS"}, ap=0)
        assert res_cov["saved"] is True

    def test_sv_3_or_better_does_not_get_cover_vs_ap0(self, monkeypatch):
        # Force a deterministic save roll of 2
        import warhammer40k_ai.units.wargear as wargear_mod
        monkeypatch.setattr(wargear_mod, "get_roll", lambda _expr: 2)

        game_map = Map(width=48, height=72)
        target = create_unit("Target", 30.0, 10.0, faction="B", model_count=1, save="3")  # 3+
        attacker = create_unit("Attacker", 10.0, 10.0, faction="A", model_count=1, save="4")
        attach_to_armies(game_map, [attacker], [target])

        wp = WargearProfile("default", {"range": "24", "A": "1", "BS_WS": "3", "S": "4", "AP": "0", "D": "1", "description": ""})

        # If cover incorrectly applied, 2+1 would pass a 3+.
        res_cov = wp._save_with_tracking(target.models[0], {"mortal_wound": False, "benefit_of_cover": True, "benefit_of_cover_source": "WOODS"}, ap=0)
        assert res_cov["saved"] is False

    def test_indirect_fire_allows_shooting_without_los(self):
        game_map = Map(width=48, height=72)
        attacker = create_unit("Attacker", 10.0, 10.0, faction="A", model_count=1, save="4")
        target = create_unit("Target", 30.0, 10.0, faction="B", model_count=1, save="4")
        attach_to_armies(game_map, [attacker], [target])

        # Ruins footprint between attacker and target -> blocks LOS normally.
        ruins = TerrainFactory.create_ruins([(15.0, 8.0), (25.0, 8.0), (25.0, 12.0), (15.0, 12.0)], wall_height=4.0, num_floors=1)
        game_map.add_terrain_feature(ruins)

        indirect_wp = WargearProfile("default", {"range": "48", "A": "1", "BS_WS": "4", "S": "4", "AP": "0", "D": "1", "description": "Indirect Fire"})
        assert attacker._can_model_shoot_weapon_at_target(attacker.models[0], indirect_wp, target, game_map) is True

    def test_indirect_fire_hit_roll_1_2_3_always_fail_and_minus_one_to_hit(self, monkeypatch):
        import warhammer40k_ai.units.wargear as wargear_mod

        # First test: 1-3 always fail (use roll=3)
        monkeypatch.setattr(wargear_mod, "get_roll", lambda _expr: 3)
        attacker = create_unit("Attacker", 10.0, 10.0, faction="A", model_count=1, save="4")
        target = create_unit("Target", 30.0, 10.0, faction="B", model_count=1, save="4")
        wp = WargearProfile("default", {"range": "48", "A": "1", "BS_WS": "2", "S": "4", "AP": "0", "D": "1", "description": "Indirect Fire"})
        hit = wp._hit_target_with_tracking(target, attacker.models[0], {"indirect_fire_no_visible": True})
        assert hit["hit"] is False

        # Second test: -1 to hit matters (use roll=4 vs BS 4+ should miss)
        monkeypatch.setattr(wargear_mod, "get_roll", lambda _expr: 4)
        wp2 = WargearProfile("default", {"range": "48", "A": "1", "BS_WS": "4", "S": "4", "AP": "0", "D": "1", "description": "Indirect Fire"})
        hit2 = wp2._hit_target_with_tracking(target, attacker.models[0], {"indirect_fire_no_visible": True})
        assert hit2["hit"] is False

    def test_leading_unit_benefit_of_cover_applies_to_ranged_only(self, monkeypatch):
        import warhammer40k_ai.units.wargear as wargear_mod
        monkeypatch.setattr(wargear_mod, "get_roll", lambda _expr: 3)

        ability_text = (
            "While this model is leading a unit, each time a ranged attack targets that unit, "
            "models in it have the Benefit of Cover against that attack."
        )
        leader_ability = [{
            "name": "Shielded Command",
            "description": ability_text,
            "type": "Ability",
            "parameter": "",
        }]

        bodyguard = create_unit("Bodyguard", 10.0, 10.0, faction="A", model_count=1, save="4", datasheet_id="BG1")
        leader = create_unit(
            "Leader",
            12.0,
            10.0,
            faction="A",
            model_count=1,
            save="4",
            datasheet_id="L1",
            abilities=leader_ability,
            attached_to=["BG1"],
        )
        game_map = Map(width=48, height=72)
        attach_to_armies(game_map, [bodyguard, leader], [])
        leader.attach_to_unit(bodyguard)

        target_no_leader = create_unit("NoLeader", 20.0, 10.0, faction="B", model_count=1, save="4", datasheet_id="BG2")

        ranged_wp = WargearProfile("ranged", {"range": "24", "A": "1", "BS_WS": "3", "S": "4", "AP": "0", "D": "1", "description": ""})
        melee_wp = WargearProfile("melee", {"range": "Melee", "A": "1", "BS_WS": "3", "S": "4", "AP": "0", "D": "1", "description": ""})

        res_no = ranged_wp._save_with_tracking(target_no_leader.models[0], {"mortal_wound": False}, ap=0)
        assert res_no["saved"] is False

        res_ranged = ranged_wp._save_with_tracking(bodyguard.models[0], {"mortal_wound": False}, ap=0)
        assert res_ranged["saved"] is True

        res_melee = melee_wp._save_with_tracking(bodyguard.models[0], {"mortal_wound": False}, ap=0)
        assert res_melee["saved"] is False

    def test_objective_range_benefit_of_cover(self, monkeypatch):
        import warhammer40k_ai.units.wargear as wargear_mod
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint

        monkeypatch.setattr(wargear_mod, "get_roll", lambda _expr: 3)

        ability_text = (
            "While this unit is within range of an objective marker, each time a ranged attack targets this unit, "
            "models in this unit have the Benefit of Cover against that attack."
        )
        ability = [{
            "name": "Twisted Defence Force",
            "description": ability_text,
            "type": "Ability",
            "parameter": "",
        }]

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
        army_a = Army("Army A", "Detachment A")
        army_b = Army("Army B", "Detachment B")
        p1 = Player("P1", PlayerControl.LOCAL, army=army_a)
        p2 = Player("P2", PlayerControl.REMOTE, army=army_b)
        game.add_player(p1)
        game.add_player(p2)

        target = create_unit("Target", 10.0, 10.0, faction="A", model_count=1, save="4", abilities=ability)
        attacker = create_unit("Attacker", 30.0, 10.0, faction="B", model_count=1, save="4")
        army_a.add_unit(target)
        army_b.add_unit(attacker)

        objective_point = ObjectivePoint(10.0, 10.0, 0.0, control_radius=3.0)
        objective = Objective(
            name="Test Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=objective_point,
        )
        game.map.add_objective(objective)

        ranged_wp = WargearProfile("ranged", {"range": "24", "A": "1", "BS_WS": "3", "S": "4", "AP": "0", "D": "1", "description": ""})

        res_in_range = ranged_wp._save_with_tracking(target.models[0], {"mortal_wound": False}, ap=0, roll_value=3, allow_rerolls=False)
        assert res_in_range["saved"] is True

        target.models[0].set_location(30.0, 30.0, 0.0, 0.0)
        res_out = ranged_wp._save_with_tracking(target.models[0], {"mortal_wound": False}, ap=0, roll_value=3, allow_rerolls=False)
        assert res_out["saved"] is False

    def test_aura_benefit_of_cover_applies_to_ranged_only(self, monkeypatch):
        import warhammer40k_ai.units.wargear as wargear_mod
        import warhammer40k_ai.utility.aura_effects as aura_mod

        monkeypatch.setattr(wargear_mod, "get_roll", lambda _expr: 1)
        monkeypatch.setattr(aura_mod, "unit_within_range_of_unit", lambda *_args, **_kwargs: True)

        ability_text = (
            "While a friendly War Dog model is within 6\" of this model, "
            "that WAR DOG model has the Benefit of Cover."
        )
        aura_ability = [{
            "name": "Infernal Aegis (Aura)",
            "description": ability_text,
            "type": "Ability",
            "parameter": "",
        }]

        game_map = Map(width=48, height=72)
        aura_source = create_unit("Source", 10.0, 10.0, faction="A", model_count=1, abilities=aura_ability)
        target = create_unit("Target", 12.0, 10.0, faction="A", model_count=1)
        attacker = create_unit("Attacker", 30.0, 10.0, faction="B", model_count=1)

        army_a, army_b = attach_to_armies(game_map, [aura_source, target], [attacker])
        game = SimpleNamespace(map=game_map)
        army_a.player = SimpleNamespace(game=game, name="P1", id="P1")
        army_b.player = SimpleNamespace(game=game, name="P2", id="P2")

        target.has_any_keyword = lambda kw: str(kw).strip().lower() == "war dog"

        ranged_wp = WargearProfile(
            "ranged",
            {"range": "24", "A": "1", "BS_WS": "3", "S": "4", "AP": "0", "D": "1", "description": ""},
        )
        attack_instance = {"mortal_wound": False}
        ranged_wp._save_with_tracking(target.models[0], attack_instance, ap=0)
        assert attack_instance.get("benefit_of_cover") is True
        assert "Infernal Aegis" in str(attack_instance.get("benefit_of_cover_source", ""))

        melee_wp = WargearProfile(
            "melee",
            {"range": "Melee", "A": "1", "BS_WS": "3", "S": "4", "AP": "0", "D": "1", "description": ""},
        )
        attack_instance_melee = {"mortal_wound": False}
        melee_wp._save_with_tracking(target.models[0], attack_instance_melee, ap=0)
        assert attack_instance_melee.get("benefit_of_cover") is None

    def test_aura_benefit_of_cover_parses_friendly_unit_wording(self, monkeypatch):
        import warhammer40k_ai.units.wargear as wargear_mod
        import warhammer40k_ai.utility.aura_effects as aura_mod

        monkeypatch.setattr(wargear_mod, "get_roll", lambda _expr: 1)
        monkeypatch.setattr(aura_mod, "unit_within_range_of_unit", lambda *_args, **_kwargs: True)

        ability_text = (
            "While a friendly DEATH GUARD unit is within 6\" of this model, each time a ranged attack targets that unit, "
            "models in that unit have the Benefit of Cover against that attack."
        )
        aura_ability = [{
            "name": "Miasma of Pestilence (Aura)",
            "description": ability_text,
            "type": "Ability",
            "parameter": "",
        }]

        game_map = Map(width=48, height=72)
        aura_source = create_unit("Source", 10.0, 10.0, faction="A", model_count=1, abilities=aura_ability)
        target = create_unit("Target", 12.0, 10.0, faction="A", model_count=1)
        attacker = create_unit("Attacker", 30.0, 10.0, faction="B", model_count=1)

        army_a, army_b = attach_to_armies(game_map, [aura_source, target], [attacker])
        game = SimpleNamespace(map=game_map)
        army_a.player = SimpleNamespace(game=game, name="P1", id="P1")
        army_b.player = SimpleNamespace(game=game, name="P2", id="P2")

        target.has_any_keyword = lambda kw: str(kw).strip().lower() == "death guard"

        ranged_wp = WargearProfile(
            "ranged",
            {"range": "24", "A": "1", "BS_WS": "3", "S": "4", "AP": "0", "D": "1", "description": ""},
        )
        attack_instance = {"mortal_wound": False}
        ranged_wp._save_with_tracking(target.models[0], attack_instance, ap=0)
        assert attack_instance.get("benefit_of_cover") is True
        assert "Miasma of Pestilence" in str(attack_instance.get("benefit_of_cover_source", ""))

    def test_selfless_protector_rule_parses(self):
        ability_text = (
            "Each time a ranged attack is allocated to an Imperial Knights model from your army, if that model "
            "is not fully visible to every model in the attacking unit because of this Knight Defender model, "
            "that model has the Benefit of Cover and a 4+ invulnerable save against that attack."
        )
        abilities = [{
            "name": "Selfless Protector",
            "description": ability_text,
            "type": "Ability",
            "parameter": "",
        }]
        defender = create_unit("Knight Defender", 20.0, 10.0, faction="A", model_count=1, abilities=abilities)

        rule = defender.get_selfless_protector_rule()
        assert isinstance(rule, dict)
        assert str(rule.get("source", "")) == "Selfless Protector"
        assert int(rule.get("invulnerable_save", 0) or 0) == 4

    def test_selfless_protector_applies_cover_and_invuln_for_imperial_knights_target(self, monkeypatch):
        import warhammer40k_ai.units.wargear as wargear_mod

        monkeypatch.setattr(wargear_mod, "get_roll", lambda _expr: 4)

        ability_text = (
            "Each time a ranged attack is allocated to an Imperial Knights model from your army, if that model "
            "is not fully visible to every model in the attacking unit because of this Knight Defender model, "
            "that model has the Benefit of Cover and a 4+ invulnerable save against that attack."
        )
        abilities = [{
            "name": "Selfless Protector",
            "description": ability_text,
            "type": "Ability",
            "parameter": "",
        }]

        game_map = Map(width=48, height=72)
        attacker = create_unit("Attacker", 10.0, 10.0, faction="B", model_count=1, save="4")
        protector = create_unit("Knight Defender", 20.0, 10.0, faction="A", model_count=1, save="4", abilities=abilities)
        target = create_unit("Armiger", 30.0, 10.0, faction="A", model_count=1, save="4")

        army_a, army_b = attach_to_armies(game_map, [protector, target], [attacker])
        game = SimpleNamespace(map=game_map)
        army_a.player = SimpleNamespace(game=game, name="P1", id="P1")
        army_b.player = SimpleNamespace(game=game, name="P2", id="P2")

        target.has_any_keyword = lambda kw: str(kw).strip().upper() == "IMPERIAL KNIGHTS"
        target.has_keyword = lambda kw: str(kw).strip().upper() == "IMPERIAL KNIGHTS"

        wp = WargearProfile("ranged", {"range": "24", "A": "1", "BS_WS": "3", "S": "6", "AP": "3", "D": "2", "description": ""})
        attack_instance = {"mortal_wound": False, "attacker_unit": attacker}
        res = wp._save_with_tracking(target.models[0], attack_instance, ap=-3, roll_value=4, allow_rerolls=False)

        assert attack_instance.get("benefit_of_cover") is True
        assert "Selfless Protector" in str(attack_instance.get("benefit_of_cover_source", ""))
        assert int(attack_instance.get("inv_save_override", 0) or 0) == 4
        assert res.get("save_type") == "invulnerable"
        assert res.get("saved") is True

    def test_selfless_protector_does_not_apply_to_non_imperial_knights_target(self, monkeypatch):
        import warhammer40k_ai.units.wargear as wargear_mod

        monkeypatch.setattr(wargear_mod, "get_roll", lambda _expr: 4)

        ability_text = (
            "Each time a ranged attack is allocated to an Imperial Knights model from your army, if that model "
            "is not fully visible to every model in the attacking unit because of this Knight Defender model, "
            "that model has the Benefit of Cover and a 4+ invulnerable save against that attack."
        )
        abilities = [{
            "name": "Selfless Protector",
            "description": ability_text,
            "type": "Ability",
            "parameter": "",
        }]

        game_map = Map(width=48, height=72)
        attacker = create_unit("Attacker", 10.0, 10.0, faction="B", model_count=1, save="4")
        protector = create_unit("Knight Defender", 20.0, 10.0, faction="A", model_count=1, save="4", abilities=abilities)
        target = create_unit("NonIK Target", 30.0, 10.0, faction="A", model_count=1, save="4")

        army_a, army_b = attach_to_armies(game_map, [protector, target], [attacker])
        game = SimpleNamespace(map=game_map)
        army_a.player = SimpleNamespace(game=game, name="P1", id="P1")
        army_b.player = SimpleNamespace(game=game, name="P2", id="P2")

        target.has_any_keyword = lambda _kw: False
        target.has_keyword = lambda _kw: False

        wp = WargearProfile("ranged", {"range": "24", "A": "1", "BS_WS": "3", "S": "6", "AP": "3", "D": "2", "description": ""})
        attack_instance = {"mortal_wound": False, "attacker_unit": attacker}
        res = wp._save_with_tracking(target.models[0], attack_instance, ap=-3, roll_value=4, allow_rerolls=False)

        assert attack_instance.get("benefit_of_cover") is None
        assert attack_instance.get("inv_save_override") is None
        assert res.get("save_type") == "armor"
        assert res.get("saved") is False
