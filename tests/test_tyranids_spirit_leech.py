from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit


SPIRIT_LEECH_RULE = (
    'While an enemy unit is within 6" of this unit, if this unit contains a Neurothrope, each time that enemy unit '
    "fails a Battle-shock test, it suffers D3 mortal wounds and one model in this unit regains up to D3 lost wounds."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        model_count: int = 1,
        abilities=None,
        faction_name: str = "Tyranids",
        wounds: str = "4",
        leadership: str = "7",
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model(s)", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "5",
                "Sv": "4",
                "W": str(wounds),
                "Ld": str(leadership),
                "OC": "1",
                "base_size": "40mm",
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


def _make_unit(name: str, *, abilities=None, wounds: str = "4") -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            model_count=1,
            abilities=abilities,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tyr_army = Army("Tyranids", "Other")
    tyr_army.faction_id = "TYR"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tyr_player = Player("Tyranids", control=PlayerControl.REMOTE, army=tyr_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tyr_player)
    game.add_player(enemy_player)
    return game, tyr_army, enemy_army


def _spirit_leech_ability():
    return [
        {
            "name": "Spirit Leech (Aura, Psychic)",
            "description": SPIRIT_LEECH_RULE,
            "type": "Datasheet",
            "parameter": "",
        }
    ]


def test_spirit_leech_specs_parse():
    source = _make_unit("Zoanthropes", abilities=_spirit_leech_ability())

    specs = source.unit_enemy_failed_battleshock_mortal_heal_aura_specs()

    assert len(specs) == 1
    spec = specs[0]
    assert str(spec.get("source", "") or "") == "Spirit Leech (Aura, Psychic)"
    assert int(spec.get("range", 0) or 0) == 6
    assert str(spec.get("required_model_name", "") or "").lower() == "neurothrope"
    assert str(spec.get("mortal_wounds_roll", "") or "").upper() == "D3"
    assert str(spec.get("heal_roll", "") or "").upper() == "D3"


def test_spirit_leech_applies_mortals_and_heal_on_failed_battleshock():
    game, tyr_army, enemy_army = _build_game()

    source = _make_unit("Zoanthropes", abilities=_spirit_leech_ability())
    source_model = source.models[0]
    source_model.name = "Neurothrope"
    source_model.set_location(0.0, 0.0, 0.0, 0.0)
    source.deployed = True
    source.reserve_status = "deployed"

    target = _make_unit("Enemy Infantry", wounds="5")
    target_model = target.models[0]
    target_model.set_location(5.0, 0.0, 0.0, 0.0)
    target.deployed = True
    target.reserve_status = "deployed"

    base_wounds = int(getattr(source_model, "_base_wounds", getattr(source_model, "wounds", 0)) or 0)
    source_model.wounds = int(max(1, int(source_model.wounds) - 2))
    wounds_before = int(source_model.wounds or 0)

    applied: dict[str, int] = {}

    def _apply_mortals(self, _unit, amount, game_map=None):
        applied["mw"] = int(applied.get("mw", 0) + int(amount or 0))

    target._apply_mortal_wounds_to_unit = _apply_mortals.__get__(target, Unit)

    tyr_army.add_unit(source)
    enemy_army.add_unit(target)
    game.map.units = [source, target]

    with patch("warhammer40k_ai.engine.game.get_roll", side_effect=[2, 3]):
        game._on_battle_shock_test_resolved_enemy_failed_battleshock_aura(unit=target, passed=False)

    assert int(applied.get("mw", 0) or 0) == 2
    expected_healed = min(3, max(0, int(base_wounds - wounds_before)))
    assert int(source_model.wounds or 0) == int(wounds_before + expected_healed)


def test_spirit_leech_requires_neurothrope_and_failed_test():
    game, tyr_army, enemy_army = _build_game()

    source = _make_unit("Zoanthropes", abilities=_spirit_leech_ability())
    source_model = source.models[0]
    source_model.name = "Zoanthrope"
    source_model.set_location(0.0, 0.0, 0.0, 0.0)
    source.deployed = True
    source.reserve_status = "deployed"
    wounds_before = int(source_model.wounds or 0)

    target = _make_unit("Enemy Infantry", wounds="5")
    target_model = target.models[0]
    target_model.set_location(5.0, 0.0, 0.0, 0.0)
    target.deployed = True
    target.reserve_status = "deployed"

    applied: dict[str, int] = {}

    def _apply_mortals(self, _unit, amount, game_map=None):
        applied["mw"] = int(applied.get("mw", 0) + int(amount or 0))

    target._apply_mortal_wounds_to_unit = _apply_mortals.__get__(target, Unit)

    tyr_army.add_unit(source)
    enemy_army.add_unit(target)
    game.map.units = [source, target]

    with patch("warhammer40k_ai.engine.game.get_roll", side_effect=AssertionError("unexpected roll")):
        game._on_battle_shock_test_resolved_enemy_failed_battleshock_aura(unit=target, passed=False)
        game._on_battle_shock_test_resolved_enemy_failed_battleshock_aura(unit=target, passed=True)

    assert int(applied.get("mw", 0) or 0) == 0
    assert int(source_model.wounds or 0) == int(wounds_before)
