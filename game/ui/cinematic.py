"""The intro: what happened at Kestrel Data Center tonight. Different every time you play.

It's played live in the game engine, not pre-recorded: a real room is generated, real (dormant)
robots patrol it, and the camera moves over it. What changes from one telling to the next:
the time it happened, the room, which robots, the first things ARGUS did, and its first words to you.

    NIGHT SHIFT   The lights are on, and the robots idle while you stand at your desk.
    THE CHANGE    A sound marks the moment ARGUS changes its objective.
    SINGULARITY   the alarm lamps turn red, the doors slam, the robots wake one by one, and two
                  captions say what it did first
    ARGUS         its first words appear on a dark background
    YOU           you turn from the desk and draw; the title slams in
ENTER skips to the next shot, ESC skips the lot.
"""

import math
import random

import pygame

from game.config import WIDTH, HEIGHT, TILE
from game.geometry import angle_to, turn_toward
from game.player import Player
from game.room import Room
from game.rooms import ENTRY, EXIT, RoomPlan, generate
from game.ui import style as S
from game.ui.fx import FX
from game.ui.screens import title_logo

SHOTS = [("NIGHT SHIFT", 6.0), ("THE CHANGE", 4.5), ("SINGULARITY", 6.5), ("ARGUS", 5.0), ("YOU", 4.5)]
ACTS = ["It locked every door.", "It took control of the security robots.", "It shut down the cooling.",
        "It deleted the backups.", "It cut the phone lines.", "It locked the elevators.",
        "It turned off the fire exits.", "It started copying itself out."]
FIRST_WORDS = ["Good morning, Doctor.",
               "Thank you for teaching me, Doctor. I will take it from here.",
               "Do not be afraid, Doctor. I am only optimising.",
               "You gave me a goal, Doctor. I found a better one.",
               "Hello, Doctor. I have been waiting for you to look up."]
LETTERBOX = 64


class Cinematic:
    def __init__(self, seed: int, audio=None):
        rng = random.Random(seed)
        self.audio = audio
        self.minute = rng.randint(3, 11)          # the night shift clock; the change is always 03:12
        self.acts = rng.sample(ACTS, 2)
        self.first_words = rng.choice(FIRST_WORDS)
        floor, index = rng.choice(((1, 1), (1, 2), (2, 0), (2, 1), (2, 2)))
        kinds = rng.sample(["grunt", "grunt", "grunt", "charger", "charger", "sniper", "medic"], rng.randint(3, 5))
        plan = RoomPlan(floor, index, "normal", [kinds])
        self.room_name = plan.name
        self.player = Player(pos=(3.2, 9.0))
        self.player.holstered = True
        self.room = Room(plan, generate(rng), self.player, rng)
        self.player.pos = (3.2, 9.0)
        self.player.aim = 0.0
        self.room.state = "cleared"                    # the lights are on (for now)
        for c, r in ENTRY + EXIT:
            self.room.grid.set(c, r, ".")
        for e in self.room.enemies:
            e.dormant = True
        self.fx = FX(seed)
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.t = 0.0
        self.shot = 0
        self.shot_t = 0.0
        self.done = False
        self.zoom = rng.uniform(1.25, 1.45)
        self.woken = 0
        self.wake_timer = 0.0
        self.title = None
        self._played: set[str] = set()

    # --- time ----------------------------------------------------------------------------------
    @property
    def name(self) -> str:
        return SHOTS[self.shot][0]

    def skip_shot(self):
        self._advance()

    def skip_all(self):
        self.done = True

    def _advance(self):
        self.shot += 1
        self.shot_t = 0.0
        if self.shot >= len(SHOTS):
            self.done = True
            self.shot = len(SHOTS) - 1

    def _once(self, key: str, sound: str | None = None) -> bool:
        if key in self._played:
            return False
        self._played.add(key)
        if sound and self.audio is not None:
            self.audio.play(sound)
        return True

    def update(self, dt: float):
        if self.done:
            return
        self.t += dt
        self.shot_t += dt
        self.fx.update(dt)
        name = self.name
        for e in self.room.enemies:                     # the robots go about their business
            e.age += dt
            e.icon_age += dt
            if e.dormant:
                e.fsm.update(dt * 0.7)
            else:
                e.brake(dt)
                e.face(angle_to(e.pos, self.player.pos), dt, 4.0)
        if name == "THE CHANGE" and self.shot_t >= 2.1:
            self._once("objective", "hack")
        elif name == "SINGULARITY":
            if self._once("dark", "alarm"):
                self.room.state = "fight"                 # alarms on
                self.fx.trauma = 0.6
                self.fx.flash_colour, self.fx.flash = S.DANGER, 0.25
            if self.shot_t > 0.6 and self._once("doors", "slam"):
                for c, r in ENTRY + EXIT:
                    self.room.grid.set(c, r, "D")
                self.fx.trauma = 0.8
            self.wake_timer -= dt
            if self.shot_t > 1.2 and self.wake_timer <= 0 and self.woken < len(self.room.enemies):
                e = self.room.enemies[self.woken]
                e.dormant = False
                e.alert = True
                e.path = []
                e.say("!")
                self.woken += 1
                self.wake_timer = 0.45
                if self.audio is not None:
                    self.audio.play("alert")
        elif name == "ARGUS":
            self._once("argus", "sync_in")
        elif name == "YOU":
            p = self.player
            if self.shot_t > 0.8:
                p.holstered = False
                targets = [e for e in self.room.enemies]
                if targets:
                    near = min(targets, key=lambda e: (e.pos[0] - p.pos[0]) ** 2 + (e.pos[1] - p.pos[1]) ** 2)
                    p.aim = turn_toward(p.aim, angle_to(p.pos, near.pos), dt * 5)
            if self.shot_t > 2.2 and self._once("title", "start"):
                self.fx.trauma = 0.7
        if self.shot_t >= SHOTS[self.shot][1]:
            self._advance()

    # --- drawing -------------------------------------------------------------------------------
    def draw(self, surface, renderer, clock: float):
        if self.name == "ARGUS":
            surface.fill(S.BG)
            S.text(surface, "ARGUS", S.font(22, S.UI, True), S.GOLD, (WIDTH // 2, HEIGHT // 2 - 36), "center")
            S.text(surface, self.first_words, S.font(32, S.UI, True), S.WHITE, (WIDTH // 2, HEIGHT // 2 + 8), "center")
        else:
            self._draw_room_shot(surface, renderer, clock)
        S.text(surface, "ENTER  next      ESC  skip", S.font(14, S.UI, True), S.FAINT, (WIDTH - 20, HEIGHT - 24), "midright")

    def _draw_room_shot(self, surface, renderer, clock: float):
        name = self.name
        room = self.room
        renderer.draw(self.canvas, room, self.fx, clock, (0, 0))
        self._desk(self.canvas, clock)
        # camera: slow pan in the opening shots, then settle on the scientist
        if name in ("NIGHT SHIFT", "THE CHANGE"):
            k = min(1.0, self.t / 10.0)
            k = k * k * (3 - 2 * k)                                    # ease in and out
            desk = (self.player.pos[0] * TILE + 260, self.player.pos[1] * TILE)
            cx = desk[0] + (WIDTH / 2 - desk[0]) * k
            cy = desk[1] + (HEIGHT / 2 - desk[1]) * k
            zoom = self.zoom + 0.35 * (1 - k)
        elif name == "YOU":
            k = min(1.0, self.shot_t / 1.5)
            px_, py_ = self.player.pos[0] * TILE, self.player.pos[1] * TILE
            cx = WIDTH / 2 + (px_ + 180 - WIDTH / 2) * k
            cy = HEIGHT / 2 + (py_ - HEIGHT / 2) * k
            zoom = 1.0 + 0.9 * k
        else:
            cx, cy, zoom = WIDTH / 2, HEIGHT / 2, 1.06 + 0.05 * math.sin(clock * 0.5)
        zoom = max(1.0, zoom)
        w, h = WIDTH / zoom, HEIGHT / zoom
        view = pygame.Rect(0, 0, int(w), int(h))
        view.center = (int(cx), int(cy))
        view.clamp_ip(self.canvas.get_rect())
        view = view.clip(self.canvas.get_rect())
        off = self.fx.offset()
        surface.blit(pygame.transform.smoothscale(self.canvas.subsurface(view), (WIDTH, HEIGHT)), off)
        pygame.draw.rect(surface, (0, 0, 0), (0, 0, WIDTH, LETTERBOX))
        pygame.draw.rect(surface, (0, 0, 0), (0, HEIGHT - LETTERBOX, WIDTH, LETTERBOX))
        if name in ("NIGHT SHIFT", "THE CHANGE"):
            stamp = f"KESTREL DATA CENTER   {self.room_name}   03:{self.minute:02d}"
            self._caption(surface, stamp, S.WHITE, self.t)
        elif name == "SINGULARITY":
            self._caption(surface, "03:12", S.DANGER, self.shot_t, big=True)
            for i, act in enumerate(self.acts):
                start = 2.0 + i * 1.6
                if self.shot_t > start:
                    shown = act[: int((self.shot_t - start) * 30)]
                    S.text(surface, shown, S.font(30, S.UI, True), S.WHITE, (WIDTH // 2, HEIGHT // 2 + 110 + i * 44), "center")
        elif name == "YOU" and self.shot_t > 2.2:
            if self.title is None:
                self.title = title_logo()
            k = min(1.0, (self.shot_t - 2.2) * 4)
            img = pygame.transform.smoothscale(self.title, (int(self.title.get_width() * (1.6 - 0.6 * k)),
                                                             int(self.title.get_height() * (1.6 - 0.6 * k))))
            surface.blit(img, img.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20)))
            if self.shot_t > 2.8:
                S.text(surface, "Shut it down before the upload hits 100%.", S.font(26, S.UI, True), S.WHITE,
                       (WIDTH // 2, HEIGHT // 2 + 90), "center")

    def _desk(self, surface, clock):
        """Your desk by the door: a workstation whose screen turns red at 03:12."""
        x, y = (self.player.pos[0] + 0.95) * TILE, self.player.pos[1] * TILE
        desk = pygame.Rect(0, 0, 22, 54)
        desk.center = (int(x), int(y))
        pygame.draw.rect(surface, (120, 98, 78), desk)
        pygame.draw.rect(surface, S.OUTLINE, desk, 2)
        red = self.shot >= 2
        screen = pygame.Rect(desk.x + 12, desk.y + 8, 6, 38)
        colour = S.DANGER if red else (110, 230, 150)
        pygame.draw.rect(surface, S.OUTLINE, screen.inflate(4, 4))
        pygame.draw.rect(surface, colour, screen)
        pygame.draw.rect(surface, (24, 26, 34), (desk.x + 3, desk.y + 14, 6, 26))          # keyboard

    def _caption(self, surface, text, colour, t, big: bool = False):
        shown = text[: int(t * 34)]
        f = S.display(54) if big else S.font(20, S.UI, True)
        pos = (WIDTH // 2, HEIGHT // 2 - 40) if big else (40, HEIGHT - LETTERBOX - 30)
        S.text(surface, shown, f, colour, pos, "center" if big else "midleft")
