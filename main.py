"""Pygame front end for MELTINGPOT: an immigrant SPENT-style survival game."""
from __future__ import annotations

import sys
import textwrap
from typing import Iterable

import pygame

from game_state import CHOICES, MAX_WEEKS, GameState, weekly_event

WIDTH, HEIGHT = 1180, 760
BG = (22, 25, 34)
PANEL = (35, 41, 55)
PANEL_ALT = (46, 54, 72)
TEXT = (239, 236, 226)
MUTED = (179, 183, 190)
ACCENT = (116, 196, 168)
GOOD = (99, 204, 132)
BAD = (224, 93, 105)
WARN = (229, 158, 91)

STAT_LABELS = {
    "cash": "Cash",
    "health": "Health",
    "community": "Community",
    "legal": "Legal stability",
}


class Button:
    def __init__(self, rect: pygame.Rect, label: str, index: int):
        self.rect = rect
        self.label = label
        self.index = index

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, small: pygame.font.Font) -> None:
        mouse = pygame.mouse.get_pos()
        color = PANEL_ALT if self.rect.collidepoint(mouse) else PANEL
        pygame.draw.rect(surface, color, self.rect, border_radius=12)
        pygame.draw.rect(surface, ACCENT, self.rect, width=2, border_radius=12)
        draw_wrapped(surface, font, self.label, self.rect.x + 14, self.rect.y + 10,
                     self.rect.width - 28, TEXT)
        draw_wrapped(surface, small, CHOICES[self.index].description, self.rect.x + 14, self.rect.y + 42,
                     self.rect.width - 28, MUTED)


def make_font(size: int, *, bold: bool = False) -> pygame.font.Font:
    font_path = pygame.font.match_font("merriweather") or pygame.font.match_font("georgia")
    if font_path:
        return pygame.font.Font(font_path, size)
    return pygame.font.SysFont("serif", size, bold=bold)


def draw_wrapped(surface: pygame.Surface, font: pygame.font.Font, text: str, x: int, y: int,
                 width: int, color: tuple[int, int, int], line_gap: int = 4) -> int:
    avg_char = max(1, font.size("x")[0])
    wrap_width = max(12, width // avg_char)
    for paragraph in text.split("\n"):
        for line in textwrap.wrap(paragraph, wrap_width) or [""]:
            surface.blit(font.render(line, True, color), (x, y))
            y += font.get_linesize() + line_gap
    return y


def draw_delta(surface: pygame.Surface, font: pygame.font.Font, delta: int, x: int, y: int) -> None:
    if delta == 0:
        return
    color = GOOD if delta > 0 else BAD
    sign = "+" if delta > 0 else ""
    surface.blit(font.render(f"{sign}{delta}", True, color), (x, y))


def draw_meter(surface: pygame.Surface, font: pygame.font.Font, label: str, value: int, delta: int,
               x: int, y: int, color: tuple[int, int, int] = ACCENT) -> None:
    text = font.render(f"{label}: {value}", True, TEXT)
    surface.blit(text, (x, y))
    draw_delta(surface, font, delta, x + text.get_width() + 12, y)
    bar = pygame.Rect(x, y + 27, 250, 12)
    pygame.draw.rect(surface, (18, 20, 28), bar, border_radius=6)
    fill = pygame.Rect(x, y + 27, int(250 * max(0, min(100, value)) / 100), 12)
    pygame.draw.rect(surface, color, fill, border_radius=6)


def visible_choices(state: GameState) -> list[int]:
    available = [index for index, choice in enumerate(CHOICES) if choice.requirement(state)]
    start = ((state.week - 1) * 3) % len(available)
    picks = [available[(start + offset) % len(available)] for offset in range(min(6, len(available)))]
    essentials = [0, 3, 8, 15]
    for item in essentials:
        if item in available and item not in picks:
            picks[-1] = item
            break
    return picks


def apply_choice(state: GameState, choice_index: int) -> tuple[str, dict[str, int]]:
    choice = CHOICES[choice_index]
    before = state.snapshot()
    choice.effect(state)
    event_text = weekly_event(state)
    state.finish_week()
    after = state.snapshot()
    deltas = {name: after[name] - before[name] for name in STAT_LABELS}
    summary = f"You chose: {choice.title}. {event_text} Bills came due at the end of the week."
    return summary, deltas


def draw_status(surface: pygame.Surface, fonts: dict[str, pygame.font.Font], state: GameState,
                deltas: dict[str, int]) -> None:
    pygame.draw.rect(surface, PANEL, (24, 94, 316, 640), border_radius=16)
    y = 118
    surface.blit(fonts["h2"].render(f"Week {min(state.week, MAX_WEEKS)} of {MAX_WEEKS}", True, TEXT), (48, y))
    y += 45

    cash_label = fonts["body"].render(f"Cash: ${state.cash}", True, ACCENT if state.cash >= 0 else BAD)
    surface.blit(cash_label, (48, y))
    draw_delta(surface, fonts["body"], deltas.get("cash", 0), 48 + cash_label.get_width() + 12, y)
    y += 32
    surface.blit(fonts["small"].render(f"Weekly bills: ${state.week_costs}", True, MUTED), (48, y))
    y += 32
    surface.blit(fonts["small"].render(f"Status: {state.status}", True, MUTED), (48, y))
    y += 30
    surface.blit(fonts["small"].render(f"Language: {state.language_path}", True, MUTED), (48, y))
    y += 47

    draw_meter(surface, fonts["small"], "Health", state.health, deltas.get("health", 0), 48, y,
               ACCENT if state.health > 35 else BAD)
    y += 76
    draw_meter(surface, fonts["small"], "Community", state.community, deltas.get("community", 0), 48, y)
    y += 76
    draw_meter(surface, fonts["small"], "Legal stability", state.legal, deltas.get("legal", 0), 48, y)
    y += 80

    draw_wrapped(surface, fonts["small"],
                 "Meow.",
                 48, y, 250, MUTED)


def draw_log(surface: pygame.Surface, fonts: dict[str, pygame.font.Font], lines: Iterable[str]) -> None:
    pygame.draw.rect(surface, PANEL, (364, 548, 792, 186), border_radius=16)
    surface.blit(fonts["h2"].render("Recent consequences", True, TEXT), (388, 568))
    y = 606
    for line in list(lines)[-4:]:
        y = draw_wrapped(surface, fonts["small"], f"• {line}", 388, y, 740, MUTED, 2)


def main() -> int:
    pygame.init()
    pygame.display.set_caption("MELTINGPOT")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    fonts = {
        "title": make_font(36, bold=True),
        "h2": make_font(22, bold=True),
        "body": make_font(20),
        "small": make_font(16),
    }
    state = GameState()
    last_deltas = {name: 0 for name in STAT_LABELS}
    summary = "Every good choice still costs something. Choose one action each week and try to last 12 weeks."
    buttons: list[Button] = []

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return 0
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return 0
                if state.is_over and event.key == pygame.K_r:
                    state = GameState()
                    last_deltas = {name: 0 for name in STAT_LABELS}
                    summary = "New season started. Every good choice still costs something."
                elif pygame.K_1 <= event.key <= pygame.K_6 and not state.is_over:
                    idx = event.key - pygame.K_1
                    current = visible_choices(state)
                    if idx < len(current):
                        summary, last_deltas = apply_choice(state, current[idx])
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not state.is_over:
                for button in buttons:
                    if button.rect.collidepoint(event.pos):
                        summary, last_deltas = apply_choice(state, button.index)
                        break

        screen.fill(BG)
        screen.blit(fonts["title"].render("MELTINGPOT", True, TEXT), (32, 28))
        screen.blit(fonts["body"].render("A SPENT-style week-by-week survival game about immigrant tradeoffs", True, MUTED), (315, 40))
        draw_status(screen, fonts, state, last_deltas)

        pygame.draw.rect(screen, PANEL, (364, 94, 792, 132), border_radius=16)
        draw_wrapped(screen, fonts["body"], summary if not state.is_over else state.ending, 388, 118, 744,
                     TEXT if not state.is_over else WARN)
        if state.is_over:
            draw_wrapped(screen, fonts["small"], "Press R to restart or Esc to quit.", 388, 188, 744, MUTED)

        buttons = []
        if not state.is_over:
            for slot, choice_index in enumerate(visible_choices(state)):
                col = slot % 2
                row = slot // 2
                rect = pygame.Rect(364 + col * 398, 250 + row * 92, 374, 76)
                button = Button(rect, CHOICES[choice_index].title, choice_index)
                button.draw(screen, fonts["body"], fonts["small"])
                buttons.append(button)
        else:
            pygame.draw.rect(screen, PANEL, (364, 250, 792, 250), border_radius=16)
            end_text = ("Final reflection: stability was shaped not only by effort, but by documents, language access, "
                        "housing gatekeeping, employer power, health care costs, and community networks.")
            draw_wrapped(screen, fonts["body"], end_text, 388, 278, 740, TEXT)

        draw_log(screen, fonts, state.log)
        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    sys.exit(main())
