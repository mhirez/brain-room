from dataclasses import dataclass, field
import math
import random

from game import config as C
from game.geometry import Point, from_angle, normalize


@dataclass
class Stats:
    max_hp: int = C.PLAYER_HP
    speed: float = C.PLAYER_SPEED
    fire_rate: float = C.FIRE_RATE
    damage: float = C.BULLET_DAMAGE
    bullet_speed: float = C.BULLET_SPEED
    shots: int = 1
    pierce: int = 0
    bounce: int = 1
    dash_cooldown: float = C.DASH_COOLDOWN
    ram: bool = False
    repair: int = 0
    rewrite_time: float = 8.0
    overload: float = 1.0
    max_charges: int = 2
    sync_drain: float = 1.0
    sync_refill: float = 1.0
    sync_slow: float = 0.2


@dataclass
class Shot:
    pos: Point
    angle: float
    speed: float
    damage: float
    pierce: int
    bounce: int


@dataclass
class Player:
    pos: Point
    stats: Stats = field(default_factory=Stats)
    radius: float = C.PLAYER_RADIUS
    vel: Point = (0.0, 0.0)
    aim: float = 0.0
    hp: int = C.PLAYER_HP
    fire_timer: float = 0.0
    dash_timer: float = 0.0
    dash_ready: float = 0.0
    dash_dir: Point = (1.0, 0.0)
    invulnerable: float = 0.0
    hurt_flash: float = 0.0
    recoil: float = 0.0
    trail: list = field(default_factory=list)
    rammed: set = field(default_factory=set)
    side: str = "player"
    name: str = "YOU"
    charges: int = 1
    charge_progress: int = 0
    sync: float = 1.0
    heal_buffer: float = 0.0
    rewrote_before: bool = False
    holstered: bool = False
    rng: random.Random = field(default_factory=lambda: random.Random(3))

    @property
    def dashing(self) -> bool:
        return self.dash_timer > 0

    @property
    def health(self) -> float:
        return self.hp / self.stats.max_hp

    @property
    def dead(self) -> bool:
        return self.hp <= 0

    @property
    def safe(self) -> bool:
        return self.dashing or self.invulnerable > 0

    def update(self, dt: float, move: Point, aim_at: Point, firing: bool, dash: bool, grid) -> tuple[list[Shot], list[str]]:
        events: list[str] = []
        self.aim = math.atan2(aim_at[1] - self.pos[1], aim_at[0] - self.pos[0])
        self.invulnerable = max(0.0, self.invulnerable - dt)
        self.hurt_flash = max(0.0, self.hurt_flash - dt)
        self.dash_ready = max(0.0, self.dash_ready - dt)
        self.recoil = max(0.0, self.recoil - dt * 8)
        self.fire_timer = max(0.0, self.fire_timer - dt)

        wish, amount = normalize(move)
        if dash and self.dash_ready <= 0 and not self.dashing:
            self.dash_dir = wish if amount > 0 else from_angle(self.aim)
            self.dash_timer = C.DASH_TIME
            self.dash_ready = self.stats.dash_cooldown
            events.append("dash")

        if self.dashing:
            self.dash_timer = max(0.0, self.dash_timer - dt)
            self.vel = (self.dash_dir[0] * C.DASH_SPEED, self.dash_dir[1] * C.DASH_SPEED)
            self.trail.append([self.pos, 0.25])
            if not self.dashing:
                self.vel = (self.dash_dir[0] * self.stats.speed, self.dash_dir[1] * self.stats.speed)
                self.invulnerable = max(self.invulnerable, 0.06)
        else:
            self.walk(dt, wish, amount)
        self.pos = grid.move(self.pos, (self.vel[0] * dt, self.vel[1] * dt), self.radius)
        for t in self.trail:
            t[1] -= dt
        self.trail = [t for t in self.trail if t[1] > 0]

        shots: list[Shot] = []
        if firing and self.fire_timer <= 0 and not self.dashing:
            shots = self.shoot()
            events.append("shoot")
        return shots, events

    def walk(self, dt: float, direction: Point, amount: float):
        target_x = direction[0] * self.stats.speed
        target_y = direction[1] * self.stats.speed
        change_x = target_x - self.vel[0]
        change_y = target_y - self.vel[1]
        speed_change = math.hypot(change_x, change_y)
        if speed_change > 0:
            rate = C.PLAYER_ACCEL if amount > 0 else C.PLAYER_FRICTION
            fraction = min(1.0, rate * dt / speed_change)
            self.vel = (self.vel[0] + change_x * fraction, self.vel[1] + change_y * fraction)

    def shoot(self) -> list[Shot]:
        self.fire_timer = 1.0 / self.stats.fire_rate
        muzzle_x = self.pos[0] + math.cos(self.aim) * 0.45
        muzzle_y = self.pos[1] + math.sin(self.aim) * 0.45
        shots = []
        for index in range(self.stats.shots):
            offset = (index - (self.stats.shots - 1) / 2) * math.radians(7)
            spread = self.rng.uniform(-C.BULLET_SPREAD, C.BULLET_SPREAD)
            angle = self.aim + offset + spread
            shots.append(Shot((muzzle_x, muzzle_y), angle, self.stats.bullet_speed,
                              self.stats.damage, self.stats.pierce, self.stats.bounce))
        self.recoil = 1.0
        return shots

    def hurt(self, amount: int = 1) -> bool:
        if self.safe or self.hp <= 0:
            return False
        self.hp = max(0, self.hp - amount)
        self.invulnerable = C.HURT_INVULNERABLE
        self.hurt_flash = 0.35
        return True

    def heal(self, amount: int = 1) -> int:
        before = self.hp
        self.hp = min(self.stats.max_hp, self.hp + amount)
        return self.hp - before
