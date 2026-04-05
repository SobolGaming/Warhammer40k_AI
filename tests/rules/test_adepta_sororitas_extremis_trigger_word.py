from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(self, name, *, faction_name="Adepta Sororitas", abilities=None):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "4",
                "Sv": "7",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: arco-flails."
        self.transport = ""


def _make_unit(name, *, faction_name="Adepta Sororitas", abilities=None) -> Unit:
    return Unit(_MockDatasheet(name, faction_name=faction_name, abilities=abilities))


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sororitas_army = Army("Adepta Sororitas", "Detachment")
    sororitas_army.faction_id = "AS"
    enemy_army = Army("Enemy", "Detachment")
    enemy_army.faction_id = "ENEMY"
    sororitas_player = Player("Sororitas", control=PlayerControl.REMOTE, army=sororitas_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sororitas_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.phase = BattleRoundPhases.FIGHT_PHASE
    return game, sororitas_army, enemy_army, sororitas_player, enemy_player


class _MeleeWargear:
    def __init__(self, name: str):
        self.name = name
        norm = str(name or "").strip().lower().replace(" ", "-")
        self._id = f"wg-{norm or 'melee'}"
        self.profiles = {}

    def is_melee(self):
        return True

    def is_ranged(self):
        return False


EXTREMIS_TRIGGER_WORD_ABILITY = {
    "name": "Extremis Trigger Word",
    "description": (
        "Each time this unit is selected to fight, you can choose to invoke its extremis trigger word. "
        "If you do, then until the end of the phase, arco-flails equipped by models in this unit have an "
        "Attacks characteristic of 6 and the [HAZARDOUS] ability."
    ),
    "type": "Datasheet",
    "parameter": "",
}


def _setup_arco_fight_scene():
    game, sororitas_army, enemy_army, sororitas_player, _enemy_player = _build_game()
    arco = _make_unit("Arco-flagellants", abilities=[EXTREMIS_TRIGGER_WORD_ABILITY])
    enemy = _make_unit("Enemy Unit", faction_name="Enemy", abilities=[])
    arco.models[0].wargear = [_MeleeWargear("arco-flails")]
    sororitas_army.add_unit(arco)
    enemy_army.add_unit(enemy)
    arco.deployed = True
    enemy.deployed = True
    game.map.units = [arco, enemy]
    game.rebuild_entity_registry()
    return game, sororitas_player, arco, enemy


def _resolve_yes(game: Game, player_id: str):
    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_CONFIRM_YES_NO
    option_id = None
    for opt in list(request.options or []):
        if bool((opt.payload or {}).get("choice", False)):
            option_id = opt.option_id
            break
    assert option_id is not None
    resolve_decision_command(game, request, option_id, player_id=player_id)


def test_extremis_trigger_word_prompt_and_apply():
    game, sororitas_player, arco, enemy = _setup_arco_fight_scene()

    game._on_fight_unit_selected_extremis_trigger_word(unit=arco, selecting_player=sororitas_player)
    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    assert str((pending[0].context or {}).get("ability", "")) == "extremis_trigger_word"

    _resolve_yes(game, sororitas_player.id)
    assert bool(arco.special_rules.get("extremis_trigger_word_active", False))

    attacks_value, _source = arco.models[0].get_temporary_weapon_attacks_override("arco-flails")
    assert int(attacks_value or 0) == 6
    bonuses = list(arco.models[0].get_temporary_weapon_keyword_bonuses("arco-flails") or [])
    assert any(str(entry.get("keyword", "") or "").strip().upper() == "HAZARDOUS" for entry in bonuses)

    model_bonus = arco.get_model_weapon_keyword_bonuses(
        attack_type="melee",
        model=arco.models[0],
        weapon_name="arco-flails",
        target=enemy,
    )
    assert bool(model_bonus.get("hazardous", False))

    game._on_fight_unit_selected_extremis_trigger_word(unit=arco, selecting_player=sororitas_player)
    assert len(list(game.decision_queue.list() or [])) == 0


def test_extremis_trigger_word_hazardous_bonus_triggers_hazardous_roll(monkeypatch):
    import warhammer40k_ai.units.wargear as wargear_module

    monkeypatch.setattr(wargear_module, "get_roll", lambda _dice: 1)
    game, sororitas_player, arco, enemy = _setup_arco_fight_scene()

    game._on_fight_unit_selected_extremis_trigger_word(unit=arco, selecting_player=sororitas_player)
    _resolve_yes(game, sororitas_player.id)

    parent = SimpleNamespace(name="arco-flails", is_melee=lambda: True, is_ranged=lambda: False)
    profile = WargearProfile(
        profile_name="Melee",
        wargear_data={
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "5",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )

    result = profile.attack(enemy, arco.models[0], game_map=getattr(game, "map", None))
    assert result is not None
    assert int(result.hazardous_roll or 0) == 1
    assert int(result.hazardous_damage or 0) == 3

