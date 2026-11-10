import math
import os
import sys

import pygame

BG = (27, 30, 36)
FLOOR = (66, 71, 80)
WALL = (38, 41, 48)
WALL_TOP = (46, 50, 58)
WALL_LIP = (98, 104, 115)
COVER = (44, 48, 56)
COVER_TOP = (54, 59, 68)
OUTLINE = (22, 24, 29)
PANEL = (24, 27, 33)
WHITE = (236, 238, 242)
DIM = (152, 159, 170)
FAINT = (98, 104, 115)
PLAYER = (72, 200, 220)
DANGER = (226, 74, 74)
GOOD = (96, 200, 120)
GOLD = (232, 180, 64)
LOCKED = (196, 64, 72)

DISPLAY = "dincondensed,avenirnextcondensed,futura,arialblack,arial"
UI = "avenirnextcondensed,avenirnext,futura,helveticaneue,arial"
MONO = "menlo,monaco,couriernew,monospace"

_fonts: dict = {}
_discs: dict = {}


def reset():
    _fonts.clear()


FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
BUNDLED = {DISPLAY: ("BarlowCondensed-SemiBold.ttf", "BarlowCondensed-Bold.ttf", 0.87),
           UI: ("BarlowSemiCondensed-Medium.ttf", "BarlowSemiCondensed-SemiBold.ttf", 1.02),
           MONO: ("IBMPlexMono-Regular.ttf", "IBMPlexMono-SemiBold.ttf", 1.0)}
_system: dict = {}


def _has_system_font(family: str) -> bool:
    if sys.platform == "emscripten":
        return False
    if family not in _system:
        _system[family] = pygame.font.match_font(family.split(",")[0]) is not None
    return _system[family]


def font(size: int, family: str = UI, bold: bool = False) -> pygame.font.Font:
    key = (size, family, bold)
    if key not in _fonts:
        if family in BUNDLED and not _has_system_font(family):
            regular, heavy, scale = BUNDLED[family]
            path = os.path.join(FONT_DIR, heavy if bold else regular)
            _fonts[key] = pygame.font.Font(path, max(1, round(size * scale)))
        else:
            _fonts[key] = pygame.font.SysFont(family, size, bold=bold)
    return _fonts[key]


def display(size: int) -> pygame.font.Font:
    return font(size, DISPLAY, True)


def mono(size: int, bold: bool = False) -> pygame.font.Font:
    return font(size, MONO, bold)


def text(surface, s: str, f: pygame.font.Font, colour, pos, anchor: str = "topleft", alpha: int = 255):
    img = f.render(s, True, colour)
    if alpha < 255:
        img.set_alpha(alpha)
    rect = img.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    surface.blit(img, rect)
    return rect


def spaced(surface, s: str, f: pygame.font.Font, colour, pos, spacing: int, anchor: str = "center", alpha=255):
    imgs = [f.render(ch, True, colour) for ch in s]
    width = sum(i.get_width() for i in imgs) + spacing * (len(imgs) - 1)
    height = max(i.get_height() for i in imgs)
    strip = pygame.Surface((width, height), pygame.SRCALPHA)
    x = 0
    for img in imgs:
        strip.blit(img, (x, 0))
        x += img.get_width() + spacing
    if alpha < 255:
        strip.set_alpha(alpha)
    rect = strip.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    surface.blit(strip, rect)
    return rect


def disc(surface, pos, radius: float, colour, alpha: int = 255):
    radius = max(1, int(radius))
    if alpha >= 255:
        pygame.draw.circle(surface, colour, (int(pos[0]), int(pos[1])), radius)
        return
    key = (radius, tuple(colour), max(0, alpha) // 16 * 16)
    if key not in _discs:
        if len(_discs) > 256:
            _discs.clear()
        img = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(img, (*colour, key[2]), (radius, radius), radius)
        _discs[key] = img
    surface.blit(_discs[key], (int(pos[0]) - radius, int(pos[1]) - radius))


def mix(a, b, t: float):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def scale(c, k: float):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def polygon(center, radius: float, sides: int, angle: float):
    return [(center[0] + math.cos(angle + 2 * math.pi * i / sides) * radius,
             center[1] + math.sin(angle + 2 * math.pi * i / sides) * radius) for i in range(sides)]


def dashed(surface, colour, a, b, dash: int = 8, gap: int = 6, width: int = 2):
    length = math.dist(a, b)
    if length < 1:
        return
    dx, dy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    d = 0.0
    while d < length:
        e = min(length, d + dash)
        pygame.draw.line(surface, colour, (a[0] + dx * d, a[1] + dy * d), (a[0] + dx * e, a[1] + dy * e), width)
        d += dash + gap


def keycap(surface, label: str, center, colour=WHITE, size: int = 18):
    f = mono(size, True)
    img = f.render(label, True, colour)
    box = img.get_rect(center=(int(center[0]), int(center[1]))).inflate(22, 12)
    pygame.draw.rect(surface, PANEL, box)
    pygame.draw.rect(surface, scale(colour, 0.7), box, 2)
    surface.blit(img, img.get_rect(center=box.center))
    return box


def wrap(s: str, f: pygame.font.Font, width: int) -> list[str]:
    lines, line = [], ""
    for word in s.split():
        test = f"{line} {word}".strip()
        if f.size(test)[0] <= width or not line:
            line = test
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines
