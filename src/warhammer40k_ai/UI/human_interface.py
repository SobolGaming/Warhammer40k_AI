import pygame
from typing import Callable, List, Tuple, TYPE_CHECKING

from .ui_constants import TILE_SIZE, TEXT_ACCENT, TEXT_PRIMARY, TEXT_SECONDARY
import logging
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from warhammer40k_ai.units.unit import Unit


class HumanUIInterface:
    """Interface class that bridges human UI components with the deployment system."""

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height

        # UI components
        from .dialogs import ScoutChoiceDialog
        self.scout_choice_dialog = ScoutChoiceDialog(screen_width, screen_height)
        from .dialogs import FightUnitSelectionDialog
        self.fight_unit_selection_dialog = FightUnitSelectionDialog(screen_width, screen_height)

        # State for handling UI interactions
        self.current_unit_for_placement = None
        self.current_deployment_zone = None
        self.placement_mode = False

    def choose_deployment_zone(self, available_zones: List[dict]) -> dict:
        """Human chooses deployment zone via UI."""
        # For now, return the first available zone
        # In a full implementation, this would show a zone selection dialog
        return available_zones[0]

    def declare_reserves(self, player) -> dict:
        """
        Return a deterministic reserves declaration for deployment flow.

        Local UI currently does not expose a dedicated pre-deployment reserves
        picker in this path, so default to deploying units unless a unit is
        explicitly forced to start in reserves (for example, AIRCRAFT).
        """
        army = player.get_army() if player is not None else None
        if army is None:
            return {}
        decisions: dict[str, str] = {}
        for unit in list(getattr(army, "units", []) or []):
            must_start = False
            try:
                must_start = bool(getattr(unit, "must_start_in_reserves", lambda: False)())
            except Exception:
                must_start = False
            decisions[unit.id] = "reserves" if must_start else "deploy"
        return decisions

    def choose_unit_deployment_position(
        self,
        unit: 'Unit',
        deployment_zone: dict,
        already_deployed: List['Unit'],
    ) -> Tuple[float, float]:
        """Human chooses unit position via UI clicking."""

        # Set up for position selection
        self.current_unit_for_placement = unit
        self.current_deployment_zone = deployment_zone
        self.placement_mode = True

        selected_position = None
        position_selected = False

        logger.info(f"Click on the battlefield to place {unit.name}")
        # Compute a bounding box for display only from mission polygons
        try:
            xs, ys = [], []
            for mz in (deployment_zone.get('mission_zones') or []):
                for vx, vy in getattr(mz, 'vertices', []):
                    xs.append(float(vx))
                    ys.append(float(vy))
            if xs and ys:
                logger.info(f"Deployment zone bounds: X({min(xs):.1f} - {max(xs):.1f}), "
                    f"Y({min(ys):.1f} - {max(ys):.1f})")
        except Exception:
            pass

        # Wait for position selection
        clock = pygame.time.Clock()
        while not position_selected and self.placement_mode:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    # Return center of deployment zone as default
                    x_center, y_center = self._zone_centroid(deployment_zone)
                    return x_center, y_center

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # Convert screen coordinates to game coordinates
                    game_x, game_y = self.screen_to_game_coords(event.pos)

                    # Check if position is within deployment zone
                    if self.is_position_in_zone(game_x, game_y, deployment_zone):
                        selected_position = (game_x, game_y)
                        position_selected = True
                        logger.info(f"Unit {unit.name} will be placed at ({game_x:.1f}, {game_y:.1f})")
                    else:
                        logger.info(f"Invalid position ({game_x:.1f}, {game_y:.1f}) - "
                            "must be within deployment zone")

                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    # Cancel and use center of deployment zone
                    x_center, y_center = self._zone_centroid(deployment_zone)
                    selected_position = (x_center, y_center)
                    position_selected = True
                    logger.info("Position selection cancelled, using center of deployment zone")

            clock.tick(60)

        self.placement_mode = False
        self.current_unit_for_placement = None
        self.current_deployment_zone = None

        if selected_position:
            return selected_position
        return self._zone_centroid(deployment_zone)

    def screen_to_game_coords(self, screen_pos: Tuple[int, int]) -> Tuple[float, float]:
        """Convert screen coordinates to game coordinates."""
        # This would need to account for zoom, pan, and coordinate system
        # For now, simplified conversion assuming 1:1 mapping
        x, y = screen_pos
        # Convert from screen pixels to game inches
        game_x = x / TILE_SIZE
        game_y = y / TILE_SIZE
        return game_x, game_y

    def is_position_in_zone(self, x: float, y: float, zone: dict) -> bool:
        """Check if a position is within the deployment zone."""
        mzs = zone.get('mission_zones') or []
        if not mzs:
            raise RuntimeError("Deployment zone missing mission_zones polygons (invalid configuration).")
        for mz in mzs:
            if mz.contains_point(x, y):
                return True
        return False

    def _zone_centroid(self, zone: dict) -> Tuple[float, float]:
        """Best-effort centroid for a compound mission zone."""
        mzs = zone.get('mission_zones') or []
        if not mzs:
            raise RuntimeError("Deployment zone missing mission_zones polygons (invalid configuration).")
        try:
            xs, ys = [], []
            for mz in mzs:
                for vx, vy in getattr(mz, 'vertices', []):
                    xs.append(float(vx))
                    ys.append(float(vy))
            if xs and ys:
                return (sum(xs) / len(xs), sum(ys) / len(ys))
        except Exception:
            pass
        # Fallback to battlefield center if something is very wrong
        return (30.0, 22.0)

    def update(self, screen):
        """Update and draw UI components."""
        # Draw placement indicator if in placement mode
        if self.placement_mode and self.current_unit_for_placement:
            self.draw_placement_indicator(screen)

    def draw_placement_indicator(self, screen):
        """Draw visual indicator for unit placement."""
        if not self.current_unit_for_placement or not self.current_deployment_zone:
            return

        zoom_level = 1.0
        game_view = getattr(self, "game_view", None)
        if game_view is not None:
            zoom_level = float(getattr(game_view, "zoom_level", 1.0) or 1.0)

        # Draw deployment zone outline (mission polygons)
        zone = self.current_deployment_zone
        mzs = zone.get('mission_zones') or []
        if not mzs:
            raise RuntimeError("Deployment zone missing mission_zones polygons (invalid configuration).")
        for mz in mzs:
            pts = []
            for vx, vy in getattr(mz, "vertices", []):
                sx = int(vx * TILE_SIZE * zoom_level)
                sy = int(vy * TILE_SIZE * zoom_level)
                pts.append((sx, sy))
            if len(pts) >= 3:
                pygame.draw.polygon(screen, TEXT_ACCENT, pts, 3)

        # Draw unit name
        font = pygame.font.SysFont('Arial', 16, bold=True)
        text = font.render(f"Place {self.current_unit_for_placement.name}", True, TEXT_PRIMARY)
        screen.blit(text, (10, 10))

        # Draw instructions
        instr_font = pygame.font.SysFont('Arial', 14)
        instructions = [
            "Left click to place unit",
            "ESC to use center position",
            "Must be in highlighted zone",
        ]

        for i, instruction in enumerate(instructions):
            instr_text = instr_font.render(instruction, True, TEXT_SECONDARY)
            screen.blit(instr_text, (10, 40 + i * 20))

    def handle_event(self, event):
        """Handle pygame events for non-dialog UI components only.

        Dialogs are exclusively handled by DialogManager.
        """
        return False

    def show_scout_dialog(self, unit, callback, game_map=None, decision_request=None):
        """Show the scout move dialog for a unit."""
        # print(f"HumanUIInterface.show_scout_dialog called for {unit.name}")
        self.scout_choice_dialog.show(unit, callback, game_map, decision_request=decision_request)
        # print(f"DEBUG: Scout dialog show() completed, visible={self.scout_choice_dialog.visible}")

    def show_fight_unit_selection_dialog(
        self,
        stage_name: str,
        eligible_units: List['Unit'],
        on_unit_selected: Callable[[str], None],
        on_cancel: Callable[[], None] = None,
        decision_request=None,
    ):
        """Show the fight unit selection dialog for a stage."""
        logger.info(f"HumanUIInterface.show_fight_unit_selection_dialog called for {stage_name} "
            f"stage with {len(eligible_units)} units")
        self.fight_unit_selection_dialog.show(stage_name, eligible_units, on_unit_selected, on_cancel, decision_request=decision_request)

    def show_melee_weapon_declaration_dialog(self, unit, callback, game_map=None, target_unit=None, decision_request=None):
        """Show the melee weapon declaration dialog for a unit."""
        logger.info(f"HumanUIInterface.show_melee_weapon_declaration_dialog called for {unit.name}")
        # Delegate to the game view's dialog instance to avoid duplicates
        if hasattr(self, 'game_view') and hasattr(self.game_view, 'melee_weapon_declaration_dialog'):
            self.game_view.melee_weapon_declaration_dialog.show(
                unit,
                callback,
                game_map,
                target_unit=target_unit,
                decision_request=decision_request,
            )
        else:
            logger.error("ERROR: Error: melee_weapon_declaration_dialog not found on game_view")
            # Call callback with empty declarations to prevent hanging
            if callback:
                callback([])
