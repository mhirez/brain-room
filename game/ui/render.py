import math
import random

import pygame

from game.ai.charger import CHARGE_DIST
from game.ai.grunt import FAN
from game.config import TILE, WIDTH, HEIGHT, VIEW_HALF_ANGLE
from game.room import COLOURS
from game.rooms import ENTRY, EXIT
from game.ui import art
from game.ui import style as S

RACK_PUSH = 2.0
RACK_FRICTION = 12.0
RACK_MAX = 8.0
RACK_EDGE = 3
LAMPS = ((0.5, 3.5), (0.5, 14.5), (31.5, 3.5), (31.5, 14.5))


def px(p) -> tuple[float, float]:
    return p[0] * TILE, p[1] * TILE


class Renderer:
    def __init__(self):
        self._bg_for = None
        self.bg: pygame.Surface | None = None
        self.floor_bg: pygame.Surface | None = None
        self.anchors: list[tuple[float, float]] = []
        self.overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.rng = random.Random(11)
        self.racks: list[pygame.Rect] = []
        self.rack_of: dict = {}
        self.rack_motion: list[list[float]] = []
        self._last_t = None

    def background(self, room) -> pygame.Surface:
        if self._bg_for is not room:
            self.bg = build_background(room.grid, room.plan.theme)
            self.room_grid, self.room_theme = room.grid, room.plan.theme
            self.floor_bg = None
            self._find_racks(room.grid)
            self.anchors = [(c * TILE, r * TILE) for c, r in ((4, 0), (16, 0), (27, 0), (4, 18), (16, 18), (27, 18))]
            self._bg_for = room
        return self.bg

    def _find_racks(self, grid):
        self.racks, self.rack_of, self.rack_motion = [], {}, []
        for r in range(grid.rows):
            for c in range(grid.cols):
                if grid.at(c, r) != "X" or (c, r) in self.rack_of:
                    continue
                block, todo = len(self.racks), [(c, r)]
                self.rack_of[(c, r)] = block
                c0, r0, c1, r1 = c, r, c, r
                while todo:
                    tc, tr = todo.pop()
                    c0, r0, c1, r1 = min(c0, tc), min(r0, tr), max(c1, tc), max(r1, tr)
                    for n in ((tc + 1, tr), (tc - 1, tr), (tc, tr + 1), (tc, tr - 1)):
                        if grid.at(*n) == "X" and n not in self.rack_of:
                            self.rack_of[n] = block
                            todo.append(n)
                rect = pygame.Rect(c0 * TILE, r0 * TILE, (c1 - c0 + 1) * TILE, (r1 - r0 + 1) * TILE)
                self.racks.append(rect.inflate(RACK_EDGE * 2, RACK_EDGE * 2))
                self.rack_motion.append([0.0, 0.0, 0.0, 0.0])

    def _rack_offset(self, block: int) -> tuple[int, int]:
        m = self.rack_motion[block]
        return round(m[0]), round(m[1])

    def _move_racks(self, fx, dt: float):
        for tile, (dx, dy), strength in fx.rack_hits:
            block = self.rack_of.get(tuple(tile))
            if block is not None:
                m = self.rack_motion[block]
                m[2] += dx * RACK_PUSH * RACK_FRICTION * strength
                m[3] += dy * RACK_PUSH * RACK_FRICTION * strength
        fx.rack_hits.clear()
        slow = math.exp(-RACK_FRICTION * dt)
        for m in self.rack_motion:
            if m[2] == 0.0 and m[3] == 0.0:
                continue
            m[0] += m[2] * dt
            m[1] += m[3] * dt
            m[2] *= slow
            m[3] *= slow
            far = math.hypot(m[0], m[1])
            if far > RACK_MAX:
                m[0], m[1] = m[0] * RACK_MAX / far, m[1] * RACK_MAX / far
            if abs(m[2]) + abs(m[3]) < 0.5:
                m[2] = m[3] = 0.0

    def _racks(self, surface, off):
        for block, rect in enumerate(self.racks):
            dx, dy = self._rack_offset(block)
            if dx or dy:
                if self.floor_bg is None:
                    self.floor_bg = build_background(self.room_grid, self.room_theme, racks=False)
                surface.blit(self.floor_bg, (rect.x + off[0], rect.y + off[1]), area=rect)
                surface.blit(self.bg, (rect.x + dx + off[0], rect.y + dy + off[1]), area=rect)

    def _bake_wrecks(self, fx):
        for (x, y), colour, size in fx.new_wrecks:
            r = TILE * 0.7 * size
            scorch = pygame.Surface((int(r * 2) + 2, int(r * 2) + 2), pygame.SRCALPHA)
            pts = [(r + math.cos(k * math.pi / 5) * r * self.rng.uniform(0.6, 1.0),
                    r + math.sin(k * math.pi / 5) * r * self.rng.uniform(0.6, 1.0)) for k in range(10)]
            pygame.draw.polygon(scorch, (20, 21, 25, 110), pts)
            self.bg.blit(scorch, (int(x - r), int(y - r)))
            for _ in range(int(5 + 4 * size)):
                a = self.rng.uniform(0, 2 * math.pi)
                d = self.rng.uniform(2, TILE * 0.55 * size)
                cx, cy = x + math.cos(a) * d, y + math.sin(a) * d
                s = self.rng.uniform(2, 6) * size
                pts = S.polygon((cx, cy), s, self.rng.choice((3, 4)), self.rng.uniform(0, 6))
                pygame.draw.polygon(self.bg, self.rng.choice((art.METAL, art.METAL_DARK, art.METAL_LIGHT)), pts)
            bit = (x + self.rng.uniform(-6, 6), y + self.rng.uniform(-6, 6))
            pygame.draw.circle(self.bg, S.scale(colour, 0.6), (int(bit[0]), int(bit[1])), 2)
        fx.new_wrecks.clear()

    def draw(self, surface, room, fx, t: float, off=(0, 0)):
        dt = 0.0 if self._last_t is None else max(0.0, min(0.05, t - self._last_t))
        self._last_t = t
        building = self.background(room)
        self._bake_wrecks(fx)
        self._move_racks(fx, dt)
        if off != (0, 0):
            surface.fill(S.BG)
        surface.blit(building, off)
        self._racks(surface, off)
        self._doors(surface, room, t, off)
        self._lamps(surface, room, t, off)
        fx.draw_under(surface, off)
        self._pickups(surface, room, t, off)

        self.overlay.fill((0, 0, 0, 0))
        for e in room.enemies:
            if not e.alert and e.kind != "warden" and not getattr(e, "dormant", False):
                self._cone(self.overlay, room, e, off)
        for e in room.enemies:
            self._telegraph(self.overlay, surface, room, e, t, off)
        self._shells(self.overlay, room, off)
        surface.blit(self.overlay, (0, 0))
        fx.draw_network(surface, off)

        for e in room.enemies:
            beam = getattr(e, "beam", None)
            if beam is not None and not beam.dead:
                self._heal_beam(surface, e, beam, t, off)
        for e in room.enemies:
            self._enemy(surface, e, t, off)
        self._player(surface, room.player, t, off)
        self._bullets(surface, room, off)
        fx.draw(surface, off)
        for e in room.enemies:
            self._icon(surface, e, off)

    def _lamps(self, surface, room, t, off):
        clear = room.state != "fight"
        for i, (c, r) in enumerate(LAMPS):
            x, y = c * TILE + off[0], r * TILE + off[1]
            on = clear or math.sin(t * 6 + i) > -0.2
            colour = S.GOOD if clear else (S.DANGER if on else (90, 34, 38))
            box = pygame.Rect(0, 0, 10, 14)
            box.center = (int(x), int(y))
            pygame.draw.rect(surface, S.OUTLINE, box.inflate(4, 4))
            pygame.draw.rect(surface, colour, box)

    def _doors(self, surface, room, t, off):
        for tiles, is_exit in ((ENTRY, False), (EXIT, True)):
            locked = room.grid.at(*tiles[0]) == "D"
            x0, y0 = tiles[0][0] * TILE + off[0], tiles[0][1] * TILE + off[1]
            rect = pygame.Rect(x0, y0, TILE, TILE * len(tiles))
            if locked:
                pygame.draw.rect(surface, (40, 14, 24), rect)
                for i in range(4):
                    y = rect.y + 8 + i * (rect.height - 16) // 3
                    pygame.draw.line(surface, S.LOCKED, (rect.x + 6, y), (rect.right - 6, y), 4)
            else:
                opened = min(1.0, (room.time - room.cleared_at) / 0.6) if is_exit else 1.0
                pygame.draw.rect(surface, (34, 52, 42), rect)
                if opened < 1:
                    half = int(rect.height / 2 * (1 - opened))
                    pygame.draw.rect(surface, (40, 14, 24), (rect.x, rect.y, rect.w, half))
                    pygame.draw.rect(surface, (40, 14, 24), (rect.x, rect.bottom - half, rect.w, half))
                if is_exit and room.state != "fight":
                    for k in range(3):
                        phase = (t * 1.6 + k / 3) % 1
                        if math.sin(phase * math.pi) < 0.25:
                            continue
                        x = rect.x - TILE * 2.4 + phase * TILE * 2.2
                        cy = rect.centery
                        pygame.draw.lines(surface, S.OUTLINE, False, [(x, cy - 12), (x + 11, cy), (x, cy + 12)], 8)
                        pygame.draw.lines(surface, S.GOOD, False, [(x, cy - 12), (x + 11, cy), (x, cy + 12)], 4)
            pygame.draw.rect(surface, S.OUTLINE, rect, 2)

    def _pickups(self, surface, room, t, off):
        for k in room.pickups:
            x, y = px(k.pos)
            x, y = x + off[0], y + off[1] + math.sin(t * 5 + k.pos[0]) * 3
            art.shadow(surface, (x + 2, y + 10 - math.sin(t * 5 + k.pos[0]) * 3), 20, 8)
            pygame.draw.rect(surface, S.OUTLINE, (x - 11, y - 9, 22, 18))
            pygame.draw.rect(surface, S.WHITE, (x - 9, y - 7, 18, 14))
            pygame.draw.line(surface, S.GOOD, (x - 5, y), (x + 5, y), 4)
            pygame.draw.line(surface, S.GOOD, (x, y - 5), (x, y + 5), 4)

    def _cone(self, overlay, room, e, off):
        x, y = px(e.pos)
        s = e.senses.suspicion
        colour = S.mix((255, 255, 255), (255, 220, 60), min(1, s * 2)) if s < 0.5 else \
            S.mix((255, 220, 60), S.DANGER, (s - 0.5) * 2)
        pts = [(x + off[0], y + off[1])]
        n = 14
        for i in range(n + 1):
            a = e.facing - VIEW_HALF_ANGLE + 2 * VIEW_HALF_ANGLE * i / n
            d = room.grid.raycast(e.pos, a, e.view_range)
            pts.append((x + off[0] + math.cos(a) * d * TILE, y + off[1] + math.sin(a) * d * TILE))
        pygame.draw.polygon(overlay, (*colour, int(22 + 40 * s)), pts)
        pygame.draw.lines(overlay, (*colour, int(40 + 90 * s)), True, pts, 1)

    def _telegraph(self, overlay, surface, room, e, t, off):
        if e.windup <= 0 and e.state not in ("SWEEP",):
            return
        x, y = px(e.pos)
        x, y = x + off[0], y + off[1]
        colour = room.colour(e)
        k = e.windup
        live = S.WHITE if e.locked else colour
        alpha = 230 if e.locked else int(70 + 150 * k)
        width = 3 if e.locked else 2
        grid = room.grid
        kind = e.kind
        if kind == "grunt" and e.state == "AIM":
            for i in (-1, 0, 1):
                a = e.aim + i * getattr(e, "fan", FAN)
                d = min(14.0, grid.raycast(e.pos, a, 14.0))
                end = (x + math.cos(a) * d * TILE, y + math.sin(a) * d * TILE)
                pygame.draw.line(overlay, (*live, alpha if i == 0 else alpha // 2), (x, y), end, width if i == 0 else 1)
        elif kind == "charger" and e.state == "WINDUP":
            self._band(overlay, (x, y), e.aim, e.charge_len * TILE, e.radius * TILE, live, alpha)
            if e.charge_len < CHARGE_DIST - 0.05:
                ex = x + math.cos(e.aim) * (e.charge_len + e.radius) * TILE
                ey = y + math.sin(e.aim) * (e.charge_len + e.radius) * TILE
                pygame.draw.circle(overlay, (*live, alpha), (int(ex), int(ey)), 7, 2)
        elif kind == "sniper" and e.state == "AIM":
            end = (x + math.cos(e.aim) * e.laser_len * TILE, y + math.sin(e.aim) * e.laser_len * TILE)
            pulse = 0.6 + 0.4 * math.sin(t * 30)
            pygame.draw.line(overlay, (*live, int(alpha * (1 if e.locked else pulse))), (x, y), end, 3 if e.locked else 1)
            pygame.draw.circle(overlay, (*live, 230), (int(end[0]), int(end[1])), 5 if e.locked else 3)
        elif kind == "bulwark" and e.state == "WINDUP":
            self._band(overlay, (x, y), e.aim, 2.0 * TILE + e.radius * TILE, e.radius * TILE * 0.9, live, alpha)
        elif kind == "swarm" and e.state == "WINDUP":
            d = min(6.0, room.grid.raycast(e.pos, e.aim, 6.0))
            end = (x + math.cos(e.aim) * d * TILE, y + math.sin(e.aim) * d * TILE)
            pygame.draw.line(overlay, (*live, alpha), (x, y), end, 3 if e.locked else 2)
        elif kind == "mortar" and e.state == "AIM":
            ax, ay = e.aim_point[0] * TILE + off[0], e.aim_point[1] * TILE + off[1]
            ring = int(1.1 * TILE)
            pygame.draw.circle(overlay, (*live, alpha // 4), (int(ax), int(ay)), ring)
            pygame.draw.circle(overlay, (*live, alpha), (int(ax), int(ay)), ring, 3 if e.locked else 2)
            pygame.draw.line(overlay, (*live, alpha // 2), (x, y), (ax, ay), 1)
        elif kind == "warden":
            self._warden_telegraph(overlay, surface, room, e, (x, y), live, alpha, t)
        if e.windup > 0 and e.state in ("AIM", "WINDUP"):
            r = e.radius * TILE * (1.1 + 1.6 * (1 - k))
            pygame.draw.circle(overlay, (*live, alpha), (int(x), int(y)), int(r), 2 if not e.locked else 3)

    def _shells(self, overlay, room, off):
        for s in room.shells:
            colour = room.colour(s.owner) if s.owner is not None else (255, 200, 120)
            tx, ty = s.target[0] * TILE + off[0], s.target[1] * TILE + off[1]
            k = s.progress
            live = S.WHITE if k > 0.8 else colour
            ring = int(s.blast * TILE)
            pygame.draw.circle(overlay, (*colour, 40 + int(60 * k)), (int(tx), int(ty)), ring)
            pygame.draw.circle(overlay, (*live, 230), (int(tx), int(ty)), ring, 2)
            pygame.draw.circle(overlay, (*live, 200), (int(tx), int(ty)), max(3, int(ring * (1.8 - k))), 2)
            sx, sy = s.pos[0] * TILE + off[0], s.pos[1] * TILE + off[1]
            lift = math.sin(k * math.pi) * TILE * 2.2
            pygame.draw.circle(overlay, (0, 0, 0, 110), (int(sx), int(sy)), 5)
            pygame.draw.circle(overlay, (*colour, 255), (int(sx), int(sy - lift)), 6)
            pygame.draw.circle(overlay, (255, 255, 255, 255), (int(sx), int(sy - lift)), 3)

    def _band(self, overlay, origin, angle, length, half, colour, alpha):
        x, y = origin
        dx, dy = math.cos(angle), math.sin(angle)
        nx, ny = -dy * half, dx * half
        pts = [(x + nx, y + ny), (x + dx * length + nx, y + dy * length + ny),
               (x + dx * length - nx, y + dy * length - ny), (x - nx, y - ny)]
        pygame.draw.polygon(overlay, (*colour, alpha // 3), pts)
        pygame.draw.polygon(overlay, (*colour, alpha), pts, 2)

    def _warden_telegraph(self, overlay, surface, room, w, pos, live, alpha, t):
        x, y = pos
        if w.state == "SWEEP":
            end = (x + math.cos(w.aim) * w.beam_len * TILE, y + math.sin(w.aim) * w.beam_len * TILE)
            pygame.draw.line(overlay, (255, 230, 150, 120), pos, end, 18)
            pygame.draw.line(surface, S.WHITE, pos, end, 5)
            pygame.draw.circle(surface, S.GOLD, (int(end[0]), int(end[1])), 9)
            return
        if w.state != "WINDUP":
            return
        attack = w.attack
        if attack == "volley":
            for i in range(7):
                a = w.aim + math.radians(-30 + 10 * i)
                d = min(12.0, room.grid.raycast(w.pos, a, 12.0))
                pygame.draw.line(overlay, (*live, alpha // 2), pos, (x + math.cos(a) * d * TILE, y + math.sin(a) * d * TILE), 1)
        elif attack == "ring":
            r = w.radius * TILE + w.windup * TILE * 3
            pygame.draw.circle(overlay, (*live, alpha), (int(x), int(y)), int(r), 3)
        elif attack == "sweep":
            start = w.sweep_from if w.locked else w.aim - w.sweep_dir * math.radians(60)
            pts = [pos]
            for i in range(13):
                a = start + w.sweep_dir * math.radians(120) * i / 12
                d = min(20.0, room.grid.raycast(w.pos, a, 20.0))
                pts.append((x + math.cos(a) * d * TILE, y + math.sin(a) * d * TILE))
            pygame.draw.polygon(overlay, (*live, alpha // 4), pts)
            pygame.draw.lines(overlay, (*live, alpha), True, pts, 2)
        elif attack == "charge":
            self._band(overlay, pos, w.aim, w.beam_len * TILE, w.radius * TILE, live, alpha)

    def _heal_beam(self, surface, m, target, t, off):
        a = (px(m.pos)[0] + off[0], px(m.pos)[1] + off[1])
        b = (px(target.pos)[0] + off[0], px(target.pos)[1] + off[1])
        pygame.draw.line(surface, S.OUTLINE, a, b, 6)
        pygame.draw.line(surface, S.GOOD, a, b, 3)
        for k in range(3):
            f = (t * 1.8 + k / 3) % 1
            p = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            pygame.draw.circle(surface, S.WHITE, (int(p[0]), int(p[1])), 3)
        pygame.draw.circle(surface, S.GOOD, (int(b[0]), int(b[1])), int(TILE * 0.55), 2)

    def _enemy(self, surface, e, t, off):
        x, y = px(e.pos)
        x, y = x + off[0], y + off[1]
        colour = e.room.colour(e)
        accent = art.DORMANT if getattr(e, "dormant", False) else colour
        white = e.flash > 0
        if e.kind == "warden":
            core = {1: S.GOLD, 2: (255, 150, 40), 3: (255, 70, 60)}[e.phase]
            r = e.radius * TILE
            art.core(surface, e, x, y, r, core, white, t, self.anchors, off)
            if e.shield > 0:
                pygame.draw.circle(surface, S.PLAYER, (int(x), int(y)), int(r * 1.5), 3 if int(t * 10) % 2 else 2)
            return
        r = e.radius * TILE * 1.2
        art.DRAW[e.kind](surface, e, x, y, r, accent, white, t)
        if e.state == "STUNNED":
            for i in range(3):
                b = t * 6 + i * 2 * math.pi / 3
                pygame.draw.circle(surface, S.GOLD, (int(x + math.cos(b) * r), int(y - r * 1.3 + math.sin(b) * r * 0.35)), 3)
        if e.firewall > 0:
            ring = S.polygon((x, y), r * 1.75, 6, t * 0.8)
            pygame.draw.polygon(surface, (170, 210, 255), ring, 2)
        if e.side == "player":
            left = max(0.0, e.turned_until - e.room.time) / e.room.player.stats.rewrite_time
            rect = pygame.Rect(0, 0, int(r * 3.2), int(r * 3.2))
            rect.center = (int(x), int(y))
            pygame.draw.arc(surface, S.PLAYER, rect, math.pi / 2, math.pi / 2 + 2 * math.pi * left, 3)
            pygame.draw.polygon(surface, S.PLAYER, S.polygon((x + r * 1.2, y - r * 1.2), 5, 4, 0))
        if e.hp < e.max_hp:
            w = int(r * 2.2)
            bar = pygame.Rect(int(x - w / 2), int(y + r + 9), w, 4)
            pygame.draw.rect(surface, S.OUTLINE, bar.inflate(2, 2))
            pygame.draw.rect(surface, colour, (bar.x, bar.y, int(bar.w * e.health), bar.h))

    def _icon(self, surface, e, off):
        if not e.icon:
            return
        x, y = px(e.pos)
        k = 1 + 0.6 * math.exp(-e.icon_age * 12)
        colour = S.DANGER if e.icon == "!" else S.GOLD
        img = S.display(int(19 * k)).render(e.icon, True, S.OUTLINE)
        rect = img.get_rect(midbottom=(int(x + off[0]), int(y + off[1] - e.radius * TILE * 1.3 - 6)))
        plate = pygame.Rect(0, 0, rect.h - 2, rect.h - 2)
        plate.center = rect.center
        pygame.draw.rect(surface, S.OUTLINE, plate.inflate(4, 4))
        pygame.draw.rect(surface, colour, plate)
        surface.blit(img, rect)

    def _player(self, surface, p, t, off):
        for pos, life in p.trail:
            x, y = px(pos)
            S.disc(surface, (x + off[0], y + off[1]), p.radius * TILE * 1.2, S.PLAYER, int(min(1.0, life * 2.4) * 120))
        if p.dead or (p.invulnerable > 0 and not p.dashing and int(t * 16) % 2 == 0):
            return
        x, y = px(p.pos)
        a = p.aim
        back = p.recoil * 3
        x, y = x + off[0] - math.cos(a) * back, y + off[1] - math.sin(a) * back
        r = p.radius * TILE * 1.3
        edge = S.DANGER if p.hurt_flash > 0.25 else S.OUTLINE
        art.scientist(surface, x, y, a, r, edge, aiming=not p.holstered)

    def _bullets(self, surface, room, off):
        for b in room.bullets:
            x, y = px(b.pos)
            x, y = x + off[0], y + off[1]
            speed = math.hypot(*b.vel) or 1
            dx, dy = b.vel[0] / speed, b.vel[1] / speed
            if b.owner is room.player:
                tail = (x - dx * 14, y - dy * 14)
                pygame.draw.line(surface, S.OUTLINE, tail, (x, y), 7)
                pygame.draw.line(surface, S.PLAYER, tail, (x, y), 4)
                pygame.draw.line(surface, S.WHITE, (x - dx * 7, y - dy * 7), (x, y), 2)
                continue
            colour = S.PLAYER if b.side == "player" else COLOURS.get(getattr(b.owner, "kind", ""), S.DANGER)
            if b.heavy:
                tail = (x - dx * 34, y - dy * 34)
                pygame.draw.line(surface, S.OUTLINE, tail, (x, y), 8)
                pygame.draw.line(surface, colour, tail, (x, y), 5)
                pygame.draw.line(surface, S.WHITE, (x - dx * 18, y - dy * 18), (x, y), 2)
            else:
                rr = int(b.radius * TILE)
                pygame.draw.circle(surface, S.OUTLINE, (int(x), int(y)), rr + 2)
                pygame.draw.circle(surface, colour, (int(x), int(y)), rr)
                pygame.draw.circle(surface, S.WHITE, (int(x), int(y)), max(2, rr - 3))


THEMES = {"violet": S.FLOOR,
          "ice": (64, 73, 84),
          "emerald": (62, 75, 71),
          "steel": (72, 73, 76),
          "indigo": (66, 66, 86)}
SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _edges(grid, c, r):
    x0, y0, x1, y1 = c * TILE, r * TILE, (c + 1) * TILE - 1, (r + 1) * TILE - 1
    ends = {(1, 0): ((x1, y0), (x1, y1)), (-1, 0): ((x0, y0), (x0, y1)),
            (0, 1): ((x0, y1), (x1, y1)), (0, -1): ((x0, y0), (x1, y0))}
    for dc, dr in SIDES:
        n = grid.at(c + dc, r + dr)
        if n in ".D" and 0 <= c + dc < grid.cols and 0 <= r + dr < grid.rows:
            yield dc, dr, *ends[(dc, dr)]


def build_background(grid, theme: str = "violet", racks: bool = True):
    floor = THEMES.get(theme, S.FLOOR)
    seam = S.scale(floor, 0.93)
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill(floor)
    for x in range(TILE, WIDTH, TILE * 2):
        pygame.draw.line(surf, seam, (x, 0), (x, HEIGHT))
    for y in range(TILE, HEIGHT, TILE * 2):
        pygame.draw.line(surf, seam, (0, y), (WIDTH, y))
    for (c, r) in ENTRY + EXIT:
        side = 1 if c == 0 else -1
        zone = pygame.Rect(0, 0, TILE, TILE)
        zone.topleft = ((c + side) * TILE, r * TILE)
        stripe = pygame.Surface(zone.size, pygame.SRCALPHA)
        for k in range(-TILE, TILE * 2, 12):
            pygame.draw.line(stripe, (*S.GOLD, 90), (k, 0), (k + TILE, TILE), 5)
        surf.blit(stripe, zone.topleft)
    if racks:
        shadow = S.scale(floor, 0.62)
        for r in range(grid.rows):
            for c in range(grid.cols):
                if grid.at(c, r) == "X":
                    pygame.draw.rect(surf, shadow, (c * TILE + RACK_EDGE, r * TILE + RACK_EDGE, TILE, TILE))
    for r in range(grid.rows):
        for c in range(grid.cols):
            ch = grid.at(c, r)
            rect = pygame.Rect(c * TILE, r * TILE, TILE, TILE)
            if ch == "#":
                pygame.draw.rect(surf, S.WALL, rect)
                if grid.at(c, r + 1) == "." and r + 1 < grid.rows:
                    pygame.draw.rect(surf, S.WALL_TOP, (rect.x, rect.bottom - 12, TILE, 12))
            elif racks and ch == "X":
                pygame.draw.rect(surf, S.COVER, rect)
                inner = rect.inflate(-6, -6)
                pygame.draw.rect(surf, S.COVER_TOP, inner)
                for y in (inner.y + 10, inner.y + 21):
                    pygame.draw.rect(surf, S.COVER, (inner.x + 4, y, inner.w - 8, 3))
                pygame.draw.rect(surf, S.FAINT, (inner.right - 8, inner.y + 5, 4, 3))
    for r in range(grid.rows):
        for c in range(grid.cols):
            ch = grid.at(c, r)
            if ch == "#":
                for dc, dr, a, b in _edges(grid, c, r):
                    pygame.draw.line(surf, S.WALL_LIP, a, b, 3)
            elif racks and ch == "X":
                for dc, dr, a, b in _edges(grid, c, r):
                    pygame.draw.line(surf, S.OUTLINE, a, b, 3)
    return surf.convert() if pygame.display.get_surface() else surf
