from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count=1,
        base_size="32mm",
    ):
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "6",
                "Ld": "6",
                "OC": "1",
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _make_unit(name, *, abilities=None, keywords=None, faction_keywords=None, model_count=1):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        keywords=keywords,
        faction_keywords=faction_keywords,
        model_count=model_count,
    )
    return Unit(datasheet)


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield)

    blood_angels = Army.with_detachment("Blood Angels", detachment_type="Liberator Assault Group")
    blood_angels.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    blood_player = Player("Blood", control=PlayerControl.LOCAL, army=blood_angels)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(blood_player)
    game.add_player(enemy_player)
    return game, blood_player, enemy_player, blood_angels, enemy_army


class _DummyWargear:
    def is_melee(self):
        return True


class _DummyProfile:
    def __init__(self):
        self.parent_wargear = _DummyWargear()


class _DummyRangedWargear:
    def is_melee(self):
        return False


class _DummyRangedProfile:
    def __init__(self):
        self.parent_wargear = _DummyRangedWargear()


def _tycho_style_rule():
    return {
        "name": "Death Vision of Sanguinius",
        "description": (
            "If this model is destroyed by a melee attack, after the attacking unit has finished making its attacks, "
            "you can roll one D6, adding 2 to the result if the attacking unit contains the enemy WARLORD: on a 2-3, "
            "that enemy unit suffers 3 mortal wounds; on a 4-5, that enemy unit suffers D3+3 mortal wounds; on a 6+, "
            "that enemy unit suffers D6+3 mortal wounds."
        ),
        "type": "Datasheet",
        "parameter": "",
    }


def _captain_style_rule():
    return {
        "name": "Death Vision of Sanguinius",
        "description": (
            "If this model is destroyed by a melee attack, after the attacking unit has finished making its attacks, "
            "you can roll one D6, adding 2 to the result if the attacking unit contains the enemy WARLORD: on a 2-3, "
            "that enemy unit suffers D3 mortal wounds; on a 4-5, that enemy unit suffers 3 mortal wounds; on a 6+, "
            "that enemy unit suffers D3+3 mortal wounds."
        ),
        "type": "Datasheet",
        "parameter": "",
    }


def test_death_vision_of_sanguinius_uses_warlord_bonus_and_high_table():
    game, blood_player, _enemy_player, blood_angels, enemy_army = _build_game()

    tycho = _make_unit("Tycho the Lost", abilities=[_tycho_style_rule()], keywords=["CHARACTER"])
    enemy = _make_unit("Enemy Warlord", keywords=["CHARACTER"])
    enemy.is_warlord = True
    enemy_army.warlord = enemy

    blood_angels.add_unit(tycho)
    enemy_army.add_unit(enemy)
    tycho.deployed = True
    enemy.deployed = True
    game.map.units = [tycho, enemy]
    game.rebuild_entity_registry()

    tycho._last_destroyed_by_unit = enemy
    tycho._last_destroyed_by_weapon_profile = _DummyProfile()
    model = tycho.models[0]
    model._wounds = 0

    applied = []
    tycho._apply_mortal_wounds_to_unit = lambda target, amount, **_kwargs: applied.append((target, int(amount)))

    blood_player.set_next_optional_decision("DEATH_VISION_OF_SANGUINIUS", True)

    with patch("warhammer40k_ai.units.unit.get_roll", side_effect=[4, 5]):
        tycho._handle_model_destroyed(model, game.map)
        tycho.end_attack_resolution(game_map=game.map)

    assert applied == [(enemy, 5)]


def test_death_vision_of_sanguinius_resolves_from_attached_leader_root_queue():
    game, blood_player, _enemy_player, blood_angels, enemy_army = _build_game()

    bodyguard = _make_unit("Assault Intercessors", model_count=5)
    captain = _make_unit("Death Company Captain", abilities=[_captain_style_rule()], keywords=["CHARACTER"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"])

    blood_angels.add_unit(bodyguard)
    blood_angels.add_unit(captain)
    enemy_army.add_unit(enemy)
    bodyguard.deployed = True
    captain.deployed = True
    enemy.deployed = True
    captain.can_be_attached_to = [bodyguard.get_datasheet_id()]
    captain.attached_to = bodyguard
    bodyguard.attached_leaders = [captain]
    game.map.units = [bodyguard, enemy]
    game.rebuild_entity_registry()

    captain._last_destroyed_by_unit = enemy
    captain._last_destroyed_by_weapon_profile = _DummyProfile()
    model = captain.models[0]
    model._wounds = 0

    applied = []
    captain._apply_mortal_wounds_to_unit = lambda target, amount, **_kwargs: applied.append((target, int(amount)))

    blood_player.set_next_optional_decision("DEATH_VISION_OF_SANGUINIUS", True)

    with patch("warhammer40k_ai.units.unit.get_roll", side_effect=[2, 3]):
        captain._handle_model_destroyed(model, game.map)
        pending = list(getattr(bodyguard, "_death_vision_of_sanguinius_pending", []) or [])
        assert len(pending) == 1
        bodyguard.end_attack_resolution(game_map=game.map)

    assert applied == [(enemy, 3)]


def test_death_vision_of_sanguinius_requires_melee_attack():
    game, blood_player, _enemy_player, blood_angels, enemy_army = _build_game()

    tycho = _make_unit("Tycho the Lost", abilities=[_tycho_style_rule()], keywords=["CHARACTER"])
    enemy = _make_unit("Enemy Shooters", keywords=["INFANTRY"])

    blood_angels.add_unit(tycho)
    enemy_army.add_unit(enemy)
    tycho.deployed = True
    enemy.deployed = True
    game.map.units = [tycho, enemy]
    game.rebuild_entity_registry()

    tycho._last_destroyed_by_unit = enemy
    tycho._last_destroyed_by_weapon_profile = _DummyRangedProfile()
    model = tycho.models[0]
    model._wounds = 0

    applied = []
    tycho._apply_mortal_wounds_to_unit = lambda target, amount, **_kwargs: applied.append((target, int(amount)))

    blood_player.set_next_optional_decision("DEATH_VISION_OF_SANGUINIUS", True)

    with patch("warhammer40k_ai.units.unit.get_roll", side_effect=[6, 6]):
        tycho._handle_model_destroyed(model, game.map)
        tycho.end_attack_resolution(game_map=game.map)

    assert applied == []
