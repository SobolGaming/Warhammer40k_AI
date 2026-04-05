from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.UI.dialogs.dialog_manager import DialogManager


class _DummyDialog:
    def __init__(self):
        self.visible = False

    def handle_event(self, _event):
        return False

    def draw(self, _screen):
        return None


def _build_game_view():
    return SimpleNamespace(
        ui_interface=None,
        yes_no_dialog=None,
        frenzy_choice_dialog=None,
        dice_roll_dialog=None,
        blessings_of_khorne_dialog=None,
        blood_tithe_dialog=None,
        voice_of_command_dialog=None,
        gate_of_infinity_dialog=None,
        secondary_discard_dialog=None,
        hazard_objective_select_dialog=None,
        battlefield_point_pick_dialog=None,
        movement_choice_dialog=_DummyDialog(),
        individual_model_movement_dialog=_DummyDialog(),
        coherency_violation_dialog=None,
        weapon_choice_dialog=None,
        shooting_declaration_dialog=None,
        charge_declaration_dialog=None,
        melee_weapon_declaration_dialog=None,
        melee_target_allocation_dialog=None,
        melee_weapon_target_allocation_dialog=None,
        melee_attack_split_dialog=None,
        fight_target_selection_dialog=None,
        exploding_horrors_model_selection_dialog=None,
        target_model_selection_dialog=None,
        firing_deck_dialog=None,
        transport_embark_dialog=None,
        transport_disembark_dialog=None,
        transport_assignment_dialog=None,
        player_color_picker_dialog=None,
        reserves_allocation_dialog=None,
        precision_allocation_dialog=None,
        damage_allocation_dialog=None,
        mission_selection_dialog=None,
        leader_attachment_dialog=None,
        overwatch_shooter_dialog=_DummyDialog(),
        battle_focus_dialog=_DummyDialog(),
    )


def test_overwatch_priority_over_movement_when_activated_same_frame() -> None:
    game_view = _build_game_view()
    manager = DialogManager(game_view)

    game_view.individual_model_movement_dialog.visible = True
    game_view.overwatch_shooter_dialog.visible = True

    assert manager.top() is game_view.overwatch_shooter_dialog


def test_battle_focus_priority_over_movement_when_activated_same_frame() -> None:
    game_view = _build_game_view()
    manager = DialogManager(game_view)

    game_view.individual_model_movement_dialog.visible = True
    game_view.battle_focus_dialog.visible = True

    assert manager.top() is game_view.battle_focus_dialog
