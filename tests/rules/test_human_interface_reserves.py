from types import SimpleNamespace

from warhammer40k_ai.UI.human_interface import HumanUIInterface


def test_declare_reserves_defaults_to_deploy_unless_forced() -> None:
    ui = HumanUIInterface.__new__(HumanUIInterface)
    forced = SimpleNamespace(id="u_forced", must_start_in_reserves=lambda: True)
    normal = SimpleNamespace(id="u_normal", must_start_in_reserves=lambda: False)
    army = SimpleNamespace(units=[forced, normal])
    player = SimpleNamespace(get_army=lambda: army)

    decisions = ui.declare_reserves(player)

    assert decisions == {
        "u_forced": "reserves",
        "u_normal": "deploy",
    }
