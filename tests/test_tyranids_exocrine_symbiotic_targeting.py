from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units import wargear as wargear_mod
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


SYMBIOTIC_TARGETING_TEXT = (
    "In your Shooting phase, after this model has shot, select one enemy unit hit by one or more of those attacks. "
    "Until the end of the phase, each time a friendly TYRANIDS model makes an attack that targets that unit, "
    "re-roll a Hit roll of 1."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        model_count: int = 1,
        abilities=None,
        keywords=None,
        faction_keywords=None,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Tyranids"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model(s)", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "8",
                "T": "8",
                "Sv": "3",
                "W": "8",
                "Ld": "7",
                "OC": "2",
                "base_size": "60mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
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
        ),
        quantity=1,
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army("Tyranids", detachment_type="Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    tyr_player = Player("Tyr", PlayerControl.LOCAL, army=tyr_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    return game, tyr_player, enemy_player, tyr_army, enemy_army


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


def _test_profile():
    parent = SimpleNamespace(name="Test Bio-weapon", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_symbiotic_targeting_parses_post_shoot_hit_reroll_spec():
    exocrine = _make_unit(
        "Exocrine",
        abilities=[
            {
                "name": "Symbiotic Targeting",
                "description": SYMBIOTIC_TARGETING_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["MONSTER"],
        faction_keywords=["TYRANIDS"],
    )

    specs = exocrine.unit_post_shoot_keyword_hit_reroll_ones_specs()
    assert len(specs) == 1
    assert str(specs[0].get("keyword_phrase", "")) == "tyranids"


def test_symbiotic_targeting_marks_hit_unit_for_tyranid_hit_reroll_ones():
    game, tyr_player, enemy_player, tyr_army, enemy_army = _build_game()
    exocrine = _make_unit(
        "Exocrine",
        abilities=[
            {
                "name": "Symbiotic Targeting",
                "description": SYMBIOTIC_TARGETING_TEXT,
                "type": "Datasheet",
                "parameter": "",
            }
        ],
        keywords=["MONSTER"],
        faction_keywords=["TYRANIDS"],
    )
    ally = _make_unit(
        "Termagants",
        keywords=["INFANTRY"],
        faction_keywords=["TYRANIDS"],
    )
    enemy_target = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )

    tyr_army.add_unit(exocrine)
    tyr_army.add_unit(ally)
    enemy_army.add_unit(enemy_target)
    game.map.units = [exocrine, ally, enemy_target]
    game.rebuild_entity_registry()

    game._on_unit_shooting_resolved_post_shoot_keyword_hit_reroll_ones(
        attacker_unit=exocrine,
        hits_by_target={enemy_target: 1},
    )
    req = next(iter(list(game.decision_queue.list() or [])), None)
    assert req is not None
    assert req.decision_type == DECISION_CHOOSE_QUARRY

    resolve_decision_command(game, req, req.options[0].option_id, player_id=tyr_player.id)

    profile = _test_profile()
    rolls = iter([1, 5])
    original_roll = wargear_mod.get_roll
    wargear_mod.get_roll = lambda _d: next(rolls)
    try:
        result = profile._hit_target_with_tracking(
            enemy_target,
            ally.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )
    finally:
        wargear_mod.get_roll = original_roll

    assert int(result.get("roll", 0) or 0) == 5
    assert int(result.get("reroll_of_one", 0) or 0) == 1

    game.phase = BattleRoundPhases.FIGHT_PHASE
    rolls = iter([1])
    original_roll = wargear_mod.get_roll
    wargear_mod.get_roll = lambda _d: next(rolls)
    try:
        result_out_of_phase = profile._hit_target_with_tracking(
            enemy_target,
            ally.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )
    finally:
        wargear_mod.get_roll = original_roll

    assert int(result_out_of_phase.get("reroll_of_one", 0) or 0) == 0
