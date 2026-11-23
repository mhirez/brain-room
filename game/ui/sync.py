"""DEBUG view (the SYNC mechanic): hold right click and time slows; you trained ARGUS, so you can
read its robots' decisions. Every robot shows what it INTENDS to do.

This is the player-facing half of the AI View: the same decisions, shown as plain words.
  ATTACK   it has an attack token and is winding up
  FLANK    it's going round the side (its dashed route is drawn)
  COVER    it's running to (or hiding in) a spot you can't see
  MOVE     it's repositioning / closing in / circling
  HEAL     it's healing someone (who is highlighted)
  RETREAT  it's getting away from you
  SEARCH   it has lost you (or never saw you)
Hover a machine to read its mind: its options, scored, and whether you can rewrite it.
"""

import math

import pygame

from game.config import TILE, WIDTH, HEIGHT
from game.geometry import distance
from game.room import COLOURS
from game.ui import style as S

INTENT = {"AIM": ("ATTACK", S.DANGER), "FIRE": ("ATTACK", S.DANGER), "WINDUP": ("ATTACK", S.DANGER),
          "CHARGE": ("ATTACK", S.DANGER), "FLANK": ("FLANK", (255, 160, 60)),
          "TAKE COVER": ("COVER", (120, 170, 255)), "HIDE": ("COVER", (120, 170, 255)),
          "REPOSITION": ("MOVE", S.WHITE), "POSITION": ("MOVE", S.WHITE), "STALK": ("MOVE", S.WHITE),
          "CIRCLE": ("WAIT TURN", S.DIM), "STRAFE": ("WAIT TURN", S.DIM), "HEAL": ("HEAL", S.GOOD),
          "SHELTER": ("RETREAT", S.GOLD), "FLEE": ("RETREAT", S.GOLD), "EVADE": ("RETREAT", S.GOLD),
          "TAG ALONG": ("FOLLOW", S.DIM), "PATROL": ("PATROL", S.FAINT), "INVESTIGATE": ("SEARCH", S.GOLD),
          "SEARCH": ("SEARCH", S.GOLD), "ENGAGE": ("THINKING", S.DIM), "STUNNED": ("DAZED", S.WHITE),
          "RECOVER": ("RECOVER", S.DIM), "DRIFT": ("MOVE", S.WHITE), "SWEEP": ("ATTACK", S.DANGER),
          "ESCORT": ("WITH YOU", S.PLAYER), "BASH": ("ATTACK", S.DANGER), "DIVE": ("ATTACK", S.DANGER),
          "ADVANCE": ("MOVE", S.WHITE), "GUARD": ("GUARD", (255, 180, 230)), "SEEK": ("MOVE", S.WHITE),
          "FLOCK": ("WAIT TURN", S.DIM)}


def px(p):
    return p[0] * TILE, p[1] * TILE


def hovered(room, mouse_px):
    m = (mouse_px[0] / TILE, mouse_px[1] / TILE)
    near = [e for e in room.enemies if distance(e.pos, m) < max(1.2, e.radius + 0.6)]
    return min(near, key=lambda e: distance(e.pos, m)) if near else None


_layers: dict = {}


def _layer(name: str) -> pygame.Surface:
    """Full-screen see-through layers, made once and reused every frame."""
    if name not in _layers:
        _layers[name] = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        if name == "veil":
            _layers[name].fill((20, 34, 56, 110))
    return _layers[name]


def draw(surface, room, mouse_px, t: float, player):
    surface.blit(_layer("veil"), (0, 0))
    focus = hovered(room, mouse_px)
    layer = _layer("marks")
    layer.fill((0, 0, 0, 0))
    for e in room.enemies:
        x, y = px(e.pos)
        if e.spot is not None and e.state in ("FLANK", "TAKE COVER", "REPOSITION", "POSITION", "EVADE", "FLEE"):
            S.dashed(layer, (*COLOURS[e.kind], 200), (x, y), px(e.spot), 6, 5, 2)
        if e.foe is not None and e.foe is not room.player and e.side == "argus":
            pygame.draw.line(layer, (*S.PLAYER, 170), (x, y), px(e.foe.pos), 1)   # hunting a traitor
        beam = getattr(e, "beam", None)
        if beam is not None:
            pygame.draw.line(layer, (*S.GOOD, 200), (x, y), px(beam.pos), 2)
    surface.blit(layer, (0, 0))
    for e in room.enemies:
        _intent(surface, room, e, t)
    if focus is not None:
        _mind(surface, room, focus, t)
    _header(surface, player, t)


def _intent(surface, room, e, t):
    x, y = px(e.pos)
    label, colour = INTENT.get(e.state, (e.state, S.WHITE))
    if e.side == "player":
        label, colour = ("YOURS " + label if label != "WITH YOU" else label), S.PLAYER
    elif e.uid in room.coordinator.holders:
        label = "ATTACK"
    f = S.font(14, S.UI, True)
    img = f.render(label, True, colour)
    box = img.get_rect(midbottom=(int(x), int(y - e.radius * TILE * 1.3 - 14))).inflate(10, 4)
    pygame.draw.rect(surface, S.PANEL, box)
    pygame.draw.rect(surface, colour, box, 2)
    surface.blit(img, img.get_rect(center=box.center))


def _mind(surface, room, e, t):
    x, y = px(e.pos)
    r = e.radius * TILE * 1.6 + 6
    colour = S.PLAYER if e.side == "player" else COLOURS[e.kind]
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):                   # target brackets
        cx, cy = x + sx * r, y + sy * r
        pygame.draw.line(surface, colour, (cx, cy), (cx - sx * 10, cy), 3)
        pygame.draw.line(surface, colour, (cx, cy), (cx, cy - sy * 10), 3)
    why = room.rewritable(e)
    rows = sorted(e.scores.items(), key=lambda kv: -kv[1])[:3] if e.alert else []
    width, height = 250, 76 + 18 * len(rows)
    box = pygame.Rect(0, 0, width, height)
    box.midleft = (int(x + r + 14), int(y))
    if box.right > WIDTH - 8:
        box.midright = (int(x - r - 14), int(y))
    box.clamp_ip(pygame.Rect(8, 48, WIDTH - 16, HEIGHT - 56))
    panel = pygame.Surface(box.size, pygame.SRCALPHA)
    panel.fill((*S.PANEL, 240))
    surface.blit(panel, box.topleft)
    pygame.draw.rect(surface, colour, box, 2)
    name = f"{e.name}  {e.designation}" + ("  (OVERRIDDEN)" if e.side == "player" else "")
    S.text(surface, name, S.display(20), colour, (box.x + 10, box.y + 6))
    if e.kind != "warden":
        S.text(surface, f"{e.model}, generation {e.generation} copy", S.font(13, S.UI, True), S.DIM,
               (box.x + 10, box.y + 30))
    yy = box.y + 50
    for option, v in rows:
        chosen = option == e.action
        S.text(surface, option, S.mono(12, chosen), S.WHITE if chosen else S.DIM, (box.x + 10, yy))
        bar = pygame.Rect(box.x + 104, yy + 4, int(90 * min(1.2, max(0.0, v)) / 1.2), 8)
        pygame.draw.rect(surface, colour if chosen else S.FAINT, bar)
        S.text(surface, f"{v:.2f}", S.mono(12), S.WHITE if chosen else S.DIM, (box.right - 8, yy), "topright")
        yy += 18
    if e.side == "player":
        left = max(0.0, e.turned_until - room.time)
        S.text(surface, f"fights for you: {left:.1f}s", S.font(14, S.UI, True), S.PLAYER, (box.x + 10, yy + 2))
    elif why:
        S.text(surface, why, S.font(14, S.UI, True), (255, 120, 120), (box.x + 10, yy + 2))
    else:
        pulse = 0.6 + 0.4 * math.sin(t * 10)
        S.text(surface, "CLICK: OVERRIDE  (1 charge)", S.font(14, S.UI, True), S.mix(S.BG, S.PLAYER, pulse),
               (box.x + 10, yy + 2))


def _header(surface, player, t):
    """What's left of the debugger, and what a click will do, low in the middle of the screen."""
    y = HEIGHT - 70
    label = S.spaced(surface, "DEBUG", S.display(22), S.PLAYER, (WIDTH // 2 - 100, y), 4, "midright")
    bar = pygame.Rect(label.right + 14, y - 2, 200, 4)
    pygame.draw.rect(surface, S.OUTLINE, bar)
    pygame.draw.rect(surface, S.PLAYER, (bar.x, bar.y, int(bar.w * player.sync), bar.h))
    hint = "Click a robot to override it" if player.charges else "No override charges left. Every 5 kills gives one."
    S.text(surface, hint, S.font(15, S.UI, True), S.DIM, (WIDTH // 2, y + 22), "center")
