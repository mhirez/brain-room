"""The heads-up display: health, score, boss health, and contextual notices."""

import pygame

from game.config import WIDTH, HEIGHT
from game.ui import style as S

BAR_H = 40
TOAST_TIME = 3.0           # seconds an achievement or upgrade notice holds the middle of the top bar


def _health_meter(surface, hp, max_hp):
    x = 16
    gap = 3
    segment_width, extra_pixels = divmod(96 - gap * (max_hp - 1), max_hp)
    colour = S.DANGER if hp <= 2 else S.PLAYER
    S.text(surface, "Health", S.font(15, S.UI, True), S.WHITE, (x, 6))
    for index in range(max_hp):
        width = segment_width + (index < extra_pixels)
        segment = (x, 24, width, 8)
        if index < hp:
            pygame.draw.rect(surface, colour, segment)
        else:
            pygame.draw.rect(surface, S.FAINT, segment, 1)
        x += width + gap


def draw(surface, run, toast=None):
    room, p = run.room, run.player
    pygame.draw.rect(surface, S.PANEL, (0, 0, WIDTH, BAR_H))
    pygame.draw.line(surface, S.OUTLINE, (0, BAR_H), (WIDTH, BAR_H), 2)

    _health_meter(surface, p.hp, p.stats.max_hp)
    if toast is not None:
        _toast_slot(surface, toast)
    S.text(surface, f"Score {run.total_score:,}", S.font(16, S.UI, True), S.WHITE,
           (WIDTH - 16, BAR_H // 2), "midright")
    boss = room.boss
    if boss is not None and not boss.dead:
        w = 620
        box = pygame.Rect((WIDTH - w) // 2, HEIGHT - 26, w, 10)
        S.text(surface, "ARGUS", S.display(20), S.GOLD, (box.centerx, box.y - 4), "midbottom")
        pygame.draw.rect(surface, S.OUTLINE, box.inflate(4, 4))
        pygame.draw.rect(surface, S.GOLD, (box.x, box.y, int(w * boss.health), box.h))
        for f in (0.33, 0.66):
            pygame.draw.line(surface, S.OUTLINE, (box.x + int(w * f), box.y), (box.x + int(w * f), box.bottom), 2)

    combo(surface, room)


def combo(surface, room):
    """The kill chain: x1.25 per extra kill within 3 s (style kills count double), up to x3."""
    left = room.combo_left()
    if left <= 0:
        return
    m = room.multiplier
    colour = S.mix(S.GOLD, S.DANGER, (m - 1) / 2)
    S.text(surface, f"x{m:.2f}  COMBO", S.display(22), colour, (WIDTH - 16, BAR_H + 26), "topright")
    bar = pygame.Rect(WIDTH - 136, BAR_H + 54, 120, 4)
    pygame.draw.rect(surface, S.OUTLINE, bar)
    pygame.draw.rect(surface, colour, (bar.right - int(bar.w * left), bar.y, int(bar.w * left), bar.h))


def _toast_slot(surface, toast):
    """Show an achievement or upgrade briefly in the middle of the top bar."""
    title, text, age = toast
    a = min(1.0, age * 6) * min(1.0, max(0.0, (TOAST_TIME - age) * 3))
    layer = pygame.Surface((520, BAR_H), pygame.SRCALPHA)
    kind = S.font(13, S.UI, True).render(title, True, S.GOLD)
    name = S.display(22).render(text, True, S.WHITE)
    x = (520 - kind.get_width() - 30 - name.get_width()) // 2
    pygame.draw.polygon(layer, S.GOLD, S.polygon((x + 5, BAR_H // 2), 6, 4, 0))
    layer.blit(kind, kind.get_rect(midleft=(x + 16, BAR_H // 2 + 1)))
    layer.blit(name, name.get_rect(midleft=(x + 30 + kind.get_width(), BAR_H // 2 + 1)))
    layer.set_alpha(int(255 * a))
    surface.blit(layer, (WIDTH // 2 + 40 - 260, 0))


def toasts(surface, items):
    """Off the play screen (the research page): the newest notice rises at the bottom."""
    if not items:
        return
    title, text, age = items[0]
    a = min(1.0, age * 6) * min(1.0, max(0.0, (TOAST_TIME - age) * 3))
    w, h = 360, 50
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    panel.fill((*S.PANEL, 245))
    pygame.draw.rect(panel, S.GOLD, (0, 0, w, h), 2)
    S.text(panel, title, S.font(13, S.UI, True), S.GOLD, (16, h // 2), "midleft")
    S.text(panel, text, S.display(22), S.WHITE, (w - 16, h // 2 + 1), "midright")
    panel.set_alpha(int(255 * a))
    surface.blit(panel, ((WIDTH - w) // 2, HEIGHT - 110 + int(12 * (1 - min(1.0, age * 5)))))


def location(surface, title: str, subtitle: str, age: float, duration: float):
    """An ordinary room: its name slides in under the top bar, top left, and fades."""
    if age > duration:
        return
    ease = 1 - (1 - min(1.0, age * 4)) ** 3
    a = ease * min(1.0, max(0.0, (duration - age) * 2))
    layer = pygame.Surface((520, 90), pygame.SRCALPHA)
    S.text(layer, subtitle, S.font(15, S.UI, True), S.DIM, (0, 4))
    name = S.spaced(layer, title, S.display(38), S.WHITE, (0, 26), 2, "topleft")
    pygame.draw.rect(layer, S.PLAYER, (0, name.bottom + 6, 56, 3))
    layer.set_alpha(int(255 * a))
    surface.blit(layer, (58 - int(30 * (1 - ease)), BAR_H + 20))


def stinger(surface, title: str, subtitle: str, age: float, duration: float):
    """Show a brief room-clear notice."""
    if age > duration:
        return
    alpha = min(1.0, age * 8) * min(1.0, max(0.0, (duration - age) * 2.5))
    banner(surface, title, subtitle, alpha, S.GOOD)


def banner(surface, title: str, subtitle: str, alpha: float, colour=S.WHITE):
    if alpha <= 0:
        return
    heading = S.font(28, S.UI, True)
    detail = S.font(17, S.UI, True)
    width = max(heading.size(title)[0], detail.size(subtitle)[0]) + 44
    panel = pygame.Surface((width, 62 if subtitle else 42), pygame.SRCALPHA)
    panel.fill((*S.PANEL, 242))
    S.text(panel, title, heading, colour, (width // 2, 20), "center")
    if subtitle:
        S.text(panel, subtitle, detail, S.DIM, (width // 2, 45), "center")
    panel.set_alpha(int(255 * min(1.0, alpha)))
    surface.blit(panel, panel.get_rect(midbottom=(WIDTH // 2, HEIGHT - 62)))


def controls_hint(surface, alpha: float):
    """A compact first-room reminder that fades after the player moves."""
    if alpha <= 0:
        return
    controls = "WASD  Move      Space  Shoot      Shift  Dash      Right click  Debug      Tab  AI view"
    font = S.font(17, S.UI, True)
    box = pygame.Rect(0, 0, font.size(controls)[0] + 36, 34)
    box.midbottom = (WIDTH // 2, HEIGHT - 12)
    panel = pygame.Surface(box.size, pygame.SRCALPHA)
    panel.fill((*S.PANEL, 238))
    S.text(panel, controls, font, S.WHITE, panel.get_rect().center, "center")
    panel.set_alpha(int(255 * min(1.0, alpha)))
    surface.blit(panel, box)


def argus_line(surface, line: str, t: float):
    """ARGUS speaks as you enter a room: typed out, held, then gone."""
    if not line or t > 6.0 or t < 0.9:
        return
    t -= 0.9
    shown = line[: int(t * 38)]
    alpha = min(1.0, (5.1 - t) * 1.5)
    if alpha <= 0 or not shown:
        return
    f = S.font(20, S.UI, True)
    label = S.font(14, S.UI, True).render("ARGUS", True, S.GOLD)
    img = f.render(shown, True, (255, 236, 200))
    w = max(420, img.get_width() + label.get_width() + 60)
    box = pygame.Rect(0, 0, w, 40)
    box.midtop = (WIDTH // 2, BAR_H + 14)
    panel = pygame.Surface(box.size, pygame.SRCALPHA)
    panel.fill((*S.PANEL, int(235 * alpha)))
    pygame.draw.rect(panel, (*S.GOLD, int(255 * alpha)), (0, 0, 4, box.h))
    label.set_alpha(int(255 * alpha))
    img.set_alpha(int(255 * alpha))
    panel.blit(label, (14, (40 - label.get_height()) // 2))
    panel.blit(img, (28 + label.get_width(), (40 - img.get_height()) // 2))
    surface.blit(panel, box.topleft)


def crosshair(surface, pos, t: float, colour=S.PLAYER):
    x, y = int(pos[0]), int(pos[1])
    pygame.draw.circle(surface, S.OUTLINE, (x, y), 10, 4)
    pygame.draw.circle(surface, colour, (x, y), 9, 2)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        pygame.draw.line(surface, S.OUTLINE, (x + dx * 12, y + dy * 12), (x + dx * 20, y + dy * 20), 5)
        pygame.draw.line(surface, colour, (x + dx * 13, y + dy * 13), (x + dx * 19, y + dy * 19), 2)
    pygame.draw.circle(surface, S.WHITE, (x, y), 2)
