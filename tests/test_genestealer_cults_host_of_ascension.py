from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


class _MockDatasheet:
    def __init__(self, name: str, *, faction: str, keywords=None, faction_keywords=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "3",
                "Sv": "5",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = []


def _make_unit(name: str, *, faction: str, faction_keywords: list[str], keywords: list[str]) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction=faction,
            keywords=keywords,
            faction_keywords=faction_keywords,
        )
    )
    model = unit.models[0]
    model.wargear.append(
        SimpleNamespace(
            _id=f"{name}:autopistol",
            name="Autopistol",
            is_ranged=lambda: True,
            is_melee=lambda: False,
            profiles={},
        )
    )
    model.wargear.append(
        SimpleNamespace(
            _id=f"{name}:cult_knife",
            name="Cult Knife",
            is_ranged=lambda: False,
            is_melee=lambda: True,
            profiles={},
        )
    )
    unit.deployed = True
    return unit


def _make_game(detachment_type: str) -> tuple[Game, Player, Player, Unit]:
    gsc_army = Army("Genestealer Cults", detachment_type)
    gsc_army.faction_id = "GC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

    gsc_player = Player("GSC", PlayerControl.LOCAL, army=gsc_army)
    enemy_player = Player("Enemy", PlayerControl.LOCAL, army=enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[gsc_player, enemy_player])
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.turn = 1

    gsc_unit = _make_unit(
        "Neophyte Hybrids",
        faction="Genestealer Cults",
        faction_keywords=["GENESTEALER CULTS"],
        keywords=["INFANTRY"],
    )
    gsc_army.add_unit(gsc_unit)
    game.map.units = [gsc_unit]
    game.rebuild_entity_registry()
    return game, gsc_player, enemy_player, gsc_unit


def _weapon_bonuses(unit: Unit, weapon_name: str, *, attack_type: str) -> dict:
    return unit.get_model_weapon_keyword_bonuses(
        model=unit.models[0],
        weapon_name=weapon_name,
        attack_type=attack_type,
    )


def test_a_perfect_ambush_applies_on_reinforcements_setup() -> None:
    game, _gsc_player, _enemy_player, gsc_unit = _make_game("Host of Ascension")
    game.current_player_index = 0

    game.event_system.publish(
        "unit_set_up",
        unit=gsc_unit,
        set_up_as_reinforcements=True,
    )

    ranged_bonuses = _weapon_bonuses(gsc_unit, "Autopistol", attack_type="ranged")
    assert ranged_bonuses.get("sustained_hits_value", 0) == 1
    assert ranged_bonuses.get("ignores_cover", False) is True

    melee_bonuses = _weapon_bonuses(gsc_unit, "Cult Knife", attack_type="melee")
    assert melee_bonuses.get("sustained_hits_value", 0) == 1
    assert melee_bonuses.get("ignores_cover", False) is True


def test_a_perfect_ambush_expires_at_end_of_owners_next_fight_phase() -> None:
    game, gsc_player, enemy_player, gsc_unit = _make_game("Host of Ascension")
    game.current_player_index = 1

    game.event_system.publish(
        "unit_set_up",
        unit=gsc_unit,
        set_up_as_reinforcements=True,
    )

    before_cleanup = _weapon_bonuses(gsc_unit, "Autopistol", attack_type="ranged")
    assert before_cleanup.get("sustained_hits_value", 0) == 1
    assert before_cleanup.get("ignores_cover", False) is True

    game._on_phase_end_cleanup(player=enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)
    after_enemy_fight = _weapon_bonuses(gsc_unit, "Autopistol", attack_type="ranged")
    assert after_enemy_fight.get("sustained_hits_value", 0) == 1
    assert after_enemy_fight.get("ignores_cover", False) is True

    game._on_phase_end_cleanup(player=gsc_player, phase=BattleRoundPhases.FIGHT_PHASE)
    after_owner_fight = _weapon_bonuses(gsc_unit, "Autopistol", attack_type="ranged")
    assert after_owner_fight.get("sustained_hits_value", 0) == 0
    assert after_owner_fight.get("ignores_cover", False) is False
