import math

import pygame

from game.config import TILE, VIEW_HALF_ANGLE, ALERT_HALF_ANGLE
from game.geometry import distance
from game.room import COLOURS
from game.ui import style as S


def px(p):
    return p[0] * TILE, p[1] * TILE


_layer = None


def draw(surface, room, mouse, t: float, director=None):
    global _layer
    if _layer is None or _layer.get_size() != surface.get_size():
        _layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    layer = _layer
    layer.fill((0, 0, 0, 0))
    focus = None
    if room.enemies:
        m = (mouse[0] / TILE, mouse[1] / TILE)
        nearest = min(room.enemies, key=lambda e: distance(e.pos, m))
        if distance(nearest.pos, m) < 2.5:
            focus = nearest
    if focus is not None:
        _heatmap(layer, room, focus)
    for e in room.enemies:
        if not e.alert or e is focus:
            _cone(layer, room, e)
        _knowledge(layer, room, e, t)
    surface.blit(layer, (0, 0))
    placed: list[pygame.Rect] = []
    for e in room.enemies:
        _card(surface, room, e, e is focus, placed)
    _panel(surface, room, focus, director)


def _cone(layer, room, e):
    x, y = px(e.pos)
    half = ALERT_HALF_ANGLE if e.alert else VIEW_HALF_ANGLE
    reach = e.view_range * (1.2 if e.alert else 1.0)
    pts = [(x, y)]
    for i in range(21):
        a = e.facing - half + 2 * half * i / 20
        d = room.grid.raycast(e.pos, a, reach)
        pts.append((x + math.cos(a) * d * TILE, y + math.sin(a) * d * TILE))
    pygame.draw.lines(layer, (*COLOURS[e.kind], 90), True, pts, 1)


def _knowledge(layer, room, e, t):
    colour = COLOURS[e.kind]
    x, y = px(e.pos)
    s = e.senses
    if s.sees:
        pygame.draw.line(layer, (120, 255, 160, 170), (x, y), px(room.player.pos), 1)
    elif e.alert and s.last_known is not None:
        lx, ly = px(s.last_known)
        S.dashed(layer, (255, 90, 90, 190), (x, y), (lx, ly), 6, 6, 1)
        pygame.draw.line(layer, (255, 90, 90, 230), (lx - 7, ly - 7), (lx + 7, ly + 7), 3)
        pygame.draw.line(layer, (255, 90, 90, 230), (lx - 7, ly + 7), (lx + 7, ly - 7), 3)
        S.text(layer, f"{s.age(room.time):.1f}s ago", S.mono(11, True), (255, 150, 150), (lx + 10, ly - 8))
    if e.path:
        pts = [(x, y)] + [px(p) for p in e.path]
        for a, b in zip(pts, pts[1:]):
            S.dashed(layer, (*colour, 200), a, b, 4, 5, 2)
    if e.spot is not None and e.alert:
        sx, sy = px(e.spot)
        pygame.draw.polygon(layer, (*colour, 220), [(sx, sy - 8), (sx + 8, sy), (sx, sy + 8), (sx - 8, sy)], 2)


def _heatmap(layer, room, e):
    entry = room.tactics.debug.get(e.uid)
    if not entry:
        return
    purpose, scores, best = entry
    if not scores:
        return
    lo, hi = min(scores.values()), max(scores.values())
    span = max(1e-6, hi - lo)
    for (c, r), v in scores.items():
        k = (v - lo) / span
        colour = S.mix((40, 90, 255), (255, 60, 60), k)
        pygame.draw.rect(layer, (*colour, int(40 + 110 * k)), (c * TILE + 2, r * TILE + 2, TILE - 4, TILE - 4))
    if best is not None:
        pygame.draw.rect(layer, (255, 255, 255, 255), (best[0] * TILE, best[1] * TILE, TILE, TILE), 3)
        S.text(layer, purpose.upper(), S.font(14, S.UI, True), S.WHITE, (best[0] * TILE + TILE // 2, best[1] * TILE - 4), "midbottom")


def _card(surface, room, e, focused, placed):
    colour = COLOURS[e.kind]
    x, y = px(e.pos)
    title = f"{e.designation}   {e.state}"
    tags = []
    if e.uid in room.coordinator.holders:
        tags.append("TOKEN")
    if room.coordinator.flanker == e.uid:
        tags.append("FLANKER")
    if not e.alert:
        tags.append(f"suspicion {int(e.senses.suspicion * 100)}%")
    if e.firewall > 0:
        tags.append("FIREWALL")
    if e.predicts:
        tags.append("LEADS SHOTS")
    if e.blocked:
        tags.append("ALLY IN LINE")
    if e.side == "player":
        tags.append("REWRITTEN")
    rows = sorted(e.scores.items(), key=lambda kv: -kv[1])[:4] if e.alert else []
    if e.alert and len(e.foe_scores) > 1:
        target = max(e.foe_scores, key=e.foe_scores.get)
        tags.append(f"target: {target}")
    f = S.font(13, S.UI, True)
    small = S.mono(11)
    width = 150
    height = 20 + (14 if tags else 0) + 14 * len(rows)
    box = pygame.Rect(0, 0, width, height)
    box.midtop = (int(x), int(y + e.radius * TILE + 16))
    box.clamp_ip(surface.get_rect().inflate(-8, -8))
    for _ in range(8):
        hit = box.collidelist(placed)
        if hit < 0:
            break
        box.y = placed[hit].bottom + 2
    placed.append(box)
    panel = pygame.Surface(box.size, pygame.SRCALPHA)
    panel.fill((*S.PANEL, 235 if focused else 200))
    surface.blit(panel, box.topleft)
    pygame.draw.rect(surface, colour if focused else S.scale(colour, 0.6), box, 2 if focused else 1)
    S.text(surface, title, f, colour, (box.x + 6, box.y + 3))
    yy = box.y + 20
    if tags:
        S.text(surface, "  ".join(tags), small, S.GOLD, (box.x + 6, yy))
        yy += 14
    for i, (name, v) in enumerate(rows):
        chosen = name == e.action
        S.text(surface, name, small, S.WHITE if chosen else S.DIM, (box.x + 6, yy))
        bar = pygame.Rect(box.x + 74, yy + 3, int(64 * min(1.2, max(0.0, v)) / 1.2), 7)
        pygame.draw.rect(surface, colour if chosen else S.FAINT, bar)
        S.text(surface, f"{v:.2f}", small, S.WHITE if chosen else S.DIM, (box.right - 4, yy), "topright")
        yy += 14


def _focus_line(room, focus) -> str:
    if focus is None:
        return "hover an enemy: see its tactical map"
    entry = room.tactics.debug.get(focus.uid)
    if not entry:
        return f"{focus.name}: no spots scored yet"
    return f"{focus.name}: {entry[0]} map (white = best)"


LEGEND = [("cone", "PERCEPTION", "what it can see"), ("sight", "LINE OF SIGHT", "it sees you now"),
          ("memory", "MEMORY", "where it last saw you"), ("path", "A* PATH", "the route it planned"),
          ("state", "FSM STATE", "on its card, by its name"), ("bars", "DESIRABILITY", "each option scored, best wins")]


def _sample(surface, kind, x, y):
    if kind == "cone":
        pygame.draw.polygon(surface, S.DIM, [(x, y), (x + 22, y - 7), (x + 22, y + 7)], 1)
    elif kind == "sight":
        pygame.draw.line(surface, (120, 255, 160), (x, y), (x + 22, y), 1)
    elif kind == "memory":
        S.dashed(surface, (255, 90, 90), (x, y), (x + 12, y), 3, 3, 1)
        pygame.draw.line(surface, (255, 90, 90), (x + 15, y - 4), (x + 22, y + 4), 2)
        pygame.draw.line(surface, (255, 90, 90), (x + 15, y + 4), (x + 22, y - 4), 2)
    elif kind == "path":
        S.dashed(surface, S.GOLD, (x, y), (x + 22, y), 4, 3, 2)
    elif kind == "state":
        pygame.draw.rect(surface, S.DIM, (x, y - 5, 22, 10), 1)
    elif kind == "bars":
        for k, w in enumerate((20, 13, 8)):
            pygame.draw.rect(surface, S.WHITE if k == 0 else S.FAINT, (x, y - 5 + k * 4, w, 2))


def _panel(surface, room, focus, director=None):
    c = room.coordinator
    box = pygame.Rect(10, 48, 280, 70 + 20 * len(LEGEND))
    panel = pygame.Surface(box.size, pygame.SRCALPHA)
    panel.fill((*S.PANEL, 225))
    surface.blit(panel, box.topleft)
    pygame.draw.rect(surface, S.scale(S.GOLD, 0.5), box, 1)
    S.text(surface, "AI View", S.font(16, S.UI, True), S.GOLD, (box.x + 10, box.y + 6))
    S.text(surface, "Tab to close", S.font(13, S.UI, True), S.DIM, (box.right - 10, box.y + 7), "topright")
    squad = f"SQUAD   {len(c.holders)} / {c.slots} attack tokens   flanker {'#' + str(c.flanker) if c.flanker else 'none'}"
    S.text(surface, squad, S.font(12, S.UI, True), S.WHITE, (box.x + 10, box.y + 28))
    y = box.y + 56
    for kind, name, what in LEGEND:
        _sample(surface, kind, box.x + 12, y + 7)
        S.text(surface, name, S.font(12, S.UI, True), S.WHITE, (box.x + 44, y))
        S.text(surface, what, S.font(12, S.UI, True), S.DIM, (box.x + 140, y))
        y += 20
    S.text(surface, _focus_line(room, focus), S.font(12, S.UI, True), S.GOLD, (box.x + 10, y + 2))
    if director is not None:
        _director(surface, director, box.bottom + 8)


def _director(surface, d, top: int):
    p = d.profile
    habits = [("far away", p.far), ("up close", p.close), ("unseen", p.hidden), ("moving", p.moving),
              ("accuracy", p.accuracy), ("rewrites/room", min(1.0, p.rewrites / 2))]
    rows = sorted(d.scores.items(), key=lambda kv: -kv[1])[:4]
    box = pygame.Rect(10, top, 270, 44 + 16 * len(habits) + 16 * len(rows))
    panel = pygame.Surface(box.size, pygame.SRCALPHA)
    panel.fill((*S.PANEL, 225))
    surface.blit(panel, box.topleft)
    pygame.draw.rect(surface, S.scale(S.GOLD, 0.6), box, 1)
    S.text(surface, "ARGUS'S MODEL OF YOU", S.font(14, S.UI, True), S.GOLD, (box.x + 10, box.y + 5))
    y = box.y + 24
    for name, v in habits:
        S.text(surface, name, S.mono(11), S.DIM, (box.x + 10, y))
        pygame.draw.rect(surface, (50, 40, 20), (box.x + 120, y + 3, 100, 7))
        pygame.draw.rect(surface, S.GOLD, (box.x + 120, y + 3, int(100 * max(0.0, min(1.0, v))), 7))
        y += 16
    S.text(surface, "countermeasures (deployed in white)", S.mono(11), S.GOLD, (box.x + 10, y + 2))
    y += 18
    for name, v in rows:
        colour = S.WHITE if name in d.deployed else S.DIM
        S.text(surface, f"{name:<11} {v:.2f}", S.mono(11, name in d.deployed), colour, (box.x + 10, y))
        y += 16
