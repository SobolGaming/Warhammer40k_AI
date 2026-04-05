import types
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(self, name, *, unit_comp="1 Test Model", abilities=None, keywords=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = ["TYRANIDS"]
        self.datasheets_unit_composition = [{"description": unit_comp}]
        self.datasheets_models_cost = [{"description": unit_comp, "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "1",
                "Sv": "7",
                "W": "1",
                "Ld": "7",
                "OC": "1",
                "base_size": "25mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = []


def _make_unit(name, *, ability_desc=None, model_count=1, keywords=None):
    from warhammer40k_ai.units.unit import Unit

    abilities = []
    if ability_desc:
        abilities.append(
            {
                "name": "Floating Death",
                "description": ability_desc,
                "type": "Datasheet",
                "parameter": "",
            }
        )
    datasheet = _MockDatasheet(
        name,
        unit_comp=f"{model_count} Test Models",
        abilities=abilities,
        keywords=keywords,
    )
    return Unit(datasheet)


def _setup_players(unit, enemies):
    player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"))
    player.has_control = lambda: False
    enemy_player = SimpleNamespace(name="P2", id="P2", control=SimpleNamespace(name="REMOTE"))
    enemy_player.has_control = lambda: False

    army = SimpleNamespace(player=player, units=[unit])
    enemy_army = SimpleNamespace(player=enemy_player, units=list(enemies))
    player.army = army
    enemy_player.army = enemy_army
    player.get_army = lambda: army
    enemy_player.get_army = lambda: enemy_army
    unit.set_parent_army(army)
    for enemy in enemies:
        enemy.set_parent_army(enemy_army)
    return player, enemy_player


def _find_quarry_request(game):
    from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY

    for req in list(game.decision_queue.list() or []):
        if req.decision_type != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("mortal_wounds_kind", "") or "") == "floating_death":
            return req
    return None


def test_unit_floating_death_specs_parse_both_variants():
    spore_desc = (
        "Each time this unit or an enemy unit ends a move, for each model in this unit that is within 3\" of one or "
        "more enemy units, select one of those enemy units. That model in this unit is destroyed, then roll one D6: "
        "on a 2-5, that enemy unit suffers 1 mortal wound; on a 6, that enemy unit suffers D3 mortal wounds."
    )
    mucolid_desc = (
        "Each time this unit or an enemy unit ends a move, for each model in this unit that is within 3\" of one or "
        "more enemy units, select one of those enemy units. That model in this unit is destroyed, then roll one D6: "
        "on a 2-5, that enemy unit suffers D3 mortal wounds; on a 6, that enemy unit suffers D6 mortal wounds."
    )

    spore = _make_unit("Spore Mines", ability_desc=spore_desc, model_count=1)
    mucolid = _make_unit("Mucolid Spores", ability_desc=mucolid_desc, model_count=1)

    spore_specs = spore.unit_floating_death_specs()
    mucolid_specs = mucolid.unit_floating_death_specs()

    assert len(spore_specs) == 1
    assert len(mucolid_specs) == 1

    spore_spec = spore_specs[0]
    mucolid_spec = mucolid_specs[0]
    assert int(spore_spec.get("range", 0) or 0) == 3
    assert int(spore_spec.get("on_mid_flat", 0) or 0) == 1
    assert str(spore_spec.get("on_mid_die", "") or "") == ""
    assert str(spore_spec.get("on_high_die", "") or "") == "D3"

    assert int(mucolid_spec.get("range", 0) or 0) == 3
    assert int(mucolid_spec.get("on_mid_flat", 0) or 0) == 0
    assert str(mucolid_spec.get("on_mid_die", "") or "") == "D3"
    assert str(mucolid_spec.get("on_high_die", "") or "") == "D6"


def test_floating_death_triggers_from_enemy_move_event_and_resolves_single_target(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    ability_desc = (
        "Each time this unit or an enemy unit ends a move, for each model in this unit that is within 3\" of one or "
        "more enemy units, select one of those enemy units. That model in this unit is destroyed, then roll one D6: "
        "on a 2-5, that enemy unit suffers 1 mortal wound; on a 6, that enemy unit suffers D3 mortal wounds."
    )
    spore = _make_unit("Spore Mines", ability_desc=ability_desc, model_count=1)
    enemy = _make_unit("Enemy Unit", model_count=1)
    spore.deployed = True
    enemy.deployed = True

    player, enemy_player = _setup_players(spore, [enemy])
    source_model = spore.models[0]
    source_model.set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(2.0, 0.0, 0.0, 0.0)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.players = [player, enemy_player]

    applied = {}

    def _apply(self, target_unit, amount, game_map=None):
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        applied["target"] = target_unit
        return 0

    spore._apply_mortal_wounds_to_unit = types.MethodType(_apply, spore)

    rolls = {"D6": [6], "D3": [2]}

    def _fake_get_roll(die):
        return rolls[str(die)].pop(0)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    game.event_system.publish("unit_move_ended", unit=enemy, action="move")

    assert _find_quarry_request(game) is None
    assert int(applied.get("amount", 0) or 0) == 2
    assert applied.get("target") is enemy
    assert source_model not in list(spore.models or [])
    assert len(list(spore.models or [])) == 0


def test_floating_death_triggers_from_own_move_event(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    ability_desc = (
        "Each time this unit or an enemy unit ends a move, for each model in this unit that is within 3\" of one or "
        "more enemy units, select one of those enemy units. That model in this unit is destroyed, then roll one D6: "
        "on a 2-5, that enemy unit suffers 1 mortal wound; on a 6, that enemy unit suffers D3 mortal wounds."
    )
    spore = _make_unit("Spore Mines", ability_desc=ability_desc, model_count=1)
    enemy = _make_unit("Enemy Unit", model_count=1)
    spore.deployed = True
    enemy.deployed = True

    player, enemy_player = _setup_players(spore, [enemy])
    source_model = spore.models[0]
    source_model.set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(2.0, 0.0, 0.0, 0.0)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.players = [player, enemy_player]

    applied = {}

    def _apply(self, target_unit, amount, game_map=None):
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        applied["target"] = target_unit
        return 0

    spore._apply_mortal_wounds_to_unit = types.MethodType(_apply, spore)

    rolls = {"D6": [2]}

    def _fake_get_roll(die):
        return rolls[str(die)].pop(0)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    game.event_system.publish("unit_move_ended", unit=spore, action="move")

    assert _find_quarry_request(game) is None
    assert int(applied.get("amount", 0) or 0) == 1
    assert applied.get("target") is enemy
    assert source_model not in list(spore.models or [])


def test_floating_death_does_not_trigger_on_other_friendly_unit_move(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    ability_desc = (
        "Each time this unit or an enemy unit ends a move, for each model in this unit that is within 3\" of one or "
        "more enemy units, select one of those enemy units. That model in this unit is destroyed, then roll one D6: "
        "on a 2-5, that enemy unit suffers 1 mortal wound; on a 6, that enemy unit suffers D3 mortal wounds."
    )
    spore = _make_unit("Spore Mines", ability_desc=ability_desc, model_count=1)
    ally = _make_unit("Friendly Unit", model_count=1)
    enemy = _make_unit("Enemy Unit", model_count=1)
    spore.deployed = True
    ally.deployed = True
    enemy.deployed = True

    player, enemy_player = _setup_players(spore, [enemy])
    player.army.units.append(ally)
    ally.set_parent_army(player.army)

    source_model = spore.models[0]
    source_model.set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(2.0, 0.0, 0.0, 0.0)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.players = [player, enemy_player]

    applied = {}

    def _apply(self, target_unit, amount, game_map=None):
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        return 0

    spore._apply_mortal_wounds_to_unit = types.MethodType(_apply, spore)
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _die: 6)

    game.event_system.publish("unit_move_ended", unit=ally, action="move")

    assert _find_quarry_request(game) is None
    assert int(applied.get("amount", 0) or 0) == 0
    assert source_model in list(spore.models or [])


def test_floating_death_multi_model_sequences_with_target_decision(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.utility.decision_utils import resolve_decision_command
    from warhammer40k_ai.utility.entity_ids import get_entity_id

    ability_desc = (
        "Each time this unit or an enemy unit ends a move, for each model in this unit that is within 3\" of one or "
        "more enemy units, select one of those enemy units. That model in this unit is destroyed, then roll one D6: "
        "on a 2-5, that enemy unit suffers 1 mortal wound; on a 6, that enemy unit suffers D3 mortal wounds."
    )
    spore = _make_unit("Spore Mines", ability_desc=ability_desc, model_count=2)
    enemy_a = _make_unit("Enemy A", model_count=1)
    enemy_b = _make_unit("Enemy B", model_count=1)
    spore.deployed = True
    enemy_a.deployed = True
    enemy_b.deployed = True

    player, enemy_player = _setup_players(spore, [enemy_a, enemy_b])

    model_a = spore.models[0]
    model_b = spore.models[1]
    model_a._id = "floating-death-model-a"
    model_b._id = "floating-death-model-b"
    model_a.set_location(0.0, 0.0, 0.0, 0.0)
    model_b.set_location(2.2, 2.2, 0.0, 0.0)
    enemy_a.models[0].set_location(2.0, 0.0, 0.0, 0.0)
    enemy_b.models[0].set_location(-2.0, 0.0, 0.0, 0.0)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.players = [player, enemy_player]

    applied_by_target = {}

    def _apply(self, target_unit, amount, game_map=None):
        key = str(get_entity_id(target_unit) or getattr(target_unit, "name", ""))
        applied_by_target[key] = int(applied_by_target.get(key, 0) or 0) + int(amount or 0)
        return 0

    spore._apply_mortal_wounds_to_unit = types.MethodType(_apply, spore)

    rolls = {"D6": [2, 6], "D3": [3]}

    def _fake_get_roll(die):
        return rolls[str(die)].pop(0)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    game.event_system.publish("unit_move_ended", unit=enemy_a, action="move")

    request = _find_quarry_request(game)
    assert request is not None
    assert str((request.context or {}).get("mortal_wounds_kind", "") or "") == "floating_death"
    assert str((request.context or {}).get("model_id", "") or "") == str(get_entity_id(model_a))

    enemy_b_id = str(get_entity_id(enemy_b) or "")
    option_id = None
    for option in list(request.options or []):
        if str((option.payload or {}).get("target_unit_id", "") or "") == enemy_b_id:
            option_id = option.option_id
            break
    assert option_id is not None
    resolve_decision_command(game, request, option_id, player_id=player.id)

    assert _find_quarry_request(game) is None
    assert model_a not in list(spore.models or [])
    assert model_b not in list(spore.models or [])
    assert len(list(spore.models or [])) == 0
    assert int(applied_by_target.get(str(get_entity_id(enemy_b)), 0) or 0) == 1
    assert int(applied_by_target.get(str(get_entity_id(enemy_a)), 0) or 0) == 3


def test_floating_death_mucolid_variant_uses_d6_on_six(monkeypatch):
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game

    ability_desc = (
        "Each time this unit or an enemy unit ends a move, for each model in this unit that is within 3\" of one or "
        "more enemy units, select one of those enemy units. That model in this unit is destroyed, then roll one D6: "
        "on a 2-5, that enemy unit suffers D3 mortal wounds; on a 6, that enemy unit suffers D6 mortal wounds."
    )
    mucolid = _make_unit("Mucolid Spores", ability_desc=ability_desc, model_count=1)
    enemy = _make_unit("Enemy Unit", model_count=1)
    mucolid.deployed = True
    enemy.deployed = True

    player, enemy_player = _setup_players(mucolid, [enemy])

    source_model = mucolid.models[0]
    source_model.set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(2.0, 0.0, 0.0, 0.0)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.players = [player, enemy_player]

    applied = {}

    def _apply(self, target_unit, amount, game_map=None):
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        return 0

    mucolid._apply_mortal_wounds_to_unit = types.MethodType(_apply, mucolid)

    rolls = {"D6": [6, 5]}

    def _fake_get_roll(die):
        return rolls[str(die)].pop(0)

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", _fake_get_roll)

    game.event_system.publish("unit_move_ended", unit=enemy, action="move")

    assert int(applied.get("amount", 0) or 0) == 5
    assert source_model not in list(mucolid.models or [])
    assert len(list(mucolid.models or [])) == 0
