"""Game feel: particles, screen shake, hit-stop, screen flashes and floating text.

The room reports effects as tuples (see room.py); FX turns them into things on screen.
Positions here are in pixels.
"""

from dataclasses import dataclass
import math
import random

import pygame

from game.config import TILE, WIDTH, HEIGHT
from game.ui import style as S

LINK_TIME = 0.9                  # how long a network link stays drawn (s)


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    colour: tuple
    size: float
    kind: str = "dot"          # dot, spark, ring, text, plus
    text: str = ""
    drag: float = 3.0
    grow: float = 0.0


class FX:
    def __init__(self, seed: int = 5):
        self.rng = random.Random(seed)
        self.particles: list[Particle] = []
        self.trauma = 0.0
        self.stop = 0.0
        self.flash_colour = (255, 255, 255)
        self.flash = 0.0
        self.warps: list[list] = []      # [x, y, age]
        self.zaps: list[list] = []       # [points, life] rewrite lightning
        self.links: list[list] = []      # [ax, ay, bx, by, age]: an alert travelling robot to robot
        self.thoughts: list[list] = []   # [robot, age]: a robot just changed its mind
        self.t = 0.0
        self.said = False                # ARGUS started a new line this frame
        self.new_wrecks: list = []       # robots destroyed this frame (the renderer bakes their wreckage)
        self.rack_hits: list = []        # (tile, direction, strength): racks knocked this frame

    def clear(self):
        self.particles.clear()
        self.warps.clear()
        self.zaps.clear()
        self.links.clear()
        self.thoughts.clear()
        self.new_wrecks.clear()
        self.rack_hits.clear()
        self.trauma = 0.0
        self.flash = 0.0

    # --- input -----------------------------------------------------------------------------
    def consume(self, events: list[tuple]):
        for ev in events:
            kind = ev[0]
            if kind == "say":
                self.said = True
            elif kind == "wreck":
                self.new_wrecks.append((px(ev[1]), ev[2], ev[3]))
            elif kind == "rack":
                self.rack_hits.append((ev[1], ev[2], ev[3]))
            elif kind == "shake":
                self.trauma = min(1.0, self.trauma + ev[1])
            elif kind == "stop":
                self.stop = max(self.stop, ev[1])
            elif kind == "flash":
                self.flash_colour, self.flash = ev[1], 0.25
            elif kind == "spark":
                self.sparks(px(ev[1]), ev[2], 5, 260)
            elif kind == "burst":
                self.burst(px(ev[1]), ev[2], ev[3])
            elif kind == "ring":
                x, y = px(ev[1])
                self.particles.append(Particle(x, y, 0, 0, 0.45, 0.45, ev[2], 8, "ring", grow=ev[3] * TILE / 0.45))
            elif kind == "text":
                x, y = px(ev[1])
                self.particles.append(Particle(x, y - 20, 0, -50, 0.9, 0.9, ev[3], 20, "text", ev[2], drag=1.5))
            elif kind == "muzzle":
                x, y = px(ev[1])
                a = ev[2]
                for _ in range(3):
                    s = self.rng.uniform(80, 260)
                    b = a + self.rng.uniform(-0.35, 0.35)
                    self.particles.append(Particle(x, y, math.cos(b) * s, math.sin(b) * s, 0.09, 0.09, ev[3], 3, "spark"))
            elif kind == "trail":
                x, y = px(ev[1])
                self.particles.append(Particle(x, y, 0, 0, 0.18, 0.18, ev[2], ev[3] * TILE, "ghost"))
            elif kind == "heal":
                x, y = px(ev[1])
                self.particles.append(Particle(x + self.rng.uniform(-10, 10), y, 0, -40, 0.6, 0.6,
                                               S.GOOD, 5, "plus", drag=0.5))
            elif kind == "casing":                        # a brass shell flies out to the right
                x, y = px(ev[1])
                a = ev[2] + math.pi / 2 + self.rng.uniform(-0.3, 0.3)
                s = self.rng.uniform(90, 150)
                self.particles.append(Particle(x, y, math.cos(a) * s, math.sin(a) * s, 0.7, 0.7, (214, 170, 80), 4,
                                               "casing", drag=7, grow=self.rng.uniform(-20, 20)))
            elif kind == "warp":
                x, y = px(ev[1])
                self.warps.append([x, y, 0.0])
            elif kind == "link":                          # ARGUS's network passing on a sighting
                (ax, ay), (bx, by) = px(ev[1]), px(ev[2])
                self.links.append([ax, ay, bx, by, 0.0])
            elif kind == "thought":                       # a robot's decision just changed
                self.thoughts = [t for t in self.thoughts if t[0] is not ev[1]] + [[ev[1], 0.0]]
            elif kind == "zap":
                a, b = px(ev[1]), px(ev[2])
                pts = [a]
                n = 9
                for i in range(1, n):
                    f = i / n
                    jitter = self.rng.uniform(-14, 14)
                    nx, ny = -(b[1] - a[1]), b[0] - a[0]
                    length = math.hypot(nx, ny) or 1
                    pts.append((a[0] + (b[0] - a[0]) * f + nx / length * jitter,
                                a[1] + (b[1] - a[1]) * f + ny / length * jitter))
                pts.append(b)
                self.zaps.append([pts, 0.3])

    def ambient(self, room, dt: float):
        """Ongoing effects: damaged robots smoke, dazed ones spit sparks."""
        for e in room.enemies:
            if e.kind == "warden":
                hurt = e.health < 0.66
            else:
                hurt = e.health < 0.45
            x, y = px(e.pos)
            if hurt and self.rng.random() < dt * 9:
                self.particles.append(Particle(x + self.rng.uniform(-6, 6), y + self.rng.uniform(-6, 6),
                                               self.rng.uniform(-10, 10), -self.rng.uniform(15, 35), 1.4, 1.4,
                                               (70, 74, 86), self.rng.uniform(5, 9), "smoke", drag=0.6, grow=9))
            if e.state == "STUNNED" and self.rng.random() < dt * 12:
                self.sparks((x, y), (255, 230, 150), 2, 180)

    def sparks(self, pos, colour, n: int, speed: float):
        for _ in range(n):
            a = self.rng.uniform(0, 2 * math.pi)
            s = self.rng.uniform(0.3, 1.0) * speed
            self.particles.append(Particle(pos[0], pos[1], math.cos(a) * s, math.sin(a) * s,
                                           0.25, 0.25, colour, 2, "spark", drag=6))

    def burst(self, pos, colour, size: float):
        n = int(14 + 20 * size)
        for _ in range(n):
            a = self.rng.uniform(0, 2 * math.pi)
            s = self.rng.uniform(80, 420) * (0.6 + 0.4 * size)
            life = self.rng.uniform(0.3, 0.7)
            kind = "spark" if self.rng.random() < 0.6 else "dot"
            self.particles.append(Particle(pos[0], pos[1], math.cos(a) * s, math.sin(a) * s, life, life,
                                           S.mix(colour, S.WHITE, self.rng.random() * 0.4),
                                           self.rng.uniform(2, 5), kind, drag=4))
        self.particles.append(Particle(pos[0], pos[1], 0, 0, 0.35, 0.35, colour, 6, "ring",
                                       grow=(1.4 + size) * TILE / 0.35))
        self.particles.append(Particle(pos[0], pos[1], 0, 0, 0.18, 0.18, S.WHITE, 18 + 14 * size, "flash"))

    # --- time --------------------------------------------------------------------------------
    def update(self, dt: float):
        self.t += dt
        self.trauma = max(0.0, self.trauma - dt * 1.8)
        self.flash = max(0.0, self.flash - dt)
        for z in self.zaps:
            z[1] -= dt
        self.zaps = [z for z in self.zaps if z[1] > 0]
        for w in self.warps:
            w[2] += dt
        self.warps = [w for w in self.warps if w[2] < 1.15]
        for link in self.links:
            link[4] += dt
        self.links = [link for link in self.links if link[4] < LINK_TIME]
        for th in self.thoughts:
            th[1] += dt
        self.thoughts = [th for th in self.thoughts if th[1] < 0.35 and not th[0].dead]
        alive = []
        for p in self.particles:
            p.life -= dt
            if p.life <= 0:
                continue
            k = math.exp(-p.drag * dt)
            p.vx, p.vy = p.vx * k, p.vy * k
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.size += p.grow * dt
            alive.append(p)
        self.particles = alive[-900:]

    def offset(self) -> tuple[int, int]:
        amount = self.trauma ** 2 * 14
        if amount < 0.3:
            return 0, 0
        return (int(math.sin(self.t * 71) * amount), int(math.cos(self.t * 57) * amount))

    # --- drawing -----------------------------------------------------------------------------
    def draw_under(self, surface, off):
        """Warp-in markers (drawn under the enemies)."""
        for x, y, age in self.warps:
            k = age / 1.1
            r = int(TILE * (1.2 - 0.7 * k))
            c = S.DANGER if int(age * 9) % 2 else S.WHITE
            S.disc(surface, (x + off[0], y + off[1]), r, S.DANGER, 60)
            pygame.draw.circle(surface, c, (x + off[0], y + off[1]), r, 3)
            pygame.draw.circle(surface, c, (x + off[0], y + off[1]), int(r * 0.45), 2)

    def draw_network(self, surface, off):
        """The AI made visible: sightings passed robot to robot over ARGUS's network (a packet
        runs down a thin gold line), and a bracket flash when a robot changes its decision."""
        ox, oy = off
        for ax, ay, bx, by, age in self.links:
            k = min(1.0, age / 0.4)                                    # the packet's journey
            a, b = (ax + ox, ay + oy), (bx + ox, by + oy)
            S.dashed(surface, S.GOLD, a, b, 4, 5, 2 if age < LINK_TIME - 0.25 else 1)
            p = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
            pygame.draw.circle(surface, S.OUTLINE, (int(p[0]), int(p[1])), 5)
            pygame.draw.circle(surface, S.GOLD, (int(p[0]), int(p[1])), 3)
        for e, age in self.thoughts:
            x, y = e.pos[0] * TILE + ox, e.pos[1] * TILE + oy
            r = e.radius * TILE * (1.6 + age * 2)
            c = S.GOLD
            for side in (-1, 1):                                       # ⟨ ⟩ around the robot
                tip = (x + side * r, y)
                pygame.draw.lines(surface, c, False, [(tip[0] - side * 5, y - 7), tip, (tip[0] - side * 5, y + 7)], 2)

    def draw(self, surface, off):
        ox, oy = off
        for pts, life in self.zaps:
            moved = [(x + ox, y + oy) for x, y in pts]
            k = life / 0.3
            pygame.draw.lines(surface, S.OUTLINE, False, moved, 2 + int(5 * k))
            pygame.draw.lines(surface, S.PLAYER, False, moved, 1 + int(3 * k))
        for p in self.particles:
            k = p.life / p.max_life
            x, y = p.x + ox, p.y + oy
            if p.kind == "spark":
                tail = (x - p.vx * 0.03 * k, y - p.vy * 0.03 * k)
                pygame.draw.line(surface, p.colour, (x, y), tail, max(1, int(p.size)))
            elif p.kind == "dot":
                pygame.draw.rect(surface, p.colour, (int(x), int(y), max(1, int(p.size * k * 1.6)), max(1, int(p.size * k * 1.6))))
            elif p.kind == "ring":
                pygame.draw.circle(surface, p.colour, (int(x), int(y)), int(p.size), max(1, int(3 * k)))
            elif p.kind == "flash":
                pygame.draw.circle(surface, p.colour, (int(x), int(y)), max(1, int(p.size * k)))
            elif p.kind == "ghost":
                S.disc(surface, (x, y), p.size, p.colour, int(110 * k))
            elif p.kind == "smoke":
                S.disc(surface, (x, y), p.size, (96, 100, 110), int(150 * k))
            elif p.kind == "casing":
                spin = p.size + p.life * 20
                dx, dy = math.cos(spin) * 2.5, math.sin(spin) * 2.5
                pygame.draw.line(surface, p.colour, (x - dx, y - dy), (x + dx, y + dy), 2)
            elif p.kind == "plus":
                d = 2 + int(3 * k)
                pygame.draw.line(surface, p.colour, (x - d, y), (x + d, y), 3)
                pygame.draw.line(surface, p.colour, (x, y - d), (x, y + d), 3)
            elif p.kind == "text":
                S.text(surface, p.text, S.display(int(p.size)), p.colour, (x, y), "center", int(255 * min(1, k * 2)))
        if self.flash > 0:
            frame = edge_frame(self.flash_colour)
            frame.set_alpha(int(220 * self.flash / 0.25))
            surface.blit(frame, (0, 0))


_frames: dict = {}


def edge_frame(colour) -> pygame.Surface:
    """A solid coloured border round the screen (the 'you got hit' flash)."""
    if colour not in _frames:
        frame = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(frame, colour, (0, 0, WIDTH, HEIGHT), 12)
        _frames[colour] = frame
    return _frames[colour]


def px(p) -> tuple[float, float]:
    return p[0] * TILE, p[1] * TILE
