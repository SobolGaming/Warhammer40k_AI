import types

from warhammer40k_ai.units.wargear import AttackResult, Wargear


class DummyUnit:
    def __init__(self):
        self.special_rules = {}

    def get_parent_army(self):
        return types.SimpleNamespace(player=types.SimpleNamespace(game=None))


class DummyModel:
    def __init__(self):
        self.name = "Attacker"
        self.parent_unit = DummyUnit()
        self.is_character = False

    def get_temporary_melee_attacks_bonus(self):
        return 0

    def return_closest_model_in_unit(self, _target):
        return None, 0.0


class DummyTarget:
    def __init__(self):
        self.name = "Target"
        self.models = []


def _make_profile(attacks: str = "3"):
    wargear_data = {
        "name": "Test Blade",
        "type": "Melee",
        "range": "Melee",
        "A": attacks,
        "BS_WS": "3+",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    wargear = Wargear(wargear_data)
    return list(wargear.profiles.values())[0]


def _make_attack_result(profile, attacker, target):
    return AttackResult(
        weapon_name="Test Blade",
        attacker_name=attacker.name,
        target_unit_name=target.name,
        attacks_rolled=0,
        attacks_dice_expression=str(profile.attacks),
        attacks_dice_rolls=[],
        attacks_special_modifiers=[],
        hit_results=[],
        wound_results=[],
        save_results=[],
        damage_results=[],
        hazardous_roll=None,
        hazardous_damage=0,
        total_hits=0,
        total_wounds=0,
        total_saves_failed=0,
        total_damage_dealt=0,
        models_killed=0,
    )


def test_attack_count_override_applies():
    profile = _make_profile(attacks="3")
    attacker = DummyModel()
    target = DummyTarget()
    attack_result = _make_attack_result(profile, attacker, target)

    info = profile._resolve_attack_count(
        target,
        attacker,
        attack_result,
        publish_roll_event=False,
        attacks_override=2,
        attacks_override_modifiers=["Override"],
        attacks_override_note="Split 2 of 5",
    )

    assert info.num_attacks == 2
    assert attack_result.attacks_rolled == 2
    assert "Override" in attack_result.attacks_special_modifiers
    assert "Split 2 of 5" in attack_result.attacks_special_modifiers
