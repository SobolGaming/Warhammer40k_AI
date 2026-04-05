from types import SimpleNamespace


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        with_droneport_ability: bool,
    ) -> None:
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = ["FORTIFICATION"] if "Tidewall" in name else ["INFANTRY"]
        self.faction_keywords = ["T'AU EMPIRE"] if "Tidewall" in name else ["ENEMY"]
        self.datasheets_unit_composition = [{"description": f"1 {name}"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": "100"}]
        self.datasheets_models = [
            {
                "M": "4",
                "T": "8",
                "Sv": "3",
                "W": "10",
                "Ld": "7",
                "OC": "0",
                "base_size": "Use model",
                "inv_sv": "-",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = [
            {
                "line": "1",
                "line_in_wargear": "1",
                "dice": "",
                "name": "Drone defenders",
                "description": "assault, twin-linked",
                "range": "20",
                "type": "Ranged",
                "A": "8",
                "BS_WS": "5",
                "S": "5",
                "AP": "0",
                "D": "1",
            }
        ]
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        if with_droneport_ability:
            self.datasheets_abilities.append(
                {
                    "name": "Droneport",
                    "description": (
                        "Each time this FORTIFICATION is selected to shoot, its drone defender's weapon will target "
                        "and resolve attacks against every enemy unit that is an eligible target to this FORTIFICATION."
                    ),
                    "type": "Datasheet",
                    "parameter": "",
                }
            )
        self.loadout = "<b>This model is equipped with:</b> drone defenders."
        self.transport = ""


class _EnemyMap:
    def __init__(self, enemies):
        self._enemies = list(enemies)

    def get_enemy_units(self, _unit):
        return list(self._enemies)


def _make_unit(name: str, *, with_droneport_ability: bool):
    from warhammer40k_ai.units.unit import Unit
    from warhammer40k_ai.units.wargear import Wargear

    unit = Unit(_MockDatasheet(name, with_droneport_ability=with_droneport_ability))
    if unit.models and not list(getattr(unit.models[0], "wargear", []) or []):
        unit.models[0].wargear = [
            Wargear(
                {
                    "name": "Drone defenders",
                    "type": "Ranged",
                    "range": "20",
                    "A": "8",
                    "BS_WS": "5",
                    "S": "5",
                    "AP": "0",
                    "D": "1",
                    "description": "assault, twin-linked",
                }
            )
        ]
    return unit


def _attach_to_armies(shooter, enemies):
    friendly_army = SimpleNamespace(player=SimpleNamespace(game=None), faction_id="TAU", units=[shooter])
    enemy_army = SimpleNamespace(player=SimpleNamespace(game=None), faction_id="EN", units=list(enemies))
    shooter.set_parent_army(friendly_army)
    for enemy in enemies:
        enemy.set_parent_army(enemy_army)


def _prepare_shooter_test_doubles(shooter, profile, eligible_targets, attacked_targets):
    shooter.validate_ctan_power_selection = lambda *_args, **_kwargs: (True, "")
    shooter._is_locked_in_combat = lambda _game_map: False
    shooter._resolve_pending_attack_mortal_wounds = lambda *_args, **_kwargs: None
    shooter._resolve_pending_horrors_split = lambda **_kwargs: None

    def _validate(_weapon_profile, target_unit, _models_with_weapon, _game_map, **_kwargs):
        return {"valid": bool(target_unit in eligible_targets), "reason": "ok"}

    def _execute(_weapon_profile, target_unit, _models, _game_map, _weapon_instance, **_kwargs):
        attacked_targets.append(target_unit)
        return 1

    shooter._validate_shooting_declaration = _validate
    shooter._execute_weapon_attacks = _execute


def test_droneport_expands_drone_defenders_to_every_eligible_enemy_unit():
    shooter = _make_unit("Tidewall Droneport", with_droneport_ability=True)
    enemy_a = _make_unit("Enemy A", with_droneport_ability=False)
    enemy_b = _make_unit("Enemy B", with_droneport_ability=False)
    enemy_c = _make_unit("Enemy C", with_droneport_ability=False)
    _attach_to_armies(shooter, [enemy_a, enemy_b, enemy_c])

    profile = shooter.models[0].wargear[0].profiles["default"]
    attacked_targets = []
    eligible_targets = {enemy_a, enemy_b}
    _prepare_shooter_test_doubles(shooter, profile, eligible_targets, attacked_targets)

    declarations = [{"weapon_profile": profile, "target_unit": enemy_a, "models": [shooter.models[0]]}]
    result = shooter.execute_shooting_declarations(declarations, game_map=_EnemyMap([enemy_a, enemy_b, enemy_c]))

    assert result is True
    assert attacked_targets.count(enemy_a) == 1
    assert attacked_targets.count(enemy_b) == 1
    assert enemy_c not in attacked_targets
    assert len(attacked_targets) == 2


def test_without_droneport_ability_declarations_are_not_expanded():
    shooter = _make_unit("Tidewall Droneport", with_droneport_ability=False)
    enemy_a = _make_unit("Enemy A", with_droneport_ability=False)
    enemy_b = _make_unit("Enemy B", with_droneport_ability=False)
    _attach_to_armies(shooter, [enemy_a, enemy_b])

    profile = shooter.models[0].wargear[0].profiles["default"]
    attacked_targets = []
    eligible_targets = {enemy_a, enemy_b}
    _prepare_shooter_test_doubles(shooter, profile, eligible_targets, attacked_targets)

    declarations = [{"weapon_profile": profile, "target_unit": enemy_a, "models": [shooter.models[0]]}]
    result = shooter.execute_shooting_declarations(declarations, game_map=_EnemyMap([enemy_a, enemy_b]))

    assert result is True
    assert attacked_targets == [enemy_a]
