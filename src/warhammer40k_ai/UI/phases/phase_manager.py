from __future__ import annotations

import pygame
from abc import ABC, abstractmethod
from typing import Protocol, List, Dict, Tuple, Optional

from warhammer40k_ai.engine.fight_phase_manager import FightPhaseManager, FightStage
from warhammer40k_ai.utility.calcs import clear_enemy_model_cache
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.dice import get_roll

from ..ui_constants import TILE_SIZE
from ...utility.debug import describe_callable
from ...engine.ui_decision_bridge import (
    require_pending_decision_request as _require_pending_decision_request,
)
import logging
logger = logging.getLogger(__name__)


def _apply_game_command(game, kind: str, *, player_id: str | None = None, payload: Optional[dict] = None):
    from ...engine.commands import GameCommand

    cmd = GameCommand.create(kind, player_id=player_id, payload=dict(payload or {}))
    return game.apply_command(cmd)

def _current_player_id(game) -> str | None:
    try:
        return game.get_current_player().id
    except Exception:
        return None


def _execute_setup_phase_cmd(game, *, player_id: str | None = None, payload: Optional[dict] = None):
    from ...engine.command_kinds import CMD_EXECUTE_SETUP_PHASE

    return _apply_game_command(game, CMD_EXECUTE_SETUP_PHASE, player_id=player_id, payload=payload)


def _advance_setup_phase_cmd(game, *, player_id: str | None = None):
    from ...engine.command_kinds import CMD_ADVANCE_SETUP_PHASE

    return _apply_game_command(game, CMD_ADVANCE_SETUP_PHASE, player_id=player_id, payload={})


def _set_deployment_waiting_cmd(game, value: bool, *, player_id: str | None = None):
    from ...engine.command_kinds import CMD_SET_DEPLOYMENT_WAITING

    return _apply_game_command(game, CMD_SET_DEPLOYMENT_WAITING, player_id=player_id, payload={"value": bool(value)})


def _next_phase_cmd(game, *, player_id: str | None = None):
    from ...engine.command_kinds import CMD_NEXT_PHASE

    return _apply_game_command(game, CMD_NEXT_PHASE, player_id=player_id, payload={})


class PhaseEventHandler(Protocol):
    """Protocol for phase-specific event handlers"""
    def handle_event(self, event: pygame.event.Event, game_view: 'GameView') -> bool:
        """Handle pygame event for this phase. Returns True if event was consumed."""
        ...
    
    def get_allowed_actions(self) -> List[str]:
        """Get list of allowed actions for this phase"""
        ...

class BasePhaseHandler(ABC):
    """Base class for phase-specific event handlers"""
    
    def __init__(self, game_view: 'GameView'):
        self.game_view = game_view
        self.game = game_view.game
    
    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame event for this phase. Returns True if event was consumed."""
        pass
    
    @abstractmethod
    def get_allowed_actions(self) -> List[str]:
        """Get list of allowed actions for this phase"""
        pass
    
    def is_valid_action(self, action: str) -> bool:
        """Check if an action is valid for this phase"""
        return action in self.get_allowed_actions()

    def _current_player_has_control(self) -> bool:
        try:
            current_player = self.game.get_current_player()
        except Exception:
            return False
        if current_player is None:
            return False
        has_control = getattr(current_player, "has_control", None)
        if callable(has_control):
            return bool(has_control())
        return False

class SetupPhaseHandler(BasePhaseHandler):
    """Handles events during setup phases"""
    def __init__(self, game_view: 'GameView'):
        super().__init__(game_view)
        self._auto_declare_flow_started = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                if self._is_remote_game():
                    return True
                if not self._current_player_has_control():
                    return True
                # Handle setup phase advancement
                current_phase = self.game.get_current_setup_phase()
                
                # Check if we're in deployment phase and waiting for deployment input
                if (current_phase.name == 'DEPLOY_ARMIES' and 
                    hasattr(self.game, 'waiting_for_deployment_input') and 
                    self.game.waiting_for_deployment_input):
                    # Continue deployment
                    _set_deployment_waiting_cmd(self.game, False, player_id=_current_player_id(self.game))
                    return True
                
                # Execute the current setup phase
                setup_kwargs = {
                    'player1_army_file': None,  # These would come from game config
                    'player2_army_file': None,
                    'manual_phases': True
                }
                
                # For DEPLOY_ARMIES phase, handle based on local control
                if current_phase.name == 'DEPLOY_ARMIES':
                    has_local_players = any(getattr(player, "has_control", lambda: False)() for player in self.game.players)
                    if has_local_players:
                        setup_kwargs['manual_phases'] = True
                
                # Store which phase we're executing to know when to refresh UI
                current_phase_before = self.game.get_current_setup_phase()
                
                # Handle special phase-specific UI interactions
                if current_phase_before.name == 'SELECT_MISSION_OBJECTIVES':
                    # Show mission selection dialog
                    self._show_mission_selection_dialog()
                    return True  # Don't advance phase yet, wait for dialog

                if current_phase_before.name == 'DECLARE_BATTLE_FORMATIONS':
                    # Declare Battle Formations is a 3-step interactive flow:
                    # 1) Attach Leaders (both players confirm)
                    # 2) Embark in Transports (both players confirm)
                    # 3) Allocate Reserves (both players confirm)
                    self._start_declare_battle_formations_flow()
                    return True  # Don't advance phase yet, wait for dialog
                
                exec_result = _execute_setup_phase_cmd(self.game, player_id=_current_player_id(self.game), payload=setup_kwargs)
                adv_result = _advance_setup_phase_cmd(self.game, player_id=_current_player_id(self.game))
                setup_complete = bool(getattr(adv_result, "value", False)) if adv_result and getattr(adv_result, "ok", False) else False
                
                # Update UI after specific phases that change game state
                if current_phase_before.name == 'MUSTER_ARMIES':
                    # Armies were just loaded - refresh roster panes
                    self.game_view.refresh_roster_panes()
                    logger.info("UI updated after armies loaded")
                elif current_phase_before.name == 'DETERMINE_ATTACKER_AND_DEFENDER':
                    # Attacker/Defender roles determined - update titles
                    self.game_view.update_roster_pane_titles()
                    logger.info("UI updated after attacker/defender determined")
                
                if setup_complete:
                    # Final update after all setup phases complete
                    self.game_view.refresh_roster_panes()
                    self.game_view.update_roster_pane_titles()
                    logger.info("UI updated after setup completion")
                
                return True
        
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:  # Right click - show unit details
            hovered_unit, _ = self.game_view.get_hovered_unit(event.pos[0], event.pos[1])
            if hovered_unit:
                self.game_view.detailed_unit = hovered_unit
                self.game_view.detail_panel_pos = event.pos
                return True
        
        return False
    
    def _show_mission_selection_dialog(self):
        """Show the mission selection dialog for SELECT_MISSION_OBJECTIVES phase."""
        from ..dialogs import MissionSelectionDialog, MissionSelectionModal
        from ...utility.decision_utils import resolve_decision_command
        from ...engine.decision_kinds import DECISION_CHOOSE_MISSION

        def _pending_request():
            for req in list(self.game.decision_queue.list() or []):
                if getattr(req, "decision_type", None) == DECISION_CHOOSE_MISSION:
                    return req
            return None

        req = _pending_request()
        if req is None:
            logger.warning("Mission selection request missing from authoritative queue; dialog not opened.")
            return

        # Create mission selection dialog
        inner = MissionSelectionDialog(
            self.game_view.screen.get_width(),
            self.game_view.screen.get_height(),
        )

        modal = MissionSelectionModal(inner)
        self.game_view.mission_selection_dialog = modal  # keep reference for debugging

        def _apply_result(result: dict) -> None:
            combination = result.get("combination") or {}
            layout = result.get("layout")
            option_id = result.get("option_id", "")
            if not option_id:
                logger.error("ERROR: Mission selection option not found in decision options")
                return
            resolve_decision_command(self.game, req, option_id, result_payload={"layout": layout})
            logger.info(f"Mission selected: {combination.get('id')} - {combination.get('primary')} / {combination.get('deployment')} / Layout {layout}")

            # Execute the phase and advance
            _execute_setup_phase_cmd(self.game, player_id=_current_player_id(self.game), payload={})
            _advance_setup_phase_cmd(self.game, player_id=_current_player_id(self.game))

        def _cancel() -> None:
            logger.info("Mission selection cancelled - using default")
            if req.options:
                default_opt = req.options[0]
                combo = dict(getattr(default_opt, "payload", {}) or {}).get("combination", {})
                layouts = list(combo.get("layouts", []) or [])
                layout = layouts[0] if layouts else 1
                resolve_decision_command(self.game, req, default_opt.option_id, result_payload={"layout": layout})
            _execute_setup_phase_cmd(self.game, player_id=_current_player_id(self.game), payload={})
            _advance_setup_phase_cmd(self.game, player_id=_current_player_id(self.game))

        modal.show(on_confirm=_apply_result, on_cancel=_cancel, decision_request=req)
        # Push to modal stack
        try:
            self.game_view.dialog_manager.open(modal, modal=True)
        except Exception:
            pass

        logger.info("Mission Selection Dialog opened - choose from approved combinations A-T")

    def _show_leader_attachment_dialog(self):
        """Show the leader attachment dialog for DECLARE_BATTLE_FORMATIONS phase."""
        from ..dialogs import LeaderAttachmentDialog
        from ...engine.command_kinds import CMD_RESOLVE_DECISION
        from ...engine.commands import GameCommand
        from ...engine.decision_kinds import DECISION_ATTACH_LEADER

        dialog = LeaderAttachmentDialog(
            self.game_view.screen.get_width(),
            self.game_view.screen.get_height()
        )

        # Store dialog in game view for event handling
        self.game_view.leader_attachment_dialog = dialog

        def _on_done(selected_option_ids):
            for leader_id, option_id in (selected_option_ids or {}).items():
                req = leader_requests.get(leader_id)
                if req is None:
                    continue
                payload = {
                    "decision_id": req.decision_id,
                    "option_id": option_id,
                    "result_payload": {},
                }
                cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
                self.game.apply_command(cmd)
            # Apply/validate leader attachments, then proceed to transport assignments (then execute/advance)
            try:
                for p in self.game.players:
                    army = p.get_army()
                    if army:
                        army.validate_leaders()
            except Exception as e:
                logger.exception(f"  Leader attachment validation failed: {e}")
                return

            # Refresh roster panes so attached leaders collapse (once implemented)
            try:
                self.game_view.refresh_roster_panes()
            except Exception:
                pass

            # Next: declare which units start embarked within transports
            self._show_transport_assignment_dialog()

        def _on_cancel():
            # Stay in this phase; do nothing else
            return

        # Use player1's and player2's combined units for attachments (each leader can only attach within its army)
        all_units = []
        try:
            if self.game_view.player1 and self.game_view.player1.get_army():
                all_units.extend(self.game_view.player1.get_army().units)
            if self.game_view.player2 and self.game_view.player2.get_army():
                all_units.extend(self.game_view.player2.get_army().units)
        except Exception:
            pass

        pending = {
            str(getattr(req, "context", {}).get("leader_id", "")): req
            for req in list(self.game.decision_queue.list() or [])
            if getattr(req, "decision_type", None) == DECISION_ATTACH_LEADER
        }
        leader_requests = pending
        if not leader_requests:
            self._show_transport_assignment_dialog()
            return

        dialog.show(
            all_units,
            leader_requests=leader_requests,
            on_confirm=_on_done,
            on_cancel=_on_cancel,
        )
        dialog.visible = True
        try:
            self.game_view.dialog_manager.open(dialog, modal=True)
        except Exception:
            pass

        logger.info("Leader Attachment Dialog opened - select leaders and attach to eligible units")

    def _show_transport_assignment_dialog(self):
        """Show the transport assignment dialog for DECLARE_BATTLE_FORMATIONS phase."""
        from ..dialogs import TransportAssignmentDialog
        from ...engine.command_kinds import CMD_RESOLVE_DECISION
        from ...engine.commands import GameCommand
        from ...engine.decision_kinds import DECISION_ASSIGN_TRANSPORT

        dialog = TransportAssignmentDialog(
            self.game_view.screen.get_width(),
            self.game_view.screen.get_height()
        )
        self.game_view.transport_assignment_dialog = dialog

        # Use both armies' units; the dialog filters passengers by transport.can_transport()
        all_units = []
        try:
            if self.game_view.player1 and self.game_view.player1.get_army():
                all_units.extend(self.game_view.player1.get_army().units)
            if self.game_view.player2 and self.game_view.player2.get_army():
                all_units.extend(self.game_view.player2.get_army().units)
        except Exception:
            pass

        def _apply(selected_option_ids):
            for unit_id, option_id in (selected_option_ids or {}).items():
                req = unit_requests.get(unit_id)
                if req is None:
                    continue
                payload = {
                    "decision_id": req.decision_id,
                    "option_id": option_id,
                    "result_payload": {},
                }
                cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
                self.game.apply_command(cmd)

            # Execute the phase and advance
            _execute_setup_phase_cmd(self.game, player_id=_current_player_id(self.game), payload={})
            _advance_setup_phase_cmd(self.game, player_id=_current_player_id(self.game))

        def _skip():
            # Execute the phase and advance without changing transport assignments
            for unit_id, req in (unit_requests or {}).items():
                default_id = ""
                for opt in list(getattr(req, "options", []) or []):
                    payload = dict(getattr(opt, "payload", {}) or {})
                    if payload.get("transport_id") is None:
                        default_id = opt.option_id
                        break
                if not default_id:
                    continue
                payload = {
                    "decision_id": req.decision_id,
                    "option_id": default_id,
                    "result_payload": {},
                }
                cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
                self.game.apply_command(cmd)
            _execute_setup_phase_cmd(self.game, player_id=_current_player_id(self.game), payload={})
            _advance_setup_phase_cmd(self.game, player_id=_current_player_id(self.game))

        pending = {
            str(getattr(req, "context", {}).get("unit_id", "")): req
            for req in list(self.game.decision_queue.list() or [])
            if getattr(req, "decision_type", None) == DECISION_ASSIGN_TRANSPORT
        }
        unit_requests = pending
        if not unit_requests:
            _execute_setup_phase_cmd(self.game, player_id=_current_player_id(self.game), payload={})
            _advance_setup_phase_cmd(self.game, player_id=_current_player_id(self.game))
            return

        dialog.show(all_units, unit_requests=unit_requests, on_confirm=_apply, on_cancel=_skip)
        dialog.visible = True
        try:
            self.game_view.dialog_manager.open(dialog, modal=True)
        except Exception:
            pass

        logger.info("Transport Assignment Dialog opened - select transports and units to start embarked")

    def _show_shadow_assignment_dialog(self, *, players=None, on_done=None) -> None:
        """Show SHADOW ASSIGNMENT replacement prompts for eligible Imperial Agents assassins."""
        from ..dialogs import QuarrySelectionDialog
        from ...engine.command_kinds import CMD_RESOLVE_DECISION
        from ...engine.commands import GameCommand
        from ...engine.decision_kinds import DECISION_SHADOW_ASSIGNMENT
        from ..decision_ui_utils import first_option_id

        selected_players = [p for p in list(players or self.game.players or []) if p is not None]
        selected_player_ids = {str(getattr(p, "id", "") or "") for p in selected_players}
        all_units = []
        for player in selected_players:
            army = player.get_army()
            if army is None:
                continue
            all_units.extend(list(getattr(army, "units", []) or []))

        queue = getattr(self.game, "decision_queue", None)
        pending = []
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_SHADOW_ASSIGNMENT:
                    continue
                req_player_id = str(getattr(req, "player_id", "") or "")
                if selected_player_ids and req_player_id not in selected_player_ids:
                    continue
                pending.append(req)
        if not pending:
            if callable(on_done):
                on_done()
            return

        pending.sort(
            key=lambda req: (
                str(getattr(req, "player_id", "") or ""),
                str(getattr(req, "context", {}).get("unit_id", "") or ""),
                str(getattr(req, "decision_id", "") or ""),
            )
        )

        def _skip_option_id(req) -> str:
            for opt in list(getattr(req, "options", []) or []):
                payload = dict(getattr(opt, "payload", {}) or {})
                action = str(payload.get("action", "") or "").strip().lower()
                replacement = payload.get("replacement_datasheet_id")
                if action == "skip" or replacement is None:
                    return opt.option_id
            return str(first_option_id(req) or "")

        def _resolve(req, option_id: str) -> None:
            if not option_id:
                return
            payload = {
                "decision_id": req.decision_id,
                "option_id": option_id,
                "result_payload": {},
            }
            cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
            self.game.apply_command(cmd)

        def _advance() -> None:
            if not pending:
                if callable(on_done):
                    on_done()
                return

            req = pending.pop(0)
            unit_id = str(getattr(req, "context", {}).get("unit_id", "") or "")
            registry = getattr(self.game, "entity_registry", None)
            unit = registry.get(unit_id, kind="unit") if registry is not None else None
            if unit is None:
                default_id = _skip_option_id(req)
                if default_id:
                    _resolve(req, default_id)
                _advance()
                return

            dialog = QuarrySelectionDialog(
                self.game_view.screen.get_width(),
                self.game_view.screen.get_height(),
            )
            self.game_view.shadow_assignment_dialog = dialog
            title = f"Shadow Assignment - {getattr(unit, 'name', 'Assassin')}"
            header = "Select a replacement OFFICIO ASSASSINORUM model or choose None."
            subtitle = "Replacement must not exceed current points and cannot create duplicate assassin names."

            def _on_confirm(option_id: str):
                _resolve(req, option_id)
                try:
                    self.game_view.refresh_roster_panes()
                except Exception:
                    pass
                _advance()

            def _on_cancel():
                default_id = _skip_option_id(req)
                if default_id:
                    _resolve(req, default_id)
                    try:
                        self.game_view.refresh_roster_panes()
                    except Exception:
                        pass
                _advance()

            dialog.show(
                title=title,
                header=header,
                subtitle=subtitle,
                on_confirm=_on_confirm,
                on_cancel=_on_cancel,
                decision_request=req,
                show_cancel=True,
            )
            try:
                self.game_view.dialog_manager.open(dialog, modal=True)
            except Exception:
                _on_cancel()

        _advance()

    def _start_player_color_selection_flow(self, players, on_done) -> None:
        """Prompt local players to choose a UI color before setup interaction dialogs."""
        from ...engine.decision_kinds import DECISION_CHOOSE_PLAYER_COLOR

        queue = getattr(self.game, "decision_queue", None)
        pending_requests = []

        for player in list(players or []):
            if player is None:
                continue
            has_control_fn = getattr(player, "has_control", None)
            if not callable(has_control_fn) or not bool(has_control_fn()):
                continue
            player_id = str(getattr(player, "id", "") or "")
            if not player_id:
                continue

            request = None
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if getattr(req, "decision_type", None) != DECISION_CHOOSE_PLAYER_COLOR:
                        continue
                    if str(getattr(req, "player_id", "") or "") == player_id:
                        request = req
                        break

            if request is not None:
                pending_requests.append((player, request))

        self._pending_player_color_queue = pending_requests
        self._player_color_on_done = on_done

        if not pending_requests:
            self._finish_player_color_selection()
            return

        self._open_next_player_color_prompt()

    def _finish_player_color_selection(self) -> None:
        callback = getattr(self, "_player_color_on_done", None)
        self._player_color_on_done = None
        if callable(callback):
            callback()

    def _open_next_player_color_prompt(self) -> None:
        queue = list(getattr(self, "_pending_player_color_queue", []) or [])
        if not queue:
            self._pending_player_color_queue = []
            self._finish_player_color_selection()
            return

        from ...utility.decision_utils import resolve_decision_command
        from ..decision_ui_utils import first_option_id
        from ..dialogs import PlayerColorPickerDialog

        player, request = queue.pop(0)
        self._pending_player_color_queue = queue

        dialog = getattr(self.game_view, "player_color_picker_dialog", None)
        if dialog is None:
            dialog = PlayerColorPickerDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
            self.game_view.player_color_picker_dialog = dialog

        player_name = str(getattr(player, "name", "Player") or "Player")
        initial_hue = getattr(player, "ui_color_hue_degrees", None)
        initial_rgb = None
        get_rgb = getattr(player, "get_ui_color_rgb", None)
        if callable(get_rgb):
            initial_rgb = get_rgb()
        else:
            raw_rgb = getattr(player, "ui_color_rgb", None)
            if isinstance(raw_rgb, (list, tuple)) and len(raw_rgb) == 3:
                initial_rgb = (int(raw_rgb[0]), int(raw_rgb[1]), int(raw_rgb[2]))

        def _on_confirm(option_id: str) -> None:
            resolve_decision_command(
                self.game,
                request,
                option_id,
                player_id=getattr(player, "id", None),
            )
            self._open_next_player_color_prompt()

        def _on_cancel() -> None:
            fallback = first_option_id(request)
            if fallback:
                resolve_decision_command(
                    self.game,
                    request,
                    fallback,
                    player_id=getattr(player, "id", None),
                )
            self._open_next_player_color_prompt()

        dialog.show(
            player_name=player_name,
            on_confirm=_on_confirm,
            on_cancel=_on_cancel,
            decision_request=request,
            initial_hue_degrees=initial_hue,
            initial_rgb=initial_rgb,
        )
        self.game_view.dialog_manager.open(dialog, modal=True)

    def _start_hover_mode_selection_flow(self, players, on_done) -> None:
        """Prompt local players to choose Hover mode for eligible AIRCRAFT before formations dialogs."""
        queue = []
        for player in list(players or []):
            try:
                if player is None or not getattr(player, "has_control", lambda: False)():
                    continue
            except Exception:
                continue
            try:
                army = player.get_army()
            except Exception:
                army = None
            if army is None:
                continue
            for unit in list(getattr(army, "units", []) or []):
                try:
                    if bool(getattr(unit, "hover_declared", False)):
                        continue
                except Exception:
                    pass
                try:
                    if not bool(getattr(unit, "has_hover", lambda: False)()):
                        continue
                except Exception:
                    continue
                try:
                    if not bool(getattr(unit, "has_keyword", lambda *_a, **_k: False)("Aircraft")):
                        continue
                except Exception:
                    continue
                queue.append((player, unit))

        self._pending_hover_mode_queue = queue
        self._hover_mode_on_done = on_done

        if not queue:
            self._finish_hover_mode_selection()
            return

        self._open_next_hover_mode_prompt()

    def _finish_hover_mode_selection(self) -> None:
        """Finalize Hover mode selection."""
        cb = getattr(self, "_hover_mode_on_done", None)
        self._hover_mode_on_done = None
        if callable(cb):
            try:
                cb()
            except Exception:
                pass

    def _open_next_hover_mode_prompt(self) -> None:
        q = list(getattr(self, "_pending_hover_mode_queue", []) or [])
        if not q:
            self._pending_hover_mode_queue = []
            self._finish_hover_mode_selection()
            return

        player, unit = q.pop(0)
        self._pending_hover_mode_queue = q

        title = "Hover Mode"
        pname = getattr(player, "name", "Player")
        uname = getattr(unit, "name", "Unit")
        msg = (
            f"Enable Hover mode for {uname} ({pname})?\n\n"
            "Hover removes the AIRCRAFT keyword and sets Move to 20\"."
        )
        try:
            from ...utility.entity_ids import get_entity_id
            unit_id = get_entity_id(unit)
        except Exception:
            unit_id = ""

        def _advance(_chosen: bool):
            self._open_next_hover_mode_prompt()

        if callable(getattr(self, "_request_yes_no", None)):
            ctx = {"ability": "hover_mode", "unit_id": unit_id}
            self._request_yes_no(title, msg, "Hover", "Aircraft", _advance, player=player, context=ctx)
        else:
            try:
                def _fallback(chosen: bool):
                    try:
                        unit.set_hover_mode(bool(chosen))
                    except Exception:
                        pass
                    try:
                        unit.hover_declared = True
                    except Exception:
                        pass
                    self._open_next_hover_mode_prompt()

                self.yes_no_dialog.show(title, msg, _fallback, yes_label="Hover", no_label="Aircraft")
                self.dialog_manager.open(self.yes_no_dialog, modal=True)
            except Exception:
                _advance(False)

    def _start_patrol_squad_selection_flow(self, players, on_done) -> None:
        """Prompt local players for PATROL SQUAD split choices before formations dialogs."""
        from ...engine.decision_kinds import DECISION_CONFIRM_YES_NO

        local_players = []
        for player in list(players or []):
            try:
                if player is not None and bool(getattr(player, "has_control", lambda: False)()):
                    local_players.append(player)
            except Exception:
                continue

        local_player_ids = {str(getattr(player, "id", "") or "") for player in local_players}
        queue = getattr(self.game, "decision_queue", None)
        pending: list = []
        if queue is not None and hasattr(queue, "list"):
            for req in list(queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_CONFIRM_YES_NO:
                    continue
                if str(getattr(req, "player_id", "") or "") not in local_player_ids:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "patrol_squad":
                    continue
                pending.append(req)

        requests = list(pending)

        requests.sort(
            key=lambda req: (
                str(getattr(req, "player_id", "") or ""),
                str(getattr(req, "context", {}).get("unit_id", "") or ""),
                str(getattr(req, "decision_id", "") or ""),
            )
        )
        self._pending_patrol_squad_queue = list(requests)
        self._patrol_squad_on_done = on_done
        if not requests:
            self._finish_patrol_squad_selection()
            return
        self._open_next_patrol_squad_prompt()

    def _finish_patrol_squad_selection(self) -> None:
        cb = getattr(self, "_patrol_squad_on_done", None)
        self._patrol_squad_on_done = None
        if callable(cb):
            try:
                cb()
            except Exception:
                pass

    def _open_next_patrol_squad_prompt(self) -> None:
        queue = list(getattr(self, "_pending_patrol_squad_queue", []) or [])
        if not queue:
            self._pending_patrol_squad_queue = []
            self._finish_patrol_squad_selection()
            return

        request = queue.pop(0)
        self._pending_patrol_squad_queue = queue
        ctx = dict(getattr(request, "context", {}) or {})
        title = str(getattr(request, "prompt", "") or "Patrol Squad")
        message = str(ctx.get("message", "") or "")
        if not message:
            message = "Split this unit into two units of five models each?"

        from ...utility.decision_utils import resolve_decision_command
        from ..decision_ui_utils import first_option_id

        def _done(option_id: str):
            choice_id = str(option_id or "")
            if not choice_id:
                for option in list(getattr(request, "options", []) or []):
                    payload = dict(getattr(option, "payload", {}) or {})
                    if payload.get("choice") is False:
                        choice_id = str(getattr(option, "option_id", "") or "")
                        break
            if not choice_id:
                choice_id = str(first_option_id(request) or "")
            if choice_id:
                resolve_decision_command(self.game, request, choice_id)
            try:
                self.game_view.refresh_roster_panes()
            except Exception:
                pass
            self._open_next_patrol_squad_prompt()

        dialog = getattr(self.game_view, "yes_no_dialog", None)
        if dialog is None:
            self._open_next_patrol_squad_prompt()
            return
        try:
            dialog.show(title, message, _done, decision_request=request)
            self.game_view.dialog_manager.open(dialog, modal=True)
        except Exception:
            _done("")

    def _start_declare_battle_formations_flow(self) -> None:
        """
        Run Declare Battle Formations as simultaneous per-player dialogs:
        - Leaders (P1 + P2 at once) -> Transports (P1 + P2 at once) -> Reserves (P1 + P2 at once)
        Only after BOTH players click Done do we proceed to the next step.
        """
        if self._is_remote_game():
            self._start_remote_declare_battle_formations_flow()
            return
        players = list(getattr(self.game, "players", []) or [])
        if not players:
            # Fallback: execute and advance (no UI)
            _execute_setup_phase_cmd(self.game, player_id=_current_player_id(self.game), payload={})
            _advance_setup_phase_cmd(self.game, player_id=_current_player_id(self.game))
            return

        def _after_hover():
            def _army_units(p):
                try:
                    a = p.get_army()
                    return list(getattr(a, "units", []) or [])
                except Exception:
                    return []

            if len(players) != 2:
                logger.info("  Side-by-side formations UI currently supports exactly 2 players; falling back to sequential flow.")
                # Keep existing behavior by running as two sequential dialogs (old implementation).
                # (We intentionally do not duplicate the old nested functions here.)
                try:
                    self._show_shadow_assignment_dialog(on_done=self._show_leader_attachment_dialog)
                    return
                except Exception:
                    _execute_setup_phase_cmd(self.game, player_id=_current_player_id(self.game), payload={})
                    _advance_setup_phase_cmd(self.game, player_id=_current_player_id(self.game))
                    return

            p_left, p_right = players[0], players[1]
            a_left, a_right = p_left.get_army(), p_right.get_army()
            if a_left is None or a_right is None:
                _execute_setup_phase_cmd(self.game, player_id=_current_player_id(self.game), payload={})
                _advance_setup_phase_cmd(self.game, player_id=_current_player_id(self.game))
                return

            from ..dialogs.side_by_side_modal import SideBySideModal

            def _position_two(left_dlg, right_dlg) -> None:
                # Place near left/right edges; allow overlap if screen is narrow (dialogs are draggable)
                margin = 12
                left_dlg.x = margin
                left_dlg.y = 60
                try:
                    left_dlg._update_title_bar()
                    left_dlg._update_buttons()
                except Exception:
                    pass
                right_dlg.x = max(margin, self.game_view.screen.get_width() - right_dlg.width - margin)
                right_dlg.y = 60
                try:
                    right_dlg._update_title_bar()
                    right_dlg._update_buttons()
                except Exception:
                    pass

            # Shared helpers
            def _mark_attached_leaders_handled(army) -> None:
                try:
                    for u in list(getattr(army, "units", []) or []):
                        if bool(getattr(u, "is_attached_leader", False)):
                            u.deployed = True
                        if bool(getattr(u, "is_joined_support", False)):
                            u.deployed = True
                except Exception:
                    pass

            def _apply_transport_assignments(army, units, assignments) -> bool:
                return bool(self.game.apply_transport_assignments(army, units, assignments))

            def _show_leaders():
                # Step 1: Leaders (both at once)
                from ..dialogs import LeaderAttachmentDialog
                from ...engine.command_kinds import CMD_RESOLVE_DECISION
                from ...engine.commands import GameCommand
                from ...engine.decision_kinds import DECISION_ATTACH_LEADER
                left_leaders = LeaderAttachmentDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
                right_leaders = LeaderAttachmentDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
                left_leaders.title = f"Attach Leaders - {p_left.name}"
                right_leaders.title = f"Attach Leaders - {p_right.name}"

                modal = SideBySideModal(self.game_view.screen.get_width(), self.game_view.screen.get_height(), left_leaders, right_leaders)
                _position_two(left_leaders, right_leaders)

                def _maybe_advance_from_leaders():
                    if modal.left_done and modal.right_done:
                        try:
                            self.game_view.refresh_roster_panes()
                        except Exception:
                            pass
                        modal.hide()
                        _show_support_artillery()

                def _left_done(selected_option_ids):
                    for leader_id, option_id in (selected_option_ids or {}).items():
                        req = l_requests.get(leader_id)
                        if req is None:
                            continue
                        payload = {
                            "decision_id": req.decision_id,
                            "option_id": option_id,
                            "result_payload": {},
                        }
                        cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
                        self.game.apply_command(cmd)
                    try:
                        a_left.validate_leaders()
                    except Exception as e:
                        logger.exception(f"  {p_left.name} leader attachment validation failed: {e}")
                        return
                    _mark_attached_leaders_handled(a_left)
                    modal.left_done = True
                    _maybe_advance_from_leaders()

                def _right_done(selected_option_ids):
                    for leader_id, option_id in (selected_option_ids or {}).items():
                        req = r_requests.get(leader_id)
                        if req is None:
                            continue
                        payload = {
                            "decision_id": req.decision_id,
                            "option_id": option_id,
                            "result_payload": {},
                        }
                        cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
                        self.game.apply_command(cmd)
                    try:
                        a_right.validate_leaders()
                    except Exception as e:
                        logger.exception(f"  {p_right.name} leader attachment validation failed: {e}")
                        return
                    _mark_attached_leaders_handled(a_right)
                    modal.right_done = True
                    _maybe_advance_from_leaders()

                pending = {
                    str(getattr(req, "context", {}).get("leader_id", "")): req
                    for req in list(self.game.decision_queue.list() or [])
                    if getattr(req, "decision_type", None) == DECISION_ATTACH_LEADER
                }
                l_units = _army_units(p_left)
                r_units = _army_units(p_right)
                from ...utility.entity_ids import get_entity_id
                l_ids = {get_entity_id(u) for u in l_units}
                r_ids = {get_entity_id(u) for u in r_units}
                l_requests = {lid: req for lid, req in pending.items() if lid in l_ids}
                r_requests = {rid: req for rid, req in pending.items() if rid in r_ids}
                if not l_requests and not r_requests:
                    _show_support_artillery()
                    return

                left_leaders.show(
                    l_units,
                    leader_requests=l_requests,
                    on_confirm=_left_done,
                    on_cancel=lambda: None,
                )
                right_leaders.show(
                    r_units,
                    leader_requests=r_requests,
                    on_confirm=_right_done,
                    on_cancel=lambda: None,
                )

                modal.show()
                try:
                    self.game_view.dialog_manager.open(modal, modal=True)
                except Exception:
                    pass

            def _show_support_artillery():
                # Step 2: Support Artillery joins (both at once)
                from ..dialogs import LeaderAttachmentDialog
                from ...engine.command_kinds import CMD_RESOLVE_DECISION
                from ...engine.commands import GameCommand
                from ...engine.decision_kinds import DECISION_ATTACH_SUPPORT_ARTILLERY

                left_support = LeaderAttachmentDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
                right_support = LeaderAttachmentDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
                left_support.title = f"Attach Joined Support Units - {p_left.name}"
                right_support.title = f"Attach Joined Support Units - {p_right.name}"

                modal = SideBySideModal(self.game_view.screen.get_width(), self.game_view.screen.get_height(), left_support, right_support)
                _position_two(left_support, right_support)

                def _maybe_advance_from_support():
                    if modal.left_done and modal.right_done:
                        try:
                            self.game_view.refresh_roster_panes()
                        except Exception:
                            pass
                        modal.hide()
                        _show_transports()

                def _left_done(selected_option_ids):
                    for support_id, option_id in (selected_option_ids or {}).items():
                        req = l_requests.get(support_id)
                        if req is None:
                            continue
                        payload = {
                            "decision_id": req.decision_id,
                            "option_id": option_id,
                            "result_payload": {},
                        }
                        cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
                        self.game.apply_command(cmd)
                    try:
                        a_left.validate_support_artillery()
                    except Exception as e:
                        logger.exception(f"  {p_left.name} joined support validation failed: {e}")
                        return
                    _mark_attached_leaders_handled(a_left)
                    modal.left_done = True
                    _maybe_advance_from_support()

                def _right_done(selected_option_ids):
                    for support_id, option_id in (selected_option_ids or {}).items():
                        req = r_requests.get(support_id)
                        if req is None:
                            continue
                        payload = {
                            "decision_id": req.decision_id,
                            "option_id": option_id,
                            "result_payload": {},
                        }
                        cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
                        self.game.apply_command(cmd)
                    try:
                        a_right.validate_support_artillery()
                    except Exception as e:
                        logger.exception(f"  {p_right.name} joined support validation failed: {e}")
                        return
                    _mark_attached_leaders_handled(a_right)
                    modal.right_done = True
                    _maybe_advance_from_support()

                pending = {
                    str(getattr(req, "context", {}).get("support_unit_id", "")): req
                    for req in list(self.game.decision_queue.list() or [])
                    if getattr(req, "decision_type", None) == DECISION_ATTACH_SUPPORT_ARTILLERY
                }
                l_units = _army_units(p_left)
                r_units = _army_units(p_right)
                from ...utility.entity_ids import get_entity_id
                l_ids = {get_entity_id(u) for u in l_units}
                r_ids = {get_entity_id(u) for u in r_units}
                l_requests = {uid: req for uid, req in pending.items() if uid in l_ids}
                r_requests = {uid: req for uid, req in pending.items() if uid in r_ids}

                if not l_requests and not r_requests:
                    _show_transports()
                    return

                def _support_units(units):
                    return [u for u in units if bool(getattr(u, "has_joined_support_ability", lambda: False)())]

                def _bodyguard_units(units):
                    return [
                        u for u in units
                        if not bool(getattr(u, "is_leader", False))
                        and not bool(getattr(u, "is_joined_support", False))
                    ]

                left_support.show(
                    l_units,
                    leaders=_support_units(l_units),
                    bodyguards=_bodyguard_units(l_units),
                    leader_requests=l_requests,
                    on_confirm=_left_done,
                    on_cancel=lambda: None,
                    title=f"Attach Joined Support Units - {p_left.name}",
                    subtitle="Select a support/retinue unit, then choose an eligible bodyguard unit (or Unattached).",
                    left_label="Support/Retinue Units",
                    right_label="Bodyguard Units",
                )
                right_support.show(
                    r_units,
                    leaders=_support_units(r_units),
                    bodyguards=_bodyguard_units(r_units),
                    leader_requests=r_requests,
                    on_confirm=_right_done,
                    on_cancel=lambda: None,
                    title=f"Attach Joined Support Units - {p_right.name}",
                    subtitle="Select a support/retinue unit, then choose an eligible bodyguard unit (or Unattached).",
                    left_label="Support/Retinue Units",
                    right_label="Bodyguard Units",
                )

                modal.show()
                try:
                    self.game_view.dialog_manager.open(modal, modal=True)
                except Exception:
                    pass

            def _show_transports():
                from ..dialogs import TransportAssignmentDialog
                from ...engine.command_kinds import CMD_RESOLVE_DECISION
                from ...engine.commands import GameCommand
                from ...engine.decision_kinds import DECISION_ASSIGN_TRANSPORT
                ldlg = TransportAssignmentDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
                rdlg = TransportAssignmentDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
                ldlg.title = f"Transports - {p_left.name}"
                rdlg.title = f"Transports - {p_right.name}"

                m = SideBySideModal(self.game_view.screen.get_width(), self.game_view.screen.get_height(), ldlg, rdlg)
                _position_two(ldlg, rdlg)

                units_l = _army_units(p_left)
                units_r = _army_units(p_right)

                def _maybe_advance():
                    if m.left_done and m.right_done:
                        try:
                            self.game_view.refresh_roster_panes()
                        except Exception:
                            pass
                        m.hide()
                        _show_reserves()

                def _l_done(selected_option_ids):
                    for unit_id, option_id in (selected_option_ids or {}).items():
                        req = l_requests.get(unit_id)
                        if req is None:
                            continue
                        payload = {
                            "decision_id": req.decision_id,
                            "option_id": option_id,
                            "result_payload": {},
                        }
                        cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
                        self.game.apply_command(cmd)
                    m.left_done = True
                    _maybe_advance()

                def _r_done(selected_option_ids):
                    for unit_id, option_id in (selected_option_ids or {}).items():
                        req = r_requests.get(unit_id)
                        if req is None:
                            continue
                        payload = {
                            "decision_id": req.decision_id,
                            "option_id": option_id,
                            "result_payload": {},
                        }
                        cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
                        self.game.apply_command(cmd)
                    m.right_done = True
                    _maybe_advance()

                pending = {
                    str(getattr(req, "context", {}).get("unit_id", "")): req
                    for req in list(self.game.decision_queue.list() or [])
                    if getattr(req, "decision_type", None) == DECISION_ASSIGN_TRANSPORT
                }
                from ...utility.entity_ids import get_entity_id

                l_ids = {get_entity_id(u) for u in units_l}
                r_ids = {get_entity_id(u) for u in units_r}
                l_requests = {uid: req for uid, req in pending.items() if uid in l_ids}
                r_requests = {uid: req for uid, req in pending.items() if uid in r_ids}
                if not l_requests and not r_requests:
                    _show_reserves()
                    return

                ldlg.show(units_l, unit_requests=l_requests, on_confirm=_l_done, on_cancel=lambda: None)
                rdlg.show(units_r, unit_requests=r_requests, on_confirm=_r_done, on_cancel=lambda: None)
                m.show()
                try:
                    self.game_view.dialog_manager.open(m, modal=True)
                except Exception:
                    pass

            def _show_reserves():
                from ..dialogs import ReservesAllocationDialog
                from ...engine.decision_kinds import DECISION_DECLARE_RESERVES
                from ...utility.decision_utils import resolve_decision_command
                ldlg = ReservesAllocationDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
                rdlg = ReservesAllocationDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
                ldlg.title = f"Allocate Reserves - {p_left.name}"
                rdlg.title = f"Allocate Reserves - {p_right.name}"

                m = SideBySideModal(self.game_view.screen.get_width(), self.game_view.screen.get_height(), ldlg, rdlg)
                _position_two(ldlg, rdlg)

                def _maybe_advance():
                    if m.left_done and m.right_done:
                        m.hide()
                        # Execute phase logic (validations) and advance setup phase.
                        _execute_setup_phase_cmd(self.game, player_id=_current_player_id(self.game), payload={})
                        _advance_setup_phase_cmd(self.game, player_id=_current_player_id(self.game))
                        try:
                            self.game_view.refresh_roster_panes()
                        except Exception:
                            pass

                def _l_done(option_id, buckets):
                    if l_request is not None:
                        resolve_decision_command(self.game, l_request, option_id, result_payload={"unit_ids_by_bucket": buckets})
                    m.left_done = True
                    _maybe_advance()

                def _r_done(option_id, buckets):
                    if r_request is not None:
                        resolve_decision_command(self.game, r_request, option_id, result_payload={"unit_ids_by_bucket": buckets})
                    m.right_done = True
                    _maybe_advance()

                pending = [
                    req for req in list(self.game.decision_queue.list() or [])
                    if getattr(req, "decision_type", None) == DECISION_DECLARE_RESERVES
                ]
                l_request = next((req for req in pending if req.player_id == p_left.id), None)
                r_request = next((req for req in pending if req.player_id == p_right.id), None)
                if l_request is None and r_request is None:
                    _execute_setup_phase_cmd(self.game, player_id=_current_player_id(self.game), payload={})
                    _advance_setup_phase_cmd(self.game, player_id=_current_player_id(self.game))
                    try:
                        self.game_view.refresh_roster_panes()
                    except Exception:
                        pass
                    return

                ldlg.show(a_left, on_confirm=_l_done, on_cancel=lambda: None, decision_request=l_request)
                rdlg.show(a_right, on_confirm=_r_done, on_cancel=lambda: None, decision_request=r_request)
                m.show()
                try:
                    self.game_view.dialog_manager.open(m, modal=True)
                except Exception:
                    pass

            def _refresh_army_rule_panel(player_obj) -> None:
                try:
                    if self.game_view.rule_detail_panel and self.game_view.rule_detail_panel.visible and isinstance(self.game_view._rule_panel_state, dict):
                        state = self.game_view._rule_panel_state
                        if state.get("player") is player_obj and state.get("rule_type") == "army":
                            self.game_view._toggle_rule_panel(player_obj, "army", force_refresh=True)
                except Exception:
                    pass

            def _show_shadow_assignments():
                self._show_shadow_assignment_dialog(
                    players=[p_left, p_right],
                    on_done=_show_leaders,
                )

            def _needs_plague_selection(player_obj) -> bool:
                try:
                    army = player_obj.get_army()
                except Exception:
                    army = None
                if army is None:
                    return False
                try:
                    mgr = getattr(army, "nurgles_gift", None)
                except Exception:
                    mgr = None
                if mgr is None:
                    return False
                if not getattr(mgr, "_army_has_gift", lambda: False)():
                    return False
                if getattr(mgr, "active_plague_key", None):
                    return False
                return True

            def _show_plague_selection():
                needs_left = _needs_plague_selection(p_left)
                needs_right = _needs_plague_selection(p_right)
                if not (needs_left or needs_right):
                    _show_shadow_assignments()
                    return

                from ..dialogs import NurglesGiftPlagueDialog
                from ...engine.decision_kinds import DECISION_CHOOSE_PLAGUE
                from ...engine.decisions import DecisionOption, DecisionRequest
                from ...utility.decision_utils import resolve_decision_value
                from ...utility.entity_ids import get_entity_id
                from ..decision_ui_utils import first_option_id

                try:
                    from ...rules.nurgles_gift import DEFAULT_PLAGUES
                    options = list(DEFAULT_PLAGUES)
                except Exception:
                    options = []

                def _plague_request(player, army):
                    army_id = get_entity_id(army)
                    pending = [
                        req for req in list(self.game.decision_queue.list() or [])
                        if getattr(req, "decision_type", None) == DECISION_CHOOSE_PLAGUE
                        and str(getattr(req, "context", {}).get("army_id", "")) == army_id
                    ]
                    if pending:
                        return pending[0]
                    req_options = []
                    for plague in options:
                        key = getattr(plague, "key", None)
                        if not key:
                            continue
                        name = getattr(plague, "name", None) or str(plague)
                        summary = getattr(plague, "summary", "") or getattr(plague, "effect", "")
                        req_options.append(
                            DecisionOption.create(
                                name,
                                payload={"choice_key": str(key), "summary": summary, "army_id": army_id},
                            )
                        )
                    if not req_options:
                        return None
                    req = _require_pending_decision_request(self.game,
                        DECISION_CHOOSE_PLAGUE,
                        "Nurgle's Gift: select one Plague.",
                        player_id=getattr(player, "id", None),
                        options=req_options,
                        context={
                            "ability": "nurgles_gift_declare",
                            "ability_name": "Nurgle's Gift",
                            "army_id": army_id,
                            "optional": False,
                        },

                    )
                    return req

                if needs_left and needs_right:
                    ldlg = NurglesGiftPlagueDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
                    rdlg = NurglesGiftPlagueDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
                    ldlg.title = f"Nurgle's Gift - {p_left.name}"
                    rdlg.title = f"Nurgle's Gift - {p_right.name}"

                    m = SideBySideModal(self.game_view.screen.get_width(), self.game_view.screen.get_height(), ldlg, rdlg)
                    _position_two(ldlg, rdlg)

                    def _maybe_advance():
                        if m.left_done and m.right_done:
                            m.hide()
                            _show_shadow_assignments()

                    l_request = _plague_request(p_left, a_left)
                    r_request = _plague_request(p_right, a_right)
                    if l_request is None or r_request is None:
                        _show_shadow_assignments()
                        return

                    def _l_done(option_id: str):
                        resolve_decision_value(self.game, l_request, option_id)
                        _refresh_army_rule_panel(p_left)
                        m.left_done = True
                        _maybe_advance()

                    def _r_done(option_id: str):
                        resolve_decision_value(self.game, r_request, option_id)
                        _refresh_army_rule_panel(p_right)
                        m.right_done = True
                        _maybe_advance()

                    def _l_cancel():
                        default_id = first_option_id(l_request)
                        if default_id:
                            resolve_decision_value(self.game, l_request, default_id)
                            _refresh_army_rule_panel(p_left)
                        m.left_done = True
                        _maybe_advance()

                    def _r_cancel():
                        default_id = first_option_id(r_request)
                        if default_id:
                            resolve_decision_value(self.game, r_request, default_id)
                            _refresh_army_rule_panel(p_right)
                        m.right_done = True
                        _maybe_advance()

                    ldlg.show(on_confirm=_l_done, on_cancel=_l_cancel, decision_request=l_request)
                    rdlg.show(on_confirm=_r_done, on_cancel=_r_cancel, decision_request=r_request)
                    m.show()
                    try:
                        self.game_view.dialog_manager.open(m, modal=True)
                    except Exception:
                        pass
                    return

                dlg = NurglesGiftPlagueDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
                if needs_left:
                    dlg.title = f"Nurgle's Gift - {p_left.name}"
                    target_player = p_left
                    target_army = a_left
                else:
                    dlg.title = f"Nurgle's Gift - {p_right.name}"
                    target_player = p_right
                    target_army = a_right

                target_request = _plague_request(target_player, target_army)
                if target_request is None:
                    _show_shadow_assignments()
                    return

                def _done(option_id: str):
                    resolve_decision_value(self.game, target_request, option_id)
                    _refresh_army_rule_panel(target_player)
                    _show_shadow_assignments()

                def _cancel():
                    default_id = first_option_id(target_request)
                    if default_id:
                        resolve_decision_value(self.game, target_request, default_id)
                        _refresh_army_rule_panel(target_player)
                    _show_shadow_assignments()

                dlg.show(on_confirm=_done, on_cancel=_cancel, decision_request=target_request)
                try:
                    self.game_view.dialog_manager.open(dlg, modal=True)
                except Exception:
                    pass

            _show_plague_selection()

    

        def _after_player_colors():
            self._start_hover_mode_selection_flow(
                players,
                lambda: self._start_patrol_squad_selection_flow(players, _after_hover),
            )

        self._start_player_color_selection_flow(players, _after_player_colors)
        return

    def _is_remote_game(self) -> bool:
        players = list(getattr(self.game, "players", []) or [])
        if not players:
            return False
        for player in players:
            try:
                if not bool(getattr(player, "has_control", lambda: False)()):
                    return True
            except Exception:
                return True
        return False

    def _get_local_player(self):
        for player in list(getattr(self.game, "players", []) or []):
            try:
                if bool(getattr(player, "has_control", lambda: False)()):
                    return player
            except Exception:
                continue
        return None

    def _has_pending_formation_decisions(self, player) -> bool:
        queue = getattr(self.game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return False
        from ...engine.decision_kinds import (
            DECISION_ATTACH_LEADER,
            DECISION_ASSIGN_TRANSPORT,
            DECISION_CHOOSE_PLAYER_COLOR,
            DECISION_DECLARE_RESERVES,
            DECISION_CHOOSE_PLAGUE,
            DECISION_SHADOW_ASSIGNMENT,
            DECISION_CONFIRM_YES_NO,
        )
        types = {
            DECISION_ATTACH_LEADER,
            DECISION_ASSIGN_TRANSPORT,
            DECISION_CHOOSE_PLAYER_COLOR,
            DECISION_DECLARE_RESERVES,
            DECISION_CHOOSE_PLAGUE,
            DECISION_SHADOW_ASSIGNMENT,
        }
        pid = getattr(player, "id", None)
        for req in list(queue.list() or []):
            decision_type = getattr(req, "decision_type", None)
            if decision_type not in types:
                if decision_type != DECISION_CONFIRM_YES_NO:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                ability = str(ctx.get("ability", "") or "")
                if ability not in ("hover_mode", "patrol_squad"):
                    continue
            req_pid = getattr(req, "player_id", None)
            if pid is None or req_pid is None or str(req_pid) == str(pid):
                return True
        return False

    def _formation_dialog_active(self) -> bool:
        for attr in (
            "player_color_picker_dialog",
            "shadow_assignment_dialog",
            "leader_attachment_dialog",
            "transport_assignment_dialog",
            "reserves_allocation_dialog",
        ):
            dlg = getattr(self.game_view, attr, None)
            try:
                if dlg is not None and bool(getattr(dlg, "visible", False)):
                    return True
            except Exception:
                continue
        return False

    def maybe_auto_start_setup_flow(self) -> None:
        if not self._is_remote_game():
            self._auto_declare_flow_started = False
            return
        if not bool(getattr(self.game, "is_in_setup_phase", lambda: False)()):
            self._auto_declare_flow_started = False
            return
        phase = self.game.get_current_setup_phase()
        if phase is None or phase.name != "DECLARE_BATTLE_FORMATIONS":
            self._auto_declare_flow_started = False
            return

        local_player = self._get_local_player()
        if local_player is None:
            return

        if self._auto_declare_flow_started:
            if (not self._formation_dialog_active()) and self._has_pending_formation_decisions(local_player):
                self._auto_declare_flow_started = False
            else:
                return

        if not self._has_pending_formation_decisions(local_player):
            return

        self._auto_declare_flow_started = True
        self._start_remote_declare_battle_formations_flow()

    def _start_remote_declare_battle_formations_flow(self) -> None:
        player = self._get_local_player()
        if player is None:
            return
        army = None
        try:
            army = player.get_army()
        except Exception:
            army = None
        if army is None:
            return
        units = list(getattr(army, "units", []) or [])

        from ..dialogs import (
            LeaderAttachmentDialog,
            NurglesGiftPlagueDialog,
            PlayerColorPickerDialog,
            ReservesAllocationDialog,
            TransportAssignmentDialog,
        )
        from ...engine.decision_kinds import (
            DECISION_ATTACH_LEADER,
            DECISION_ATTACH_SUPPORT_ARTILLERY,
            DECISION_ASSIGN_TRANSPORT,
            DECISION_CHOOSE_PLAYER_COLOR,
            DECISION_DECLARE_RESERVES,
            DECISION_CHOOSE_PLAGUE,
            DECISION_CONFIRM_YES_NO,
        )
        from ...engine.command_kinds import CMD_RESOLVE_DECISION
        from ...engine.commands import GameCommand
        from ...engine.decisions import DecisionOption, DecisionRequest
        from ...utility.decision_utils import resolve_decision_command, resolve_decision_value
        from ...utility.entity_ids import get_entity_id
        from ..decision_ui_utils import first_option_id

        queue = getattr(self.game, "decision_queue", None)
        unit_by_id = {get_entity_id(u): u for u in units if u is not None}

        def _refresh_units_cache() -> None:
            nonlocal units, unit_by_id
            units = list(getattr(army, "units", []) or [])
            unit_by_id = {get_entity_id(u): u for u in units if u is not None}

        def _pending_requests(decision_type: str, *, context_key: str, valid_ids: set[str]):
            pending = {}
            if queue is None or not hasattr(queue, "list"):
                return pending
            for req in list(queue.list() or []):
                if getattr(req, "decision_type", None) != decision_type:
                    continue
                if str(getattr(req, "player_id", "")) != str(getattr(player, "id", "")):
                    continue
                ctx_id = str(getattr(req, "context", {}).get(context_key, "") or "")
                if ctx_id and ctx_id in valid_ids:
                    pending[ctx_id] = req
            return pending

        def _pending_single(decision_type: str):
            if queue is None or not hasattr(queue, "list"):
                return None
            for req in list(queue.list() or []):
                if getattr(req, "decision_type", None) != decision_type:
                    continue
                if str(getattr(req, "player_id", "")) == str(getattr(player, "id", "")):
                    return req
            return None

        def _pending_hover_requests():
            pending = []
            if queue is None or not hasattr(queue, "list"):
                return pending
            for req in list(queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_CONFIRM_YES_NO:
                    continue
                if str(getattr(req, "player_id", "")) != str(getattr(player, "id", "")):
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "hover_mode":
                    continue
                pending.append(req)
            return pending

        def _pending_patrol_squad_requests():
            pending = []
            if queue is None or not hasattr(queue, "list"):
                return pending
            for req in list(queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_CONFIRM_YES_NO:
                    continue
                if str(getattr(req, "player_id", "")) != str(getattr(player, "id", "")):
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("ability", "") or "") != "patrol_squad":
                    continue
                pending.append(req)
            return pending

        def _show_player_color():
            req = _pending_single(DECISION_CHOOSE_PLAYER_COLOR)
            if req is None:
                _show_hover()
                return

            dialog = getattr(self.game_view, "player_color_picker_dialog", None)
            if dialog is None:
                dialog = PlayerColorPickerDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
                self.game_view.player_color_picker_dialog = dialog

            player_name = str(getattr(player, "name", "Player") or "Player")
            initial_hue = getattr(player, "ui_color_hue_degrees", None)
            initial_rgb = None
            get_rgb = getattr(player, "get_ui_color_rgb", None)
            if callable(get_rgb):
                initial_rgb = get_rgb()
            else:
                raw_rgb = getattr(player, "ui_color_rgb", None)
                if isinstance(raw_rgb, (list, tuple)) and len(raw_rgb) == 3:
                    initial_rgb = (int(raw_rgb[0]), int(raw_rgb[1]), int(raw_rgb[2]))

            def _done(option_id: str) -> None:
                resolve_decision_command(
                    self.game,
                    req,
                    option_id,
                    player_id=getattr(player, "id", None),
                )
                _show_player_color()

            def _cancel() -> None:
                default_id = first_option_id(req)
                if default_id:
                    resolve_decision_command(
                        self.game,
                        req,
                        default_id,
                        player_id=getattr(player, "id", None),
                    )
                _show_player_color()

            dialog.show(
                player_name=player_name,
                on_confirm=_done,
                on_cancel=_cancel,
                decision_request=req,
                initial_hue_degrees=initial_hue,
                initial_rgb=initial_rgb,
            )
            self.game_view.dialog_manager.open(dialog, modal=True)

        def _show_reserves():
            _refresh_units_cache()
            req = _pending_single(DECISION_DECLARE_RESERVES)
            if req is None:
                return
            dlg = ReservesAllocationDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
            self.game_view.reserves_allocation_dialog = dlg

            def _on_done(option_id, buckets):
                resolve_decision_command(
                    self.game,
                    req,
                    option_id,
                    result_payload={"unit_ids_by_bucket": buckets},
                )
                try:
                    self.game_view.refresh_roster_panes()
                except Exception:
                    pass

            dlg.show(army, on_confirm=_on_done, on_cancel=lambda: None, decision_request=req)
            try:
                self.game_view.dialog_manager.open(dlg, modal=True)
            except Exception:
                pass

        def _show_transports():
            _refresh_units_cache()
            unit_ids = {get_entity_id(u) for u in units}
            pending = _pending_requests(DECISION_ASSIGN_TRANSPORT, context_key="unit_id", valid_ids=unit_ids)
            if not pending:
                _show_reserves()
                return
            dlg = TransportAssignmentDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
            self.game_view.transport_assignment_dialog = dlg

            def _apply(selected_option_ids):
                for unit_id, option_id in (selected_option_ids or {}).items():
                    req = pending.get(unit_id)
                    if req is None:
                        continue
                    payload = {
                        "decision_id": req.decision_id,
                        "option_id": option_id,
                        "result_payload": {},
                    }
                    cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
                    self.game.apply_command(cmd)
                _show_reserves()

            def _skip():
                for unit_id, req in (pending or {}).items():
                    default_id = ""
                    for opt in list(getattr(req, "options", []) or []):
                        payload = dict(getattr(opt, "payload", {}) or {})
                        if payload.get("transport_id") is None:
                            default_id = opt.option_id
                            break
                    if not default_id:
                        continue
                    payload = {
                        "decision_id": req.decision_id,
                        "option_id": default_id,
                        "result_payload": {},
                    }
                    cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
                    self.game.apply_command(cmd)
                _show_reserves()

            dlg.show(units, unit_requests=pending, on_confirm=_apply, on_cancel=_skip)
            try:
                self.game_view.dialog_manager.open(dlg, modal=True)
            except Exception:
                pass

        def _show_support_artillery():
            _refresh_units_cache()
            support_ids = {
                get_entity_id(u)
                for u in units
                if bool(getattr(u, "has_joined_support_ability", lambda: False)())
            }
            pending = _pending_requests(
                DECISION_ATTACH_SUPPORT_ARTILLERY,
                context_key="support_unit_id",
                valid_ids=support_ids,
            )
            if not pending:
                _show_transports()
                return
            dlg = LeaderAttachmentDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
            self.game_view.leader_attachment_dialog = dlg

            def _on_done(selected_option_ids):
                for support_id, option_id in (selected_option_ids or {}).items():
                    req = pending.get(support_id)
                    if req is None:
                        continue
                    payload = {
                        "decision_id": req.decision_id,
                        "option_id": option_id,
                        "result_payload": {},
                    }
                    cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
                    self.game.apply_command(cmd)
                try:
                    army.validate_support_artillery()
                except Exception as e:
                    logger.exception(f"  {player.name} joined support validation failed: {e}")
                    return
                try:
                    self.game_view.refresh_roster_panes()
                except Exception:
                    pass
                _show_transports()

            support_units = [u for u in units if bool(getattr(u, "has_joined_support_ability", lambda: False)())]
            bodyguard_units = [
                u for u in units
                if not bool(getattr(u, "is_leader", False))
                and not bool(getattr(u, "is_joined_support", False))
            ]
            dlg.show(
                units,
                leaders=support_units,
                bodyguards=bodyguard_units,
                leader_requests=pending,
                on_confirm=_on_done,
                on_cancel=lambda: None,
                title=f"Attach Joined Support Units - {player.name}",
                subtitle="Select a support/retinue unit, then choose an eligible bodyguard unit (or Unattached).",
                left_label="Support/Retinue Units",
                right_label="Bodyguard Units",
            )
            dlg.visible = True
            try:
                self.game_view.dialog_manager.open(dlg, modal=True)
            except Exception:
                pass

        def _show_leaders():
            _refresh_units_cache()
            leader_ids = {get_entity_id(u) for u in units if bool(getattr(u, "is_leader", False))}
            pending = _pending_requests(DECISION_ATTACH_LEADER, context_key="leader_id", valid_ids=leader_ids)
            if not pending:
                _show_transports()
                return
            dlg = LeaderAttachmentDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
            self.game_view.leader_attachment_dialog = dlg

            def _on_done(selected_option_ids):
                for leader_id, option_id in (selected_option_ids or {}).items():
                    req = pending.get(leader_id)
                    if req is None:
                        continue
                    payload = {
                        "decision_id": req.decision_id,
                        "option_id": option_id,
                        "result_payload": {},
                    }
                    cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
                    self.game.apply_command(cmd)
                try:
                    army.validate_leaders()
                except Exception as e:
                    logger.exception(f"  {player.name} leader attachment validation failed: {e}")
                    return
                try:
                    self.game_view.refresh_roster_panes()
                except Exception:
                    pass
                _show_support_artillery()

            dlg.show(units, leader_requests=pending, on_confirm=_on_done, on_cancel=lambda: None)
            dlg.visible = True
            try:
                self.game_view.dialog_manager.open(dlg, modal=True)
            except Exception:
                pass

        def _show_shadow_assignments():
            _refresh_units_cache()
            self._show_shadow_assignment_dialog(
                players=[player],
                on_done=_after_shadow_assignments,
            )

        def _after_shadow_assignments():
            _refresh_units_cache()
            try:
                self.game_view.refresh_roster_panes()
            except Exception:
                pass
            _show_leaders()

        def _show_plague():
            req = _pending_single(DECISION_CHOOSE_PLAGUE)
            if req is None:
                mgr = getattr(army, "nurgles_gift", None)
                if mgr is None or not getattr(mgr, "_army_has_gift", lambda: False)():
                    _show_shadow_assignments()
                    return
                if getattr(mgr, "active_plague_key", None):
                    _show_shadow_assignments()
                    return
                try:
                    from ...rules.nurgles_gift import DEFAULT_PLAGUES
                except Exception:
                    _show_shadow_assignments()
                    return
                army_id = get_entity_id(army)
                options = []
                for plague in list(DEFAULT_PLAGUES):
                    key = getattr(plague, "key", None)
                    if not key:
                        continue
                    name = getattr(plague, "name", None) or str(plague)
                    summary = getattr(plague, "summary", "") or getattr(plague, "effect", "")
                    options.append(
                        DecisionOption.create(
                            name,
                            payload={"choice_key": str(key), "summary": summary, "army_id": army_id},
                        )
                    )
                if not options:
                    _show_shadow_assignments()
                    return
                req = _require_pending_decision_request(self.game,
                    DECISION_CHOOSE_PLAGUE,
                    "Nurgle's Gift: select one Plague.",
                    player_id=getattr(player, "id", None),
                    options=options,
                    context={
                        "ability": "nurgles_gift_declare",
                        "ability_name": "Nurgle's Gift",
                        "army_id": army_id,
                        "optional": False,
                    },

                )

            dlg = NurglesGiftPlagueDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
            dlg.title = f"Nurgle's Gift - {player.name}"

            def _done(option_id: str):
                resolve_decision_value(self.game, req, option_id)
                _show_shadow_assignments()

            def _cancel():
                default_id = first_option_id(req)
                if default_id:
                    resolve_decision_value(self.game, req, default_id)
                _show_shadow_assignments()

            dlg.show(on_confirm=_done, on_cancel=_cancel, decision_request=req)
            try:
                self.game_view.dialog_manager.open(dlg, modal=True)
            except Exception:
                pass

        def _show_hover():
            _refresh_units_cache()
            pending = _pending_hover_requests()
            if not pending:
                _show_patrol_squads()
                return
            req = pending[0]
            ctx = dict(getattr(req, "context", {}) or {})
            unit_id = str(ctx.get("unit_id", "") or "")
            unit = unit_by_id.get(unit_id)
            msg = str(ctx.get("message", "") or "")
            if not msg:
                unit_name = getattr(unit, "name", "Unit") if unit is not None else "Unit"
                msg = (
                    f"Enable Hover mode for {unit_name} ({player.name})?\n\n"
                    "Hover removes the AIRCRAFT keyword and sets Move to 20\"."
                )
            title = str(getattr(req, "prompt", "") or "Hover Mode")
            dlg = getattr(self.game_view, "yes_no_dialog", None)
            if dlg is None:
                return

            def _done(option_id: str):
                resolve_decision_command(self.game, req, option_id)
                _show_hover()

            dlg.show(title, msg, _done, decision_request=req)
            try:
                self.game_view.dialog_manager.open(dlg, modal=True)
            except Exception:
                return

        def _show_patrol_squads():
            _refresh_units_cache()
            pending = _pending_patrol_squad_requests()
            if not pending:
                _show_plague()
                return
            req = pending[0]
            ctx = dict(getattr(req, "context", {}) or {})
            title = str(getattr(req, "prompt", "") or "Patrol Squad")
            msg = str(ctx.get("message", "") or "")
            if not msg:
                msg = "Split this unit into two units of five models each?"
            dlg = getattr(self.game_view, "yes_no_dialog", None)
            if dlg is None:
                _show_plague()
                return

            def _done(option_id: str):
                resolve_decision_command(self.game, req, option_id)
                try:
                    self.game_view.refresh_roster_panes()
                except Exception:
                    pass
                _show_patrol_squads()

            dlg.show(title, msg, _done, decision_request=req)
            try:
                self.game_view.dialog_manager.open(dlg, modal=True)
            except Exception:
                return

        _show_player_color()

    def get_allowed_actions(self) -> List[str]:
        return ["advance_setup_phase", "view_unit_details"]

class DeploymentPhaseHandler(BasePhaseHandler):
    """Handles events during deployment phase"""
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        # Per-model deployment: handle hover + facing rotation BEFORE any UI-interface consumes the event.
        if (hasattr(self.game_view, 'individual_model_movement_dialog') and
            self.game_view.individual_model_movement_dialog and
            self.game_view.individual_model_movement_dialog.visible and
            getattr(self.game_view.individual_model_movement_dialog, 'movement_type', '') == 'deploy' and
            self.game_view.individual_model_movement_dialog.selected_model_index is not None):

            # Track hover position for silhouette preview
            if event.type == pygame.MOUSEMOTION:
                x, y = event.pos
                if self.game_view.battlefield_left < x < self.game_view.battlefield_right:
                    battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)
                    self.game_view.individual_model_preview_target = (battlefield_x, battlefield_y)
                    return True
                else:
                    self.game_view.individual_model_preview_target = None

            # Mouse wheel rotates facing in 5 deg increments (consume to prevent zoom)
            if event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if self.game_view.battlefield_left < mx < self.game_view.battlefield_right:
                    try:
                        self.game_view.individual_model_movement_dialog.rotate_deploy_facing_degrees(float(event.y) * 5.0)
                    except Exception:
                        pass
                    return True

            # Some environments emit wheel as MOUSEBUTTONDOWN with button 4/5.
            if event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):
                mx, my = pygame.mouse.get_pos()
                if self.game_view.battlefield_left < mx < self.game_view.battlefield_right:
                    try:
                        delta = 5.0 if event.button == 4 else -5.0
                        self.game_view.individual_model_movement_dialog.rotate_deploy_facing_degrees(delta)
                    except Exception:
                        pass
                    return True

        # Handle UI interface events
        if self.game_view.ui_interface and self.game_view.ui_interface.handle_event(event):
            return True
        
        # Handle deployment-specific mouse events
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._handle_deployment_click(event.pos)
        
        # Handle deployment-specific keyboard events
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                # Force complete deployment phase
                self.game_view.force_complete_deployment()
                return True
            elif event.key == pygame.K_ESCAPE:
                # Cancel current unit selection
                self.game_view.selected_unit = None
                self.game_view.left_roster_pane.selected_unit = None
                self.game_view.right_roster_pane.selected_unit = None
                return True
        
        # Handle right-click for unit details (works in all phases)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:  # Right click - show unit details
            hovered_unit, _ = self.game_view.get_hovered_unit(event.pos[0], event.pos[1])
            if hovered_unit:
                self.game_view.detailed_unit = hovered_unit
                self.game_view.detail_panel_pos = event.pos
                return True
        
        return False
    
    def _handle_deployment_click(self, mouse_pos) -> bool:
        """Handle mouse clicks during deployment phase"""
        x, y = mouse_pos

        logger.debug(f"DEBUG: _handle_deployment_click at ({x}, {y})")
        logger.debug(f"DEBUG: Left roster rect: {self.game_view.left_roster_pane.rect}")
        logger.debug(f"DEBUG: Right roster rect: {self.game_view.right_roster_pane.rect}")

        # Check roster pane clicks first
        if self.game_view.left_roster_pane.rect.collidepoint(x, y):
            logger.debug(f"DEBUG: Click is in LEFT roster pane")
            self.game_view.left_roster_pane.on_mouse_press(x, y, 1)
            self.game_view.selected_unit = self.game_view.left_roster_pane.selected_unit
            return True
        elif self.game_view.right_roster_pane.rect.collidepoint(x, y):
            logger.debug(f"DEBUG: Click is in RIGHT roster pane")
            self.game_view.right_roster_pane.on_mouse_press(x, y, 1)
            self.game_view.selected_unit = self.game_view.right_roster_pane.selected_unit
            return True
        else:
            logger.debug(f"DEBUG: Click is NOT in any roster pane")

        # Handle battlefield deployment clicks
        if (self.game_view.selected_unit and not self.game_view.selected_unit.deployed and
            self.game_view.battlefield_left < x < self.game_view.battlefield_right):
            # Always route to per-model deployment dialog for human deployments
            battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)
            battlefield_z = self.game.map.get_height_at_point(battlefield_x, battlefield_y)

            # If dialog is already visible in deploy mode, forward the click to it
            if (hasattr(self.game_view, 'individual_model_movement_dialog') and
                self.game_view.individual_model_movement_dialog and
                self.game_view.individual_model_movement_dialog.visible and
                getattr(self.game_view.individual_model_movement_dialog, 'movement_type', '') == 'deploy'):
                return self.game_view.individual_model_movement_dialog.handle_battlefield_click(
                    battlefield_x, battlefield_y, battlefield_z
                )

            # Ensure per-model deployment dialog is opened
            def on_deploy_complete(completed: bool):
                # Engine resolves deployment state through DecisionRequest/Command.
                if completed:
                    self.game_view.selected_unit = None
                    self.game_view.left_roster_pane.selected_unit = None
                    self.game_view.right_roster_pane.selected_unit = None
                # Clear flag
                try:
                    self.game_view.deployment_mode_for_selected_unit = None
                except Exception:
                    pass

            try:
                self.game_view.deployment_mode_for_selected_unit = 'per_model'
            except Exception:
                pass

            # Ensure dialog instance exists
            if not (hasattr(self.game_view, 'individual_model_movement_dialog') and self.game_view.individual_model_movement_dialog):
                try:
                    from ..dialogs.individual_model_movement_dialog import IndividualModelMovementDialog
                    self.game_view.individual_model_movement_dialog = IndividualModelMovementDialog(self.game_view.screen.get_width(), self.game_view.screen.get_height())
                except Exception:
                    pass

            logger.info(f"[DeploymentPhaseHandler] Opening per-model deployment dialog for {self.game_view.selected_unit.name}")
            self._request_move_unit_decision(
                self.game_view.selected_unit,
                "deploy",
                on_deploy_complete,
                max_distance=0.0,
            )

            # Immediately forward this battlefield click to place the first model
            return self.game_view.individual_model_movement_dialog.handle_battlefield_click(
                battlefield_x, battlefield_y, battlefield_z
            )
        
        return False

    def _request_move_unit_decision(
        self,
        unit: 'Unit',
        movement_type: str,
        callback,
        *,
        max_distance: float | None = None,
        target_unit=None,
        placement_validator=None,
        decision_request=None,
    ) -> None:
        """
        Deployment-phase proxy for shared move/placement decision orchestration.

        This forwards to PhaseManager's shared helper so deployment uses the same
        decision path as movement/fight placement interactions.
        """
        phase_manager = getattr(self.game_view, "phase_manager", None)
        if phase_manager is None or not hasattr(phase_manager, "_request_move_unit_decision"):
            raise RuntimeError("DeploymentPhaseHandler missing PhaseManager move decision helper.")
        phase_manager._request_move_unit_decision(
            unit,
            movement_type,
            callback,
            max_distance=max_distance,
            target_unit=target_unit,
            placement_validator=placement_validator,
            decision_request=decision_request,
        )
    
    def _handle_battlefield_deployment(self, x: int, y: int) -> bool:
        """Handle unit deployment on battlefield"""
        # Check if deployment zones are loaded
        if not hasattr(self.game, 'deployment_zones') or not self.game.deployment_zones:
            logger.info(f"Press SPACE to begin deployment sequence first")
            return True
        
        # Convert screen coordinates to game coordinates using helper method
        battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)
        
        # Attempt to deploy the unit
        # Store original model positions for potential rollback
        original_model_positions = [model.get_location() for model in self.game_view.selected_unit.models]
        
        # During deployment, use relaxed friendly unit avoidance to allow tighter formations
        # Use deployment boundary repulsors to keep formation inside mission zones/cutouts
        deployment_repulsors = self.game_view.game.get_boundary_repulsors(self.game_view.selected_unit, context='deployment')
        model_positions = self.game_view.selected_unit.calculate_model_positions(
            battlefield_x, battlefield_y, self.game_view.game_map,
            avoid_friendly_units=False, boundary_repulsors=deployment_repulsors) # TODO - add zoom back -- , 0.0, self.game_view.zoom_level)
        
        if model_positions:
            # Set model positions
            for model, position in zip(self.game_view.selected_unit.models, model_positions):
                model_x, model_y, model_z, model_facing = position
                model.set_location(model_x, model_y, model_z, model_facing)
            
            unit_x = sum(pos[0] for pos in model_positions) / len(model_positions)
            unit_y = sum(pos[1] for pos in model_positions) / len(model_positions)
            
            # Validate deployment position
            current_deployment_player = self.game.get_current_deployment_player()
            player_id = current_deployment_player.id if current_deployment_player else None
            
            if player_id and not self.game.is_valid_deployment_position(
                self.game_view.selected_unit, unit_x, unit_y, player_id):
                # Invalid position - reset and show error
                if self.game_view.selected_unit.has_infiltrate():
                    logger.error(f"ERROR: Invalid deployment position for {self.game_view.selected_unit.name} (Infiltrate)")
                else:
                    logger.error(f"ERROR: Invalid deployment position for {self.game_view.selected_unit.name}")
                self.game_view.reset_unit_position(self.game_view.selected_unit,
                                                 None, original_model_positions)
                return True
            
            # Valid deployment - unit position is now determined by model positions
            
            if self.game_view.game_map.place_unit(self.game_view.selected_unit):
                # Print per-model positions; include z only if non-zero
                try:
                    parts = []
                    for m in self.game_view.selected_unit.models:
                        pos = m.get_location()
                        if not pos:
                            continue
                        mx, my = pos[0], pos[1]
                        mz = pos[2] if len(pos) > 2 else 0.0
                        if abs(mz) < 1e-6:
                            parts.append(f"({mx:.1f}, {my:.1f})")
                        else:
                            parts.append(f"({mx:.1f}, {my:.1f}, {mz:.1f})")
                    positions_str = ", ".join(parts)
                    logger.info(f"Unit {self.game_view.selected_unit.name} deployed at: {positions_str}")
                except Exception:
                    logger.info(f"Unit {self.game_view.selected_unit.name} deployed at ({unit_x:.1f}, {unit_y:.1f})")
                self.game_view.selected_unit.deployed = True
                
                # Record deployment action
                if current_deployment_player and self.game_view.selected_unit.position:
                    self.game.record_deployment_action(current_deployment_player, 
                                                     self.game_view.selected_unit, 'deployed', 
                                                     self.game_view.selected_unit.position)
                
                # Advance to next player's deployment turn
                self.game.advance_deployment_turn(self.game_view.selected_unit)
                
                # Clear selection
                self.game_view.selected_unit = None
                self.game_view.left_roster_pane.selected_unit = None
                self.game_view.right_roster_pane.selected_unit = None
            else:
                logger.error("Failed to place unit")
                self.game_view.reset_unit_position(self.game_view.selected_unit,
                                                 None, original_model_positions)
        
        return True
    
    def get_allowed_actions(self) -> List[str]:
        return ["select_unit", "deploy_unit", "view_unit_details", "complete_deployment"]

class BattlePhaseHandler(BasePhaseHandler):
    """Handles events during battle phases (movement, shooting, etc.)"""
    
    def __init__(self, game_view: 'GameView'):
        super().__init__(game_view)
        self.fight_phase_manager = None
        self._rise_to_challenge_flow_active = False
        self._pending_rise_to_challenge_queue = []
        self._decision_callbacks = {}
        self._decision_subscription_enabled = False
        # Pending dice-driven movement flows
        self._pending_advance_units: set[str] = set()
        self._pending_move_modifier_actions: Dict[str, dict] = {}
        self._pending_pre_move_ability_actions: Dict[str, dict] = {}
        if self.game is not None:
            event_system = getattr(self.game, "event_system", None)
            if event_system is not None:
                event_system.subscribe("roll_made", self._on_roll_made)
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame events during battle phases"""
        if event.type == pygame.MOUSEMOTION:
            # print(f"DEBUG: BattlePhaseHandler.handle_event - MOUSEMOTION at {event.pos}")
            pass
        
        # Handle keyboard events
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                return self._handle_space_key()

        # Handle mouse events
        if event.type == pygame.MOUSEBUTTONDOWN:
            return self._handle_battle_click(event.pos, event.button)
        elif event.type == pygame.MOUSEMOTION:
            return self._handle_battle_motion(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            return self._handle_battle_release(event.pos, event.button)

        return False

    def _handle_space_key(self) -> bool:
        """Handle SPACE key for manual phase advancement"""
        if not self._current_player_has_control():
            return True
        current_phase = self.game.phase

        # Fight phase - check if we can skip/complete it
        if current_phase.name == 'FIGHT_PHASE':
            if self.fight_phase_manager and not self.fight_phase_manager.is_complete():
                # Force complete the fight phase
                logger.info("INFO: Manually completing fight phase...")
                self.fight_phase_manager._complete_fight_phase()
                return True
            else:
                # Fight phase already complete, advance to next phase
                logger.info("INFO: Fight phase complete, advancing to next phase...")
                return False  # Let main loop advance phase

        # For other phases, let main loop handle advancement
        else:
            logger.info(f"INFO: Manually advancing {current_phase.name}...")
            return False  # Let main loop advance phase

    def _handle_battle_click(self, mouse_pos, button) -> bool:
        """Handle battlefield clicks during battle phases"""
        x, y = mouse_pos

        # Check if shooting declaration dialog is in targeting mode
        if (hasattr(self.game_view, 'shooting_declaration_dialog') and
            self.game_view.shooting_declaration_dialog.is_targeting_mode):
            # Only handle left clicks for targeting
            if button != 1:  # Not a left click
                return True  # Still consume the event in targeting mode

            # Only handle clicks on the battlefield area
            if self.game_view.battlefield_left < x < self.game_view.battlefield_right:
                # Convert screen coordinates to game coordinates for targeting using helper method
                battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)

                # Handle battlefield targeting for shooting declaration
                handled = self.game_view.shooting_declaration_dialog.handle_battlefield_targeting(battlefield_x, battlefield_y)
            return True  # Consume all clicks in targeting mode, but only after trying to handle them
        
        # Handle unit selection and actions based on current phase
        if button == 1:  # Left click
            # Check roster pane clicks
            if self.game_view.left_roster_pane.rect.collidepoint(x, y):
                self.game_view.left_roster_pane.on_mouse_press(x, y, button)
                selected_unit = self.game_view.left_roster_pane.selected_unit
                if selected_unit:
                    self._handle_unit_selection(selected_unit)
                return True
            elif self.game_view.right_roster_pane.rect.collidepoint(x, y):
                self.game_view.right_roster_pane.on_mouse_press(x, y, button)
                selected_unit = self.game_view.right_roster_pane.selected_unit
                if selected_unit:
                    self._handle_unit_selection(selected_unit)
                return True
            
            # Handle battlefield clicks based on current phase
            elif self.game_view.battlefield_left < x < self.game_view.battlefield_right:
                return self._handle_battlefield_action(x, y)
        
        elif button == 3:  # Right click - show unit details
            hovered_unit, _ = self.game_view.get_hovered_unit(x, y)
            if hovered_unit:
                self.game_view.detailed_unit = hovered_unit
                self.game_view.detail_panel_pos = (x, y)
                return True

        return False
    
    def _synchronize_unit_selection(self, unit) -> None:
        """Synchronize unit selection between RosterPane and battlefield"""
        # Update the main selected unit
        self.game_view.selected_unit = unit
        
        # Update roster pane selections to match
        # Find which roster pane this unit belongs to and update its selection
        if unit.parent_army:
            if unit.parent_army.player == self.game_view.player1:
                self.game_view.left_roster_pane.selected_unit = unit
                self.game_view.right_roster_pane.selected_unit = None
            elif unit.parent_army.player == self.game_view.player2:
                self.game_view.right_roster_pane.selected_unit = unit
                self.game_view.left_roster_pane.selected_unit = None
    
    def _handle_unit_selection(self, unit) -> None:
        """Handle unit selection based on current phase"""
        current_phase = self.game.phase
        current_player = self.game.get_current_player()
        
        # Check if this unit belongs to the current player
        if not (unit.parent_army and unit.parent_army.player == current_player):
            logger.error(f"ERROR: {unit.name} does not belong to current player {current_player.name}")
            return
        
        # Only allow local control to interact with units during their turn
        if not current_player.has_control():
            logger.error(f"ERROR: Current player {current_player.name} has no local control")
            return
        
        # Synchronize selection across UI components
        self._synchronize_unit_selection(unit)
        
        # Handle phase-specific unit selection
        if current_phase.name == 'MOVEMENT_PHASE':
            self._handle_movement_phase_selection(unit)
        elif current_phase.name == 'SHOOTING_PHASE':
            self._handle_shooting_phase_selection(unit)
        elif current_phase.name == 'CHARGE_PHASE':
            self._handle_charge_phase_selection(unit)
        elif current_phase.name == 'FIGHT_PHASE':
            self._handle_fight_phase_selection(unit)
        else:
            logger.error(f"ERROR: Unit selection not available in {current_phase.name}")

    def _pending_phase_select_unit_request(self, unit, *, phase_name: str, phase_step: str | None = None):
        from ...engine.decision_kinds import DECISION_SELECT_UNIT
        from ...utility.entity_ids import maybe_entity_id

        unit_id = str(maybe_entity_id(unit) or "")
        for req in list(self.game.decision_queue.list() or []):
            if getattr(req, "decision_type", None) != DECISION_SELECT_UNIT:
                continue
            ctx = dict(getattr(req, "context", {}) or {})
            if str(ctx.get("phase_name", "") or "").strip().upper() != str(phase_name or "").strip().upper():
                continue
            if phase_step is not None and str(ctx.get("phase_step", "") or "").strip().upper() != str(phase_step or "").strip().upper():
                continue
            allowed_unit_ids = {
                str(value or "").strip()
                for value in list(ctx.get("allowed_unit_ids", []) or [])
                if str(value or "").strip()
            }
            if unit_id and allowed_unit_ids and unit_id not in allowed_unit_ids:
                continue
            return req
        return None

    def _resolve_phase_select_unit_request(self, unit, request) -> bool:
        from ...engine.command_kinds import CMD_RESOLVE_DECISION
        from ...engine.commands import GameCommand
        from ...utility.entity_ids import maybe_entity_id

        if request is None:
            return False
        unit_id = str(maybe_entity_id(unit) or "")
        matching_option = next(
            (
                opt
                for opt in list(getattr(request, "options", []) or [])
                if str((getattr(opt, "payload", {}) or {}).get("unit_id", "") or "").strip() == unit_id
            ),
            None,
        )
        if matching_option is None:
            logger.error("ERROR: %s is not an allowed activation target", getattr(unit, "name", "Unit"))
            return False
        payload = {
            "decision_id": request.decision_id,
            "option_id": matching_option.option_id,
            "result_payload": {"unit_id": unit_id},
        }
        cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=request.player_id, payload=payload)
        cmd_result = self.game.apply_command(cmd)
        if cmd_result is None or not bool(getattr(cmd_result, "ok", False)):
            logger.error("ERROR: Unit activation decision rejected for %s", getattr(unit, "name", "Unit"))
            return False
        return True
    
    def _handle_movement_phase_selection(self, unit) -> None:
        """Handle unit selection during movement phase"""
        # Movement validation is handled by the game logic
        from ...engine.command_kinds import CMD_RESOLVE_DECISION
        from ...engine.commands import GameCommand
        from ...engine.decision_kinds import DECISION_MOVE_UNIT, DECISION_SELECT_MOVEMENT_ACTION, DECISION_SELECT_UNIT
        from ...utility.entity_ids import maybe_entity_id

        unit_id = str(maybe_entity_id(unit) or "")

        def _pending_select_unit_request(phase_step: str):
            for req in list(self.game.decision_queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_SELECT_UNIT:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("phase_name", "") or "").strip().upper() != "MOVEMENT_PHASE":
                    continue
                if str(ctx.get("phase_step", "") or "").strip().upper() != str(phase_step or "").strip().upper():
                    continue
                allowed_unit_ids = {
                    str(value or "").strip()
                    for value in list(ctx.get("allowed_unit_ids", []) or [])
                    if str(value or "").strip()
                }
                if unit_id and allowed_unit_ids and unit_id not in allowed_unit_ids:
                    continue
                return req
            return None

        def _resolve_select_unit_request(request) -> bool:
            if request is None:
                return False
            matching_option = next(
                (
                    opt
                    for opt in list(getattr(request, "options", []) or [])
                    if str((getattr(opt, "payload", {}) or {}).get("unit_id", "") or "").strip() == unit_id
                ),
                None,
            )
            if matching_option is None:
                logger.error(
                    "ERROR: %s is not an allowed Movement activation target",
                    getattr(unit, "name", "Unit"),
                )
                return False
            payload = {
                "decision_id": request.decision_id,
                "option_id": matching_option.option_id,
                "result_payload": {"unit_id": unit_id},
            }
            cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=request.player_id, payload=payload)
            cmd_result = self.game.apply_command(cmd)
            if cmd_result is None or not bool(getattr(cmd_result, "ok", False)):
                logger.error(
                    "ERROR: Unit activation decision rejected for %s",
                    getattr(unit, "name", "Unit"),
                )
                return False
            return True

        def _pending_reinforcements_move_request():
            for req in list(self.game.decision_queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_MOVE_UNIT:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("placement_kind", "") or "").strip() != "reserves_arrival":
                    continue
                if str(ctx.get("unit_id", "") or "").strip() != unit_id:
                    continue
                return req
            return None

        reinforcement_select_req = _pending_select_unit_request("REINFORCEMENTS")
        if reinforcement_select_req is not None:
            if not _resolve_select_unit_request(reinforcement_select_req):
                return
        reinforcement_move_req = _pending_reinforcements_move_request()
        if reinforcement_move_req is not None:
            self._request_move_unit_decision(
                unit,
                "deploy",
                lambda _completed: None,
                decision_request=reinforcement_move_req,
            )
            return

        round_state = getattr(unit, "round_state", None)
        already_resolved_movement = bool(
            getattr(round_state, "moved_this_round", False)
            or getattr(round_state, "advanced_this_round", False)
            or getattr(round_state, "fell_back_this_round", False)
        )
        if already_resolved_movement:
            logger.info("INFO: %s already moved this phase; movement actions disabled", getattr(unit, "name", "Unit"))

            def _already_moved_choice(_choice):
                return

            self.game_view.movement_choice_dialog.show(
                unit,
                _already_moved_choice,
                self.game.map,
                decision_request=None,
            )
            return

        def _pending_movement_request():
            for req in list(self.game.decision_queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_SELECT_MOVEMENT_ACTION:
                    continue
                if str(getattr(req, "context", {}).get("unit_id", "")) == unit_id:
                    return req
            return None

        select_unit_req = _pending_select_unit_request("MOVE_UNITS")
        if select_unit_req is not None:
            if not _resolve_select_unit_request(select_unit_req):
                return

        req = _pending_movement_request()
        if req is None:
            try:
                req = _require_pending_decision_request(
                    self.game,
                    DECISION_SELECT_MOVEMENT_ACTION,
                    f"Select movement action for {getattr(unit, 'name', 'Unit')}",
                    player_id=getattr(self.game.get_current_player(), "id", None),
                    context={"unit_id": unit_id},
                )
            except RuntimeError:
                logger.error(
                    "ERROR: No pending movement action request found for %s",
                    getattr(unit, "name", "Unit"),
                )
                return

        def _option_for_action(action: str) -> str:
            for opt in list(getattr(req, "options", []) or []):
                payload = dict(getattr(opt, "payload", {}) or {})
                if str(payload.get("action_type", "") or "").lower() == action:
                    return opt.option_id
            return ""

        def on_movement_choice(choice):
            option_id = _option_for_action(choice)
            if option_id:
                payload = {
                    "decision_id": req.decision_id,
                    "option_id": option_id,
                    "result_payload": {},
                }
                cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
                cmd_result = self.game.apply_command(cmd)
                if cmd_result is None or not bool(getattr(cmd_result, "ok", False)):
                    logger.error(
                        "ERROR: Movement action decision rejected for %s (%s)",
                        getattr(unit, "name", "Unit"),
                        str(choice or ""),
                    )
                    return
            else:
                logger.error(
                    "ERROR: No matching movement option for %s (%s)",
                    getattr(unit, "name", "Unit"),
                    str(choice or ""),
                )
                return
            self._handle_movement_choice(unit, choice)

        self.game_view.movement_choice_dialog.show(unit, on_movement_choice, self.game.map, decision_request=req)
    
    def _handle_shooting_phase_selection(self, unit) -> None:
        """Handle unit selection during shooting phase"""
        if not unit or not unit.is_alive():
            return

        select_unit_req = self._pending_phase_select_unit_request(
            unit,
            phase_name="SHOOTING_PHASE",
            phase_step="SHOOT_UNITS",
        )
        if select_unit_req is not None:
            if not self._resolve_phase_select_unit_request(unit, select_unit_req):
                return
        
        # Check if unit can shoot
        action_lock_active = bool(getattr(unit.round_state, "action_locked_until_turn_end", False))
        allow_shoot_while_action = False
        if action_lock_active:
            try:
                army = unit.get_parent_army()
            except Exception:
                army = None
            sm_mgr = getattr(army, "space_marines_detachments", None) if army is not None else None
            if sm_mgr is not None and getattr(sm_mgr, "seekers_companions_allow_shoot_while_action", None):
                try:
                    allow_shoot_while_action = bool(
                        sm_mgr.seekers_companions_allow_shoot_while_action(
                            unit,
                            game=self.game,
                        )
                    )
                except Exception:
                    allow_shoot_while_action = False
            if not allow_shoot_while_action:
                try:
                    allow_fn = getattr(unit, "allows_shoot_while_started_action_from_unit_contains_rule", None)
                    if callable(allow_fn):
                        allow_shoot_while_action = bool(allow_fn(game=self.game))
                except Exception:
                    allow_shoot_while_action = False
        if unit.round_state.shot_this_round:
            action_shoot_exception_available = bool(
                action_lock_active
                and allow_shoot_while_action
                and (not bool(getattr(unit.round_state, "action_permitted_shoot_used", False)))
            )
            if not action_shoot_exception_available:
                logger.error(f"ERROR: {unit.name} has already shot this round")
                return

        try:
            if hasattr(unit, "is_shooting_phase_ineligible") and unit.is_shooting_phase_ineligible(self.game):
                logger.error(f"ERROR: {unit.name} is not eligible to shoot this phase")
                return
        except Exception:
            pass
        
        if unit.round_state.fell_back_this_round:
            logger.error(f"ERROR: {unit.name} cannot shoot after falling back")
            return
        
        # Check if unit is engaged and can't shoot with detailed debugging
        enemy_units = self.game.map.get_enemy_units(unit)
        engaged_enemies = []

        for enemy in enemy_units:
            if enemy.is_alive() and self.game.map.is_within_engagement_range(unit, enemy):
                engaged_enemies.append(enemy.name)

        is_engaged = len(engaged_enemies) > 0

        if is_engaged:
            logger.debug(f"DEBUG: {unit.name} is in engagement range of: {', '.join(engaged_enemies)}")

            # Show detailed position information
            if unit.models:
                unit_pos = unit.models[0].get_location() if unit.models[0].is_alive else None
                logger.debug(f"DEBUG: {unit.name} position: {unit_pos}")

                for enemy_name in engaged_enemies:
                    enemy_unit = next((e for e in enemy_units if e.name == enemy_name), None)
                    if enemy_unit and enemy_unit.models:
                        enemy_pos = enemy_unit.models[0].get_location() if enemy_unit.models[0].is_alive else None
                        if unit_pos and enemy_pos:
                            distance = ((unit_pos[0] - enemy_pos[0])**2 + (unit_pos[1] - enemy_pos[1])**2)**0.5
                            logger.debug(f"DEBUG: Distance to {enemy_name}: {distance:.1f}\"")

        if is_engaged:
            # Check if unit has any weapons that can shoot while engaged
            has_eligible_weapons = False
            for model in unit.models:
                if not model.is_alive:
                    continue
                for wargear in model.wargear:
                    if wargear.is_ranged():
                        for profile in wargear.profiles.values():
                            if unit.can_shoot_in_engagement_range(self.game.map, profile):
                                has_eligible_weapons = True
                                break
                        if has_eligible_weapons:
                            break
                if has_eligible_weapons:
                    break
            
            if not has_eligible_weapons:
                logger.error(f"ERROR: {unit.name} is engaged and has no weapons that can shoot in engagement range")
                return
        
        def _show_shooting_dialog():
            # Show shooting declaration dialog
            def on_shooting_complete(_executed: bool):
                self._clear_shooting_selection()
            from ...engine.decision_kinds import DECISION_DECLARE_SHOTS
            from ...utility.entity_ids import get_entity_id

            unit_id = get_entity_id(unit)
            req = _require_pending_decision_request(self.game,
                DECISION_DECLARE_SHOTS,
                f"Declare shots for {getattr(unit, 'name', 'Unit')}",
                player_id=getattr(self.game.get_current_player(), "id", None),
                context={"unit_id": unit_id, "out_of_phase": False},

            )
            self.game_view.shooting_declaration_dialog.show(
                unit,
                on_shooting_complete,
                self.game.map,
                self.game_view,
                decision_request=req,
            )

        # Firing Deck X (Transport): allow selecting embarked weapons to be treated as the transport's weapons.
        try:
            has_fd, fd_x = unit.has_firing_deck()
        except Exception:
            has_fd, fd_x = (False, 0)

        if has_fd and int(fd_x or 0) > 0 and list(getattr(unit, "transport_passengers", []) or []):
            entries = []
            per_weapon_count = {}

            try:
                passengers = list(getattr(unit, "transport_passengers", []) or [])
            except Exception:
                passengers = []

            for punit in passengers:
                # Include attached leaders' models as well
                try:
                    models = punit.get_attached_unit_models()
                except Exception:
                    models = list(getattr(punit, "models", []) or [])

                for m in models:
                    if not getattr(m, "is_alive", False):
                        continue
                    for w in list(getattr(m, "wargear", []) or []):
                        try:
                            if not w.is_ranged():
                                continue
                        except Exception:
                            continue

                        for profile_name, profile in (getattr(w, "profiles", {}) or {}).items():
                            # Explicit requirement: do not list ONE SHOT weapons for firing deck selection
                            if profile.is_one_shot():
                                continue
                            key = (str(getattr(w, "name", "Weapon")), str(profile_name))
                            c = int(per_weapon_count.get(key, 0))
                            if c >= int(fd_x or 0):
                                continue
                            per_weapon_count[key] = c + 1
                            selection_cost = 1
                            try:
                                selection_cost = max(1, int(unit.get_firing_deck_selection_cost(m) or 1))
                            except Exception:
                                selection_cost = 1
                            entries.append({
                                "model": m,
                                "wargear": w,
                                "profile": profile,
                                "profile_name": profile_name,
                                "passenger_unit": punit,
                                "selection_cost": selection_cost,
                            })

            if entries:
                if not hasattr(self.game_view, "firing_deck_dialog") or self.game_view.firing_deck_dialog is None:
                    from ..dialogs import FiringDeckDialog
                    self.game_view.firing_deck_dialog = FiringDeckDialog(
                        self.game_view.screen.get_width(),
                        self.game_view.screen.get_height(),
                    )

                def _on_confirm(chosen_entries):
                    from ...engine.decision_kinds import DECISION_DECLARE_FIRING_DECK
                    from ...engine.decisions import DecisionOption, DecisionRequest
                    from ...utility.decision_utils import resolve_decision_value
                    from ...utility.entity_ids import get_entity_id

                    transport_id = get_entity_id(unit)
                    options = [
                        DecisionOption.create(
                            "Confirm firing deck",
                            payload={"transport_id": transport_id, "action": "confirm"},
                        ),
                        DecisionOption.create(
                            "Skip firing deck",
                            payload={"transport_id": transport_id, "action": "skip"},
                        ),
                    ]
                    req = _require_pending_decision_request(self.game,
                        DECISION_DECLARE_FIRING_DECK,
                        f"Declare firing deck for {getattr(unit, 'name', 'Transport')}",
                        player_id=getattr(self.game.get_current_player(), "id", None),
                        options=options,
                        context={"transport_id": transport_id},

                    )
                    resolve_decision_value(
                        self.game,
                        req,
                        options[0].option_id,
                        result_payload={"selected_entries": chosen_entries},
                    )
                    _show_shooting_dialog()

                def _on_cancel():
                    from ...engine.decision_kinds import DECISION_DECLARE_FIRING_DECK
                    from ...engine.decisions import DecisionOption, DecisionRequest
                    from ...utility.decision_utils import resolve_decision_value
                    from ...utility.entity_ids import get_entity_id

                    transport_id = get_entity_id(unit)
                    options = [
                        DecisionOption.create(
                            "Confirm firing deck",
                            payload={"transport_id": transport_id, "action": "confirm"},
                        ),
                        DecisionOption.create(
                            "Skip firing deck",
                            payload={"transport_id": transport_id, "action": "skip"},
                        ),
                    ]
                    req = _require_pending_decision_request(self.game,
                        DECISION_DECLARE_FIRING_DECK,
                        f"Declare firing deck for {getattr(unit, 'name', 'Transport')}",
                        player_id=getattr(self.game.get_current_player(), "id", None),
                        options=options,
                        context={"transport_id": transport_id},

                    )
                    resolve_decision_value(
                        self.game,
                        req,
                        options[1].option_id,
                        result_payload={"selected_entries": []},
                    )
                    _show_shooting_dialog()

                self.game_view.firing_deck_dialog.show(
                    unit,
                    fd_x,
                    entries,
                    _on_confirm,
                    _on_cancel,
                )
                return

        _show_shooting_dialog()
    
    def _handle_charge_phase_selection(self, unit) -> None:
        """Handle unit selection during charge phase"""
        select_unit_req = self._pending_phase_select_unit_request(
            unit,
            phase_name="CHARGE_PHASE",
            phase_step="DECLARE_CHARGES",
        )
        if select_unit_req is not None:
            if not self._resolve_phase_select_unit_request(unit, select_unit_req):
                return

        # Check if unit has already charged this round
        if hasattr(unit.round_state, 'attempted_charge_this_round') and unit.round_state.attempted_charge_this_round:
            logger.error(f"ERROR: {unit.name} has already attempted a charge this round")
            return
        
        # Check if unit can charge (not advanced unless allowed, not fell back, etc.)
        if unit.round_state.fell_back_this_round:
            logger.error(f"ERROR: {unit.name} fell back and cannot charge")
            return
        
        # Show charge declaration dialog
        from ...engine.command_kinds import CMD_RESOLVE_DECISION
        from ...engine.commands import GameCommand
        from ...engine.decision_kinds import DECISION_DECLARE_CHARGE
        from ...utility.entity_ids import get_entity_id
        req = _require_pending_decision_request(self.game,
            DECISION_DECLARE_CHARGE,
            f"Declare charge for {getattr(unit, 'name', 'Unit')}",
            player_id=getattr(self.game.get_current_player(), "id", None),
            context={"unit_id": get_entity_id(unit)},

        )

        self._open_charge_declaration_request(unit, req)

    def _open_charge_declaration_request(self, unit, req) -> None:
        from ...engine.command_kinds import CMD_RESOLVE_DECISION
        from ...engine.commands import GameCommand
        from ...utility.entity_ids import get_entity_id

        def _option_id_for_target(target_unit) -> str:
            tid = get_entity_id(target_unit)
            for opt in list(getattr(req, "options", []) or []):
                payload = dict(getattr(opt, "payload", {}) or {})
                if str(payload.get("target_unit_id", "")) == tid:
                    return opt.option_id
            return ""

        def on_charge_declaration(charging_unit, target_units):
            targets = list(target_units or [])
            if not targets:
                return False
            option_id = _option_id_for_target(targets[0])
            if not option_id:
                return False
            payload = {
                "decision_id": req.decision_id,
                "option_id": option_id,
                "result_payload": {"target_unit_ids": [get_entity_id(t) for t in targets]},
            }
            cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
            cmd_result = self.game.apply_command(cmd)
            apply_result = getattr(cmd_result, "value", None)
            if apply_result is None or not getattr(apply_result, "ok", False):
                return False
            return True  # Charge declaration selection complete

        self.game_view.charge_declaration_dialog.show(
            unit,
            on_charge_declaration,
            self.game.map,
            self.game_view,
            decision_request=req,
        )
    def _handle_fight_phase_selection(self, unit) -> None:
        """Handle unit selection during fight phase"""
        current_player = self.game.get_current_player()
        opponent_player = self.game.get_opponent()
        
        # Initialize fight phase manager if not already done
        if not self.fight_phase_manager:
            self._initialize_fight_phase_manager(current_player, opponent_player)

        select_unit_req = self._pending_phase_select_unit_request(unit, phase_name="FIGHT_PHASE")
        if select_unit_req is not None:
            self._resolve_phase_select_unit_request(unit, select_unit_req)
            return
        
        # Check if it's this player's turn to select a unit
        active_player = self.fight_phase_manager.get_active_player()
        unit_owner = unit.get_parent_army().player if unit.get_parent_army() else None
        
        if not unit_owner:
            logger.error(f"ERROR: {unit.name} has no owner")
            return
        
        if active_player != unit_owner:
            logger.error(f"ERROR: It's {active_player.name}'s turn to select a unit, not {unit_owner.name}'s")
            return
        
        # Check if unit is eligible to fight in current stage
        eligible_units = self.fight_phase_manager._get_eligible_units_for_player(unit_owner)
        if unit not in eligible_units:
            logger.error(f"ERROR: {unit.name} is not eligible to fight in the current stage")
            return
        
        # Unit is valid - process the selection
        logger.info(f"OK: {unit_owner.name} selected {unit.name} to fight")
        self.fight_phase_manager.unit_selected(unit, current_player, opponent_player)
    
    def _initialize_fight_phase_manager(self, current_player: Player, opponent_player: Player) -> None:
        """Initialize the fight phase manager with proper callbacks."""
        logger.info("INFO: Initializing Fight Phase Manager")
        ensure_manager = getattr(self.game, "_ensure_fight_phase_manager_started", None)
        if callable(ensure_manager):
            manager = ensure_manager()
        else:
            manager = None
        if manager is None:
            manager = getattr(self.game, "fight_phase_manager", None)
        if manager is None:
            manager = FightPhaseManager(self.game)
            manager.start_fight_phase(current_player, opponent_player)
        self.fight_phase_manager = manager
        try:
            self.game.fight_phase_manager = self.fight_phase_manager
        except Exception:
            pass
        
        def on_target_selection_required(fighting_unit: Unit, eligible_targets: List[Unit], active_player: Player):
            if not active_player.has_control():
                logger.info(f"Waiting for remote target selection: {active_player.name}")
                return

            def _start_fight_target_selection() -> None:
                logger.info(f"INFO: {active_player.name} must select targets for {fighting_unit.name}")
                logger.info(f"   Eligible targets: {[target.name for target in eligible_targets]}")
                from ...engine.decision_kinds import DECISION_SELECT_FIGHT_TARGETS
                from ...engine.decisions import DecisionOption, DecisionRequest
                from ...utility.decision_utils import resolve_decision_value
                from ...utility.entity_ids import get_entity_id

                target_ids = []
                options = []
                for target in list(eligible_targets or []):
                    target_id = get_entity_id(target)
                    target_ids.append(target_id)
                    label = getattr(target, "name", "Target")
                    options.append(
                        DecisionOption.create(
                            label,
                            payload={"target_unit_id": target_id},
                        )
                    )
                if len(target_ids) > 1:
                    options.append(
                        DecisionOption.create(
                            "All engaged targets",
                            payload={"target_unit_ids": list(target_ids), "action": "all"},
                        )
                    )

                req = _require_pending_decision_request(self.game,
                    DECISION_SELECT_FIGHT_TARGETS,
                    f"Select targets for {getattr(fighting_unit, 'name', 'Unit')}",
                    player_id=getattr(active_player, "id", None),
                    options=options,
                    context={"unit_id": get_entity_id(fighting_unit)},

                )

                def _resolve_targets(option_id: str, selected_ids: List[str]):
                    payload = {"target_unit_ids": list(selected_ids or [])}
                    value, apply_result = resolve_decision_value(self.game, req, option_id, result_payload=payload)
                    if value is None or apply_result is None or not getattr(apply_result, "ok", False):
                        errors = list(getattr(apply_result, "errors", ()) or [])
                        if any("Formless Horror" in str(err or "") for err in errors):
                            # Re-open target selection; Formless Horror gate requires a new choice.
                            refreshed = []
                            for t in list(eligible_targets or []):
                                if t is None:
                                    continue
                                try:
                                    if hasattr(fighting_unit, "_formless_horror_target_blocked"):
                                        if fighting_unit._formless_horror_target_blocked(t, game=self.game):
                                            continue
                                except Exception:
                                    pass
                                refreshed.append(t)
                            if refreshed:
                                self.game_view.fight_target_selection_dialog.show(
                                    fighting_unit,
                                    refreshed,
                                    on_target_selected,
                                    on_cancel,
                                    decision_request=req,
                                )
                            return
                        value = [t for t in list(eligible_targets or []) if t is not None]
                    if not value:
                        value = [t for t in list(eligible_targets or []) if t is not None]
                    self._start_comprehensive_fight_sequence(fighting_unit, list(value), current_player, opponent_player)

                if len(target_ids) <= 1:
                    option_id = options[0].option_id if options else ""
                    logger.info("INFO: Auto-selecting single target")
                    _resolve_targets(option_id, target_ids)
                    return

                def on_target_selected(option_id: str, selected_ids: List[str]):
                    _resolve_targets(option_id, selected_ids)

                def on_cancel():
                    fallback = target_ids
                    option_id = ""
                    for opt in options:
                        payload = dict(getattr(opt, "payload", {}) or {})
                        if payload.get("action") == "all":
                            option_id = opt.option_id
                            fallback = list(payload.get("target_unit_ids") or target_ids)
                            break
                    if not option_id and options:
                        option_id = options[0].option_id
                        fallback = [target_ids[0]] if target_ids else []
                    _resolve_targets(option_id, fallback)

                self.game_view.fight_target_selection_dialog.show(
                    fighting_unit,
                    eligible_targets,
                    on_target_selected,
                    on_cancel,
                    decision_request=req,
                )

            def _start_exploding_horrors_flow() -> bool:
                if fighting_unit is None or not callable(getattr(fighting_unit, "can_use_exploding_horrors", None)):
                    return False
                if not fighting_unit.can_use_exploding_horrors():
                    return False
                if not eligible_targets:
                    return False
                brimstones = []
                try:
                    brimstones = list(fighting_unit._horrors_brimstone_models() or [])
                except Exception:
                    brimstones = []
                if not brimstones:
                    return False

                from ...engine.decision_kinds import (
                    DECISION_SELECT_EXPLODING_HORRORS_MODELS,
                    DECISION_SELECT_EXPLODING_HORRORS_TARGET,
                )
                from ...engine.decisions import DecisionOption, DecisionRequest
                from ...engine.decision_handlers._helpers import find_option, get_unit, is_skip_choice
                from ...utility.decision_utils import resolve_decision_value
                from ...utility.entity_ids import get_entity_id

                options = []
                for target in list(eligible_targets or []):
                    target_id = get_entity_id(target)
                    label = getattr(target, "name", "Target")
                    options.append(DecisionOption.create(label, payload={"target_unit_id": target_id}))
                options.append(
                    DecisionOption.create(
                        "Do not use Exploding Horrors",
                        payload={"action": "skip"},
                    )
                )

                req = _require_pending_decision_request(self.game,
                    DECISION_SELECT_EXPLODING_HORRORS_TARGET,
                    f"Exploding Horrors - Select target for {getattr(fighting_unit, 'name', 'Unit')}",
                    player_id=getattr(active_player, "id", None),
                    options=options,
                    context={"unit_id": get_entity_id(fighting_unit)},

                )

                def _start_model_selection(target_unit: Unit) -> None:
                    if target_unit is None:
                        _start_fight_target_selection()
                        return
                    current_brimstones = []
                    try:
                        current_brimstones = list(fighting_unit._horrors_brimstone_models() or [])
                    except Exception:
                        current_brimstones = []
                    if not current_brimstones:
                        _start_fight_target_selection()
                        return

                    model_options = [DecisionOption.create("Confirm", payload={"action": "confirm"})]
                    req_models = _require_pending_decision_request(self.game,
                        DECISION_SELECT_EXPLODING_HORRORS_MODELS,
                        "Exploding Horrors - Select Brimstones",
                        player_id=getattr(active_player, "id", None),
                        options=model_options,
                        context={
                            "unit_id": get_entity_id(fighting_unit),
                            "target_unit_id": get_entity_id(target_unit),
                            "allowed_model_ids": [get_entity_id(m) for m in current_brimstones],
                        },

                    )

                    def _apply_models_local(option_id: str, payload: dict):
                        value, apply_result = resolve_decision_value(
                            self.game, req_models, option_id, result_payload=payload
                        )
                        if value is None or apply_result is None or not getattr(apply_result, "ok", False):
                            _start_fight_target_selection()
                            return
                        game_map = getattr(self.game, "map", None)
                        fighting_unit.resolve_exploding_horrors(target_unit, list(value or []), game_map=game_map)
                        _start_fight_target_selection()

                    def _on_models_resolved(request, result):
                        if request is None or result is None:
                            _start_fight_target_selection()
                            return
                        selected = list(getattr(result, "payload", {}).get("model_ids", []) or [])
                        if not selected:
                            _start_fight_target_selection()
                            return
                        from ...engine.decision_handlers._helpers import resolve_model
                        models = [resolve_model(self.game, mid) for mid in selected]
                        models = [m for m in models if m is not None]
                        game_map = getattr(self.game, "map", None)
                        fighting_unit.resolve_exploding_horrors(target_unit, models, game_map=game_map)
                        _start_fight_target_selection()

                    dialog = getattr(self.game_view, "exploding_horrors_model_selection_dialog", None)
                    if dialog is not None and hasattr(dialog, "show"):
                        def on_confirm(option_id: str, payload: dict):
                            _apply_models_local(option_id, payload)

                        dialog.show(
                            fighting_unit,
                            current_brimstones,
                            on_confirm,
                            decision_request=req_models,
                        )
                    else:
                        self._register_decision_callback(req_models, _on_models_resolved)

                def _apply_target(option_id: str):
                    value, apply_result = resolve_decision_value(self.game, req, option_id)
                    if apply_result is None or not getattr(apply_result, "ok", False):
                        _start_fight_target_selection()
                        return
                    if value is None:
                        _start_fight_target_selection()
                        return
                    _start_model_selection(value)

                def _on_target_resolved(request, result):
                    if request is None or result is None:
                        _start_fight_target_selection()
                        return
                    if is_skip_choice(request, result):
                        _start_fight_target_selection()
                        return
                    opt = find_option(request, getattr(result, "option_id", ""))
                    payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
                    target_unit = get_unit(self.game, str(payload.get("target_unit_id", "") or ""))
                    _start_model_selection(target_unit)

                def on_target_selected(option_id: str, _selected_ids: List[str]):
                    _apply_target(option_id)

                def on_cancel():
                    skip_option_id = ""
                    for opt in options:
                        payload = dict(getattr(opt, "payload", {}) or {})
                        if payload.get("action") == "skip":
                            skip_option_id = opt.option_id
                            break
                    if skip_option_id:
                        _apply_target(skip_option_id)
                    else:
                        _start_fight_target_selection()

                dialog = getattr(self.game_view, "fight_target_selection_dialog", None)
                if dialog is not None and hasattr(dialog, "show"):
                    dialog.show(
                        fighting_unit,
                        eligible_targets,
                        on_target_selected,
                        on_cancel,
                        decision_request=req,
                        title="Exploding Horrors",
                        instructions="Select an engaged enemy unit, or choose not to use this ability.",
                    )
                else:
                    self._register_decision_callback(req, _on_target_resolved)
                return True

            if _start_exploding_horrors_flow():
                return
            _start_fight_target_selection()
        
        def on_stage_complete():
            logger.info("OK: Fight Phase complete")
            def _advance_phase():
                self.fight_phase_manager = None
                try:
                    self.game.fight_phase_manager = None
                except Exception:
                    pass
                _next_phase_cmd(self.game, player_id=_current_player_id(self.game))

            self._maybe_prompt_rise_to_challenge(current_player, opponent_player, _advance_phase)

        def on_movement_required(movement_type: str, unit: Unit, callback, decision_request=None):
            """Handle pile-in and consolidate movements using Individual Model Movement Dialog"""
            logger.info(f"{unit.name} needs to perform {movement_type} movement")

            # Determine max distance based on movement type
            max_distance = 3.0  # Default is 3"
            try:
                override = unit.get_fight_phase_move_distance_override(movement_type)
                if override is not None:
                    max_distance = float(override)
            except Exception:
                max_distance = 3.0

            self._request_move_unit_decision(
                unit,
                movement_type,
                callback,
                max_distance=max_distance,
                decision_request=decision_request,
            )

        def on_weapon_selection_required(unit: Unit, target_unit: Unit, callback):
            """Handle melee weapon selection using Melee Weapon Declaration Dialog"""
            logger.info(f"{unit.name} needs to select melee weapons against {target_unit.name}")
            def _show_weapons():
                self._request_melee_weapon_declarations(unit, target_unit, callback)
            if hasattr(self.game_view, "_maybe_prompt_fight_within_3"):
                self.game_view._maybe_prompt_fight_within_3(unit, target_unit, _show_weapons)
            else:
                _show_weapons()

        self.fight_phase_manager.on_target_selection_required = on_target_selection_required
        self.fight_phase_manager.on_stage_complete = on_stage_complete
        self.fight_phase_manager.on_movement_required = on_movement_required
        self.fight_phase_manager.on_weapon_selection_required = on_weapon_selection_required
        
        # Start the fight phase
        if getattr(self.fight_phase_manager, "_current_player", None) is None:
            self.fight_phase_manager.start_fight_phase(current_player, opponent_player)

    def _ensure_decision_subscription(self) -> None:
        if self._decision_subscription_enabled:
            return
        es = getattr(self.game, "event_system", None)
        if es is None:
            return
        es.subscribe("decision_resolved", self._on_decision_resolved, group="ui:phase_manager")
        self._decision_subscription_enabled = True

    def _register_decision_callback(self, request, callback) -> None:
        if request is None or callback is None:
            return
        try:
            self._decision_callbacks[request.decision_id] = callback
        except Exception:
            return
        self._ensure_decision_subscription()

    def _on_decision_resolved(self, request=None, result=None, **_kwargs) -> None:
        if request is None or result is None:
            return
        try:
            cb = self._decision_callbacks.pop(getattr(request, "decision_id", ""), None)
        except Exception:
            cb = None
        try:
            from ...engine.decision_kinds import DECISION_CHOOSE_MOVE_MODIFIER_IGNORES, DECISION_CONFIRM_YES_NO
            if getattr(request, "decision_type", None) == DECISION_CHOOSE_MOVE_MODIFIER_IGNORES:
                unit_id = str(getattr(request, "context", {}).get("unit_id", "") or "")
                if unit_id:
                    self._resume_pending_move_modifier_action(unit_id)
                    try:
                        if unit_id in self._pending_advance_units:
                            reg = getattr(self.game, "entity_registry", None)
                            unit_obj = reg.get(str(unit_id), kind="unit") if reg is not None else None
                            if unit_obj is not None:
                                self._handle_advance_roll_ready(unit_obj)
                    except Exception:
                        pass
            if getattr(request, "decision_type", None) == DECISION_CONFIRM_YES_NO:
                ctx = dict(getattr(request, "context", {}) or {})
                if str(ctx.get("ability", "") or "") in (
                    "movement_phase_move_weapon_bonus",
                    "flickerjump",
                    "advance_redeploy",
                    "normal_move_redeploy",
                ):
                    unit_id = str(ctx.get("unit_id", "") or "")
                    if unit_id:
                        self._resume_pending_pre_move_ability_action(unit_id)
        except Exception:
            pass
        if cb is None:
            return
        try:
            cb(request, result)
        except Exception:
            pass

    def _pending_decision_for_unit(self, decision_kind: str, unit):
        if unit is None:
            return None
        queue = getattr(self.game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return None
        try:
            from ...utility.entity_ids import get_entity_id
            unit_id = get_entity_id(unit)
        except Exception:
            return None
        for req in list(queue.list() or []):
            if getattr(req, "decision_type", None) != decision_kind:
                continue
            ctx = getattr(req, "context", {}) or {}
            if str(ctx.get("unit_id", "")) == str(unit_id):
                return req
        return None

    def _resume_pending_move_modifier_action(self, unit_id: str) -> None:
        if not unit_id:
            return
        entry = self._pending_move_modifier_actions.pop(str(unit_id), None)
        if entry is None:
            return
        callback = entry.get("callback")
        if callable(callback):
            try:
                callback()
            except Exception:
                pass

    def _resume_pending_pre_move_ability_action(self, unit_id: str) -> None:
        if not unit_id:
            return
        entry = self._pending_pre_move_ability_actions.pop(str(unit_id), None)
        if entry is None:
            return
        callback = entry.get("callback")
        if callable(callback):
            try:
                callback()
            except Exception:
                pass

    def _maybe_prompt_rise_to_challenge(self, current_player: Player, opponent_player: Player, on_done) -> None:
        if self._rise_to_challenge_flow_active:
            return
        queue = []
        for p in (current_player, opponent_player):
            if p is None:
                continue
            try:
                candidates = list(self.game._rise_to_challenge_candidates(p) or [])
            except Exception:
                candidates = []
            if candidates:
                queue.append((p, candidates))
        if not queue:
            if callable(on_done):
                on_done()
            return
        self._pending_rise_to_challenge_queue = queue
        self._open_next_rise_to_challenge_prompt(current_player, opponent_player, on_done)

    def _open_next_rise_to_challenge_prompt(self, current_player: Player, opponent_player: Player, on_done) -> None:
        q = list(getattr(self, "_pending_rise_to_challenge_queue", []) or [])
        if not q:
            self._pending_rise_to_challenge_queue = []
            self._rise_to_challenge_flow_active = False
            if callable(on_done):
                on_done()
            return
        player, candidates = q.pop(0)
        self._pending_rise_to_challenge_queue = q

        def _finish():
            self._rise_to_challenge_flow_active = False
            self._open_next_rise_to_challenge_prompt(current_player, opponent_player, on_done)

        if player is None or not candidates:
            _finish()
            return

        is_human = False
        try:
            is_human = bool(getattr(player, "has_control", lambda: False)())
        except Exception:
            is_human = False

        def _use_rise_to_challenge(unit):
            if unit is None:
                _finish()
                return
            try:
                sr = getattr(unit, "special_rules", None)
                if not isinstance(sr, dict):
                    sr = {}
                sr["enhancement_rise_to_challenge_used"] = True
                if bool(sr.get("enhancement_sanguinius_grace")):
                    sr["enhancement_sanguinius_grace_used"] = True
                    once_key = str(
                        sr.get("enhancement_sanguinius_grace_once_key", "sanguinius_grace")
                        or "sanguinius_grace"
                    ).strip().lower()
                    if once_key:
                        mark_used = getattr(unit, "mark_unit_once_per_battle_used", None)
                        if callable(mark_used):
                            source_name = str(
                                sr.get("enhancement_sanguinius_grace_source", "")
                                or "Sanguinius' Grace"
                            ).strip() or "Sanguinius' Grace"
                            mark_used(once_key, ability_name=source_name)
                unit.special_rules = sr
            except Exception:
                pass

            def _after_exquisite():
                self._start_bonus_fight_sequence(unit, player, current_player, opponent_player, _finish)

            if hasattr(self.game_view, "_prompt_exquisite_swordsmanship_choice"):
                try:
                    self.game_view._prompt_exquisite_swordsmanship_choice(unit, _after_exquisite)
                    return
                except Exception:
                    pass
            try:
                unit.set_exquisite_swordsmanship_choice("LETHAL")
            except Exception:
                pass
            _after_exquisite()

        if not is_human:
            try:
                from ...engine.decision_kinds import DECISION_SELECT_RISE_TO_CHALLENGE
                from ...engine.decisions import DecisionOption, DecisionRequest
                from ...engine.decision_handlers._helpers import find_option, get_unit, is_skip_choice
            except Exception:
                _finish()
                return

            options = []
            for unit in candidates:
                try:
                    label = str(getattr(unit, "name", "Unit") or "Unit")
                except Exception:
                    label = "Unit"
                options.append(DecisionOption.create(label, payload={"unit_id": get_entity_id(unit)}))
            options.append(DecisionOption.create("Skip", payload={"action": "skip"}))

            req = _require_pending_decision_request(self.game,
                DECISION_SELECT_RISE_TO_CHALLENGE,
                "Select Rise to the Challenge unit.",
                player_id=getattr(player, "id", None),
                options=options,
                context={},
            )
            self._rise_to_challenge_flow_active = True

            def _on_resolved(request, result):
                if request is None or result is None:
                    _finish()
                    return
                if is_skip_choice(request, result):
                    _finish()
                    return
                opt = find_option(request, result.option_id)
                payload = dict(getattr(opt, "payload", {}) or {}) if opt is not None else {}
                unit = get_unit(self.game, str(payload.get("unit_id", "") or ""))
                if unit is None:
                    _finish()
                    return
                _use_rise_to_challenge(unit)

            self._register_decision_callback(req, _on_resolved)
            return

        self._rise_to_challenge_flow_active = True
        try:
            from ...engine.decision_kinds import DECISION_SELECT_RISE_TO_CHALLENGE
        except Exception:
            DECISION_SELECT_RISE_TO_CHALLENGE = "SELECT_RISE_TO_CHALLENGE"

        if callable(getattr(self.game_view, "_resolve_unit_selection_dialog", None)):
            self.game_view._resolve_unit_selection_dialog(
                player=player,
                candidates=candidates,
                on_chosen=_use_rise_to_challenge,
                decision_type=DECISION_SELECT_RISE_TO_CHALLENGE,
                prompt="Select Rise to the Challenge unit.",
                title="Rise to the Challenge",
                subtitle="End of Fight phase: fight one additional time",
                dialog=self.game_view.overwatch_shooter_dialog,
                allow_skip=True,
            )
            return
        _use_rise_to_challenge(candidates[0] if candidates else None)

    def _start_bonus_fight_sequence(
        self,
        unit: Unit,
        player: Player,
        current_player: Player,
        opponent_player: Player,
        on_done,
    ) -> None:
        if unit is None:
            if callable(on_done):
                on_done()
            return
        try:
            game_map = getattr(self.game, "map", None)
        except Exception:
            game_map = None
        if game_map is None:
            if callable(on_done):
                on_done()
            return
        try:
            enemies = list(game_map.get_enemy_units(unit) or [])
        except Exception:
            enemies = []
        if not enemies:
            if callable(on_done):
                on_done()
            return
        engaged = []
        seen = set()
        for enemy in enemies:
            if enemy is None:
                continue
            try:
                root = enemy.get_attached_unit_root()
            except Exception:
                root = enemy
            if root is None:
                continue
            rid = get_entity_id(root)
            if rid in seen:
                continue
            seen.add(rid)
            try:
                if not root.is_alive():
                    continue
            except Exception:
                continue
            try:
                if game_map.is_within_engagement_range(unit, root):
                    engaged.append(root)
            except Exception:
                continue
        if not engaged:
            if callable(on_done):
                on_done()
            return

        if player is current_player:
            opponent = opponent_player
        else:
            opponent = current_player

        try:
            self._bonus_fight_on_complete = on_done
        except Exception:
            self._bonus_fight_on_complete = on_done
        self._start_comprehensive_fight_sequence(unit, engaged, player, opponent)

    def _serialize_unit_positions(self, unit: Unit, *, allowed_model_ids: Optional[set[str]] = None) -> List[dict]:
        from ...utility.entity_ids import get_entity_id

        try:
            models = list(unit.get_attached_unit_models() or [])
        except Exception:
            models = list(getattr(unit, "models", []) or [])
        entries: List[dict] = []
        for model in models:
            try:
                if not getattr(model, "is_alive", True):
                    if allowed_model_ids is None or str(get_entity_id(model)) not in allowed_model_ids or not bool(getattr(model, "_careen_pending_move", False)):
                        continue
            except Exception:
                pass
            if allowed_model_ids is not None and str(get_entity_id(model)) not in allowed_model_ids:
                continue
            base = getattr(model, "model_base", None)
            if base is None:
                continue
            try:
                x = float(getattr(base, "x", 0.0))
                y = float(getattr(base, "y", 0.0))
                z = float(getattr(base, "z", 0.0))
                facing = float(getattr(base, "facing", 0.0))
            except Exception:
                continue
            entries.append(
                {
                    "model_id": get_entity_id(model),
                    "position": [x, y, z],
                    "facing": facing,
                }
            )
        return entries

    def _request_move_unit_decision(
        self,
        unit: Unit,
        movement_type: str,
        callback,
        *,
        max_distance: float | None = None,
        target_unit=None,
        placement_validator=None,
        decision_request=None,
    ) -> None:
        if movement_type in ("pile_in", "consolidate") and bool(getattr(unit, "is_aircraft", False)):
            logger.info(f"{getattr(unit, 'name', 'Unit')} cannot {movement_type.replace('_', ' ')} (AIRCRAFT)")
            if callable(callback):
                callback(False)
            return
        from ...engine.decision_kinds import DECISION_MOVE_UNIT
        from ...engine.decisions import DecisionOption, DecisionRequest
        from ...utility.decision_utils import resolve_decision_command
        from ...utility.entity_ids import get_entity_id
        from ..decision_ui_utils import option_id_for_action, first_option_id

        req = decision_request
        if req is None:
            unit_id = get_entity_id(unit)
            options = [
                DecisionOption.create(
                    "Confirm",
                    payload={"unit_id": unit_id, "movement_type": movement_type, "action": "confirm"},
                ),
                DecisionOption.create(
                    "Skip",
                    payload={"unit_id": unit_id, "movement_type": movement_type, "action": "skip"},
                ),
            ]
            player_id = None
            try:
                player_id = unit.get_parent_army().player.id
            except Exception:
                player_id = None
            context = {"unit_id": unit_id, "movement_type": movement_type}
            if movement_type == "deploy":
                context["placement_kind"] = "deployment"
            req = _require_pending_decision_request(self.game,
                DECISION_MOVE_UNIT,
                f"Move {getattr(unit, 'name', 'Unit')} ({movement_type})",
                player_id=player_id,
                options=options,
                context=context,

            )
        elif max_distance is None:
            try:
                max_distance = float(getattr(req, "context", {}).get("max_distance", 0) or 0)
            except Exception:
                max_distance = None
        confirm_id = first_option_id(req)
        skip_id = option_id_for_action(req, "skip") or confirm_id
        ctx = getattr(req, "context", {}) or {}
        allowed_ids = ctx.get("allowed_model_ids")
        allowed_set = None
        if allowed_ids is not None:
            allowed_set = {str(v) for v in list(allowed_ids or []) if v is not None}
        allow_skip = bool(ctx.get("allow_skip", True))
        placement_kind = str(ctx.get("placement_kind", "") or "") or None

        def _on_move_complete(completed: bool):
            if completed:
                payload = {"model_positions": self._serialize_unit_positions(unit, allowed_model_ids=allowed_set)}
                cmd_result = resolve_decision_command(self.game, req, confirm_id, result_payload=payload)
                if not getattr(cmd_result, "ok", False):
                    try:
                        err_list = list(getattr(cmd_result, "errors", ()) or ())
                    except Exception:
                        err_list = []
                    logger.error(f"ERROR: Decision resolve failed for {getattr(req, 'decision_type', '')}: {err_list}")
            else:
                cmd_result = resolve_decision_command(self.game, req, skip_id, result_payload={"skipped": True})
                if not getattr(cmd_result, "ok", False):
                    try:
                        err_list = list(getattr(cmd_result, "errors", ()) or ())
                    except Exception:
                        err_list = []
                    logger.error(f"ERROR: Decision resolve failed for {getattr(req, 'decision_type', '')}: {err_list}")
            if callable(callback):
                logger.debug(f"DEBUG: Calling callback from _on_move_complete {describe_callable(callback)} with argument {completed}")
                callback(completed)

        self.game_view.individual_model_movement_dialog.show(
            unit,
            movement_type,
            _on_move_complete,
            self.game.map,
            max_distance,
            target_unit=target_unit,
            placement_validator=placement_validator,
            decision_request=req,
            place_only_model_ids=allowed_set,
            allow_skip=allow_skip,
            placement_kind=placement_kind,
        )
        try:
            self.game_view.dialog_manager.open(self.game_view.individual_model_movement_dialog, modal=True)
        except Exception:
            logger.exception(f"Unexpected Error while opening individual_model_movement_dialog")
            pass

    def _request_melee_weapon_declarations(
        self,
        unit: Unit,
        target_unit: Optional[Unit],
        on_complete,
        *,
        eligible_models=None,
    ) -> None:
        from ...engine.decision_kinds import DECISION_DECLARE_MELEE_WEAPONS
        from ...engine.decisions import DecisionOption, DecisionRequest
        from ...utility.decision_utils import resolve_decision_value
        from ...utility.entity_ids import get_entity_id

        unit_id = get_entity_id(unit)
        options = [DecisionOption.create("Confirm", payload={"unit_id": unit_id})]
        context = {"unit_id": unit_id}
        if target_unit is not None:
            context["target_unit_id"] = get_entity_id(target_unit)
        player_id = None
        try:
            player_id = unit.get_parent_army().player.id
        except Exception:
            player_id = None
        req = _require_pending_decision_request(self.game,
            DECISION_DECLARE_MELEE_WEAPONS,
            f"Declare melee weapons for {getattr(unit, 'name', 'Unit')}",
            player_id=player_id,
            options=options,
            context=context,

        )

        def _on_confirm(option_id: str, payload: dict):
            value, apply_result = resolve_decision_value(self.game, req, option_id, result_payload=payload)
            if value is None or apply_result is None or not getattr(apply_result, "ok", False):
                value = []
            on_complete(value)
            try:
                self.game_view.melee_weapon_declaration_dialog.hide()
            except Exception:
                pass

        self.game_view.melee_weapon_declaration_dialog.show(
            unit,
            _on_confirm,
            self.game.map,
            target_unit=target_unit,
            eligible_models=eligible_models,
            decision_request=req,
        )
    
    def _start_comprehensive_fight_sequence(self, fighting_unit: Unit, target_units: List[Unit], current_player: Player, opponent_player: Player):
        """Start the comprehensive fight sequence following proper Warhammer 40k rules."""
        logger.info(f"Starting comprehensive fight sequence: {fighting_unit.name} vs {[t.name for t in target_units]}")
        
        # Step 1: Pile-in movement
        def on_pile_in_complete(completed: bool):
            logger.info(f"{fighting_unit.name} pile-in completed: {completed}")
            
            if len(target_units) == 1:
                # Single target - proceed directly to weapon allocation
                self._start_weapon_allocation_phase(fighting_unit, target_units[0], current_player, opponent_player)
            else:
                logger.info("INFO: Multiple targets available - selecting weapons then allocating targets per weapon")
                self._start_multi_target_weapon_allocation_phase(
                    fighting_unit,
                    target_units,
                    current_player,
                    opponent_player,
                )
        
        # Start pile-in movement
        logger.info(f"{fighting_unit.name} needs to perform pile_in movement")
        max_distance = 3.0
        try:
            override = fighting_unit.get_fight_phase_move_distance_override("pile_in")
            if override is not None:
                max_distance = float(override)
        except Exception:
            max_distance = 3.0
        self._request_move_unit_decision(
            fighting_unit,
            "pile_in",
            on_pile_in_complete,
            max_distance=max_distance,
        )

    def _start_multi_target_weapon_allocation_phase(
        self,
        fighting_unit: Unit,
        target_units: List[Unit],
        current_player: Player,
        opponent_player: Player,
    ) -> None:
        """Select melee weapons, then allocate each weapon bundle to targets."""
        eligible_models = None
        try:
            allow_within_3 = False
            if hasattr(fighting_unit, "has_fight_within_3_ability") and fighting_unit.has_fight_within_3_ability():
                allow_within_3 = bool(fighting_unit.fight_within_3_active())
            eligible_models = set()
            for target in target_units:
                models = fighting_unit.get_fight_eligible_models_for_target(
                    target,
                    game_map=self.game.map,
                    allow_within_3=allow_within_3,
                )
                eligible_models.update(models or [])
            if not eligible_models:
                eligible_models = None
        except Exception:
            eligible_models = None

        def on_weapon_allocation_complete(weapon_declarations):
            logger.info(f"Weapon allocation completed with {len(weapon_declarations)} declarations")
            self._start_multi_target_weapon_target_allocation_phase(
                fighting_unit,
                target_units,
                weapon_declarations,
                current_player,
                opponent_player,
            )

        def _show_weapons():
            self._request_melee_weapon_declarations(
                fighting_unit,
                None,
                on_weapon_allocation_complete,
                eligible_models=eligible_models,
            )

        if hasattr(self.game_view, "_maybe_prompt_fight_within_3"):
            self.game_view._maybe_prompt_fight_within_3(fighting_unit, target_units[0], _show_weapons)
        else:
            _show_weapons()

    def _start_multi_target_weapon_target_allocation_phase(
        self,
        fighting_unit: Unit,
        target_units: List[Unit],
        weapon_declarations: List[dict],
        current_player: Player,
        opponent_player: Player,
    ) -> None:
        """Allocate weapon bundles to targets (and optional splits), then resolve attacks."""
        def on_allocation_confirm(attack_declarations: List[dict]):
            if not attack_declarations:
                logger.info("INFO: No weapon target allocations - skipping attacks")
                self._start_consolidate_phase(fighting_unit, current_player, opponent_player)
                return
            self._start_multi_target_attack_resolution(
                fighting_unit,
                target_units,
                attack_declarations,
                current_player,
                opponent_player,
            )

        def on_allocation_cancel():
            logger.info("INFO: Weapon target allocation cancelled")
            self.fight_phase_manager._switch_active_player(current_player, opponent_player)

        from ...engine.decision_kinds import DECISION_ALLOCATE_MELEE_TARGETS
        from ...engine.decisions import DecisionOption, DecisionRequest
        from ...utility.decision_utils import resolve_decision_value
        from ...utility.entity_ids import get_entity_id

        unit_id = get_entity_id(fighting_unit)
        options = [DecisionOption.create("Confirm", payload={"unit_id": unit_id})]
        req = _require_pending_decision_request(self.game,
            DECISION_ALLOCATE_MELEE_TARGETS,
            f"Allocate melee targets for {getattr(fighting_unit, 'name', 'Unit')}",
            player_id=getattr(current_player, "id", None),
            options=options,
            context={"unit_id": unit_id},

        )

        def _on_confirm(option_id: str, payload: dict):
            value, apply_result = resolve_decision_value(self.game, req, option_id, result_payload=payload)
            if value is None or apply_result is None or not getattr(apply_result, "ok", False):
                on_allocation_cancel()
                return
            on_allocation_confirm(value)

        self.game_view.melee_weapon_target_allocation_dialog.show(
            fighting_unit,
            target_units,
            weapon_declarations,
            _on_confirm,
            self.game.map,
            game=self.game,
            on_cancel=on_allocation_cancel,
            split_dialog=self.game_view.melee_attack_split_dialog,
            decision_request=req,
        )

    def _start_multi_target_attack_resolution(
        self,
        fighting_unit: Unit,
        target_units: List[Unit],
        attack_declarations: List[dict],
        current_player: Player,
        opponent_player: Player,
    ) -> None:
        grouped: dict[Unit, list] = {}
        for decl in attack_declarations:
            target = decl.get("target_unit")
            if target is None:
                continue
            grouped.setdefault(target, []).append(decl)

        ordered_targets = [t for t in target_units if t in grouped]
        if not ordered_targets:
            logger.info("INFO: No target groups to resolve")
            self._start_consolidate_phase(fighting_unit, current_player, opponent_player)
            return

        index = {"value": 0}

        def _advance():
            while index["value"] < len(ordered_targets):
                target = ordered_targets[index["value"]]
                decls = list(grouped.get(target, []) or [])
                index["value"] += 1
                if not decls:
                    continue
                self._start_target_model_selection_phase(
                    fighting_unit,
                    target,
                    decls,
                    current_player,
                    opponent_player,
                    on_complete=_advance,
                    skip_consolidate=True,
                )
                return
            self._start_consolidate_phase(fighting_unit, current_player, opponent_player)

        _advance()
    
    def _start_weapon_allocation_phase(
        self,
        fighting_unit: Unit,
        target_unit: Unit,
        current_player: Player,
        opponent_player: Player,
        *,
        eligible_models=None,
        on_complete=None,
        skip_consolidate: bool = False,
    ):
        """Handle weapon allocation phase - each model selects one weapon (except EXTRA ATTACKS)."""
        logger.info(f"Starting weapon allocation: {fighting_unit.name} vs {target_unit.name}")
        
        def on_weapon_allocation_complete(weapon_declarations):
            logger.info(f"Weapon allocation completed with {len(weapon_declarations)} declarations")
            self._start_target_model_selection_phase(
                fighting_unit,
                target_unit,
                weapon_declarations,
                current_player,
                opponent_player,
                on_complete=on_complete,
                skip_consolidate=skip_consolidate,
            )
        
        # Show melee weapon declaration dialog for weapon allocation
        def _show_weapons():
            self._request_melee_weapon_declarations(
                fighting_unit,
                target_unit,
                on_weapon_allocation_complete,
                eligible_models=eligible_models,
            )
        if hasattr(self.game_view, "_maybe_prompt_fight_within_3"):
            self.game_view._maybe_prompt_fight_within_3(fighting_unit, target_unit, _show_weapons)
        else:
            _show_weapons()
    
    def _start_target_model_selection_phase(
        self,
        fighting_unit: Unit,
        target_unit: Unit,
        weapon_declarations: List,
        current_player: Player,
        opponent_player: Player,
        *,
        on_complete=None,
        skip_consolidate: bool = False,
    ):
        """Handle target model selection phase."""
        logger.info(f"INFO: Starting target model selection phase")
        
        # NOTE: PRECISION (10e) is *not* "pick a target model up-front".
        # It is an allocation override that happens after a successful wound is allocated.
        # We handle this during attack resolution (see _resolve_single_attack) via the
        # engine-level precision_allocation_provider + PrecisionAllocationDialog.

        # Check if target unit has mixed attributes.
        has_mixed_attributes = self._unit_has_mixed_attributes(target_unit)
        
        if has_mixed_attributes:
            logger.info(f"INFO: Mixed attributes detected - defender selects wound allocation")

            from ...engine.decision_kinds import DECISION_SELECT_TARGET_MODEL
            from ...engine.decisions import DecisionOption, DecisionRequest
            from ...utility.decision_utils import resolve_decision_value
            from ...utility.entity_ids import get_entity_id

            try:
                candidates = list(target_unit.get_models_for_wound_allocation() or [])
            except Exception:
                candidates = [m for m in getattr(target_unit, "models", []) if getattr(m, "is_alive", False)]

            options = [DecisionOption.create("Auto allocation", payload={"model_id": None})]
            for model in list(candidates or []):
                label = getattr(model, "name", "Model")
                options.append(DecisionOption.create(label, payload={"model_id": get_entity_id(model)}))

            req = _require_pending_decision_request(self.game,
                DECISION_SELECT_TARGET_MODEL,
                f"Select wound allocation for {getattr(target_unit, 'name', 'Unit')}",
                player_id=getattr(opponent_player, "id", None),
                options=options,
                context={"unit_id": get_entity_id(target_unit)},

            )

            def _apply_selection(option_id: str):
                value, apply_result = resolve_decision_value(self.game, req, option_id)
                if apply_result is None or not getattr(apply_result, "ok", False):
                    value = None
                if value is not None:
                    logger.info(f"INFO: Wound allocation: {getattr(value, 'name', 'model')} selected to receive wounds")
                    for decl in weapon_declarations:
                        decl['wound_target'] = value
                else:
                    logger.info("INFO: Wound allocation: using automatic allocation")
                self._start_attack_resolution_phase(
                    fighting_unit,
                    target_unit,
                    weapon_declarations,
                    current_player,
                    opponent_player,
                    on_complete=on_complete,
                    skip_consolidate=skip_consolidate,
                )

            auto_option_id = options[0].option_id if options else ""

            def on_wound_model_selected(option_id: str):
                _apply_selection(option_id)

            def on_wound_cancelled():
                _apply_selection(auto_option_id)

            self.game_view.target_model_selection_dialog.show(
                fighting_unit,
                target_unit,
                weapon_declarations,
                "wound_allocation",
                on_wound_model_selected,
                on_wound_cancelled,
                decision_request=req,
            )
            
        else:
            logger.info(f"INFO: No special targeting required - proceeding to attack resolution")
            self._start_attack_resolution_phase(
                fighting_unit,
                target_unit,
                weapon_declarations,
                current_player,
                opponent_player,
                on_complete=on_complete,
                skip_consolidate=skip_consolidate,
            )
    
    def _unit_has_mixed_attributes(self, unit: Unit) -> bool:
        """Check if a unit has models with different toughness, save, or wounds."""
        if len(unit.models) <= 1:
            return False
        
        first_model = unit.models[0]
        for model in unit.models[1:]:
            if (model.toughness != first_model.toughness or 
                model.save != first_model.save or 
                model.wounds != first_model.wounds):
                return True
        return False
    
    def _start_attack_resolution_phase(
        self,
        fighting_unit: Unit,
        target_unit: Unit,
        weapon_declarations: List,
        current_player: Player,
        opponent_player: Player,
        *,
        on_complete=None,
        skip_consolidate: bool = False,
    ):
        """Handle sequential attack resolution."""
        logger.info(f"Starting attack resolution phase")
        
        # Resolve attacks sequentially
        self._resolve_sequential_attacks(fighting_unit, target_unit, weapon_declarations)

        if skip_consolidate:
            if callable(on_complete):
                on_complete()
            return

        self._start_consolidate_phase(fighting_unit, current_player, opponent_player)

    def _start_consolidate_phase(self, fighting_unit: Unit, current_player: Player, opponent_player: Player) -> None:
        """Handle consolidate movement after attacks are resolved."""
        def on_consolidate_complete(completed: bool):
            logger.info(f"INFO: {fighting_unit.name} consolidate completed: {completed}")

            on_bonus = getattr(self, "_bonus_fight_on_complete", None)
            if callable(on_bonus):
                try:
                    self._bonus_fight_on_complete = None
                except Exception:
                    pass
                on_bonus()
                return

            self.fight_phase_manager.finalize_unit_fight(fighting_unit, current_player, opponent_player)

        logger.info(f"INFO: {fighting_unit.name} needs to perform consolidate movement")
        max_distance = 3.0
        try:
            override = fighting_unit.get_fight_phase_move_distance_override("consolidate")
            if override is not None:
                max_distance = float(override)
        except Exception:
            max_distance = 3.0
        self._request_move_unit_decision(
            fighting_unit,
            "consolidate",
            on_consolidate_complete,
            max_distance=max_distance,
        )
    
    def _resolve_sequential_attacks(self, fighting_unit: Unit, target_unit: Unit, weapon_declarations: List):
        """Resolve attacks one at a time with proper wound allocation."""
        logger.info(f"Resolving {len(weapon_declarations)} weapon attacks sequentially")
        fight_manager = self.fight_phase_manager or FightPhaseManager(self.game)
        attack_unit = fighting_unit
        if hasattr(fight_manager, "_as_attached_view"):
            attack_unit = fight_manager._as_attached_view(fighting_unit)
        attack_summary = fight_manager._resolve_melee_attacks(attack_unit, target_unit, weapon_declarations)
        self.game._maybe_trigger_daemonic_poisons(
            attacker_unit=attack_unit,
            hits_by_target=attack_summary.get("hits_by_target"),
            hit_models_by_target=attack_summary.get("hit_models_by_target"),
            phase="fight",
        )
    
    def _get_weapon_attacks(self, weapon_profile) -> int:
        """Get the number of attacks for a weapon profile."""
        attacks = getattr(weapon_profile, 'attacks', 1)
        if hasattr(attacks, 'resolve'):
            # Handle dice-based attacks like "D6" or "2D3"
            return attacks.resolve()
        elif isinstance(attacks, str):
            # Handle string-based attacks
            from ...utility.dice import get_roll
            return get_roll(attacks)
        else:
            return int(attacks) if attacks else 1
    
    def _select_wound_target(self, target_unit: Unit):
        """Select the target model for wound allocation following 40k rules."""
        if not target_unit.is_alive():
            return None

        # Use engine wound-allocation candidates (handles attached units: bodyguard -> leaders)
        try:
            candidates = target_unit.get_models_for_wound_allocation()
        except Exception:
            candidates = [model for model in getattr(target_unit, "models", []) if getattr(model, "is_alive", True)]
        if not candidates:
            return None

        from ...utility.damage_allocation import damage_allocation_choice
        choice = damage_allocation_choice(candidates)
        if choice.forced_model is not None:
            return choice.forced_model
        if choice.choice_models:
            return choice.choice_models[0]
        return None
    
    def _choose_precision_allocation_target(self, attacking_model, target_unit: Unit, weapon_profile):
        """
        If this is a PRECISION weapon attacking an Attached Unit with visible CHARACTER models,
        prompt the attacker (human) once to choose allocation target for the rest of this weapon profile.
        Returns: chosen CHARACTER model, or None to allocate normally (bodyguards).
        """
        # Attached unit root
        try:
            root = target_unit.get_attached_unit_root()
        except Exception:
            root = target_unit

        try:
            has_attached_leaders = bool(getattr(root, "attached_leaders", []) or [])
        except Exception:
            has_attached_leaders = False
        if not has_attached_leaders:
            return None

        # Collect visible CHARACTER models in the attached unit group
        try:
            all_models = root.get_models_for_collision()
        except Exception:
            all_models = list(getattr(root, "models", []) or [])

        char_models = []
        for m in all_models:
            if not getattr(m, "is_alive", True):
                continue
            if not bool(getattr(m, "is_character", False)):
                continue
            # Visibility requirement (only if map supports it)
            gm = getattr(self, "game", None)
            game_map = getattr(gm, "map", None) if gm is not None else None
            can_see = getattr(game_map, "can_model_see_model", None) if game_map is not None else None
            if callable(can_see):
                if not can_see(attacking_model, m):
                    continue
            char_models.append(m)

        if not char_models:
            return None

        gm = getattr(self, "game", None)
        game_map = getattr(gm, "map", None) if gm is not None else None
        return char_models[0]

    def _resolve_single_attack(self, attacking_model, weapon_profile, target_model, target_unit, *, precision_choice_model=None) -> bool:
        """Resolve a single attack and return True if it caused damage."""
        try:
            # Get attack stats
            weapon_skill = getattr(weapon_profile, 'skill', 4)
            strength = getattr(weapon_profile, 'strength', attacking_model.strength if hasattr(attacking_model, 'strength') else 4)
            ap = getattr(weapon_profile, 'ap', 0)
            damage = getattr(weapon_profile, 'damage', 1)
            
            # Roll to hit
            from ...utility.dice import get_roll
            hit_roll = get_roll("1D6")
            hit_needed = weapon_skill
            
            logger.info(f"    INFO: Hit: {hit_roll} vs {hit_needed}+ = {'HIT' if hit_roll >= hit_needed else 'MISS'}")
            
            if hit_roll < hit_needed:
                return False
            
            # Roll to wound
            wound_roll = get_roll("1D6")
            wound_needed = self._calculate_wound_target(strength, target_model.toughness)
            
            logger.info(f"    WOUND: Wound: {wound_roll} vs {wound_needed}+ = {'WOUND' if wound_roll >= wound_needed else 'NO WOUND'}")
            
            if wound_roll < wound_needed:
                return False

            # PRECISION allocation override: after a successful wound, the attacker may allocate
            # that wound to a visible CHARACTER model in the Attached unit.
            if precision_choice_model is not None:
                try:
                    gm = getattr(self, "game", None)
                    game_map = getattr(gm, "map", None) if gm is not None else None
                    can_see = getattr(game_map, "can_model_see_model", None) if game_map is not None else None
                    if getattr(precision_choice_model, "is_alive", True) and (not callable(can_see) or can_see(attacking_model, precision_choice_model)):
                        target_model = precision_choice_model
                        logger.info(f"    INFO: PRECISION allocation: {getattr(target_model, 'name', 'CHARACTER')}")
                except Exception:
                    pass
            
            # Roll save with proper AP and invulnerable consideration
            save_roll = get_roll("1D6")
            # Normalize AP (e.g., -2)
            try:
                ap_value = int(ap)
            except Exception:
                ap_value = 0
            base_save = getattr(target_model, 'save', 7)
            normal_needed = max(base_save - ap_value, 2)

            # Check invulnerable save and whether its condition applies
            effective_needed = normal_needed
            detail_text = f"{base_save}+ with AP {ap_value}"
            if hasattr(target_model, 'inv_save'):
                inv_value, inv_condition = target_model.inv_save
                if inv_value:
                    # Build a minimal attack_instance for condition checks
                    attack_instance = {'weapon_profile': weapon_profile, 'is_mortal': False}
                    cond_ok = True
                    if inv_condition and hasattr(target_model, '_check_invulnerable_save_condition'):
                        try:
                            cond_ok = target_model._check_invulnerable_save_condition(inv_condition, attack_instance)
                        except Exception:
                            cond_ok = True
                    if cond_ok and inv_value < effective_needed:
                        effective_needed = inv_value
                        detail_text = f"{inv_value}+ Invuln"

            # Check invulnerable save from wargear abilities (model-specific).
            try:
                t_unit = getattr(target_model, "parent_unit", None)
                if t_unit is not None and hasattr(t_unit, "get_model_invulnerable_save_override"):
                    inv_override, inv_reason = t_unit.get_model_invulnerable_save_override(target_model)
                    if inv_override and int(inv_override) < effective_needed:
                        effective_needed = int(inv_override)
                        if inv_reason:
                            detail_text = f"{inv_override}+ Invuln ({inv_reason})"
                        else:
                            detail_text = f"{inv_override}+ Invuln"
            except Exception:
                pass

            logger.info(f"     Save: {save_roll} vs {effective_needed}+ ({detail_text}) = {'SAVED' if save_roll >= effective_needed else 'FAILED'}")
            
            if save_roll >= effective_needed:
                return False
            
            # Apply damage using the proper take_damage method
            if isinstance(damage, str):
                damage_dealt = get_roll(damage)
            else:
                damage_dealt = int(damage) if damage else 1
            
            logger.info(f"    ' Damage: {damage_dealt}")
            
            # Use the model's take_damage method which handles FNP, death, etc.
            wounds_before = target_model.wounds
            excess_damage = target_model.take_damage(damage_dealt, is_mortal=False, weapon_profile=weapon_profile)
            actual_damage = wounds_before - target_model.wounds
            
            return actual_damage > 0
            
        except Exception as e:
            logger.exception(f"    ERROR: Attack resolution error: {e}")
            return False
    
    def _calculate_wound_target(self, strength: int, toughness: int) -> int:
        """Calculate the target number needed to wound."""
        if strength >= toughness * 2:
            return 2
        elif strength > toughness:
            return 3
        elif strength == toughness:
            return 4
        elif strength * 2 <= toughness:
            return 6
        else:
            return 5
    
    def get_fight_phase_status(self) -> dict:
        """Get the current fight phase status for UI display"""
        current_player = self.game.get_current_player()
        opponent = self.game.get_opponent()
        
        if self.fight_phase_manager:
            # Use fight phase manager for accurate status
            return self.fight_phase_manager.get_stage_info(current_player, opponent)
        else:
            # Fallback to old logic if manager not initialized
            current_fight_first = self.game.get_fight_first_units(current_player)
            current_remaining = self.game.get_remaining_combatant_units(current_player)
            opponent_fight_first = self.game.get_fight_first_units(opponent)
            opponent_remaining = self.game.get_remaining_combatant_units(opponent)
            
            if current_fight_first or opponent_fight_first:
                current_stage = "Fight First"
            elif current_remaining or opponent_remaining:
                current_stage = "Remaining Combatants"
            else:
                current_stage = "Complete"
            
            return {
                "current_stage": current_stage,
                "active_player": None,
                "current_player_fight_first": len(current_fight_first),
                "current_player_remaining": len(current_remaining),
                "opponent_fight_first": len(opponent_fight_first),
                "opponent_remaining": len(opponent_remaining),
                "fought_units": 0,
                "is_complete": current_stage == "Complete"
            }
    
    def _handle_movement_choice(self, unit, choice: str) -> None:
        """Handle movement choice selection using Unit's movement system"""
        from warhammer40k_ai.units.unit import MovementAction
        
        # Map UI choices to Unit's MovementAction enum
        choice_mapping = {
            'move': MovementAction.MOVE,
            'advance': MovementAction.ADVANCE,
            'fall_back': MovementAction.FALL_BACK,
            'stationary': MovementAction.REMAIN_STATIONARY
        }
        
        if choice not in choice_mapping:
            # Transport actions (not MovementAction enum)
            if choice == 'embark' and getattr(unit, "is_transport", False):
                return self._show_transport_embark_dialog(unit)
            if choice == 'disembark' and getattr(unit, "is_transport", False):
                return self._show_transport_disembark_dialog(unit)
            logger.error(f"ERROR: Invalid movement choice: {choice}")
            return
        
        # Get the unit's current engagement state
        engagement_state = unit.get_engagement_state(self.game.map)
        available_actions = unit.get_available_move_actions(engagement_state.value)
        
        # Check if the chosen action is available
        chosen_action = choice_mapping[choice]
        if chosen_action.value not in available_actions:
            logger.error(f"ERROR: {choice.title()} action not available for {unit.name}")
            return

        def _begin_movement():
            # Store the chosen action for battlefield click handling
            self.game_view.selected_unit_for_movement = unit
            self.game_view.movement_action = chosen_action
            # Keep the selected model if one was previously selected
            if not hasattr(self.game_view, 'selected_model_for_movement'):
                self.game_view.selected_model_for_movement = None

            if choice == 'stationary':
                # Execute stationary action via server decision
                try:
                    from ...engine.decision_kinds import DECISION_SELECT_MOVEMENT_ACTION
                    from ...engine.decisions import DecisionOption, DecisionRequest
                    from ...utility.decision_utils import resolve_decision_command
                    from ...utility.entity_ids import get_entity_id

                    unit_id = get_entity_id(unit)
                    req = _require_pending_decision_request(self.game,
                        DECISION_SELECT_MOVEMENT_ACTION,
                        f"{getattr(unit, 'name', 'Unit')} remains stationary",
                        player_id=getattr(self.game.get_current_player(), "id", None),
                        options=[DecisionOption.create("Confirm", payload={"unit_id": unit_id, "action_type": "stationary"})],
                        context={"unit_id": unit_id},

                    )
                    if req.options:
                        resolve_decision_command(self.game, req, req.options[0].option_id, result_payload={})
                    logger.info(f"INFO: {unit.name} remains stationary")
                except Exception:
                    logger.exception(f"ERROR: Failed to resolve stationary action for {unit.name}")
                # Clear selection since action is complete
                self.game_view.selected_unit_for_movement = None
                self.game_view.movement_action = None
                self.game_view.selected_model_for_movement = None
                return
            if choice == 'advance':
                # Advance roll is requested by the SELECT_MOVEMENT_ACTION decision that was
                # already resolved in _handle_movement_phase_selection. Do not re-request it.
                try:
                    from ...utility.entity_ids import get_entity_id

                    unit_id = get_entity_id(unit)
                    self._pending_advance_units.add(unit_id)
                except Exception:
                    logger.exception(f"ERROR: Failed to stage advance flow for {unit.name}")
                    try:
                        self._pending_advance_units.discard(get_entity_id(unit))
                    except Exception:
                        pass
                # If the roll resolved immediately (headless), open movement now.
                try:
                    if getattr(unit.round_state, "advance_roll", None):
                        self._handle_advance_roll_ready(unit)
                except Exception:
                    pass
                return

            max_distance = unit.movement
            if choice == "move":
                try:
                    max_distance += float(unit.get_phase_movement_distance_bonus("move", game=self.game) or 0)
                except Exception:
                    pass

            if choice != 'stationary':
                from ...engine.decision_kinds import DECISION_MOVE_UNIT
                from ...engine.decisions import DecisionOption, DecisionRequest
                from ...utility.entity_ids import get_entity_id

                unit_id = get_entity_id(unit)
                move_request = _require_pending_decision_request(self.game,
                    DECISION_MOVE_UNIT,
                    f"Move {getattr(unit, 'name', 'Unit')}",
                    player_id=getattr(self.game.get_current_player(), "id", None),
                    options=[
                        DecisionOption.create(
                            "Confirm move",
                            payload={"unit_id": unit_id, "movement_type": choice},
                        )
                    ],
                    context={"unit_id": unit_id, "movement_type": choice, "max_distance": max_distance},

                )

                # Open individual model movement dialog
                def on_movement_complete(completed: bool):
                    from ...engine.command_kinds import CMD_RESOLVE_DECISION
                    from ...engine.commands import GameCommand
                    from ...utility.entity_ids import get_entity_id

                    payload = {"skipped": not completed}
                    if completed:
                        model_positions = []
                        for model in list(getattr(unit, "models", []) or []):
                            if not getattr(model, "is_alive", True):
                                continue
                            loc = model.get_location()
                            if not loc:
                                continue
                            model_positions.append(
                                {
                                    "model_id": get_entity_id(model),
                                    "position": [float(loc[0]), float(loc[1]), float(loc[2])],
                                    "facing": float(getattr(model.model_base, "facing", 0.0)),
                                }
                            )
                        payload["model_positions"] = model_positions
                    cmd_payload = {
                        "decision_id": move_request.decision_id,
                        "option_id": move_request.options[0].option_id if move_request.options else "",
                        "result_payload": payload,
                    }
                    cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=move_request.player_id, payload=cmd_payload)
                    self.game.apply_command(cmd)
                    if completed:
                        logger.info(f"{unit.name} {choice} movement completed")
                    else:
                        logger.info(f"{unit.name} {choice} movement skipped")
                    # Clear selection after movement
                    self.game_view.selected_unit_for_movement = None
                    self.game_view.movement_action = None
                    self.game_view.selected_model_for_movement = None

                self.game_view.individual_model_movement_dialog.show(
                    unit,
                    choice,
                    on_movement_complete,
                    self.game.map,
                    max_distance,
                    decision_request=move_request,
                )

        def _begin_movement_with_move_choice():
            if choice in ("move", "fall_back"):
                from ...engine.decision_kinds import DECISION_CHOOSE_MOVE_MODIFIER_IGNORES
                try:
                    from ...utility.entity_ids import get_entity_id
                    unit_id = get_entity_id(unit)
                except Exception:
                    unit_id = ""
                pending_req = self._pending_decision_for_unit(DECISION_CHOOSE_MOVE_MODIFIER_IGNORES, unit)
                pending_flag = False
                try:
                    pending_flag = bool(getattr(unit.round_state, "move_modifier_choice_pending", False))
                except Exception:
                    pending_flag = False
                if pending_req is not None or pending_flag:
                    if unit_id:
                        self._pending_move_modifier_actions[str(unit_id)] = {"callback": _begin_movement}
                    if pending_req is not None:
                        self._register_decision_callback(
                            pending_req,
                            lambda _req, _res, uid=str(unit_id): self._resume_pending_move_modifier_action(uid),
                        )
                    return
            _begin_movement()

        def _maybe_begin_advance_redeploy_placement() -> bool:
            if choice not in ("move", "advance"):
                return False
            if self.game is None or unit is None:
                return False
            from ...engine.decision_kinds import DECISION_MOVE_UNIT
            try:
                from ...utility.entity_ids import get_entity_id
                unit_id = get_entity_id(unit)
            except Exception:
                unit_id = ""
            if not unit_id:
                return False
            queue = getattr(self.game, "decision_queue", None)
            if queue is None or not hasattr(queue, "list"):
                return False
            pending_req = None
            expected_kind = "advance_redeploy_9h" if choice == "advance" else "normal_move_redeploy_9h"
            for req in list(queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_MOVE_UNIT:
                    continue
                ctx = dict(getattr(req, "context", {}) or {})
                if str(ctx.get("placement_kind", "") or "") != expected_kind:
                    continue
                if str(ctx.get("unit_id", "") or "") != str(unit_id):
                    continue
                pending_req = req
                break
            if pending_req is None:
                return False

            def _on_complete(_completed: bool):
                self._pending_advance_units.discard(str(unit_id))
                self.game_view.selected_unit_for_movement = None
                self.game_view.movement_action = None
                self.game_view.selected_model_for_movement = None

            self._request_move_unit_decision(
                unit,
                "advance" if choice == "advance" else "move",
                _on_complete,
                decision_request=pending_req,
            )
            return True

        def _maybe_prompt_pre_normal_move_ability(next_step) -> bool:
            if choice not in ("move", "advance"):
                return False
            if self.game is None or unit is None:
                return False
            try:
                from ...utility.entity_ids import get_entity_id
                unit_id = get_entity_id(unit)
            except Exception:
                unit_id = ""

            has_ability = False
            ability_key = ""
            queue_method = None
            if choice == "move":
                try:
                    specs = unit.unit_movement_phase_normal_move_redeploy_specs() or []
                except Exception:
                    specs = []
                for spec in list(specs or []):
                    once_key = str(spec.get("ability_key", "") or "").strip().lower()
                    if once_key and bool(getattr(unit, "has_used_unit_once_per_battle", lambda _k: False)(once_key)):
                        continue
                    has_ability = True
                    ability_key = "normal_move_redeploy"
                    queue_method = "_queue_movement_phase_normal_move_redeploy"
                    break
                if not has_ability:
                    try:
                        specs = unit.unit_movement_phase_normal_move_speed_mortal_wounds_specs() or []
                    except Exception:
                        specs = []
                    if specs:
                        has_ability = True
                        ability_key = "flickerjump"
                        queue_method = "_queue_movement_phase_flickerjump"
                if not has_ability:
                    try:
                        models = list(getattr(unit, "models", []) or [])
                    except Exception:
                        models = []
                    for m in models:
                        if not getattr(m, "is_alive", True):
                            continue
                        try:
                            specs = unit.model_movement_phase_normal_move_weapon_attacks_bonus_specs(m) or []
                        except Exception:
                            specs = []
                        if not specs:
                            continue
                        for spec in specs:
                            key = str(spec.get("key") or "movement_phase_normal_move_bonus").strip().lower()
                            if not key:
                                key = "movement_phase_normal_move_bonus"
                            if getattr(m, "has_used_once_per_battle", lambda _k: False)(key):
                                continue
                            has_ability = True
                            ability_key = "movement_phase_move_weapon_bonus"
                            queue_method = "_queue_movement_phase_normal_move_weapon_attacks_bonus"
                            break
                        if has_ability:
                            break
            else:
                try:
                    specs = unit.unit_movement_phase_advance_redeploy_specs() or []
                except Exception:
                    specs = []
                if specs:
                    has_ability = True
                    ability_key = "advance_redeploy"
                    queue_method = "_queue_movement_phase_advance_redeploy"
            if not has_ability:
                return False

            if bool(getattr(self.game, "is_authoritative", True)):
                try:
                    queue_fn = getattr(self.game, queue_method or "", None)
                    if callable(queue_fn):
                        queue_fn(player=self.game.get_current_player(), unit=unit)
                except Exception:
                    pass

            pending_req = None
            queue = getattr(self.game, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                from ...engine.decision_kinds import DECISION_CONFIRM_YES_NO
                for req in list(queue.list() or []):
                    if getattr(req, "decision_type", None) != DECISION_CONFIRM_YES_NO:
                        continue
                    ctx = getattr(req, "context", {}) or {}
                    if str(ctx.get("ability", "") or "") != ability_key:
                        continue
                    if unit_id and str(ctx.get("unit_id", "")) != str(unit_id):
                        continue
                    pending_req = req
                    break

            if pending_req is None:
                return False

            if unit_id:
                self._pending_pre_move_ability_actions[str(unit_id)] = {"callback": next_step}

            if pending_req is not None:
                try:
                    player = self.game.get_current_player()
                except Exception:
                    player = None
                try:
                    if player is not None and getattr(player, "has_control", lambda: False)():
                        dlg = getattr(self.game_view, "yes_no_dialog", None)
                        if dlg is not None and not (dlg.visible and getattr(dlg, "decision_request", None) is pending_req):
                            from ...utility.decision_utils import resolve_decision_command
                            title = str(getattr(pending_req, "prompt", "") or "Confirm")
                            ctx = dict(getattr(pending_req, "context", {}) or {})
                            message = str(ctx.get("message", "") or ctx.get("ability_name", "") or title)

                            def _done(option_id: str):
                                if option_id:
                                    resolve_decision_command(self.game, pending_req, option_id, player_id=getattr(player, "id", None))
                                try:
                                    dlg.hide()
                                except Exception:
                                    pass

                            dlg.show(title, message, _done, decision_request=pending_req)
                            try:
                                self.game_view.dialog_manager.open(dlg, modal=True)
                            except Exception:
                                pass
                except Exception:
                    pass
            return True

        def _begin_movement_after_pre_ability():
            if _maybe_begin_advance_redeploy_placement():
                return
            _begin_movement_with_move_choice()

        def _begin_movement_with_pre_ability():
            if _maybe_prompt_pre_normal_move_ability(_begin_movement_after_pre_ability):
                return
            _begin_movement_after_pre_ability()

        if choice in ("move", "advance", "fall_back"):
            self.game_view._maybe_prompt_battle_focus_move(unit, choice, _begin_movement_with_pre_ability)
        else:
            _begin_movement_with_pre_ability()

    def _on_roll_made(self, player=None, unit=None, roll_type: str = "", **kwargs) -> None:
        if unit is None:
            return
        try:
            if player is not None and not bool(getattr(player, "has_control", lambda: False)()):
                return
        except Exception:
            return
        roll_type = str(roll_type or "").strip().lower()
        if roll_type == "advance":
            self._handle_advance_roll_ready(unit)

    def _handle_advance_roll_ready(self, unit) -> None:
        try:
            unit_id = get_entity_id(unit)
        except Exception:
            return
        if unit_id not in self._pending_advance_units:
            return
        from ...engine.decision_kinds import (
            DECISION_CHOOSE_ADVANCE_MODIFIER_IGNORES,
            DECISION_CHOOSE_MOVE_MODIFIER_IGNORES,
        )
        pending_adv_req = self._pending_decision_for_unit(DECISION_CHOOSE_ADVANCE_MODIFIER_IGNORES, unit)
        pending_move_req = self._pending_decision_for_unit(DECISION_CHOOSE_MOVE_MODIFIER_IGNORES, unit)
        pending_adv_flag = False
        pending_move_flag = False
        try:
            pending_adv_flag = bool(getattr(unit.round_state, "advance_modifier_choice_pending", False))
            pending_move_flag = bool(getattr(unit.round_state, "move_modifier_choice_pending", False))
        except Exception:
            pending_adv_flag = False
            pending_move_flag = False
        if pending_adv_req is not None or pending_move_req is not None or pending_adv_flag or pending_move_flag:
            return
        self._pending_advance_units.discard(unit_id)
        try:
            advance_roll = int(getattr(getattr(unit, "round_state", None), "advance_roll", 0) or 0)
        except Exception:
            advance_roll = 0
        if advance_roll <= 0:
            return
        max_distance = float(getattr(unit, "movement", 0) or 0) + float(advance_roll)

        def _on_complete(completed: bool):
            if completed:
                logger.info(f"{unit.name} advance movement completed")
            else:
                logger.info(f"{unit.name} advance movement skipped")
            self.game_view.selected_unit_for_movement = None
            self.game_view.movement_action = None
            self.game_view.selected_model_for_movement = None

        self._request_move_unit_decision(unit, "advance", _on_complete, max_distance=max_distance)

    def _show_transport_embark_dialog(self, transport_unit) -> None:
        """Show a dialog listing only valid units that can embark into the selected transport."""
        from ..dialogs import TransportEmbarkDialog
        from ...utility.movement_utils import compute_embark_candidates
        from ...engine.command_kinds import CMD_RESOLVE_DECISION
        from ...engine.commands import GameCommand
        from ...engine.decision_kinds import DECISION_EMBARK
        from ...engine.decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        # Compute candidates using the same checks as the dialog (but here so it stays correct even if dialog not refreshed)
        candidates = compute_embark_candidates(transport_unit, self.game.map)

        if not hasattr(self.game_view, "transport_embark_dialog"):
            self.game_view.transport_embark_dialog = TransportEmbarkDialog(
                self.game_view.screen.get_width(),
                self.game_view.screen.get_height(),
            )

        pending = [
            req for req in list(self.game.decision_queue.list() or [])
            if getattr(req, "decision_type", None) == DECISION_EMBARK
            and str(getattr(req, "context", {}).get("transport_id", "")) == get_entity_id(transport_unit)
        ]
        unit_requests = {}
        if pending:
            for req in pending:
                unit_id = str(getattr(req, "context", {}).get("unit_id", ""))
                if unit_id:
                    unit_requests[unit_id] = req
        else:
            for unit in candidates:
                unit_id = get_entity_id(unit)
                options = [
                    DecisionOption.create(
                        "Embark",
                        payload={"unit_id": unit_id, "transport_id": get_entity_id(transport_unit)},
                    ),
                    DecisionOption.create(
                        "Do not embark",
                        payload={"unit_id": unit_id, "transport_id": None},
                    ),
                ]
                req = _require_pending_decision_request(self.game,
                    DECISION_EMBARK,
                    f"Embark {getattr(unit, 'name', 'Unit')}",
                    player_id=getattr(self.game.get_current_player(), "id", None),
                    options=options,
                    context={"unit_id": unit_id, "transport_id": get_entity_id(transport_unit)},

                )
                unit_requests[unit_id] = req

        req_candidates = []
        for unit in candidates:
            if get_entity_id(unit) in unit_requests:
                req_candidates.append(unit)

        def _option_id(req, embark: bool) -> str:
            for opt in list(getattr(req, "options", []) or []):
                payload = dict(getattr(opt, "payload", {}) or {})
                if embark and payload.get("transport_id") is not None:
                    return opt.option_id
                if not embark and payload.get("transport_id") is None:
                    return opt.option_id
            return ""

        def _confirm(selected_units):
            selected_ids = {get_entity_id(u) for u in list(selected_units or [])}
            for unit_id, req in unit_requests.items():
                embark = unit_id in selected_ids
                option_id = _option_id(req, embark)
                if not option_id:
                    continue
                payload = {
                    "decision_id": req.decision_id,
                    "option_id": option_id,
                    "result_payload": {},
                }
                cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
                self.game.apply_command(cmd)

        def _cancel():
            for unit_id, req in unit_requests.items():
                option_id = _option_id(req, False)
                if not option_id:
                    continue
                payload = {
                    "decision_id": req.decision_id,
                    "option_id": option_id,
                    "result_payload": {},
                }
                cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
                self.game.apply_command(cmd)

        self.game_view.transport_embark_dialog.show(transport_unit, req_candidates, _confirm, _cancel)

    def _show_transport_disembark_dialog(self, transport_unit) -> None:
        """Show a dialog to pick which embarked unit(s) to disembark from this transport."""
        from ..dialogs import TransportDisembarkDialog
        from ...engine.command_kinds import CMD_RESOLVE_DECISION
        from ...engine.commands import GameCommand
        from ...engine.decision_kinds import DECISION_DISEMBARK
        from ...engine.decisions import DecisionOption, DecisionRequest
        from ...utility.entity_ids import get_entity_id

        passengers = list(getattr(transport_unit, "transport_passengers", []) or [])
        if not passengers:
            logger.error(f"ERROR: {transport_unit.name} has no embarked units")
            return

        if not hasattr(self.game_view, "transport_disembark_dialog"):
            self.game_view.transport_disembark_dialog = TransportDisembarkDialog(
                self.game_view.screen.get_width(),
                self.game_view.screen.get_height(),
            )

        pending = [
            req for req in list(self.game.decision_queue.list() or [])
            if getattr(req, "decision_type", None) == DECISION_DISEMBARK
            and str(getattr(req, "context", {}).get("transport_id", "")) == get_entity_id(transport_unit)
        ]
        unit_requests = {}
        if pending:
            for req in pending:
                unit_id = str(getattr(req, "context", {}).get("unit_id", ""))
                if unit_id:
                    unit_requests[unit_id] = req
        else:
            for unit in passengers:
                unit_id = get_entity_id(unit)
                options = [
                    DecisionOption.create(
                        "Disembark",
                        payload={"unit_id": unit_id, "transport_id": get_entity_id(transport_unit)},
                    ),
                    DecisionOption.create(
                        "Remain embarked",
                        payload={"unit_id": unit_id, "transport_id": None},
                    ),
                ]
                req = _require_pending_decision_request(self.game,
                    DECISION_DISEMBARK,
                    f"Disembark {getattr(unit, 'name', 'Unit')}",
                    player_id=getattr(self.game.get_current_player(), "id", None),
                    options=options,
                    context={"unit_id": unit_id, "transport_id": get_entity_id(transport_unit)},

                )
                unit_requests[unit_id] = req

        def _option_id(req, disembark: bool) -> str:
            for opt in list(getattr(req, "options", []) or []):
                payload = dict(getattr(opt, "payload", {}) or {})
                if disembark and payload.get("transport_id") is not None:
                    return opt.option_id
                if not disembark and payload.get("transport_id") is None:
                    return opt.option_id
            return ""

        def _confirm(selected_units):
            selected_ids = {get_entity_id(u) for u in list(selected_units or [])}
            for unit_id, req in unit_requests.items():
                disembark = unit_id in selected_ids
                option_id = _option_id(req, disembark)
                if not option_id:
                    continue
                payload = {
                    "decision_id": req.decision_id,
                    "option_id": option_id,
                    "result_payload": {},
                }
                cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
                self.game.apply_command(cmd)

        def _cancel():
            for unit_id, req in unit_requests.items():
                option_id = _option_id(req, False)
                if not option_id:
                    continue
                payload = {
                    "decision_id": req.decision_id,
                    "option_id": option_id,
                    "result_payload": {},
                }
                cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=payload)
                self.game.apply_command(cmd)

        self.game_view.transport_disembark_dialog.show(transport_unit, passengers, _confirm, _cancel)
    
    def _handle_battlefield_action(self, x: int, y: int) -> bool:
        """Handle battlefield actions based on current battle phase"""
        current_phase = self.game.phase
        
        # Phase-specific actions
        if current_phase.name == 'MOVEMENT_PHASE':
            return self._handle_movement_action(x, y)
        elif current_phase.name == 'SHOOTING_PHASE':
            return self._handle_shooting_action(x, y)
        elif current_phase.name == 'CHARGE_PHASE':
            return self._handle_charge_action(x, y)
        elif current_phase.name == 'FIGHT_PHASE':
            return self._handle_fight_action(x, y)
        
        return False
    
    def _handle_movement_action(self, x: int, y: int) -> bool:
        """Handle movement phase actions using Unit's movement system"""
        # Check if individual model movement dialog is active
        if (hasattr(self.game_view, 'individual_model_movement_dialog') and
            self.game_view.individual_model_movement_dialog.visible):
            # Handle battlefield click for individual model movement using helper method
            battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)
            battlefield_z = self.game.map.get_height_at_point(battlefield_x, battlefield_y)
            
            return self.game_view.individual_model_movement_dialog.handle_battlefield_click(
                battlefield_x, battlefield_y, battlefield_z
            )
        
        # Check if we clicked on a model first for selection
        clicked_model = self.game_view.get_model_at_position(x, y)
        if clicked_model:
            # Try to select this unit for movement and track the specific model
            clicked_unit = clicked_model.parent_unit
            self.game_view.selected_unit = clicked_unit
            self.game_view.selected_model_for_movement = clicked_model  # Track the specific model
            self._handle_unit_selection(clicked_unit)
            return True
        
        # Old unit-level movement handling removed - now using Individual Model Movement Dialog for all movement
        
        return False
    
    # Old movement validation method removed - now using Individual Model Movement Dialog for all movement
    
    def _handle_shooting_action(self, x: int, y: int) -> bool:
        """Handle shooting phase actions - allow clicking on units to select them for shooting"""
        # Check if we're in targeting mode from the shooting declaration dialog
        if (hasattr(self.game_view, 'shooting_declaration_dialog') and 
            self.game_view.shooting_declaration_dialog.is_targeting_mode):
            # Let the dialog handle the targeting (expects game coords)
            battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)
            return self.game_view.shooting_declaration_dialog.handle_battlefield_targeting(battlefield_x, battlefield_y)
        
        # If not in targeting mode, handle unit selection
        clicked_unit = self.game_view.get_unit_at_position(x, y)
        if clicked_unit:
            # Try to select this unit for shooting
            self.game_view.selected_unit = clicked_unit
            self._handle_unit_selection(clicked_unit)
            return True
        
        return False
    
    def _show_weapon_choice_dialog(self, unit):
        """Show weapon selection dialog for the unit"""
        if not hasattr(self.game_view, 'weapon_choice_dialog'):
            from ..dialogs import WeaponChoiceDialog
        self.game_view.weapon_choice_dialog = WeaponChoiceDialog(
                self.game_view.screen.get_width(), 
                self.game_view.screen.get_height()
            )

        from ...engine.decision_kinds import DECISION_SELECT_WEAPON
        from ...engine.decisions import DecisionOption, DecisionRequest
        from ...utility.decision_utils import resolve_decision_value
        from ...utility.entity_ids import get_entity_id
        from ..dialogs.weapon_choice_dialog import collect_available_weapons

        available_weapons = collect_available_weapons(unit)
        options = []
        unit_id = get_entity_id(unit)
        for info in available_weapons:
            wargear = info.get("wargear")
            profile_name = info.get("profile_name")
            if wargear is None or not profile_name:
                continue
            try:
                wname = str(getattr(wargear, "name", "Weapon") or "Weapon")
            except Exception:
                wname = "Weapon"
            label = wname
            if len(getattr(wargear, "profiles", {}) or {}) > 1:
                label = f"{label} ({profile_name})"
            options.append(
                DecisionOption.create(
                    label,
                    payload={
                        "unit_id": unit_id,
                        "wargear_id": get_entity_id(wargear),
                        "profile_name": str(profile_name),
                    },
                )
            )
        if not options:
            return
        req = _require_pending_decision_request(self.game,
            DECISION_SELECT_WEAPON,
            f"Select weapon for {getattr(unit, 'name', 'Unit')}",
            player_id=getattr(self.game.get_current_player(), "id", None),
            options=options,
            context={"unit_id": unit_id},

        )

        def on_weapon_choice(option_id: str):
            value, _apply = resolve_decision_value(self.game, req, option_id)
            weapon_profile = None
            if isinstance(value, dict):
                wargear_id = value.get("wargear_id")
                profile_name = value.get("profile_name")
                registry = getattr(self.game, "entity_registry", None)
                wargear = registry.get(str(wargear_id), kind="wargear") if registry is not None else None
                if wargear is not None:
                    weapon_profile = getattr(wargear, "profiles", {}).get(str(profile_name))
            self.game_view.selected_weapon_profile = weapon_profile
            # Clear any previous shooting selection state
            if hasattr(self.game_view, 'selected_shooting_models'):
                self.game_view.selected_shooting_models = []
        
        self.game_view.weapon_choice_dialog.show(unit, on_weapon_choice, self.game.map, decision_request=req)
    
    def _clear_shooting_selection(self):
        """Clear shooting selection state"""
        if hasattr(self.game_view, 'selected_weapon_profile'):
            self.game_view.selected_weapon_profile = None
        if hasattr(self.game_view, 'selected_shooting_models'):
            self.game_view.selected_shooting_models = []
    
    def _validate_shooting_target(self, shooting_unit, target_unit, weapon_profile) -> dict:
        """Validate if shooting unit can target the enemy unit with the selected weapon"""
        # Check if target is an enemy unit
        if target_unit.get_parent_army() == shooting_unit.get_parent_army():
            return {"valid": False, "reason": "Cannot target friendly units"}
        
        # Check if target is alive
        if not target_unit.is_alive():
            return {"valid": False, "reason": "Target unit is destroyed"}
        
        # Check if unit can shoot (not advanced unless allowed, not fell back, etc.)
        if shooting_unit.round_state.advanced_this_round:
            # Unit method already checks both weapon-specific and unit-specific abilities
            if not shooting_unit.can_shoot_after_advance(weapon_profile):
                return {"valid": False, "reason": "Unit advanced and cannot shoot with this weapon"}
        
        if shooting_unit.round_state.fell_back_this_round:
            if not shooting_unit.can_shoot_after_fall_back(weapon_profile):
                return {"valid": False, "reason": "Unit fell back and cannot shoot with this weapon"}
        
        # Check if any models in the unit can shoot this weapon at the target
        models_in_range = []
        game_map = getattr(self.game, "map", None)
        for model in shooting_unit.models:
            if not model.is_alive:
                continue
                
            # Check if this model has the weapon
            has_weapon = False
            for wargear in model.wargear:
                if weapon_profile.parent_wargear == wargear:
                    has_weapon = True
                    break
            
            if not has_weapon:
                continue
            
            can_shoot = None
            can_shoot_fn = getattr(shooting_unit, "_can_model_shoot_weapon_at_target", None)
            if game_map is not None and callable(can_shoot_fn):
                can_shoot = bool(can_shoot_fn(model, weapon_profile, target_unit, game_map))
            if can_shoot is None:
                # Fallback: range + basic LOS check
                closest_target_model, distance = model.return_closest_model_in_unit(target_unit)
                if distance <= weapon_profile.range.max:
                    if self._has_line_of_sight(model, closest_target_model):
                        can_shoot = True
                    else:
                        can_shoot = False
                else:
                    can_shoot = False
            if can_shoot:
                models_in_range.append(model)
        
        if not models_in_range:
            return {"valid": False, "reason": "No models in range with line of sight"}
        
        return {"valid": True, "reason": f"{len(models_in_range)} models can shoot"}
    
    def _has_line_of_sight(self, shooting_model, target_model) -> bool:
        """Line of sight check using engine-level geometry where available."""
        game_map = getattr(self.game, "map", None)
        shooter_unit = getattr(shooting_model, "parent_unit", None)
        target_unit = getattr(target_model, "parent_unit", None)
        if game_map is not None and shooter_unit is not None and target_unit is not None:
            fn = getattr(shooter_unit, "_has_line_of_sight_to_target", None)
            if callable(fn):
                return bool(fn(shooting_model, target_unit, game_map))
        if game_map is not None:
            can_see = getattr(game_map, "can_model_see_model", None)
            if callable(can_see):
                return bool(can_see(shooting_model, target_model))
        return True
    
    def _handle_charge_action(self, x: int, y: int) -> bool:
        """Handle charge phase actions"""
        # Check if individual model movement dialog is active (for charge movement)
        if (hasattr(self.game_view, 'individual_model_movement_dialog') and
            self.game_view.individual_model_movement_dialog.visible):
            # Handle battlefield click for individual model movement during charge using helper method
            battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)
            battlefield_z = self.game.map.get_height_at_point(battlefield_x, battlefield_y)

            return self.game_view.individual_model_movement_dialog.handle_battlefield_click(
                battlefield_x, battlefield_y, battlefield_z
            )

        # Always check if a unit was clicked on the battlefield first
        clicked_unit = self.game_view.get_unit_at_position(x, y)
        current_player = self.game.get_current_player()
        if clicked_unit and clicked_unit.get_parent_army() and clicked_unit.get_parent_army().player == current_player:
            self.game_view.selected_unit = clicked_unit
            self._synchronize_unit_selection(clicked_unit)
            self._handle_charge_phase_selection(clicked_unit)
            return True
        # If no unit was clicked, fall back to selected unit (e.g., from RosterPane)
        if self.game_view.selected_unit:
            if self.game_view.selected_unit.get_parent_army() and self.game_view.selected_unit.get_parent_army().player == current_player:
                self._handle_charge_phase_selection(self.game_view.selected_unit)
                return True
        return False
    
    def _handle_fight_action(self, x: int, y: int) -> bool:
        """Handle fight phase actions"""
        current_player = self.game.get_current_player()
        opponent_player = self.game.get_opponent()
        
        # Initialize fight phase manager if not already done
        if not self.fight_phase_manager:
            self._initialize_fight_phase_manager(current_player, opponent_player)
        
        # If fight phase manager is still None after initialization, fight phase is complete
        if not self.fight_phase_manager:
            logger.info("OK: Fight phase is complete - no actions available")
            return False
        
        # Always check if a unit was clicked on the battlefield first
        clicked_unit = self.game_view.get_unit_at_position(x, y)
        
        # If a unit was clicked, check if it's a friendly unit to select for fighting
        if clicked_unit and clicked_unit.get_parent_army():
            unit_owner = clicked_unit.get_parent_army().player
            active_player = self.fight_phase_manager.get_active_player()
            
            # Check if this is the active player's unit
            if unit_owner == active_player:
                self.game_view.selected_unit = clicked_unit
                self._synchronize_unit_selection(clicked_unit)
                self._handle_fight_phase_selection(clicked_unit)
                return True
            else:
                logger.error(f"ERROR: It's {active_player.name}'s turn to select a unit, not {unit_owner.name}'s")
                return False
        
        # If no unit was clicked, fall back to selected unit (e.g., from RosterPane)
        if self.game_view.selected_unit:
            unit_owner = self.game_view.selected_unit.get_parent_army().player if self.game_view.selected_unit.get_parent_army() else None
            active_player = self.fight_phase_manager.get_active_player()
            
            if unit_owner == active_player:
                self._handle_fight_phase_selection(self.game_view.selected_unit)
                return True
            else:
                logger.error(f"ERROR: It's {active_player.name}'s turn to select a unit, not {unit_owner.name}'s")
                return False
        
        return False
    
    def get_allowed_actions(self) -> List[str]:
        current_phase = self.game.phase
        current_player = self.game.get_current_player()
        
        # Base actions available in all phases
        base_actions = ["view_unit_details", "advance_phase"]
        
        # Only allow unit selection for local control
        if current_player.has_control():
            base_actions.append("select_unit")
        
        # Phase-specific actions
        if current_phase.name == 'MOVEMENT_PHASE':
            if current_player.has_control():
                return base_actions + ["move_unit", "advance_unit", "remain_stationary", "fall_back"]
            else:
                return base_actions
        elif current_phase.name == 'SHOOTING_PHASE':
            if current_player.has_control():
                return base_actions + ["select_weapon", "target_unit", "cancel_shooting"]
            else:
                return base_actions
        elif current_phase.name == 'CHARGE_PHASE':
            if current_player.has_control():
                return base_actions + ["declare_charge", "charge_move"]
            else:
                return base_actions
        elif current_phase.name == 'FIGHT_PHASE':
            if current_player.has_control():
                return base_actions + ["pile_in", "fight", "consolidate"]
            else:
                return base_actions
        else:
            return base_actions
    
    def _handle_battle_motion(self, mouse_pos) -> bool:
        """Handle mouse motion during battle phases"""
        x, y = mouse_pos
        # print(f"DEBUG: _handle_battle_motion called with ({x}, {y})")

        # Individual model movement tracking now has priority over old systems

        # Update hover states for UI components
        if hasattr(self.game_view, 'shooting_declaration_dialog') and self.game_view.shooting_declaration_dialog.visible:
            self.game_view.shooting_declaration_dialog.update_hover((x, y))
            return True

        if hasattr(self.game_view, 'movement_choice_dialog') and self.game_view.movement_choice_dialog.visible:
            self.game_view.movement_choice_dialog.update_hover((x, y))
            return True

        # Old unit-level movement tracking removed - now using Individual Model Movement Dialog for all movement

        # Track mouse position for individual model movement preview


        if (hasattr(self.game_view, 'individual_model_movement_dialog') and
            self.game_view.individual_model_movement_dialog.visible and
            self.game_view.individual_model_movement_dialog.selected_model_index is not None):

            logger.debug(f"DEBUG: Individual model movement tracking active at ({x}, {y})")

            # Check if mouse is over battlefield area
            if self.game_view.battlefield_left < x < self.game_view.battlefield_right:
                # Convert to game coordinates using helper method
                battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)

                # Store mouse position for individual model movement preview
                self.game_view.individual_model_preview_target = (battlefield_x, battlefield_y)
                logger.debug(f"DEBUG: Set preview target to ({battlefield_x:.1f}, {battlefield_y:.1f})")
                return True
            else:
                # Clear preview when mouse leaves battlefield
                self.game_view.individual_model_preview_target = None
                # print(f"DEBUG: Cleared preview target (mouse outside battlefield)")
        else:
            # Debug why tracking isn't active
            if hasattr(self.game_view, 'individual_model_movement_dialog'):
                dialog = self.game_view.individual_model_movement_dialog
                # print(f"DEBUG: Dialog exists - visible: {dialog.visible}, selected_model: {dialog.selected_model_index}")
            else:
                logger.debug(f"DEBUG: No individual_model_movement_dialog found")

        # Update roster pane hovers
        if self.game_view.left_roster_pane.rect.collidepoint(x, y):
            return True
        elif self.game_view.right_roster_pane.rect.collidepoint(x, y):
            return True

        return False
    
    def _handle_battle_release(self, mouse_pos, button) -> bool:
        """Handle mouse button release during battle phases"""
        # Currently no specific handling needed for mouse release
        return False

class PhaseManager:
    """Manages phase-specific event handling"""
    
    def __init__(self, game_view: 'GameView'):
        self.game_view = game_view
        self.game = game_view.game
        # Initialize phase handlers
        self.setup_handler = SetupPhaseHandler(game_view)
        self.deployment_handler = DeploymentPhaseHandler(game_view)
        self.prebattle_handler = PreBattlePhaseHandler(game_view)
        self.battle_handler = BattlePhaseHandler(game_view)
        
        # Movement system state
        from ..dialogs import MovementChoiceDialog, IndividualModelMovementDialog
        from ..dialogs.coherency_violation_dialog import CoherencyViolationDialog
        self.game_view.movement_choice_dialog = MovementChoiceDialog(game_view.screen.get_width(), game_view.screen.get_height())
        self.game_view.individual_model_movement_dialog = IndividualModelMovementDialog(game_view.screen.get_width(), game_view.screen.get_height())
        self.game_view.coherency_violation_dialog = CoherencyViolationDialog(game_view.screen.get_width(), game_view.screen.get_height())
        self.game_view.selected_unit_for_movement = None
        self.game_view.movement_action = None  # MovementAction enum value
        self.game_view.movement_preview_target = None  # For real-time movement preview
        
        # Shooting system state
        from ..dialogs import ShootingDeclarationDialog
        self.game_view.shooting_declaration_dialog = ShootingDeclarationDialog(game_view.screen.get_width(), game_view.screen.get_height())
        
        # Charge system state
        from ..dialogs import ChargeDeclarationDialog
        self.game_view.charge_declaration_dialog = ChargeDeclarationDialog(game_view.screen.get_width(), game_view.screen.get_height())
        
        # Melee weapon declaration system state
        from ..dialogs import MeleeWeaponDeclarationDialog, MeleeWeaponTargetAllocationDialog, MeleeAttackSplitDialog
        self.game_view.melee_weapon_declaration_dialog = MeleeWeaponDeclarationDialog(game_view.screen.get_width(), game_view.screen.get_height())

        # Melee target allocation dialog for multi-target fights
        from ..dialogs import MeleeTargetAllocationDialog
        self.game_view.melee_target_allocation_dialog = MeleeTargetAllocationDialog(game_view.screen.get_width(), game_view.screen.get_height())
        self.game_view.melee_weapon_target_allocation_dialog = MeleeWeaponTargetAllocationDialog(game_view.screen.get_width(), game_view.screen.get_height())
        self.game_view.melee_attack_split_dialog = MeleeAttackSplitDialog(game_view.screen.get_width(), game_view.screen.get_height())
        
        # Fight target selection dialog
        from ..dialogs.fight_target_selection_dialog import FightTargetSelectionDialog
        self.game_view.fight_target_selection_dialog = FightTargetSelectionDialog(game_view.screen.get_width(), game_view.screen.get_height())

        # Exploding Horrors model selection dialog
        from ..dialogs.exploding_horrors_model_selection_dialog import ExplodingHorrorsModelSelectionDialog
        self.game_view.exploding_horrors_model_selection_dialog = ExplodingHorrorsModelSelectionDialog(game_view.screen.get_width(), game_view.screen.get_height())
        
        # Target model selection dialog
        from ..dialogs.target_model_selection_dialog import TargetModelSelectionDialog
        self.game_view.target_model_selection_dialog = TargetModelSelectionDialog(game_view.screen.get_width(), game_view.screen.get_height())

    def get_current_handler(self) -> BasePhaseHandler:
        """Get the appropriate handler for the current game phase"""
        if self.game.is_in_setup_phase():
            current_setup_phase = self.game.get_current_setup_phase()
            if current_setup_phase.name == 'DEPLOY_ARMIES':
                return self.deployment_handler
            elif current_setup_phase.name == 'RESOLVE_PREBATTLE_RULES':
                # Start the scout phase if not already started for this phase
                if not hasattr(self.prebattle_handler, 'scout_phase_started') or not self.prebattle_handler.scout_phase_started:
                    logger.info("Starting scout phase...")
                    self.prebattle_handler.scout_phase_started = bool(self.prebattle_handler.start_scout_phase())
                return self.prebattle_handler
            else:
                return self.setup_handler
        elif self.game.is_deployment_phase():
            return self.deployment_handler
        else:
            # Battle phases
            # Auto-start fight phase if we're in fight phase and it hasn't been started
            if self.game.is_fight_phase():
                if not hasattr(self.battle_handler, 'fight_phase_started') or not self.battle_handler.fight_phase_started:
                    logger.info("Auto-starting fight phase...")
                    current_player = self.game.get_current_player()
                    opponent_player = self.game.get_opponent()
                    self.battle_handler._initialize_fight_phase_manager(current_player, opponent_player)
                    self.battle_handler.fight_phase_started = True
            else:
                # Reset fight phase flag when not in fight phase
                if hasattr(self.battle_handler, 'fight_phase_started'):
                    self.battle_handler.fight_phase_started = False
            return self.battle_handler
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Route event to appropriate phase handler"""
        # Global dialog routing (modal stack) always goes first.
        try:
            if hasattr(self.game_view, "dialog_manager") and self.game_view.dialog_manager:
                if self.game_view.dialog_manager.handle_event(event):
                    return True
        except Exception:
            pass

        handler = self.get_current_handler()
        handler_name = handler.__class__.__name__

        # Debug: Log which handler is being used
        # TODO: Uncomment for event debugging
        # if event.type in [pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION]:
        #     event_name = {
        #         pygame.KEYDOWN: "KEYDOWN",
        #         pygame.MOUSEBUTTONDOWN: "MOUSEBUTTONDOWN",
        #         pygame.MOUSEBUTTONUP: "MOUSEBUTTONUP",
        #         pygame.MOUSEMOTION: "MOUSEMOTION"
        #     }.get(event.type, f"TYPE_{event.type}")
        #     print(f"DEBUG: PhaseManager - Routing {event_name} to {handler_name}")

        result = handler.handle_event(event)

        # TODO: Uncomment for event debugging
        # if event.type in [pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION]:
        #     print(f"DEBUG: PhaseManager - {handler_name} returned {result}")

        return result

    def update(self) -> None:
        """Per-frame hooks for auto-starting setup flows in remote games."""
        try:
            if self.game.is_in_setup_phase():
                self.setup_handler.maybe_auto_start_setup_flow()
        except Exception:
            pass
    
    def get_current_allowed_actions(self) -> List[str]:
        """Get allowed actions for current phase"""
        handler = self.get_current_handler()
        return handler.get_allowed_actions()
    
    def is_action_allowed(self, action: str) -> bool:
        """Check if an action is allowed in the current phase"""
        return action in self.get_current_allowed_actions()

    def _request_move_unit_decision(
        self,
        unit: 'Unit',
        movement_type: str,
        callback,
        *,
        max_distance: float | None = None,
        target_unit=None,
        placement_validator=None,
        decision_request=None,
    ) -> None:
        """PhaseManager proxy for move/placement decisions used by multiple UI entry points."""
        handler = getattr(self, "battle_handler", None)
        if handler is None or not hasattr(handler, "_request_move_unit_decision"):
            raise RuntimeError("PhaseManager missing battle_handler move decision helper.")
        handler._request_move_unit_decision(
            unit,
            movement_type,
            callback,
            max_distance=max_distance,
            target_unit=target_unit,
            placement_validator=placement_validator,
            decision_request=decision_request,
        )

class PreBattlePhaseHandler(BasePhaseHandler):
    """Handles events during the RESOLVE_PREBATTLE_RULES phase (e.g., Scout moves)"""
    def __init__(self, game_view: 'GameView'):
        super().__init__(game_view)
        self.scout_units_queue = []  # List of (unit, player) tuples
        self.current_scout_unit = None
        self.current_scout_player = None  # Track current player for cache clearing
        self.awaiting_battlefield_click = False
        self.scout_callback = None
        self.scout_distance = 0
        self.mouse_pos = None  # Track mouse position for visual feedback

    def start_scout_phase(self) -> bool:
        """Initialize the queue of eligible human scout units."""
        logger.info("Initializing scout phase...")
        self.scout_units_queue = []
        self.current_scout_unit = None
        self.current_scout_player = None  # Reset player tracking
        self.awaiting_battlefield_click = False
        self.scout_callback = None
        self.scout_distance = 0
        self.mouse_pos = None

        # Get all eligible human scout units in correct order
        game = self.game_view.game
        if game is None:
            return False

        # Strike Swiftly selections can grant Scouts and must resolve before scout queueing.
        queue_prompts = getattr(self.game_view, "_queue_strike_swiftly_prompts", None)
        if callable(queue_prompts):
            queue_prompts(game)
        queue_student_prompts = getattr(self.game_view, "_queue_student_of_kauyon_prompts", None)
        if callable(queue_student_prompts):
            queue_student_prompts(game)
        try:
            from ...engine.decision_kinds import DECISION_CHOOSE_QUARRY
        except Exception:
            DECISION_CHOOSE_QUARRY = None
        if DECISION_CHOOSE_QUARRY:
            queue = getattr(game, "decision_queue", None)
            if queue is not None and hasattr(queue, "list"):
                for req in list(queue.list() or []):
                    if str(getattr(req, "decision_type", "")) != DECISION_CHOOSE_QUARRY:
                        continue
                    ctx = dict(getattr(req, "context", {}) or {})
                    if str(ctx.get("ability", "") or "") not in {"strike_swiftly", "student_of_kauyon"}:
                        continue
                    logger.info("Waiting for pre-battle enhancement selections before Scout moves.")
                    return False
        
        # During setup phase, use first_turn_player_index instead of current_player_index
        if game.first_turn_player_index is not None:
            first_turn_player = game.players[game.first_turn_player_index]
        else:
            # Fallback to attacker if first turn not determined yet
            first_turn_player = game.get_attacker() if game.attacker_index is not None else game.players[0]
        
        players_in_order = [first_turn_player] + [p for p in game.players if p != first_turn_player]
        logger.debug(f"DEBUG: Scout phase players in order: {[p.name for p in players_in_order]}")
        
        for player in players_in_order:
            if player.has_control() and player.get_army():
                logger.debug(f"DEBUG: Checking {player.name}'s units for scout ability")
                for unit in player.get_army().units:
                    has_scout, scout_distance = unit.has_scout()
                    logger.debug(f"DEBUG: {unit.name} - has_scout={has_scout}, deployed={unit.deployed}, reserve_status={unit.reserve_status}, scout_move_made={getattr(unit, 'scout_move_made', False)}")
                    if has_scout and unit.deployed and unit.reserve_status == 'deployed' and not getattr(unit, 'scout_move_made', False):
                        self.scout_units_queue.append((unit, player, scout_distance))
                        logger.debug(f"DEBUG: Added {unit.name} to scout queue")
        
        logger.debug(f"DEBUG: Scout queue has {len(self.scout_units_queue)} units: {[unit.name for unit, player, distance in self.scout_units_queue]}")
        self._next_scout_unit()
        return True

    def _next_scout_unit(self):
        logger.debug(f"DEBUG: _next_scout_unit called, queue has {len(self.scout_units_queue)} units")
        if self.scout_units_queue:
            unit, player, scout_distance = self.scout_units_queue.pop(0)
            logger.debug(f"DEBUG: Processing next scout unit: {unit.name} (Player: {player.name})")

            # Check if player has changed and clear enemy model cache if so
            if self.current_scout_player != player:
                if self.current_scout_player is not None:  # Not the first unit

                    clear_enemy_model_cache(self.game_view.game.map)
                    logger.info(f"Scout phase player switched to {player.name} - cleared enemy model cache")
                self.current_scout_player = player

            self.current_scout_unit = unit
            self.scout_distance = scout_distance
            self.awaiting_battlefield_click = False
            self._show_scout_dialog(unit)
        else:
            # print(f"DEBUG: Scout queue is empty, scout phase complete")
            self.current_scout_unit = None
            self.current_scout_player = None  # Reset player tracking
            self.awaiting_battlefield_click = False
            self.scout_callback = None
            self.scout_distance = 0
            self.mouse_pos = None
            logger.info("OK: All human SCOUT moves complete. Press SPACE to continue.")

    def _show_scout_dialog(self, unit):
        # print(f"DEBUG: _show_scout_dialog called for {unit.name}")
        from ...engine.command_kinds import CMD_RESOLVE_DECISION
        from ...engine.commands import GameCommand
        from ...engine.decision_kinds import DECISION_SCOUT_MOVE
        from ...utility.entity_ids import get_entity_id

        def _pending_request():
            for req in list(self.game_view.game.decision_queue.list() or []):
                if getattr(req, "decision_type", None) != DECISION_SCOUT_MOVE:
                    continue
                if str(getattr(req, "context", {}).get("unit_id", "")) == get_entity_id(unit):
                    return req
            return None

        req = _pending_request()
        if req is None:
            self._next_scout_unit()
            return

        def _option_for_action(action: str) -> str:
            for opt in list(getattr(req, "options", []) or []):
                payload = dict(getattr(opt, "payload", {}) or {})
                if str(payload.get("action", "") or "").lower() == action:
                    return opt.option_id
            return ""

        def _send_decision(action: str, payload: dict) -> None:
            option_id = _option_for_action(action)
            if not option_id:
                return
            cmd_payload = {
                "decision_id": req.decision_id,
                "option_id": option_id,
                "result_payload": payload,
            }
            cmd = GameCommand.create(CMD_RESOLVE_DECISION, player_id=req.player_id, payload=cmd_payload)
            self.game_view.game.apply_command(cmd)

        def on_scout_choice(choice):
            # print(f"DEBUG: Scout choice for {unit.name}: {choice}")
            if choice == 'scout':
                # Open individual model movement dialog for scout movement
                def on_scout_movement_complete(completed: bool):
                    # print(f"DEBUG: Scout movement complete for {unit.name}: completed={completed}")
                    # print(f"DEBUG: Setting scout_move_made=True for {unit.name}")
                    if completed:
                        logger.info(f"OK: {unit.name} scout movement completed")
                        model_positions = []
                        for model in list(getattr(unit, "models", []) or []):
                            if not getattr(model, "is_alive", True):
                                continue
                            loc = model.get_location()
                            if not loc:
                                continue
                            model_positions.append(
                                {
                                    "model_id": get_entity_id(model),
                                    "position": [float(loc[0]), float(loc[1]), float(loc[2])],
                                    "facing": float(getattr(model.model_base, "facing", 0.0)),
                                }
                            )
                        _send_decision("scout", {"model_positions": model_positions})
                    else:
                        logger.info(f"INFO:  {unit.name} scout movement skipped")
                        _send_decision("skip", {})
                    # print(f"DEBUG: Calling _next_scout_unit() to proceed to next unit")
                    self._next_scout_unit()

                self.game_view.individual_model_movement_dialog.show(
                    unit, 'scout', on_scout_movement_complete, self.game_view.game.map, self.scout_distance
                )
            elif choice == 'skip':
                _send_decision("skip", {})
                logger.info(f"OK: {unit.name} scout move skipped")
                self._next_scout_unit()
            elif choice == 'defer':
                logger.info(f"INFO:  {unit.name} scout decision deferred - moving to end of current player's queue")
                # Move this unit to the end of the current player's units in the queue
                player = None
                for p in self.game_view.game.players:
                    if unit in p.army.units:
                        player = p
                        break

                if player:
                    # Find where to insert: after the last unit of the same player
                    insert_position = 0
                    last_same_player_position = -1

                    for i in range(len(self.scout_units_queue)):
                        _, queue_player, _ = self.scout_units_queue[i]
                        if queue_player == player:
                            last_same_player_position = i

                    # Insert after the last unit of the same player
                    insert_position = last_same_player_position + 1

                    self.scout_units_queue.insert(insert_position, (unit, player, self.scout_distance))
                    # print(f"DEBUG: {unit.name} added back to position {insert_position} (after last {player.name} unit). Queue now has {len(self.scout_units_queue)} units")

                    # Debug: show current queue
                    # queue_debug = [(u.name, p.name) for u, p, _ in self.scout_units_queue]
                    # print(f"DEBUG: Current queue: {queue_debug}")

                self._next_scout_unit()
        # print(f"DEBUG: About to call ui_interface.show_scout_dialog for {unit.name}")
        self.game_view.ui_interface.show_scout_dialog(
            unit,
            on_scout_choice,
            self.game_view.game.map,
            decision_request=req,
        )
        # print(f"DEBUG: ui_interface.show_scout_dialog completed for {unit.name}")
        # print(f"DEBUG: Scout dialog visible: {self.game_view.ui_interface.scout_choice_dialog.visible}")

    def _validate_scout_destination(self, unit, destination: Tuple[float, float]) -> dict:
        """Validate if a destination is valid for a scout move using pathfinding."""
        from warhammer40k_ai.pathing.api import PathQuery, preview_model_path
        from warhammer40k_ai.utility.calcs import MovementType

        game_x, game_y = destination

        # Check if destination is within battlefield bounds
        battlefield_width, battlefield_height = self.game_view.game.get_battlefield_size()
        if game_x < 0 or game_x >= battlefield_width or game_y < 0 or game_y >= battlefield_height:
            return {'valid': False, 'reason': 'Outside battlefield bounds'}

        first_model = None
        for model in unit.models:
            if model.is_alive:
                first_model = model
                break
        if first_model is None:
            return {'valid': False, 'reason': 'No valid models in unit'}

        path_result = preview_model_path(
            PathQuery(
                model=first_model,
                target=(float(game_x), float(game_y), float(first_model.model_base.z)),
                movement_type=MovementType.SCOUT,
                max_distance=float(self.scout_distance),
                game_map=self.game_view.game.map,
            )
        ).to_legacy_dict()

        # If pathfinding fails, fall back to basic validation
        if not path_result['valid']:
            return path_result

        # Additional SCOUT-specific validation: 9" restriction from enemy units
        # Use the unit's prospective formation at this destination and measure base-to-base closest-point distance.
        snapshot = [m.get_location() for m in unit.models]
        try:
            prospective = unit.calculate_model_positions(game_x, game_y, self.game_view.game.map, avoid_friendly_units=True)
        finally:
            for m, loc in zip(unit.models, snapshot):
                if loc:
                    m.set_location(*loc)

        if not prospective:
            return {'valid': False, 'reason': 'No valid formation at destination'}

        from ...utility.aura_utils import distance_between_bases_3d
        enemy_units = self.game_view.game.get_enemy_units(unit.get_parent_army().player)
        enemy_models = [em for eu in enemy_units if eu.is_alive() and eu.deployed for em in eu.models if em.is_alive]
        for idx, (x, y, z, facing) in enumerate(prospective):
            if idx >= len(unit.models):
                break
            mb = unit._create_potential_base(x, y, z, facing, model=unit.models[idx])
            for em in enemy_models:
                d = float(distance_between_bases_3d(mb, em.model_base))
                if d < 9.0:
                    return {'valid': False, 'reason': f'Too close to {em.parent_unit.name} ({d:.1f}\")'}

        return path_result

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            # print(f"DEBUG: PreBattlePhaseHandler received MOUSEMOTION event at {event.pos}")
            pass

        # Track mouse position for visual feedback
        if event.type == pygame.MOUSEMOTION and self.awaiting_battlefield_click:
            self.mouse_pos = event.pos
        
        # Handle mouse motion for path preview during individual model movement
        if event.type == pygame.MOUSEMOTION:
            # print(f"DEBUG: PreBattlePhaseHandler mouse motion event received")

            # Debug: Check individual model movement dialog visibility
            has_dialog = hasattr(self.game_view, 'individual_model_movement_dialog')
            # print(f"DEBUG: has_dialog={has_dialog}")

            if has_dialog:
                dialog_obj = self.game_view.individual_model_movement_dialog
                dialog_visible = dialog_obj.visible
                dialog_unit = getattr(dialog_obj, 'unit', None)
                unit_name = dialog_unit.name if dialog_unit else None
                # print(f"DEBUG: Mouse motion - has_dialog={has_dialog}, dialog_visible={dialog_visible}, dialog_unit={unit_name}")

                if dialog_visible:
                    x, y = event.pos
                    # print(f"DEBUG: PreBattlePhaseHandler individual model mouse motion at ({x}, {y})")

                    # Check if mouse is over battlefield area
                    if self.game_view.battlefield_left < x < self.game_view.battlefield_right:
                        # Convert to game coordinates using helper method
                        battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)

                        # Store mouse position for individual model movement preview
                        self.game_view.individual_model_preview_target = (battlefield_x, battlefield_y)
                        # print(f"DEBUG: PreBattlePhaseHandler set individual_model_preview_target to ({battlefield_x:.1f}, {battlefield_y:.1f})")
                        return True
                    else:
                        # Clear preview when mouse leaves battlefield
                        self.game_view.individual_model_preview_target = None
                        # print(f"DEBUG: PreBattlePhaseHandler cleared individual_model_preview_target (mouse outside battlefield)")
                        return True
            else:
                pass
                # print(f"DEBUG: Mouse motion - has_dialog={has_dialog}")

        # Handle battlefield clicks for individual model movement during scout phase
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # Left click
            x, y = event.pos
            
            # Check if clicking on battlefield area
            if self.game_view.battlefield_left < x < self.game_view.battlefield_right:
                # Check if individual model movement dialog is active
                if (hasattr(self.game_view, 'individual_model_movement_dialog') and
                    self.game_view.individual_model_movement_dialog.visible):
                    # Convert screen coordinates to game coordinates using helper method
                    battlefield_x, battlefield_y = self.game_view.screen_to_game_coords(x, y)
                    battlefield_z = self.game_view.game.map.get_height_at_point(battlefield_x, battlefield_y)
                    
                    # Handle battlefield click for individual model movement
                    return self.game_view.individual_model_movement_dialog.handle_battlefield_click(
                        battlefield_x, battlefield_y, battlefield_z
                    )
        
        # Allow SPACE to skip to next phase if all done
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            if not self._current_player_has_control():
                return True
            if not self.scout_units_queue and not self.awaiting_battlefield_click:
                logger.info("Proceeding to next phase...")
                return False  # Let the main loop advance the phase
        return False

    def draw_scout_visual_feedback(self, battlefield_surface: pygame.Surface):
        """Draw visual feedback for scout moves on the battlefield surface with pathfinding."""
        if not self.awaiting_battlefield_click or not self.current_scout_unit or not self.mouse_pos:
            return

        # Get unit position from first model
        first_model = None
        for model in self.current_scout_unit.models:
            if model.is_alive:
                first_model = model
                break

        if not first_model:
            return

        unit_pos = first_model.get_location()
        if not unit_pos:
            return

        # Convert unit position to battlefield surface coordinates (no roster pane offset)
        unit_surface_x = int(unit_pos[0] * TILE_SIZE * self.game_view.zoom_level + self.game_view.offset_x)
        unit_surface_y = int(unit_pos[1] * TILE_SIZE * self.game_view.zoom_level + self.game_view.offset_y)

        # Get mouse position in game coordinates for validation using helper method
        mouse_x, mouse_y = self.mouse_pos
        mouse_game_x, mouse_game_y = self.game_view.screen_to_game_coords(mouse_x, mouse_y)

        # Convert mouse position to battlefield surface coordinates
        mouse_surface_x = int(mouse_game_x * TILE_SIZE * self.game_view.zoom_level + self.game_view.offset_x)
        mouse_surface_y = int(mouse_game_y * TILE_SIZE * self.game_view.zoom_level + self.game_view.offset_y)

        # Use pathing API to get movement preview
        from warhammer40k_ai.pathing.api import PathQuery, preview_model_path
        from warhammer40k_ai.utility.calcs import MovementType

        path_result = preview_model_path(
            PathQuery(
                model=first_model,
                target=(float(mouse_game_x), float(mouse_game_y), float(first_model.model_base.z)),
                movement_type=MovementType.SCOUT,
                max_distance=float(self.scout_distance),
                game_map=self.game_view.game.map,
            )
        ).to_legacy_dict()

        # Choose color based on pathfinding result
        if path_result['valid']:
            color = (0, 255, 255)  # Cyan for valid path
            alpha = 100
        else:
            color = (255, 165, 0)  # Orange for invalid path
            alpha = 150

        # Draw scout range circle around unit (only if unit is visible on battlefield surface)
        if (0 <= unit_surface_x <= battlefield_surface.get_width() and 0 <= unit_surface_y <= battlefield_surface.get_height()):
            circle_radius = int(self.scout_distance * TILE_SIZE * self.game_view.zoom_level)
            pygame.draw.circle(battlefield_surface, (*color, 50), (unit_surface_x, unit_surface_y), circle_radius, 2)

        # Draw pathfinding path if available
        if path_result['path'] and len(path_result['path']) > 1:
            # Convert path points to screen coordinates
            path_points = []
            for point in path_result['path']:
                screen_x = int(point[0] * TILE_SIZE * self.game_view.zoom_level + self.game_view.offset_x)
                screen_y = int(point[1] * TILE_SIZE * self.game_view.zoom_level + self.game_view.offset_y)
                path_points.append((screen_x, screen_y))

            # Draw the path as connected lines
            if len(path_points) > 1:
                pygame.draw.lines(battlefield_surface, (*color, alpha), False, path_points, 3)

                # Draw small circles at path waypoints
                for point in path_points[1:-1]:  # Skip start and end points
                    pygame.draw.circle(battlefield_surface, (*color, alpha//2), point, 3)
        else:
            # Fallback to straight line if no path available
            distance = ((mouse_game_x - unit_pos[0]) ** 2 + (mouse_game_y - unit_pos[1]) ** 2) ** 0.5
            if distance <= self.scout_distance:
                pygame.draw.line(battlefield_surface, (*color, alpha),
                               (unit_surface_x, unit_surface_y), (mouse_surface_x, mouse_surface_y), 3)

        # Draw destination indicator with actual model base footprint at mouse position
        # Get the first alive model to determine base size
        first_model = None
        for model in self.current_scout_unit.models:
            if model.is_alive:
                first_model = model
                break

        if first_model:
            self.game_view._draw_model_base_preview(battlefield_surface, first_model,
                                                  mouse_game_x, mouse_game_y, color)
        
        # Draw distance text using pathfinding results
        try:
            font = pygame.font.Font(None, 24)
            if path_result['path']:
                distance_text = f"{path_result['distance']:.1f}\""
            else:
                # Fallback to straight-line distance
                distance = ((mouse_game_x - unit_pos[0]) ** 2 + (mouse_game_y - unit_pos[1]) ** 2) ** 0.5
                distance_text = f"{distance:.1f}\" (direct)"

            text_surface = font.render(distance_text, True, color)
            text_rect = text_surface.get_rect(center=(mouse_surface_x, mouse_surface_y - 20))
            battlefield_surface.blit(text_surface, text_rect)
        except:
            pass  # Skip text rendering if font fails

        # Draw validation message using pathfinding results
        if not path_result['valid']:
            try:
                error_font = pygame.font.Font(None, 20)
                error_text = path_result['reason']
                # Wrap text if too long
                if len(error_text) > 40:
                    error_text = error_text[:37] + "..."
                error_surface = error_font.render(error_text, True, (255, 255, 255))
                error_rect = error_surface.get_rect(center=(mouse_surface_x, mouse_surface_y + 20))
                # Draw background for error text
                bg_rect = error_rect.inflate(10, 5)
                pygame.draw.rect(battlefield_surface, (0, 0, 0, 180), bg_rect)
                battlefield_surface.blit(error_surface, error_rect)
            except:
                pass  # Skip error text rendering if font fails

    def get_allowed_actions(self) -> List[str]:
        return ["scout_move", "skip_scout", "advance_setup_phase"]
