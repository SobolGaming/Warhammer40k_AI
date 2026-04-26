from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable

import pygame

from ..engine.training_mode import (
    TrainingObservation,
    TrainingScenario,
    TrainingSession,
    best_training_action_id,
)


BG = (20, 22, 26)
PANEL = (33, 37, 44)
PANEL_ALT = (42, 48, 58)
BORDER = (78, 87, 104)
TEXT = (236, 240, 246)
MUTED = (168, 176, 190)
ACCENT = (88, 166, 255)
GOOD = (72, 188, 122)
WARN = (229, 178, 84)
BAD = (229, 92, 92)
BUTTON = (52, 60, 73)
BUTTON_HOVER = (66, 77, 95)


@dataclass(frozen=True)
class TrainingButton:
    rect: pygame.Rect
    action_id: str
    label: str


class TrainingModeApp:
    def __init__(
        self,
        session: TrainingSession,
        *,
        situations: int = 20,
        screen_size: tuple[int, int] = (1280, 800),
        clock_factory: Callable[[], pygame.time.Clock] | None = None,
    ) -> None:
        self.session = session
        self.situations = max(1, int(situations or 1))
        self.screen_size = screen_size
        self.clock_factory = clock_factory or pygame.time.Clock
        self.scenario_index = 0
        self.current_scenario: TrainingScenario | None = None
        self.current_observation: TrainingObservation | None = None
        self.buttons: list[TrainingButton] = []
        self.next_rect = pygame.Rect(0, 0, 0, 0)
        self.started_at = time.perf_counter()
        self.running = True

    def run(self) -> list[TrainingObservation]:
        pygame.init()
        pygame.display.set_caption("Warhammer 40,000 AI Training Mode")
        screen = pygame.display.set_mode(self.screen_size, pygame.RESIZABLE)
        clock = self.clock_factory()
        fonts = {
            "title": pygame.font.SysFont("arial", 28, bold=True),
            "body": pygame.font.SysFont("arial", 18),
            "small": pygame.font.SysFont("arial", 15),
        }
        self._load_next_scenario()
        while self.running:
            for event in pygame.event.get():
                screen = self._handle_event(event, screen)
            self._draw(screen, fonts)
            pygame.display.flip()
            clock.tick(60)
        pygame.quit()
        return list(self.session.store.observations)

    def _load_next_scenario(self) -> None:
        if self.scenario_index >= self.situations:
            self.running = False
            return
        self.current_scenario = self.session.next_scenario()
        self.current_observation = None
        self.buttons = []
        self.started_at = time.perf_counter()
        self.scenario_index += 1

    def _handle_event(self, event: pygame.event.Event, screen: pygame.Surface) -> pygame.Surface:
        if event.type == pygame.QUIT:
            self.running = False
            return screen
        if event.type == pygame.VIDEORESIZE:
            screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            self.screen_size = screen.get_size()
            return screen
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.running = False
                return screen
            if self.current_observation is not None and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._load_next_scenario()
                return screen
            if self.current_observation is None and pygame.K_1 <= event.key <= pygame.K_9:
                index = int(event.key - pygame.K_1)
                if 0 <= index < len(self.buttons):
                    self._select_action(self.buttons[index].action_id)
                return screen
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.current_observation is not None and self.next_rect.collidepoint(event.pos):
                self._load_next_scenario()
                return screen
            if self.current_observation is None:
                for button in self.buttons:
                    if button.rect.collidepoint(event.pos):
                        self._select_action(button.action_id)
                        return screen
        return screen

    def _select_action(self, action_id: str) -> None:
        if self.current_scenario is None or self.current_observation is not None:
            return
        elapsed_ms = int(round((time.perf_counter() - self.started_at) * 1000.0))
        self.current_observation = self.session.record_selection(
            self.current_scenario,
            action_id,
            source="training_ui",
            wall_clock_ms=elapsed_ms,
        )

    def _draw(self, screen: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        screen.fill(BG)
        width, height = screen.get_size()
        margin = 28
        title = f"Training situation {self.scenario_index} / {self.situations}"
        _draw_text(screen, fonts["title"], title, (margin, 24), TEXT)
        if self.current_scenario is None:
            _draw_text(screen, fonts["body"], "Complete", (margin, 70), TEXT)
            return
        payload = self.current_scenario.to_ui_payload()
        prompt_rect = pygame.Rect(margin, 72, max(300, width - (2 * margin)), 118)
        pygame.draw.rect(screen, PANEL, prompt_rect, border_radius=6)
        pygame.draw.rect(screen, BORDER, prompt_rect, 1, border_radius=6)
        _draw_wrapped(screen, fonts["body"], str(payload["prompt"]), prompt_rect.inflate(-24, -20), TEXT)
        _draw_wrapped(
            screen,
            fonts["small"],
            _situation_summary(payload),
            pygame.Rect(margin + 12, 132, max(280, width - (2 * margin) - 24), 46),
            MUTED,
        )
        self._draw_candidates(screen, fonts, width, height, margin)
        if self.current_observation is not None:
            self._draw_feedback(screen, fonts, width, height, margin)

    def _draw_candidates(
        self,
        screen: pygame.Surface,
        fonts: dict[str, pygame.font.Font],
        width: int,
        height: int,
        margin: int,
    ) -> None:
        del height
        scenario = self.current_scenario
        if scenario is None:
            return
        payload = scenario.to_ui_payload()
        candidates = list(payload.get("candidates", []) or [])
        button_top = 214
        button_height = 72
        gap = 12
        self.buttons = []
        mouse_pos = pygame.mouse.get_pos()
        best_action_id = best_training_action_id(scenario)
        for index, candidate in enumerate(candidates):
            rect = pygame.Rect(margin, button_top + (index * (button_height + gap)), width - (2 * margin), button_height)
            legal = bool(dict(candidate).get("legal", False))
            action_id = str(dict(candidate).get("action_id", "") or "")
            color = BUTTON_HOVER if rect.collidepoint(mouse_pos) and self.current_observation is None else BUTTON
            if not legal:
                color = (44, 44, 48)
            pygame.draw.rect(screen, color, rect, border_radius=6)
            border_color = ACCENT if action_id == best_action_id else BORDER
            pygame.draw.rect(screen, border_color, rect, 1, border_radius=6)
            number = f"{index + 1}. "
            label = number + str(dict(candidate).get("label", "") or action_id)
            _draw_text(screen, fonts["body"], label, (rect.x + 14, rect.y + 10), TEXT if legal else MUTED)
            _draw_text(
                screen,
                fonts["small"],
                str(dict(candidate).get("summary", "") or ""),
                (rect.x + 14, rect.y + 40),
                MUTED,
            )
            if legal:
                self.buttons.append(TrainingButton(rect=rect, action_id=action_id, label=label))

    def _draw_feedback(
        self,
        screen: pygame.Surface,
        fonts: dict[str, pygame.font.Font],
        width: int,
        height: int,
        margin: int,
    ) -> None:
        observation = self.current_observation
        if observation is None:
            return
        rect = pygame.Rect(margin, max(540, height - 180), width - (2 * margin), 138)
        pygame.draw.rect(screen, PANEL_ALT, rect, border_radius=6)
        pygame.draw.rect(screen, BORDER, rect, 1, border_radius=6)
        evaluation = observation.evaluation
        color = GOOD if evaluation.matched_best else WARN
        headline = (
            "Best match"
            if evaluation.matched_best
            else f"Recorded choice; best candidate was {evaluation.best_action_id}"
        )
        _draw_text(screen, fonts["body"], headline, (rect.x + 14, rect.y + 12), color)
        detail = (
            f"Score {evaluation.selected_score:.2f} / {evaluation.best_score:.2f}  "
            f"reward {evaluation.reward:.3f}"
        )
        _draw_text(screen, fonts["small"], detail, (rect.x + 14, rect.y + 44), TEXT)
        feedback = dict(evaluation.feedback or {})
        feedback_line = _feedback_line(feedback)
        _draw_wrapped(screen, fonts["small"], feedback_line, pygame.Rect(rect.x + 14, rect.y + 68, rect.width - 150, 44), MUTED)
        self.next_rect = pygame.Rect(rect.right - 120, rect.bottom - 48, 96, 32)
        pygame.draw.rect(screen, ACCENT, self.next_rect, border_radius=5)
        _draw_text(screen, fonts["small"], "Next", (self.next_rect.x + 32, self.next_rect.y + 8), (8, 16, 28))


def _draw_text(
    screen: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    pos: tuple[int, int],
    color: tuple[int, int, int],
) -> None:
    surface = font.render(str(text), True, color)
    screen.blit(surface, pos)


def _draw_wrapped(
    screen: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    rect: pygame.Rect,
    color: tuple[int, int, int],
) -> None:
    words = str(text or "").split()
    line = ""
    y = rect.y
    line_height = font.get_linesize()
    for word in words:
        trial = f"{line} {word}".strip()
        if font.size(trial)[0] <= rect.width:
            line = trial
            continue
        if line:
            _draw_text(screen, font, line, (rect.x, y), color)
            y += line_height
        line = word
        if y + line_height > rect.bottom:
            return
    if line and y + line_height <= rect.bottom:
        _draw_text(screen, font, line, (rect.x, y), color)


def _situation_summary(payload: dict[str, object]) -> str:
    stage = str(payload.get("stage", "") or "")
    situation = dict(payload.get("situation", {}) or {})
    if stage == "shooting_phase":
        shooter = dict(situation.get("shooter", {}) or {})
        targets = list(situation.get("targets", []) or [])
        target_names = ", ".join(str(dict(target).get("name", "") or "") for target in targets)
        return f"{shooter.get('name', 'Shooter')} has multiple profiles. Targets: {target_names}."
    if stage == "deployment_reserves":
        army = list(situation.get("army", []) or [])
        cap = int(situation.get("reserve_cap_points", 0) or 0)
        return f"{len(army)} generated units, reserve policy cap {cap} points."
    return ""


def _feedback_line(feedback: dict[str, object]) -> str:
    keys = [
        "expected_damage",
        "objective_swing",
        "reserve_points",
        "reserve_threat",
        "board_presence",
        "over_cap_penalty",
    ]
    parts = []
    for key in keys:
        if key not in feedback:
            continue
        value = feedback.get(key)
        if isinstance(value, float):
            parts.append(f"{key}={value:.2f}")
        else:
            parts.append(f"{key}={value}")
    if not parts:
        return ""
    return ", ".join(parts)


__all__ = ["TrainingModeApp"]
