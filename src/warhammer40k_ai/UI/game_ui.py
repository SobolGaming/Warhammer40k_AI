import pygame
import math
import re
from typing import Optional, Tuple, Dict, List, Protocol, Callable, Any
from types import SimpleNamespace
from abc import ABC, abstractmethod
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.utility.model_base import Base, BaseType
from warhammer40k_ai.roster.player import Player
from warhammer40k_ai.utility.dice import get_roll
from warhammer40k_ai.utility.ability_support import ABILITY_BLESSINGS_OF_KHORNE, army_has_ability_id
from warhammer40k_ai.utility.entity_ids import get_entity_id

# Import UI panels
from .panels.roster_pane import RosterPane
from .panels.stratagem_pane import StratagemPane
from .panels.info_pane import InfoPane
from .panels.unit_detail_panel import UnitDetailPanel
from .panels.rule_detail_panel import RuleDetailPanel
from .panels.popup_overlays import PopupOverlayRenderer
from .rendering.battlefield_renderer import draw_battlefield, draw_terrain_feature
from .rendering.board_renderer import draw_deployment_zones, draw_objective
from .rendering.unit_renderer import draw_units
from .rendering.range_renderer import draw_individual_model_movement_range, draw_weapon_ranges
from .phases.phase_manager import PhaseManager, PreBattlePhaseHandler
from .layout.hud_layout import draw_bottom_logs_pane, draw_stratagem_panes, draw_top_status_pane
from .ui_constants import (
    TILE_SIZE,
    BATTLEFIELD_WIDTH_INCHES,
    BATTLEFIELD_HEIGHT_INCHES,
    BATTLEFIELD_WIDTH,
    BATTLEFIELD_HEIGHT,
    CULT_AMBUSH_MARKER_RADIUS_INCHES,
    WHITE,
    BLACK,
    GREY,
    LIGHT_GREY,
    DARK_GREY,
    GREEN,
    BLUE,
    RED,
    PURPLE,
    SUPPORTED_ARMY_RULES,
    SUPPORTED_DETACHMENT_RULES,
    PANEL_BG,
    PANEL_BORDER,
    BUTTON_BG,
    BUTTON_HOVER,
    BUTTON_SELECTED,
    BUTTON_DISABLED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_ACCENT,
    TEXT_DISABLED,
    HEALTH_GOOD,
    HEALTH_DAMAGED,
    HEALTH_CRITICAL,
    RESERVES_BUTTON_BG,
    RESERVES_BUTTON_HOVER,
    STRATEGIC_RESERVES_BG,
    STRATEGIC_RESERVES_HOVER,
    STRATEGIC_BUTTON_BG,
    DEPLOY_BUTTON_BG,
    DEPLOY_BUTTON_HOVER,
    GameState,
    MIN_ZOOM,
    MAX_ZOOM,
    ZOOM_SPEED,
    PAN_SPEED,
    MOUSE_PAN_SPEED,
    ROSTER_PANE_WIDTH,
    ROSTER_PANE_BUTTON_HEIGHT,
    ROSTER_FONT_SIZE,
    ROSTER_LINE_HEIGHT,
    INFO_PANE_HEIGHT,
    STRATAGEM_PANE_WIDTH,
    FONT_LARGE,
    FONT_MEDIUM,
    FONT_SMALL,
    FONT_TINY,
    ICON_SCALE_FACTOR,
    ICON_MIN_SIZE,
    ICON_OVERLAY_ALPHA,
    UNIT_COLOR_VARIATIONS,
)

from .dialogs.secondary_discard_dialog import SecondaryDiscardDialog
from .dialogs.overwatch_shooter_dialog import OverwatchShooterDialog
from .dialogs.battlefield_point_pick_dialog import BattlefieldPointPickDialog

class GameView:
    def __init__(self, screen, env, game, game_map, player1, player2, ui_interface=None):
        self.screen = screen
        self.env = env
        self.game = game
        self.game_map = game_map
        self.player1 = player1
        self.player2 = player2
        self.selected_unit = None
        self.dragging_unit = None
        self.dragging = False
        self.drag_offset = (0, 0)
        self.zoom_level = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.detailed_unit = None
        self.detail_panel_pos = (0, 0)
        self.unit_detail_panel = UnitDetailPanel()
        self.rule_detail_panel = RuleDetailPanel()
        self._rule_panel_state = None
        self._rule_support_cache = {}
        self._waha_helper = None
        
        # UI scaling factor removed - rendering uses fixed inch grid with zoom only
        
        # UI interface for human player interaction
        self.ui_interface = ui_interface

        # Set reference back to game view in UI interface for dialog access
        if ui_interface:
            ui_interface.game_view = self

        # Central dialog manager (modal stack)
        from .dialogs import DialogManager
        self.dialog_manager = DialogManager(self)

        # Wire combat UI hooks into the Map (used by core combat code like WargearProfile.attack()).
        try:
            if self.game and getattr(self.game, "map", None) is not None:
                self.game.map.precision_allocation_provider = self._precision_allocation_provider
                self.game.map.damage_allocation_provider = self._damage_allocation_provider
                self.game.map.hazardous_allocation_provider = self._hazardous_allocation_provider
                self.game.map.roll_reroll_provider = self._roll_reroll_provider
                self.game.map.reanimation_allocation_provider = self._reanimation_allocation_provider
                self.game.map.miracle_dice_provider = self._miracle_dice_provider
                self.game.map.aspect_shrine_provider = self._aspect_shrine_provider
        except Exception:
            pass
        try:
            if self.game_map is not None:
                self.game_map.precision_allocation_provider = self._precision_allocation_provider
                self.game_map.damage_allocation_provider = self._damage_allocation_provider
                self.game_map.hazardous_allocation_provider = self._hazardous_allocation_provider
                self.game_map.roll_reroll_provider = self._roll_reroll_provider
                self.game_map.reanimation_allocation_provider = self._reanimation_allocation_provider
                self.game_map.miracle_dice_provider = self._miracle_dice_provider
                self.game_map.aspect_shrine_provider = self._aspect_shrine_provider
        except Exception:
            pass
        
        # Phase-based event handling system
        self.phase_manager = PhaseManager(self)
        
        # Mouse panning support
        self.panning = False
        self.pan_start_pos = (0, 0)
        self.pan_start_offset = (0, 0)

        # Create roster and stratagem panes with reference to all units for color correlation
        # Fixed panes; battlefield viewport derived from actual screen size
        scaled_roster_width = ROSTER_PANE_WIDTH
        scaled_stratagem_width = STRATAGEM_PANE_WIDTH
        scaled_info_height = INFO_PANE_HEIGHT
        screen_width, screen_height = self.screen.get_size()
        scaled_battlefield_width = max(100, screen_width - 2 * (scaled_roster_width + scaled_stratagem_width))
        scaled_battlefield_height = max(100, screen_height - scaled_info_height)

        # Roster panes should not overlap the bottom logs pane; limit to battlefield height
        roster_pane_height = scaled_battlefield_height
        player1_units = player1.get_army().units if player1.get_army() else []
        player2_units = player2.get_army().units if player2.get_army() else []

        self.scaled_stratagem_width = scaled_stratagem_width
        self.battlefield_left = scaled_stratagem_width + scaled_roster_width
        self.battlefield_right = self.battlefield_left + scaled_battlefield_width

        self.left_stratagem_pane = StratagemPane(0, 0, scaled_stratagem_width, roster_pane_height,
                                                 f"Player 1 ({player1.name})")
        self.right_stratagem_pane = StratagemPane(self.battlefield_right + scaled_roster_width, 0,
                                                  scaled_stratagem_width, roster_pane_height,
                                                  f"Player 2 ({player2.name})")

        self.left_roster_pane = RosterPane(scaled_stratagem_width, 0, scaled_roster_width, roster_pane_height,
                                           player1_units, f"Player 1 ({player1.name})")
        self.right_roster_pane = RosterPane(self.battlefield_right, 0, scaled_roster_width,
                                            roster_pane_height, player2_units,
                                            f"Player 2 ({player2.name})")
        
        # Store scaled dimensions for mouse coordinate conversion
        self.scaled_roster_width = scaled_roster_width
        self.scaled_battlefield_width = scaled_battlefield_width
        self.scaled_battlefield_height = scaled_battlefield_height
        self.scaled_info_height = scaled_info_height
        
        # Pass all units to roster panes for color correlation
        all_units = player1_units + player2_units
        self.left_roster_pane.all_units = all_units
        self.right_roster_pane.all_units = all_units
        self.left_stratagem_pane.player = self.player1
        self.right_stratagem_pane.player = self.player2
        
        # Set game_view reference in roster panes for deployment dialog
        self.left_roster_pane.game_view = self
        self.right_roster_pane.game_view = self
        
        # Position InfoPane between roster panes and below battlefield
        self.info_pane = InfoPane(self.battlefield_left, scaled_battlefield_height,
                                  scaled_battlefield_width, scaled_info_height, self.selected_unit)
        
        # Stratagem interaction dialogs
        screen_width, screen_height = self.screen.get_size()
        # Generic Yes/No prompt dialog (used for optional abilities, confirmations, etc.)
        from .dialogs import YesNoDialog, FrenzyChoiceDialog
        self.yes_no_dialog = YesNoDialog(screen_width, screen_height)
        self.frenzy_choice_dialog = FrenzyChoiceDialog(screen_width, screen_height)
        self.cult_ambush_point_dialog = BattlefieldPointPickDialog(screen_width, screen_height)
        self.secondary_discard_dialog = SecondaryDiscardDialog(screen_width, screen_height)
        self.overwatch_shooter_dialog = OverwatchShooterDialog(screen_width, screen_height)
        self.battle_focus_dialog = OverwatchShooterDialog(screen_width, screen_height)
        # Blessings of Khorne dialog (lazy-create only if needed)
        self.blessings_of_khorne_dialog = None
        self.blood_tithe_dialog = None
        self.templar_vows_dialog = None
        self.shadow_form_dialog = None
        self.harbingers_of_dread_dialog = None
        self.doctrina_imperatives_dialog = None
        self.combat_doctrines_dialog = None
        self.combat_drugs_dialog = None
        self.voice_of_command_dialog = None
        self.voice_of_command_officer_dialog = None
        self.voice_of_command_target_dialog = None
        self.gate_of_infinity_dialog = None
        self.dark_pacts_dialog = None
        self.pledge_selection_dialog = None
        self.martial_katah_dialog = None
        self.cabal_ritual_dialog = None
        self.cabal_caster_dialog = None
        self.cabal_target_dialog = None
        # Stratagem interaction helpers
        def _resolve_unit_selection_dialog(
            *,
            player,
            candidates,
            on_chosen,
            decision_type: str,
            prompt: str,
            title: str | None = None,
            subtitle: str | None = None,
            enemy_unit=None,
            dialog=None,
            allow_skip: bool = True,
        ):
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.decision_utils import resolve_decision_value
            from ..utility.entity_ids import get_entity_id
            from .decision_ui_utils import option_id_for_action

            units = list(candidates or [])
            if not units:
                on_chosen(None)
                return
            dlg = dialog or self.overwatch_shooter_dialog
            if dlg is None:
                on_chosen(units[0] if units else None)
                return

            options = []
            for unit in units:
                try:
                    label = str(getattr(unit, "name", "Unit") or "Unit")
                except Exception:
                    label = "Unit"
                options.append(
                    DecisionOption.create(
                        label,
                        payload={"unit_id": get_entity_id(unit)},
                    )
                )
            if allow_skip:
                options.append(DecisionOption.create("Skip", payload={"action": "skip"}))

            ctx = {}
            if enemy_unit is not None:
                try:
                    ctx["enemy_unit_id"] = get_entity_id(enemy_unit)
                except Exception:
                    pass

            req = DecisionRequest.create(
                decision_type,
                prompt,
                player_id=getattr(player, "id", None),
                options=options,
                context=ctx,
            )
            self.game.request_decision(req)

            def _on_confirm(option_id: str):
                value, apply = resolve_decision_value(self.game, req, option_id)
                if apply is None or not getattr(apply, "ok", False):
                    on_chosen(None)
                else:
                    on_chosen(value)
                try:
                    dlg.hide()
                except Exception:
                    pass

            def _on_cancel():
                if allow_skip:
                    option_id = option_id_for_action(req, "skip")
                    if option_id:
                        resolve_decision_value(self.game, req, option_id, result_payload={"skipped": True})
                on_chosen(None)
                try:
                    dlg.hide()
                except Exception:
                    pass

            dlg.show(
                units,
                enemy_unit,
                _on_confirm,
                title=title,
                subtitle=subtitle,
                on_cancel=_on_cancel,
                decision_request=req,
            )
            try:
                self.dialog_manager.open(dlg, modal=True)
            except Exception:
                pass

        self._resolve_unit_selection_dialog = _resolve_unit_selection_dialog

        def _request_secondary_discard(player, game, on_chosen):
            from ..engine.decision_kinds import DECISION_DISCARD_SECONDARY
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.decision_utils import resolve_decision_value

            cards = list(getattr(player, 'active_secondaries', []) or [])
            if not cards:
                on_chosen(None)
                return
            options = []
            for card in cards:
                try:
                    name = str(getattr(card, "name", "Secondary") or "Secondary")
                except Exception:
                    name = "Secondary"
                options.append(DecisionOption.create(name, payload={"card_name": name}))
            req = DecisionRequest.create(
                DECISION_DISCARD_SECONDARY,
                "Select a secondary to discard.",
                player_id=getattr(player, "id", None),
                options=options,
            )
            self.game.request_decision(req)

            def _on_confirm(option_id: str):
                value, _apply = resolve_decision_value(self.game, req, option_id)
                on_chosen(value)
                try:
                    self.secondary_discard_dialog.hide()
                except Exception:
                    pass

            self.secondary_discard_dialog.show(cards, _on_confirm, decision_request=req)
            try:
                self.dialog_manager.open(self.secondary_discard_dialog, modal=True)
            except Exception:
                pass
        self._request_secondary_discard = _request_secondary_discard

        def _request_overwatch_shooter(player, game, enemy_unit, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            # Build candidate list as StratagemManager did, but UI-driven
            candidates = []
            for unit in player.get_army().units or []:
                if not unit.is_alive() or not unit.deployed:
                    continue
                if getattr(unit, 'is_titanic', False):
                    continue
                dist = self.game.map.get_distance_between_units(unit, enemy_unit)
                if dist is not None and dist <= 24.0:
                    candidates.append(unit)
            if not candidates:
                on_chosen(None)
                return
            enemy_name = getattr(enemy_unit, "name", "enemy unit") if enemy_unit else "enemy unit"
            _resolve_unit_selection_dialog(
                player=player,
                candidates=candidates,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Overwatch shooter.",
                title="Select Overwatch Shooter",
                subtitle=f"Choose a unit to fire at {enemy_name}",
                enemy_unit=enemy_unit,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_overwatch_shooter = _request_overwatch_shooter

        def _request_heroic_intervention_unit(player, game, enemy_unit, candidates, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                if enemy_unit is None:
                    on_chosen(None)
                    return
                try:
                    from ..rules.stratagems import _unit_cannot_be_target_of_stratagem
                except Exception:
                    _unit_cannot_be_target_of_stratagem = None
                for unit in player.get_army().units or []:
                    if not unit.is_alive() or not unit.deployed:
                        continue
                    try:
                        if unit.has_keyword("Vehicle") and not unit.has_keyword("Walker"):
                            continue
                    except Exception:
                        pass
                    if callable(_unit_cannot_be_target_of_stratagem) and _unit_cannot_be_target_of_stratagem(unit):
                        continue
                    dist = None
                    try:
                        dist = self.game.map.get_distance_between_units(unit, enemy_unit)
                    except Exception:
                        dist = None
                    if dist is None or dist > 6.0:
                        continue
                    try:
                        if not unit.can_declare_charge_against(enemy_unit, game, out_of_turn=True):
                            continue
                    except Exception:
                        continue
                    cand.append(unit)
            if not cand:
                on_chosen(None)
                return
            enemy_name = getattr(enemy_unit, "name", "enemy unit") if enemy_unit else "enemy unit"
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Heroic Intervention unit.",
                title="Select Heroic Intervention Unit",
                subtitle=f"Charge into {enemy_name} (within 6\")",
                enemy_unit=enemy_unit,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_heroic_intervention_unit = _request_heroic_intervention_unit

        def _request_rapid_ingress_unit(player, game, candidates, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            # Candidates are the units in reserves that can arrive this battle round
            cand = list(candidates or [])
            if not cand:
                # Fallback: compute from game state
                try:
                    cand = list(game.get_units_that_can_arrive_from_reserves(player))
                except Exception:
                    cand = []
            if not cand:
                on_chosen(None)
                return
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Rapid Ingress unit.",
                title="Select Rapid Ingress Unit",
                subtitle="Choose a unit in Reserves to arrive now",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_rapid_ingress_unit = _request_rapid_ingress_unit

        def _request_counter_offensive_unit(player, game, candidates, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                try:
                    cand = list(game.get_eligible_fighting_units(player))
                except Exception:
                    cand = []
            try:
                fight_mgr = getattr(game, "fight_phase_manager", None)
                fought = getattr(fight_mgr, "fought_units", set()) if fight_mgr else set()
                cand = [u for u in cand if u not in fought]
            except Exception:
                pass
            if not cand:
                on_chosen(None)
                return
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Counter-Offensive unit.",
                title="Select Counter-Offensive Unit",
                subtitle="Choose a unit to fight next",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_counter_offensive_unit = _request_counter_offensive_unit

        def _request_hack_and_slash_unit(player, game, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = []
            try:
                from ..rules.stratagems import _unit_cannot_be_target_of_stratagem
            except Exception:
                _unit_cannot_be_target_of_stratagem = None
            try:
                army = player.get_army()
                we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
                if we_mgr is None or not getattr(we_mgr, "is_berzerker_warband", lambda: False)():
                    on_chosen(None)
                    return
            except Exception:
                on_chosen(None)
                return
            for unit in player.get_army().units or []:
                try:
                    if not unit.is_alive() or not unit.deployed:
                        continue
                    if callable(_unit_cannot_be_target_of_stratagem) and _unit_cannot_be_target_of_stratagem(unit):
                        continue
                    if not (hasattr(unit, "has_any_keyword") and unit.has_any_keyword("WORLD EATERS")):
                        continue
                    charged = bool(getattr(getattr(unit, "round_state", None), "charged_this_round", False))
                    if not charged:
                        continue
                    if bool(getattr(getattr(unit, "round_state", None), "fought_this_phase", False)):
                        continue
                    cand.append(unit)
                except Exception:
                    continue
            if not cand:
                on_chosen(None)
                return
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Hack and Slash unit.",
                title="Select Hack and Slash Unit",
                subtitle="Charged this turn; has not fought",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_hack_and_slash_unit = _request_hack_and_slash_unit

        def _request_frenzied_resilience_unit(player, game, candidates, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                on_chosen(None)
                return
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Frenzied Resilience unit.",
                title="Select Frenzied Resilience Unit",
                subtitle="Targeted by enemy in Fight phase",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_frenzied_resilience_unit = _request_frenzied_resilience_unit

        def _request_cruel_bladesman_unit(player, game, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = []
            try:
                from ..rules.stratagems import _unit_cannot_be_target_of_stratagem
            except Exception:
                _unit_cannot_be_target_of_stratagem = None
            try:
                army = player.get_army()
                mgr = getattr(army, "emperors_children", None) if army is not None else None
                if mgr is None or not getattr(mgr, "is_peerless_bladesmen", lambda: False)():
                    on_chosen(None)
                    return
            except Exception:
                on_chosen(None)
                return
            seen = set()
            for unit in list(getattr(army, "units", []) or []):
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                if root is None:
                    continue
                uid = get_entity_id(root)
                if uid in seen:
                    continue
                seen.add(uid)
                try:
                    if not root.is_alive() or not getattr(root, "deployed", False):
                        continue
                except Exception:
                    continue
                try:
                    if getattr(root, "is_in_reserves", lambda: False)():
                        continue
                except Exception:
                    continue
                if callable(_unit_cannot_be_target_of_stratagem) and _unit_cannot_be_target_of_stratagem(root):
                    continue
                try:
                    if not mgr.is_emperors_children_unit(root):
                        continue
                except Exception:
                    continue
                charged = bool(getattr(getattr(root, "round_state", None), "charged_this_round", False))
                if not charged:
                    continue
                if bool(getattr(getattr(root, "round_state", None), "fought_this_phase", False)):
                    continue
                cand.append(root)
            if not cand:
                on_chosen(None)
                return
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Cruel Bladesman unit.",
                title="Select Cruel Bladesman Unit",
                subtitle="Charged this turn; has not fought",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_cruel_bladesman_unit = _request_cruel_bladesman_unit

        def _request_death_ecstasy_unit(player, game, candidates, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                on_chosen(None)
                return
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Death Ecstasy unit.",
                title="Select Death Ecstasy Unit",
                subtitle="Targeted by enemy in Fight phase",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_death_ecstasy_unit = _request_death_ecstasy_unit

        def _request_terrifying_spectacle_unit(player, game, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = []
            try:
                from ..rules.stratagems import _unit_cannot_be_target_of_stratagem
            except Exception:
                _unit_cannot_be_target_of_stratagem = None
            try:
                army = player.get_army()
                mgr = getattr(army, "emperors_children", None) if army is not None else None
                if mgr is None or not getattr(mgr, "is_peerless_bladesmen", lambda: False)():
                    on_chosen(None)
                    return
            except Exception:
                on_chosen(None)
                return
            seen = set()
            for unit in list(getattr(army, "units", []) or []):
                try:
                    root = unit.get_attached_unit_root()
                except Exception:
                    root = unit
                if root is None:
                    continue
                uid = get_entity_id(root)
                if uid in seen:
                    continue
                seen.add(uid)
                try:
                    if not root.is_alive() or not getattr(root, "deployed", False):
                        continue
                except Exception:
                    continue
                try:
                    if getattr(root, "is_in_reserves", lambda: False)():
                        continue
                except Exception:
                    continue
                if callable(_unit_cannot_be_target_of_stratagem) and _unit_cannot_be_target_of_stratagem(root):
                    continue
                try:
                    if not mgr.is_emperors_children_unit(root):
                        continue
                except Exception:
                    continue
                sr = getattr(root, "special_rules", None)
                if not isinstance(sr, dict):
                    continue
                if not sr.get("ec_last_turn_charged", False):
                    continue
                if not sr.get("ec_last_turn_destroyed_enemy_in_fight", False):
                    continue
                cand.append(root)
            if not cand:
                on_chosen(None)
                return
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Terrifying Spectacle unit.",
                title="Select Terrifying Spectacle Unit",
                subtitle="Charged last turn and destroyed an enemy unit",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_terrifying_spectacle_unit = _request_terrifying_spectacle_unit

        def _request_cut_down_the_weak_unit(player, game, candidates, enemy_unit, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                on_chosen(None)
                return
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Cut Down the Weak unit.",
                title="Select Cut Down the Weak Unit",
                subtitle="Within 6\" of the enemy that Fell Back",
                enemy_unit=enemy_unit,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_cut_down_the_weak_unit = _request_cut_down_the_weak_unit

        def _request_murder_call_unit(player, game, candidates, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                try:
                    from ..rules.stratagems import _unit_cannot_be_target_of_stratagem
                except Exception:
                    _unit_cannot_be_target_of_stratagem = None
                try:
                    army = player.get_army()
                    we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
                    if we_mgr is None or not getattr(we_mgr, "is_khorne_daemonkin", lambda: False)():
                        on_chosen(None)
                        return
                except Exception:
                    on_chosen(None)
                    return
                game_map = getattr(game, "map", None)
                if game_map is None:
                    on_chosen(None)
                    return
                seen = set()
                for unit in player.get_army().units or []:
                    try:
                        root = unit.get_attached_unit_root()
                    except Exception:
                        root = unit
                    if root is None:
                        continue
                    try:
                        uid = get_entity_id(root)
                    except Exception:
                        continue
                    if uid in seen:
                        continue
                    seen.add(uid)
                    try:
                        if not root.is_alive():
                            continue
                    except Exception:
                        pass
                    try:
                        if not getattr(root, "deployed", False):
                            continue
                    except Exception:
                        continue
                    try:
                        if getattr(root, "is_in_reserves", lambda: False)():
                            continue
                    except Exception:
                        pass
                    try:
                        if not we_mgr.unit_is_blood_legions(root):
                            continue
                    except Exception:
                        continue
                    if callable(_unit_cannot_be_target_of_stratagem) and _unit_cannot_be_target_of_stratagem(root):
                        continue
                    try:
                        engaged = False
                        for enemy in list(game_map.get_enemy_units(root) or []):
                            if not getattr(enemy, "is_alive", lambda: True)():
                                continue
                            if not getattr(enemy, "deployed", True):
                                continue
                            if game_map.is_within_engagement_range(root, enemy):
                                engaged = True
                                break
                        if engaged:
                            continue
                    except Exception:
                        pass
                    cand.append(root)
            if not cand:
                on_chosen(None)
                return
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Murder-Call unit.",
                title="Select Murder-Call Unit",
                subtitle="BLOOD LEGIONS not in Engagement Range",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_murder_call_unit = _request_murder_call_unit

        def _request_summoned_by_slaughter_unit(player, game, candidates, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            def _is_bloodletters(u) -> bool:
                if u is None:
                    return False
                try:
                    if hasattr(u, "has_any_keyword") and u.has_any_keyword("BLOODLETTERS"):
                        return True
                except Exception:
                    pass
                try:
                    if hasattr(u, "has_keyword") and u.has_keyword("BLOODLETTERS"):
                        return True
                except Exception:
                    pass
                try:
                    return "bloodletters" in str(getattr(u, "name", "") or "").strip().lower()
                except Exception:
                    return False

            cand = list(candidates or [])
            if not cand:
                try:
                    from ..rules.stratagems import _unit_cannot_be_target_of_stratagem
                except Exception:
                    _unit_cannot_be_target_of_stratagem = None
                try:
                    army = player.get_army()
                    we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
                    if we_mgr is None or not getattr(we_mgr, "is_khorne_daemonkin", lambda: False)():
                        on_chosen(None)
                        return
                except Exception:
                    on_chosen(None)
                    return
                seen = set()
                for unit in player.get_army().units or []:
                    try:
                        root = unit.get_attached_unit_root()
                    except Exception:
                        root = unit
                    if root is None:
                        continue
                    try:
                        uid = get_entity_id(root)
                    except Exception:
                        continue
                    if uid in seen:
                        continue
                    seen.add(uid)
                    try:
                        if not root.is_in_reserves():
                            continue
                    except Exception:
                        continue
                    try:
                        if not root.is_alive():
                            continue
                    except Exception:
                        pass
                    if not _is_bloodletters(root):
                        continue
                    if callable(_unit_cannot_be_target_of_stratagem) and _unit_cannot_be_target_of_stratagem(root):
                        continue
                    cand.append(root)
            if not cand:
                on_chosen(None)
                return
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Summoned by Slaughter unit.",
                title="Select Summoned by Slaughter Unit",
                subtitle="Bloodletters unit in Reserves",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_summoned_by_slaughter_unit = _request_summoned_by_slaughter_unit

        def _request_daemonic_fury_targets(player, game, candidates, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                try:
                    from ..rules.stratagems import _unit_cannot_be_target_of_stratagem
                except Exception:
                    _unit_cannot_be_target_of_stratagem = None
                try:
                    army = player.get_army()
                    we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
                    if we_mgr is None or not getattr(we_mgr, "is_khorne_daemonkin", lambda: False)():
                        on_chosen(None, None)
                        return
                except Exception:
                    on_chosen(None, None)
                    return
                game_map = getattr(game, "map", None)
                if game_map is None:
                    on_chosen(None, None)
                    return
                seen = set()
                for unit in player.get_army().units or []:
                    try:
                        root = unit.get_attached_unit_root()
                    except Exception:
                        root = unit
                    if root is None:
                        continue
                    try:
                        uid = get_entity_id(root)
                    except Exception:
                        continue
                    if uid in seen:
                        continue
                    seen.add(uid)
                    try:
                        if not root.is_alive():
                            continue
                    except Exception:
                        pass
                    try:
                        if not getattr(root, "deployed", False):
                            continue
                    except Exception:
                        continue
                    try:
                        if getattr(root, "is_in_reserves", lambda: False)():
                            continue
                    except Exception:
                        pass
                    if callable(_unit_cannot_be_target_of_stratagem) and _unit_cannot_be_target_of_stratagem(root):
                        continue
                    try:
                        if not we_mgr.unit_is_blood_legions(root):
                            continue
                    except Exception:
                        continue
                    cand.append(root)
            if not cand:
                on_chosen(None, None)
                return

            def _pick_world_eaters(bl_unit):
                if bl_unit is None:
                    on_chosen(None, None)
                    return
                we_candidates = []
                try:
                    army = player.get_army()
                    we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
                except Exception:
                    army = None
                    we_mgr = None
                game_map = getattr(game, "map", None)
                if army is not None and we_mgr is not None and game_map is not None:
                    seen = set()
                    for unit in list(getattr(army, "units", []) or []):
                        try:
                            root = unit.get_attached_unit_root()
                        except Exception:
                            root = unit
                        if root is None:
                            continue
                        try:
                            uid = get_entity_id(root)
                        except Exception:
                            continue
                        if uid in seen:
                            continue
                        seen.add(uid)
                        try:
                            if not root.is_alive():
                                continue
                        except Exception:
                            pass
                        try:
                            if not getattr(root, "deployed", False):
                                continue
                        except Exception:
                            continue
                        try:
                            if getattr(root, "is_in_reserves", lambda: False)():
                                continue
                        except Exception:
                            pass
                        try:
                            if not we_mgr.unit_is_world_eaters(root):
                                continue
                        except Exception:
                            continue
                        try:
                            dist = game_map.get_distance_between_units(root, bl_unit)
                        except Exception:
                            dist = None
                        if dist is None or dist > 6.0:
                            continue
                        we_candidates.append(root)
                if not we_candidates:
                    on_chosen(bl_unit, None)
                    return
                _resolve_unit_selection_dialog(
                    player=player,
                    candidates=we_candidates,
                    on_chosen=lambda unit: on_chosen(bl_unit, unit),
                    decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                    prompt="Select Daemonic Fury World Eaters unit.",
                    title="Select Daemonic Fury World Eaters Unit",
                    subtitle=f"Within 6\" of {getattr(bl_unit, 'name', 'unit')}",
                    enemy_unit=bl_unit,
                    dialog=self.overwatch_shooter_dialog,
                    allow_skip=True,
                )

            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=_pick_world_eaters,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Daemonic Fury Blood Legions unit.",
                title="Select Daemonic Fury Blood Legions Unit",
                subtitle="BLOOD LEGIONS unit in your army",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )

        self._request_daemonic_fury_targets = _request_daemonic_fury_targets

        def _request_daemontide_targets(player, game, candidates, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                try:
                    from ..rules.stratagems import _unit_cannot_be_target_of_stratagem
                except Exception:
                    _unit_cannot_be_target_of_stratagem = None
                try:
                    army = player.get_army()
                    we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
                    if we_mgr is None or not getattr(we_mgr, "is_khorne_daemonkin", lambda: False)():
                        on_chosen(None, None)
                        return
                except Exception:
                    on_chosen(None, None)
                    return
                seen = set()
                for unit in player.get_army().units or []:
                    try:
                        root = unit.get_attached_unit_root()
                    except Exception:
                        root = unit
                    if root is None:
                        continue
                    try:
                        uid = get_entity_id(root)
                    except Exception:
                        continue
                    if uid in seen:
                        continue
                    seen.add(uid)
                    try:
                        if not root.is_alive():
                            continue
                    except Exception:
                        pass
                    try:
                        if not getattr(root, "deployed", False):
                            continue
                    except Exception:
                        continue
                    try:
                        if getattr(root, "is_in_reserves", lambda: False)():
                            continue
                    except Exception:
                        pass
                    if callable(_unit_cannot_be_target_of_stratagem) and _unit_cannot_be_target_of_stratagem(root):
                        continue
                    try:
                        if not we_mgr.unit_is_world_eaters(root):
                            continue
                    except Exception:
                        continue
                    cand.append(root)
            if not cand:
                on_chosen(None, None)
                return

            def _pick_blood_legions(we_unit):
                if we_unit is None:
                    on_chosen(None, None)
                    return
                bl_candidates = []
                try:
                    army = player.get_army()
                    we_mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
                except Exception:
                    army = None
                    we_mgr = None
                game_map = getattr(game, "map", None)
                if army is not None and we_mgr is not None and game_map is not None:
                    seen = set()
                    for unit in list(getattr(army, "units", []) or []):
                        try:
                            root = unit.get_attached_unit_root()
                        except Exception:
                            root = unit
                        if root is None:
                            continue
                        try:
                            uid = get_entity_id(root)
                        except Exception:
                            continue
                        if uid in seen:
                            continue
                        seen.add(uid)
                        try:
                            if not root.is_alive():
                                continue
                        except Exception:
                            pass
                        try:
                            if not getattr(root, "deployed", False):
                                continue
                        except Exception:
                            continue
                        try:
                            if getattr(root, "is_in_reserves", lambda: False)():
                                continue
                        except Exception:
                            pass
                        try:
                            if not we_mgr.unit_is_blood_legions(root):
                                continue
                        except Exception:
                            continue
                        try:
                            dist = game_map.get_distance_between_units(root, we_unit)
                        except Exception:
                            dist = None
                        if dist is None or dist > 6.0:
                            continue
                        bl_candidates.append(root)
                if not bl_candidates:
                    on_chosen(we_unit, None)
                    return
                _resolve_unit_selection_dialog(
                    player=player,
                    candidates=bl_candidates,
                    on_chosen=lambda unit: on_chosen(we_unit, unit),
                    decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                    prompt="Select Daemontide Blood Legions unit.",
                    title="Select Daemontide Blood Legions Unit",
                    subtitle=f"Within 6\" of {getattr(we_unit, 'name', 'unit')}",
                    enemy_unit=we_unit,
                    dialog=self.overwatch_shooter_dialog,
                    allow_skip=True,
                )

            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=_pick_blood_legions,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Daemontide World Eaters unit.",
                title="Select Daemontide World Eaters Unit",
                subtitle="WORLD EATERS unit in your army",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )

        self._request_daemontide_targets = _request_daemontide_targets

        def _request_blessing_of_burning_blood_unit(player, game, we_unit, candidates, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                on_chosen(None)
                return
            subtitle = "Select BLOOD LEGIONS unit"
            if we_unit is not None:
                subtitle = f"Within 6\" of {getattr(we_unit, 'name', 'unit')}"
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Blessing of Burning Blood unit.",
                title="Select Blessing of Burning Blood Unit",
                subtitle=subtitle,
                enemy_unit=we_unit,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )

        self._request_blessing_of_burning_blood_unit = _request_blessing_of_burning_blood_unit

        def _request_blitzing_firepower_unit(player, game, candidates, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                mgr = getattr(player, "stratagems", None)
                try:
                    if mgr is not None and hasattr(mgr, "_blitzing_firepower_candidates"):
                        cand = list(mgr._blitzing_firepower_candidates() or [])
                except Exception:
                    cand = []
            if not cand:
                on_chosen(None)
                return
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Blitzing Firepower unit.",
                title="Select Blitzing Firepower Unit",
                subtitle="ASURYANI unit that has not shot",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_blitzing_firepower_unit = _request_blitzing_firepower_unit

        def _request_lightning_fast_reactions_unit(player, game, candidates, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                on_chosen(None)
                return
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Lightning-Fast Reactions unit.",
                title="Select Lightning-Fast Reactions Unit",
                subtitle="Targeted by enemy this phase",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_lightning_fast_reactions_unit = _request_lightning_fast_reactions_unit

        def _request_unyielding_forms_unit(player, game, candidates, enemy_unit, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                on_chosen(None)
                return
            enemy_name = getattr(enemy_unit, "name", "enemy unit") if enemy_unit is not None else "enemy unit"
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Unyielding Forms unit.",
                title="Select Unyielding Forms Unit",
                subtitle=f"Targeted by {enemy_name}",
                enemy_unit=enemy_unit,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_unyielding_forms_unit = _request_unyielding_forms_unit

        def _request_merciless_reclamation_unit(player, game, candidates, on_chosen, phase_name=None):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                mgr = getattr(player, "stratagems", None)
                try:
                    if mgr is not None and hasattr(mgr, "_starshatter_merciless_reclamation_candidates"):
                        cand = list(mgr._starshatter_merciless_reclamation_candidates(phase_name) or [])
                except Exception:
                    cand = []
            if not cand:
                on_chosen(None)
                return
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Merciless Reclamation unit.",
                title="Select Merciless Reclamation Unit",
                subtitle="NECRONS unit that has not acted",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_merciless_reclamation_unit = _request_merciless_reclamation_unit

        def _request_dimensional_tunnel_unit(player, game, candidates, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                mgr = getattr(player, "stratagems", None)
                try:
                    if mgr is not None and hasattr(mgr, "_starshatter_dimensional_tunnel_candidates"):
                        cand = list(mgr._starshatter_dimensional_tunnel_candidates() or [])
                except Exception:
                    cand = []
            if not cand:
                on_chosen(None)
                return
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Dimensional Tunnel unit.",
                title="Select Dimensional Tunnel Unit",
                subtitle="NECRONS VEHICLE or MOUNTED (non-TITANIC)",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_dimensional_tunnel_unit = _request_dimensional_tunnel_unit

        def _request_chronoshift_unit(player, game, candidates, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                mgr = getattr(player, "stratagems", None)
                try:
                    if mgr is not None and hasattr(mgr, "_starshatter_chronoshift_candidates"):
                        cand = list(mgr._starshatter_chronoshift_candidates() or [])
                except Exception:
                    cand = []
            if not cand:
                on_chosen(None)
                return
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Chronoshift unit.",
                title="Select Chronoshift Unit",
                subtitle="NECRONS VEHICLE or MOUNTED that has not moved",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_chronoshift_unit = _request_chronoshift_unit

        def _request_endless_servitude_unit(player, game, candidates, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                on_chosen(None)
                return
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Endless Servitude unit.",
                title="Select Endless Servitude Unit",
                subtitle="Within a controlled objective",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_endless_servitude_unit = _request_endless_servitude_unit

        def _request_reactive_reposition_unit(player, game, candidates, enemy_unit, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                on_chosen(None)
                return
            enemy_name = getattr(enemy_unit, "name", "enemy unit") if enemy_unit is not None else "enemy unit"
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Reactive Reposition unit.",
                title="Select Reactive Reposition Unit",
                subtitle=f"Targeted by {enemy_name}",
                enemy_unit=enemy_unit,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_reactive_reposition_unit = _request_reactive_reposition_unit

        def _request_webway_tunnel_unit(player, game, candidates, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                on_chosen(None)
                return
            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=on_chosen,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Webway Tunnel unit.",
                title="Select Webway Tunnel Unit",
                subtitle="ASURYANI INFANTRY within 9\" of an edge",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        self._request_webway_tunnel_unit = _request_webway_tunnel_unit

        def _request_skyborne_sanctuary_targets(player, game, candidates, transport_candidates_by_unit, on_chosen):
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            cand = list(candidates or [])
            if not cand:
                on_chosen(None, None)
                return

            def _pick_transport(unit):
                if unit is None:
                    on_chosen(None, None)
                    return
                transports = []
                try:
                    if isinstance(transport_candidates_by_unit, dict):
                        transports = list(transport_candidates_by_unit.get(unit) or [])
                except Exception:
                    transports = []
                if not transports:
                    try:
                        from ..utility.aura_utils import unit_wholly_within_range_of_unit
                    except Exception:
                        unit_wholly_within_range_of_unit = None
                    for t in player.get_army().units or []:
                        try:
                            if t is None or not t.is_alive() or not getattr(t, "deployed", False):
                                continue
                            if not getattr(t, "is_transport", False):
                                continue
                            if not t.can_transport(unit):
                                continue
                            if callable(unit_wholly_within_range_of_unit):
                                if not unit_wholly_within_range_of_unit(t, unit, 6.0, use_attached_aggregate=True):
                                    continue
                            transports.append(t)
                        except Exception:
                            continue
                if not transports:
                    on_chosen(unit, None)
                    return
                _resolve_unit_selection_dialog(
                    player=player,
                    candidates=transports,
                    on_chosen=lambda t: on_chosen(unit, t),
                    decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                    prompt="Select Skyborne Sanctuary transport.",
                    title="Select Skyborne Sanctuary Transport",
                    subtitle=f"Embark {getattr(unit, 'name', 'unit')} within 6\"",
                    enemy_unit=unit,
                    dialog=self.overwatch_shooter_dialog,
                    allow_skip=True,
                )

            _resolve_unit_selection_dialog(
                player=player,
                candidates=cand,
                on_chosen=_pick_transport,
                decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                prompt="Select Skyborne Sanctuary unit.",
                title="Select Skyborne Sanctuary Unit",
                subtitle="Not within Engagement Range and wholly within 6\"",
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )

        self._request_skyborne_sanctuary_targets = _request_skyborne_sanctuary_targets

        # Generic yes/no prompt hook for optional ability decisions (e.g., Direct the Slaughter)
        def _request_yes_no(
            title: str,
            message: str,
            yes_label: str,
            no_label: str,
            on_chosen,
            *,
            player=None,
            context: Optional[dict] = None,
        ):
            from ..engine.decision_kinds import DECISION_CONFIRM_YES_NO
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.decision_utils import resolve_decision_command

            options = [
                DecisionOption.create(yes_label or "Yes", payload={"choice": True}),
                DecisionOption.create(no_label or "No", payload={"choice": False}),
            ]
            ctx = dict(context or {})
            ctx["message"] = message
            req = DecisionRequest.create(
                DECISION_CONFIRM_YES_NO,
                title or "Confirm",
                player_id=getattr(player, "id", None) if player is not None else (getattr(self.game.get_current_player(), "id", None) if self.game else None),
                options=options,
                context=ctx,
            )
            if self.game is not None:
                self.game.request_decision(req)
            choice_map = {opt.option_id: bool(opt.payload.get("choice", False)) for opt in options}

            def _on_confirm(option_id: str):
                if self.game is not None and option_id:
                    resolve_decision_command(self.game, req, option_id)
                on_chosen(choice_map.get(option_id, False))
                try:
                    self.yes_no_dialog.hide()
                except Exception:
                    pass

            self.yes_no_dialog.show(
                title,
                message,
                _on_confirm,
                decision_request=req,
            )
            try:
                # Make it explicitly topmost
                self.dialog_manager.open(self.yes_no_dialog, modal=True)
            except Exception:
                pass
        self._request_yes_no = _request_yes_no
        self.phase_manager._request_yes_no = self._request_yes_no

        def _request_overwatch_shooting(shooter_unit, enemy_unit, on_done):
            from ..engine.decision_kinds import DECISION_DECLARE_SHOTS
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.entity_ids import get_entity_id

            # Reuse ShootingDeclarationDialog for interactive weapon selection/targeting
            if not hasattr(self, 'shooting_declaration_dialog'):
                from .dialogs import ShootingDeclarationDialog
                self.shooting_declaration_dialog = ShootingDeclarationDialog(self.screen.get_width(), self.screen.get_height())
            # Configure dialog to auto-target the moved enemy unit
            try:
                self.shooting_declaration_dialog.force_single_target_unit = enemy_unit
            except Exception:
                pass

            try:
                unit_id = get_entity_id(shooter_unit)
            except Exception:
                unit_id = ""
            options = [
                DecisionOption.create("Confirm", payload={"action": "confirm", "unit_id": unit_id}),
                DecisionOption.create("Skip", payload={"action": "skip", "unit_id": unit_id}),
            ]
            req = DecisionRequest.create(
                DECISION_DECLARE_SHOTS,
                f"Declare Overwatch shots for {getattr(shooter_unit, 'name', 'Unit')}",
                player_id=getattr(getattr(shooter_unit.get_parent_army(), "player", None), "id", None),
                options=options,
                context={"unit_id": unit_id, "out_of_phase": True},
            )
            if self.game is not None:
                self.game.request_decision(req)

            def _cb(executed: bool):
                self.shooting_declaration_dialog.force_single_target_unit = None
                on_done(bool(executed))

            self.shooting_declaration_dialog.show(
                shooter_unit,
                _cb,
                self.game.map,
                self,
                out_of_phase=True,
                allow_actions=False,
                decision_request=req,
            )
            # Ensure dialog is visible and receives events immediately
            self.shooting_declaration_dialog.visible = True
        self._request_overwatch_shooting = _request_overwatch_shooting

        def _request_setup_reactive_shooting(shooter_unit, enemy_unit, source, on_done):
            from ..engine.decision_kinds import DECISION_DECLARE_SHOTS
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.entity_ids import maybe_entity_id

            if not hasattr(self, 'shooting_declaration_dialog'):
                from .dialogs import ShootingDeclarationDialog
                self.shooting_declaration_dialog = ShootingDeclarationDialog(self.screen.get_width(), self.screen.get_height())
            self.shooting_declaration_dialog.force_single_target_unit = enemy_unit

            unit_id = str(maybe_entity_id(shooter_unit) or "")
            target_id = str(maybe_entity_id(enemy_unit) or "")
            options = [
                DecisionOption.create("Confirm", payload={"action": "confirm", "unit_id": unit_id}),
                DecisionOption.create("Skip", payload={"action": "skip", "unit_id": unit_id}),
            ]
            title = str(source or "Reactive Response").strip() or "Reactive Response"
            req = DecisionRequest.create(
                DECISION_DECLARE_SHOTS,
                f"{title}: Declare shots for {getattr(shooter_unit, 'name', 'Unit')}",
                player_id=getattr(getattr(shooter_unit.get_parent_army(), "player", None), "id", None),
                options=options,
                context={"unit_id": unit_id, "out_of_phase": True, "force_target_unit_id": target_id, "source": title},
            )
            if self.game is not None:
                self.game.request_decision(req)

            def _cb(executed: bool):
                try:
                    self.shooting_declaration_dialog.force_single_target_unit = None
                except Exception:
                    pass
                on_done(bool(executed))

            self.shooting_declaration_dialog.show(
                shooter_unit,
                _cb,
                self.game.map,
                self,
                out_of_phase=True,
                allow_actions=False,
                decision_request=req,
            )
            self.shooting_declaration_dialog.visible = True
        self._request_setup_reactive_shooting = _request_setup_reactive_shooting

        def _request_frenzy_shooting(shooter_unit, enemy_unit, on_done):
            from ..engine.decision_kinds import DECISION_DECLARE_SHOTS
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.entity_ids import get_entity_id

            if not hasattr(self, 'shooting_declaration_dialog'):
                from .dialogs import ShootingDeclarationDialog
                self.shooting_declaration_dialog = ShootingDeclarationDialog(self.screen.get_width(), self.screen.get_height())
            try:
                self.shooting_declaration_dialog.force_single_target_unit = enemy_unit
            except Exception:
                pass

            try:
                unit_id = get_entity_id(shooter_unit)
            except Exception:
                unit_id = ""
            options = [
                DecisionOption.create("Confirm", payload={"action": "confirm", "unit_id": unit_id}),
                DecisionOption.create("Skip", payload={"action": "skip", "unit_id": unit_id}),
            ]
            req = DecisionRequest.create(
                DECISION_DECLARE_SHOTS,
                f"Declare Frenzy shots for {getattr(shooter_unit, 'name', 'Unit')}",
                player_id=getattr(getattr(shooter_unit.get_parent_army(), "player", None), "id", None),
                options=options,
                context={"unit_id": unit_id, "out_of_phase": True},
            )
            if self.game is not None:
                self.game.request_decision(req)

            def _cb(executed: bool):
                try:
                    self.shooting_declaration_dialog.force_single_target_unit = None
                except Exception:
                    pass
                on_done(bool(executed))

            self.shooting_declaration_dialog.show(
                shooter_unit,
                _cb,
                self.game.map,
                self,
                out_of_phase=True,
                allow_actions=False,
                decision_request=req,
            )
            self.shooting_declaration_dialog.visible = True
        self._request_frenzy_shooting = _request_frenzy_shooting

        # WORLD EATERS: SKULLS FOR THE SKULL THRONE! -> interactive Blessings roll (extra global Blessing)
        def _request_blessings_roll(player, game, context, on_done):
            try:
                army = player.get_army()
            except Exception:
                on_done(False)
                return
            mgr = getattr(army, "blessings_of_khorne", None)
            if mgr is None:
                on_done(False)
                return
            if self.blessings_of_khorne_dialog is None:
                try:
                    from .dialogs import BlessingsOfKhorneDialog
                    sw, sh = self.screen.get_size()
                    self.blessings_of_khorne_dialog = BlessingsOfKhorneDialog(sw, sh)
                except Exception:
                    self.blessings_of_khorne_dialog = None
            if self.blessings_of_khorne_dialog is None:
                on_done(False)
                return

            # Determine if Favoured of Khorne reroll is available (bearer on battlefield)
            rerolls_allowed = 0
            try:
                if hasattr(mgr, "favoured_of_khorne_rerolls_for_army"):
                    rerolls_allowed = int(mgr.favoured_of_khorne_rerolls_for_army(army) or 0)
            except Exception:
                rerolls_allowed = 0

            from ..rules.blessings_of_khorne import BlessingsTiming
            unit = context.get("attacker_unit") or context.get("unit") or context.get("target_unit")
            try:
                extra_active = mgr.get_unit_specific_blessings(unit, battle_round=int(getattr(game, "turn", 0) or 0))
            except Exception:
                extra_active = set()
            ctx = mgr.create_roll_context(
                battle_round=int(getattr(game, "turn", 0) or 0),
                timing=BlessingsTiming.OTHER,
                extra_dice_from_idols=0,
                rerolls_allowed=rerolls_allowed,
                max_activations=1,
                counts_toward_baseline_limit=False,
                already_active_keys=set(getattr(mgr, "active_blessing_keys", set()) or set()) | set(extra_active),
                reborn_in_blood_available=False,
            )

            from ..engine.decision_kinds import DECISION_CHOOSE_BLESSINGS
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.decision_utils import resolve_decision_value
            from ..utility.entity_ids import get_entity_id

            army_id = get_entity_id(army) if army is not None else ""
            options = [DecisionOption.create("Confirm", payload={"army_id": army_id})]
            req = DecisionRequest.create(
                DECISION_CHOOSE_BLESSINGS,
                "Select Blessings of Khorne.",
                player_id=getattr(player, "id", None),
                options=options,
                context={"army_id": army_id, "ctx": {}},
            )
            if self.game is not None:
                self.game.request_decision(req)

            def _on_confirm(option_id: str, payload: dict):
                value, apply_result = resolve_decision_value(self.game, req, option_id, result_payload=payload)
                if apply_result is None or not getattr(apply_result, "ok", False):
                    payload = {}
                else:
                    payload = dict(payload or {})
                    payload["result"] = value
                try:
                    from ..utility.event_bus import append_action
                    sel_keys = list(payload.get("selected_blessings") or payload.get("result", {}).get("activated") or [])
                    use_reborn = bool(payload.get("use_reborn") or payload.get("result", {}).get("reborn_used"))
                    names = []
                    if sel_keys:
                        for k in sel_keys:
                            try:
                                d = mgr.definitions.get(str(k).strip().upper())
                            except Exception:
                                d = None
                            names.append(getattr(d, "name", None) or str(k))
                    if use_reborn:
                        names.append("Reborn in Blood")
                    if not names:
                        names_text = "no blessings activated"
                    else:
                        names_text = ", ".join(names)
                    dice = list(getattr(payload.get("ctx", None), "dice", []) or [])
                    dice_text = ", ".join(str(int(d)) for d in dice) if dice else "?"
                    append_action(player, f"Blessings of Khorne (Skulls for the Skull Throne!): {names_text} (dice: {dice_text})")
                except Exception:
                    pass
                try:
                    if isinstance(payload, dict):
                        payload["unit"] = unit
                except Exception:
                    pass
                on_done(payload)

            def _on_cancel():
                option_id = options[0].option_id if options else ""
                resolve_decision_value(
                    self.game,
                    req,
                    option_id,
                    result_payload={"selected_blessings": [], "use_reborn": False},
                )
                on_done(None)

            self.blessings_of_khorne_dialog.show(
                player=player,
                game=game,
                army=army,
                ctx=ctx,
                on_confirm=_on_confirm,
                on_cancel=_on_cancel,
                decision_request=req,
            )
            try:
                self.dialog_manager.open(self.blessings_of_khorne_dialog, modal=True)
            except Exception:
                pass
        self._request_blessings_roll = _request_blessings_roll
        self._stratagem_panes = {
            self.player1: self.left_stratagem_pane,
            self.player2: self.right_stratagem_pane,
        }
        self._overwatch_flow_active = False
        self._heroic_flow_active = False
        self._optional_flow_active = False
        self._blessings_flow_active = False
        self._battle_focus_flow_active = False
        self._oath_of_moment_flow_active = False
        self._code_chivalric_flow_active = False
        self._bondsman_flow_active = False
        self._necrons_enhancement_flow_active = False
        self._summoned_by_slaughter_flow_active = False
        self._dark_pacts_flow_active = False
        self._martial_katah_flow_active = False
        self._emperors_children_pledge_flow_active = False
        self._emperors_children_exquisite_flow_active = False
        self._emperors_children_sensational_flow_active = False
        self._cabal_flow_active = False
        self._voice_of_command_flow_active = False
        self._gate_of_infinity_flow_active = False
        self._shadow_in_the_warp_flow_active = False
        self._pain_flow_active = False
        self._waaagh_flow_active = False
        self._ftgg_flow_active = False
        self._cult_ambush_flow_active = False
        self._cult_ambush_marker_flow_active = False
        self._voice_of_command_pending_order = None

        # Initialize shared UI state
        self._ui_hitboxes = {}
        self._mission_popup = None
        self._vp_history_popup = None
        self._cp_history_popup = None
        self.popup_overlays = PopupOverlayRenderer()

        # Blessings of Khorne start-of-battle-round hook
        self._pending_blessings_queue = []
        # Templar Vows start-of-battle-round hook
        self._pending_templar_vows_queue = []
        # Belakor Shadow Form selection queue
        self._pending_shadow_form_queue = []
        # Angron Wrathful Presence selection queue
        self._pending_wrathful_presence_queue = []
        # Daemonic Allegiance selection queue (Soul Grinder)
        self._pending_daemonic_allegiance_queue = []
        # Chaos Knights: Harbingers of Dread selection queue
        self._pending_harbingers_queue = []
        # Adeptus Mechanicus: Doctrina Imperatives selection queue
        self._pending_doctrina_queue = []
        # Space Marines: Combat Doctrines selection queue
        self._pending_combat_doctrines_queue = []
        # Drukhari: Combat Drugs selection queue
        self._pending_combat_drugs_queue = []
        # Imperial Knights: Code Chivalric selection queue
        self._pending_code_chivalric_queue = []
        # Imperial Knights: Bondsman selection queue
        self._pending_bondsman_queue = []
        # Necrons enhancements: command phase target selection queue
        self._pending_necrons_enhancement_queue = []
        # Chaos Space Marines: Dark Pacts selection queue
        self._pending_dark_pacts_queue = []
        # Astra Militarum: Voice of Command prompt queue
        self._pending_voice_of_command_queue = []
        # Grey Knights: Gate of Infinity prompt queue
        self._pending_gate_of_infinity_queue = []
        # End of opponent's turn: Strategic Reserves prompt queue
        self._pending_opponent_turn_reserves_queue = []
        self._opponent_turn_reserves_flow_active = False
        # Adeptus Custodes: Martial Ka'tah selection queue
        self._pending_martial_katah_queue = []
        # Emperor's Children: Pledge/Exquisite/Sensational prompt queues
        self._pending_emperors_children_pledge_queue = []
        self._pending_emperors_children_exquisite_queue = []
        self._pending_emperors_children_sensational_queue = []
        # Tyranids: Shadow in the Warp prompt queue
        self._pending_shadow_in_the_warp_queue = []
        # Drukhari: Power from Pain prompt queue
        self._pending_pain_prompt_queue = []
        # SLAANESH/DAEMONS (Shalaxi): Monarch of the Hunt quarry selection queue
        self._pending_quarry_queue = []
        # Genestealer Cults: Cult Ambush prompt queues
        self._pending_cult_ambush_queue = []
        self._pending_cult_ambush_marker_queue = []
        # World Eaters: Blood Tithe prompt queue
        self._pending_blood_tithe_queue = []
        self._blood_tithe_flow_active = False
        # World Eaters: Blood Surge prompt queue
        self._pending_blood_surge_queue = []
        self._blood_surge_flow_active = False
        # Reverberating Summons prompt queue
        self._pending_reverberating_summons_queue = []
        self._reverberating_summons_flow_active = False
        # Reactive enemy-move prompt queue (e.g. Loping Speed)
        self._pending_loping_speed_queue = []
        self._loping_speed_flow_active = False
        # Setup reactive shoot/charge prompt queue
        self._pending_setup_reactive_shoot_charge_queue = []
        self._setup_reactive_shoot_charge_flow_active = False
        # Charge-end mortal wound prompts
        self._pending_charge_mortal_wounds_queue = []
        self._charge_mortal_wounds_flow_active = False
        # Charge phase end bodyguard loss prompts
        self._pending_charge_phase_bodyguard_loss_queue = []
        self._charge_phase_bodyguard_loss_flow_active = False
        # Fight phase end mortal wound prompts
        self._pending_fight_end_mortal_wounds_queue = []
        self._fight_end_mortal_wounds_flow_active = False
        # Move-over mortal wound prompts
        self._pending_move_over_mortal_wounds_queue = []
        self._move_over_mortal_wounds_flow_active = False
        # Post-shoot Battle-shock prompts
        self._pending_post_shoot_battleshock_queue = []
        self._post_shoot_battleshock_flow_active = False
        # Post-shoot suppression prompts
        self._pending_post_shoot_suppress_queue = []
        self._post_shoot_suppress_flow_active = False
        # Transport reactive disembark prompts
        self._pending_transport_reactive_disembark_queue = []
        self._transport_reactive_disembark_flow_active = False
        try:
            if self.game and getattr(self.game, "event_system", None) is not None:
                self.game.event_system.subscribe("battle_round_started", self._on_battle_round_started)
                # Optional ability prompts (phase-start timing windows)
                self.game.event_system.subscribe("phase_start", self._on_phase_start_optional_ability_prompts)
                # Oath of Moment target selection (start of Command phase)
                self.game.event_system.subscribe("oath_of_moment_prompt", self._on_oath_of_moment_prompt)
                # Imperial Knights: Code Chivalric selection (setup)
                self.game.event_system.subscribe("code_chivalric_prompt", self._on_code_chivalric_prompt)
                # Daemonic Allegiance selection (muster phase)
                self.game.event_system.subscribe("daemonic_allegiance_prompt", self._on_daemonic_allegiance_prompt)
                # Imperial Knights: Bondsman selection (Command phase)
                self.game.event_system.subscribe("bondsman_prompt", self._on_bondsman_prompt)
                # Necrons enhancements: command phase bearer target selection
                self.game.event_system.subscribe(
                    "necrons_command_phase_enhancement_prompt",
                    self._on_necrons_command_phase_enhancement_prompt,
                )
                # Tyranids: Shadow in the Warp prompt (either Command phase)
                self.game.event_system.subscribe("shadow_in_the_warp_prompt", self._on_shadow_in_the_warp_prompt)
                # Orks: Waaagh! prompt (start of Command phase)
                self.game.event_system.subscribe("waaagh_prompt", self._on_waaagh_prompt)
                # T'au Empire: For the Greater Good observer/spotter selection
                self.game.event_system.subscribe("for_the_greater_good_prompt", self._on_for_the_greater_good_prompt)
                # Dark Pacts prompt when a unit is selected to shoot or fight
                self.game.event_system.subscribe("dark_pacts_prompt", self._on_dark_pacts_prompt)
                # Astra Militarum: Voice of Command prompt at Command phase start/end
                self.game.event_system.subscribe("voice_of_command_prompt", self._on_voice_of_command_prompt)
                # Space Marines: Combat Doctrines prompt
                self.game.event_system.subscribe("combat_doctrines_prompt", self._on_combat_doctrines_prompt)
                # Drukhari: Combat Drugs prompt
                self.game.event_system.subscribe("combat_drugs_prompt", self._on_combat_drugs_prompt)
                # Grey Knights: Gate of Infinity prompt at end of opponent's Fight phase
                self.game.event_system.subscribe("gate_of_infinity_prompt", self._on_gate_of_infinity_prompt)
                # End of opponent's turn: Strategic Reserves prompt
                self.game.event_system.subscribe(
                    "opponent_turn_strategic_reserves_prompt",
                    self._on_opponent_turn_strategic_reserves_prompt,
                )
                # Adeptus Custodes: Martial Ka'tah stance selection
                self.game.event_system.subscribe("martial_katah_prompt", self._on_martial_katah_prompt)
                # Emperor's Children: Detachment prompts
                self.game.event_system.subscribe("emperors_children_pledge_prompt", self._on_emperors_children_pledge_prompt)
                self.game.event_system.subscribe("emperors_children_exquisite_prompt", self._on_emperors_children_exquisite_prompt)
                self.game.event_system.subscribe("emperors_children_sensational_prompt", self._on_emperors_children_sensational_prompt)
                self.game.event_system.subscribe("emperors_children_pact_points_updated", self._on_emperors_children_pact_points_updated)
                # Drukhari: Power from Pain prompt when a unit can be empowered
                self.game.event_system.subscribe("pain_token_prompt", self._on_pain_token_prompt)
                # World Eaters: Blood Tithe prompt (Command phase / fight-phase A Worthy Skull)
                self.game.event_system.subscribe("blood_tithe_prompt", self._on_blood_tithe_prompt)
                self.game.event_system.subscribe("blood_tithe_updated", self._on_blood_tithe_updated)
                # World Eaters: Blood Surge prompt on opponent shooting casualties
                self.game.event_system.subscribe("blood_surge_prompt", self._on_blood_surge_prompt)
                self.game.event_system.subscribe("reverberating_summons_prompt", self._on_reverberating_summons_prompt)
                # Reactive normal move prompt (enemy unit ends move within range)
                self.game.event_system.subscribe("loping_speed_prompt", self._on_loping_speed_prompt)
                # Setup reactive shoot/charge prompt (enemy unit set up within range)
                self.game.event_system.subscribe("setup_reactive_shoot_charge_prompt", self._on_setup_reactive_shoot_charge_prompt)
                # World Eaters: Frenzy prompt (Helbrute reactive shoot/fight)
                self.game.event_system.subscribe("frenzy_prompt", self._on_frenzy_prompt)
                # Charge-end mortal wound target selection
                self.game.event_system.subscribe("charge_mortal_wounds_prompt", self._on_charge_mortal_wounds_prompt)
                # Move-over mortal wound target selection
                self.game.event_system.subscribe("move_over_mortal_wounds_prompt", self._on_move_over_mortal_wounds_prompt)
                # Charge phase end leadership test bodyguard loss
                self.game.event_system.subscribe(
                    "charge_phase_bodyguard_loss_prompt",
                    self._on_charge_phase_bodyguard_loss_prompt,
                )
                self.game.event_system.subscribe(
                    "fight_phase_end_mortal_wounds_prompt",
                    self._on_fight_phase_end_mortal_wounds_prompt,
                )
                # Post-shoot Battle-shock target selection
                self.game.event_system.subscribe("post_shoot_battleshock_prompt", self._on_post_shoot_battleshock_prompt)
                # Post-shoot suppression target selection
                self.game.event_system.subscribe("post_shoot_suppress_prompt", self._on_post_shoot_suppress_prompt)
                # Transport reactive disembark prompt
                self.game.event_system.subscribe("transport_reactive_disembark_prompt", self._on_transport_reactive_disembark_prompt)
                # Quarry re-pick when quarry is destroyed
                self.game.event_system.subscribe("unit_destroyed", self._on_unit_destroyed_for_monarch_of_the_hunt)
                # Battle Focus reactive prompts (Opportunity Seized / Fade Back)
                self.game.event_system.subscribe("battle_focus_opportunity_prompt", self._on_battle_focus_opportunity_prompt)
                self.game.event_system.subscribe("battle_focus_fade_back_prompt", self._on_battle_focus_fade_back_prompt)
                # Cabal of Sorcerers: Temporal Surge movement prompt
                self.game.event_system.subscribe("cabal_temporal_surge_move", self._on_cabal_temporal_surge_move)
                # Warhost: Fire and Fade reactive movement prompt
                self.game.event_system.subscribe("fire_and_fade_move", self._on_fire_and_fade_move)
                # Necrons: Reactive Reposition movement prompt
                self.game.event_system.subscribe("reactive_reposition_move", self._on_reactive_reposition_move)
                # Cabal of Sorcerers: Ritual resolution popup
                self.game.event_system.subscribe("cabal_ritual_resolved", self._on_cabal_ritual_resolved)
                # Leagues of Votann: Prioritised Efficiency updates (Yield Points / mode)
                self.game.event_system.subscribe("prioritised_efficiency_updated", self._on_prioritised_efficiency_updated)
                # Genestealer Cults: Cult Ambush prompts + HUD updates
                self.game.event_system.subscribe("cult_ambush_prompt", self._on_cult_ambush_prompt)
                self.game.event_system.subscribe("cult_ambush_reinforcements_prompt", self._on_cult_ambush_reinforcements_prompt)
                self.game.event_system.subscribe("cult_ambush_updated", self._on_cult_ambush_updated)
        except Exception:
            pass

    def _on_battle_round_started(self, game=None, battle_round: int = 0, **_kwargs):
        """Event hook: at start of battle round, prompt local players for Blessings of Khorne selection."""
        try:
            game = game or self.game
            br = int(battle_round or getattr(game, "turn", 0) or 0)
        except Exception:
            return
        if br <= 0:
            return

        # Build queue of players to prompt (human WE only), starting with the current player.
        try:
            current = game.get_current_player()
            others = [p for p in list(getattr(game, "players", []) or []) if p is not current]
            order = [current] + others
        except Exception:
            order = list(getattr(game, "players", []) or [])

        queue = []
        for p in order:
            try:
                if p is None or not p.has_control():
                    continue
                army = p.get_army()
                if not self._army_has_blessings_of_khorne(army):
                    continue
                if getattr(army, "blessings_of_khorne", None) is None:
                    continue
                queue.append(p)
            except Exception:
                continue

        if queue:
            self._pending_blessings_queue = list(queue)
            self._open_next_blessings_prompt(br)

        # BLACK TEMPLARS: Templar Vows are chosen at the start of the first battle round.
        if br == 1:
            queue = []
            for p in order:
                try:
                    if p is None or not p.has_control():
                        continue
                    army = p.get_army()
                    mgr = getattr(army, "templar_vows", None) if army is not None else None
                    if mgr is None:
                        continue
                    if not getattr(mgr, "_army_has_vows", lambda: False)():
                        continue
                    if getattr(mgr, "active_vow_key", None):
                        continue
                    queue.append(p)
                except Exception:
                    continue
            if queue:
                self._pending_templar_vows_queue = list(queue)
                self._open_next_templar_vows_prompt()

        # CHAOS KNIGHTS: Harbingers of Dread selection at the start of battle rounds 1, 3, and 5.
        if br in (1, 3, 5):
            queue = []
            for p in order:
                try:
                    if p is None or not p.has_control():
                        continue
                    army = p.get_army()
                    mgr = getattr(army, "harbingers_of_dread", None) if army is not None else None
                    if mgr is None or not getattr(mgr, "_army_has_harbingers", lambda: False)():
                        continue
                    if getattr(mgr, "last_selection_round", None) == br:
                        continue
                    if not getattr(mgr, "get_available_dread_abilities", lambda: [])():
                        continue
                    queue.append(p)
                except Exception:
                    continue
            if queue:
                self._pending_harbingers_queue = list(queue)
                self._open_next_harbingers_prompt(br)

        # ADEPTUS MECHANICUS: Doctrina Imperatives selection at the start of each battle round.
        queue = []
        for p in order:
            try:
                if p is None or not p.has_control():
                    continue
                army = p.get_army()
                mgr = getattr(army, "doctrina_imperatives", None) if army is not None else None
                if mgr is None or not getattr(mgr, "_army_has_doctrina", lambda: False)():
                    continue
                if getattr(mgr, "active_round", None) == br and getattr(mgr, "active_imperative_key", None):
                    continue
                queue.append(p)
            except Exception:
                continue
        if queue:
            self._pending_doctrina_queue = list(queue)
            self._open_next_doctrina_prompt(br)

        # BELAKOR: Shadow Form is chosen at the start of each battle round.
        queue = []
        for p in order:
            try:
                if p is None or not p.has_control():
                    continue
                army = p.get_army()
                mgr = getattr(army, "shadow_form", None) if army is not None else None
                if mgr is None:
                    continue
                units = list(getattr(mgr, "get_shadow_form_units", lambda: [])() or [])
                if not units:
                    continue
                try:
                    from ..rules.shadow_form import get_active_shadow_form_key
                except Exception:
                    get_active_shadow_form_key = None
                for unit in units:
                    if get_active_shadow_form_key is not None:
                        if get_active_shadow_form_key(unit, battle_round=br):
                            continue
                    queue.append((p, unit, br))
            except Exception:
                continue
        if queue:
            self._pending_shadow_form_queue = list(queue)
            self._open_next_shadow_form_prompt()

        # ANGRON: Wrathful Presence is chosen at the start of each battle round.
        queue = []
        for p in order:
            try:
                if p is None or not p.has_control():
                    continue
                army = p.get_army()
                mgr = getattr(army, "wrathful_presence", None) if army is not None else None
                if mgr is None:
                    continue
                units = list(getattr(mgr, "get_wrathful_presence_units", lambda: [])() or [])
                if not units:
                    continue
                try:
                    from ..rules.wrathful_presence import get_active_wrathful_presence_key
                except Exception:
                    get_active_wrathful_presence_key = None
                for unit in units:
                    if get_active_wrathful_presence_key is not None:
                        if get_active_wrathful_presence_key(unit, battle_round=br):
                            continue
                    queue.append((p, unit, br))
            except Exception:
                continue
        if queue:
            self._pending_wrathful_presence_queue = list(queue)
            self._open_next_wrathful_presence_prompt()

        # SHALAXI: Monarch of the Hunt triggers at the start of the first battle round.
        if br == 1:
            self._queue_monarch_of_the_hunt_prompts(game)

    # ---------------- Optional ability prompt windows (UI-driven) ----------------

    def _on_phase_start_optional_ability_prompts(self, player=None, phase=None, **_kwargs):
        """
        UI-driven optional ability prompts.

        - Possessed Lord: once per battle, start of Fight phase, prompt to activate.
        - Enhancement: once per battle, start of Fight phase -> Fight First for bearer's unit.
        - Bodyguard return: Command phase, prompt to return destroyed Bodyguard models.
        """
        try:
            pname = str(getattr(phase, "name", "") or "").strip().upper()
        except Exception:
            pname = ""
        if pname == "FIGHT_PHASE":
            if player is None:
                return
            try:
                # Only prompt the active player (avoid double prompts from opponent publishes)
                if player is not self.game.get_current_player():
                    return
            except Exception:
                pass
            # Only for local control (remote controller decides externally).
            try:
                if player is None or not getattr(player, "has_control", lambda: False)():
                    return
            except Exception:
                return

            army = getattr(player, "army", None)
            if army is None:
                return

            # Build queue of optional activations at the start of the Fight phase.
            queue = []
            for unit in list(getattr(army, "units", []) or []):
                try:
                    if not unit.is_alive():
                        continue
                except Exception:
                    continue
                has_possessed_lord = False
                for ab in (getattr(unit, "possible_abilities", []) or []):
                    nm = str(getattr(ab, "name", "") or "").strip().lower()
                    if nm == "possessed lord":
                        has_possessed_lord = True
                        break
                if not has_possessed_lord:
                    continue
                for m in list(getattr(unit, "models", []) or []):
                    try:
                        if not getattr(m, "is_alive", True):
                            continue
                    except Exception:
                        continue
                    try:
                        if getattr(m, "has_used_once_per_battle", lambda _k: False)("possessed_lord"):
                            continue
                    except Exception:
                        pass
                    queue.append({"kind": "possessed_lord", "unit": unit, "model": m})
                    break  # typical character: prompt once per unit

            # Enhancement: once per battle, start of Fight phase -> Fight First for bearer's unit.
            for unit in list(getattr(army, "units", []) or []):
                try:
                    if not unit.is_alive():
                        continue
                except Exception:
                    pass
                try:
                    if not unit.has_enhancement_fight_first_once_per_battle():
                        continue
                    if not unit.can_use_enhancement_fight_first():
                        continue
                except Exception:
                    continue
                try:
                    model = unit._get_enhancement_bearer_model()
                except Exception:
                    model = None
                if model is None:
                    continue
                queue.append({"kind": "enhancement_fight_first", "unit": unit, "model": model})

            if not queue:
                return

            # Store and process sequentially so we don't stack multiple modals at once.
            self._pending_optional_ability_queue = list(queue)
            self._process_next_optional_ability_prompt(player)
            return

        if pname != "COMMAND_PHASE":
            return
        if player is None:
            return
        try:
            if player is not self.game.get_current_player():
                return
        except Exception:
            pass
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        army = getattr(player, "army", None)
        if army is None:
            return

        queue = []
        for unit in list(getattr(army, "units", []) or []):
            try:
                if not unit.is_alive():
                    continue
            except Exception:
                continue
            try:
                if not bool(getattr(unit, "is_attached_leader", False)):
                    continue
            except Exception:
                continue
            ability = None
            try:
                ability = unit.get_command_phase_bodyguard_return_ability()
            except Exception:
                ability = None
            if not ability:
                continue
            try:
                bodyguard = unit.get_attached_unit_root()
            except Exception:
                bodyguard = None
            if bodyguard is None or bodyguard is unit:
                continue
            try:
                if not getattr(bodyguard, "deployed", True):
                    continue
                if str(getattr(bodyguard, "reserve_status", "deployed")) != "deployed":
                    continue
                if hasattr(bodyguard, "is_in_reserves") and callable(getattr(bodyguard, "is_in_reserves")):
                    if bool(bodyguard.is_in_reserves()):
                        continue
                if bool(getattr(bodyguard, "embarked_in", None)):
                    continue
                if bool(getattr(bodyguard, "is_embarked", False)):
                    continue
            except Exception:
                pass
            try:
                if len(getattr(bodyguard, "models", []) or []) <= 0:
                    continue
            except Exception:
                continue
            try:
                if not list(getattr(bodyguard, "models_lost", []) or []):
                    continue
            except Exception:
                continue
            amount = 0
            try:
                amount = int(ability.get("amount", 0) or 0)
            except Exception:
                amount = 0
            if amount <= 0:
                continue
            queue.append(
                {
                    "unit": unit,
                    "bodyguard": bodyguard,
                    "ability": ability,
                    "remaining": amount,
                    "returned_any": False,
                }
            )

        if not queue:
            return

        self._pending_bodyguard_return_prompt_queue = list(queue)
        self._process_next_bodyguard_return_prompt(player)

    def _process_next_optional_ability_prompt(self, player):
        q = list(getattr(self, "_pending_optional_ability_queue", []) or [])
        if not q:
            self._pending_optional_ability_queue = []
            return
        item = q.pop(0)
        self._pending_optional_ability_queue = q

        kind = "possessed_lord"
        unit = None
        model = None
        if isinstance(item, dict):
            kind = str(item.get("kind", "possessed_lord") or "possessed_lord")
            unit = item.get("unit")
            model = item.get("model")
        else:
            try:
                unit, model = item
            except Exception:
                unit = None
                model = None

        if unit is None or model is None:
            self._process_next_optional_ability_prompt(player)
            return

        title = "Optional Ability"
        if kind == "enhancement_fight_first":
            try:
                enh_name = str(getattr(getattr(unit, "enhancement", None), "name", "") or "").strip()
            except Exception:
                enh_name = ""
            label = enh_name or "Enhancement"
            msg = (
                f"Use {label} for {getattr(model, 'name', 'Model')} "
                f"({getattr(unit, 'name', 'Unit')})?\n\n"
                "Once per battle: bearer unit gains Fights First until end of Fight phase."
            )
        else:
            msg = (
                f"Use Possessed Lord for {getattr(model, 'name', 'Model')} "
                f"({getattr(unit, 'name', 'Unit')})?\n\n"
                "Once per battle: +3A (melee) and Devastating Wounds until end of Fight phase."
            )

        def _done(chosen: bool):
            if chosen:
                if kind == "enhancement_fight_first":
                    try:
                        unit.activate_enhancement_fight_first()
                    except Exception:
                        pass
                else:
                    try:
                        model.activate_possessed_lord()
                    except Exception:
                        pass
            # Continue queue
            self._process_next_optional_ability_prompt(player)

        try:
            self._request_yes_no(title, msg, "Use", "Skip", _done, player=player)
        except Exception:
            _done(False)

    def _format_model_wargear_summary(self, model) -> str:
        try:
            wargear = list(getattr(model, "wargear", []) or [])
        except Exception:
            wargear = []
        if not wargear:
            return ""
        counts = {}
        for wg in wargear:
            try:
                name = str(getattr(wg, "name", "") or "").strip()
            except Exception:
                name = ""
            if not name:
                continue
            counts[name] = counts.get(name, 0) + 1
        parts = []
        for name, count in counts.items():
            if count > 1:
                parts.append(f"{name} x{count}")
            else:
                parts.append(name)
        if not parts:
            return ""
        return "Wargear: " + ", ".join(parts)

    def _process_next_bodyguard_return_prompt(self, player):
        q = list(getattr(self, "_pending_bodyguard_return_prompt_queue", []) or [])
        if not q:
            self._pending_bodyguard_return_prompt_queue = []
            return
        item = q.pop(0)
        self._pending_bodyguard_return_prompt_queue = q

        if isinstance(item, dict):
            unit = item.get("unit")
            bodyguard = item.get("bodyguard")
            ability = item.get("ability")
            remaining = int(item.get("remaining", 0) or 0)
            returned_any = bool(item.get("returned_any", False))
        else:
            try:
                unit, bodyguard, ability = item
            except Exception:
                unit = None
                bodyguard = None
                ability = None
            remaining = 0
            returned_any = False
        if unit is None or bodyguard is None or ability is None:
            self._process_next_bodyguard_return_prompt(player)
            return

        amount = 0
        try:
            amount = int(ability.get("amount", 0) or 0)
        except Exception:
            amount = 0
        if amount <= 0:
            self._process_next_bodyguard_return_prompt(player)
            return
        if remaining <= 0:
            remaining = amount

        ability_name = ability.get("name", "") or "Bodyguard Return"
        title = ability_name
        subtitle = getattr(bodyguard, "name", "Unit")
        instruction = "Select a destroyed Bodyguard model to return, or choose None."
        if remaining != 1:
            instruction = f"Select a destroyed Bodyguard model to return ({remaining} remaining), or choose None."

        try:
            destroyed = list(getattr(bodyguard, "models_lost", []) or [])
        except Exception:
            destroyed = []
        if not destroyed:
            self._process_next_bodyguard_return_prompt(player)
            return

        state = {"returned_any": returned_any}

        def _done(chosen):
            if chosen is None:
                try:
                    from ..utility.event_bus import append_action
                    if player is not None:
                        if state["returned_any"]:
                            append_action(player, f"{ability_name}: no additional models returned to {subtitle}.")
                        else:
                            append_action(player, f"{ability_name}: no model returned to {subtitle}.")
                except Exception:
                    pass
                self._process_next_bodyguard_return_prompt(player)
                return

            returned = 0
            try:
                returned = unit.return_destroyed_bodyguard_models(
                    1,
                    game_map=getattr(self.game, "map", None),
                    chosen_models=[chosen],
                )
            except Exception:
                returned = 0
            if returned > 0:
                try:
                    from ..utility.event_bus import append_action
                    if player is not None:
                        summary = self._format_model_wargear_summary(chosen)
                        if summary:
                            append_action(player, f"{ability_name}: returned {getattr(chosen, 'name', 'Model')} ({summary}) to {subtitle}.")
                        else:
                            append_action(player, f"{ability_name}: returned {getattr(chosen, 'name', 'Model')} to {subtitle}.")
                except Exception:
                    pass
                state["returned_any"] = True

            remaining_next = remaining - 1
            try:
                destroyed_left = list(getattr(bodyguard, "models_lost", []) or [])
            except Exception:
                destroyed_left = []
            if remaining_next > 0 and destroyed_left:
                next_item = {
                    "unit": unit,
                    "bodyguard": bodyguard,
                    "ability": ability,
                    "remaining": remaining_next,
                    "returned_any": state["returned_any"],
                }
                self._pending_bodyguard_return_prompt_queue = [next_item] + list(
                    getattr(self, "_pending_bodyguard_return_prompt_queue", []) or []
                )
            self._process_next_bodyguard_return_prompt(player)

        try:
            from .dialogs import DamageAllocationDialog
        except Exception:
            _done(None)
            return

        if not hasattr(self, "damage_allocation_dialog") or self.damage_allocation_dialog is None:
            self.damage_allocation_dialog = DamageAllocationDialog(self.screen.get_width(), self.screen.get_height())
        from ..engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id

        options = [DecisionOption.create("None", payload={"model_id": None, "action": "skip"})]
        for model in destroyed:
            options.append(
                DecisionOption.create(
                    getattr(model, "name", "Model"),
                    payload={"model_id": get_entity_id(model)},
                )
            )
        req = DecisionRequest.create(
            DECISION_ALLOCATE_DAMAGE,
            "Select destroyed Bodyguard model to return.",
            player_id=getattr(player, "id", None),
            options=options,
            context={"unit_id": get_entity_id(bodyguard), "selection_kind": "bodyguard_return"},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_choice(option_id: str):
            value, apply_result = resolve_decision_value(self.game, req, option_id)
            if apply_result is None or not getattr(apply_result, "ok", False):
                _done(None)
                return
            _done(value)

        dlg = self.damage_allocation_dialog
        try:
            dlg.show(
                bodyguard,
                destroyed,
                title=title,
                subtitle=subtitle,
                instruction=instruction,
                on_choice=_on_choice,
                include_none=True,
                none_label="None",
                show_wargear=True,
                decision_request=req,
            )
            self.dialog_manager.open(dlg, modal=True)
        except Exception:
            _done(None)

    def _on_dark_pacts_prompt(self, player=None, unit=None, phase_name=None, trigger=None, game=None, **_kwargs):
        if player is None or unit is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        if self._dark_pacts_flow_active:
            self._pending_dark_pacts_queue.append((player, unit, phase_name, trigger))
            return
        self._pending_dark_pacts_queue.append((player, unit, phase_name, trigger))
        self._open_next_dark_pacts_prompt(game or self.game)

    def _open_next_dark_pacts_prompt(self, game):
        q = list(getattr(self, "_pending_dark_pacts_queue", []) or [])
        if not q:
            self._pending_dark_pacts_queue = []
            self._dark_pacts_flow_active = False
            return
        player, unit, phase_name, trigger = q.pop(0)
        self._pending_dark_pacts_queue = q

        if player is None or unit is None:
            self._open_next_dark_pacts_prompt(game)
            return
        try:
            if not unit.can_use_dark_pacts():
                self._open_next_dark_pacts_prompt(game)
                return
        except Exception:
            self._open_next_dark_pacts_prompt(game)
            return
        try:
            sr = getattr(unit, "special_rules", None)
            exp = ""
            if isinstance(sr, dict):
                exp = str(sr.get("dark_pacts_expires_phase", "") or "").strip().upper()
                if sr.get("dark_pacts_active") and exp == str(phase_name or "").strip().upper():
                    self._open_next_dark_pacts_prompt(game)
                    return
        except Exception:
            pass

        if self.dark_pacts_dialog is None:
            try:
                from .dialogs import DarkPactsDialog
                sw, sh = self.screen.get_width(), self.screen.get_height()
                self.dark_pacts_dialog = DarkPactsDialog(sw, sh)
            except Exception:
                self.dark_pacts_dialog = None
        if self.dark_pacts_dialog is None:
            self._dark_pacts_flow_active = False
            return

        subtitle = f"{getattr(unit, 'name', 'Unit')} selected to {('shoot' if trigger == 'shooting' else 'fight')}."
        options = [
            {
                "label": "Skip Dark Pact",
                "summary": "Do not make a Dark Pact.",
                "value": None,
            },
            {
                "label": "Lethal Hits",
                "summary": "Weapons gain [LETHAL HITS] until end of phase.",
                "value": "LETHAL HITS",
            },
            {
                "label": "Sustained Hits 1",
                "summary": "Weapons gain [SUSTAINED HITS 1] until end of phase.",
                "value": "SUSTAINED HITS 1",
            },
        ]

        from ..engine.decision_kinds import DECISION_CHOOSE_DARK_PACT
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from .decision_ui_utils import option_id_for_action

        unit_id = get_entity_id(unit)
        decision_options = []
        for opt in list(options or []):
            label = str(opt.get("label", "Choice"))
            value = opt.get("value")
            payload = {
                "unit_id": unit_id,
                "choice": value,
                "summary": opt.get("summary", ""),
                "phase_name": phase_name or "",
                "trigger": trigger or "",
            }
            if value is None:
                payload["action"] = "skip"
            decision_options.append(DecisionOption.create(label, payload=payload))

        req = DecisionRequest.create(
            DECISION_CHOOSE_DARK_PACT,
            f"Select Dark Pact for {getattr(unit, 'name', 'Unit')}",
            player_id=getattr(player, "id", None),
            options=decision_options,
            context={"unit_id": unit_id, "phase_name": phase_name or "", "trigger": trigger or ""},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_confirm(option_id: str):
            value, apply_result = resolve_decision_value(self.game, req, option_id)
            if apply_result is None or not getattr(apply_result, "ok", False):
                value = None
            try:
                if value:
                    player.set_next_optional_decision("DARK_PACTS", True)
                    player.set_next_optional_selection("DARK_PACTS_CHOICE", value)
                else:
                    player.set_next_optional_decision("DARK_PACTS", False)
            except Exception:
                pass
            self._dark_pacts_flow_active = False
            self._open_next_dark_pacts_prompt(game)

        def _on_cancel():
            skip_id = option_id_for_action(req, "skip")
            if skip_id:
                resolve_decision_value(self.game, req, skip_id)
            self._dark_pacts_flow_active = False
            self._open_next_dark_pacts_prompt(game)

        self._dark_pacts_flow_active = True
        self.dark_pacts_dialog.show(on_confirm=_on_confirm, on_cancel=_on_cancel, subtitle=subtitle, decision_request=req)
        try:
            self.dialog_manager.open(self.dark_pacts_dialog, modal=True)
        except Exception:
            self._dark_pacts_flow_active = False
            self._open_next_dark_pacts_prompt(game)

    # ---------------- Voice of Command prompts ----------------

    def _on_voice_of_command_prompt(self, player=None, phase_name=None, trigger=None, game=None, **_kwargs):
        if player is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        if self._voice_of_command_flow_active:
            self._pending_voice_of_command_queue.append((player, phase_name, trigger))
            return
        self._pending_voice_of_command_queue.append((player, phase_name, trigger))
        self._open_next_voice_of_command_prompt(game or self.game)

    def _open_next_voice_of_command_prompt(self, game):
        q = list(getattr(self, "_pending_voice_of_command_queue", []) or [])
        if not q:
            self._pending_voice_of_command_queue = []
            self._voice_of_command_flow_active = False
            return
        player, phase_name, trigger = q.pop(0)
        self._pending_voice_of_command_queue = q

        if player is None:
            self._open_next_voice_of_command_prompt(game)
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            self._open_next_voice_of_command_prompt(game)
            return
        mgr = getattr(army, "voice_of_command", None)
        if mgr is None or not getattr(mgr, "_army_has_voice", lambda: False)():
            self._open_next_voice_of_command_prompt(game)
            return

        self._voice_of_command_flow_active = True
        self._open_voice_of_command_officer_dialog(player, game, phase_name, trigger)

    def _end_voice_of_command_flow(self, game):
        self._voice_of_command_flow_active = False
        self._open_next_voice_of_command_prompt(game)

    def _open_voice_of_command_officer_dialog(self, player, game, phase_name, trigger):
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            self._end_voice_of_command_flow(game)
            return
        mgr = getattr(army, "voice_of_command", None)
        if mgr is None or not getattr(mgr, "_army_has_voice", lambda: False)():
            self._end_voice_of_command_flow(game)
            return

        try:
            officers = list(mgr.get_eligible_officers(game=game, player=player, phase_name=phase_name, trigger=trigger) or [])
        except Exception:
            officers = []
        if not officers:
            self._end_voice_of_command_flow(game)
            return

        battle_round = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        choices = []
        used = set()
        for officer in officers:
            try:
                remaining = int(mgr.orders_remaining(officer, battle_round))
            except Exception:
                remaining = 0
            label = f"{getattr(officer, 'name', 'Officer')} ({remaining} order{'s' if remaining != 1 else ''} remaining)"
            base = label
            idx = 2
            while label in used:
                label = f"{base} [{idx}]"
                idx += 1
            used.add(label)
            choices.append(SimpleNamespace(name=label, unit=officer, remaining=remaining))

        if self.voice_of_command_officer_dialog is None:
            try:
                from .dialogs import QuarrySelectionDialog
                sw, sh = self.screen.get_width(), self.screen.get_height()
                self.voice_of_command_officer_dialog = QuarrySelectionDialog(sw, sh)
            except Exception:
                self.voice_of_command_officer_dialog = None
        if self.voice_of_command_officer_dialog is None:
            self._end_voice_of_command_flow(game)
            return

        def _on_confirm(choice):
            officer = getattr(choice, "unit", None) if choice is not None else None
            if officer is None:
                self._end_voice_of_command_flow(game)
                return
            self._open_voice_of_command_order_dialog(player, game, phase_name, trigger, officer)

        def _on_cancel():
            self._end_voice_of_command_flow(game)

        subtitle = "Choose an officer to issue orders."
        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from .decision_ui_utils import option_id_for_action

        options = [
            DecisionOption.create("Skip orders", payload={"action": "skip"}),
        ]
        for choice in choices:
            unit = getattr(choice, "unit", None)
            if unit is None:
                continue
            options.append(
                DecisionOption.create(
                    getattr(choice, "name", "Officer"),
                    payload={"target_unit_id": get_entity_id(unit)},
                )
            )

        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Select an officer to issue orders.",
            player_id=getattr(player, "id", None),
            options=options,
            context={"phase_name": phase_name or "", "trigger": trigger or ""},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_confirm(option_id: str):
            value, apply_result = resolve_decision_value(self.game, req, option_id)
            if apply_result is None or not getattr(apply_result, "ok", False) or value is None:
                self._end_voice_of_command_flow(game)
                return
            self._open_voice_of_command_order_dialog(player, game, phase_name, trigger, value)

        def _on_cancel():
            skip_id = option_id_for_action(req, "skip")
            if skip_id:
                resolve_decision_value(self.game, req, skip_id)
            self._end_voice_of_command_flow(game)

        self.voice_of_command_officer_dialog.show(
            title="Voice of Command",
            header="Select an officer.",
            subtitle=subtitle,
            on_confirm=_on_confirm,
            on_cancel=_on_cancel,
            decision_request=req,
        )
        try:
            self.dialog_manager.open(self.voice_of_command_officer_dialog, modal=True)
        except Exception:
            self._end_voice_of_command_flow(game)

    def _open_voice_of_command_order_dialog(self, player, game, phase_name, trigger, officer):
        if officer is None:
            self._open_voice_of_command_officer_dialog(player, game, phase_name, trigger)
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            self._end_voice_of_command_flow(game)
            return
        mgr = getattr(army, "voice_of_command", None)
        if mgr is None or not getattr(mgr, "_army_has_voice", lambda: False)():
            self._end_voice_of_command_flow(game)
            return

        battle_round = int(getattr(game, "turn", 0) or 0) if game is not None else 0
        try:
            remaining = int(mgr.orders_remaining(officer, battle_round))
        except Exception:
            remaining = 0
        if remaining <= 0:
            self._open_voice_of_command_officer_dialog(player, game, phase_name, trigger)
            return

        if self.voice_of_command_dialog is None:
            try:
                from .dialogs import VoiceOfCommandDialog
                sw, sh = self.screen.get_width(), self.screen.get_height()
                self.voice_of_command_dialog = VoiceOfCommandDialog(sw, sh)
            except Exception:
                self.voice_of_command_dialog = None
        if self.voice_of_command_dialog is None:
            self._end_voice_of_command_flow(game)
            return

        try:
            orders = mgr.get_available_orders(officer)
        except Exception:
            try:
                from ..rules.voice_of_command import ORDER_LIST
                orders = list(ORDER_LIST or [])
            except Exception:
                orders = []

        from ..engine.decision_kinds import DECISION_ISSUE_ORDER
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from .decision_ui_utils import option_id_for_action

        officer_id = get_entity_id(officer)
        army_id = get_entity_id(army) if army is not None else ""
        decision_options = [
            DecisionOption.create(
                "Skip orders",
                payload={"action": "skip", "officer_unit_id": officer_id, "army_id": army_id},
            )
        ]
        for order in list(orders or []):
            decision_options.append(
                DecisionOption.create(
                    getattr(order, "name", "Order"),
                    payload={
                        "officer_unit_id": officer_id,
                        "order_key": getattr(order, "key", ""),
                        "summary": getattr(order, "summary", ""),
                        "army_id": army_id,
                    },
                )
            )

        req = DecisionRequest.create(
            DECISION_ISSUE_ORDER,
            f"Select order for {getattr(officer, 'name', 'Officer')}",
            player_id=getattr(player, "id", None),
            options=decision_options,
            context={"officer_unit_id": officer_id, "army_id": army_id, "phase_name": phase_name or "", "trigger": trigger or ""},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_confirm(option_id: str):
            skip_id = option_id_for_action(req, "skip")
            if skip_id and option_id == skip_id:
                resolve_decision_value(self.game, req, option_id)
                self._open_voice_of_command_officer_dialog(player, game, phase_name, trigger)
                return
            self._voice_of_command_pending_order = {
                "request": req,
                "option_id": option_id,
                "officer": officer,
            }
            self._open_voice_of_command_target_dialog(player, game, phase_name, trigger, officer, None)

        def _on_cancel():
            skip_id = option_id_for_action(req, "skip")
            if skip_id:
                resolve_decision_value(self.game, req, skip_id)
            self._open_voice_of_command_officer_dialog(player, game, phase_name, trigger)

        self.voice_of_command_dialog.show(on_confirm=_on_confirm, on_cancel=_on_cancel, decision_request=req)
        try:
            self.dialog_manager.open(self.voice_of_command_dialog, modal=True)
        except Exception:
            self._end_voice_of_command_flow(game)

    def _open_voice_of_command_target_dialog(self, player, game, phase_name, trigger, officer, order):
        if officer is None:
            self._open_voice_of_command_officer_dialog(player, game, phase_name, trigger)
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            self._end_voice_of_command_flow(game)
            return
        mgr = getattr(army, "voice_of_command", None)
        if mgr is None or not getattr(mgr, "_army_has_voice", lambda: False)():
            self._end_voice_of_command_flow(game)
            return

        pending = getattr(self, "_voice_of_command_pending_order", None)
        order_key = ""
        order_label = "Order"
        if isinstance(pending, dict):
            req = pending.get("request")
            option_id = pending.get("option_id")
            if req is not None and option_id:
                for opt in list(getattr(req, "options", []) or []):
                    if opt.option_id == option_id:
                        payload = dict(getattr(opt, "payload", {}) or {})
                        order_key = str(payload.get("order_key", "") or "")
                        order_label = str(getattr(opt, "label", "Order") or "Order")
                        break
        if not order_key and order is not None:
            order_key = str(getattr(order, "key", "") or "")
            order_label = str(getattr(order, "name", "Order") or "Order")

        try:
            targets = list(mgr.get_eligible_targets(officer, game=game, order_key=order_key) or [])
        except Exception:
            targets = []
        if not targets:
            self._open_voice_of_command_order_dialog(player, game, phase_name, trigger, officer)
            return

        if self.voice_of_command_target_dialog is None:
            try:
                from .dialogs import QuarrySelectionDialog
                sw, sh = self.screen.get_width(), self.screen.get_height()
                self.voice_of_command_target_dialog = QuarrySelectionDialog(sw, sh)
            except Exception:
                self.voice_of_command_target_dialog = None
        if self.voice_of_command_target_dialog is None:
            self._end_voice_of_command_flow(game)
            return

        order_name = order_label or getattr(order, "name", "Order")
        header = f"{getattr(officer, 'name', 'Officer')} issues {order_name}."
        subtitle = "Choose an eligible friendly unit within 6\"."

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from .decision_ui_utils import option_id_for_action

        target_options = [
            DecisionOption.create("Cancel", payload={"action": "skip"}),
        ]
        for tgt in list(targets or []):
            target_options.append(
                DecisionOption.create(
                    getattr(tgt, "name", "Unit"),
                    payload={"target_unit_id": get_entity_id(tgt)},
                )
            )
        target_req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Select Voice of Command target.",
            player_id=getattr(player, "id", None),
            options=target_options,
            context={"officer_unit_id": get_entity_id(officer), "order_key": order_key},
        )
        if self.game is not None:
            self.game.request_decision(target_req)

        def _resolve_issue_order(target_unit):
            ok = False
            pending_order = getattr(self, "_voice_of_command_pending_order", None)
            req = pending_order.get("request") if isinstance(pending_order, dict) else None
            option_id = pending_order.get("option_id") if isinstance(pending_order, dict) else None
            if req is not None and option_id:
                payload = {"target_unit_id": get_entity_id(target_unit)}
                value, apply_result = resolve_decision_value(self.game, req, option_id, result_payload=payload)
                ok = bool(value) if apply_result is not None and getattr(apply_result, "ok", False) else False
            return ok

        def _on_target(option_id: str):
            value, apply_result = resolve_decision_value(self.game, target_req, option_id)
            if apply_result is None or not getattr(apply_result, "ok", False) or value is None:
                self._open_voice_of_command_order_dialog(player, game, phase_name, trigger, officer)
                return
            ok = _resolve_issue_order(value)
            if ok:
                target_unit = value
                try:
                    from ..utility.event_bus import append_action
                    append_action(
                        player,
                        f"Voice of Command: {order_name} from {getattr(officer, 'name', 'Officer')} to {getattr(target_unit, 'name', 'Unit')}",
                    )
                except Exception:
                    pass
                try:
                    if self.rule_detail_panel and self.rule_detail_panel.visible and isinstance(self._rule_panel_state, dict):
                        if self._rule_panel_state.get("player") is player and self._rule_panel_state.get("rule_type") == "army":
                            self._toggle_rule_panel(player, "army", force_refresh=True)
                except Exception:
                    pass
            battle_round = int(getattr(game, "turn", 0) or 0) if game is not None else 0
            try:
                remaining = int(mgr.orders_remaining(officer, battle_round))
            except Exception:
                remaining = 0
            if remaining > 0:
                self._open_voice_of_command_order_dialog(player, game, phase_name, trigger, officer)
            else:
                self._open_voice_of_command_officer_dialog(player, game, phase_name, trigger)

        def _on_cancel():
            skip_id = option_id_for_action(target_req, "skip")
            if skip_id:
                resolve_decision_value(self.game, target_req, skip_id)
            pending_order = getattr(self, "_voice_of_command_pending_order", None)
            if isinstance(pending_order, dict):
                req = pending_order.get("request")
                option_id = pending_order.get("option_id")
                if req is not None and option_id:
                    resolve_decision_value(self.game, req, option_id, result_payload={"action": "skip"})
            self._open_voice_of_command_order_dialog(player, game, phase_name, trigger, officer)

        self.voice_of_command_target_dialog.show(
            title=f"{order_name} Target",
            header=header,
            subtitle=subtitle,
            on_confirm=_on_target,
            on_cancel=_on_cancel,
            decision_request=target_req,
        )
        try:
            self.dialog_manager.open(self.voice_of_command_target_dialog, modal=True)
        except Exception:
            self._end_voice_of_command_flow(game)

    # ---------------- Gate of Infinity prompts ----------------

    def _on_gate_of_infinity_prompt(self, player=None, max_units=None, game=None, **_kwargs):
        if player is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        try:
            cap = int(max_units or 0)
        except Exception:
            cap = 0
        if self._gate_of_infinity_flow_active:
            self._pending_gate_of_infinity_queue.append((player, cap))
            return
        self._pending_gate_of_infinity_queue.append((player, cap))
        self._open_next_gate_of_infinity_prompt(game or self.game)

    def _finish_gate_of_infinity_flow(self, game):
        self._gate_of_infinity_flow_active = False
        self._open_next_gate_of_infinity_prompt(game)

    def _open_next_gate_of_infinity_prompt(self, game):
        q = list(getattr(self, "_pending_gate_of_infinity_queue", []) or [])
        if not q:
            self._pending_gate_of_infinity_queue = []
            self._gate_of_infinity_flow_active = False
            return
        player, cap = q.pop(0)
        self._pending_gate_of_infinity_queue = q

        if player is None:
            self._open_next_gate_of_infinity_prompt(game)
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            self._open_next_gate_of_infinity_prompt(game)
            return
        mgr = getattr(army, "gate_of_infinity", None)
        if mgr is None or not getattr(mgr, "_army_has_gate", lambda: False)():
            self._open_next_gate_of_infinity_prompt(game)
            return
        if cap <= 0:
            try:
                cap = int(mgr.get_max_units_for_battlefield(game))
            except Exception:
                cap = 0
        if cap <= 0:
            self._open_next_gate_of_infinity_prompt(game)
            return
        try:
            eligible = list(mgr.get_eligible_units(game=game, player=player) or [])
        except Exception:
            eligible = []
        if not eligible:
            self._open_next_gate_of_infinity_prompt(game)
            return

        self._gate_of_infinity_flow_active = True
        self._open_gate_of_infinity_dialog(player, game, eligible, cap)

    def _open_gate_of_infinity_dialog(self, player, game, eligible, remaining: int):
        if remaining <= 0 or not eligible:
            self._finish_gate_of_infinity_flow(game)
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            self._finish_gate_of_infinity_flow(game)
            return
        mgr = getattr(army, "gate_of_infinity", None)
        if mgr is None:
            self._finish_gate_of_infinity_flow(game)
            return

        if self.gate_of_infinity_dialog is None:
            try:
                from .dialogs import QuarrySelectionDialog
                sw, sh = self.screen.get_width(), self.screen.get_height()
                self.gate_of_infinity_dialog = QuarrySelectionDialog(sw, sh)
            except Exception:
                self.gate_of_infinity_dialog = None
        if self.gate_of_infinity_dialog is None:
            self._finish_gate_of_infinity_flow(game)
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id

        options = [
            DecisionOption.create("Done", payload={"action": "skip"}),
        ]
        for unit in list(eligible or []):
            options.append(
                DecisionOption.create(
                    getattr(unit, "name", "Unit"),
                    payload={"target_unit_id": get_entity_id(unit)},
                )
            )
        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Select Gate of Infinity unit.",
            player_id=getattr(player, "id", None),
            options=options,
            context={"ability": "gate_of_infinity", "remaining": int(remaining or 0)},
        )
        if self.game is not None:
            self.game.request_decision(req)

        header = f"Select up to {remaining} unit{'s' if remaining != 1 else ''} to enter Strategic Reserves."
        subtitle = "Eligible units must be on the battlefield and not in Engagement Range."

        def _on_confirm(option_id: str):
            value, apply_result = resolve_decision_value(self.game, req, option_id)
            if apply_result is None or not getattr(apply_result, "ok", False) or value is None:
                self._finish_gate_of_infinity_flow(game)
                return
            unit = value
            try:
                unit = value.get_attached_unit_root()
            except Exception:
                unit = value
            try:
                mgr.send_units_to_strategic_reserves([unit], game=game)
            except Exception:
                pass
            try:
                from ..utility.event_bus import append_action
                append_action(
                    player,
                    f"Gate of Infinity: {getattr(unit, 'name', 'Unit')} placed into Strategic Reserves",
                )
            except Exception:
                pass
            try:
                if self.rule_detail_panel and self.rule_detail_panel.visible and isinstance(self._rule_panel_state, dict):
                    if self._rule_panel_state.get("player") is player and self._rule_panel_state.get("rule_type") == "army":
                        self._toggle_rule_panel(player, "army", force_refresh=True)
            except Exception:
                pass

            new_eligible = [u for u in eligible if u is not unit]
            self._open_gate_of_infinity_dialog(player, game, new_eligible, remaining - 1)

        from .decision_ui_utils import option_id_for_action

        def _on_cancel():
            skip_id = option_id_for_action(req, "skip")
            if skip_id:
                resolve_decision_value(self.game, req, skip_id, result_payload={"skipped": True})
            self._finish_gate_of_infinity_flow(game)

        self.gate_of_infinity_dialog.show(
            title="Gate of Infinity",
            header=header,
            subtitle=subtitle,
            on_confirm=_on_confirm,
            on_cancel=_on_cancel,
            decision_request=req,
        )
        try:
            self.dialog_manager.open(self.gate_of_infinity_dialog, modal=True)
        except Exception:
            self._finish_gate_of_infinity_flow(game)

    # ---------------- End of Opponent Turn: Strategic Reserves prompts ----------------

    def _on_opponent_turn_strategic_reserves_prompt(self, player=None, units=None, game=None, **_kwargs):
        if player is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        entries = []
        for item in list(units or []):
            if isinstance(item, dict):
                unit = item.get("unit")
                ability = item.get("ability")
            else:
                unit = item
                ability = None
            if unit is None:
                continue
            entries.append((player, unit, ability))
        if not entries:
            return

        if self._opponent_turn_reserves_flow_active:
            self._pending_opponent_turn_reserves_queue.extend(entries)
            return

        self._pending_opponent_turn_reserves_queue.extend(entries)
        self._open_next_opponent_turn_strategic_reserves_prompt(game or self.game)

    def _open_next_opponent_turn_strategic_reserves_prompt(self, game):
        q = list(getattr(self, "_pending_opponent_turn_reserves_queue", []) or [])
        if not q:
            self._pending_opponent_turn_reserves_queue = []
            self._opponent_turn_reserves_flow_active = False
            return
        player, unit, ability = q.pop(0)
        self._pending_opponent_turn_reserves_queue = q

        if player is None or unit is None:
            self._open_next_opponent_turn_strategic_reserves_prompt(game)
            return

        def _eligible(u):
            try:
                if not u.is_alive():
                    return False
            except Exception:
                pass
            try:
                if not getattr(u, "deployed", False):
                    return False
                if str(getattr(u, "reserve_status", "deployed")) != "deployed":
                    return False
                if bool(getattr(u, "embarked_in", None)) or bool(getattr(u, "is_embarked", False)):
                    return False
            except Exception:
                return False
            gm = getattr(game, "map", None) if game is not None else None
            if gm is None:
                return False
            try:
                for enemy in list(gm.get_enemy_units(u) or []):
                    if not getattr(enemy, "is_alive", lambda: True)():
                        continue
                    if not getattr(enemy, "deployed", True):
                        continue
                    if gm.is_within_engagement_range(u, enemy):
                        return False
            except Exception:
                return False
            return True

        if not _eligible(unit):
            self._open_next_opponent_turn_strategic_reserves_prompt(game)
            return

        self._opponent_turn_reserves_flow_active = True
        ability_name = None
        if isinstance(ability, dict):
            ability_name = ability.get("name")
        title = ability_name or "Strategic Reserves"
        msg = (
            f"{getattr(unit, 'name', 'Unit')} is not within Engagement Range.\n"
            "Remove it from the battlefield and place it into Strategic Reserves?"
        )

        def _done(chosen: bool):
            if chosen:
                try:
                    unit.enter_strategic_reserves_midgame(
                        game=game,
                        game_map=getattr(game, "map", None),
                        reason="end of opponent turn",
                    )
                except Exception:
                    pass
                try:
                    from ..utility.event_bus import append_action
                    if player is not None:
                        ab_name = ability_name or "Strategic Reserves"
                        append_action(player, f"{ab_name}: {getattr(unit, 'name', 'Unit')} placed into Strategic Reserves.")
                except Exception:
                    pass
            self._open_next_opponent_turn_strategic_reserves_prompt(game)

        try:
            self._request_yes_no(title, msg, "Yes", "No", _done, player=player)
        except Exception:
            _done(False)

    # ---------------- Martial Ka'tah prompts ----------------

    def _on_martial_katah_prompt(self, player=None, unit=None, phase_name=None, game=None, **_kwargs):
        if player is None or unit is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        if self._martial_katah_flow_active:
            self._pending_martial_katah_queue.append((player, unit, phase_name))
            return
        self._pending_martial_katah_queue.append((player, unit, phase_name))
        self._open_next_martial_katah_prompt(game or self.game)

    def _open_next_martial_katah_prompt(self, game):
        q = list(getattr(self, "_pending_martial_katah_queue", []) or [])
        if not q:
            self._pending_martial_katah_queue = []
            self._martial_katah_flow_active = False
            return
        player, unit, _phase_name = q.pop(0)
        self._pending_martial_katah_queue = q

        if player is None or unit is None:
            self._open_next_martial_katah_prompt(game)
            return
        try:
            if not unit.attached_unit_has_martial_katah():
                self._open_next_martial_katah_prompt(game)
                return
        except Exception:
            self._open_next_martial_katah_prompt(game)
            return

        if self.martial_katah_dialog is None:
            try:
                from .dialogs import MartialKatahDialog
                sw, sh = self.screen.get_width(), self.screen.get_height()
                self.martial_katah_dialog = MartialKatahDialog(sw, sh)
            except Exception:
                self.martial_katah_dialog = None
        if self.martial_katah_dialog is None:
            self._martial_katah_flow_active = False
            return

        subtitle = f"{getattr(unit, 'name', 'Unit')} selected to fight."
        from ..engine.decision_kinds import DECISION_CHOOSE_MARTIAL_KATAH
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id
        from .decision_ui_utils import option_id_for_payload

        unit_id = get_entity_id(unit)
        options = [
            DecisionOption.create(
                "Dacatarai Stance",
                payload={
                    "unit_id": unit_id,
                    "choice_key": "DACATARAI",
                    "summary": "Melee weapons gain [SUSTAINED HITS 1] for this fight.",
                },
            ),
            DecisionOption.create(
                "Rendax Stance",
                payload={
                    "unit_id": unit_id,
                    "choice_key": "RENDAX",
                    "summary": "Melee weapons gain [LETHAL HITS] for this fight.",
                },
            ),
        ]
        req = DecisionRequest.create(
            DECISION_CHOOSE_MARTIAL_KATAH,
            "Select Martial Ka'tah stance.",
            player_id=getattr(getattr(unit.get_parent_army(), "player", None), "id", None),
            options=options,
            context={"unit_id": unit_id},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_confirm(option_id: str):
            resolve_decision_value(self.game, req, option_id)
            self._martial_katah_flow_active = False
            self._open_next_martial_katah_prompt(game)

        def _on_cancel():
            default_id = option_id_for_payload(req, "choice_key", "DACATARAI")
            if default_id:
                resolve_decision_value(self.game, req, default_id)
            self._martial_katah_flow_active = False
            self._open_next_martial_katah_prompt(game)

        self._martial_katah_flow_active = True
        self.martial_katah_dialog.show(on_confirm=_on_confirm, on_cancel=_on_cancel, subtitle=subtitle, decision_request=req)
        try:
            self.dialog_manager.open(self.martial_katah_dialog, modal=True)
        except Exception:
            self._martial_katah_flow_active = False
            self._open_next_martial_katah_prompt(game)

    # ---------------- Emperor's Children prompts ----------------

    def _on_emperors_children_pledge_prompt(self, player=None, game=None, battle_round: int = 0, max_value: int = 1, default_value: int = 1, manager=None, **_kwargs):
        if player is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        if self._emperors_children_pledge_flow_active:
            self._pending_emperors_children_pledge_queue.append((player, game, battle_round, max_value, default_value, manager))
            return
        self._pending_emperors_children_pledge_queue.append((player, game, battle_round, max_value, default_value, manager))
        self._open_next_emperors_children_pledge_prompt(game or self.game)

    def _open_next_emperors_children_pledge_prompt(self, game):
        q = list(getattr(self, "_pending_emperors_children_pledge_queue", []) or [])
        if not q:
            self._pending_emperors_children_pledge_queue = []
            self._emperors_children_pledge_flow_active = False
            return
        player, game_ctx, battle_round, max_value, default_value, manager = q.pop(0)
        self._pending_emperors_children_pledge_queue = q

        game_ctx = game_ctx or game or self.game
        if player is None or game_ctx is None:
            self._open_next_emperors_children_pledge_prompt(game_ctx)
            return
        mgr = manager
        if mgr is None:
            try:
                army = player.get_army()
            except Exception:
                army = None
            mgr = getattr(army, "emperors_children", None) if army is not None else None
        if mgr is None:
            self._open_next_emperors_children_pledge_prompt(game_ctx)
            return

        if self.pledge_selection_dialog is None:
            try:
                from .dialogs import PledgeSelectionDialog
                sw, sh = self.screen.get_width(), self.screen.get_height()
                self.pledge_selection_dialog = PledgeSelectionDialog(sw, sh)
            except Exception:
                self.pledge_selection_dialog = None
        if self.pledge_selection_dialog is None:
            self._emperors_children_pledge_flow_active = False
            return

        try:
            max_value = max(1, int(max_value or 1))
        except Exception:
            max_value = 1
        try:
            default_value = int(default_value or 1)
        except Exception:
            default_value = 1
        default_value = max(1, min(default_value, max_value))

        subtitle = f"Battle round {int(battle_round or getattr(game_ctx, 'turn', 0) or 0)}"

        from ..engine.decision_kinds import DECISION_CHOOSE_PLEDGE
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id
        from .decision_ui_utils import option_id_for_payload

        army_id = get_entity_id(player.get_army()) if player is not None else ""
        options = []
        for value in range(1, max_value + 1):
            options.append(
                DecisionOption.create(
                    f"{value}",
                    payload={"pledge_value": int(value), "army_id": army_id},
                )
            )
        req = DecisionRequest.create(
            DECISION_CHOOSE_PLEDGE,
            "Select pledge value.",
            player_id=getattr(player, "id", None),
            options=options,
            context={"army_id": army_id, "battle_round": int(battle_round or 0), "max_value": max_value},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_confirm(option_id: str):
            resolve_decision_value(self.game, req, option_id)
            self._emperors_children_pledge_flow_active = False
            try:
                if self.rule_detail_panel and self.rule_detail_panel.visible and isinstance(self._rule_panel_state, dict):
                    if self._rule_panel_state.get("player") is player and self._rule_panel_state.get("rule_type") == "detachment":
                        self._toggle_rule_panel(player, "detachment", force_refresh=True)
            except Exception:
                pass
            self._open_next_emperors_children_pledge_prompt(game_ctx)

        def _on_cancel():
            default_id = option_id_for_payload(req, "pledge_value", int(default_value))
            if default_id:
                resolve_decision_value(self.game, req, default_id)
            self._emperors_children_pledge_flow_active = False
            self._open_next_emperors_children_pledge_prompt(game_ctx)

        self._emperors_children_pledge_flow_active = True
        self.pledge_selection_dialog.show(
            default_value=default_value,
            on_confirm=_on_confirm,
            on_cancel=_on_cancel,
            subtitle=subtitle,
            decision_request=req,
        )
        try:
            self.dialog_manager.open(self.pledge_selection_dialog, modal=True)
        except Exception:
            self._emperors_children_pledge_flow_active = False
            self._open_next_emperors_children_pledge_prompt(game_ctx)

    def _on_emperors_children_exquisite_prompt(self, player=None, unit=None, phase_name=None, game=None, **_kwargs):
        if player is None or unit is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        if self._emperors_children_exquisite_flow_active:
            self._pending_emperors_children_exquisite_queue.append((player, unit, phase_name, game))
            return
        self._pending_emperors_children_exquisite_queue.append((player, unit, phase_name, game))
        self._open_next_emperors_children_exquisite_prompt(game or self.game)

    def _open_next_emperors_children_exquisite_prompt(self, game):
        q = list(getattr(self, "_pending_emperors_children_exquisite_queue", []) or [])
        if not q:
            self._pending_emperors_children_exquisite_queue = []
            self._emperors_children_exquisite_flow_active = False
            return
        player, unit, _phase_name, game_ctx = q.pop(0)
        self._pending_emperors_children_exquisite_queue = q

        game_ctx = game_ctx or game or self.game
        if player is None or unit is None:
            self._open_next_emperors_children_exquisite_prompt(game_ctx)
            return

        if self.martial_katah_dialog is None:
            try:
                from .dialogs import MartialKatahDialog
                sw, sh = self.screen.get_width(), self.screen.get_height()
                self.martial_katah_dialog = MartialKatahDialog(sw, sh)
            except Exception:
                self.martial_katah_dialog = None
        if self.martial_katah_dialog is None:
            self._emperors_children_exquisite_flow_active = False
            return

        subtitle = f"{getattr(unit, 'name', 'Unit')} selected to fight."
        from ..engine.decision_kinds import DECISION_CHOOSE_MARTIAL_KATAH
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id
        from .decision_ui_utils import option_id_for_payload

        unit_id = get_entity_id(unit)
        options = [
            DecisionOption.create(
                "Lethal Hits",
                payload={
                    "unit_id": unit_id,
                    "choice_key": "LETHAL",
                    "selection_kind": "exquisite_swordsmanship",
                    "summary": "Melee weapons gain [LETHAL HITS] for this fight.",
                },
            ),
            DecisionOption.create(
                "Sustained Hits 1",
                payload={
                    "unit_id": unit_id,
                    "choice_key": "SUSTAINED",
                    "selection_kind": "exquisite_swordsmanship",
                    "summary": "Melee weapons gain [SUSTAINED HITS 1] for this fight.",
                },
            ),
        ]
        req = DecisionRequest.create(
            DECISION_CHOOSE_MARTIAL_KATAH,
            "Select Exquisite Swordsmanship stance.",
            player_id=getattr(getattr(unit.get_parent_army(), "player", None), "id", None),
            options=options,
            context={"unit_id": unit_id, "selection_kind": "exquisite_swordsmanship"},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_confirm(option_id: str):
            resolve_decision_value(self.game, req, option_id)
            self._emperors_children_exquisite_flow_active = False
            self._open_next_emperors_children_exquisite_prompt(game_ctx)

        def _on_cancel():
            default_id = option_id_for_payload(req, "choice_key", "LETHAL")
            if default_id:
                resolve_decision_value(self.game, req, default_id)
            self._emperors_children_exquisite_flow_active = False
            self._open_next_emperors_children_exquisite_prompt(game_ctx)

        self._emperors_children_exquisite_flow_active = True
        self.martial_katah_dialog.show(on_confirm=_on_confirm, on_cancel=_on_cancel, subtitle=subtitle, title="Exquisite Swordsmanship", decision_request=req)
        try:
            self.dialog_manager.open(self.martial_katah_dialog, modal=True)
        except Exception:
            self._emperors_children_exquisite_flow_active = False
            self._open_next_emperors_children_exquisite_prompt(game_ctx)

    def _prompt_exquisite_swordsmanship_choice(self, unit, on_done=None) -> None:
        if unit is None:
            if callable(on_done):
                on_done()
            return
        player = None
        try:
            player = unit.get_parent_army().player
        except Exception:
            player = None
        is_human = False
        try:
            is_human = bool(getattr(player, "has_control", lambda: False)())
        except Exception:
            is_human = False
        if self.martial_katah_dialog is None:
            try:
                from .dialogs import MartialKatahDialog
                sw, sh = self.screen.get_width(), self.screen.get_height()
                self.martial_katah_dialog = MartialKatahDialog(sw, sh)
            except Exception:
                self.martial_katah_dialog = None
        if self.martial_katah_dialog is None:
            try:
                unit.set_exquisite_swordsmanship_choice("LETHAL")
            except Exception:
                pass
            if callable(on_done):
                on_done()
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_MARTIAL_KATAH
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.entity_ids import get_entity_id
        from .decision_ui_utils import option_id_for_payload

        unit_id = get_entity_id(unit)
        options = [
            DecisionOption.create(
                "Lethal Hits",
                payload={
                    "unit_id": unit_id,
                    "choice_key": "LETHAL",
                    "selection_kind": "exquisite_swordsmanship",
                    "summary": "Melee weapons gain [LETHAL HITS] for this fight.",
                },
            ),
            DecisionOption.create(
                "Sustained Hits 1",
                payload={
                    "unit_id": unit_id,
                    "choice_key": "SUSTAINED",
                    "selection_kind": "exquisite_swordsmanship",
                    "summary": "Melee weapons gain [SUSTAINED HITS 1] for this fight.",
                },
            ),
        ]
        req = DecisionRequest.create(
            DECISION_CHOOSE_MARTIAL_KATAH,
            "Select Exquisite Swordsmanship stance.",
            player_id=getattr(player, "id", None),
            options=options,
            context={"unit_id": unit_id, "selection_kind": "exquisite_swordsmanship"},
        )
        if self.game is not None:
            self.game.request_decision(req)

        if not is_human:
            registrar = getattr(getattr(self, "phase_manager", None), "_register_decision_callback", None)
            if callable(registrar):
                def _on_resolved(_request, _result):
                    if callable(on_done):
                        on_done()
                registrar(req, _on_resolved)
                return
            if callable(on_done):
                on_done()
            return

        from ..utility.decision_utils import resolve_decision_value
        def _finish(option_id: str):
            resolve_decision_value(self.game, req, option_id)
            if callable(on_done):
                on_done()

        def _on_confirm(option_id: str):
            _finish(option_id)

        def _on_cancel():
            default_id = option_id_for_payload(req, "choice_key", "LETHAL")
            if default_id:
                _finish(default_id)
            else:
                if callable(on_done):
                    on_done()

        try:
            self.martial_katah_dialog.show(
                on_confirm=_on_confirm,
                on_cancel=_on_cancel,
                subtitle=f"{getattr(unit, 'name', 'Unit')} fights again.",
                title="Exquisite Swordsmanship",
                decision_request=req,
            )
            self.dialog_manager.open(self.martial_katah_dialog, modal=True)
        except Exception:
            try:
                unit.set_exquisite_swordsmanship_choice("LETHAL")
            except Exception:
                pass
            if callable(on_done):
                on_done()

    def _on_emperors_children_sensational_prompt(self, player=None, unit=None, phase_name=None, game=None, **_kwargs):
        if player is None or unit is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        if self._emperors_children_sensational_flow_active:
            self._pending_emperors_children_sensational_queue.append((player, unit, phase_name, game))
            return
        self._pending_emperors_children_sensational_queue.append((player, unit, phase_name, game))
        self._open_next_emperors_children_sensational_prompt(game or self.game)

    def _open_next_emperors_children_sensational_prompt(self, game):
        q = list(getattr(self, "_pending_emperors_children_sensational_queue", []) or [])
        if not q:
            self._pending_emperors_children_sensational_queue = []
            self._emperors_children_sensational_flow_active = False
            return
        player, unit, _phase_name, game_ctx = q.pop(0)
        self._pending_emperors_children_sensational_queue = q

        game_ctx = game_ctx or game or self.game
        if player is None or unit is None:
            self._open_next_emperors_children_sensational_prompt(game_ctx)
            return

        title = "Sensational Performance"
        msg = f"Activate Sensational Performance for {getattr(unit, 'name', 'Unit')}?"

        def _done(chosen: bool):
            if chosen:
                try:
                    sr = getattr(unit, "special_rules", None)
                    if not isinstance(sr, dict):
                        sr = {}
                    sr["sensational_performance_active"] = True
                    sr["sensational_performance_expires_phase"] = "FIGHT_PHASE"
                    sr["sensational_performance_strength_bonus"] = 1
                    sr["sensational_performance_ap_bonus"] = 1
                    unit.special_rules = sr
                except Exception:
                    pass
            try:
                from ..utility.event_bus import append_action
                if player is not None:
                    action = "activated" if chosen else "skipped"
                    append_action(player, f"Sensational Performance: {getattr(unit, 'name', 'Unit')} {action}.")
            except Exception:
                pass
            self._emperors_children_sensational_flow_active = False
            self._open_next_emperors_children_sensational_prompt(game_ctx)

        try:
            self._emperors_children_sensational_flow_active = True
            self._request_yes_no(title, msg, "Use", "Skip", _done)
        except Exception:
            self._emperors_children_sensational_flow_active = False
            self._open_next_emperors_children_sensational_prompt(game_ctx)

    def _on_emperors_children_pact_points_updated(self, player=None, **_kwargs):
        if player is None:
            return
        try:
            if self.rule_detail_panel and self.rule_detail_panel.visible and isinstance(self._rule_panel_state, dict):
                if self._rule_panel_state.get("player") is player and self._rule_panel_state.get("rule_type") == "detachment":
                    self._toggle_rule_panel(player, "detachment", force_refresh=True)
        except Exception:
            pass

    # ---------------- Blood Tithe prompts ----------------

    def _on_blood_tithe_prompt(
        self,
        player=None,
        game=None,
        manager=None,
        options=None,
        points: int = 0,
        timing: str = "",
        source: str = "",
        ignore_command_phase_limit: bool = False,
        **_kwargs,
    ):
        if player is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        payload = (player, game, manager, options, points, timing, source, ignore_command_phase_limit)
        if self._blood_tithe_flow_active:
            self._pending_blood_tithe_queue.append(payload)
            return
        self._pending_blood_tithe_queue.append(payload)
        self._open_next_blood_tithe_prompt(game or self.game)

    def _open_next_blood_tithe_prompt(self, game):
        q = list(getattr(self, "_pending_blood_tithe_queue", []) or [])
        if not q:
            self._pending_blood_tithe_queue = []
            self._blood_tithe_flow_active = False
            return
        player, game_ctx, manager, options, points, timing, source, ignore_limit = q.pop(0)
        self._pending_blood_tithe_queue = q

        game_ctx = game_ctx or game or self.game
        if player is None or game_ctx is None:
            self._open_next_blood_tithe_prompt(game_ctx)
            return

        if manager is None:
            try:
                army = player.get_army()
            except Exception:
                army = None
            manager = getattr(army, "world_eaters_detachments", None) if army is not None else None
        if manager is None:
            self._open_next_blood_tithe_prompt(game_ctx)
            return

        try:
            option_list = list(options or manager.get_available_blood_tithe_abilities() or [])
        except Exception:
            option_list = []
        if not option_list:
            self._open_next_blood_tithe_prompt(game_ctx)
            return

        try:
            points = int(points or getattr(manager, "blood_tithe_points", 0) or 0)
        except Exception:
            points = 0

        if self.blood_tithe_dialog is None:
            try:
                sw, sh = self.screen.get_width(), self.screen.get_height()
                from .dialogs import BloodTitheDialog
                self.blood_tithe_dialog = BloodTitheDialog(sw, sh)
            except Exception:
                self.blood_tithe_dialog = None
        if self.blood_tithe_dialog is None:
            self._open_next_blood_tithe_prompt(game_ctx)
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_BLOOD_TITHE
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id
        from .decision_ui_utils import option_id_for_action

        def _finish():
            self._blood_tithe_flow_active = False
            self._open_next_blood_tithe_prompt(game_ctx)

        army_id = get_entity_id(player.get_army()) if player is not None else ""
        options = [DecisionOption.create("Skip", payload={"action": "skip"})]
        option_labels = {}
        for choice in option_list:
            key = getattr(choice, "key", None) or getattr(choice, "choice_key", None)
            if not key:
                continue
            label = getattr(choice, "name", None) or str(choice)
            payload = {
                "ability_key": str(key),
                "army_id": army_id,
                "timing": timing,
                "cost": getattr(choice, "cost", None),
                "summary": getattr(choice, "summary", ""),
            }
            opt = DecisionOption.create(label, payload=payload)
            options.append(opt)
            option_labels[opt.option_id] = label
        req = DecisionRequest.create(
            DECISION_CHOOSE_BLOOD_TITHE,
            "Select a Blood Tithe ability.",
            player_id=getattr(player, "id", None),
            options=options,
            context={
                "army_id": army_id,
                "timing": timing,
                "ignore_command_phase_limit": bool(ignore_limit),
            },
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_confirm(option_id: str):
            value, apply_result = resolve_decision_value(self.game, req, option_id)
            if apply_result is not None and getattr(apply_result, "ok", False) and value:
                try:
                    from ..utility.event_bus import append_action
                    label = option_labels.get(option_id, "Blood Tithe")
                    append_action(player, f"Blood Tithe: {label}")
                except Exception:
                    pass
            _finish()

        def _on_cancel():
            skip_id = option_id_for_action(req, "skip")
            if skip_id:
                resolve_decision_value(self.game, req, skip_id)
            _finish()

        self._blood_tithe_flow_active = True
        try:
            self.blood_tithe_dialog.show(
                points=points,
                timing=timing,
                source=source,
                on_confirm=_on_confirm,
                on_cancel=_on_cancel,
                decision_request=req,
            )
            self.dialog_manager.open(self.blood_tithe_dialog, modal=True)
        except Exception:
            self._blood_tithe_flow_active = False
            self._open_next_blood_tithe_prompt(game_ctx)

    def _on_blood_tithe_updated(self, player=None, **_kwargs):
        if player is None:
            return
        try:
            if self.rule_detail_panel and self.rule_detail_panel.visible and isinstance(self._rule_panel_state, dict):
                if self._rule_panel_state.get("player") is player and self._rule_panel_state.get("rule_type") == "detachment":
                    self._toggle_rule_panel(player, "detachment", force_refresh=True)
        except Exception:
            pass

    # ---------------- Power from Pain prompts ----------------

    def _on_pain_token_prompt(self, player=None, unit=None, trigger=None, abilities=None, game=None, **_kwargs):
        if player is None or unit is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        if self._pain_flow_active:
            self._pending_pain_prompt_queue.append((player, unit, trigger, abilities, game))
            return
        self._pending_pain_prompt_queue.append((player, unit, trigger, abilities, game))
        self._open_next_pain_prompt(game or self.game)

    def _open_next_pain_prompt(self, game):
        q = list(getattr(self, "_pending_pain_prompt_queue", []) or [])
        if not q:
            self._pending_pain_prompt_queue = []
            self._pain_flow_active = False
            return
        player, unit, trigger, abilities, game_ctx = q.pop(0)
        self._pending_pain_prompt_queue = q

        game_ctx = game_ctx or game or self.game
        if player is None or unit is None or game_ctx is None:
            self._open_next_pain_prompt(game_ctx)
            return

        mgr = self._get_power_from_pain_manager(player)
        if mgr is None:
            self._open_next_pain_prompt(game_ctx)
            return

        try:
            ability_list = list(abilities or mgr.get_applicable_pain_ability_names(unit, trigger=trigger or "", game=game_ctx))
        except Exception:
            ability_list = []
        if not ability_list:
            self._open_next_pain_prompt(game_ctx)
            return

        tokens = int(getattr(mgr, "tokens", 0) or 0)
        if tokens <= 0:
            self._open_next_pain_prompt(game_ctx)
            return

        phase_label = str(getattr(getattr(game_ctx, "phase", None), "name", "") or "").replace("_", " ").title()
        ability_text = ", ".join(ability_list)
        title = "Power from Pain"
        msg = (
            f"{getattr(unit, 'name', 'Unit')} can be Empowered.\n\n"
            f"Spend 1 Pain token to activate: {ability_text}.\n"
            f"Phase: {phase_label or 'Current phase'}\n"
            f"Tokens available: {tokens}"
        )

        def _done(chosen: bool):
            if chosen:
                try:
                    mgr.empower_unit_for_trigger(unit, trigger=trigger or "", game=game_ctx)
                except Exception:
                    pass
            self._pain_flow_active = False
            self._open_next_pain_prompt(game_ctx)

        self._pain_flow_active = True
        try:
            self._request_yes_no(title, msg, "Use", "Skip", _done, player=player)
        except Exception:
            self._pain_flow_active = False
            self._open_next_pain_prompt(game_ctx)

    # ---------------- Blood Surge prompts ----------------

    def _on_blood_surge_prompt(self, player=None, unit=None, attacker_unit=None, game=None, **_kwargs):
        if player is None or unit is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        if self._blood_surge_flow_active:
            self._pending_blood_surge_queue.append((player, unit, attacker_unit, game))
            return
        self._pending_blood_surge_queue.append((player, unit, attacker_unit, game))
        self._open_next_blood_surge_prompt(game or self.game)

    def _open_next_blood_surge_prompt(self, game):
        q = list(getattr(self, "_pending_blood_surge_queue", []) or [])
        if not q:
            self._pending_blood_surge_queue = []
            self._blood_surge_flow_active = False
            return
        player, unit, attacker_unit, game_ctx = q.pop(0)
        self._pending_blood_surge_queue = q

        game_ctx = game_ctx or game or self.game
        if player is None or unit is None or game_ctx is None:
            self._open_next_blood_surge_prompt(game_ctx)
            return

        try:
            if not unit.can_blood_surge(game=game_ctx, game_map=getattr(game_ctx, "map", None)):
                self._open_next_blood_surge_prompt(game_ctx)
                return
        except Exception:
            self._open_next_blood_surge_prompt(game_ctx)
            return

        attacker_name = getattr(attacker_unit, "name", "Enemy unit")
        title = "Blood Surge"
        msg = (
            f"{attacker_name} destroyed models in {getattr(unit, 'name', 'unit')}.\n\n"
            "Blood Surge: Move D6+2\" as close as possible to the closest non-AIRCRAFT enemy unit.\n"
            "This unit cannot Blood Surge while Battle-shocked or within Engagement Range."
        )

        def _finish_and_next():
            self._blood_surge_flow_active = False
            self._open_next_blood_surge_prompt(game_ctx)

        def _start_blood_surge_move():
            try:
                max_distance = int(game_ctx.roll_blood_surge_distance(unit) or 0)
            except Exception:
                max_distance = 0
            if max_distance <= 0:
                _finish_and_next()
                return

            def _move_done(completed: bool):
                try:
                    if completed:
                        unit.mark_blood_surge_used(game_ctx)
                except Exception:
                    pass
                _finish_and_next()

            try:
                self.phase_manager._request_move_unit_decision(
                    unit,
                    "blood_surge",
                    _move_done,
                    max_distance=max_distance,
                )
            except Exception:
                _finish_and_next()

        fixed_active = False
        try:
            sr = getattr(unit, "special_rules", None)
            if isinstance(sr, dict) and sr.get("blood_surge_fixed_distance", None) is not None:
                expected = unit._blood_surge_phase_key(game_ctx)
                fixed_key = sr.get("blood_surge_fixed_distance_phase_key", None)
                if str(fixed_key or "") == str(expected or ""):
                    fixed_active = True
        except Exception:
            fixed_active = False

        manager = getattr(player, "stratagems", None)
        wrath = None
        phase_label = str(getattr(getattr(game_ctx, "phase", None), "name", "") or "").replace("_", " ").title()
        if manager is not None:
            wrath = manager.get_by_name("BERZERKER'S WRATH") or manager.get_by_name("BERZERKER'S WRATH")
            if wrath is not None:
                try:
                    if not manager.can_use(
                        wrath.name,
                        target_unit=unit,
                        attacker_unit=attacker_unit,
                        phase_name=phase_label or "Shooting phase",
                    ):
                        wrath = None
                except Exception:
                    wrath = None

        def _ask_wrath_then_surge():
            if wrath is None or manager is None:
                _start_blood_surge_move()
                return

            try:
                cost = wrath.cp_cost
                if hasattr(player, "preview_stratagem_cp_cost"):
                    cost = int(player.preview_stratagem_cp_cost(wrath, target_unit=unit).get("cost", wrath.cp_cost))
            except Exception:
                cost = wrath.cp_cost
            title2 = "Berzerker's Wrath"
            msg2 = (
                "Use Berzerker's Wrath to set Blood Surge distance to 8\" (no roll)?\n"
                f"CP cost: {int(cost)}"
            )

            def _wrath_done(use_wrath: bool):
                if use_wrath:
                    ok = manager.use(
                        wrath.name,
                        target_unit=unit,
                        attacker_unit=attacker_unit,
                        phase_name=phase_label or "Shooting phase",
                        dequeue=True,
                    )
                    if not ok:
                        print("Berzerker's Wrath failed; using normal Blood Surge.")
                _start_blood_surge_move()

            try:
                self._request_yes_no(title2, msg2, "Wrath", "Normal", _wrath_done, player=player)
            except Exception:
                _start_blood_surge_move()

        def _done(choice: bool):
            if not choice:
                _finish_and_next()
                return
            _ask_wrath_then_surge()

        self._blood_surge_flow_active = True
        if fixed_active:
            _start_blood_surge_move()
            return
        try:
            self._request_yes_no(title, msg, "Surge", "Skip", _done, player=player)
        except Exception:
            _finish_and_next()

    # ---------------- Reverberating Summons prompt ----------------

    def _on_reverberating_summons_prompt(
        self,
        player=None,
        attacker_model=None,
        candidates=None,
        ability_name=None,
        game=None,
        **_kwargs,
    ):
        if player is None or attacker_model is None:
            return
        has_control = getattr(player, "has_control", None)
        if not callable(has_control) or not has_control():
            return

        if self._reverberating_summons_flow_active:
            self._pending_reverberating_summons_queue.append(
                (player, attacker_model, candidates, ability_name, game)
            )
            return
        self._pending_reverberating_summons_queue.append(
            (player, attacker_model, candidates, ability_name, game)
        )
        self._open_next_reverberating_summons_prompt(game or self.game)

    def _open_next_reverberating_summons_prompt(self, game):
        q = list(getattr(self, "_pending_reverberating_summons_queue", []) or [])
        if not q:
            self._pending_reverberating_summons_queue = []
            self._reverberating_summons_flow_active = False
            return
        player, attacker_model, candidates, ability_name, game_ctx = q.pop(0)
        self._pending_reverberating_summons_queue = q

        game_ctx = game_ctx or game or self.game
        if player is None or attacker_model is None or game_ctx is None:
            self._open_next_reverberating_summons_prompt(game_ctx)
            return

        from ..rules.reverberating_summons import ABILITY_NAME, get_reverberating_summons_candidates

        ability_label = ability_name or ABILITY_NAME
        eligible = get_reverberating_summons_candidates(
            attacker_model,
            game_map=getattr(game_ctx, "map", None),
            units=candidates,
        )
        if not eligible:
            self._open_next_reverberating_summons_prompt(game_ctx)
            return

        def _finish_and_next():
            self._reverberating_summons_flow_active = False
            self._open_next_reverberating_summons_prompt(game_ctx)

        def _select_model_for_unit(unit):
            if unit is None:
                _finish_and_next()
                return
            self._open_reverberating_summons_model_prompt(
                player=player,
                unit=unit,
                ability_name=ability_label,
                game_ctx=game_ctx,
                on_done=_finish_and_next,
            )

        title = ability_label or "Reverberating Summons"
        prompt = "Select a friendly Plaguebearers unit within 12\", or choose None."
        subtitle = f"Bearer: {getattr(attacker_model, 'name', 'Model')}"

        self._reverberating_summons_flow_active = True
        from ..engine.decision_kinds import DECISION_SELECT_REVERBERATING_SUMMONS_UNIT

        self._resolve_unit_selection_dialog(
            player=player,
            candidates=eligible,
            on_chosen=_select_model_for_unit,
            decision_type=DECISION_SELECT_REVERBERATING_SUMMONS_UNIT,
            prompt=prompt,
            title=title,
            subtitle=subtitle,
            enemy_unit=None,
            dialog=self.overwatch_shooter_dialog,
            allow_skip=True,
        )

    def _open_reverberating_summons_model_prompt(self, *, player, unit, ability_name, game_ctx, on_done):
        if player is None or unit is None:
            on_done()
            return
        destroyed = list(getattr(unit, "models_lost", []) or [])
        if not destroyed:
            on_done()
            return

        from .dialogs import DamageAllocationDialog
        if not hasattr(self, "damage_allocation_dialog") or self.damage_allocation_dialog is None:
            self.damage_allocation_dialog = DamageAllocationDialog(self.screen.get_width(), self.screen.get_height())

        from ..engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id

        options = [DecisionOption.create("None", payload={"model_id": None, "action": "skip"})]
        for model in destroyed:
            options.append(
                DecisionOption.create(
                    getattr(model, "name", "Model"),
                    payload={"model_id": get_entity_id(model)},
                )
            )
        req = DecisionRequest.create(
            DECISION_ALLOCATE_DAMAGE,
            "Select destroyed Plaguebearer model to return.",
            player_id=getattr(player, "id", None),
            options=options,
            context={"unit_id": get_entity_id(unit), "selection_kind": "reverberating_summons_return"},
        )
        if game_ctx is not None:
            game_ctx.request_decision(req)

        def _on_choice(option_id: str):
            value, apply_result = resolve_decision_value(game_ctx, req, option_id)
            if apply_result is None or not getattr(apply_result, "ok", False):
                on_done()
                return
            if value is None:
                from ..utility.event_bus import append_action

                append_action(player, f"{ability_name}: no model returned to {getattr(unit, 'name', 'Unit')}.")
                on_done()
                return
            returned = unit.return_destroyed_bodyguard_models(
                1,
                game_map=getattr(game_ctx, "map", None),
                chosen_models=[value],
            )
            if returned > 0:
                from ..utility.event_bus import append_action

                summary = self._format_model_wargear_summary(value)
                if summary:
                    append_action(
                        player,
                        f"{ability_name}: returned {getattr(value, 'name', 'Model')} ({summary}) to {getattr(unit, 'name', 'Unit')}.",
                    )
                else:
                    append_action(
                        player,
                        f"{ability_name}: returned {getattr(value, 'name', 'Model')} to {getattr(unit, 'name', 'Unit')}.",
                    )
            on_done()

        dlg = self.damage_allocation_dialog
        dlg.show(
            unit,
            destroyed,
            title=ability_name or "Reverberating Summons",
            subtitle=getattr(unit, "name", "Unit"),
            instruction="Select a destroyed Plaguebearer model to return, or choose None.",
            on_choice=_on_choice,
            include_none=True,
            none_label="None",
            show_wargear=True,
            decision_request=req,
        )
        self.dialog_manager.open(dlg, modal=True)

    # ---------------- Reactive enemy-move prompts (Loping Speed) ----------------

    def _on_loping_speed_prompt(self, player=None, unit=None, moving_unit=None, rule=None, game=None, **_kwargs):
        if player is None or unit is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        if self._loping_speed_flow_active:
            self._pending_loping_speed_queue.append((player, unit, moving_unit, rule, game))
            return
        self._pending_loping_speed_queue.append((player, unit, moving_unit, rule, game))
        self._open_next_loping_speed_prompt(game or self.game)

    def _open_next_loping_speed_prompt(self, game):
        q = list(getattr(self, "_pending_loping_speed_queue", []) or [])
        if not q:
            self._pending_loping_speed_queue = []
            self._loping_speed_flow_active = False
            return
        player, unit, moving_unit, rule, game_ctx = q.pop(0)
        self._pending_loping_speed_queue = q

        game_ctx = game_ctx or game or self.game
        if player is None or unit is None or game_ctx is None:
            self._open_next_loping_speed_prompt(game_ctx)
            return

        try:
            rng = int((rule or {}).get("range", 9) or 9)
        except Exception:
            rng = 9
        try:
            if not unit.can_loping_speed(
                game=game_ctx,
                game_map=getattr(game_ctx, "map", None),
                moving_unit=moving_unit,
                range_override=rng,
            ):
                self._open_next_loping_speed_prompt(game_ctx)
                return
        except Exception:
            self._open_next_loping_speed_prompt(game_ctx)
            return

        source = str((rule or {}).get("source", "") or "Reactive Move").strip() or "Reactive Move"
        enemy_name = getattr(moving_unit, "name", "Enemy unit")
        title = source
        move_label = "D6"
        try:
            fixed = (rule or {}).get("max_distance")
            if fixed is not None:
                move_label = str(int(fixed))
            else:
                roll_spec = str((rule or {}).get("distance_roll", "") or "").strip()
                if roll_spec:
                    move_label = roll_spec.upper()
        except Exception:
            move_label = "D6"
        msg = (
            f"{enemy_name} ended a move within {int(rng)}\" of {getattr(unit, 'name', 'unit')}.\n\n"
            f"{source}: Make a Normal move of up to {move_label}\"?"
        )

        def _finish_and_next():
            self._loping_speed_flow_active = False
            self._open_next_loping_speed_prompt(game_ctx)

        def _start_loping_speed_move():
            try:
                max_distance = int(game_ctx.roll_loping_speed_distance(unit) or 0)
            except Exception:
                max_distance = 0
            if max_distance <= 0:
                _finish_and_next()
                return

            def _move_done(completed: bool):
                try:
                    if completed:
                        unit.mark_loping_speed_used(game_ctx)
                except Exception:
                    pass
                _finish_and_next()

            try:
                self.phase_manager._request_move_unit_decision(
                    unit,
                    "loping_speed",
                    _move_done,
                    max_distance=max_distance,
                )
            except Exception:
                _finish_and_next()

        def _done(choice: bool):
            if not choice:
                _finish_and_next()
                return
            _start_loping_speed_move()

        self._loping_speed_flow_active = True
        try:
            self._request_yes_no(title, msg, "Move", "Skip", _done, player=player)
        except Exception:
            _finish_and_next()

    # ---------------- Setup reactive shoot/charge prompts ----------------

    def _on_setup_reactive_shoot_charge_prompt(self, player=None, unit=None, candidates=None, rule=None, game=None, **_kwargs):
        if player is None or unit is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        entry = (player, unit, list(candidates or []), rule, game)
        if self._setup_reactive_shoot_charge_flow_active:
            self._pending_setup_reactive_shoot_charge_queue.append(entry)
            return
        self._pending_setup_reactive_shoot_charge_queue.append(entry)
        self._open_next_setup_reactive_shoot_charge_prompt(game or self.game)

    def _open_next_setup_reactive_shoot_charge_prompt(self, game):
        q = list(getattr(self, "_pending_setup_reactive_shoot_charge_queue", []) or [])
        if not q:
            self._pending_setup_reactive_shoot_charge_queue = []
            self._setup_reactive_shoot_charge_flow_active = False
            return
        player, unit, candidates, rule, game_ctx = q.pop(0)
        self._pending_setup_reactive_shoot_charge_queue = q

        game_ctx = game_ctx or game or self.game
        if player is None or unit is None or game_ctx is None:
            self._open_next_setup_reactive_shoot_charge_prompt(game_ctx)
            return
        rule = rule or unit.get_setup_reactive_shoot_or_charge_rule()
        if not rule:
            self._open_next_setup_reactive_shoot_charge_prompt(game_ctx)
            return
        if not unit.can_setup_reactive_shoot_or_charge(game=game_ctx, game_map=getattr(game_ctx, "map", None)):
            self._open_next_setup_reactive_shoot_charge_prompt(game_ctx)
            return

        source = str((rule or {}).get("source", "") or "Reactive Response").strip() or "Reactive Response"
        try:
            rng = int((rule or {}).get("range", 12) or 12)
        except Exception:
            rng = 12

        actionable = []
        for enemy in list(candidates or []):
            if enemy is None:
                continue
            if not enemy.is_alive():
                continue
            if not getattr(enemy, "deployed", True):
                continue
            if enemy.get_parent_army() == unit.get_parent_army():
                continue
            if not game_ctx._setup_reactive_available_actions(unit, enemy):
                continue
            actionable.append(enemy)
        if not actionable:
            self._open_next_setup_reactive_shoot_charge_prompt(game_ctx)
            return

        title = source
        subtitle = (
            f"Select an enemy unit set up within {int(rng)}\" of {getattr(unit, 'name', 'Unit')}."
        )

        def _finish_and_next():
            unit.clear_setup_reactive_shoot_or_charge_candidates(game_ctx)
            self._setup_reactive_shoot_charge_flow_active = False
            self._open_next_setup_reactive_shoot_charge_prompt(game_ctx)

        def _on_target_chosen(target_unit):
            if target_unit is None:
                _finish_and_next()
                return

            try:
                actions = list(game_ctx._setup_reactive_available_actions(unit, target_unit) or [])
            except Exception:
                actions = []
            if not actions:
                _finish_and_next()
                return

            def _on_action_chosen(action_choice):
                if not action_choice:
                    _finish_and_next()
                    return
                unit.mark_setup_reactive_shoot_or_charge_used(game_ctx)

                action = str(action_choice)
                if action == "shoot":
                    def _done(_executed: bool):
                        _finish_and_next()
                    if callable(getattr(self, "_request_setup_reactive_shooting", None)):
                        self._request_setup_reactive_shooting(unit, target_unit, source, _done)
                    else:
                        _finish_and_next()
                    return
                if action == "charge":
                    game_ctx.attempt_charge(unit, target_unit, out_of_turn=True, count_as_charged=False)
                    _finish_and_next()
                    return
                _finish_and_next()

            from ..engine.decision_kinds import DECISION_CHOOSE_SETUP_REACTIVE_ACTION
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.decision_utils import resolve_decision_value

            options = []
            if "shoot" in actions:
                options.append(DecisionOption.create("Shoot", payload={"action": "shoot"}))
            if "charge" in actions:
                options.append(DecisionOption.create("Charge", payload={"action": "charge"}))
            if not options:
                _finish_and_next()
                return
            req = DecisionRequest.create(
                DECISION_CHOOSE_SETUP_REACTIVE_ACTION,
                f"{source}: Choose action",
                player_id=getattr(player, "id", None),
                options=options,
                context={"unit_id": getattr(unit, "_id", ""), "target_unit_id": getattr(target_unit, "_id", "")},
            )
            self.game.request_decision(req)

            def _on_confirm(option_id: str):
                value, apply = resolve_decision_value(self.game, req, option_id)
                if apply is None or not getattr(apply, "ok", False):
                    _finish_and_next()
                else:
                    _on_action_chosen(value)
                try:
                    self.overwatch_shooter_dialog.hide()
                except Exception:
                    pass

            def _on_cancel():
                _finish_and_next()
                try:
                    self.overwatch_shooter_dialog.hide()
                except Exception:
                    pass

            self.overwatch_shooter_dialog.show(
                [],
                target_unit,
                _on_confirm,
                title=title,
                subtitle=f"Choose how {getattr(unit, 'name', 'Unit')} responds to {getattr(target_unit, 'name', 'Unit')}.",
                on_cancel=_on_cancel,
                decision_request=req,
            )
            try:
                self.dialog_manager.open(self.overwatch_shooter_dialog, modal=True)
            except Exception:
                pass

        self._setup_reactive_shoot_charge_flow_active = True
        from ..engine.decision_kinds import DECISION_SELECT_SETUP_REACTIVE_TARGET

        if callable(getattr(self, "_resolve_unit_selection_dialog", None)):
            self._resolve_unit_selection_dialog(
                player=player,
                candidates=actionable,
                on_chosen=_on_target_chosen,
                decision_type=DECISION_SELECT_SETUP_REACTIVE_TARGET,
                prompt="Select setup reactive target.",
                title=title,
                subtitle=subtitle,
                enemy_unit=None,
                dialog=self.overwatch_shooter_dialog,
                allow_skip=True,
            )
        else:
            _on_target_chosen(actionable[0] if actionable else None)

    # ---------------- Frenzy prompts ----------------

    def _on_frenzy_prompt(self, player=None, unit=None, attacker_unit=None, options=None, game=None, **_kwargs):
        if player is None or unit is None or attacker_unit is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        game_ctx = game or self.game
        if game_ctx is None:
            return

        opts = [str(o or "").strip().lower() for o in (options or [])]
        opts = [o for o in opts if o in ("shoot", "fight")]
        if not opts:
            return

        def _resolve_choice(choice: str):
            if choice == "shoot":
                if callable(getattr(self, "_request_frenzy_shooting", None)):
                    self._request_frenzy_shooting(unit, attacker_unit, lambda _ok: None)
                else:
                    try:
                        game_ctx._execute_frenzy_shooting(unit, attacker_unit)
                    except Exception:
                        pass
                return
            if choice == "fight":
                self._start_frenzy_fight_sequence(unit, attacker_unit, game_ctx)
                return

        if len(opts) == 1:
            _resolve_choice(opts[0])
            return

        try:
            from ..engine.decision_kinds import DECISION_CHOOSE_FRENZY_TARGET
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.decision_utils import resolve_decision_value
            from ..utility.entity_ids import get_entity_id
            from .decision_ui_utils import option_id_for_action

            unit_id = get_entity_id(unit)
            options = [
                DecisionOption.create("Shoot", payload={"action": "shoot", "unit_id": unit_id}),
                DecisionOption.create("Fight", payload={"action": "fight", "unit_id": unit_id}),
                DecisionOption.create("Skip", payload={"action": "skip", "unit_id": unit_id}),
            ]
            req = DecisionRequest.create(
                DECISION_CHOOSE_FRENZY_TARGET,
                "Choose Frenzy response.",
                player_id=getattr(getattr(unit.get_parent_army(), "player", None), "id", None),
                options=options,
                context={"unit_id": unit_id, "attacker_unit_id": get_entity_id(attacker_unit)},
            )
            if self.game is not None:
                self.game.request_decision(req)

            def _on_choice(option_id: str):
                value, apply_result = resolve_decision_value(self.game, req, option_id)
                if apply_result is None or not getattr(apply_result, "ok", False):
                    return
                choice = ""
                if isinstance(value, dict):
                    choice = str(value.get("action", "") or value.get("choice", "") or "").strip().lower()
                if not choice:
                    choice = str(value or "").strip().lower()
                if not choice and option_id_for_action(req, "skip") == option_id:
                    return
                _resolve_choice(choice)

            self.frenzy_choice_dialog.show(
                getattr(unit, "name", "Unit"),
                getattr(attacker_unit, "name", "Enemy unit"),
                opts,
                _on_choice,
                decision_request=req,
            )
            self.dialog_manager.open(self.frenzy_choice_dialog, modal=True)
        except Exception:
            return

    def _maybe_prompt_fight_within_3(self, unit, target_unit, on_done):
        if on_done is None:
            return
        try:
            if hasattr(unit, "clear_fight_within_3_active"):
                unit.clear_fight_within_3_active()
        except Exception:
            pass
        try:
            if not (hasattr(unit, "has_fight_within_3_ability") and unit.has_fight_within_3_ability()):
                on_done()
                return
        except Exception:
            on_done()
            return

        game_map = getattr(self, "game", None)
        game_map = getattr(game_map, "map", None)
        if target_unit is None or game_map is None:
            on_done()
            return

        try:
            base_eligible = unit.get_fight_eligible_models_for_target(
                target_unit,
                game_map=game_map,
                allow_within_3=False,
            )
            expanded_eligible = unit.get_fight_eligible_models_for_target(
                target_unit,
                game_map=game_map,
                allow_within_3=True,
            )
        except Exception:
            on_done()
            return

        if set(expanded_eligible) == set(base_eligible):
            on_done()
            return

        ability_name = "Fight Within 3\""
        try:
            sources = unit.get_fight_within_3_sources()
            if sources:
                ability_name = sources[0]
        except Exception:
            ability_name = "Fight Within 3\""

        player = None
        try:
            player = unit.get_parent_army().player
        except Exception:
            player = None

        if player is None:
            on_done()
            return

        is_human = False
        try:
            is_human = bool(getattr(player, "has_control", lambda: False)())
        except Exception:
            is_human = False

        if not is_human:
            should = False
            try:
                ctx = {
                    "unit": unit,
                    "target_unit": target_unit,
                    "ability_sources": list(unit.get_fight_within_3_sources() or []),
                }
                should = bool(player._should_use_optional_ability("FIGHT_WITHIN_3", ctx))
            except Exception:
                should = False
            if should:
                try:
                    unit.set_fight_within_3_active(True, source=ability_name)
                except Exception:
                    pass
            on_done()
            return

        title = ability_name
        msg = f"Use {ability_name} to let models within 3\" of enemy models fight?"

        def _done(chosen: bool):
            if chosen:
                try:
                    unit.set_fight_within_3_active(True, source=ability_name)
                except Exception:
                    pass
                try:
                    from ..utility.event_bus import append_action
                    append_action(player, f"{ability_name}: {getattr(unit, 'name', 'Unit')} can fight within 3\".")
                except Exception:
                    pass
            on_done()

        try:
            self._request_yes_no(title, msg, "Use", "Skip", _done, player=player)
        except Exception:
            _done(False)

    def _start_frenzy_fight_sequence(self, unit, attacker_unit, game_ctx):
        if unit is None or attacker_unit is None or game_ctx is None:
            return
        game_map = getattr(game_ctx, "map", None)
        if game_map is None:
            try:
                game_ctx._execute_frenzy_fight(unit, attacker_unit, phase_name=str(getattr(game_ctx.phase, "name", "") or ""))
            except Exception:
                pass
            return

        def _start_consolidate():
            max_distance = 3.0
            try:
                override = unit.get_fight_phase_move_distance_override("consolidate")
                if override is not None:
                    max_distance = float(override)
            except Exception:
                max_distance = 3.0
            self.phase_manager._request_move_unit_decision(
                unit,
                "consolidate",
                lambda _completed: None,
                max_distance=max_distance,
            )

        def _on_weapon_selection_complete(weapon_declarations):
            try:
                game_ctx.resolve_frenzy_melee_attacks(unit, attacker_unit, weapon_declarations)
            except Exception:
                pass
            _start_consolidate()

        def _on_pile_in_complete(_completed: bool):
            try:
                if not game_map.is_within_engagement_range(unit, attacker_unit):
                    return
            except Exception:
                pass
            def _show_weapons():
                self.phase_manager._request_melee_weapon_declarations(unit, attacker_unit, _on_weapon_selection_complete)
            self._maybe_prompt_fight_within_3(unit, attacker_unit, _show_weapons)

        max_distance = 3.0
        try:
            override = unit.get_fight_phase_move_distance_override("pile_in")
            if override is not None:
                max_distance = float(override)
        except Exception:
            max_distance = 3.0
        self.phase_manager._request_move_unit_decision(
            unit,
            "pile_in",
            _on_pile_in_complete,
            max_distance=max_distance,
        )

    # ---------------- Charge-end mortal wound prompts ----------------

    def _on_charge_mortal_wounds_prompt(self, player=None, unit=None, candidates=None, ability=None, on_select=None, **_kwargs):
        if player is None or unit is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        cand = list(candidates or [])
        if not cand:
            return

        if self._charge_mortal_wounds_flow_active:
            self._pending_charge_mortal_wounds_queue.append((player, unit, cand, ability, on_select))
            return
        self._pending_charge_mortal_wounds_queue.append((player, unit, cand, ability, on_select))
        self._open_next_charge_mortal_wounds_prompt(self.game)

    def _open_next_charge_mortal_wounds_prompt(self, game):
        q = list(getattr(self, "_pending_charge_mortal_wounds_queue", []) or [])
        if not q:
            self._pending_charge_mortal_wounds_queue = []
            self._charge_mortal_wounds_flow_active = False
            return
        player, unit, candidates, ability, on_select = q.pop(0)
        self._pending_charge_mortal_wounds_queue = q

        if player is None or unit is None:
            self._open_next_charge_mortal_wounds_prompt(game)
            return
        cand = list(candidates or [])
        if not cand:
            self._open_next_charge_mortal_wounds_prompt(game)
            return

        ability_name = str((ability or {}).get("name", "") or "Charge Mortals")
        title = ability_name
        subtitle = f"{getattr(unit, 'name', 'Unit')} ended a charge. Select a target."

        def _finish(chosen):
            try:
                self.overwatch_shooter_dialog.hide()
            except Exception:
                pass
            if chosen is None and cand:
                chosen = cand[0]
            if callable(on_select) and chosen is not None:
                try:
                    on_select(chosen)
                except Exception:
                    pass
            self._charge_mortal_wounds_flow_active = False
            self._open_next_charge_mortal_wounds_prompt(game)

        def _on_cancel():
            _finish(cand[0] if cand else None)

        self._charge_mortal_wounds_flow_active = True
        try:
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            if callable(getattr(self, "_resolve_unit_selection_dialog", None)):
                self._resolve_unit_selection_dialog(
                    player=player,
                    candidates=cand,
                    on_chosen=_finish,
                    decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                    prompt="Select charge mortal wounds target.",
                    title=title,
                    subtitle=subtitle,
                    enemy_unit=unit,
                    dialog=self.overwatch_shooter_dialog,
                    allow_skip=True,
                )
            else:
                _finish(cand[0] if cand else None)
        except Exception:
            self._charge_mortal_wounds_flow_active = False
            self._open_next_charge_mortal_wounds_prompt(game)

    # ---------------- Move-over mortal wound prompts ----------------

    def _on_move_over_mortal_wounds_prompt(
        self,
        player=None,
        unit=None,
        model=None,
        candidates=None,
        ability=None,
        on_select=None,
        **_kwargs,
    ):
        if player is None or unit is None or model is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        cand = list(candidates or [])
        if not cand:
            return

        if self._move_over_mortal_wounds_flow_active:
            self._pending_move_over_mortal_wounds_queue.append((player, unit, model, cand, ability, on_select))
            return
        self._pending_move_over_mortal_wounds_queue.append((player, unit, model, cand, ability, on_select))
        self._open_next_move_over_mortal_wounds_prompt(self.game)

    def _open_next_move_over_mortal_wounds_prompt(self, game):
        q = list(getattr(self, "_pending_move_over_mortal_wounds_queue", []) or [])
        if not q:
            self._pending_move_over_mortal_wounds_queue = []
            self._move_over_mortal_wounds_flow_active = False
            return
        player, unit, model, candidates, ability, on_select = q.pop(0)
        self._pending_move_over_mortal_wounds_queue = q

        if player is None or unit is None or model is None:
            self._open_next_move_over_mortal_wounds_prompt(game)
            return
        cand = list(candidates or [])
        if not cand:
            self._open_next_move_over_mortal_wounds_prompt(game)
            return

        ability_name = str((ability or {}).get("source", "") or "Move-over mortals")
        title = ability_name
        subtitle = f"{getattr(model, 'name', 'Model')} ({getattr(unit, 'name', 'Unit')}): select target or skip."

        def _finish(chosen):
            try:
                self.overwatch_shooter_dialog.hide()
            except Exception:
                pass
            if callable(on_select) and chosen is not None:
                try:
                    on_select(chosen)
                except Exception:
                    pass
            self._move_over_mortal_wounds_flow_active = False
            self._open_next_move_over_mortal_wounds_prompt(game)

        def _on_cancel():
            _finish(None)

        self._move_over_mortal_wounds_flow_active = True
        try:
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            if callable(getattr(self, "_resolve_unit_selection_dialog", None)):
                self._resolve_unit_selection_dialog(
                    player=player,
                    candidates=cand,
                    on_chosen=_finish,
                    decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                    prompt="Select move-over mortal wounds target.",
                    title=title,
                    subtitle=subtitle,
                    enemy_unit=unit,
                    dialog=self.overwatch_shooter_dialog,
                    allow_skip=True,
                )
            else:
                _finish(cand[0] if cand else None)
        except Exception:
            self._move_over_mortal_wounds_flow_active = False
            self._open_next_move_over_mortal_wounds_prompt(game)

    # ---------------- Charge phase bodyguard loss prompts ----------------

    def _on_charge_phase_bodyguard_loss_prompt(
        self,
        player=None,
        unit=None,
        bodyguard=None,
        candidates=None,
        ability=None,
        on_select=None,
        **_kwargs,
    ):
        if player is None or unit is None or bodyguard is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        cand = list(candidates or [])
        if not cand:
            return

        if self._charge_phase_bodyguard_loss_flow_active:
            self._pending_charge_phase_bodyguard_loss_queue.append((player, unit, bodyguard, cand, ability, on_select))
            return
        self._pending_charge_phase_bodyguard_loss_queue.append((player, unit, bodyguard, cand, ability, on_select))
        self._open_next_charge_phase_bodyguard_loss_prompt(self.game)

    def _open_next_charge_phase_bodyguard_loss_prompt(self, game):
        q = list(getattr(self, "_pending_charge_phase_bodyguard_loss_queue", []) or [])
        if not q:
            self._pending_charge_phase_bodyguard_loss_queue = []
            self._charge_phase_bodyguard_loss_flow_active = False
            return
        player, unit, bodyguard, candidates, ability, on_select = q.pop(0)
        self._pending_charge_phase_bodyguard_loss_queue = q

        if player is None or unit is None or bodyguard is None:
            self._open_next_charge_phase_bodyguard_loss_prompt(game)
            return
        cand = list(candidates or [])
        if not cand:
            self._open_next_charge_phase_bodyguard_loss_prompt(game)
            return

        ability_name = str((ability or {}).get("name", "") or "Leadership Test")
        title = ability_name
        subtitle = getattr(bodyguard, "name", "Unit")
        instruction = "Leadership test failed. Select a Bodyguard model to destroy."

        def _finish(chosen):
            if chosen is None and cand:
                chosen = cand[0]
            if callable(on_select) and chosen is not None:
                try:
                    on_select(chosen)
                except Exception:
                    pass
            self._charge_phase_bodyguard_loss_flow_active = False
            self._open_next_charge_phase_bodyguard_loss_prompt(game)

        self._charge_phase_bodyguard_loss_flow_active = True
        try:
            from .dialogs import DamageAllocationDialog
        except Exception:
            self._charge_phase_bodyguard_loss_flow_active = False
            self._open_next_charge_phase_bodyguard_loss_prompt(game)
            return

        if not hasattr(self, "damage_allocation_dialog") or self.damage_allocation_dialog is None:
            self.damage_allocation_dialog = DamageAllocationDialog(self.screen.get_width(), self.screen.get_height())

        from ..engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id

        options = []
        for model in cand:
            options.append(
                DecisionOption.create(
                    getattr(model, "name", "Model"),
                    payload={"model_id": get_entity_id(model)},
                )
            )
        req = DecisionRequest.create(
            DECISION_ALLOCATE_DAMAGE,
            "Select Bodyguard model to destroy.",
            player_id=getattr(player, "id", None),
            options=options,
            context={"unit_id": get_entity_id(bodyguard), "selection_kind": "bodyguard_loss"},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_choice(option_id: str):
            value, apply_result = resolve_decision_value(self.game, req, option_id)
            if apply_result is None or not getattr(apply_result, "ok", False):
                _finish(cand[0] if cand else None)
                return
            _finish(value)

        dlg = self.damage_allocation_dialog
        try:
            dlg.show(
                bodyguard,
                cand,
                title=title,
                subtitle=subtitle,
                instruction=instruction,
                on_choice=_on_choice,
                include_none=False,
                show_wargear=True,
                decision_request=req,
            )
            self.dialog_manager.open(dlg, modal=True)
        except Exception:
            self._charge_phase_bodyguard_loss_flow_active = False
            self._open_next_charge_phase_bodyguard_loss_prompt(game)

    # ---------------- Fight phase end mortal wound prompts ----------------

    def _on_fight_phase_end_mortal_wounds_prompt(
        self,
        player=None,
        unit=None,
        model=None,
        candidates=None,
        ability=None,
        on_select=None,
        **_kwargs,
    ):
        if player is None or unit is None or model is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        cand = list(candidates or [])
        if not cand:
            return

        if self._fight_end_mortal_wounds_flow_active:
            self._pending_fight_end_mortal_wounds_queue.append((player, unit, model, cand, ability, on_select))
            return
        self._pending_fight_end_mortal_wounds_queue.append((player, unit, model, cand, ability, on_select))
        self._open_next_fight_end_mortal_wounds_prompt(self.game)

    def _open_next_fight_end_mortal_wounds_prompt(self, game):
        q = list(getattr(self, "_pending_fight_end_mortal_wounds_queue", []) or [])
        if not q:
            self._pending_fight_end_mortal_wounds_queue = []
            self._fight_end_mortal_wounds_flow_active = False
            return
        player, unit, model, candidates, ability, on_select = q.pop(0)
        self._pending_fight_end_mortal_wounds_queue = q

        if player is None or unit is None or model is None:
            self._open_next_fight_end_mortal_wounds_prompt(game)
            return
        cand = list(candidates or [])
        if not cand:
            self._open_next_fight_end_mortal_wounds_prompt(game)
            return

        ability_name = str((ability or {}).get("source", "") or "Fight phase mortals")
        title = ability_name
        subtitle = f"{getattr(model, 'name', 'Model')} ({getattr(unit, 'name', 'Unit')}): select target or cancel."

        def _finish(chosen):
            try:
                self.overwatch_shooter_dialog.hide()
            except Exception:
                pass
            if callable(on_select):
                try:
                    on_select(chosen)
                except Exception:
                    pass
            self._fight_end_mortal_wounds_flow_active = False
            self._open_next_fight_end_mortal_wounds_prompt(game)

        def _on_cancel():
            _finish(None)

        self._fight_end_mortal_wounds_flow_active = True
        try:
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            if callable(getattr(self, "_resolve_unit_selection_dialog", None)):
                self._resolve_unit_selection_dialog(
                    player=player,
                    candidates=cand,
                    on_chosen=_finish,
                    decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                    prompt="Select fight phase mortal wounds target.",
                    title=title,
                    subtitle=subtitle,
                    enemy_unit=unit,
                    dialog=self.overwatch_shooter_dialog,
                    allow_skip=True,
                )
            else:
                _finish(cand[0] if cand else None)
        except Exception:
            self._fight_end_mortal_wounds_flow_active = False
            self._open_next_fight_end_mortal_wounds_prompt(game)

    # ---------------- Post-shoot battle-shock prompts ----------------

    def _on_post_shoot_battleshock_prompt(
        self,
        player=None,
        attacker_unit=None,
        model=None,
        candidates=None,
        ability=None,
        on_select=None,
        **_kwargs,
    ):
        if player is None or attacker_unit is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        cand = list(candidates or [])
        if not cand:
            return

        if self._post_shoot_battleshock_flow_active:
            self._pending_post_shoot_battleshock_queue.append((player, attacker_unit, model, cand, ability, on_select))
            return
        self._pending_post_shoot_battleshock_queue.append((player, attacker_unit, model, cand, ability, on_select))
        self._open_next_post_shoot_battleshock_prompt(self.game)

    def _open_next_post_shoot_battleshock_prompt(self, game):
        q = list(getattr(self, "_pending_post_shoot_battleshock_queue", []) or [])
        if not q:
            self._pending_post_shoot_battleshock_queue = []
            self._post_shoot_battleshock_flow_active = False
            return
        player, attacker_unit, model, candidates, ability, on_select = q.pop(0)
        self._pending_post_shoot_battleshock_queue = q

        if player is None or attacker_unit is None:
            self._open_next_post_shoot_battleshock_prompt(game)
            return
        cand = list(candidates or [])
        if not cand:
            self._open_next_post_shoot_battleshock_prompt(game)
            return

        ability_name = str((ability or {}).get("name", "") or "Post-shoot Battle-shock")
        model_name = getattr(model, "name", None) or getattr(attacker_unit, "name", "Model")
        title = ability_name
        subtitle = f"{model_name} shot. Select a unit to take a Battle-shock test."

        def _finish(chosen):
            try:
                self.overwatch_shooter_dialog.hide()
            except Exception:
                pass
            if chosen is None and cand:
                chosen = cand[0]
            if callable(on_select) and chosen is not None:
                try:
                    on_select(chosen)
                except Exception:
                    pass
            self._post_shoot_battleshock_flow_active = False
            self._open_next_post_shoot_battleshock_prompt(game)

        def _on_cancel():
            _finish(cand[0] if cand else None)

        self._post_shoot_battleshock_flow_active = True
        try:
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            if callable(getattr(self, "_resolve_unit_selection_dialog", None)):
                self._resolve_unit_selection_dialog(
                    player=player,
                    candidates=cand,
                    on_chosen=_finish,
                    decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                    prompt="Select post-shoot battleshock target.",
                    title=title,
                    subtitle=subtitle,
                    enemy_unit=attacker_unit,
                    dialog=self.overwatch_shooter_dialog,
                    allow_skip=True,
                )
            else:
                _finish(cand[0] if cand else None)
        except Exception:
            self._post_shoot_battleshock_flow_active = False
            self._open_next_post_shoot_battleshock_prompt(game)

    # ---------------- Post-shoot suppression prompts ----------------

    def _on_post_shoot_suppress_prompt(
        self,
        player=None,
        attacker_unit=None,
        model=None,
        candidates=None,
        ability=None,
        on_select=None,
        **_kwargs,
    ):
        if player is None or attacker_unit is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        cand = list(candidates or [])
        if not cand:
            return

        if self._post_shoot_suppress_flow_active:
            self._pending_post_shoot_suppress_queue.append((player, attacker_unit, model, cand, ability, on_select))
            return
        self._pending_post_shoot_suppress_queue.append((player, attacker_unit, model, cand, ability, on_select))
        self._open_next_post_shoot_suppress_prompt(self.game)

    def _open_next_post_shoot_suppress_prompt(self, game):
        q = list(getattr(self, "_pending_post_shoot_suppress_queue", []) or [])
        if not q:
            self._pending_post_shoot_suppress_queue = []
            self._post_shoot_suppress_flow_active = False
            return
        player, attacker_unit, model, candidates, ability, on_select = q.pop(0)
        self._pending_post_shoot_suppress_queue = q

        if player is None or attacker_unit is None:
            self._open_next_post_shoot_suppress_prompt(game)
            return
        cand = list(candidates or [])
        if not cand:
            self._open_next_post_shoot_suppress_prompt(game)
            return

        ability_name = str((ability or {}).get("name", "") or "Suppression")
        model_name = getattr(model, "name", None) or getattr(attacker_unit, "name", "Model")
        title = ability_name
        subtitle = f"{model_name} shot. Select a unit to suppress."

        def _finish(chosen):
            try:
                self.overwatch_shooter_dialog.hide()
            except Exception:
                pass
            if chosen is None and cand:
                chosen = cand[0]
            if callable(on_select) and chosen is not None:
                try:
                    on_select(chosen)
                except Exception:
                    pass
            self._post_shoot_suppress_flow_active = False
            self._open_next_post_shoot_suppress_prompt(game)

        def _on_cancel():
            _finish(cand[0] if cand else None)

        self._post_shoot_suppress_flow_active = True
        try:
            from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER

            if callable(getattr(self, "_resolve_unit_selection_dialog", None)):
                self._resolve_unit_selection_dialog(
                    player=player,
                    candidates=cand,
                    on_chosen=_finish,
                    decision_type=DECISION_SELECT_OVERWATCH_SHOOTER,
                    prompt="Select suppression target.",
                    title=title,
                    subtitle=subtitle,
                    enemy_unit=attacker_unit,
                    dialog=self.overwatch_shooter_dialog,
                    allow_skip=True,
                )
            else:
                _finish(cand[0] if cand else None)
        except Exception:
            self._post_shoot_suppress_flow_active = False
            self._open_next_post_shoot_suppress_prompt(game)

    # ---------------- Transport reactive disembark prompts ----------------

    def _on_transport_reactive_disembark_prompt(self, player=None, transport=None, enemy_unit=None, ability=None, game=None, **_kwargs):
        if player is None or transport is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        entry = (player, transport, enemy_unit, ability)
        if self._transport_reactive_disembark_flow_active:
            self._pending_transport_reactive_disembark_queue.append(entry)
            return
        self._pending_transport_reactive_disembark_queue.append(entry)
        self._open_next_transport_reactive_disembark_prompt(game or self.game)

    def _open_next_transport_reactive_disembark_prompt(self, game):
        q = list(getattr(self, "_pending_transport_reactive_disembark_queue", []) or [])
        if not q:
            self._pending_transport_reactive_disembark_queue = []
            self._transport_reactive_disembark_flow_active = False
            return
        player, transport, enemy_unit, ability = q.pop(0)
        self._pending_transport_reactive_disembark_queue = q

        if player is None or transport is None:
            self._open_next_transport_reactive_disembark_prompt(game)
            return

        try:
            if hasattr(transport, "is_alive") and not transport.is_alive():
                self._open_next_transport_reactive_disembark_prompt(game)
                return
        except Exception:
            pass

        try:
            if not getattr(transport, "deployed", True):
                self._open_next_transport_reactive_disembark_prompt(game)
                return
        except Exception:
            pass

        try:
            ability_range = float((ability or {}).get("range", 0) or 0)
        except Exception:
            ability_range = 0.0
        if ability_range > 0 and enemy_unit is not None:
            try:
                from ..utility.aura_utils import unit_within_range_of_unit
                if not unit_within_range_of_unit(transport, enemy_unit, ability_range):
                    self._open_next_transport_reactive_disembark_prompt(game)
                    return
            except Exception:
                pass

        passengers = list(getattr(transport, "transport_passengers", []) or [])
        if not passengers:
            self._open_next_transport_reactive_disembark_prompt(game)
            return

        eligible = []
        for u in passengers:
            if u is None:
                continue
            try:
                if not u.is_alive():
                    continue
            except Exception:
                pass
            try:
                if getattr(u, "embarked_in", None) is not transport:
                    continue
            except Exception:
                pass
            try:
                if getattr(u.round_state, "embarked_this_round", False):
                    continue
                if getattr(u.round_state, "disembarked_this_round", False):
                    continue
            except Exception:
                pass
            eligible.append(u)

        if not eligible:
            self._open_next_transport_reactive_disembark_prompt(game)
            return

        from ..engine.decision_kinds import DECISION_DISEMBARK
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id

        transport_id = get_entity_id(transport)
        pending = [
            req for req in list(self.game.decision_queue.list() or [])
            if getattr(req, "decision_type", None) == DECISION_DISEMBARK
            and str(getattr(req, "context", {}).get("transport_id", "")) == transport_id
        ]
        unit_requests = {}
        if pending:
            for req in pending:
                unit_id = str(getattr(req, "context", {}).get("unit_id", "")) or ""
                if unit_id:
                    unit_requests[unit_id] = req
        else:
            for unit in eligible:
                unit_id = get_entity_id(unit)
                options = [
                    DecisionOption.create(
                        "Disembark",
                        payload={"unit_id": unit_id, "transport_id": transport_id},
                    ),
                    DecisionOption.create(
                        "Remain embarked",
                        payload={"unit_id": unit_id, "transport_id": None},
                    ),
                ]
                req = DecisionRequest.create(
                    DECISION_DISEMBARK,
                    f"Disembark {getattr(unit, 'name', 'Unit')}",
                    player_id=getattr(player, "id", None),
                    options=options,
                    context={"unit_id": unit_id, "transport_id": transport_id},
                )
                self.game.request_decision(req)
                unit_requests[unit_id] = req

        def _option_id(req, disembark: bool) -> str:
            for opt in list(getattr(req, "options", []) or []):
                payload = dict(getattr(opt, "payload", {}) or {})
                if disembark and payload.get("transport_id") is not None:
                    return opt.option_id
                if not disembark and payload.get("transport_id") is None:
                    return opt.option_id
            return ""

        option_ids = {}
        for unit_id, req in unit_requests.items():
            option_ids[unit_id] = {
                "disembark": _option_id(req, True),
                "remain": _option_id(req, False),
            }

        self._transport_reactive_disembark_flow_active = True

        def _restore_positions(unit, positions):
            if not unit or not positions:
                return
            for m, pos in positions.items():
                if pos is None:
                    continue
                try:
                    m.set_location(*pos)
                except Exception:
                    pass

        def _disembark_units(selected_units):
            if not selected_units:
                for unit_id, req in unit_requests.items():
                    remain_id = option_ids.get(unit_id, {}).get("remain", "")
                    if remain_id:
                        resolve_decision_value(self.game, req, remain_id)
                self._transport_reactive_disembark_flow_active = False
                self._open_next_transport_reactive_disembark_prompt(game)
                return

            queue_units = list(selected_units)
            selected_ids = {get_entity_id(u) for u in queue_units if u is not None}
            for unit_id, req in unit_requests.items():
                if unit_id in selected_ids:
                    continue
                remain_id = option_ids.get(unit_id, {}).get("remain", "")
                if remain_id:
                    resolve_decision_value(self.game, req, remain_id)

            def _open_next_unit():
                if not queue_units:
                    self._transport_reactive_disembark_flow_active = False
                    self._open_next_transport_reactive_disembark_prompt(game)
                    return
                unit = queue_units.pop(0)
                if unit is None:
                    _open_next_unit()
                    return
                try:
                    if getattr(unit, "embarked_in", None) is not transport:
                        _open_next_unit()
                        return
                except Exception:
                    pass

                try:
                    models = list(unit.get_models_for_collision() or [])
                except Exception:
                    models = list(getattr(unit, "models", []) or [])
                original_positions = {m: m.get_location() for m in models}

                def _placement_validator(model, x: float, y: float, z: float) -> dict:
                    try:
                        return unit.validate_disembark_placement(
                            model,
                            x,
                            y,
                            z,
                            transport_unit=transport,
                            game_map=self.game.map,
                            max_distance=3.0,
                            require_not_in_engagement=True,
                        )
                    except Exception:
                        return {"valid": False, "reason": "Disembark validation failed"}

                def _on_complete(completed: bool):
                    unit_id = get_entity_id(unit)
                    req = unit_requests.get(unit_id)
                    result_value = None
                    if req is not None:
                        if completed:
                            payload = {"model_positions": self.phase_manager._serialize_unit_positions(unit)}
                            option_id = option_ids.get(unit_id, {}).get("disembark", "")
                            if option_id:
                                result_value, _apply = resolve_decision_value(self.game, req, option_id, result_payload=payload)
                        else:
                            option_id = option_ids.get(unit_id, {}).get("remain", "")
                            if option_id:
                                resolve_decision_value(self.game, req, option_id)
                    if completed and not result_value:
                        _restore_positions(unit, original_positions)
                    if not completed:
                        _restore_positions(unit, original_positions)
                    _open_next_unit()

                try:
                    self.phase_manager._request_move_unit_decision(
                        unit,
                        "deploy",
                        _on_complete,
                        max_distance=0.0,
                        placement_validator=_placement_validator,
                    )
                except Exception:
                    _restore_positions(unit, original_positions)
                    _open_next_unit()

            _open_next_unit()

        def _on_cancel():
            self._transport_reactive_disembark_flow_active = False
            self._open_next_transport_reactive_disembark_prompt(game)

        try:
            if not hasattr(self.game_view, "transport_disembark_dialog"):
                from .dialogs import TransportDisembarkDialog
                self.game_view.transport_disembark_dialog = TransportDisembarkDialog(
                    self.game_view.screen.get_width(),
                    self.game_view.screen.get_height(),
                )
            self.game_view.transport_disembark_dialog.show(
                transport,
                eligible,
                _disembark_units,
                on_cancel=_on_cancel,
                confirm_label="Disembark",
                show_cancel=False,
            )
            self.dialog_manager.open(self.game_view.transport_disembark_dialog, modal=True)
        except Exception:
            self._transport_reactive_disembark_flow_active = False
            self._open_next_transport_reactive_disembark_prompt(game)

    def _on_oath_of_moment_prompt(self, player=None, game=None, **_kwargs):
        """Prompt local players to select an Oath of Moment target at Command phase start."""
        if player is None:
            return
        try:
            is_human = bool(getattr(player, "has_control", lambda: False)())
        except Exception:
            is_human = False
        if not is_human:
            return

        game = game or self.game
        if game is None:
            return

        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            return
        mgr = getattr(army, "oath_of_moment", None)
        if mgr is None or not getattr(mgr, "army_has_oath", lambda: False)():
            return
        if getattr(mgr, "oathOfMomentTargetUnitId", None):
            return
        if bool(getattr(self, "_oath_of_moment_flow_active", False)):
            return

        try:
            options = list(getattr(mgr, "get_eligible_enemy_units", lambda **_k: [])(game=game, player=player) or [])
        except Exception:
            options = []
        if not options:
            return
        if len(options) == 1:
            mgr.set_target(options[0])
            return

        try:
            from .dialogs import QuarrySelectionDialog
        except Exception:
            mgr.set_target(options[0])
            return

        if not hasattr(self, "oath_of_moment_dialog") or self.oath_of_moment_dialog is None:
            self.oath_of_moment_dialog = QuarrySelectionDialog(self.screen.get_width(), self.screen.get_height())

        dlg = self.oath_of_moment_dialog

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id

        req_options = []
        for enemy in options:
            req_options.append(
                DecisionOption.create(
                    getattr(enemy, "name", "Unit"),
                    payload={"target_unit_id": get_entity_id(enemy)},
                )
            )
        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Select Oath of Moment target.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"ability": "oath_of_moment"},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _done(option_id: str):
            value, apply_result = resolve_decision_value(self.game, req, option_id)
            if apply_result is None or not getattr(apply_result, "ok", False) or value is None:
                self._oath_of_moment_flow_active = False
                return
            try:
                mgr.set_target(value)
            finally:
                self._oath_of_moment_flow_active = False

        def _cancel():
            self._oath_of_moment_flow_active = False

        self._oath_of_moment_flow_active = True
        dlg.show(
            title=f"Oath of Moment - {getattr(player, 'name', 'Player')}",
            header="Choose an enemy unit to be your Oath of Moment target.",
            subtitle="Target lasts until your next Command phase.",
            on_confirm=_done,
            on_cancel=_cancel,
            decision_request=req,
        )
        try:
            self.dialog_manager.open(dlg, modal=True)
        except Exception:
            self._oath_of_moment_flow_active = False

    def _on_code_chivalric_prompt(self, player=None, game=None, **_kwargs):
        if player is None:
            return
        try:
            is_human = bool(getattr(player, "has_control", lambda: False)())
        except Exception:
            is_human = False
        if not is_human:
            return
        game = game or self.game
        if game is None:
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            return
        mgr = getattr(army, "code_chivalric", None)
        if mgr is None or not getattr(mgr, "_army_has_code_chivalric", lambda: False)():
            return
        if getattr(mgr, "selected_deed_key", None) and getattr(mgr, "selected_quality_key", None):
            return
        if bool(getattr(self, "_code_chivalric_flow_active", False)):
            return
        self._pending_code_chivalric_queue.append(player)
        self._open_next_code_chivalric_prompt(game)

    def _open_next_code_chivalric_prompt(self, game=None) -> None:
        if getattr(self, "_code_chivalric_flow_active", False):
            return
        if not self._pending_code_chivalric_queue:
            return
        player = self._pending_code_chivalric_queue.pop(0)
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            self._open_next_code_chivalric_prompt(game)
            return
        mgr = getattr(army, "code_chivalric", None)
        if mgr is None or not getattr(mgr, "_army_has_code_chivalric", lambda: False)():
            self._open_next_code_chivalric_prompt(game)
            return

        if not hasattr(self, "code_chivalric_dialog") or self.code_chivalric_dialog is None:
            try:
                from .dialogs import CodeChivalricDialog
                sw, sh = self.screen.get_size()
                self.code_chivalric_dialog = CodeChivalricDialog(sw, sh)
            except Exception:
                self.code_chivalric_dialog = None
        if self.code_chivalric_dialog is None:
            try:
                mgr.roll_deed(game=game, player=player)
                mgr.roll_quality()
            except Exception:
                pass
            self._open_next_code_chivalric_prompt(game)
            return

        from ..utility.event_bus import append_action
        from ..rules.code_chivalric import CODE_CHIVALRIC_DEEDS, CODE_CHIVALRIC_QUALITIES, DEED_LAY_LOW

        try:
            roll_option = SimpleNamespace(
                key="ROLL",
                name="Roll D6 (random)",
                summary="Randomly select one option.",
            )
        except Exception:
            roll_option = None

        dlg = self.code_chivalric_dialog
        self._code_chivalric_flow_active = True

        def _finish():
            self._code_chivalric_flow_active = False
            self._open_next_code_chivalric_prompt(game)

        def _prompt_character_target():
            try:
                options = list(mgr.get_eligible_character_models(game=game, player=player) or [])
            except Exception:
                options = []
            if not options:
                _finish()
                return
            from ..engine.decision_kinds import DECISION_SELECT_TARGET_MODEL
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.decision_utils import resolve_decision_value
            from ..utility.entity_ids import get_entity_id

            req_options = []
            for model in options:
                unit_name = getattr(getattr(model, "parent_unit", None), "name", "")
                label = f"{getattr(model, 'name', '')} ({unit_name})" if unit_name else str(getattr(model, "name", ""))
                req_options.append(
                    DecisionOption.create(
                        label,
                        payload={"model_id": get_entity_id(model)},
                    )
                )
            req = DecisionRequest.create(
                DECISION_SELECT_TARGET_MODEL,
                "Select Code Chivalric target model.",
                player_id=getattr(player, "id", None),
                options=req_options,
                context={"selection_kind": "code_chivalric_target"},
            )
            if self.game is not None:
                self.game.request_decision(req)

            try:
                from .dialogs import QuarrySelectionDialog
            except Exception:
                mgr.set_deed_target_model(options[0])
                _finish()
                return

            if not hasattr(self, "code_chivalric_target_dialog") or self.code_chivalric_target_dialog is None:
                self.code_chivalric_target_dialog = QuarrySelectionDialog(self.screen.get_width(), self.screen.get_height())
            tdlg = self.code_chivalric_target_dialog

            def _done(option_id: str):
                try:
                    value, apply_result = resolve_decision_value(self.game, req, option_id)
                    if apply_result is not None and getattr(apply_result, "ok", False) and value is not None:
                        mgr.set_deed_target_model(value)
                finally:
                    _finish()

            def _cancel():
                _finish()

            tdlg.show(
                title=f"Code Chivalric - {getattr(player, 'name', 'Player')}",
                header="Choose an enemy CHARACTER model as your Oath target.",
                subtitle="Lay Low the Tyrant",
                on_confirm=_done,
                on_cancel=_cancel,
                decision_request=req,
            )
            try:
                self.dialog_manager.open(tdlg, modal=True)
            except Exception:
                _cancel()

        def _choose_quality():
            from ..engine.decision_kinds import DECISION_CHOOSE_CHIVALRIC_OATH
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.decision_utils import resolve_decision_value
            from ..utility.entity_ids import get_entity_id

            army_id = get_entity_id(player.get_army()) if player is not None else ""
            req_options = []
            option_labels = {}
            if roll_option is not None:
                opt = DecisionOption.create(
                    getattr(roll_option, "name", "Roll D6 (random)"),
                    payload={"choice_key": "ROLL", "random": True, "oath_kind": "quality"},
                )
                req_options.append(opt)
                option_labels[opt.option_id] = opt.label
            for quality in list(CODE_CHIVALRIC_QUALITIES or []):
                key = getattr(quality, "key", None) or getattr(quality, "choice_key", None)
                name = getattr(quality, "name", None) or str(quality)
                summary = getattr(quality, "summary", "") or getattr(quality, "effect", "")
                if not key:
                    continue
                opt = DecisionOption.create(
                    name,
                    payload={"choice_key": str(key), "oath_kind": "quality", "summary": summary, "army_id": army_id},
                )
                req_options.append(opt)
                option_labels[opt.option_id] = name
            req = DecisionRequest.create(
                DECISION_CHOOSE_CHIVALRIC_OATH,
                "Select Code Chivalric Quality.",
                player_id=getattr(player, "id", None),
                options=req_options,
                context={"oath_kind": "quality", "army_id": army_id},
            )
            if self.game is not None:
                self.game.request_decision(req)

            def _on_quality(option_id: str):
                value, apply_result = resolve_decision_value(self.game, req, option_id)
                if apply_result is not None and getattr(apply_result, "ok", False):
                    try:
                        if isinstance(value, dict) and value.get("quality") is not None:
                            quality = value.get("quality")
                            append_action(player, f"Code Chivalric Quality: {quality.name} (rolled {value.get('roll')})")
                        else:
                            label = option_labels.get(option_id, "Code Chivalric Quality")
                            append_action(player, f"Code Chivalric Quality: {label}")
                    except Exception:
                        pass
                if mgr.deed_requires_character_target() and not getattr(mgr, "deed_target_model_id", None):
                    _prompt_character_target()
                    return
                _finish()

            dlg.show(
                title="Code Chivalric - Quality",
                header="Choose a Quality for this battle.",
                on_confirm=_on_quality,
                decision_request=req,
            )
            try:
                self.dialog_manager.open(dlg, modal=True)
            except Exception:
                _finish()

        def _choose_deed():
            if getattr(mgr, "selected_deed_key", None):
                _choose_quality()
                return
            from ..engine.decision_kinds import DECISION_CHOOSE_CHIVALRIC_OATH
            from ..engine.decisions import DecisionOption, DecisionRequest
            from ..utility.decision_utils import resolve_decision_value
            from ..utility.entity_ids import get_entity_id

            army_id = get_entity_id(player.get_army()) if player is not None else ""
            req_options = []
            option_labels = {}
            if roll_option is not None:
                opt = DecisionOption.create(
                    getattr(roll_option, "name", "Roll D6 (random)"),
                    payload={"choice_key": "ROLL", "random": True, "oath_kind": "deed"},
                )
                req_options.append(opt)
                option_labels[opt.option_id] = opt.label
            for deed in list(CODE_CHIVALRIC_DEEDS or []):
                key = getattr(deed, "key", None) or getattr(deed, "choice_key", None)
                name = getattr(deed, "name", None) or str(deed)
                summary = getattr(deed, "summary", "") or getattr(deed, "effect", "")
                if not key:
                    continue
                opt = DecisionOption.create(
                    name,
                    payload={"choice_key": str(key), "oath_kind": "deed", "summary": summary, "army_id": army_id},
                )
                req_options.append(opt)
                option_labels[opt.option_id] = name
            req = DecisionRequest.create(
                DECISION_CHOOSE_CHIVALRIC_OATH,
                "Select Code Chivalric Deed.",
                player_id=getattr(player, "id", None),
                options=req_options,
                context={"oath_kind": "deed", "army_id": army_id},
            )
            if self.game is not None:
                self.game.request_decision(req)

            def _on_deed(option_id: str):
                value, apply_result = resolve_decision_value(self.game, req, option_id)
                if apply_result is not None and getattr(apply_result, "ok", False):
                    try:
                        if isinstance(value, dict) and value.get("deed") is not None:
                            deed = value.get("deed")
                            append_action(player, f"Code Chivalric Deed: {deed.name} (rolled {value.get('roll')})")
                        else:
                            label = option_labels.get(option_id, "Code Chivalric Deed")
                            append_action(player, f"Code Chivalric Deed: {label}")
                    except Exception:
                        pass
                _choose_quality()

            dlg.show(
                title="Code Chivalric - Deed",
                header="Choose a Deed for this battle.",
                on_confirm=_on_deed,
                decision_request=req,
            )
            try:
                self.dialog_manager.open(dlg, modal=True)
            except Exception:
                _finish()

        if getattr(mgr, "selected_deed_key", None) == DEED_LAY_LOW.key and getattr(mgr, "selected_quality_key", None):
            if not getattr(mgr, "deed_target_model_id", None):
                _prompt_character_target()
                return
            _finish()
            return

        _choose_deed()

    def _on_bondsman_prompt(self, player=None, game=None, **_kwargs):
        if player is None:
            return
        try:
            is_human = bool(getattr(player, "has_control", lambda: False)())
        except Exception:
            is_human = False
        if not is_human:
            return
        game = game or self.game
        if game is None:
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            return
        mgr = getattr(army, "bondsman", None)
        if mgr is None or not getattr(mgr, "_army_has_bondsman", lambda: False)():
            return
        if bool(getattr(self, "_bondsman_flow_active", False)):
            return
        try:
            sources = list(mgr.get_bondsman_sources())
        except Exception:
            sources = []
        if not sources:
            return
        self._pending_bondsman_queue = list(sources)
        self._open_next_bondsman_prompt(game, player)

    def _open_next_bondsman_prompt(self, game, player):
        if not self._pending_bondsman_queue:
            self._bondsman_flow_active = False
            return
        self._bondsman_flow_active = True
        source_unit = self._pending_bondsman_queue.pop(0)
        try:
            mgr = getattr(player.get_army(), "bondsman", None)
        except Exception:
            mgr = None
        if mgr is None:
            self._open_next_bondsman_prompt(game, player)
            return
        try:
            targets = list(mgr.get_eligible_armigers(source_unit, game_map=getattr(game, "map", None)) or [])
        except Exception:
            targets = []
        if not targets:
            self._open_next_bondsman_prompt(game, player)
            return
        try:
            from .dialogs import QuarrySelectionDialog
        except Exception:
            mgr.apply_bondsman_effects(source_unit, targets[0])
            self._open_next_bondsman_prompt(game, player)
            return
        if not hasattr(self, "bondsman_dialog") or self.bondsman_dialog is None:
            self.bondsman_dialog = QuarrySelectionDialog(self.screen.get_width(), self.screen.get_height())
        dlg = self.bondsman_dialog
        ability_names = []
        try:
            ability_names = list(mgr.get_bondsman_ability_names(source_unit))
        except Exception:
            ability_names = []
        subtitle = ", ".join(ability_names) if ability_names else "Bondsman ability"

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id

        req_options = []
        for target in targets:
            req_options.append(
                DecisionOption.create(
                    getattr(target, "name", "Unit"),
                    payload={"target_unit_id": get_entity_id(target)},
                )
            )
        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Select Bondsman target.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"source_unit_id": get_entity_id(source_unit), "ability": "bondsman"},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _done(option_id: str):
            value, apply_result = resolve_decision_value(self.game, req, option_id)
            if apply_result is not None and getattr(apply_result, "ok", False) and value is not None:
                try:
                    mgr.apply_bondsman_effects(source_unit, value)
                except Exception:
                    pass
                try:
                    from ..utility.event_bus import append_action
                    append_action(player, f"Bondsman: {source_unit.name} -> {getattr(value, 'name', '')}")
                except Exception:
                    pass
            self._open_next_bondsman_prompt(game, player)

        def _cancel():
            self._open_next_bondsman_prompt(game, player)

        dlg.show(
            title=f"Bondsman - {getattr(source_unit, 'name', 'Unit')}",
            header=f"Select an ARMIGER within 12\" of {getattr(source_unit, 'name', 'this model')}.",
            subtitle=subtitle,
            on_confirm=_done,
            on_cancel=_cancel,
            decision_request=req,
        )
        try:
            self.dialog_manager.open(dlg, modal=True)
        except Exception:
            _cancel()

    def _on_necrons_command_phase_enhancement_prompt(self, player=None, game=None, **_kwargs):
        if player is None:
            return
        try:
            is_human = bool(getattr(player, "has_control", lambda: False)())
        except Exception:
            is_human = False
        if not is_human:
            return
        game = game or self.game
        if game is None:
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            return
        mgr = getattr(army, "necrons_detachments", None)
        if mgr is None:
            return
        if bool(getattr(self, "_necrons_enhancement_flow_active", False)):
            return
        try:
            sources = list(mgr.get_command_phase_bearer_sources() or [])
        except Exception:
            sources = []
        if not sources:
            return
        self._pending_necrons_enhancement_queue = list(sources)
        self._open_next_necrons_command_phase_enhancement_prompt(game, player)

    def _open_next_necrons_command_phase_enhancement_prompt(self, game, player):
        if not self._pending_necrons_enhancement_queue:
            self._necrons_enhancement_flow_active = False
            return
        self._necrons_enhancement_flow_active = True
        entry = self._pending_necrons_enhancement_queue.pop(0)
        source_unit = entry.get("source")
        spec = entry.get("spec")
        try:
            mgr = getattr(player.get_army(), "necrons_detachments", None)
        except Exception:
            mgr = None
        if mgr is None or source_unit is None or spec is None:
            self._open_next_necrons_command_phase_enhancement_prompt(game, player)
            return
        try:
            targets = list(mgr.get_command_phase_bearer_targets(source_unit, spec) or [])
        except Exception:
            targets = []
        if not targets:
            self._open_next_necrons_command_phase_enhancement_prompt(game, player)
            return
        try:
            from .dialogs import QuarrySelectionDialog
        except Exception:
            mgr.apply_command_phase_bearer_effect(source_unit, targets[0], spec)
            self._open_next_necrons_command_phase_enhancement_prompt(game, player)
            return

        if not hasattr(self, "necrons_enhancement_dialog") or self.necrons_enhancement_dialog is None:
            self.necrons_enhancement_dialog = QuarrySelectionDialog(self.screen.get_width(), self.screen.get_height())
        dlg = self.necrons_enhancement_dialog

        effect_text = ""
        if getattr(spec, "effect_key", "") == "fell_back_shoot":
            effect_text = "Selected unit can shoot after Falling Back until your next Command phase."
        elif getattr(spec, "effect_key", "") == "damage_reduction":
            effect_text = f"Selected unit takes -{int(getattr(spec, 'effect_value', 1) or 1)} Damage until your next Command phase."

        header = (
            f"{getattr(spec, 'ability_name', 'Command Phase Ability')}: "
            f"select a friendly {getattr(spec, 'target_label', 'unit')} within "
            f"{int(getattr(spec, 'range_inches', 0) or 0)}\" of {getattr(source_unit, 'name', 'this model')}."
        )

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id

        req = None
        try:
            queue = getattr(self.game, "decision_queue", None)
            source_id = str(get_entity_id(source_unit) or "")
            for pending in list(getattr(queue, "list", lambda: [])() or []):
                if str(getattr(pending, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                    continue
                ctx = dict(getattr(pending, "context", {}) or {})
                if not ctx.get("necrons_command_phase_enhancement"):
                    continue
                if str(ctx.get("source_unit_id", "")) != source_id:
                    continue
                if str(ctx.get("effect_key", "")) != str(getattr(spec, "effect_key", "")):
                    continue
                if str(ctx.get("ability", "")) != str(getattr(spec, "ability_name", "")):
                    continue
                req = pending
                break
        except Exception:
            req = None
        if req is None:
            try:
                req = mgr.build_command_phase_bearer_request(game, player, source_unit, spec, targets)
            except Exception:
                req = None
        if req is None:
            mgr.apply_command_phase_bearer_effect(source_unit, targets[0], spec)
            self._open_next_necrons_command_phase_enhancement_prompt(game, player)
            return

        def _done(option_id: str):
            value, apply_result = resolve_decision_value(self.game, req, option_id)
            if apply_result is not None and getattr(apply_result, "ok", False) and value is not None:
                try:
                    from ..utility.event_bus import append_action
                    append_action(
                        player,
                        f"{getattr(spec, 'ability_name', 'Command Phase Ability')}: "
                        f"{getattr(source_unit, 'name', 'Source')} -> {getattr(value, 'name', '')}",
                    )
                except Exception:
                    pass
            self._open_next_necrons_command_phase_enhancement_prompt(game, player)

        def _cancel():
            self._pending_necrons_enhancement_queue = [entry] + list(
                getattr(self, "_pending_necrons_enhancement_queue", []) or []
            )
            self._open_next_necrons_command_phase_enhancement_prompt(game, player)

        dlg.show(
            title=f"{getattr(spec, 'ability_name', 'Command Phase Ability')}",
            header=header,
            subtitle=effect_text,
            on_confirm=_done,
            on_cancel=_cancel,
            decision_request=req,
            show_cancel=False,
        )
        try:
            self.dialog_manager.open(dlg, modal=True)
        except Exception:
            _cancel()

    def _on_shadow_in_the_warp_prompt(self, player=None, game=None, **_kwargs):
        if player is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        game = game or self.game
        if game is None:
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            return
        mgr = getattr(army, "shadow_in_the_warp", None)
        if mgr is None:
            return
        try:
            if not mgr.can_use_now(game=game, player=player):
                return
        except Exception:
            return

        if self._shadow_in_the_warp_flow_active:
            self._pending_shadow_in_the_warp_queue.append(player)
            return
        self._pending_shadow_in_the_warp_queue.append(player)
        self._open_next_shadow_in_the_warp_prompt(game)

    def _open_next_shadow_in_the_warp_prompt(self, game):
        q = list(getattr(self, "_pending_shadow_in_the_warp_queue", []) or [])
        if not q:
            self._pending_shadow_in_the_warp_queue = []
            self._shadow_in_the_warp_flow_active = False
            return
        player = q.pop(0)
        self._pending_shadow_in_the_warp_queue = q

        try:
            army = player.get_army()
        except Exception:
            army = None
        mgr = getattr(army, "shadow_in_the_warp", None) if army is not None else None
        if mgr is None:
            self._open_next_shadow_in_the_warp_prompt(game)
            return
        try:
            if not mgr.can_use_now(game=game, player=player):
                self._open_next_shadow_in_the_warp_prompt(game)
                return
        except Exception:
            self._open_next_shadow_in_the_warp_prompt(game)
            return

        title = "Shadow in the Warp"
        msg = (
            "Use Shadow in the Warp now?\n\n"
            "Once per battle, in either Command phase, each enemy unit on the battlefield "
            "must take a Battle-shock test. If an enemy unit is within 6\" of your SYNAPSE units, "
            "subtract 1 from that test."
        )

        def _done(chosen: bool):
            try:
                if chosen:
                    mgr.activate(game=game, player=player)
            finally:
                self._shadow_in_the_warp_flow_active = False
                self._open_next_shadow_in_the_warp_prompt(game)

        self._shadow_in_the_warp_flow_active = True
        try:
            self._request_yes_no(title, msg, "Use", "Skip", _done, player=player)
        except Exception:
            self._shadow_in_the_warp_flow_active = False
            self._open_next_shadow_in_the_warp_prompt(game)

    def _on_waaagh_prompt(self, player=None, game=None, **_kwargs):
        if player is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        if self._waaagh_flow_active:
            return

        game = game or self.game
        if game is None:
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            return
        mgr = getattr(army, "waaagh", None)
        if mgr is None:
            return
        try:
            if not mgr.can_call_now(game=game, player=player):
                return
        except Exception:
            return

        title = "Waaagh!"
        msg = (
            "Call the Waaagh! now?\n\n"
            "Until the start of your next Command phase:\n"
            "- Your units can charge after advancing\n"
            "- Melee weapons get +1S and +1A\n"
            "- Your models gain a 5+ invulnerable save"
        )

        def _done(choice: bool):
            try:
                if choice:
                    mgr.call_waaagh(game=game, player=player)
            finally:
                self._waaagh_flow_active = False

        self._waaagh_flow_active = True
        try:
            self._request_yes_no(title, msg, "Call", "Skip", _done, player=player)
        except Exception:
            self._waaagh_flow_active = False

    def _on_prioritised_efficiency_updated(self, player=None, **_kwargs):
        if player is None:
            return
        try:
            if self.rule_detail_panel and self.rule_detail_panel.visible and isinstance(self._rule_panel_state, dict):
                if self._rule_panel_state.get("player") is player and self._rule_panel_state.get("rule_type") == "army":
                    self._toggle_rule_panel(player, "army", force_refresh=True)
        except Exception:
            pass

    def _on_cult_ambush_updated(self, player=None, **_kwargs):
        if player is None:
            return
        try:
            if self.rule_detail_panel and self.rule_detail_panel.visible and isinstance(self._rule_panel_state, dict):
                if self._rule_panel_state.get("player") is player and self._rule_panel_state.get("rule_type") == "army":
                    self._toggle_rule_panel(player, "army", force_refresh=True)
        except Exception:
            pass

    def _on_cult_ambush_prompt(self, player=None, unit=None, cost=None, game=None, **_kwargs):
        if player is None or unit is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        if self._cult_ambush_flow_active:
            self._pending_cult_ambush_queue.append((player, unit, cost, game))
            return
        self._pending_cult_ambush_queue.append((player, unit, cost, game))
        self._open_next_cult_ambush_prompt(game or self.game)

    def _open_next_cult_ambush_prompt(self, game):
        q = list(getattr(self, "_pending_cult_ambush_queue", []) or [])
        if not q:
            self._pending_cult_ambush_queue = []
            self._cult_ambush_flow_active = False
            return
        player, unit, cost, game_ctx = q.pop(0)
        self._pending_cult_ambush_queue = q

        game_ctx = game_ctx or game or self.game
        if player is None or unit is None or game_ctx is None:
            self._open_next_cult_ambush_prompt(game_ctx)
            return

        mgr = self._get_cult_ambush_manager(player)
        if mgr is None:
            self._open_next_cult_ambush_prompt(game_ctx)
            return

        try:
            cost_val = int(cost if cost is not None else mgr.resurgence_cost_for_unit(unit) or 0)
        except Exception:
            cost_val = 0
        try:
            points = int(getattr(mgr, "resurgence_points", 0) or 0)
        except Exception:
            points = 0
        if cost_val <= 0 or points < cost_val:
            self._open_next_cult_ambush_prompt(game_ctx)
            return

        title = "Cult Ambush"
        msg = (
            f"Spend {cost_val} Resurgence point(s) to return {getattr(unit, 'name', 'unit')} in Cult Ambush?\n\n"
            f"Resurgence points available: {points}"
        )

        def _done(choice: bool):
            try:
                self._cult_ambush_flow_active = False
                if choice:
                    new_unit = mgr.spend_resurgence_for_unit(unit, game=game_ctx)
                    if new_unit is None:
                        return

                    # If no legal marker placement exists, skip the marker dialog.
                    try:
                        if mgr.find_marker_position(game_ctx) is None:
                            return
                    except Exception:
                        pass

                    def _validate(x, y):
                        try:
                            ok = bool(mgr._marker_position_valid(game_ctx, float(x), float(y)))
                        except Exception:
                            ok = False
                        if ok:
                            return {"valid": True, "reason": "OK"}
                        return {"valid": False, "reason": "Must be more than 9\" from enemy units"}

                    from ..engine.decision_kinds import DECISION_PICK_POINT
                    from ..engine.decisions import DecisionOption, DecisionRequest
                    from ..utility.decision_utils import resolve_decision_value
                    from .decision_ui_utils import option_id_for_action

                    options = [
                        DecisionOption.create("Confirm", payload={"action": "confirm"}),
                        DecisionOption.create("Skip", payload={"action": "skip"}),
                    ]
                    req = DecisionRequest.create(
                        DECISION_PICK_POINT,
                        "Select Cult Ambush marker point.",
                        player_id=getattr(player, "id", None),
                        options=options,
                        context={"unit_id": get_entity_id(unit)},
                    )
                    if self.game is not None:
                        self.game.request_decision(req)

                    def _confirm(option_id: str, point):
                        try:
                            payload = {"point": list(point)}
                            value, apply_result = resolve_decision_value(self.game, req, option_id, result_payload=payload)
                            if value is None or apply_result is None or not getattr(apply_result, "ok", False):
                                value = point
                            mgr.place_marker_at(game_ctx, value[0], value[1])
                        finally:
                            self._cult_ambush_flow_active = False
                            self._open_next_cult_ambush_prompt(game_ctx)

                    def _cancel():
                        skip_id = option_id_for_action(req, "skip")
                        if skip_id:
                            resolve_decision_value(self.game, req, skip_id, result_payload={"skipped": True})
                        self._cult_ambush_flow_active = False
                        self._open_next_cult_ambush_prompt(game_ctx)

                    self._cult_ambush_flow_active = True
                    try:
                        self.cult_ambush_point_dialog.show(
                            game_view=self,
                            title="Cult Ambush Marker",
                            instructions="Select a marker position more than 9\" from enemy units.",
                            validate_cb=_validate,
                            on_confirm=_confirm,
                            on_cancel=_cancel,
                            decision_request=req,
                        )
                        self.dialog_manager.open(self.cult_ambush_point_dialog, modal=True)
                        return
                    except Exception:
                        self._cult_ambush_flow_active = False
                        return
            finally:
                if not self._cult_ambush_flow_active:
                    self._open_next_cult_ambush_prompt(game_ctx)

        self._cult_ambush_flow_active = True
        try:
            self._request_yes_no(title, msg, "Use", "Skip", _done, player=player)
        except Exception:
            self._cult_ambush_flow_active = False
            self._open_next_cult_ambush_prompt(game_ctx)

    def _on_cult_ambush_reinforcements_prompt(self, player=None, markers=None, game=None, **_kwargs):
        if player is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return
        markers = list(markers or [])
        if not markers:
            return
        for marker in markers:
            self._pending_cult_ambush_marker_queue.append((player, marker, game))
        if self._cult_ambush_marker_flow_active:
            return
        self._open_next_cult_ambush_marker_prompt(game or self.game)

    def _open_next_cult_ambush_marker_prompt(self, game):
        q = list(getattr(self, "_pending_cult_ambush_marker_queue", []) or [])
        if not q:
            self._pending_cult_ambush_marker_queue = []
            self._cult_ambush_marker_flow_active = False
            return
        player, marker, game_ctx = q.pop(0)
        self._pending_cult_ambush_marker_queue = q

        game_ctx = game_ctx or game or self.game
        if player is None or marker is None or game_ctx is None:
            self._open_next_cult_ambush_marker_prompt(game_ctx)
            return

        mgr = self._get_cult_ambush_manager(player)
        if mgr is None:
            self._open_next_cult_ambush_marker_prompt(game_ctx)
            return
        if not bool(getattr(marker, "active", False)):
            self._open_next_cult_ambush_marker_prompt(game_ctx)
            return

        try:
            units = list(mgr.get_units_in_cult_ambush(game=game_ctx, only_arrivable=True) or [])
        except Exception:
            units = []
        if not units:
            self._open_next_cult_ambush_marker_prompt(game_ctx)
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id
        from .decision_ui_utils import option_id_for_action

        req_options = [DecisionOption.create("Skip (leave marker)", payload={"action": "skip"})]
        for unit in units:
            req_options.append(
                DecisionOption.create(
                    getattr(unit, "name", "Unit"),
                    payload={"target_unit_id": get_entity_id(unit)},
                )
            )
        req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Select Cult Ambush unit.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"marker_id": get_entity_id(marker) if marker is not None else None},
        )
        if self.game is not None:
            self.game.request_decision(req)

        try:
            from .dialogs import QuarrySelectionDialog
        except Exception:
            self._open_next_cult_ambush_marker_prompt(game_ctx)
            return

        if not hasattr(self, "cult_ambush_unit_dialog") or self.cult_ambush_unit_dialog is None:
            self.cult_ambush_unit_dialog = QuarrySelectionDialog(self.screen.get_width(), self.screen.get_height())

        title = "Cult Ambush"
        subtitle = f"Marker at ({getattr(marker, 'x', 0.0):.1f}\", {getattr(marker, 'y', 0.0):.1f}\")"

        def _on_confirm(option_id: str):
            try:
                value, apply_result = resolve_decision_value(self.game, req, option_id)
                if apply_result is None or not getattr(apply_result, "ok", False) or value is None:
                    return
                mgr.deploy_unit_from_marker(value, marker, game=game_ctx)
            finally:
                self._cult_ambush_marker_flow_active = False
                self._open_next_cult_ambush_marker_prompt(game_ctx)

        def _on_cancel():
            skip_id = option_id_for_action(req, "skip")
            if skip_id:
                resolve_decision_value(self.game, req, skip_id)
            self._cult_ambush_marker_flow_active = False
            self._open_next_cult_ambush_marker_prompt(game_ctx)

        self._cult_ambush_marker_flow_active = True
        try:
            self.cult_ambush_unit_dialog.show(
                title=title,
                header="Select a unit to set up using this Cult Ambush marker.",
                subtitle=subtitle,
                on_confirm=_on_confirm,
                on_cancel=_on_cancel,
                decision_request=req,
            )
            self.dialog_manager.open(self.cult_ambush_unit_dialog, modal=True)
        except Exception:
            self._cult_ambush_marker_flow_active = False
            self._open_next_cult_ambush_marker_prompt(game_ctx)

    def _on_for_the_greater_good_prompt(self, player=None, game=None, **_kwargs):
        if player is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        if self._ftgg_flow_active:
            return

        game = game or self.game
        if game is None:
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            return
        mgr = getattr(army, "for_the_greater_good", None)
        if mgr is None:
            return

        self._ftgg_flow_active = True
        self._open_next_ftgg_observer_prompt(game, player)

    def _open_next_ftgg_observer_prompt(self, game, player) -> None:
        if not self._ftgg_flow_active:
            return
        if game is None or player is None:
            self._ftgg_flow_active = False
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        mgr = getattr(army, "for_the_greater_good", None) if army is not None else None
        if mgr is None:
            self._ftgg_flow_active = False
            return

        try:
            observers = list(mgr.get_eligible_observers(game=game, player=player) or [])
        except Exception:
            observers = []
        options = []
        for obs in observers:
            try:
                targets = list(mgr.get_eligible_spotted_targets(obs, game=game, player=player) or [])
            except Exception:
                targets = []
            if targets:
                options.append(obs)
        if not options:
            self._ftgg_flow_active = False
            return

        try:
            from .dialogs import QuarrySelectionDialog
        except Exception:
            self._ftgg_flow_active = False
            return

        if not hasattr(self, "ftgg_observer_dialog") or self.ftgg_observer_dialog is None:
            self.ftgg_observer_dialog = QuarrySelectionDialog(self.screen.get_width(), self.screen.get_height())
        obs_dialog = self.ftgg_observer_dialog

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id
        from .decision_ui_utils import option_id_for_action

        obs_options = [DecisionOption.create("Cancel", payload={"action": "skip"})]
        for obs in options:
            obs_options.append(
                DecisionOption.create(
                    getattr(obs, "name", "Unit"),
                    payload={"target_unit_id": get_entity_id(obs)},
                )
            )
        obs_req = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "Select For the Greater Good observer.",
            player_id=getattr(player, "id", None),
            options=obs_options,
            context={"ability": "for_the_greater_good", "step": "observer"},
        )
        if self.game is not None:
            self.game.request_decision(obs_req)

        def _cancel_observer():
            skip_id = option_id_for_action(obs_req, "skip")
            if skip_id:
                resolve_decision_value(self.game, obs_req, skip_id)
            self._ftgg_flow_active = False

        def _on_observer(option_id: str):
            observer_unit, apply_result = resolve_decision_value(self.game, obs_req, option_id)
            if apply_result is None or not getattr(apply_result, "ok", False) or observer_unit is None:
                _cancel_observer()
                return
            try:
                targets = list(mgr.get_eligible_spotted_targets(observer_unit, game=game, player=player) or [])
            except Exception:
                targets = []
            if not targets:
                self._open_next_ftgg_observer_prompt(game, player)
                return
            if len(targets) == 1:
                try:
                    mgr.mark_spotted(observer_unit, targets[0], game=game, player=player)
                except Exception:
                    pass
                self._open_next_ftgg_observer_prompt(game, player)
                return

            if not hasattr(self, "ftgg_target_dialog") or self.ftgg_target_dialog is None:
                self.ftgg_target_dialog = QuarrySelectionDialog(self.screen.get_width(), self.screen.get_height())
            tgt_dialog = self.ftgg_target_dialog

            tgt_options = [DecisionOption.create("Cancel", payload={"action": "skip"})]
            for target in targets:
                tgt_options.append(
                    DecisionOption.create(
                        getattr(target, "name", "Unit"),
                        payload={"target_unit_id": get_entity_id(target)},
                    )
                )
            tgt_req = DecisionRequest.create(
                DECISION_CHOOSE_QUARRY,
                "Select For the Greater Good target.",
                player_id=getattr(player, "id", None),
                options=tgt_options,
                context={"ability": "for_the_greater_good", "step": "target"},
            )
            if self.game is not None:
                self.game.request_decision(tgt_req)

            def _cancel_target():
                skip_id = option_id_for_action(tgt_req, "skip")
                if skip_id:
                    resolve_decision_value(self.game, tgt_req, skip_id)
                self._ftgg_flow_active = False

            def _on_target(option_id: str):
                target_unit, apply_result = resolve_decision_value(self.game, tgt_req, option_id)
                if apply_result is None or not getattr(apply_result, "ok", False) or target_unit is None:
                    _cancel_target()
                    return
                try:
                    mgr.mark_spotted(observer_unit, target_unit, game=game, player=player)
                except Exception:
                    pass
                self._open_next_ftgg_observer_prompt(game, player)

            tgt_dialog.show(
                title=f"For the Greater Good - {getattr(player, 'name', 'Player')}",
                header=f"Choose a Spotted target for {getattr(observer_unit, 'name', 'Observer')}.",
                subtitle="Each enemy unit can only be Spotted once per phase.",
                on_confirm=_on_target,
                on_cancel=_cancel_target,
                decision_request=tgt_req,
            )
            try:
                self.dialog_manager.open(tgt_dialog, modal=True)
            except Exception:
                self._ftgg_flow_active = False

        obs_dialog.show(
            title=f"For the Greater Good - {getattr(player, 'name', 'Player')}",
            header="Select an Observer unit.",
            subtitle="Cancel to stop selecting Observers for this phase.",
            on_confirm=_on_observer,
            on_cancel=_cancel_observer,
            decision_request=obs_req,
        )
        try:
            self.dialog_manager.open(obs_dialog, modal=True)
        except Exception:
            self._ftgg_flow_active = False

    def _army_has_blessings_of_khorne(self, army) -> bool:
        if army is None:
            return False
        if not army_has_ability_id(army, ABILITY_BLESSINGS_OF_KHORNE):
            return False
        for unit in list(getattr(army, "units", []) or []):
            try:
                if unit.attached_unit_has_blessings_of_khorne():
                    return True
            except Exception:
                continue
        return False

    # ---------------- Battle Focus prompts ----------------

    def _battle_focus_option_label(self, option: str, mgr=None) -> str:
        opt = str(option or "").strip().upper()
        warhost = False
        try:
            warhost = bool(getattr(mgr, "is_warhost_detachment", lambda: False)())
        except Exception:
            warhost = False
        swift_bonus = 3 if warhost else 2
        reactive_bonus = 2 if warhost else 1
        labels = {
            "SWIFT_AS_THE_WIND": f"Swift as the Wind (+{swift_bonus}\" Move)",
            "FLITTING_SHADOWS": "Flitting Shadows (No Overwatch)",
            "STAR_ENGINES": "Star Engines (Advance + Shoot)",
            "SUDDEN_STRIKE": "Sudden Strike (6\" pile-in/consolidate)",
            "OPPORTUNITY_SEIZED": f"Opportunity Seized (Reactive move 1D6+{reactive_bonus}\")",
            "FADE_BACK": f"Fade Back (Reactive move 1D6+{reactive_bonus}\")",
        }
        if opt in labels:
            return labels[opt]
        return opt.replace("_", " ").title()

    def _get_battle_focus_manager(self, player):
        if player is None:
            return None
        try:
            army = player.get_army()
        except Exception:
            army = None
        return getattr(army, "battle_focus", None) if army is not None else None

    def _get_power_from_pain_manager(self, player):
        if player is None:
            return None
        try:
            army = player.get_army()
        except Exception:
            army = None
        return getattr(army, "power_from_pain", None) if army is not None else None

    def _get_prioritised_efficiency_manager(self, player):
        if player is None:
            return None
        try:
            army = player.get_army()
        except Exception:
            army = None
        return getattr(army, "prioritised_efficiency", None) if army is not None else None

    def _get_cult_ambush_manager(self, player):
        if player is None:
            return None
        try:
            army = player.get_army()
        except Exception:
            army = None
        return getattr(army, "cult_ambush", None) if army is not None else None

    def _get_acts_of_faith_manager(self, player):
        if player is None:
            return None
        try:
            army = player.get_army()
        except Exception:
            army = None
        return getattr(army, "acts_of_faith", None) if army is not None else None

    def _shadow_of_chaos_hud(self, player) -> Optional[dict]:
        if player is None or self.game is None:
            return None
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            return None
        mgr = getattr(army, "shadow_of_chaos", None)
        if mgr is None or not getattr(mgr, "army_has_shadow", lambda: False)():
            return None
        try:
            zones = set(mgr.get_shadow_zones(game=self.game, player=player))
        except Exception:
            zones = set()

        zone_labels = {
            "own": "Own Deployment Zone",
            "nml": "No Man's Land",
            "enemy": "Opponent Deployment Zone",
        }
        highlight_words = [label for key, label in zone_labels.items() if key in zones]
        hint = " | ".join(zone_labels.values())
        return {
            "label": "Shadow of Chaos Zones",
            "hint": hint,
            "highlight_words": highlight_words,
            "show_button": False,
        }

    def _battle_focus_hud_maneuver_options(self, unit, mgr) -> Dict[str, str]:
        if unit is None or mgr is None or self.game is None:
            return {}
        available_actions = []
        try:
            engagement_state = unit.get_engagement_state(self.game.map)
            available_actions = list(unit.get_available_move_actions(engagement_state.value) or [])
        except Exception:
            available_actions = []

        action_map = {}
        try:
            from warhammer40k_ai.units.unit import MovementAction
            action_map = {
                MovementAction.MOVE.value: "move",
                MovementAction.ADVANCE.value: "advance",
                MovementAction.FALL_BACK.value: "fall_back",
            }
        except Exception:
            action_map = {}

        actions = []
        for act in available_actions:
            act_name = None
            if isinstance(act, str):
                act_name = act
            else:
                act_name = action_map.get(act)
            if act_name in ("move", "advance", "fall_back") and act_name not in actions:
                actions.append(act_name)

        if not actions:
            return {}

        maneuver_to_label: Dict[str, str] = {}
        for action in actions:
            try:
                options = mgr.get_move_maneuver_options(unit, action, self.game)
            except Exception:
                options = []
            for maneuver in options:
                if maneuver not in maneuver_to_label:
                    maneuver_to_label[maneuver] = self._battle_focus_option_label(maneuver, mgr)

        return {label: maneuver for maneuver, label in maneuver_to_label.items()}

    def _battle_focus_hud_enabled(self, player, mgr) -> bool:
        if self._battle_focus_flow_active:
            return False
        if self.game is None:
            return False
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return False
        except Exception:
            return False
        if int(getattr(mgr, "tokens", 0) or 0) <= 0:
            return False
        if not self.game.is_movement_phase():
            return False
        try:
            if self.game.get_current_player() is not player:
                return False
        except Exception:
            return False
        unit = getattr(self, "selected_unit", None)
        if unit is None:
            return False
        try:
            if unit.get_parent_army() != player.get_army():
                return False
        except Exception:
            return False
        return bool(self._battle_focus_hud_maneuver_options(unit, mgr))

    def _battle_focus_hud_hint(self, player, mgr) -> str:
        if self.game is None:
            return ""
        if self._battle_focus_flow_active:
            return "Battle Focus selection already active."
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return ""
        except Exception:
            return ""
        if int(getattr(mgr, "tokens", 0) or 0) <= 0:
            return "No tokens remaining."
        if not self.game.is_movement_phase():
            return "Available during the Movement phase."
        try:
            if self.game.get_current_player() is not player:
                return "Available during your Movement phase."
        except Exception:
            return ""
        unit = getattr(self, "selected_unit", None)
        if unit is None:
            return "Select a unit to use a token."
        try:
            if unit.get_parent_army() != player.get_army():
                return "Select one of your units."
        except Exception:
            return "Select one of your units."
        if not self._battle_focus_hud_maneuver_options(unit, mgr):
            return "No eligible maneuvers for the selected unit."
        return ""

    def _open_battle_focus_hud_use(self, player) -> None:
        if self._battle_focus_flow_active:
            return
        if self.game is None or player is None:
            return
        mgr = self._get_battle_focus_manager(player)
        if mgr is None:
            return
        if not self._battle_focus_hud_enabled(player, mgr):
            return

        unit = getattr(self, "selected_unit", None)
        if unit is None:
            return
        options = self._battle_focus_hud_maneuver_options(unit, mgr)
        if not options:
            return

        tokens = int(getattr(mgr, "tokens", 0) or 0)
        title = "Battle Focus"

        if len(options) == 1:
            label = next(iter(options.keys()))
            maneuver = options.get(label)
            msg = f"Use {label} for {getattr(unit, 'name', 'unit')}?\n\nTokens remaining: {tokens}"

            def _done(choice: bool):
                try:
                    if choice and maneuver:
                        mgr.apply_maneuver(unit, maneuver, self.game)
                finally:
                    self._battle_focus_flow_active = False

            self._battle_focus_flow_active = True
            try:
                self._request_yes_no(title, msg, "Use", "Cancel", _done, player=player)
            except Exception:
                self._battle_focus_flow_active = False
            return

        subtitle = f"{getattr(unit, 'name', 'unit')} - choose a maneuver (Tokens: {tokens})"

        from ..engine.decision_kinds import DECISION_CHOOSE_ASPECT
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id
        from .decision_ui_utils import option_id_for_action

        unit_id = get_entity_id(unit)
        req_options = [DecisionOption.create("Skip", payload={"action": "skip"})]
        for label, maneuver in options.items():
            req_options.append(
                DecisionOption.create(
                    label,
                    payload={"choice": str(maneuver), "unit_id": unit_id},
                )
            )
        req = DecisionRequest.create(
            DECISION_CHOOSE_ASPECT,
            "Select Battle Focus maneuver.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"unit_id": unit_id, "ability": "battle_focus"},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_confirm(option_id: str):
            self._battle_focus_flow_active = False
            value, apply_result = resolve_decision_value(self.game, req, option_id)
            if apply_result is None or not getattr(apply_result, "ok", False):
                return
            if value:
                mgr.apply_maneuver(unit, value, self.game)

        def _on_cancel():
            skip_id = option_id_for_action(req, "skip")
            if skip_id:
                resolve_decision_value(self.game, req, skip_id)
            self._battle_focus_flow_active = False

        self._battle_focus_flow_active = True
        self.battle_focus_dialog.show(
            list(options.keys()),
            None,
            _on_confirm,
            title=title,
            subtitle=subtitle,
            on_cancel=_on_cancel,
            decision_request=req,
        )
        try:
            self.dialog_manager.open(self.battle_focus_dialog, modal=True)
        except Exception:
            self._battle_focus_flow_active = False

    def _maybe_prompt_battle_focus_move(self, unit, action: str, on_done: Callable[[], None]) -> None:
        if on_done is None:
            return
        if self._battle_focus_flow_active:
            on_done()
            return

        mgr = None
        player = None
        try:
            army = unit.get_parent_army()
            mgr = getattr(army, "battle_focus", None) if army is not None else None
            player = getattr(army, "player", None) if army is not None else None
        except Exception:
            mgr = None
            player = None
        if mgr is None or player is None or self.game is None:
            on_done()
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                on_done()
                return
        except Exception:
            on_done()
            return

        options = mgr.get_move_maneuver_options(unit, action, self.game)
        if not options:
            on_done()
            return

        tokens = int(getattr(mgr, "tokens", 0) or 0)
        title = "Battle Focus"

        if len(options) == 1:
            opt = options[0]
            label = self._battle_focus_option_label(opt, mgr)
            msg = f"Use {label} for {getattr(unit, 'name', 'unit')}?\n\nTokens remaining: {tokens}"

            def _done(choice: bool):
                try:
                    if choice:
                        mgr.apply_maneuver(unit, opt, self.game)
                finally:
                    self._battle_focus_flow_active = False
                    on_done()

            self._battle_focus_flow_active = True
            try:
                self._request_yes_no(title, msg, "Use", "Skip", _done, player=player)
            except Exception:
                self._battle_focus_flow_active = False
                on_done()
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_ASPECT
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id
        from .decision_ui_utils import option_id_for_action

        unit_id = get_entity_id(unit)
        req_options = [DecisionOption.create("Skip", payload={"action": "skip"})]
        for opt in options:
            label = self._battle_focus_option_label(opt, mgr)
            req_options.append(
                DecisionOption.create(
                    label,
                    payload={"choice": str(opt), "unit_id": unit_id},
                )
            )
        req = DecisionRequest.create(
            DECISION_CHOOSE_ASPECT,
            "Select Battle Focus maneuver.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"unit_id": unit_id, "ability": "battle_focus", "action": action},
        )
        if self.game is not None:
            self.game.request_decision(req)
        choices = [opt.label for opt in req_options]
        subtitle = f"Choose an Agile Manoeuvre for {getattr(unit, 'name', 'unit')} (Tokens: {tokens})"

        def _on_confirm(option_id: str):
            self._battle_focus_flow_active = False
            value, apply_result = resolve_decision_value(self.game, req, option_id)
            if apply_result is not None and getattr(apply_result, "ok", False) and value:
                mgr.apply_maneuver(unit, value, self.game)
            on_done()

        def _on_cancel():
            skip_id = option_id_for_action(req, "skip")
            if skip_id:
                resolve_decision_value(self.game, req, skip_id)
            self._battle_focus_flow_active = False
            on_done()

        self._battle_focus_flow_active = True
        self.battle_focus_dialog.show(
            choices,
            None,
            _on_confirm,
            title=title,
            subtitle=subtitle,
            on_cancel=_on_cancel,
            decision_request=req,
        )
        try:
            self.dialog_manager.open(self.battle_focus_dialog, modal=True)
        except Exception:
            self._battle_focus_flow_active = False
            on_done()

    def _maybe_prompt_battle_focus_charge(self, unit, target_unit, on_done: Callable[[], None]) -> None:
        if on_done is None:
            return
        if self._battle_focus_flow_active:
            on_done()
            return

        mgr = None
        player = None
        try:
            army = unit.get_parent_army()
            mgr = getattr(army, "battle_focus", None) if army is not None else None
            player = getattr(army, "player", None) if army is not None else None
        except Exception:
            mgr = None
            player = None
        if mgr is None or player is None or self.game is None:
            on_done()
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                on_done()
                return
        except Exception:
            on_done()
            return

        try:
            if not mgr.can_use_flitting_on_charge(unit, self.game):
                on_done()
                return
        except Exception:
            on_done()
            return

        tokens = int(getattr(mgr, "tokens", 0) or 0)
        label = self._battle_focus_option_label(getattr(mgr, "MANEUVER_FLITTING", "FLITTING_SHADOWS"), mgr)
        target_name = getattr(target_unit, "name", "enemy unit")
        msg = f"Use {label} for {getattr(unit, 'name', 'unit')} while charging {target_name}?\n\nTokens remaining: {tokens}"

        def _done(choice: bool):
            try:
                if choice:
                    mgr.apply_maneuver(unit, mgr.MANEUVER_FLITTING, self.game)
            finally:
                self._battle_focus_flow_active = False
                on_done()

        self._battle_focus_flow_active = True
        try:
            self._request_yes_no("Battle Focus", msg, "Use", "Skip", _done, player=player)
        except Exception:
            self._battle_focus_flow_active = False
            on_done()

    def _maybe_prompt_battle_focus_sudden_strike(self, unit, on_done: Callable[[], None]) -> None:
        if on_done is None:
            return
        if self._battle_focus_flow_active:
            on_done()
            return

        mgr = None
        player = None
        try:
            army = unit.get_parent_army()
            mgr = getattr(army, "battle_focus", None) if army is not None else None
            player = getattr(army, "player", None) if army is not None else None
        except Exception:
            mgr = None
            player = None
        if mgr is None or player is None or self.game is None:
            on_done()
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                on_done()
                return
        except Exception:
            on_done()
            return

        try:
            if not mgr.can_use_sudden_strike(unit, self.game):
                on_done()
                return
        except Exception:
            on_done()
            return

        tokens = int(getattr(mgr, "tokens", 0) or 0)
        label = self._battle_focus_option_label(getattr(mgr, "MANEUVER_SUDDEN_STRIKE", "SUDDEN_STRIKE"), mgr)
        msg = f"Use {label} for {getattr(unit, 'name', 'unit')}?\n\nTokens remaining: {tokens}"

        def _done(choice: bool):
            try:
                if choice:
                    mgr.apply_maneuver(unit, mgr.MANEUVER_SUDDEN_STRIKE, self.game)
            finally:
                self._battle_focus_flow_active = False
                on_done()

        self._battle_focus_flow_active = True
        try:
            self._request_yes_no("Battle Focus", msg, "Use", "Skip", _done, player=player)
        except Exception:
            self._battle_focus_flow_active = False
            on_done()

    def _open_battle_focus_reactive_move(self, unit) -> None:
        max_distance = 0.0
        try:
            sr = getattr(unit, "special_rules", None)
            if isinstance(sr, dict):
                max_distance = float(sr.get("battle_focus_reactive_move_max", 0) or 0)
        except Exception:
            max_distance = 0.0
        if max_distance <= 0:
            self._battle_focus_flow_active = False
            return

        def _done(_completed: bool):
            self._battle_focus_flow_active = False

        try:
            self.phase_manager._request_move_unit_decision(
                unit,
                "reactive",
                _done,
                max_distance=max_distance,
            )
        except Exception:
            self._battle_focus_flow_active = False

    def _on_battle_focus_opportunity_prompt(self, player=None, moving_unit=None, candidates=None, manager=None, **_kwargs):
        if self._battle_focus_flow_active:
            return
        if player is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return
        cand = list(candidates or [])
        if not cand:
            return
        mgr = manager
        if mgr is None:
            try:
                army = player.get_army()
                mgr = getattr(army, "battle_focus", None) if army is not None else None
            except Exception:
                mgr = None
        if mgr is None:
            return

        enemy_name = getattr(moving_unit, "name", "enemy unit")
        subtitle = f"Enemy unit fell back: {enemy_name}. Select a unit to move."

        from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id
        from .decision_ui_utils import option_id_for_action

        req_options = [DecisionOption.create("Skip", payload={"action": "skip"})]
        for unit in cand:
            req_options.append(
                DecisionOption.create(
                    getattr(unit, "name", "Unit"),
                    payload={"unit_id": get_entity_id(unit)},
                )
            )
        req = DecisionRequest.create(
            DECISION_SELECT_OVERWATCH_SHOOTER,
            "Select Battle Focus reactive unit.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"ability": "battle_focus", "maneuver": "opportunity"},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_confirm(option_id: str):
            value, apply_result = resolve_decision_value(self.game, req, option_id)
            if apply_result is None or not getattr(apply_result, "ok", False) or value is None:
                self._battle_focus_flow_active = False
                return
            mgr.apply_reactive_maneuver(value, mgr.MANEUVER_OPPORTUNITY, self.game)
            self._open_battle_focus_reactive_move(value)

        def _on_cancel():
            skip_id = option_id_for_action(req, "skip")
            if skip_id:
                resolve_decision_value(self.game, req, skip_id)
            self._battle_focus_flow_active = False

        self._battle_focus_flow_active = True
        self.battle_focus_dialog.show(
            cand,
            moving_unit,
            _on_confirm,
            title="Battle Focus: Opportunity Seized",
            subtitle=subtitle,
            on_cancel=_on_cancel,
            decision_request=req,
        )
        try:
            self.dialog_manager.open(self.battle_focus_dialog, modal=True)
        except Exception:
            self._battle_focus_flow_active = False

    def _on_battle_focus_fade_back_prompt(self, player=None, attacker_unit=None, candidates=None, hits_by_unit=None, manager=None, **_kwargs):
        if self._battle_focus_flow_active:
            return
        if player is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return
        cand = list(candidates or [])
        if not cand:
            return
        mgr = manager
        if mgr is None:
            try:
                army = player.get_army()
                mgr = getattr(army, "battle_focus", None) if army is not None else None
            except Exception:
                mgr = None
        if mgr is None:
            return

        from ..engine.decision_kinds import DECISION_SELECT_OVERWATCH_SHOOTER
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id
        from .decision_ui_utils import option_id_for_action

        used = set()
        req_options = [DecisionOption.create("Skip", payload={"action": "skip"})]
        for unit in cand:
            try:
                hits = int((hits_by_unit or {}).get(unit, 0) or 0)
            except Exception:
                hits = 0
            base = f"{getattr(unit, 'name', 'unit')} (Hits: {hits})"
            label = base
            idx = 2
            while label in used:
                label = f"{base} [{idx}]"
                idx += 1
            used.add(label)
            req_options.append(
                DecisionOption.create(
                    label,
                    payload={"unit_id": get_entity_id(unit)},
                )
            )
        req = DecisionRequest.create(
            DECISION_SELECT_OVERWATCH_SHOOTER,
            "Select Battle Focus unit to fade back.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"ability": "battle_focus", "maneuver": "fade_back"},
        )
        if self.game is not None:
            self.game.request_decision(req)

        attacker_name = getattr(attacker_unit, "name", "attacker")
        subtitle = f"{attacker_name} scored hits. Select a unit to move."

        def _on_confirm(option_id: str):
            value, apply_result = resolve_decision_value(self.game, req, option_id)
            if apply_result is None or not getattr(apply_result, "ok", False) or value is None:
                self._battle_focus_flow_active = False
                return
            mgr.apply_reactive_maneuver(value, mgr.MANEUVER_FADE_BACK, self.game)
            self._open_battle_focus_reactive_move(value)

        def _on_cancel():
            skip_id = option_id_for_action(req, "skip")
            if skip_id:
                resolve_decision_value(self.game, req, skip_id)
            self._battle_focus_flow_active = False

        self._battle_focus_flow_active = True
        self.battle_focus_dialog.show(
            cand,
            attacker_unit,
            _on_confirm,
            title="Battle Focus: Fade Back",
            subtitle=subtitle,
            on_cancel=_on_cancel,
            decision_request=req,
        )
        try:
            self.dialog_manager.open(self.battle_focus_dialog, modal=True)
        except Exception:
            self._battle_focus_flow_active = False

    def _on_cabal_temporal_surge_move(self, player=None, unit=None, max_distance=None, **_kwargs):
        if player is None or unit is None or self.game is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return
        try:
            if unit.get_parent_army() != player.get_army():
                return
        except Exception:
            return
        try:
            max_dist = float(max_distance or 0)
        except Exception:
            max_dist = 0.0
        if max_dist <= 0:
            return

        def _done(_completed: bool):
            pass

        try:
            self.phase_manager._request_move_unit_decision(
                unit,
                "reactive",
                _done,
                max_distance=max_dist,
            )
        except Exception:
            return

    def _on_fire_and_fade_move(self, player=None, unit=None, max_distance=None, decision_request=None, **_kwargs):
        if player is None or unit is None or self.game is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return
        try:
            if unit.get_parent_army() != player.get_army():
                return
        except Exception:
            return
        try:
            max_dist = float(max_distance or 0)
        except Exception:
            max_dist = 0.0
        if max_dist <= 0:
            return
        if decision_request is None:
            return

        def _done(_completed: bool):
            pass

        try:
            self.phase_manager._request_move_unit_decision(
                unit,
                "reactive",
                _done,
                max_distance=max_dist,
                decision_request=decision_request,
            )
        except Exception:
            return

    def _on_reactive_reposition_move(self, player=None, unit=None, max_distance=None, decision_request=None, **_kwargs):
        if player is None or unit is None or self.game is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return
        try:
            if unit.get_parent_army() != player.get_army():
                return
        except Exception:
            return
        try:
            max_dist = float(max_distance or 0)
        except Exception:
            max_dist = 0.0
        if max_dist <= 0:
            return
        if decision_request is None:
            return

        def _done(_completed: bool):
            pass

        try:
            self.phase_manager._request_move_unit_decision(
                unit,
                "reactive",
                _done,
                max_distance=max_dist,
                decision_request=decision_request,
            )
        except Exception:
            return

    def _on_cabal_ritual_resolved(
        self,
        player=None,
        ritual=None,
        caster_unit=None,
        caster_model=None,
        target_unit=None,
        result=None,
        **_kwargs,
    ):
        if self.game is None or ritual is None or result is None:
            return
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return
        except Exception:
            return

        rolls = list(result.get("rolls") or [])
        if not rolls:
            return
        total = int(result.get("total") or 0)
        rolls_text = " + ".join(str(r) for r in rolls)
        caster_name = getattr(caster_model, "name", None) or getattr(caster_unit, "name", "Caster")
        target_name = getattr(target_unit, "name", None) or "no target"
        try:
            warp_charge = int(getattr(ritual, "warp_charge", 0) or 0)
        except Exception:
            warp_charge = 0
        channel_text = "Yes" if result.get("channeled") else "No"
        status = "Success" if result.get("success") else "Failed"
        reason = str(result.get("reason") or "")
        if reason and not result.get("success"):
            status = f"Failed ({reason})"
        mw_self = int(result.get("mortal_wounds") or 0)
        mw_target = int(result.get("target_mortal_wounds") or 0)

        body = (
            f"Caster: {caster_name} | Target: {target_name} | Ritual: {ritual.name} (WC {warp_charge}) | "
            f"Rolls: {rolls_text} = {total} | Channel the Warp: {channel_text} | "
            f"Result: {status} | Mortal wounds: self {mw_self}, target {mw_target}"
        )
        self._mission_popup = {"title": "Cabal of Sorcerers", "body": body, "image_path": None}

    # ---------------- Cabal of Sorcerers HUD ----------------

    def _get_cabal_manager(self, player):
        if player is None:
            return None
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            return None
        mgr = getattr(army, "cabal_of_sorcerers", None)
        if mgr is None:
            return None
        try:
            if not getattr(mgr, "_army_has_cabal", lambda: False)():
                return None
        except Exception:
            return None
        return mgr

    def _cabal_hud_enabled(self, player, mgr) -> bool:
        if self._cabal_flow_active:
            return False
        if self.game is None:
            return False
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return False
        except Exception:
            return False
        if not self.game.is_shooting_phase():
            return False
        try:
            if self.game.get_current_player() is not player:
                return False
        except Exception:
            return False
        try:
            casters = list(mgr.get_eligible_casters(game=self.game, player=player) or [])
        except Exception:
            casters = []
        if not casters:
            return False
        try:
            rituals = list(mgr.get_available_rituals() or [])
        except Exception:
            rituals = []
        return bool(rituals)

    def _cabal_hud_hint(self, player, mgr) -> str:
        if self.game is None:
            return ""
        if self._cabal_flow_active:
            return "Cabal ritual selection already active."
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return ""
        except Exception:
            return ""
        if not self.game.is_shooting_phase():
            return "Available during the Shooting phase."
        try:
            if self.game.get_current_player() is not player:
                return "Available during your Shooting phase."
        except Exception:
            return ""
        try:
            casters = list(mgr.get_eligible_casters(game=self.game, player=player) or [])
        except Exception:
            casters = []
        if not casters:
            return "No eligible Cabal models available."
        try:
            rituals = list(mgr.get_available_rituals() or [])
        except Exception:
            rituals = []
        if not rituals:
            return "No rituals remaining this turn."
        return ""

    def _open_cabal_hud_use(self, player) -> None:
        if self._cabal_flow_active:
            return
        if self.game is None or player is None:
            return
        mgr = self._get_cabal_manager(player)
        if mgr is None:
            return
        if not self._cabal_hud_enabled(player, mgr):
            return

        try:
            casters = list(mgr.get_eligible_casters(game=self.game, player=player) or [])
        except Exception:
            casters = []
        if not casters:
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_CHOOSE_RITUALS, DECISION_SELECT_TARGET_MODEL
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id
        from .decision_ui_utils import option_id_for_action

        if self.cabal_caster_dialog is None:
            try:
                from .dialogs import QuarrySelectionDialog
                sw, sh = self.screen.get_width(), self.screen.get_height()
                self.cabal_caster_dialog = QuarrySelectionDialog(sw, sh)
            except Exception:
                self.cabal_caster_dialog = None
        if self.cabal_caster_dialog is None:
            return

        def _cancel_flow():
            self._cabal_flow_active = False

        caster_options = [DecisionOption.create("Cancel", payload={"action": "skip"})]
        caster_map = {}
        used = set()
        for unit, model in casters:
            label = f"{getattr(unit, 'name', 'Unit')} - {getattr(model, 'name', 'Model')}"
            base = label
            idx = 2
            while label in used:
                label = f"{base} [{idx}]"
                idx += 1
            used.add(label)
            opt = DecisionOption.create(label, payload={"model_id": get_entity_id(model)})
            caster_options.append(opt)
            caster_map[opt.option_id] = (unit, model)
        caster_req = DecisionRequest.create(
            DECISION_SELECT_TARGET_MODEL,
            "Select Cabal caster.",
            player_id=getattr(player, "id", None),
            options=caster_options,
            context={"ability": "cabal", "step": "caster"},
        )
        if self.game is not None:
            self.game.request_decision(caster_req)

        def _on_caster(option_id: str):
            value, apply_result = resolve_decision_value(self.game, caster_req, option_id)
            if apply_result is None or not getattr(apply_result, "ok", False) or value is None:
                _cancel_flow()
                return
            caster_model = value
            caster_unit = getattr(caster_model, "parent_unit", None) or caster_map.get(option_id, (None, None))[0]
            rituals = list(mgr.get_available_rituals() or [])
            if not rituals:
                _cancel_flow()
                return

            if self.cabal_ritual_dialog is None:
                try:
                    from .dialogs import CabalOfSorcerersDialog
                    sw, sh = self.screen.get_width(), self.screen.get_height()
                    self.cabal_ritual_dialog = CabalOfSorcerersDialog(sw, sh)
                except Exception:
                    self.cabal_ritual_dialog = None
            if self.cabal_ritual_dialog is None:
                _cancel_flow()
                return

            subtitle = f"{getattr(caster_unit, 'name', 'Unit')} - choose a ritual"
            ritual_options = [DecisionOption.create("Cancel", payload={"action": "skip"})]
            ritual_by_option = {}
            for ritual in rituals:
                payload = {
                    "ritual_key": getattr(ritual, "key", None),
                    "caster_model_id": get_entity_id(caster_model),
                    "warp_charge": getattr(ritual, "warp_charge", None),
                    "summary": getattr(ritual, "summary", "") or getattr(ritual, "effect", ""),
                }
                opt = DecisionOption.create(getattr(ritual, "name", "Ritual"), payload=payload)
                ritual_options.append(opt)
                ritual_by_option[opt.option_id] = ritual
            ritual_req = DecisionRequest.create(
                DECISION_CHOOSE_RITUALS,
                "Select Cabal ritual.",
                player_id=getattr(player, "id", None),
                options=ritual_options,
                context={"army_id": get_entity_id(player.get_army()) if player is not None else ""},
            )
            if self.game is not None:
                self.game.request_decision(ritual_req)

            def _on_ritual(option_id: str):
                if option_id_for_action(ritual_req, "skip") == option_id:
                    resolve_decision_value(self.game, ritual_req, option_id)
                    _cancel_flow()
                    return
                ritual = ritual_by_option.get(option_id)
                if ritual is None:
                    _cancel_flow()
                    return

                game_map = getattr(self.game, "map", None)
                targets = list(mgr.get_eligible_targets(ritual, caster_model, game_map) or [])
                if not targets:
                    resolve_decision_value(self.game, ritual_req, option_id_for_action(ritual_req, "skip") or option_id)
                    _cancel_flow()
                    return

                if self.cabal_target_dialog is None:
                    try:
                        from .dialogs import QuarrySelectionDialog
                        sw, sh = self.screen.get_width(), self.screen.get_height()
                        self.cabal_target_dialog = QuarrySelectionDialog(sw, sh)
                    except Exception:
                        self.cabal_target_dialog = None
                if self.cabal_target_dialog is None:
                    _cancel_flow()
                    return

                target_title = f"{ritual.name} Target"
                target_header = "Choose a target unit."
                target_options = [DecisionOption.create("Cancel", payload={"action": "skip"})]
                for tgt in targets:
                    target_options.append(
                        DecisionOption.create(
                            getattr(tgt, "name", "Unit"),
                            payload={"target_unit_id": get_entity_id(tgt)},
                        )
                    )
                target_req = DecisionRequest.create(
                    DECISION_CHOOSE_QUARRY,
                    "Select Cabal ritual target.",
                    player_id=getattr(player, "id", None),
                    options=target_options,
                    context={"ritual_key": getattr(ritual, "key", None)},
                )
                if self.game is not None:
                    self.game.request_decision(target_req)

                def _on_target(target_option_id: str):
                    target_unit, apply_result = resolve_decision_value(self.game, target_req, target_option_id)
                    if apply_result is None or not getattr(apply_result, "ok", False) or target_unit is None:
                        _cancel_flow()
                        return
                    r1 = int(get_roll("D6") or 0)
                    r2 = int(get_roll("D6") or 0)
                    roll_sum = r1 + r2
                    msg = (
                        f"{getattr(caster_unit, 'name', 'Unit')} attempts {ritual.name}.\n"
                        f"Psychic test roll: {r1} + {r2} = {roll_sum}\n\n"
                        "Channel the Warp?"
                    )

                    def _on_channel(choice: bool):
                        try:
                            resolve_decision_value(
                                self.game,
                                ritual_req,
                                option_id,
                                result_payload={
                                    "target_unit_id": get_entity_id(target_unit),
                                    "rolls": [r1, r2],
                                    "channel_decision": choice,
                                    "caster_model_id": get_entity_id(caster_model),
                                },
                            )
                        finally:
                            self._cabal_flow_active = False

                    self._request_yes_no("Cabal of Sorcerers", msg, "Channel", "No", _on_channel, player=player)

                def _on_target_cancel():
                    skip_id = option_id_for_action(target_req, "skip")
                    if skip_id:
                        resolve_decision_value(self.game, target_req, skip_id)
                    _cancel_flow()

                self.cabal_target_dialog.show(
                    title=target_title,
                    header=target_header,
                    subtitle="Select a valid unit within 24\" and visible.",
                    on_confirm=_on_target,
                    on_cancel=_on_target_cancel,
                    decision_request=target_req,
                )
                try:
                    self.dialog_manager.open(self.cabal_target_dialog, modal=True)
                except Exception:
                    _cancel_flow()

            def _on_ritual_cancel():
                skip_id = option_id_for_action(ritual_req, "skip")
                if skip_id:
                    resolve_decision_value(self.game, ritual_req, skip_id)
                _cancel_flow()

            self.cabal_ritual_dialog.show(
                on_confirm=_on_ritual,
                on_cancel=_on_ritual_cancel,
                subtitle=subtitle,
                decision_request=ritual_req,
            )
            try:
                self.dialog_manager.open(self.cabal_ritual_dialog, modal=True)
            except Exception:
                _cancel_flow()

        def _on_caster_cancel():
            skip_id = option_id_for_action(caster_req, "skip")
            if skip_id:
                resolve_decision_value(self.game, caster_req, skip_id)
            _cancel_flow()

        self._cabal_flow_active = True
        self.cabal_caster_dialog.show(
            title="Cabal of Sorcerers",
            header="Choose a model to manifest a ritual.",
            subtitle="Each model and ritual can be used once per turn.",
            on_confirm=_on_caster,
            on_cancel=_on_caster_cancel,
            decision_request=caster_req,
        )
        try:
            self.dialog_manager.open(self.cabal_caster_dialog, modal=True)
        except Exception:
            self._cabal_flow_active = False
    def _roll_reroll_provider(self, player=None, unit=None, roll_type: str = "", value=None, dice=None, **_kwargs):
        """
        Blocking modal prompt for rule-based (free) re-rolls.
        Returns True to reroll, False to keep.
        """
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return False
        except Exception:
            return False

        try:
            from .dialogs import RollRerollDialog
        except Exception:
            return False

        if not hasattr(self, "roll_reroll_dialog") or self.roll_reroll_dialog is None:
            self.roll_reroll_dialog = RollRerollDialog(self.screen.get_width(), self.screen.get_height())

        rt = str(roll_type or "").strip().lower()
        title = "Re-roll?"
        if rt == "advance":
            title = "Advance Roll"
        elif rt == "charge":
            title = "Charge Roll"
        elif rt in ("blood_surge", "blood surge"):
            title = "Blood Surge Roll"
        elif rt == "hit":
            title = "Hit Roll"
        elif rt == "wound":
            title = "Wound Roll"

        ulabel = getattr(unit, "name", "Unit")
        msg = f"{ulabel} rolled {value}."
        try:
            if rt == "charge" and dice:
                msg = f"{ulabel} rolled {value} (dice: {list(dice)})."
        except Exception:
            pass
        # For attack rolls, show needed/eligible status with colored border
        roll_text = ""
        roll_border = None
        try:
            needed = _kwargs.get("needed", None)
            success = _kwargs.get("success", None)
            if rt in ("hit", "wound") and needed is not None and success is not None:
                roll_text = f"Rolled {int(value)} (need {int(needed)}+)"
                roll_border = "success" if bool(success) else "fail"
        except Exception:
            roll_text = ""
            roll_border = None

        if rt in ("hit", "wound"):
            reason = str(_kwargs.get("reason", "") or "").strip()
            extra = "Eligible for re-roll"
            if reason:
                extra = f"{extra} ({reason})"
            msg = f"{msg}\n\n{extra}. You may re-roll even if successful."
        else:
            msg = f"{msg}\n\nYou may re-roll this {rt} roll."

        dlg = self.roll_reroll_dialog
        choice_holder = {"choice": False, "done": False}

        from ..engine.decision_kinds import DECISION_REROLL_ROLL
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value

        allow_reroll = True
        try:
            if "allow_reroll" in _kwargs:
                allow_reroll = bool(_kwargs.get("allow_reroll", True))
        except Exception:
            allow_reroll = True

        unit_id = ""
        try:
            unit_id = get_entity_id(unit)
        except Exception:
            unit_id = ""
        options = [DecisionOption.create("Keep", payload={"reroll": False})]
        if allow_reroll:
            options.append(DecisionOption.create("Re-roll", payload={"reroll": True}))
        req = DecisionRequest.create(
            DECISION_REROLL_ROLL,
            title or "Re-roll?",
            player_id=getattr(player, "id", None) if player is not None else None,
            options=options,
            context={
                "roll_type": rt,
                "roll_value": value,
                "unit_id": unit_id,
            },
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_choice(option_id: str):
            value, apply_result = resolve_decision_value(self.game, req, option_id)
            if apply_result is None or not getattr(apply_result, "ok", False):
                value = False
            choice_holder["choice"] = bool(value)
            choice_holder["done"] = True

        dlg.show(
            title=title,
            message=msg,
            roll_text=roll_text,
            roll_border=roll_border,
            allow_reroll=allow_reroll,
            callback=_on_choice,
            keep_label="Keep",
            reroll_label="Re-roll",
            decision_request=req,
        )
        try:
            self.dialog_manager.open(dlg, modal=True)
        except Exception:
            pass

        clock = pygame.time.Clock()
        while dlg.visible and not choice_holder["done"]:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return False
                try:
                    self.dialog_manager.handle_event(event)
                except Exception:
                    pass
            try:
                self.draw()
            except Exception:
                try:
                    dlg.draw(self.screen)
                    pygame.display.update()
                except Exception:
                    pass
            clock.tick(60)

        return bool(choice_holder["choice"])

    def _aspect_shrine_provider(
        self,
        player=None,
        unit=None,
        roll_type: str = "",
        value=None,
        needed=None,
        tokens_remaining: int = 0,
        **_kwargs,
    ):
        """
        Blocking modal prompt for Aspect Shrine Token usage.
        Returns: "use", "skip", or "suppress".
        """
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return "skip"
        except Exception:
            return "skip"

        try:
            from .dialogs import AspectShrinePromptDialog
        except Exception:
            return "skip"

        if not hasattr(self, "aspect_shrine_prompt_dialog") or self.aspect_shrine_prompt_dialog is None:
            self.aspect_shrine_prompt_dialog = AspectShrinePromptDialog(self.screen.get_width(), self.screen.get_height())

        rt = str(roll_type or "").strip().lower()
        title = "Aspect Shrine Token"
        if rt == "hit":
            title = "Aspect Shrine Token (Hit)"
        elif rt == "wound":
            title = "Aspect Shrine Token (Wound)"

        ulabel = getattr(unit, "name", "Unit")
        roll_val = value
        try:
            roll_val = int(value)
        except Exception:
            roll_val = value

        roll_text = f"Rolled {roll_val}"
        try:
            if needed is not None:
                roll_text = f"Rolled {int(roll_val)} (need {int(needed)}+)"
        except Exception:
            pass

        remaining_txt = ""
        try:
            remaining_txt = f"Tokens remaining: {int(tokens_remaining)}"
        except Exception:
            remaining_txt = ""

        msg = f"{ulabel} can use an Aspect Shrine token to change this {rt or 'roll'} to an unmodified 6."
        if remaining_txt:
            msg = f"{msg}\n{remaining_txt}"

        dlg = self.aspect_shrine_prompt_dialog
        choice_holder = {"choice": "skip", "done": False}

        from ..engine.decision_kinds import DECISION_CHOOSE_ASPECT
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id

        unit_id = ""
        try:
            unit_id = get_entity_id(unit)
        except Exception:
            unit_id = ""
        options = [
            DecisionOption.create("Use", payload={"choice": "use"}),
            DecisionOption.create("Don't Use", payload={"choice": "skip"}),
            DecisionOption.create("Don't Use for this Unit", payload={"choice": "suppress"}),
        ]
        req = DecisionRequest.create(
            DECISION_CHOOSE_ASPECT,
            title or "Aspect Shrine Token",
            player_id=getattr(player, "id", None) if player is not None else None,
            options=options,
            context={"unit_id": unit_id, "roll_type": rt, "roll_value": roll_val},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_choice(option_id: str):
            value, apply_result = resolve_decision_value(self.game, req, option_id)
            if apply_result is None or not getattr(apply_result, "ok", False):
                value = "skip"
            choice_holder["choice"] = value
            choice_holder["done"] = True

        dlg.show(
            title=title,
            message=msg,
            roll_text=roll_text,
            callback=_on_choice,
            decision_request=req,
        )
        try:
            self.dialog_manager.open(dlg, modal=True)
        except Exception:
            pass

        clock = pygame.time.Clock()
        while dlg.visible and not choice_holder["done"]:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return "skip"
                try:
                    self.dialog_manager.handle_event(event)
                except Exception:
                    pass
            try:
                self.draw()
            except Exception:
                try:
                    dlg.draw(self.screen)
                    pygame.display.update()
                except Exception:
                    pass
            clock.tick(60)

        return str(choice_holder["choice"] or "skip")

    def _miracle_dice_provider(
        self,
        player=None,
        unit=None,
        roll_type: str = "",
        dice_count: int = 1,
        die_faces: int = 6,
        pool: Optional[list[int]] = None,
        **_kwargs,
    ):
        """
        Blocking modal prompt for selecting a Miracle die to substitute.
        Returns the chosen die value, or None to skip.
        """
        try:
            if player is None or not getattr(player, "has_control", lambda: False)():
                return None
        except Exception:
            return None

        values = list(pool or [])
        if not values:
            return None

        try:
            from .dialogs import MiracleDiceDialog
        except Exception:
            return None

        if not hasattr(self, "miracle_dice_dialog") or self.miracle_dice_dialog is None:
            self.miracle_dice_dialog = MiracleDiceDialog(self.screen.get_width(), self.screen.get_height())

        rt = str(roll_type or "").strip().lower()
        title = "Acts of Faith"
        ulabel = getattr(unit, "name", "Unit")
        msg = f"{ulabel} can perform an Act of Faith.\nChoose a Miracle die to substitute for this {rt or 'roll'}."
        try:
            if int(dice_count or 1) > 1:
                msg += f"\nThis replaces 1 of {int(dice_count)} dice."
        except Exception:
            pass
        try:
            needed = _kwargs.get("needed", None)
            if needed is not None:
                msg += f"\nNeed {int(needed)}+."
        except Exception:
            pass

        dlg = self.miracle_dice_dialog
        choice_holder = {"choice": None, "done": False}

        def _on_choice(chosen):
            choice_holder["choice"] = chosen
            choice_holder["done"] = True

        # Show highest values first for clarity
        try:
            values_sorted = sorted(values, reverse=True)
        except Exception:
            values_sorted = values

        dlg.show(
            title=title,
            message=msg,
            dice_values=values_sorted,
            callback=_on_choice,
            skip_label="Skip",
        )
        try:
            self.dialog_manager.open(dlg, modal=True)
        except Exception:
            pass

        clock = pygame.time.Clock()
        while dlg.visible and not choice_holder["done"]:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return None
                try:
                    self.dialog_manager.handle_event(event)
                except Exception:
                    pass
            try:
                self.draw()
            except Exception:
                try:
                    dlg.draw(self.screen)
                    pygame.display.update()
                except Exception:
                    pass
            clock.tick(60)

        return choice_holder["choice"]

    # ---------------- Monarch of the Hunt (Shalaxi) ----------------

    def _queue_monarch_of_the_hunt_prompts(self, game):
        """
        At BR1 start: prompt each human player who has a unit with 'Monarch of the Hunt' to pick a quarry.
        """
        try:
            current = game.get_current_player()
            others = [p for p in list(getattr(game, "players", []) or []) if p is not current]
            order = [current] + others
        except Exception:
            order = list(getattr(game, "players", []) or [])

        queue = []
        for p in order:
            try:
                if p is None:
                    continue
                army = p.get_army()
                if army is None:
                    continue
                for u in list(getattr(army, "units", []) or []):
                    try:
                        if not u.is_alive():
                            continue
                    except Exception:
                        continue
                    # Find Monarch of the Hunt ability by name
                    try:
                        found, _ = u._find_ability_with_patterns(["monarch of the hunt"])
                    except Exception:
                        found = False
                    if not found:
                        continue
                    # Only prompt if not already set
                    if getattr(u, "_monarch_of_the_hunt_quarry_ids", None):
                        continue
                    queue.append((p, u))
            except Exception:
                continue

        if not queue:
            return
        self._pending_quarry_queue.extend(queue)
        # If nothing is currently visible, open immediately.
        self._open_next_quarry_prompt()

    def _open_next_quarry_prompt(self):
        if not self._pending_quarry_queue:
            return
        p, shalaxi_unit = self._pending_quarry_queue.pop(0)

        # Determine enemy army (2-player game assumed)
        enemy_player = None
        try:
            for op in list(getattr(self.game, "players", []) or []):
                if op is not p:
                    enemy_player = op
                    break
        except Exception:
            enemy_player = None
        if enemy_player is None:
            self._open_next_quarry_prompt()
            return

        enemy_army = getattr(enemy_player, "army", None)
        if enemy_army is None:
            self._open_next_quarry_prompt()
            return

        # Build eligible enemy units:
        # - include reserves
        # - exclude embarked units
        # - attached leaders collapsed into bodyguard root
        eligible = []
        seen = set()
        for u in list(getattr(enemy_army, "units", []) or []):
            try:
                # Hide attached leaders as separate entries
                if bool(getattr(u, "is_attached_leader", False)):
                    continue
            except Exception:
                pass
            try:
                root = u.get_attached_unit_root()
            except Exception:
                root = u
            try:
                rid = getattr(root, "_id", None)
                if not rid or rid in seen:
                    continue
                seen.add(rid)
            except Exception:
                continue
            try:
                if not root.is_alive():
                    continue
            except Exception:
                continue
            # Cannot select embarked units as quarry (rules commentary)
            try:
                if bool(getattr(root, "is_embarked", False)):
                    continue
                if getattr(root, "embarked_in", None) is not None:
                    continue
            except Exception:
                pass
            eligible.append(root)

        eligible.sort(key=lambda x: str(getattr(x, "name", "")))
        if not eligible:
            self._open_next_quarry_prompt()
            return

        # Remote players must select quarry via an external controller.
        try:
            if not getattr(p, "has_control", lambda: False)():
                print(f"INFO: Waiting for remote quarry selection: {p.name}")
                self._pending_quarry_queue.insert(0, (p, shalaxi_unit))
                return
        except Exception:
            pass

        try:
            from .dialogs import QuarrySelectionDialog
        except Exception as exc:
            raise RuntimeError("QuarrySelectionDialog unavailable") from exc

        if not hasattr(self, "quarry_selection_dialog") or self.quarry_selection_dialog is None:
            self.quarry_selection_dialog = QuarrySelectionDialog(self.screen.get_width(), self.screen.get_height())

        dlg = self.quarry_selection_dialog

        def _on_confirm(chosen_unit):
            self._set_monarch_quarry(shalaxi_unit, chosen_unit)
            self._open_next_quarry_prompt()

        def _on_cancel():
            # Monarch of the Hunt is mandatory; if cancelled, default to first eligible.
            self._set_monarch_quarry(shalaxi_unit, eligible[0])
            self._open_next_quarry_prompt()

        subtitle = "Embarked units cannot be selected. Units in Reserves may be selected."
        dlg.show(
            title="Monarch of the Hunt",
            subtitle=subtitle,
            choices=eligible,
            on_confirm=_on_confirm,
            on_cancel=_on_cancel,
        )
        try:
            self.dialog_manager.open(dlg, modal=True)
        except Exception:
            pass

    def _set_monarch_quarry(self, shalaxi_unit, enemy_unit_root):
        # Store all members of the attached unit (reflecting persisting effects on split)
        ids = set()
        try:
            members = list(enemy_unit_root.get_attached_unit_members() or [])
        except Exception:
            members = [enemy_unit_root]
        for m in members:
            try:
                mid = getattr(m, "_id", None)
                if mid:
                    ids.add(mid)
            except Exception:
                continue
        setattr(shalaxi_unit, "_monarch_of_the_hunt_quarry_ids", ids)
        try:
            setattr(shalaxi_unit, "_monarch_of_the_hunt_quarry_name", str(getattr(enemy_unit_root, "name", "")))
        except Exception:
            pass

    def _on_unit_destroyed_for_monarch_of_the_hunt(self, unit=None, **_kwargs):
        """
        When a quarry is destroyed, immediately prompt Shalaxi to select a new quarry.

        Persisting effects:
        - If quarry was an attached unit that later splits, the designation persists on the survivor.
        - We track this by storing IDs of all attached members, then pruning to the alive subset.
        """
        if unit is None:
            return

        try:
            destroyed_owner = unit.get_parent_army().player
        except Exception:
            destroyed_owner = None

        # For each potential Shalaxi unit in the *opponent* armies, prune and repick if needed.
        for p in list(getattr(self.game, "players", []) or []):
            try:
                army = p.get_army()
            except Exception:
                army = None
            if army is None:
                continue
            for shalaxi_unit in list(getattr(army, "units", []) or []):
                quarry_ids = getattr(shalaxi_unit, "_monarch_of_the_hunt_quarry_ids", None)
                if not quarry_ids:
                    continue
                # Only if this destroyed unit is part of the quarry group
                try:
                    if getattr(unit, "_id", None) not in quarry_ids:
                        continue
                except Exception:
                    continue

                # Quarry must be an enemy unit, not friendly
                try:
                    if destroyed_owner is not None and destroyed_owner is shalaxi_unit.get_parent_army().player:
                        continue
                except Exception:
                    pass

                # Prune quarry ids to the alive subset (supports attached-unit split persistence)
                alive_ids = set()
                enemy_army = None
                try:
                    enemy_army = destroyed_owner.get_army() if destroyed_owner is not None else None
                except Exception:
                    enemy_army = None
                if enemy_army is not None:
                    by_id = {getattr(u2, "_id", None): u2 for u2 in list(getattr(enemy_army, "units", []) or [])}
                    for qid in list(quarry_ids):
                        u2 = by_id.get(qid)
                        if u2 is None:
                            continue
                        try:
                            if u2.is_alive():
                                alive_ids.add(qid)
                        except Exception:
                            continue
                setattr(shalaxi_unit, "_monarch_of_the_hunt_quarry_ids", alive_ids)

                # If none alive, repick
                if not alive_ids:
                    # Queue prompt for this Shalaxi
                    self._pending_quarry_queue.append((shalaxi_unit.get_parent_army().player, shalaxi_unit))
                    self._open_next_quarry_prompt()

    def _open_next_blessings_prompt(self, battle_round: int) -> None:
        if not self._pending_blessings_queue:
            return
        player = self._pending_blessings_queue.pop(0)
        army = player.get_army()
        mgr = getattr(army, "blessings_of_khorne", None)
        if mgr is None:
            self._open_next_blessings_prompt(battle_round)
            return
        if self.blessings_of_khorne_dialog is None:
            try:
                from .dialogs import BlessingsOfKhorneDialog
                sw, sh = self.screen.get_size()
                self.blessings_of_khorne_dialog = BlessingsOfKhorneDialog(sw, sh)
            except Exception:
                self.blessings_of_khorne_dialog = None
        if self.blessings_of_khorne_dialog is None:
            self._open_next_blessings_prompt(battle_round)
            return

        # Favoured of Khorne rerolls (unique enhancement; bearer must be on battlefield)
        rerolls_allowed = 0
        try:
            if hasattr(mgr, "favoured_of_khorne_rerolls_for_army"):
                rerolls_allowed = int(mgr.favoured_of_khorne_rerolls_for_army(army) or 0)
        except Exception:
            rerolls_allowed = 0

        # Idol of Blessed Blood (+1D6 per such model on battlefield) - start-of-battle-round only.
        idol_bonus = 0
        try:
            for u in list(getattr(army, "units", []) or []):
                if not (getattr(u, "deployed", False) and u.is_alive() and getattr(u, "reserve_status", "deployed") == "deployed"):
                    continue
                found, _ = u._find_ability_with_patterns(["idol of blessed blood", "idol of the blessed blood"])
                if found:
                    idol_bonus += 1
        except Exception:
            idol_bonus = 0

        # Reborn in Blood availability (Angron destroyed at start of battle round)
        reborn_available = False
        try:
            for u in list(getattr(army, "units", []) or []):
                found, _ = u._find_ability_with_patterns(["reborn in blood"])
                if found and (not u.is_alive()):
                    reborn_available = True
                    break
        except Exception:
            reborn_available = False

        from ..rules.blessings_of_khorne import BlessingsTiming
        ctx = mgr.create_roll_context(
            battle_round=int(battle_round),
            timing=BlessingsTiming.START_OF_BATTLE_ROUND,
            extra_dice_from_idols=idol_bonus,
            rerolls_allowed=rerolls_allowed,
            max_activations=2,
            counts_toward_baseline_limit=True,
            already_active_keys=set(),
            reborn_in_blood_available=reborn_available,
        )

        from ..engine.decision_kinds import DECISION_CHOOSE_BLESSINGS
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id

        army_id = get_entity_id(army)
        req = DecisionRequest.create(
            DECISION_CHOOSE_BLESSINGS,
            "Select Blessings of Khorne.",
            player_id=getattr(player, "id", None),
            options=[DecisionOption.create("Confirm", payload={"army_id": army_id})],
            context={"army_id": army_id, "ctx": {}},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_confirm(option_id: str, payload: dict):
            value, apply_result = resolve_decision_value(self.game, req, option_id, result_payload=payload)
            if apply_result is None or not getattr(apply_result, "ok", False):
                payload = dict(payload or {})
                payload["result"] = {}
            else:
                payload = dict(payload or {})
                payload["result"] = value
            try:
                from ..utility.event_bus import append_action
                sel_keys = list(payload.get("selected_blessings") or payload.get("result", {}).get("activated") or [])
                use_reborn = bool(payload.get("use_reborn") or payload.get("result", {}).get("reborn_used"))
                names = []
                if sel_keys:
                    for k in sel_keys:
                        try:
                            d = mgr.definitions.get(str(k).strip().upper())
                        except Exception:
                            d = None
                        names.append(getattr(d, "name", None) or str(k))
                if use_reborn:
                    names.append("Reborn in Blood")
                if not names:
                    names_text = "no blessings activated"
                else:
                    names_text = ", ".join(names)
                dice = list(getattr(payload.get("ctx", None), "dice", []) or [])
                dice_text = ", ".join(str(int(d)) for d in dice) if dice else "?"
                append_action(player, f"Blessings of Khorne: {names_text} (dice: {dice_text})")
            except Exception:
                pass
            try:
                res = payload.get("result") or {}
                if res.get("reborn_used", False):
                    army.schedule_reborn_in_blood(game=self.game)
            except Exception:
                pass
            try:
                if self.rule_detail_panel and self.rule_detail_panel.visible and isinstance(self._rule_panel_state, dict):
                    if self._rule_panel_state.get("player") is player and self._rule_panel_state.get("rule_type") == "army":
                        self._toggle_rule_panel(player, "army", force_refresh=True)
            except Exception:
                pass
            # Continue prompting any other human WE player
            self._open_next_blessings_prompt(battle_round)

        self.blessings_of_khorne_dialog.show(
            player=player,
            game=self.game,
            army=army,
            ctx=ctx,
            on_confirm=_on_confirm,
            decision_request=req,
        )
        try:
            self.dialog_manager.open(self.blessings_of_khorne_dialog, modal=True)
        except Exception:
            pass

    def _open_next_templar_vows_prompt(self) -> None:
        if not self._pending_templar_vows_queue:
            return
        player = self._pending_templar_vows_queue.pop(0)
        army = player.get_army()
        mgr = getattr(army, "templar_vows", None)
        if mgr is None:
            self._open_next_templar_vows_prompt()
            return
        if getattr(mgr, "active_vow_key", None):
            self._open_next_templar_vows_prompt()
            return
        if self.templar_vows_dialog is None:
            try:
                from .dialogs import TemplarVowsDialog
                sw, sh = self.screen.get_size()
                self.templar_vows_dialog = TemplarVowsDialog(sw, sh)
            except Exception:
                self.templar_vows_dialog = None
        if self.templar_vows_dialog is None:
            self._open_next_templar_vows_prompt()
            return

        try:
            from ..rules.templar_vows import VOW_ABHOR, VOW_ACCEPT, VOW_SUFFER, VOW_UPHOLD
            options = [VOW_ABHOR, VOW_ACCEPT, VOW_SUFFER, VOW_UPHOLD]
        except Exception:
            options = []

        from ..engine.decision_kinds import DECISION_CHOOSE_VOW
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id
        from .decision_ui_utils import option_id_for_payload

        army_id = get_entity_id(army)
        req_options = []
        for vow in options:
            key = getattr(vow, "key", None)
            name = getattr(vow, "name", None) or str(vow)
            summary = getattr(vow, "summary", "") or getattr(vow, "effect", "")
            if not key:
                continue
            req_options.append(
                DecisionOption.create(
                    name,
                    payload={"choice_key": str(key), "summary": summary, "army_id": army_id},
                )
            )
        req = DecisionRequest.create(
            DECISION_CHOOSE_VOW,
            "Select Templar Vow.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"army_id": army_id},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_confirm(option_id: str):
            resolve_decision_value(self.game, req, option_id)
            try:
                if self.rule_detail_panel and self.rule_detail_panel.visible and isinstance(self._rule_panel_state, dict):
                    if self._rule_panel_state.get("player") is player and self._rule_panel_state.get("rule_type") == "army":
                        self._toggle_rule_panel(player, "army", force_refresh=True)
            except Exception:
                pass
            self._open_next_templar_vows_prompt()

        def _on_cancel():
            default_key = getattr(options[0], "key", None) if options else None
            default_id = option_id_for_payload(req, "choice_key", default_key)
            if default_id:
                resolve_decision_value(self.game, req, default_id)
            self._open_next_templar_vows_prompt()

        self.templar_vows_dialog.show(on_confirm=_on_confirm, on_cancel=_on_cancel, decision_request=req)
        try:
            self.dialog_manager.open(self.templar_vows_dialog, modal=True)
        except Exception:
            pass

    def _open_next_harbingers_prompt(self, battle_round: int) -> None:
        if not self._pending_harbingers_queue:
            return
        player = self._pending_harbingers_queue.pop(0)
        army = player.get_army()
        mgr = getattr(army, "harbingers_of_dread", None)
        if mgr is None:
            self._open_next_harbingers_prompt(battle_round)
            return
        if getattr(mgr, "last_selection_round", None) == battle_round:
            self._open_next_harbingers_prompt(battle_round)
            return
        if not getattr(mgr, "get_available_dread_abilities", lambda: [])():
            try:
                mgr.last_selection_round = int(battle_round)
            except Exception:
                pass
            self._open_next_harbingers_prompt(battle_round)
            return

        if self.harbingers_of_dread_dialog is None:
            try:
                from .dialogs import HarbingersOfDreadDialog
                sw, sh = self.screen.get_size()
                self.harbingers_of_dread_dialog = HarbingersOfDreadDialog(sw, sh)
            except Exception:
                self.harbingers_of_dread_dialog = None
        if self.harbingers_of_dread_dialog is None:
            try:
                mgr.roll_dread_abilities(battle_round=battle_round)
            except Exception:
                pass
            self._open_next_harbingers_prompt(battle_round)
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_HARBINGER
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id
        from .decision_ui_utils import option_id_for_payload, first_option_id

        try:
            options = list(mgr.get_available_dread_abilities())
        except Exception:
            options = []

        army_id = get_entity_id(army)
        req_options = [
            DecisionOption.create(
                "Roll 2D6 (randomly select two)",
                payload={
                    "choice_key": "ROLL",
                    "random": True,
                    "summary": "Apply both results; duplicates have no additional effect.",
                    "army_id": army_id,
                },
            )
        ]
        for opt in options:
            key = getattr(opt, "key", None)
            if not key:
                continue
            name = getattr(opt, "name", None) or str(opt)
            summary = getattr(opt, "summary", "") or getattr(opt, "effect", "")
            req_options.append(
                DecisionOption.create(
                    name,
                    payload={"choice_key": str(key), "summary": summary, "army_id": army_id},
                )
            )

        req = DecisionRequest.create(
            DECISION_CHOOSE_HARBINGER,
            "Select Harbingers of Dread.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"army_id": army_id, "battle_round": battle_round},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_confirm(option_id: str):
            resolve_decision_value(self.game, req, option_id)
            try:
                if self.rule_detail_panel and self.rule_detail_panel.visible and isinstance(self._rule_panel_state, dict):
                    if self._rule_panel_state.get("player") is player and self._rule_panel_state.get("rule_type") == "army":
                        self._toggle_rule_panel(player, "army", force_refresh=True)
            except Exception:
                pass
            self._open_next_harbingers_prompt(battle_round)

        def _on_cancel():
            default_id = option_id_for_payload(req, "choice_key", "ROLL") or first_option_id(req)
            if default_id:
                resolve_decision_value(self.game, req, default_id)
            self._open_next_harbingers_prompt(battle_round)

        self.harbingers_of_dread_dialog.show(on_confirm=_on_confirm, on_cancel=_on_cancel, decision_request=req)
        try:
            self.dialog_manager.open(self.harbingers_of_dread_dialog, modal=True)
        except Exception:
            pass

    def _open_next_doctrina_prompt(self, battle_round: int) -> None:
        if not self._pending_doctrina_queue:
            return
        player = self._pending_doctrina_queue.pop(0)
        army = player.get_army()
        mgr = getattr(army, "doctrina_imperatives", None)
        if mgr is None or not getattr(mgr, "_army_has_doctrina", lambda: False)():
            self._open_next_doctrina_prompt(battle_round)
            return
        if getattr(mgr, "active_round", None) == battle_round and getattr(mgr, "active_imperative_key", None):
            self._open_next_doctrina_prompt(battle_round)
            return

        if self.doctrina_imperatives_dialog is None:
            try:
                from .dialogs import DoctrinaImperativesDialog
                sw, sh = self.screen.get_size()
                self.doctrina_imperatives_dialog = DoctrinaImperativesDialog(sw, sh)
            except Exception:
                self.doctrina_imperatives_dialog = None
        if self.doctrina_imperatives_dialog is None:
            try:
                from ..rules.doctrina_imperatives import PROTECTOR_IMPERATIVE, CONQUEROR_IMPERATIVE
                from ..utility.dice import get_roll
                roll = int(get_roll("D6") or 0)
                choice = PROTECTOR_IMPERATIVE if roll <= 3 else CONQUEROR_IMPERATIVE
                mgr.select_imperative(choice, battle_round=battle_round)
            except Exception:
                pass
            self._open_next_doctrina_prompt(battle_round)
            return

        try:
            from ..rules.doctrina_imperatives import PROTECTOR_IMPERATIVE, CONQUEROR_IMPERATIVE
            options = [PROTECTOR_IMPERATIVE, CONQUEROR_IMPERATIVE]
        except Exception:
            options = []

        from ..engine.decision_kinds import DECISION_CHOOSE_DOCTRINA
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id

        army_id = get_entity_id(army)
        req_options = []
        for opt in options:
            key = getattr(opt, "key", None)
            if not key:
                continue
            name = getattr(opt, "name", None) or str(opt)
            summary = getattr(opt, "summary", "") or getattr(opt, "effect", "")
            req_options.append(
                DecisionOption.create(
                    name,
                    payload={"choice_key": str(key), "summary": summary, "army_id": army_id},
                )
            )
        if not req_options:
            self._open_next_doctrina_prompt(battle_round)
            return

        req = DecisionRequest.create(
            DECISION_CHOOSE_DOCTRINA,
            "Select Doctrina Imperative.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"army_id": army_id, "battle_round": battle_round},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_confirm(option_id: str):
            resolve_decision_value(self.game, req, option_id)
            try:
                choice_label = ""
                for opt in list(getattr(req, "options", []) or []):
                    if opt.option_id == option_id:
                        choice_label = str(getattr(opt, "label", "") or "")
                        break
            except Exception:
                choice_label = ""
            try:
                from ..utility.event_bus import append_action
                if choice_label:
                    append_action(player, f"Doctrina Imperatives: {choice_label} (Battle Round {battle_round})")
            except Exception:
                pass
            try:
                if self.rule_detail_panel and self.rule_detail_panel.visible and isinstance(self._rule_panel_state, dict):
                    if self._rule_panel_state.get("player") is player and self._rule_panel_state.get("rule_type") == "army":
                        self._toggle_rule_panel(player, "army", force_refresh=True)
            except Exception:
                pass
            self._open_next_doctrina_prompt(battle_round)

        self.doctrina_imperatives_dialog.show(on_confirm=_on_confirm, decision_request=req)
        try:
            self.dialog_manager.open(self.doctrina_imperatives_dialog, modal=True)
        except Exception:
            pass

    def _on_combat_doctrines_prompt(self, player=None, game=None, **_kwargs):
        if player is None:
            return
        try:
            is_human = bool(getattr(player, "has_control", lambda: False)())
        except Exception:
            is_human = False
        if not is_human:
            return
        game = game or self.game
        if game is None:
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            return
        mgr = getattr(army, "combat_doctrines", None)
        if mgr is None or not getattr(mgr, "can_select_now", lambda **_k: False)(game=game):
            return
        try:
            battle_round = int(getattr(game, "turn", 0) or 0)
        except Exception:
            battle_round = 0
        self._pending_combat_doctrines_queue = [(player, battle_round)]
        self._open_next_combat_doctrines_prompt(battle_round)

    def _open_next_combat_doctrines_prompt(self, battle_round: int) -> None:
        if not self._pending_combat_doctrines_queue:
            return
        try:
            player, br = self._pending_combat_doctrines_queue.pop(0)
        except Exception:
            return
        army = player.get_army()
        mgr = getattr(army, "combat_doctrines", None) if army is not None else None
        if mgr is None or not getattr(mgr, "can_select_now", lambda **_k: False)(game=self.game):
            self._open_next_combat_doctrines_prompt(br)
            return
        try:
            options = list(getattr(mgr, "get_available_doctrines", lambda: [])() or [])
        except Exception:
            options = []
        if not options:
            self._open_next_combat_doctrines_prompt(br)
            return

        if self.combat_doctrines_dialog is None:
            try:
                from .dialogs import CombatDoctrinesDialog
                sw, sh = self.screen.get_size()
                self.combat_doctrines_dialog = CombatDoctrinesDialog(sw, sh)
            except Exception:
                self.combat_doctrines_dialog = None
        if self.combat_doctrines_dialog is None:
            self._open_next_combat_doctrines_prompt(br)
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_COMBAT_DOCTRINE
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id

        army_id = get_entity_id(army)
        req_options = []
        req_options.append(
            DecisionOption.create(
                "None",
                payload={"skip": True, "summary": "Do not select a Combat Doctrine this Command phase.", "army_id": army_id},
            )
        )
        for opt in options:
            key = getattr(opt, "key", None)
            if not key:
                continue
            name = getattr(opt, "name", None) or str(opt)
            summary = getattr(opt, "summary", "") or getattr(opt, "effect", "")
            req_options.append(
                DecisionOption.create(
                    name,
                    payload={"choice_key": str(key), "summary": summary, "army_id": army_id},
                )
            )
        if not req_options:
            self._open_next_combat_doctrines_prompt(br)
            return

        req = DecisionRequest.create(
            DECISION_CHOOSE_COMBAT_DOCTRINE,
            "Select Combat Doctrine.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"army_id": army_id, "battle_round": br},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_confirm(option_id: str):
            resolve_decision_value(self.game, req, option_id)
            try:
                choice_label = ""
                for opt in list(getattr(req, "options", []) or []):
                    if opt.option_id == option_id:
                        choice_label = str(getattr(opt, "label", "") or "")
                        break
            except Exception:
                choice_label = ""
            try:
                from ..utility.event_bus import append_action
                if choice_label:
                    append_action(player, f"Combat Doctrines: {choice_label} (Battle Round {br})")
            except Exception:
                pass
            self._open_next_combat_doctrines_prompt(br)

        self.combat_doctrines_dialog.show(on_confirm=_on_confirm, decision_request=req)
        try:
            self.dialog_manager.open(self.combat_doctrines_dialog, modal=True)
        except Exception:
            pass

    def _on_combat_drugs_prompt(self, player=None, game=None, **_kwargs):
        if player is None:
            return
        try:
            is_human = bool(getattr(player, "has_control", lambda: False)())
        except Exception:
            is_human = False
        if not is_human:
            return
        game = game or self.game
        if game is None:
            return
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            return
        mgr = getattr(army, "drukhari_detachments", None)
        if mgr is None or not getattr(mgr, "can_select_combat_drugs", lambda **_k: False)(game=game):
            return
        try:
            battle_round = int(getattr(game, "turn", 0) or 0)
        except Exception:
            battle_round = 0
        self._pending_combat_drugs_queue = [(player, battle_round)]
        self._open_next_combat_drugs_prompt(battle_round)

    def _open_next_combat_drugs_prompt(self, battle_round: int) -> None:
        if not self._pending_combat_drugs_queue:
            return
        try:
            player, br = self._pending_combat_drugs_queue.pop(0)
        except Exception:
            return
        army = player.get_army()
        mgr = getattr(army, "drukhari_detachments", None) if army is not None else None
        if mgr is None or not getattr(mgr, "can_select_combat_drugs", lambda **_k: False)(game=self.game):
            self._open_next_combat_drugs_prompt(br)
            return
        try:
            options = list(getattr(mgr, "get_available_combat_drugs", lambda: [])() or [])
        except Exception:
            options = []

        if self.combat_drugs_dialog is None:
            try:
                from .dialogs import CombatDrugsDialog
                sw, sh = self.screen.get_size()
                self.combat_drugs_dialog = CombatDrugsDialog(sw, sh)
            except Exception:
                self.combat_drugs_dialog = None
        if self.combat_drugs_dialog is None:
            self._open_next_combat_drugs_prompt(br)
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_COMBAT_DRUGS
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id
        from .decision_ui_utils import option_id_for_payload, first_option_id

        army_id = get_entity_id(army)
        req_options = [
            DecisionOption.create(
                "Roll 2D6 (randomly select two)",
                payload={
                    "choice_key": "ROLL",
                    "random": True,
                    "summary": "Apply both results; duplicates have no additional effect.",
                    "army_id": army_id,
                },
            )
        ]
        for opt in options:
            key = getattr(opt, "key", None)
            if not key:
                continue
            name = getattr(opt, "name", None) or str(opt)
            summary = getattr(opt, "summary", "") or getattr(opt, "effect", "")
            req_options.append(
                DecisionOption.create(
                    name,
                    payload={"choice_key": str(key), "summary": summary, "army_id": army_id},
                )
            )
        if not req_options:
            self._open_next_combat_drugs_prompt(br)
            return

        req = DecisionRequest.create(
            DECISION_CHOOSE_COMBAT_DRUGS,
            "Select Combat Drugs.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"army_id": army_id, "battle_round": br},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_confirm(option_id: str):
            resolve_decision_value(self.game, req, option_id)
            try:
                choice_label = ""
                for opt in list(getattr(req, "options", []) or []):
                    if opt.option_id == option_id:
                        choice_label = str(getattr(opt, "label", "") or "")
                        break
            except Exception:
                choice_label = ""
            try:
                from ..utility.event_bus import append_action
                if choice_label:
                    append_action(player, f"Combat Drugs: {choice_label} (Battle Round {br})")
            except Exception:
                pass
            try:
                if self.rule_detail_panel and self.rule_detail_panel.visible and isinstance(self._rule_panel_state, dict):
                    if self._rule_panel_state.get("player") is player and self._rule_panel_state.get("rule_type") == "army":
                        self._toggle_rule_panel(player, "army", force_refresh=True)
            except Exception:
                pass
            self._open_next_combat_drugs_prompt(br)

        def _on_cancel():
            default_id = option_id_for_payload(req, "choice_key", "ROLL") or first_option_id(req)
            if default_id:
                resolve_decision_value(self.game, req, default_id)
            self._open_next_combat_drugs_prompt(br)

        self.combat_drugs_dialog.show(on_confirm=_on_confirm, on_cancel=_on_cancel, decision_request=req)
        try:
            self.dialog_manager.open(self.combat_drugs_dialog, modal=True)
        except Exception:
            pass

    def _open_next_shadow_form_prompt(self) -> None:
        if not self._pending_shadow_form_queue:
            return
        try:
            player, unit, br = self._pending_shadow_form_queue.pop(0)
        except Exception:
            return
        army = player.get_army()
        mgr = getattr(army, "shadow_form", None)
        if mgr is None or unit is None:
            self._open_next_shadow_form_prompt()
            return
        try:
            from ..rules.shadow_form import SHADOW_FORM_OPTIONS, set_active_shadow_form, get_active_shadow_form_key
        except Exception:
            self._open_next_shadow_form_prompt()
            return

        try:
            if get_active_shadow_form_key(unit, battle_round=br):
                self._open_next_shadow_form_prompt()
                return
        except Exception:
            pass

        if self.shadow_form_dialog is None:
            try:
                from .dialogs import ShadowFormDialog
                sw, sh = self.screen.get_size()
                self.shadow_form_dialog = ShadowFormDialog(sw, sh)
            except Exception:
                self.shadow_form_dialog = None
        if self.shadow_form_dialog is None:
            self._open_next_shadow_form_prompt()
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_SHADOW_FORM
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id
        from .decision_ui_utils import first_option_id

        options = list(SHADOW_FORM_OPTIONS)
        unit_id = get_entity_id(unit)
        req_options = []
        for opt in options:
            key = getattr(opt, "key", None)
            if not key:
                continue
            name = getattr(opt, "name", None) or str(opt)
            summary = getattr(opt, "summary", "") or getattr(opt, "effect", "")
            req_options.append(
                DecisionOption.create(
                    name,
                    payload={"choice_key": str(key), "summary": summary, "unit_id": unit_id},
                )
            )
        if not req_options:
            self._open_next_shadow_form_prompt()
            return

        req = DecisionRequest.create(
            DECISION_CHOOSE_SHADOW_FORM,
            "Select Shadow Form.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"unit_id": unit_id, "battle_round": br},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_confirm(option_id: str):
            resolve_decision_value(self.game, req, option_id)
            self._open_next_shadow_form_prompt()

        def _on_cancel():
            default_id = first_option_id(req)
            if default_id:
                resolve_decision_value(self.game, req, default_id)
            self._open_next_shadow_form_prompt()

        self.shadow_form_dialog.show(
            unit_name=getattr(unit, "name", ""),
            battle_round=br,
            on_confirm=_on_confirm,
            on_cancel=_on_cancel,
            decision_request=req,
        )
        try:
            self.dialog_manager.open(self.shadow_form_dialog, modal=True)
        except Exception:
            pass

    def _open_next_wrathful_presence_prompt(self) -> None:
        if not self._pending_wrathful_presence_queue:
            return
        try:
            player, unit, br = self._pending_wrathful_presence_queue.pop(0)
        except Exception:
            return
        army = player.get_army()
        mgr = getattr(army, "wrathful_presence", None)
        if mgr is None or unit is None:
            self._open_next_wrathful_presence_prompt()
            return
        try:
            from ..rules.wrathful_presence import (
                WRATHFUL_PRESENCE_OPTIONS,
                set_active_wrathful_presence,
                get_active_wrathful_presence_key,
            )
        except Exception:
            self._open_next_wrathful_presence_prompt()
            return

        try:
            if get_active_wrathful_presence_key(unit, battle_round=br):
                self._open_next_wrathful_presence_prompt()
                return
        except Exception:
            pass

        if not hasattr(self, "wrathful_presence_dialog") or self.wrathful_presence_dialog is None:
            try:
                from .dialogs import WrathfulPresenceDialog
                sw, sh = self.screen.get_size()
                self.wrathful_presence_dialog = WrathfulPresenceDialog(sw, sh)
            except Exception:
                self.wrathful_presence_dialog = None
        if self.wrathful_presence_dialog is None:
            self._open_next_wrathful_presence_prompt()
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_WRATHFUL_PRESENCE
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id
        from .decision_ui_utils import first_option_id

        options = list(WRATHFUL_PRESENCE_OPTIONS)
        unit_id = get_entity_id(unit)
        req_options = []
        for opt in options:
            key = getattr(opt, "key", None)
            if not key:
                continue
            name = getattr(opt, "name", None) or str(opt)
            summary = getattr(opt, "summary", "") or getattr(opt, "effect", "")
            req_options.append(
                DecisionOption.create(
                    name,
                    payload={"choice_key": str(key), "summary": summary, "unit_id": unit_id},
                )
            )
        if not req_options:
            self._open_next_wrathful_presence_prompt()
            return

        req = DecisionRequest.create(
            DECISION_CHOOSE_WRATHFUL_PRESENCE,
            "Select Wrathful Presence.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"unit_id": unit_id, "battle_round": br},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_confirm(option_id: str):
            resolve_decision_value(self.game, req, option_id)
            try:
                choice_label = ""
                for opt in list(getattr(req, "options", []) or []):
                    if opt.option_id == option_id:
                        choice_label = str(getattr(opt, "label", "") or "")
                        break
            except Exception:
                choice_label = ""
            try:
                from ..utility.event_bus import append_action
                if choice_label:
                    append_action(player, f"Wrathful Presence: {choice_label} (Battle Round {br})")
            except Exception:
                pass
            self._open_next_wrathful_presence_prompt()

        def _on_cancel():
            default_id = first_option_id(req)
            if default_id:
                resolve_decision_value(self.game, req, default_id)
            self._open_next_wrathful_presence_prompt()

        self.wrathful_presence_dialog.show(
            unit_name=getattr(unit, "name", ""),
            battle_round=br,
            on_confirm=_on_confirm,
            on_cancel=_on_cancel,
            decision_request=req,
        )
        try:
            self.dialog_manager.open(self.wrathful_presence_dialog, modal=True)
        except Exception:
            pass

    def _on_daemonic_allegiance_prompt(self, player=None, units=None, game=None, **_kwargs):
        if player is None:
            return
        for unit in list(units or []):
            self._pending_daemonic_allegiance_queue.append((player, unit))
        self._open_next_daemonic_allegiance_prompt(game or self.game)

    def _open_next_daemonic_allegiance_prompt(self, game) -> None:
        queue = list(getattr(self, "_pending_daemonic_allegiance_queue", []) or [])
        if not queue:
            return
        try:
            player, unit = queue.pop(0)
        except Exception:
            return
        self._pending_daemonic_allegiance_queue = queue
        if unit is None:
            self._open_next_daemonic_allegiance_prompt(game)
            return
        try:
            if unit.get_daemonic_allegiance_selection():
                self._open_next_daemonic_allegiance_prompt(game)
                return
        except Exception:
            pass
        try:
            options = list(unit.get_daemonic_allegiance_options() or [])
        except Exception:
            options = []
        if not options:
            self._open_next_daemonic_allegiance_prompt(game)
            return

        if not hasattr(self, "daemonic_allegiance_dialog") or self.daemonic_allegiance_dialog is None:
            try:
                from .dialogs import DaemonicAllegianceDialog
                sw, sh = self.screen.get_size()
                self.daemonic_allegiance_dialog = DaemonicAllegianceDialog(sw, sh)
            except Exception:
                self.daemonic_allegiance_dialog = None
        if self.daemonic_allegiance_dialog is None:
            self._open_next_daemonic_allegiance_prompt(game)
            return

        from ..engine.decision_kinds import DECISION_CHOOSE_DAEMONIC_ALLEGIANCE
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id
        from .decision_ui_utils import first_option_id

        unit_id = get_entity_id(unit)
        req_options = []
        for opt in options:
            if isinstance(opt, (list, tuple)):
                keyword = str(opt[0]) if opt else ""
                wargear = str(opt[1]) if len(opt) > 1 else ""
            else:
                keyword = str(opt)
                wargear = ""
            if not keyword:
                continue
            req_options.append(
                DecisionOption.create(
                    keyword,
                    payload={"keyword": keyword, "wargear_name": wargear, "unit_id": unit_id},
                )
            )
        if not req_options:
            self._open_next_daemonic_allegiance_prompt(game)
            return

        req = DecisionRequest.create(
            DECISION_CHOOSE_DAEMONIC_ALLEGIANCE,
            f"Select Daemonic Allegiance for {getattr(unit, 'name', 'Unit')}.",
            player_id=getattr(player, "id", None),
            options=req_options,
            context={"unit_id": unit_id},
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_confirm(option_id: str):
            resolve_decision_value(self.game, req, option_id)
            try:
                from ..utility.event_bus import append_action
                append_action(player, f"Daemonic Allegiance: {getattr(unit, 'daemonic_allegiance', '')} ({unit.name})")
            except Exception:
                pass
            self._open_next_daemonic_allegiance_prompt(game)

        def _on_cancel():
            default_id = first_option_id(req)
            if default_id:
                resolve_decision_value(self.game, req, default_id)
            self._open_next_daemonic_allegiance_prompt(game)

        self.daemonic_allegiance_dialog.show(
            unit_name=getattr(unit, "name", ""),
            on_confirm=_on_confirm,
            on_cancel=_on_cancel,
            decision_request=req,
        )
        try:
            self.dialog_manager.open(self.daemonic_allegiance_dialog, modal=True)
        except Exception:
            pass

    def _precision_allocation_provider(self, attacker_model, target_unit, character_models, weapon_profile):
        """
        Blocking modal prompt for PRECISION allocation.
        Returns: selected CHARACTER model to allocate to, or None to allocate normally to bodyguard.
        """
        try:
            from .dialogs import PrecisionAllocationDialog
        except Exception:
            return None
        from ..engine.decision_kinds import DECISION_SELECT_PRECISION_TARGET
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id

        # Create (or reuse) dialog instance
        if not hasattr(self, "precision_allocation_dialog") or self.precision_allocation_dialog is None:
            self.precision_allocation_dialog = PrecisionAllocationDialog(self.screen.get_width(), self.screen.get_height())

        dlg = self.precision_allocation_dialog
        choice_holder = {"choice": None, "done": False}

        def _on_choice(option_id: str):
            value, apply_result = resolve_decision_value(self.game, req, option_id)
            if apply_result is None or not getattr(apply_result, "ok", False):
                value = None
            choice_holder["choice"] = value
            choice_holder["done"] = True

        # Weapon label
        try:
            wname = getattr(getattr(weapon_profile, "parent_wargear", None), "name", None) or getattr(weapon_profile, "name", "Weapon")
        except Exception:
            wname = "Weapon"

        attacker_id = get_entity_id(attacker_model)
        target_id = get_entity_id(target_unit)
        options = [
            DecisionOption.create("Bodyguard (normal allocation)", payload={"model_id": None, "action": "bodyguard"}),
        ]
        for model in list(character_models or []):
            options.append(DecisionOption.create(getattr(model, "name", "CHARACTER"), payload={"model_id": get_entity_id(model)}))
        req = DecisionRequest.create(
            DECISION_SELECT_PRECISION_TARGET,
            "Select PRECISION allocation target.",
            player_id=getattr(getattr(attacker_model.parent_unit.get_parent_army(), "player", None), "id", None) if attacker_model else None,
            options=options,
            context={"attacker_model_id": attacker_id, "target_unit_id": target_id},
        )
        if self.game is not None:
            self.game.request_decision(req)

        dlg.show(attacker_model, target_unit, wname, list(character_models or []), on_choice=_on_choice, decision_request=req)
        try:
            self.dialog_manager.open(dlg, modal=True)
        except Exception:
            pass

        # Block until choice is made (or ESC closes dialog -> defaults to bodyguard)
        clock = pygame.time.Clock()
        while dlg.visible and not choice_holder["done"]:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return None
                # Route only through dialog manager (modal)
                try:
                    self.dialog_manager.handle_event(event)
                except Exception:
                    pass
            try:
                self.draw()
            except Exception:
                try:
                    dlg.draw(self.screen)
                    pygame.display.update()
                except Exception:
                    pass
            clock.tick(60)

        if not choice_holder["done"]:
            default_option = options[0].option_id if options else ""
            value, apply_result = resolve_decision_value(self.game, req, default_option)
            if apply_result is None or not getattr(apply_result, "ok", False):
                return None
            return value

        return choice_holder["choice"]

    def _prompt_damage_allocation_decision(self, *, unit, eligible_models, title, subtitle, instruction, ctx, show_wargear: bool = False):
        try:
            from .dialogs import DamageAllocationDialog
        except Exception:
            return None
        from ..engine.decision_kinds import DECISION_ALLOCATE_DAMAGE
        from ..engine.decisions import DecisionOption, DecisionRequest
        from ..utility.decision_utils import resolve_decision_value
        from ..utility.entity_ids import get_entity_id

        if not hasattr(self, "damage_allocation_dialog") or self.damage_allocation_dialog is None:
            self.damage_allocation_dialog = DamageAllocationDialog(self.screen.get_width(), self.screen.get_height())

        dlg = self.damage_allocation_dialog
        choice_holder = {"choice": None, "done": False}

        options = [DecisionOption.create("Auto allocation", payload={"model_id": None})]
        for model in list(eligible_models or []):
            label = getattr(model, "name", "Model")
            options.append(DecisionOption.create(label, payload={"model_id": get_entity_id(model)}))

        context = dict(ctx or {})
        context["unit_id"] = get_entity_id(unit)
        req = DecisionRequest.create(
            DECISION_ALLOCATE_DAMAGE,
            title or "Allocate Damage",
            player_id=getattr(getattr(unit.get_parent_army(), "player", None), "id", None) if unit is not None else None,
            options=options,
            context=context,
        )
        if self.game is not None:
            self.game.request_decision(req)

        def _on_choice(option_id: str):
            value, apply_result = resolve_decision_value(self.game, req, option_id)
            if apply_result is None or not getattr(apply_result, "ok", False):
                value = None
            choice_holder["choice"] = value
            choice_holder["done"] = True

        dlg.show(
            unit,
            list(eligible_models or []),
            title=title or "Allocate Damage",
            subtitle=subtitle or "",
            instruction=instruction or "",
            on_choice=_on_choice,
            show_wargear=bool(show_wargear),
            decision_request=req,
        )
        try:
            self.dialog_manager.open(dlg, modal=True)
        except Exception:
            pass

        clock = pygame.time.Clock()
        while dlg.visible and not choice_holder["done"]:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return None
                try:
                    self.dialog_manager.handle_event(event)
                except Exception:
                    pass
            try:
                self.draw()
            except Exception:
                try:
                    dlg.draw(self.screen)
                    pygame.display.update()
                except Exception:
                    pass
            clock.tick(60)

        if not choice_holder["done"] and options:
            default_option = options[0].option_id
            value, apply_result = resolve_decision_value(self.game, req, default_option)
            if apply_result is None or not getattr(apply_result, "ok", False):
                return None
            return value

        return choice_holder["choice"]

    def _damage_allocation_provider(self, target_unit, eligible_models, ctx):
        """
        Blocking modal prompt for defender damage allocation.
        Returns: selected model, or None to fall back to deterministic engine choice.
        """
        reason = ""
        try:
            reason = (ctx or {}).get("reason", "") or "Allocate Damage"
        except Exception:
            reason = "Allocate Damage"
        weapon = ""
        attacker = ""
        try:
            weapon = (ctx or {}).get("weapon_name", "") or ""
            attacker = (ctx or {}).get("attacker_name", "") or ""
        except Exception:
            pass
        subtitle = getattr(target_unit, "name", "Unit")
        if weapon and attacker:
            subtitle = f"{subtitle} (from {attacker} - {weapon})"
        instruction = "If a model is already wounded, you must continue allocating to a wounded eligible model."

        return self._prompt_damage_allocation_decision(
            unit=target_unit,
            eligible_models=list(eligible_models or []),
            title=reason,
            subtitle=subtitle,
            instruction=instruction,
            ctx=ctx,
        )

    def _hazardous_allocation_provider(self, attacker_unit_root, eligible_models, ctx):
        """
        Blocking modal prompt for selecting the model that suffers a failed HAZARDOUS test.
        Returns: selected model, or None to fall back to deterministic engine choice.
        """
        subtitle = getattr(attacker_unit_root, "name", "Unit")
        instruction = "HAZARDOUS priority: wounded eligible model; otherwise non-Character; otherwise Character."
        title = "HAZARDOUS - Select Model"
        try:
            title = (ctx or {}).get("reason", "") or title
        except Exception:
            pass
        return self._prompt_damage_allocation_decision(
            unit=attacker_unit_root,
            eligible_models=list(eligible_models or []),
            title=title,
            subtitle=subtitle,
            instruction=instruction,
            ctx=ctx,
        )

    def _reanimation_allocation_provider(self, target_unit_root, eligible_models, ctx):
        """
        Blocking modal prompt for Reanimation Protocols model selection.
        Returns: selected model, or None to fall back to deterministic engine choice.
        """
        reason = ""
        instruction = ""
        try:
            reason = (ctx or {}).get("reason", "") or "Reanimation Protocols"
            instruction = (ctx or {}).get("instruction", "") or "Select a model for Reanimation Protocols."
        except Exception:
            reason = "Reanimation Protocols"
            instruction = "Select a model for Reanimation Protocols."

        subtitle = getattr(target_unit_root, "name", "Unit")
        return self._prompt_damage_allocation_decision(
            unit=target_unit_root,
            eligible_models=list(eligible_models or []),
            title=reason,
            subtitle=subtitle,
            instruction=instruction,
            ctx=ctx,
            show_wargear=True,
        )

    def resize_layout(self, screen_width: int, screen_height: int) -> None:
        """Handle window resize: recompute pane sizes and positions based on new screen size."""
        # Recompute scaled dimensions
        scaled_roster_width = ROSTER_PANE_WIDTH
        scaled_stratagem_width = STRATAGEM_PANE_WIDTH
        scaled_info_height = INFO_PANE_HEIGHT
        scaled_battlefield_width = max(100, screen_width - 2 * (scaled_roster_width + scaled_stratagem_width))
        scaled_battlefield_height = max(100, screen_height - scaled_info_height)

        # Update stored dimensions
        self.scaled_roster_width = scaled_roster_width
        self.scaled_stratagem_width = scaled_stratagem_width
        self.scaled_battlefield_width = scaled_battlefield_width
        self.scaled_battlefield_height = scaled_battlefield_height
        self.scaled_info_height = scaled_info_height
        self.battlefield_left = scaled_stratagem_width + scaled_roster_width
        self.battlefield_right = self.battlefield_left + scaled_battlefield_width

        # Resize roster panes
        # Roster panes should not overlap the bottom logs pane; limit to battlefield height
        roster_pane_height = scaled_battlefield_height
        self.left_stratagem_pane.update_rect(0, 0, scaled_stratagem_width, roster_pane_height)
        self.right_stratagem_pane.update_rect(self.battlefield_right + scaled_roster_width, 0,
                                              scaled_stratagem_width, roster_pane_height)
        self.left_roster_pane.rect.update(scaled_stratagem_width, 0, scaled_roster_width, roster_pane_height)
        self.right_roster_pane.rect.update(self.battlefield_right, 0, scaled_roster_width, roster_pane_height)
        # After rect updates, recreate buttons and clamp scroll to fix misalignment
        if hasattr(self.left_roster_pane, 'create_buttons'):
            self.left_roster_pane.create_buttons()
        if hasattr(self.right_roster_pane, 'create_buttons'):
            self.right_roster_pane.create_buttons()

        # Resize info pane
        self.info_pane.rect.update(self.battlefield_left, scaled_battlefield_height,
                                   scaled_battlefield_width, scaled_info_height)

        # No UI scale factor; rendering uses only zoom and pan

        # Optionally clamp offsets to keep view in bounds
        self.offset_x = max(min(self.offset_x, scaled_battlefield_width), -scaled_battlefield_width)
        self.offset_y = max(min(self.offset_y, scaled_battlefield_height), -scaled_battlefield_height)
    
    def refresh_roster_panes(self):
        """Refresh roster panes when armies are loaded during setup phases."""
        if self.player1 and self.player2:
            self._rule_support_cache = {}
            player1_units = self.player1.get_army().units if self.player1.get_army() else []
            player2_units = self.player2.get_army().units if self.player2.get_army() else []

            # Collapse attached Leaders into their bodyguard unit in roster panes:
            # hide leader units that have `attached_to` set.
            def _visible_roster(units):
                visible = []
                for u in list(units or []):
                    try:
                        if bool(getattr(u, "is_leader", False)) and getattr(u, "attached_to", None) is not None:
                            continue
                    except Exception:
                        pass
                    visible.append(u)
                return visible

            player1_units = _visible_roster(player1_units)
            player2_units = _visible_roster(player2_units)
            
            print(f"Refreshing roster panes: Player1 has {len(player1_units)} units, Player2 has {len(player2_units)} units")
            
            # Update roster units
            self.left_roster_pane.roster = player1_units
            self.right_roster_pane.roster = player2_units
            
            # Update player references
            self.left_roster_pane.player = self.player1
            self.right_roster_pane.player = self.player2
            self.left_stratagem_pane.player = self.player1
            self.right_stratagem_pane.player = self.player2
            self.left_stratagem_pane.player_name = f"Player 1 ({self.player1.name})"
            self.right_stratagem_pane.player_name = f"Player 2 ({self.player2.name})"
            
            # Update all_units for color correlation
            all_units = player1_units + player2_units
            self.left_roster_pane.all_units = all_units
            self.right_roster_pane.all_units = all_units
            
            # Reset scroll positions
            self.left_roster_pane.scroll_offset = 0
            self.right_roster_pane.scroll_offset = 0
            
            # Recreate buttons with new roster data
            self.left_roster_pane.create_buttons()
            self.right_roster_pane.create_buttons()
            
            print("Roster panes refreshed successfully")

    def update_roster_pane_titles(self):
        """Update roster pane titles to show Attacker/Defender after roles are determined."""
        if self.game and hasattr(self.game, 'attacker_index') and self.game.attacker_index is not None:
            # Update player names to include role
            if self.game.attacker_index == 0:  # Player 1 is attacker
                self.left_roster_pane.player_name = f"{self.player1.name} (Attacker)"
                self.right_roster_pane.player_name = f"{self.player2.name} (Defender)"
                self.left_stratagem_pane.player_name = f"Player 1 ({self.player1.name})"
                self.right_stratagem_pane.player_name = f"Player 2 ({self.player2.name})"
            else:  # Player 2 is attacker
                self.left_roster_pane.player_name = f"{self.player1.name} (Defender)"
                self.right_roster_pane.player_name = f"{self.player2.name} (Attacker)"
                self.left_stratagem_pane.player_name = f"Player 1 ({self.player1.name})"
                self.right_stratagem_pane.player_name = f"Player 2 ({self.player2.name})"

    def handle_pygame_event(self, event):
        """Handle pygame events using phase-based routing."""
        # Debug: Log all events received by GameView
        # TODO: Uncomment for event debugging
        # if event.type in [pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION]:
        #     event_name = {
        #         pygame.KEYDOWN: "KEYDOWN",
        #         pygame.MOUSEBUTTONDOWN: "MOUSEBUTTONDOWN",
        #         pygame.MOUSEBUTTONUP: "MOUSEBUTTONUP",
        #         pygame.MOUSEMOTION: "MOUSEMOTION"
        #     }.get(event.type, f"TYPE_{event.type}")
        #
        #     if event.type == pygame.KEYDOWN:
        #         print(f"DEBUG: GameView.handle_pygame_event - {event_name}: key={pygame.key.name(event.key)}")
        #     elif event.type in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP]:
        #         print(f"DEBUG: GameView.handle_pygame_event - {event_name}: button={event.button}, pos={event.pos}")
        #     elif event.type == pygame.MOUSEMOTION:
        #         # Only log mouse motion occasionally to avoid spam
        #         if hasattr(self, '_last_motion_log') and pygame.time.get_ticks() - self._last_motion_log < 100:
        #             pass  # Skip logging
        #         else:
        #             print(f"DEBUG: GameView.handle_pygame_event - {event_name}: pos={event.pos}")
        #             self._last_motion_log = pygame.time.get_ticks()

        # PRIORITY 0: Handle unit detail panel escape key
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.detailed_unit and hasattr(self.unit_detail_panel, 'handle_event') and hasattr(self.unit_detail_panel, 'visible') and self.unit_detail_panel.visible:
                # print(f"DEBUG: GameView - Delegating ESC to unit detail panel")
                if self.unit_detail_panel.handle_event(event):
                    self.close_unit_details()
                    return True

        # PRIORITY 1: Top pane and overlay handling BEFORE phase-specific handlers
        dialog_active = False
        try:
            if self.dialog_manager and self.dialog_manager.top():
                dialog_active = True
        except Exception:
            dialog_active = False
        if event.type == pygame.MOUSEBUTTONDOWN and not dialog_active:
            # Mission popup overlay closes on any click
            if getattr(self, '_cp_history_popup', None):
                self._cp_history_popup = None
                return True
            if getattr(self, '_vp_history_popup', None):
                self._vp_history_popup = None
                return True
            if getattr(self, '_mission_popup', None):
                self._mission_popup = None
                return True
            # Intercept clicks in the top status pane so they don't fall through
            if True:
                left = self.battlefield_left
                width = self.scaled_battlefield_width
                top_rect = pygame.Rect(left, 0, width, self.top_pane_height_px)
                if top_rect.collidepoint(event.pos):
                    if self._ui_hitboxes:
                        for key, (rect, player) in list(self._ui_hitboxes.items()):
                            if not str(key).startswith("vp_"):
                                continue
                            if rect.collidepoint(event.pos) and player is not None:
                                self._vp_history_popup = {"player": player}
                                self.popup_overlays.reset_vp_scroll()
                                return True
                    if self._ui_hitboxes:
                        for key, (rect, player) in list(self._ui_hitboxes.items()):
                            if not str(key).startswith("cp_"):
                                continue
                            if rect.collidepoint(event.pos) and player is not None:
                                self._cp_history_popup = {"player": player}
                                self.popup_overlays.reset_cp_scroll()
                                return True
                    # If clicking on mission buttons (primary/secondaries), open popup
                    if self._ui_hitboxes:
                        for key, (rect, card) in list(self._ui_hitboxes.items()):
                            if key != 'primary' and not str(key).startswith('sec_'):
                                continue
                            if rect.collidepoint(event.pos) and card is not None:
                                title = getattr(card, 'name', 'Mission')
                                body = getattr(card, 'description', '')
                                image_path = self.popup_overlays.find_mission_card_image_path(card, is_primary=(key == 'primary'))
                                self._mission_popup = {'title': title, 'body': body, 'image_path': image_path}
                                return True
                    # Otherwise consume the click within top pane
                    return True

            # Handle stratagem pane item clicks
            if self._ui_hitboxes:
                for key, payload in list(self._ui_hitboxes.items()):
                    if not str(key).startswith("strat_item_"):
                        continue
                    rect, item = payload
                    if rect.collidepoint(event.pos):
                        owner = item.get("owner")
                        if owner is None:
                            return True
                        if item.get("available"):
                            self._attempt_use_stratagem(owner, item)
                        return True

            # Consume clicks inside stratagem panes to avoid map interactions
            try:
                if self.left_stratagem_pane and self.left_stratagem_pane.rect.collidepoint(event.pos):
                    return True
                if self.right_stratagem_pane and self.right_stratagem_pane.rect.collidepoint(event.pos):
                    return True
            except Exception:
                pass

            # Handle bottom rule button clicks
            if self._ui_hitboxes:
                key_map = [
                    ("det_rule_p1", "detachment"),
                    ("army_rule_p1", "army"),
                    ("det_rule_p2", "detachment"),
                    ("army_rule_p2", "army"),
                ]
                for key, rule_type in key_map:
                    if key in self._ui_hitboxes:
                        rect, player = self._ui_hitboxes[key]
                        if rect.collidepoint(event.pos):
                            self._rule_support_cache.pop((get_entity_id(player), rule_type), None)
                            self._toggle_rule_panel(player, rule_type)
                            return True

            # Handle rule detail panel clicks (HUD button, etc.)
            if self.rule_detail_panel and self.rule_detail_panel.visible and event.button == 1:
                if getattr(self.rule_detail_panel, "rect", None):
                    if self.rule_detail_panel.rect.collidepoint(event.pos):
                        if hasattr(self.rule_detail_panel, "handle_event"):
                            self.rule_detail_panel.handle_event(event)
                        return True

        # PRIORITY 2: Let phase manager handle phase-specific events next
        # print(f"DEBUG: GameView - Delegating to phase manager")
        if self.phase_manager.handle_event(event):
            # print(f"DEBUG: GameView - Event was handled by phase manager")
            return True
        else:
            # print(f"DEBUG: GameView - Event was not handled by phase manager")
            pass
        
        # PRIORITY 3: Handle universal UI events that apply to all phases
        if event.type == pygame.MOUSEBUTTONDOWN:
            # Close rule panel on outside click, consume clicks inside
            if self.rule_detail_panel and self.rule_detail_panel.visible and event.button == 1:
                if getattr(self.rule_detail_panel, "rect", None):
                    if self.rule_detail_panel.rect.collidepoint(event.pos):
                        return True
                    self.rule_detail_panel.hide()
                    self._rule_panel_state = None
                    return True
            # Check for unit detail panel clicks (highest priority)
            if self.detailed_unit and event.button == 1:  # Left click
                if hasattr(self.unit_detail_panel, 'rect') and self.unit_detail_panel.rect:
                    if self.unit_detail_panel.rect.collidepoint(event.pos):
                        return True  # Consume the click on detail panel
                    else:
                        self.close_unit_details()
                        return True
            # Check for middle mouse button panning
            elif event.button == 2:  # Middle mouse button - start panning
                x, y = event.pos
                if self.battlefield_left < x < self.battlefield_right:
                    self.panning = True
                    self.pan_start_pos = (x, y)
                    self.pan_start_offset = (self.offset_x, self.offset_y)
                    return True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.on_mouse_release(event.pos[0], event.pos[1], event.button)
        elif event.type == pygame.MOUSEMOTION:
            self.on_mouse_motion(event.pos[0], event.pos[1])
        elif event.type == pygame.MOUSEWHEEL:
            if getattr(self, '_cp_history_popup', None):
                self.popup_overlays.adjust_cp_scroll(event.y)
                return True
            if getattr(self, '_vp_history_popup', None):
                self.popup_overlays.adjust_vp_scroll(event.y)
                return True
            mouse_x, mouse_y = pygame.mouse.get_pos()
            self.on_mouse_scroll(mouse_x, mouse_y, event.y)
        elif event.type == pygame.KEYDOWN:
            # Close mission popup with ESC
            if event.key == pygame.K_ESCAPE and getattr(self, '_mission_popup', None):
                self._mission_popup = None
                return True
            if event.key == pygame.K_ESCAPE and getattr(self, '_cp_history_popup', None):
                self._cp_history_popup = None
                return True
            if event.key == pygame.K_ESCAPE and getattr(self, '_vp_history_popup', None):
                self._vp_history_popup = None
                return True
            if event.key == pygame.K_ESCAPE and self.rule_detail_panel and self.rule_detail_panel.visible:
                self.rule_detail_panel.hide()
                self._rule_panel_state = None
                return True
            # Handle unit detail panel scrolling
            if self.detailed_unit:
                if event.key == pygame.K_UP or event.key == pygame.K_w:
                    self.unit_detail_panel.scroll(-30)  # Scroll up
                    return True
                elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                    self.unit_detail_panel.scroll(30)   # Scroll down
                    return True
                elif event.key == pygame.K_PAGEUP:
                    self.unit_detail_panel.scroll(-150)  # Page up
                    return True
                elif event.key == pygame.K_PAGEDOWN:
                    self.unit_detail_panel.scroll(150)   # Page down
                    return True
                elif event.key == pygame.K_HOME:
                    self.unit_detail_panel.scroll_offset = 0  # Go to top
                    return True
                elif event.key == pygame.K_END:
                    self.unit_detail_panel.scroll_offset = self.unit_detail_panel.max_scroll  # Go to bottom
                    return True
        
        return False

    # -------- Stratagem pane helpers --------
    def _attempt_use_stratagem(self, player, item: Dict[str, Any]) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        name = item.get("name")
        if not name:
            return

        context = dict(item.get("context", {}) or {})
        if item.get("is_reaction"):
            context["dequeue"] = True
        if "phase_name" not in context:
            phase_name = getattr(manager, "_current_phase_name", None)
            if phase_name:
                context["phase_name"] = phase_name

        name_u = str(name).strip().upper()
        if name_u == "NEW ORDERS" and "secondary_card" not in context:
            if callable(getattr(self, "_request_secondary_discard", None)):
                self._request_secondary_discard(player, self.game, lambda chosen: self._finalize_new_orders(player, name, context, chosen))
            return

        if name_u in ("FIRE OVERWATCH", "OVERWATCH") and "shooter_unit" not in context:
            if callable(getattr(self, "_request_overwatch_shooter", None)):
                enemy = context.get("enemy_unit")
                self._request_overwatch_shooter(player, self.game, enemy, lambda shooter: self._finalize_overwatch(player, name, context, shooter))
            return

        if name_u == "HEROIC INTERVENTION" and "unit" not in context and "target_unit" not in context:
            if callable(getattr(self, "_request_heroic_intervention_unit", None)):
                enemy = context.get("enemy_unit")
                candidates = context.get("candidates") or []
                self._request_heroic_intervention_unit(
                    player,
                    self.game,
                    enemy,
                    candidates,
                    lambda unit: self._finalize_heroic_intervention(player, name, context, unit),
                )
            return

        if name_u == "RAPID INGRESS" and "unit" not in context and "target_unit" not in context:
            if callable(getattr(self, "_request_rapid_ingress_unit", None)):
                candidates = context.get("candidates") or []
                self._request_rapid_ingress_unit(player, self.game, candidates, lambda unit: self._finalize_rapid_ingress(player, name, context, unit))
            return

        if name_u == "COUNTER-OFFENSIVE" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_counter_offensive_unit", None)):
                candidates = context.get("candidates") or []
                self._request_counter_offensive_unit(player, self.game, candidates, lambda unit: self._finalize_counter_offensive(player, name, context, unit))
            return

        if name_u == "HACK AND SLASH" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_hack_and_slash_unit", None)):
                self._request_hack_and_slash_unit(
                    player,
                    self.game,
                    lambda unit: self._finalize_hack_and_slash(player, name, context, unit),
                )
            return

        if name_u == "CRUEL BLADESMAN" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_cruel_bladesman_unit", None)):
                self._request_cruel_bladesman_unit(
                    player,
                    self.game,
                    lambda unit: self._finalize_generic_stratagem(player, name, context, unit),
                )
            return

        if name_u == "FRENZIED RESILIENCE" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_frenzied_resilience_unit", None)):
                candidates = context.get("candidates") or []
                self._request_frenzied_resilience_unit(
                    player,
                    self.game,
                    candidates,
                    lambda unit: self._finalize_frenzied_resilience(player, name, context, unit),
                )
            return

        if name_u == "DEATH ECSTASY" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_death_ecstasy_unit", None)):
                candidates = context.get("candidates") or []
                self._request_death_ecstasy_unit(
                    player,
                    self.game,
                    candidates,
                    lambda unit: self._finalize_generic_stratagem(player, name, context, unit),
                )
            return

        if name_u == "TERRIFYING SPECTACLE" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_terrifying_spectacle_unit", None)):
                self._request_terrifying_spectacle_unit(
                    player,
                    self.game,
                    lambda unit: self._finalize_generic_stratagem(player, name, context, unit),
                )
            return

        if name_u == "DAEMONIC FURY" and ("target_unit" not in context or "world_eaters_unit" not in context):
            if callable(getattr(self, "_request_daemonic_fury_targets", None)):
                candidates = context.get("candidates") or []
                self._request_daemonic_fury_targets(
                    player,
                    self.game,
                    candidates,
                    lambda bl_unit, we_unit: self._finalize_daemonic_fury(player, name, context, bl_unit, we_unit),
                )
            return

        if name_u == "CUT DOWN THE WEAK" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_cut_down_the_weak_unit", None)):
                enemy = context.get("enemy_unit")
                candidates = context.get("candidates") or []
                self._request_cut_down_the_weak_unit(
                    player,
                    self.game,
                    candidates,
                    enemy,
                    lambda unit: self._finalize_generic_stratagem(player, name, context, unit),
                )
            return

        if name_u == "DAEMONTIDE" and ("target_unit" not in context or "blood_legions_unit" not in context):
            if callable(getattr(self, "_request_daemontide_targets", None)):
                candidates = context.get("candidates") or []
                self._request_daemontide_targets(
                    player,
                    self.game,
                    candidates,
                    lambda we_unit, bl_unit: self._finalize_daemontide(player, name, context, we_unit, bl_unit),
                )
            return

        if name_u == "BLESSING OF BURNING BLOOD" and "target_unit" not in context:
            if callable(getattr(self, "_request_blessing_of_burning_blood_unit", None)):
                candidates = context.get("candidates") or []
                we_unit = context.get("world_eaters_unit")
                self._request_blessing_of_burning_blood_unit(
                    player,
                    self.game,
                    we_unit,
                    candidates,
                    lambda bl_unit: self._finalize_blessing_of_burning_blood(player, name, context, bl_unit),
                )
            return

        if name_u == "MURDER-CALL" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_murder_call_unit", None)):
                candidates = context.get("candidates") or []
                self._request_murder_call_unit(
                    player,
                    self.game,
                    candidates,
                    lambda unit: self._finalize_murder_call(player, name, context, unit),
                )
            return

        if name_u == "SUMMONED BY SLAUGHTER" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_summoned_by_slaughter_unit", None)):
                candidates = context.get("candidates") or []
                self._request_summoned_by_slaughter_unit(
                    player,
                    self.game,
                    candidates,
                    lambda unit: self._finalize_summoned_by_slaughter(player, name, context, unit),
                )
            return

        if name_u == "BLITZING FIREPOWER" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_blitzing_firepower_unit", None)):
                candidates = context.get("candidates") or []
                self._request_blitzing_firepower_unit(
                    player,
                    self.game,
                    candidates,
                    lambda unit: self._finalize_blitzing_firepower(player, name, context, unit),
                )
            return

        if name_u == "LIGHTNING-FAST REACTIONS" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_lightning_fast_reactions_unit", None)):
                candidates = context.get("candidates") or []
                self._request_lightning_fast_reactions_unit(
                    player,
                    self.game,
                    candidates,
                    lambda unit: self._finalize_lightning_fast_reactions(player, name, context, unit),
                )
            return

        if name_u == "UNYIELDING FORMS" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_unyielding_forms_unit", None)):
                candidates = context.get("candidates") or []
                enemy = context.get("attacking_unit") or context.get("enemy_unit")
                self._request_unyielding_forms_unit(
                    player,
                    self.game,
                    candidates,
                    enemy,
                    lambda unit: self._finalize_generic_stratagem(player, name, context, unit),
                )
            return

        if name_u == "MERCILESS RECLAMATION" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_merciless_reclamation_unit", None)):
                candidates = context.get("candidates") or []
                phase_name = context.get("phase_name")
                self._request_merciless_reclamation_unit(
                    player,
                    self.game,
                    candidates,
                    lambda unit: self._finalize_generic_stratagem(player, name, context, unit),
                    phase_name=phase_name,
                )
            return

        if name_u == "DIMENSIONAL TUNNEL" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_dimensional_tunnel_unit", None)):
                candidates = context.get("candidates") or []
                self._request_dimensional_tunnel_unit(
                    player,
                    self.game,
                    candidates,
                    lambda unit: self._finalize_generic_stratagem(player, name, context, unit),
                )
            return

        if name_u == "CHRONOSHIFT" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_chronoshift_unit", None)):
                candidates = context.get("candidates") or []
                self._request_chronoshift_unit(
                    player,
                    self.game,
                    candidates,
                    lambda unit: self._finalize_generic_stratagem(player, name, context, unit),
                )
            return

        if name_u == "ENDLESS SERVITUDE" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_endless_servitude_unit", None)):
                candidates = context.get("candidates") or []
                self._request_endless_servitude_unit(
                    player,
                    self.game,
                    candidates,
                    lambda unit: self._finalize_generic_stratagem(player, name, context, unit),
                )
            return

        if name_u == "REACTIVE REPOSITION" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_reactive_reposition_unit", None)):
                candidates = context.get("candidates") or []
                enemy = context.get("enemy_unit") or context.get("attacking_unit")
                self._request_reactive_reposition_unit(
                    player,
                    self.game,
                    candidates,
                    enemy,
                    lambda unit: self._finalize_generic_stratagem(player, name, context, unit),
                )
            return

        if name_u == "SKYBORNE SANCTUARY" and ("target_unit" not in context or "transport_unit" not in context):
            if callable(getattr(self, "_request_skyborne_sanctuary_targets", None)):
                candidates = context.get("candidates") or []
                transports_by_unit = context.get("transport_candidates_by_unit") or {}
                self._request_skyborne_sanctuary_targets(
                    player,
                    self.game,
                    candidates,
                    transports_by_unit,
                    lambda unit, transport: self._finalize_skyborne_sanctuary(player, name, context, unit, transport),
                )
            return

        if name_u == "WEBWAY TUNNEL" and "target_unit" not in context and "unit" not in context:
            if callable(getattr(self, "_request_webway_tunnel_unit", None)):
                candidates = context.get("candidates") or []
                self._request_webway_tunnel_unit(
                    player,
                    self.game,
                    candidates,
                    lambda unit: self._finalize_webway_tunnel(player, name, context, unit),
                )
            return

        if name_u == "MURDER-CALL" and ("target_unit" in context or "unit" in context):
            unit = context.get("target_unit") or context.get("unit")
            self._finalize_murder_call(player, name, context, unit)
            return

        if name_u == "SUMMONED BY SLAUGHTER" and ("target_unit" in context or "unit" in context) and "manual_placement" not in context:
            unit = context.get("target_unit") or context.get("unit")
            self._finalize_summoned_by_slaughter(player, name, context, unit)
            return

        if name_u == "SKULLS FOR THE SKULL THRONE!" and "attacker_unit" in context:
            if callable(getattr(self, "_request_blessings_roll", None)):
                if self._blessings_flow_active:
                    return
                self._blessings_flow_active = True

                def _done(payload):
                    self._blessings_flow_active = False
                    if not payload:
                        print("Skulls for the Skull Throne cancelled or failed")
                        return
                    ctx = dict(context)
                    try:
                        ctx["unit"] = payload.get("unit") or ctx.get("attacker_unit")
                        ctx["blessings_ctx"] = payload.get("ctx")
                        ctx["selected_blessings"] = payload.get("selected_blessings") or payload.get("result", {}).get("activated")
                    except Exception:
                        pass
                    ok2 = manager.use(name, **ctx)
                    if ok2:
                        print(f"Used stratagem: {name}")
                    else:
                        print(f"Could not use stratagem: {name}")

                self._request_blessings_roll(player, self.game, context, _done)
            return

        if callable(getattr(self, "_request_yes_no", None)):
            try:
                target_unit = context.get("target_unit", None)
                strat = manager.get_by_name(str(name)) if manager else None
                if strat is not None and target_unit is not None:
                    prev = player.preview_stratagem_cp_cost(strat, target_unit=target_unit, assume_optional_discounts=True)
                    reasons = list(prev.get("reasons", []) or [])
                    use_mop = any("Master of the Pageant" in str(r) for r in reasons)
                    use_dts = any("Direct the Slaughter" in str(r) for r in reasons)
                    tsd_reason = next((r for r in reasons if "Targeted Stratagem Discount" in str(r)), None)
                    use_tsd = bool(tsd_reason)
                    if use_mop or use_dts or use_tsd:
                        if self._optional_flow_active:
                            return
                        self._optional_flow_active = True
                        base = int(prev.get("base", getattr(strat, "cp_cost", 0) or 0) or 0)
                        if use_mop:
                            title = "Master of the Pageant"
                            msg = f"Use Master of the Pageant to reduce CP cost by 1?\n\n{str(name)}: {base}CP -> {max(0, base-1)}CP"
                            decision_key = "MASTER_OF_THE_PAGEANT"
                        elif use_dts:
                            title = "Direct the Slaughter"
                            msg = f"Use Direct the Slaughter to reduce CP cost by 1?\n\n{str(name)}: {base}CP -> {max(0, base-1)}CP"
                            decision_key = "DIRECT_THE_SLAUGHTER"
                        else:
                            label = "Stratagem CP Discount"
                            if tsd_reason:
                                m = re.search(r"Targeted Stratagem Discount\s*\(([^)]+)\)", str(tsd_reason))
                                if m:
                                    label = m.group(1).strip() or label
                            title = label
                            msg = f"Use {label} to reduce CP cost by 1?\n\n{str(name)}: {base}CP -> {max(0, base-1)}CP"
                            decision_key = "TARGETED_STRATAGEM_DISCOUNT"

                        def _done(chosen: bool):
                            self._optional_flow_active = False
                            try:
                                player.set_next_optional_decision(decision_key, bool(chosen))
                            except Exception:
                                pass
                            ok2 = manager.use(name, **context)
                            if ok2:
                                print(f"Used stratagem: {name}")
                            else:
                                print(f"Could not use stratagem: {name}")

                        self._request_yes_no(title, msg, "Use", "Skip", _done)
                        return
            except Exception:
                pass

        ok = manager.use(name, **context)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_new_orders(self, player, name: str, context: Dict[str, Any], selected_card) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        ctx = dict(context)
        ctx["secondary_card"] = selected_card
        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_generic_stratagem(self, player, name: str, context: Dict[str, Any], unit) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        if unit is None:
            print(f"{name}: no unit selected")
            return
        ctx = dict(context)
        ctx["unit"] = unit
        ctx["target_unit"] = unit
        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_overwatch(self, player, name: str, context: Dict[str, Any], shooter_unit) -> None:
        if self._overwatch_flow_active:
            return
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        if shooter_unit is None:
            print("Overwatch: no shooter selected")
            return
        ctx = dict(context)
        ctx["shooter_unit"] = shooter_unit
        if "phase_name" not in ctx:
            phase_name = getattr(manager, "_current_phase_name", None)
            if phase_name:
                ctx["phase_name"] = phase_name
        enemy = ctx.get("enemy_unit")
        if callable(getattr(self, "_request_overwatch_shooting", None)):
            try:
                setattr(shooter_unit, "_overwatch_sixes_only", True)
            except Exception:
                pass
            self._overwatch_flow_active = True

            def _done_callback(executed: bool):
                try:
                    delattr(shooter_unit, "_overwatch_sixes_only")
                except Exception:
                    pass
                self._overwatch_flow_active = False
                if executed:
                    s = manager.get_by_name(str(name)) if manager else None
                    if s and player.spend_command_points(
                        s.cp_cost,
                        reason=f"Stratagem: {s.name}",
                        source="stratagem",
                    ):
                        manager._used_this_turn["OVERWATCH"] = True
                        if ctx.get("dequeue") is True and hasattr(manager, "_dequeue_reaction_by_name"):
                            manager._dequeue_reaction_by_name(s.name)
                        print(f"Used stratagem: {name}")
                    else:
                        print("Overwatch: failed to spend CP")
                else:
                    print("Overwatch cancelled or failed")

            self._request_overwatch_shooting(shooter_unit, enemy, _done_callback)
            return

        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_heroic_intervention(self, player, name: str, context: Dict[str, Any], unit) -> None:
        if self._heroic_flow_active:
            return
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        if unit is None:
            print("Heroic Intervention: no unit selected")
            return
        enemy_unit = context.get("enemy_unit")
        if enemy_unit is None:
            print("Heroic Intervention: no enemy unit context")
            return

        dist = None
        try:
            if self.game and getattr(self.game, "map", None):
                dist = self.game.map.get_distance_between_units(unit, enemy_unit)
        except Exception:
            dist = None
        if dist is None or dist > 6.0:
            print("Heroic Intervention: unit not within 6\" of enemy")
            return

        try:
            if unit.has_keyword("Vehicle") and not unit.has_keyword("Walker"):
                print("Heroic Intervention: only WALKER vehicles can be selected")
                return
        except Exception:
            pass

        try:
            from ..rules.stratagems import _unit_cannot_be_target_of_stratagem
            if _unit_cannot_be_target_of_stratagem(unit):
                print("Heroic Intervention: unit cannot be targeted by stratagems")
                return
        except Exception:
            pass

        try:
            if not unit.can_declare_charge_against(enemy_unit, self.game, out_of_turn=True):
                print("Heroic Intervention: unit cannot declare a charge against that enemy")
                return
        except Exception:
            print("Heroic Intervention: unit cannot declare a charge against that enemy")
            return

        declared = None
        try:
            declared = self.game.declare_charge(unit, [enemy_unit], out_of_turn=True)
        except Exception:
            declared = None
        if not declared:
            print("Heroic Intervention: charge declaration failed")
            return

        name_u = str(name).strip().upper()
        if name_u == "HEROIC INTERVENTION" and name_u in getattr(manager, "_used_stratagems_this_phase", set()):
            try:
                if not manager._heroic_intervention_repeat_allowed(target_unit=unit):
                    print("Heroic Intervention: already used this phase")
                    return
            except Exception:
                print("Heroic Intervention: already used this phase")
                return

        strat = manager.get_by_name(str(name)) if manager else None
        eff_cost = None
        if strat is not None:
            eff_cost = strat.cp_cost
            try:
                if hasattr(player, "apply_stratagem_cp_cost"):
                    eff_cost = int(player.apply_stratagem_cp_cost(strat, target_unit=unit).get("cost", strat.cp_cost))
            except Exception:
                eff_cost = strat.cp_cost
        if strat is None or not player.spend_command_points(
            int(eff_cost or 0),
            reason=f"Stratagem: {strat.name}",
            source="stratagem",
        ):
            print("Heroic Intervention: failed to spend CP")
            return

        if context.get("dequeue") is True and hasattr(manager, "_dequeue_reaction_by_name"):
            manager._dequeue_reaction_by_name(strat.name)
        try:
            manager._used_stratagems_this_phase.add((strat.name or "").strip().upper())
            manager._record_heroic_intervention_use(unit)
        except Exception:
            pass

        base_roll = int(declared.get("base_roll", 0) or 0)
        modifiers = []
        getter = getattr(self.game, "get_charge_roll_modifiers", None)
        if callable(getter):
            modifiers = list(getter(unit, target_unit=enemy_unit) or [])
        mod_total = sum(int(val) for val, _source in modifiers if isinstance(val, (int, float)))
        max_charge_distance = max(0, base_roll + mod_total)
        self._heroic_flow_active = True

        def on_charge_movement_complete(completed: bool):
            self._heroic_flow_active = False
            if completed:
                in_engagement_range = False
                try:
                    enemy_units = self.game.map.get_enemy_units(unit)
                    in_engagement_range = any(
                        self.game.map.is_within_engagement_range(unit, enemy)
                        for enemy in enemy_units if enemy.is_alive()
                    )
                except Exception:
                    in_engagement_range = False
                if in_engagement_range:
                    print(f"{unit.name} Heroic Intervention charge successful - achieved engagement range")
                else:
                    print(f"{unit.name} Heroic Intervention charge failed - did not achieve engagement range")
            else:
                print(f"{unit.name} Heroic Intervention charge movement failed or skipped")

        try:
            self.phase_manager._request_move_unit_decision(
                unit,
                "charge",
                on_charge_movement_complete,
                max_distance=max_charge_distance,
                target_unit=enemy_unit,
            )
        except Exception:
            self._heroic_flow_active = False
            print("Heroic Intervention: failed to open charge movement dialog")
            return

        print(f"Used stratagem: {name}")

    def _finalize_rapid_ingress(self, player, name: str, context: Dict[str, Any], unit) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        ctx = dict(context)
        ctx["unit"] = unit
        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_counter_offensive(self, player, name: str, context: Dict[str, Any], unit) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        ctx = dict(context)
        ctx["target_unit"] = unit
        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_hack_and_slash(self, player, name: str, context: Dict[str, Any], unit) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        if unit is None:
            print("Hack and Slash: no unit selected")
            return
        ctx = dict(context)
        ctx["unit"] = unit
        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_frenzied_resilience(self, player, name: str, context: Dict[str, Any], unit) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        if unit is None:
            print("Frenzied Resilience: no unit selected")
            return
        ctx = dict(context)
        ctx["unit"] = unit
        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_daemonic_fury(self, player, name: str, context: Dict[str, Any], bl_unit, we_unit) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        if bl_unit is None or we_unit is None:
            print("Daemonic Fury: missing unit selection")
            return
        ctx = dict(context)
        ctx["target_unit"] = bl_unit
        ctx["world_eaters_unit"] = we_unit
        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_daemontide(self, player, name: str, context: Dict[str, Any], we_unit, bl_unit) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        if we_unit is None or bl_unit is None:
            print("Daemontide: missing unit selection")
            return
        ctx = dict(context)
        ctx["target_unit"] = we_unit
        ctx["blood_legions_unit"] = bl_unit
        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_blessing_of_burning_blood(self, player, name: str, context: Dict[str, Any], bl_unit) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        if bl_unit is None:
            print("Blessing of Burning Blood: no unit selected")
            return
        ctx = dict(context)
        ctx["target_unit"] = bl_unit
        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_murder_call(self, player, name: str, context: Dict[str, Any], unit) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        if unit is None:
            print("Murder-Call: no unit selected")
            return
        ctx = dict(context)
        ctx["unit"] = unit
        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_summoned_by_slaughter(self, player, name: str, context: Dict[str, Any], unit) -> None:
        if self._summoned_by_slaughter_flow_active:
            return
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        if unit is None:
            print("Summoned by Slaughter: no unit selected")
            return
        destroyed_base = context.get("destroyed_model_base") or context.get("destroyed_base")
        if destroyed_base is None:
            print("Summoned by Slaughter: missing destroyed model position")
            return
        game_map = getattr(self.game, "map", None)
        if game_map is None:
            print("Summoned by Slaughter: no map context")
            return

        strat = manager.get_by_name(str(name)) if manager else None
        if strat is not None and player.command_points < strat.cp_cost:
            print("Summoned by Slaughter: not enough CP")
            return

        destroyed_shape = None
        try:
            destroyed_shape = destroyed_base.get_base_shape()
        except Exception:
            destroyed_shape = None

        def _placement_validator(model, x: float, y: float, z: float) -> dict:
            try:
                # Build candidate base
                base = Base(model.model_base.base_type, model.model_base.radius)
                base.set_position(float(x), float(y), float(z))
                base.set_facing(float(self.individual_model_movement_dialog.get_deploy_facing_radians()))
                try:
                    base.set_model_height(float(getattr(model.model_base, "model_height", base.model_height)))
                except Exception:
                    pass
            except Exception:
                return {"valid": False, "reason": "Invalid base for placement"}

            # Battlefield boundary
            try:
                if not game_map.is_within_boundary(model, (float(x), float(y))):
                    return {"valid": False, "reason": "Outside battlefield"}
            except Exception:
                pass

            # RUINS placement validation
            try:
                from warhammer40k_ai.battlefield.map import validate_ruins_placement
                ruins_validation = validate_ruins_placement(unit, (float(x), float(y), float(z)), game_map.terrain_features, moving_model=model)
                if not ruins_validation.get("valid", False):
                    return {"valid": False, "reason": ruins_validation.get("reason", "RUINS placement invalid")}
            except Exception:
                pass

            # Wholly within 9" of destroyed model (3D distance).
            try:
                dz = abs(float(z) - float(getattr(destroyed_base, "z", 0.0)))
                if dz > 9.0 + 1e-6:
                    return {"valid": False, "reason": "Too far from destroyed model (>9\")"}
                if destroyed_shape is None:
                    return {"valid": False, "reason": "Missing destroyed model geometry"}
                r2 = math.sqrt(max(0.0, (9.0 * 9.0) - (dz * dz)))
                allowed = destroyed_shape.buffer(r2)
                if not allowed.covers(base.get_base_shape()):
                    return {"valid": False, "reason": "Not wholly within 9\" of destroyed model"}
            except Exception:
                return {"valid": False, "reason": "Placement range check failed"}

            # More than 6" horizontally away from all enemy units.
            try:
                from ..utility.aura_utils import horizontal_distance_between_bases_2d
                for enemy in list(game_map.get_enemy_units(unit) or []):
                    if not getattr(enemy, "is_alive", lambda: True)():
                        continue
                    if not getattr(enemy, "deployed", True):
                        continue
                    for em in list(getattr(enemy, "models", []) or []):
                        if not getattr(em, "is_alive", True):
                            continue
                        if float(horizontal_distance_between_bases_2d(base, em.model_base)) <= 6.0 + 1e-6:
                            return {"valid": False, "reason": "Too close to enemy (<6\")"}
            except Exception:
                pass

            return {"valid": True, "reason": "OK"}

        self._summoned_by_slaughter_flow_active = True

        def _on_complete(completed: bool):
            self._summoned_by_slaughter_flow_active = False
            if not completed:
                print("Summoned by Slaughter: placement cancelled or failed")
                return
            ctx = dict(context)
            ctx["target_unit"] = unit
            ctx["manual_placement"] = True
            ok = manager.use(name, **ctx)
            if ok:
                print(f"Used stratagem: {name}")
            else:
                print(f"Could not use stratagem: {name}")

        try:
            self.phase_manager._request_move_unit_decision(
                unit,
                "deploy",
                _on_complete,
                max_distance=0.0,
                placement_validator=_placement_validator,
            )
        except Exception:
            self._summoned_by_slaughter_flow_active = False
            print("Summoned by Slaughter: failed to open placement dialog")

    def _finalize_blitzing_firepower(self, player, name: str, context: Dict[str, Any], unit) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        if unit is None:
            print("Blitzing Firepower: no unit selected")
            return
        ctx = dict(context)
        ctx["unit"] = unit
        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_lightning_fast_reactions(self, player, name: str, context: Dict[str, Any], unit) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        if unit is None:
            print("Lightning-Fast Reactions: no unit selected")
            return
        ctx = dict(context)
        ctx["unit"] = unit
        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_skyborne_sanctuary(self, player, name: str, context: Dict[str, Any], unit, transport) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        if unit is None or transport is None:
            print("Skyborne Sanctuary: missing unit or transport")
            return
        ctx = dict(context)
        ctx["unit"] = unit
        ctx["transport_unit"] = transport
        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    def _finalize_webway_tunnel(self, player, name: str, context: Dict[str, Any], unit) -> None:
        manager = getattr(player, "stratagems", None)
        if manager is None:
            return
        if unit is None:
            print("Webway Tunnel: no unit selected")
            return
        ctx = dict(context)
        ctx["unit"] = unit
        ok = manager.use(name, **ctx)
        if ok:
            print(f"Used stratagem: {name}")
        else:
            print(f"Could not use stratagem: {name}")

    # -------- Rule info helpers --------
    def _get_waha_helper(self):
        helper = getattr(self, "_waha_helper", None)
        if helper is None:
            try:
                from ..waha_helper import WahaHelper
                helper = WahaHelper()
            except Exception:
                helper = None
            self._waha_helper = helper
        return helper

    def _pick_best_rule(self, candidates):
        if not candidates:
            return None
        def _id_key(entry):
            try:
                return int((entry.get("id") or "0").strip())
            except Exception:
                return 0
        return max(candidates, key=lambda e: (len(e.get("description", "") or ""), _id_key(e)))

    def _is_supported_rule_name(self, rule_name: str, rule_type: str) -> bool:
        name_u = (rule_name or "").strip().upper()
        if not name_u:
            return False
        if rule_type == "detachment":
            return name_u in SUPPORTED_DETACHMENT_RULES
        return name_u in SUPPORTED_ARMY_RULES

    def _get_rule_support_state(self, player, rule_type: str) -> bool:
        if player is None:
            return False
        army = player.get_army() if hasattr(player, "get_army") else None
        if army is None:
            return False
        try:
            signature = (
                getattr(army, "detachment_type", None),
                tuple(getattr(army, "faction_keyword", []) or []),
                getattr(army, "faction", None),
            )
        except Exception:
            signature = None
        cache_key = (get_entity_id(player), rule_type)
        cached = self._rule_support_cache.get(cache_key)
        if isinstance(cached, dict) and cached.get("signature") == signature:
            return bool(cached.get("supported", False))
        info = self._get_detachment_rule_info(player) if rule_type == "detachment" else self._get_army_rule_info(player)
        rule_name = ""
        try:
            rule_name = (info.get("name") or "").strip() if info else ""
        except Exception:
            rule_name = ""
        supported = self._is_supported_rule_name(rule_name, rule_type)
        self._rule_support_cache[cache_key] = {"signature": signature, "supported": supported, "rule_name": rule_name}
        return supported

    def _get_detachment_rule_info(self, player):
        army = player.get_army() if player else None
        if army is None:
            return None
        det = (getattr(army, "detachment_type", "") or "").strip()
        if not det:
            return None
        helper = self._get_waha_helper()
        if helper is None:
            return None
        det_key = det.lower()
        candidates = []
        for entry in helper.detachment_abilities.values():
            entry_det = (entry.get("detachment") or "").strip()
            if not entry_det:
                continue
            if entry_det.lower() != det_key:
                continue
            if getattr(army, "faction_id", None) and entry.get("faction_id"):
                if entry.get("faction_id") != army.faction_id:
                    continue
            candidates.append(entry)
        if not candidates:
            for entry in helper.detachment_abilities.values():
                entry_det = (entry.get("detachment") or "").strip()
                if not entry_det:
                    continue
                ed = entry_det.lower()
                if det_key not in ed and ed not in det_key:
                    continue
                if getattr(army, "faction_id", None) and entry.get("faction_id"):
                    if entry.get("faction_id") != army.faction_id:
                        continue
                candidates.append(entry)
        return self._pick_best_rule(candidates)

    def _get_army_rule_info(self, player):
        army = player.get_army() if player else None
        if army is None:
            return None
        helper = self._get_waha_helper()
        if helper is None:
            return None
        keywords = list(getattr(army, "faction_keyword", []) or [])
        if not keywords:
            try:
                for u in list(getattr(army, "units", []) or []):
                    kw = list(getattr(u, "faction_keywords", []) or [])
                    if kw:
                        keywords = kw
                        break
            except Exception:
                keywords = []
        keywords = [k for k in keywords if k]
        keywords.sort(key=len, reverse=True)
        if not keywords:
            return None
        for keyword in keywords:
            candidates = []
            for entry in helper.abilities.values():
                desc = entry.get("description", "") or ""
                if "army faction" not in desc.lower():
                    continue
                desc_l = desc.lower()
                if keyword.lower() in desc_l:
                    candidates.append(entry)
            if candidates:
                return self._pick_best_rule(candidates)
        return None

    def _toggle_rule_panel(self, player, rule_type: str, *, force_refresh: bool = False) -> None:
        if self.rule_detail_panel is None:
            return
        if self.rule_detail_panel.visible and isinstance(self._rule_panel_state, dict):
            if self._rule_panel_state.get("player") is player and self._rule_panel_state.get("rule_type") == rule_type:
                if not force_refresh:
                    self.rule_detail_panel.hide()
                    self._rule_panel_state = None
                    return

        if rule_type == "detachment":
            info = self._get_detachment_rule_info(player)
            title = "Detachment Rule"
        else:
            info = self._get_army_rule_info(player)
            title = "Army Rule"

        if not info:
            return
        rule_name = (info.get("name") or "").strip()
        legend = (info.get("legend") or "").strip()
        description = (info.get("description") or "").strip()

        supported = self._is_supported_rule_name(rule_name, rule_type)
        highlight_words = []
        if rule_type == "army" and "blessings of khorne" in rule_name.strip().lower():
            try:
                army = player.get_army()
            except Exception:
                army = None
            mgr = getattr(army, "blessings_of_khorne", None) if army is not None else None
            if mgr is not None:
                try:
                    active_keys = list(getattr(mgr, "active_blessing_keys", set()) or set())
                except Exception:
                    active_keys = []
                for key in active_keys:
                    try:
                        highlight_words.append(mgr.definitions[key].name)
                    except Exception:
                        continue
                highlight_words = sorted({str(w) for w in highlight_words if str(w).strip()}, key=str.lower)
        if rule_type == "army" and "templar vows" in rule_name.strip().lower():
            try:
                army = player.get_army()
            except Exception:
                army = None
            mgr = getattr(army, "templar_vows", None) if army is not None else None
            if mgr is not None:
                try:
                    active_vow = mgr.get_active_vow()
                except Exception:
                    active_vow = None
                if active_vow is not None:
                    try:
                        highlight_words.append(active_vow.name)
                    except Exception:
                        pass
        if rule_type == "army" and "nurgle" in rule_name.strip().lower() and "gift" in rule_name.strip().lower():
            try:
                army = player.get_army()
            except Exception:
                army = None
            mgr = getattr(army, "nurgles_gift", None) if army is not None else None
            if mgr is not None:
                try:
                    active_plague = mgr.get_active_plague()
                except Exception:
                    active_plague = None
                if active_plague is not None:
                    try:
                        highlight_words.append(active_plague.name)
                    except Exception:
                        pass
        if rule_type == "army" and "harbingers of dread" in rule_name.strip().lower():
            try:
                army = player.get_army()
            except Exception:
                army = None
            mgr = getattr(army, "harbingers_of_dread", None) if army is not None else None
            if mgr is not None:
                try:
                    active_dreads = mgr.get_active_dread_abilities()
                except Exception:
                    active_dreads = []
                for dread in active_dreads:
                    try:
                        highlight_words.append(dread.name)
                    except Exception:
                        continue
        if rule_type == "detachment" and "pledges to the dark prince" in rule_name.strip().lower():
            try:
                army = player.get_army()
            except Exception:
                army = None
            mgr = getattr(army, "emperors_children", None) if army is not None else None
            if mgr is not None:
                def _pact_active():
                    try:
                        return list(mgr.active_pact_thresholds() or [])
                    except Exception:
                        return []
                active = _pact_active()
                for token in active:
                    try:
                        highlight_words.append(token)
                    except Exception:
                        continue
                hud = {
                    "label": "Pact Points",
                    "get_tokens": lambda: int(getattr(mgr, "pact_points", 0) or 0),
                    "show_button": False,
                    "get_hint": lambda: ("Active bonuses: " + ", ".join(_pact_active())) if _pact_active() else "No Pact bonuses active.",
                    "highlight_words": active,
                }
        if rule_type == "detachment" and "blood tithe" in rule_name.strip().lower():
            try:
                army = player.get_army()
            except Exception:
                army = None
            mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if mgr is not None:
                try:
                    active_blood_tithe = [a.name for a in mgr.get_active_blood_tithe_abilities()]
                except Exception:
                    active_blood_tithe = []
                for ab in active_blood_tithe:
                    try:
                        highlight_words.append(ab)
                    except Exception:
                        continue
        hud = None
        if rule_type == "detachment" and "blood tithe" in rule_name.strip().lower():
            try:
                army = player.get_army()
            except Exception:
                army = None
            mgr = getattr(army, "world_eaters_detachments", None) if army is not None else None
            if mgr is not None:
                def _bt_hint():
                    try:
                        active = [a.name for a in mgr.get_active_blood_tithe_abilities()]
                    except Exception:
                        active = []
                    if not active:
                        return "No Blood Tithe abilities active."
                    return "Active: " + ", ".join(active)

                hud = {
                    "label": "Blood Tithe Points",
                    "get_tokens": lambda: int(getattr(mgr, "blood_tithe_points", 0) or 0),
                    "show_button": False,
                    "get_hint": _bt_hint,
                    "highlight_words": [a.name for a in mgr.get_active_blood_tithe_abilities()] if mgr else [],
                }
        if rule_type == "army" and "battle focus" in rule_name.strip().lower():
            mgr = self._get_battle_focus_manager(player)
            if mgr is not None:
                hud = {
                    "label": "Battle Focus Tokens",
                    "use_label": "Use Token",
                    "get_tokens": lambda: int(getattr(mgr, "tokens", 0) or 0),
                    "get_enabled": lambda: self._battle_focus_hud_enabled(player, mgr),
                    "get_hint": lambda: self._battle_focus_hud_hint(player, mgr),
                    "on_use": lambda: self._open_battle_focus_hud_use(player),
                }
        if rule_type == "army" and "power from pain" in rule_name.strip().lower():
            mgr = self._get_power_from_pain_manager(player)
            if mgr is not None:
                hud = {
                    "label": "Pain Tokens",
                    "get_tokens": lambda: int(getattr(mgr, "tokens", 0) or 0),
                    "show_button": False,
                }
        if rule_type == "army" and "cabal of sorcerers" in rule_name.strip().lower():
            mgr = self._get_cabal_manager(player)
            if mgr is not None:
                hud = {
                    "label": "Cabal Rituals",
                    "use_label": "Manifest",
                    "get_enabled": lambda: self._cabal_hud_enabled(player, mgr),
                    "get_hint": lambda: self._cabal_hud_hint(player, mgr),
                    "on_use": lambda: self._open_cabal_hud_use(player),
                }
        if rule_type == "army" and "shadow of chaos" in rule_name.strip().lower():
            shadow_hud = self._shadow_of_chaos_hud(player)
            if shadow_hud is not None:
                hud = shadow_hud
        if rule_type == "army" and "prioritised efficiency" in rule_name.strip().lower():
            mgr = self._get_prioritised_efficiency_manager(player)
            if mgr is not None:
                mode_name = ""
                try:
                    mode_name = str(getattr(mgr, "get_mode_name", lambda: "")() or "")
                except Exception:
                    mode_name = ""
                hud = {
                    "label": "Yield Points",
                    "get_tokens": lambda: int(getattr(mgr, "yield_points", 0) or 0),
                    "show_button": False,
                    "get_hint": lambda: f"Mode: {mode_name or 'Unknown'}",
                    "highlight_words": [mode_name] if mode_name else [],
                }
                if mode_name:
                    highlight_words.append(mode_name)
        if rule_type == "army" and "cult ambush" in rule_name.strip().lower():
            mgr = self._get_cult_ambush_manager(player)
            if mgr is not None:
                def _marker_hint():
                    try:
                        markers = len(mgr.get_active_markers())
                    except Exception:
                        markers = 0
                    try:
                        ambush_units = len(mgr.get_units_in_cult_ambush())
                    except Exception:
                        ambush_units = 0
                    return f"Markers: {markers} | Cult Ambush units: {ambush_units}"

                hud = {
                    "label": "Resurgence Points",
                    "get_tokens": lambda: int(getattr(mgr, "resurgence_points", 0) or 0),
                    "show_button": False,
                    "get_hint": _marker_hint,
                }
        if rule_type == "army" and "acts of faith" in rule_name.strip().lower():
            mgr = self._get_acts_of_faith_manager(player)
            if mgr is not None:
                def _miracle_hint():
                    try:
                        values = list(getattr(mgr, "miracle_dice", []) or [])
                    except Exception:
                        values = []
                    if not values:
                        return "No Miracle dice in pool."
                    return "Values: " + ", ".join(str(v) for v in values)

                hud = {
                    "label": "Miracle Dice",
                    "get_tokens": lambda: len(list(getattr(mgr, "miracle_dice", []) or [])),
                    "show_button": False,
                    "get_hint": _miracle_hint,
                }
        self.rule_detail_panel.set_content(
            title,
            rule_name,
            legend,
            description,
            supported=supported,
            hud=hud,
            highlight_words=highlight_words,
        )
        self._rule_panel_state = {"player": player, "rule_type": rule_type}

    # Note: on_mouse_press is now handled by phase-specific handlers in PhaseManager

    def on_mouse_release(self, x, y, button):
        """Handle mouse button release events"""
        if button == 2:  # Middle mouse button - stop panning
            self.panning = False

    def on_mouse_motion(self, x, y):
        """Handle mouse motion events"""
        if self.panning:
            # Calculate pan delta
            dx = x - self.pan_start_pos[0]
            dy = y - self.pan_start_pos[1]
            
            # Apply panning with sensitivity adjustment
            self.offset_x = self.pan_start_offset[0] + dx * MOUSE_PAN_SPEED
            self.offset_y = self.pan_start_offset[1] + dy * MOUSE_PAN_SPEED
            
            # Apply panning limits
            self.offset_x, self.offset_y = self._apply_pan_limits(self.offset_x, self.offset_y)
        
        # Update hover state for info pane
        self.info_pane.update_hover(x, y)

    def on_mouse_scroll(self, x, y, scroll_y):
        """Handle mouse scroll events"""
        # PRIORITY 0.5: Bottom logs scroll (before other panes if mouse over the boxes)
        try:
            if hasattr(self, '_bottom_log_boxes') and hasattr(self, '_bottom_log_scroll'):
                for key, rect in self._bottom_log_boxes.items():
                    if rect.collidepoint(x, y):
                        self._bottom_log_scroll[key] = max(0, int(self._bottom_log_scroll.get(key, 0)) - scroll_y)
                        return
        except Exception:
            pass
        # PRIORITY 1: Stratagem pane scrolling
        try:
            if self.left_stratagem_pane and self.left_stratagem_pane.rect.collidepoint(x, y):
                self.left_stratagem_pane.scroll(-scroll_y * 30)
                return
            if self.right_stratagem_pane and self.right_stratagem_pane.rect.collidepoint(x, y):
                self.right_stratagem_pane.scroll(-scroll_y * 30)
                return
        except Exception:
            pass
        # PRIORITY 1.5: Rule detail panel scrolling
        try:
            if self.rule_detail_panel and self.rule_detail_panel.visible:
                if getattr(self.rule_detail_panel, "rect", None) and self.rule_detail_panel.rect.collidepoint(x, y):
                    self.rule_detail_panel.scroll(-scroll_y * 30)
                    return
        except Exception:
            pass
        # PRIORITY 2: Check if scrolling in unit detail panel first (highest priority)
        if self.detailed_unit:
            # Use the rect that was set during drawing (if it exists)
            if hasattr(self.unit_detail_panel, 'rect') and self.unit_detail_panel.rect:
                # Check if mouse is over the unit detail panel using the actual rect
                if self.unit_detail_panel.rect.collidepoint(x, y):
                    self.unit_detail_panel.scroll(-scroll_y * 30)  # Scroll speed
                    return  # CRITICAL: Exit early to prevent other panels from handling the event
        
        # PRIORITY 3: Only check roster panes if unit detail panel didn't handle the event
        if self.left_roster_pane.rect.collidepoint(x, y):
            self.left_roster_pane.scroll(-scroll_y * 30)  # Scroll speed
        elif self.right_roster_pane.rect.collidepoint(x, y):
            self.right_roster_pane.scroll(-scroll_y * 30)
        
        # PRIORITY 4: Handle battlefield panning with Shift+Scroll (alternative to middle mouse)
        elif self.battlefield_left < x < self.battlefield_right:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
                # Horizontal panning with Shift+Scroll
                pan_delta = scroll_y * 20 * MOUSE_PAN_SPEED
                self.offset_x += pan_delta
                self.offset_x, self.offset_y = self._apply_pan_limits(self.offset_x, self.offset_y)
            elif keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]:
                # Vertical panning with Ctrl+Scroll
                pan_delta = scroll_y * 20 * MOUSE_PAN_SPEED
                self.offset_y += pan_delta
                self.offset_x, self.offset_y = self._apply_pan_limits(self.offset_x, self.offset_y)

    def reset_unit_position(self, unit, original_unit_position, original_model_positions):
        # Reset models to their original positions
        for model, original_position in zip(unit.models, original_model_positions):
            model.set_location(*original_position)

    def get_hovered_unit(self, x, y):
        # Check if hovering over a unit in the roster panes
        hovered_unit = self.left_roster_pane.get_hovered_unit(x, y)
        if hovered_unit:
            return hovered_unit, self.left_roster_pane
        
        hovered_unit = self.right_roster_pane.get_hovered_unit(x, y)
        if hovered_unit:
            return hovered_unit, self.right_roster_pane
        
        # Check if hovering over a model on the battlefield
        if self.battlefield_left < x < self.battlefield_right:
            battlefield_x, battlefield_y = self.screen_to_game_coords(x, y)
            
            # Create a point for the mouse position
            from shapely.geometry import Point
            mouse_point = Point(battlefield_x, battlefield_y)
            
            # Check all models in all units
            for unit in self.game_map.units:
                try:
                    models = unit.get_models_for_rendering()
                except Exception:
                    models = unit.models
                for model in models:
                    if not model.is_alive:
                        continue
                    # Get the model's base shape and check if mouse point is inside
                    model_shape = model.model_base.get_base_shape()
                    if model_shape.contains(mouse_point):
                        # Use the model's parent_unit to get the unit reference
                        parent_unit = model.parent_unit
                        # If hovering a model from an attached Leader, redirect to the bodyguard unit
                        try:
                            if bool(getattr(parent_unit, "is_leader", False)) and getattr(parent_unit, "attached_to", None) is not None:
                                parent_unit = parent_unit.attached_to
                        except Exception:
                            pass
                        # Determine which roster the unit belongs to (only if armies are loaded)
                        if (self.player1.get_army() and self.player1.get_army().units and 
                            parent_unit in self.player1.get_army().units):
                            return parent_unit, self.left_roster_pane
                        elif (self.player2.get_army() and self.player2.get_army().units and 
                              parent_unit in self.player2.get_army().units):
                            return parent_unit, self.right_roster_pane
        
        return None, None

    def get_unit_at_position(self, x: float, y: float, needs_conversion: bool = True) -> Optional[Unit]:
        """Get the unit at the given coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
            needs_conversion: If True, coordinates are screen coordinates that need conversion to game coordinates.
                            If False, coordinates are already game coordinates.
        """
        if needs_conversion:
            # Convert screen coordinates to game coordinates using helper method
            game_x, game_y = self.screen_to_game_coords(x, y)
        else:
            game_x = x
            game_y = y

        # Create a point for the game position
        from shapely.geometry import Point
        game_point = Point(game_x, game_y)

        # Prefer map units (single source of truth for battlefield presence)
        for unit in list(getattr(self.game_map, "units", []) or []):
            if not getattr(unit, "deployed", False):
                continue
            try:
                models = unit.get_models_for_rendering()
            except Exception:
                models = unit.models
            for model in models:
                if not model.is_alive:
                    continue
                model_shape = model.model_base.get_base_shape()
                if model_shape.contains(game_point):
                    u = model.parent_unit
                    try:
                        if bool(getattr(u, "is_leader", False)) and getattr(u, "attached_to", None) is not None:
                            return u.attached_to
                    except Exception:
                        pass
                    return u
        
        return None
    
    def get_model_at_position(self, x: float, y: float, needs_conversion: bool = True) -> Optional['Model']:
        """Get the specific model at the given position.

        Args:
            x: X coordinate (screen or game depending on needs_conversion)
            y: Y coordinate (screen or game depending on needs_conversion)
            needs_conversion: If True, (x,y) are screen coords; if False, already game coords.
        """
        if needs_conversion:
            game_x, game_y = self.screen_to_game_coords(x, y)
        else:
            game_x, game_y = x, y

        # Create a point for the game position
        from shapely.geometry import Point
        game_point = Point(game_x, game_y)

        for unit in list(getattr(self.game_map, "units", []) or []):
            if not getattr(unit, "deployed", False):
                continue
            try:
                models = unit.get_models_for_rendering()
            except Exception:
                models = unit.models
            for model in models:
                if not model.is_alive:
                    continue
                model_shape = model.model_base.get_base_shape()
                if model_shape.contains(game_point):
                    print(f"Found model {model.name} from unit {model.parent_unit.name}")
                    return model
        
        return None
    
    def screen_to_game_coords(self, screen_x: int, screen_y: int) -> Tuple[float, float]:
        """Convert screen coordinates to game coordinates with proper scaling"""
        top_offset = getattr(self, 'top_pane_height_px', 0)
        game_x = (screen_x - self.battlefield_left - self.offset_x) / (TILE_SIZE * self.zoom_level)
        game_y = (screen_y - top_offset - self.offset_y) / (TILE_SIZE * self.zoom_level)
        return game_x, game_y
    
    def game_to_screen_coords(self, game_x: float, game_y: float) -> Tuple[int, int]:
        """Convert game coordinates to screen coordinates with proper scaling"""
        top_offset = getattr(self, 'top_pane_height_px', 0)
        screen_x = int(self.battlefield_left + (game_x * TILE_SIZE * self.zoom_level) + self.offset_x)
        screen_y = int((game_y * TILE_SIZE * self.zoom_level) + self.offset_y + top_offset)
        return screen_x, screen_y

    def draw_move_path(self, unit: Unit):
        for model in unit.models:
            if not model.last_move_path:
                return

            # Convert game coordinates to screen coordinates
            screen_path = [self.game_to_screen_coords(point[0], point[1]) for point in model.last_move_path]

            # Draw the path
            pygame.draw.lines(self.screen, (0, 0, 255), False, screen_path, 2)

            # Draw start and end points
            start_point = screen_path[0]
            end_point = screen_path[-1]
                    # Movement path visualization simplified - removed start/end point circles

            # Draw direction arrows
            for i in range(len(screen_path) - 1):
                mid_point = ((screen_path[i][0] + screen_path[i+1][0]) // 2,
                            (screen_path[i][1] + screen_path[i+1][1]) // 2)
                # Direction indicator simplified - removed red dot

    def old_game_to_screen_coords(self, x: float, y: float) -> Tuple[int, int]:
        # DEPRECATED: Use the new game_to_screen_coords method instead
        # Convert game coordinates to screen coordinates  
        screen_x = int(self.battlefield_left + (x * TILE_SIZE * self.zoom_level) + self.offset_x)
        screen_y = int(y * TILE_SIZE * self.zoom_level + self.offset_y)
        return (screen_x, screen_y)
    
    def old_screen_to_game_coords(self, screen_pos: Tuple[int, int]) -> Tuple[float, float]:
        """DEPRECATED: Convert screen coordinates to game coordinates"""
        x, y = screen_pos
        # Convert from screen coordinates to game coordinates
        # Account for roster pane width, zoom level, and pan offset
        game_x = (x - self.battlefield_left - self.offset_x) / (TILE_SIZE * self.zoom_level)
        game_y = (y - self.offset_y) / (TILE_SIZE * self.zoom_level)
        return game_x, game_y

    def _draw_cult_ambush_markers(self, surface: pygame.Surface) -> None:
        if not self.game:
            return
        try:
            players = list(getattr(self.game, "players", []) or [])
        except Exception:
            players = []
        if not players:
            return

        color = (220, 180, 40)
        radius = max(4, int(CULT_AMBUSH_MARKER_RADIUS_INCHES * TILE_SIZE * self.zoom_level))

        for p in players:
            try:
                army = p.get_army()
            except Exception:
                army = None
            mgr = getattr(army, "cult_ambush", None) if army is not None else None
            if mgr is None:
                continue
            try:
                markers = list(mgr.get_active_markers() or [])
            except Exception:
                markers = []
            for marker in markers:
                try:
                    sx, sy = self.game_to_screen_coords(marker.x, marker.y)
                    pygame.draw.circle(surface, color, (sx, sy), radius, 2)
                    pygame.draw.circle(surface, color, (sx, sy), max(2, radius // 3), 1)
                except Exception:
                    continue

    def draw(self):
        self.screen.fill(DARK_GREY)

        # Draw stratagem panes
        draw_stratagem_panes(self)

        # Draw roster panes with enhanced styling
        self.left_roster_pane.draw(self.screen, self.game)
        self.right_roster_pane.draw(self.screen, self.game)

        # Draw the battlefield (use scaled viewport size and scaling-aware drawing)
        top_pane_height_px = int(2 * TILE_SIZE)
        self.top_pane_height_px = top_pane_height_px
        battlefield_surface = pygame.Surface((self.scaled_battlefield_width, self.scaled_battlefield_height - top_pane_height_px))
        draw_battlefield(
            battlefield_surface,
            self.zoom_level,
            self.offset_x,
            self.offset_y,
            tile_size=TILE_SIZE,
            battlefield_width_inches=BATTLEFIELD_WIDTH_INCHES,
            battlefield_height_inches=BATTLEFIELD_HEIGHT_INCHES,
            viewport_width=self.scaled_battlefield_width,
            viewport_height=self.scaled_battlefield_height,
        )

        # Draw terrain features on the battlefield
        for terrain_feature in self.game_map.terrain_features:
            draw_terrain_feature(
                battlefield_surface,
                terrain_feature,
                self.zoom_level,
                self.offset_x,
                self.offset_y,
                tile_size=TILE_SIZE,
            )

        # Draw deployment zones (with transparency)
        if hasattr(self.game, 'deployment_zones') and self.game.deployment_zones:
            draw_deployment_zones(
                battlefield_surface,
                self.game.deployment_zones,
                self.player1,
                self.player2,
                self.zoom_level,
                self.offset_x,
                self.offset_y,
            )

        # Draw objectives on the battlefield
        for objective in self.game_map.objectives:
            draw_objective(
                battlefield_surface,
                objective,
                self.zoom_level,
                self.offset_x,
                self.offset_y,
            )

        # Draw Cult Ambush markers
        self._draw_cult_ambush_markers(battlefield_surface)

        # Draw units on the battlefield
        units_to_draw = list(self.game_map.units)
        # Also draw a unit that is currently being deployed per-model (even if not registered yet)
        try:
            if (hasattr(self, 'individual_model_movement_dialog') and
                self.individual_model_movement_dialog and
                self.individual_model_movement_dialog.visible and
                self.individual_model_movement_dialog.unit and
                self.individual_model_movement_dialog.unit not in units_to_draw):
                units_to_draw.append(self.individual_model_movement_dialog.unit)
        except Exception:
            pass

        for unit in units_to_draw:
            # Check if this unit has a highlighted model for individual movement
            highlighted_model_index = None
            if (hasattr(self, 'individual_model_movement_dialog') and 
                self.individual_model_movement_dialog.visible and 
                self.individual_model_movement_dialog.unit == unit):
                highlighted_model_index = self.individual_model_movement_dialog.get_highlighted_model_index()

            # During per-model deployment, only draw models that have actually been placed
            model_indices_to_draw = None
            try:
                if (hasattr(self, 'individual_model_movement_dialog') and
                    self.individual_model_movement_dialog.visible and
                    self.individual_model_movement_dialog.unit == unit and
                    getattr(self.individual_model_movement_dialog, 'movement_type', '') == 'deploy'):
                    model_indices_to_draw = {
                        idx for idx, data in (self.individual_model_movement_dialog.model_movements or {}).items()
                        if data.get('completed', False)
                    }
            except Exception:
                model_indices_to_draw = None
            
            draw_units(
                battlefield_surface,
                unit,
                self.zoom_level,
                self.offset_x,
                self.offset_y,
                pygame.mouse.get_pos(),
                self.player1,
                self.player2,
                highlighted_model_index,
                model_indices_to_draw=model_indices_to_draw,
            )
        
        # Old unit-level movement range drawing removed - now using Individual Model Movement Dialog for all movement

        # Draw movement range indicator for individual model movement dialog
        # NOTE: skip path/range visuals during deployment placement
        if (hasattr(self, 'individual_model_movement_dialog') and
            self.individual_model_movement_dialog.visible and
            self.individual_model_movement_dialog.unit and
            self.individual_model_movement_dialog.selected_model_index is not None and
            getattr(self.individual_model_movement_dialog, 'movement_type', '') != 'deploy'):

            #print(f"DEBUG: Drawing individual model movement visualization")
            unit = self.individual_model_movement_dialog.unit
            model_index = self.individual_model_movement_dialog.selected_model_index

            if model_index < len(unit.models):
                selected_model = unit.models[model_index]
                movement_type = self.individual_model_movement_dialog.movement_type
                max_distance = self.individual_model_movement_dialog.max_distance
                game_map = self.individual_model_movement_dialog.game_map

                #print(f"DEBUG: Drawing range circle for {selected_model.name} (type: {movement_type}, distance: {max_distance})")
                # Draw range circle for the selected model
                draw_individual_model_movement_range(
                    battlefield_surface,
                    selected_model,
                    movement_type,
                    max_distance,
                    self.zoom_level,
                    self.offset_x,
                    self.offset_y,
                    game_map,
                )

                # Draw real-time path preview if mouse is hovering over battlefield
                #print(f"DEBUG: Checking for path preview - has target: {hasattr(self, 'individual_model_preview_target')}")
                #if hasattr(self, 'individual_model_preview_target'):
                    #print(f"DEBUG: Preview target value: {self.individual_model_preview_target}")

                if hasattr(self, 'individual_model_preview_target') and self.individual_model_preview_target:
                    #print(f"DEBUG: Drawing path preview for model {model_index} to {self.individual_model_preview_target}")
                    # Use unified pathfinding that accounts for already-moved models
                    from ..utility.calcs import unified_pathfinding, MovementType

                    # Get moved models from the dialog if available
                    moved_models_in_unit = set()
                    preview_movement_type = MovementType.MOVE  # Default
                    if hasattr(self, 'individual_model_movement_dialog') and self.individual_model_movement_dialog.visible:
                        for moved_index, movement_data in self.individual_model_movement_dialog.model_movements.items():
                            if movement_data.get('completed', False):
                                moved_models_in_unit.add(moved_index)

                        # Get the correct movement type from the dialog
                        dialog_movement_type = self.individual_model_movement_dialog.movement_type
                        movement_type_map = {
                            'move': MovementType.MOVE,
                            'advance': MovementType.ADVANCE,
                            'fall_back': MovementType.FALL_BACK,
                            'charge': MovementType.CHARGE,
                            'blood_surge': MovementType.BLOOD_SURGE,
                            'scout': MovementType.SCOUT,
                            'pile_in': MovementType.PILE_IN,
                            'consolidate': MovementType.CONSOLIDATE
                        }
                        preview_movement_type = movement_type_map.get(dialog_movement_type, MovementType.MOVE)
                        #print(f"DEBUG: Using movement type {preview_movement_type} for path preview (dialog type: {dialog_movement_type})")

                    # Convert 2D target to 3D if needed
                    if len(self.individual_model_preview_target) == 2:
                        target_3d = (self.individual_model_preview_target[0], self.individual_model_preview_target[1], selected_model.model_base.z)
                    else:
                        target_3d = self.individual_model_preview_target

                    # Get target unit for charge movement
                    target_unit = None
                    if hasattr(self, 'individual_model_movement_dialog') and self.individual_model_movement_dialog.visible:
                        target_unit = self.individual_model_movement_dialog.target_unit

                    path_result = unified_pathfinding(
                        model=selected_model,
                        target=target_3d,
                        movement_type=preview_movement_type,
                        max_distance=max_distance,
                        game_map=self.game.map,
                        target_unit=target_unit,
                        moved_models_in_unit=moved_models_in_unit
                    )

                    #print(f"DEBUG: Path result - valid: {path_result['valid']}, path length: {len(path_result['path']) if path_result['path'] else 0}")

                    # Draw the path and model base preview similar to scout movement
                    self._draw_individual_model_path_preview(battlefield_surface, selected_model,
                                                           path_result, self.individual_model_preview_target)
                #else:
                #    print(f"DEBUG: No preview target set for individual model movement")

        # Deployment placement: draw hover silhouette (base + facing arrow) while mouse moves over battlefield
        if (hasattr(self, 'individual_model_movement_dialog') and
            self.individual_model_movement_dialog and
            self.individual_model_movement_dialog.visible and
            getattr(self.individual_model_movement_dialog, 'movement_type', '') == 'deploy' and
            self.individual_model_movement_dialog.unit and
            self.individual_model_movement_dialog.selected_model_index is not None and
            hasattr(self, 'individual_model_preview_target') and self.individual_model_preview_target):
            try:
                unit = self.individual_model_movement_dialog.unit
                mi = self.individual_model_movement_dialog.selected_model_index
                if mi < len(unit.models):
                    m = unit.models[mi]
                    fx, fy = self.individual_model_preview_target
                    try:
                        facing = float(self.individual_model_movement_dialog.get_deploy_facing_radians())
                    except Exception:
                        facing = float(getattr(m.model_base, 'facing', 0.0))
                    ghost_color = (0, 255, 255)  # cyan
                    self._draw_model_base_preview(
                        battlefield_surface,
                        m,
                        float(fx),
                        float(fy),
                        ghost_color,
                        facing_override=facing,
                    )
            except Exception:
                pass

        # Draw weapon range indicator if a unit is selected for shooting
        if (hasattr(self, 'selected_unit') and self.selected_unit and
            hasattr(self, 'selected_weapon_profile') and self.selected_weapon_profile):
            draw_weapon_ranges(
                battlefield_surface,
                self.selected_unit,
                self.selected_weapon_profile,
                self.zoom_level,
                self.offset_x,
                self.offset_y,
            )
            # Highlight valid targets in green overlay if targeting mode active
            # Remove precomputed valid target highlighting to avoid heavy per-frame work

        # Draw scout visual feedback if in scout phase (draw on battlefield surface)
        if hasattr(self, 'phase_manager') and self.phase_manager:
            current_handler = self.phase_manager.get_current_handler()
            if isinstance(current_handler, PreBattlePhaseHandler):
                current_handler.draw_scout_visual_feedback(battlefield_surface)

        # Draw top mission/status pane and shift battlefield down
        draw_top_status_pane(self, top_pane_height_px)
        self.screen.blit(battlefield_surface, (self.battlefield_left, top_pane_height_px))

        # Draw repurposed bottom logs pane
        draw_bottom_logs_pane(self)

        # Draw unit details panel if requested
        if self.detailed_unit:
            self.unit_detail_panel.draw(self.screen, self.detailed_unit, 
                                        self.detail_panel_pos[0], self.detail_panel_pos[1])

        if self.rule_detail_panel and self.rule_detail_panel.visible:
            sw, sh = self.screen.get_size()
            x = int(self.battlefield_left + max(0, (self.scaled_battlefield_width - self.rule_detail_panel.width) // 2))
            y = int(max(10, (sh - self.rule_detail_panel.height) // 2))
            self.rule_detail_panel.draw(self.screen, x, y)

        # Draw move paths for all units (only if armies are loaded)
        current_player = self.game.get_current_player()
        if current_player and current_player.get_army() and current_player.get_army().units:
            for unit in current_player.get_army().units:
                self.draw_move_path(unit)

        # Draw UI interface components (non-dialog overlays like reserves arrival panel)
        if self.ui_interface:
            self.ui_interface.update(self.screen)

        # Draw all dialogs via the centralized modal stack (includes UI-interface dialogs).
        if hasattr(self, 'dialog_manager') and self.dialog_manager:
            self.dialog_manager.draw(self.screen)

        # Finally, draw popup overlays above everything if present
        if getattr(self, '_mission_popup', None) or getattr(self, '_vp_history_popup', None) or getattr(self, '_cp_history_popup', None):
            self.popup_overlays.set_screen(self.screen)
        if getattr(self, '_mission_popup', None):
            self.popup_overlays.draw_mission_popup(
                self._mission_popup.get('title', 'Mission'),
                self._mission_popup.get('body', ''),
                image_path=self._mission_popup.get('image_path'),
            )
        if getattr(self, '_vp_history_popup', None):
            self.popup_overlays.draw_vp_history_popup(self._vp_history_popup.get("player"))
        if getattr(self, '_cp_history_popup', None):
            self.popup_overlays.draw_cp_history_popup(self._cp_history_popup.get("player"))
        pygame.display.update()

    # Note: on_key_press is now handled by phase-specific handlers in PhaseManager
    # Detail panel scrolling is still handled in handle_pygame_event for universal access
    
    def force_complete_deployment(self):
        """Force complete the deployment phase by auto-deploying remaining units"""
        self.game.complete_deployment_phase()
        
        # Clear any selected units
        self.selected_unit = None
        self.left_roster_pane.selected_unit = None
        self.right_roster_pane.selected_unit = None
        
        print("Deployment phase completed! Press SPACE to start the game.")

    def close_unit_details(self):
        """Close the unit details panel"""
        self.detailed_unit = None
        # Reset scroll position when closing
        self.unit_detail_panel.scroll_offset = 0

    def _apply_pan_limits(self, offset_x: int, offset_y: int) -> Tuple[int, int]:
        """Apply panning limits to prevent moving outside the battlefield"""
        # Calculate world size in pixels
        tile_size_px = TILE_SIZE * self.zoom_level
        world_width_px = int(BATTLEFIELD_WIDTH_INCHES * tile_size_px)
        world_height_px = int(BATTLEFIELD_HEIGHT_INCHES * tile_size_px)

        # Viewport size is the scaled battlefield viewport
        viewport_width_px = int(self.scaled_battlefield_width)
        viewport_height_px = int(self.scaled_battlefield_height)

        # Max scrollable offsets (how far we can pan left/up as negative values)
        max_scroll_x = max(0, world_width_px - viewport_width_px)
        max_scroll_y = max(0, world_height_px - viewport_height_px)

        limited_offset_x = max(-max_scroll_x, min(0, offset_x))
        limited_offset_y = max(-max_scroll_y, min(0, offset_y))
        return limited_offset_x, limited_offset_y

    def get_phase_status(self) -> dict:
        """Get current phase status and allowed actions for debugging/testing"""
        if hasattr(self, 'phase_manager'):
            current_handler = self.phase_manager.get_current_handler()
            return {
                'current_phase': type(current_handler).__name__,
                'game_phase': self.game.phase.name if hasattr(self.game.phase, 'name') else str(self.game.phase),
                'setup_phase': self.game.get_current_setup_phase().name if self.game.is_in_setup_phase() else None,
                'is_deployment': self.game.is_deployment_phase(),
                'allowed_actions': self.phase_manager.get_current_allowed_actions()
            }
        else:
            return {'error': 'Phase manager not initialized'}

    def _draw_individual_model_path_preview(self, surface: pygame.Surface, model, path_result: dict, target_pos: tuple):
        """Draw path preview and model base for individual model movement"""
        if not path_result or not target_pos:
            return

        # Choose color based on pathfinding result
        if path_result['valid']:
            color = (0, 255, 255)  # Cyan for valid path
        else:
            color = (255, 165, 0)  # Orange for invalid path

        # Draw the path if available
        if path_result['path'] and len(path_result['path']) > 1:
            path_points = []
            for pos in path_result['path']:
                screen_x = int(pos[0] * TILE_SIZE * self.zoom_level + self.offset_x)
                screen_y = int(pos[1] * TILE_SIZE * self.zoom_level + self.offset_y)
                path_points.append((screen_x, screen_y))

            if len(path_points) > 1:
                pygame.draw.lines(surface, color, False, path_points, 3)

            # Draw target indicator with actual model base footprint
            final_pos = path_result['path'][-1]
            self._draw_model_base_preview(surface, model, final_pos[0], final_pos[1], color)
        else:
            # No path available, just draw target position
            self._draw_model_base_preview(surface, model, target_pos[0], target_pos[1], color)

    def _draw_model_base_preview(self, surface: pygame.Surface, model, game_x: float, game_y: float, color: tuple, facing_override: Optional[float] = None):
        """Draw the actual model base footprint at the specified game coordinates"""
        try:
            if not model or not hasattr(model, 'model_base'):
                # Fallback to small circle if no base information
                screen_x = int(game_x * TILE_SIZE * self.zoom_level + self.offset_x)
                screen_y = int(game_y * TILE_SIZE * self.zoom_level + self.offset_y)
                pygame.draw.circle(surface, color[:3], (screen_x, screen_y), 8, 2)
                return

            # Get the model's base shape at the target position
            facing = float(facing_override) if facing_override is not None else float(getattr(model.model_base, 'facing', 0.0))
            base_shape = model.model_base.get_base_shape_at(game_x, game_y, facing)

            # Convert the base shape to screen coordinates
            screen_points = []
            for x, y in base_shape.exterior.coords:
                screen_x = int(x * TILE_SIZE * self.zoom_level + self.offset_x)
                screen_y = int(y * TILE_SIZE * self.zoom_level + self.offset_y)
                screen_points.append((screen_x, screen_y))

            # Draw the base footprint
            if len(screen_points) > 2:
                # Draw filled shape with transparency
                alpha_color = (*color[:3], 100) if len(color) == 3 else color
                try:
                    # Create a temporary surface for alpha blending
                    temp_surface = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
                    pygame.draw.polygon(temp_surface, alpha_color, screen_points)
                    surface.blit(temp_surface, (0, 0))
                except:
                                        pygame.draw.polygon(surface, color[:3], screen_points, 2)

                # Draw outline
                pygame.draw.polygon(surface, color[:3], screen_points, 2)

                # Draw a facing arrow from the base center (matches silhouette rotation)
                try:
                    cx = int(game_x * TILE_SIZE * self.zoom_level + self.offset_x)
                    cy = int(game_y * TILE_SIZE * self.zoom_level + self.offset_y)

                    # Arrow length based on base radius (inches) scaled to pixels
                    try:
                        r = getattr(model.model_base, 'radius', (1.0, 1.0))
                        r_in = float(max(r)) if isinstance(r, (tuple, list)) else float(r)
                    except Exception:
                        r_in = 1.0
                    arrow_len = max(10.0, (r_in * 1.25) * TILE_SIZE * self.zoom_level)

                    ex = int(cx + math.cos(facing) * arrow_len)
                    ey = int(cy + math.sin(facing) * arrow_len)
                    pygame.draw.line(surface, color[:3], (cx, cy), (ex, ey), 3)

                    # Arrow head
                    head_len = max(6.0, arrow_len * 0.25)
                    left_ang = facing + math.radians(150.0)
                    right_ang = facing - math.radians(150.0)
                    lx = int(ex + math.cos(left_ang) * head_len)
                    ly = int(ey + math.sin(left_ang) * head_len)
                    rx = int(ex + math.cos(right_ang) * head_len)
                    ry = int(ey + math.sin(right_ang) * head_len)
                    pygame.draw.line(surface, color[:3], (ex, ey), (lx, ly), 3)
                    pygame.draw.line(surface, color[:3], (ex, ey), (rx, ry), 3)
                except Exception:
                    pass
        except Exception:
            return


def handle_zoom(zoom_level: float, event: pygame.event.Event) -> float:
    zoom_direction = event.y  # Positive for scroll up, negative for scroll down
    new_zoom = zoom_level + (ZOOM_SPEED * zoom_direction)
    return max(MIN_ZOOM, min(MAX_ZOOM, new_zoom))

def handle_pan(keys_pressed: Dict[int, bool], offset_x: int, offset_y: int, zoom_level: float,
               viewport_width: int, viewport_height: int) -> Tuple[int, int]:
    """Pan offsets constrained so battlefield (60x44 inches) is always visible, plus at most
    one extra row/column (black background) around edges in all directions.
    """
    tile_size = int(TILE_SIZE * zoom_level)
    world_w = BATTLEFIELD_WIDTH_INCHES * tile_size
    world_h = BATTLEFIELD_HEIGHT_INCHES * tile_size

    # Pan speed independent enough of zoom
    pan_speed = max(PAN_SPEED, int(PAN_SPEED * max(1.0, zoom_level)))
    new_offset_x, new_offset_y = offset_x, offset_y

    # Support arrow keys and WASD
    if keys_pressed[pygame.K_LEFT] or keys_pressed[pygame.K_a]:
        new_offset_x += pan_speed
    if keys_pressed[pygame.K_RIGHT] or keys_pressed[pygame.K_d]:
        new_offset_x -= pan_speed
    if keys_pressed[pygame.K_UP] or keys_pressed[pygame.K_w]:
        new_offset_y += pan_speed
    if keys_pressed[pygame.K_DOWN] or keys_pressed[pygame.K_s]:
        new_offset_y -= pan_speed

    # Allow at most one extra inch beyond battlefield on each side
    extra = tile_size  # one inch

    # Horizontal bounds: left <= offset_x <= right
    left_bound = viewport_width - world_w + extra  # when panned far right, world right edge + extra at viewport right
    right_bound = -extra  # when panned far left, world left edge - extra at viewport left
    new_offset_x = max(left_bound, min(right_bound, new_offset_x))

    # Vertical bounds
    top_bound = viewport_height - world_h + extra
    bottom_bound = -extra
    new_offset_y = max(top_bound, min(bottom_bound, new_offset_y))

    return new_offset_x, new_offset_y
