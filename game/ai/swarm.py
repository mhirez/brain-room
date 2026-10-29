import math

from game import config as C
from game.ai.agent import REACTION, STUNNED, Enemy
from game.ai.fsm import State
from game.geometry import angle_to, distance, from_angle, normalize

WINDUP = 0.45
DIVE_SPEED = 12.0
DIVE_LEN = 6.0
ORBIT = 3.5
NEIGHBOURHOOD = 4.0
SEPARATION = 1.0
WEIGHTS = {"separation": 1.6, "cohesion": 0.5, "alignment": 0.4, "orbit": 1.0}


class Swarm(Enemy):
    kind = "swarm"
    name = "MIDGE"
    base_hp = 1.5
    speed = 5.2
    radius = 0.22
    worth = 40

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.orbit = 1
        self.travelled = 0.0

    def combat_state(self):
        return ENGAGE

    def states_for(self, action):
        return {"dive": (WINDUP_, DIVE), "seek": (SEEK,), "flock": (FLOCK,)}[action]

    def options(self):
        sees = self.senses.sees
        d = distance(self.pos, self.target())
        token = self.room.coordinator.can_attack(self, self.now)
        self.blocked = sees and not self.clear_shot(self.target(), 0.3)
        return {"dive": 0.85 if sees and 2.0 <= d <= DIVE_LEN and token and self.cooldown <= 0
                and not self.blocked else 0.0,
                "seek": 0.6 if not sees else 0.0,
                "flock": 0.5 if sees else 0.0}

    def feasible(self, action):
        if action == "dive":
            return self.room.coordinator.acquire(self, self.now)
        return True

    def flock_mates(self) -> list:
        return [e for e in self.room.enemies if e is not self and not e.dead and e.kind == "swarm"
                and e.side == self.side and distance(e.pos, self.pos) < NEIGHBOURHOOD]

    def steering(self) -> tuple[float, float]:
        mates = self.flock_mates()
        sx = sy = cx = cy = ax = ay = 0.0
        for m in mates:
            d = max(0.05, distance(self.pos, m.pos))
            if d < SEPARATION:
                sx += (self.pos[0] - m.pos[0]) / (d * d)
                sy += (self.pos[1] - m.pos[1]) / (d * d)
            cx += m.pos[0]
            cy += m.pos[1]
            ax += m.vel[0]
            ay += m.vel[1]
        want = [WEIGHTS["separation"] * sx, WEIGHTS["separation"] * sy]
        if mates:
            n = len(mates)
            coh, _ = normalize((cx / n - self.pos[0], cy / n - self.pos[1]))
            ali, _ = normalize((ax / n, ay / n))
            want[0] += WEIGHTS["cohesion"] * coh[0] + WEIGHTS["alignment"] * ali[0]
            want[1] += WEIGHTS["cohesion"] * coh[1] + WEIGHTS["alignment"] * ali[1]
        target = self.target()
        to = angle_to(self.pos, target)
        d = distance(self.pos, target)
        radial = 0.8 if d > ORBIT + 0.8 else (-0.8 if d < ORBIT - 0.8 else 0.0)
        side = from_angle(to + self.orbit * math.pi / 2)
        want[0] += WEIGHTS["orbit"] * (side[0] + math.cos(to) * radial)
        want[1] += WEIGHTS["orbit"] * (side[1] + math.sin(to) * radial)
        direction, _ = normalize((want[0], want[1]))
        return direction


class Engage(State):
    name = "ENGAGE"

    def enter(self, s):
        s.think = REACTION
        s.windup = 0.0

    def update(self, s, dt):
        s.brake(dt)
        s.face_foe(dt)
        s.rethink(dt)


class Seek(State):
    name = "SEEK"

    def enter(self, s):
        s.timer = 0.0

    def update(self, s, dt):
        s.timer -= dt
        if s.timer <= 0:
            s.timer = 0.3
            s.go_to(s.target())
            s.spot = s.target()
        s.follow(dt, s.speed)
        s.rethink(dt)


class Flock(State):
    name = "FLOCK"

    def enter(self, s):
        s.path = []
        s.orbit = s.room.rng.choice((-1, 1))

    def update(self, s, dt):
        before = s.pos
        s.steer(s.steering(), dt, s.speed * 0.75)
        if distance(before, s.pos) < s.speed * 0.1 * dt:
            s.orbit *= -1
        s.face(angle_to(s.pos, s.target()), dt)
        s.rethink(dt)


class Windup(State):
    name = "WINDUP"

    def enter(self, s):
        s.path = []
        s.windup = 0.0
        s.locked = False
        s.aim = angle_to(s.pos, s.target())

    def update(self, s, dt):
        s.brake(dt)
        windup = WINDUP * s.room.tuning["windup"]
        s.windup = min(1.0, s.windup + dt / windup)
        if not s.locked:
            s.aim = angle_to(s.pos, s.target())
            s.facing = s.aim
            if s.windup >= 1 - C.LOCK_TIME / windup:
                s.locked = True
        if s.windup >= 1:
            s.fsm.change(DIVE)


class Dive(State):
    name = "DIVE"

    def enter(self, s):
        s.travelled = 0.0
        s.windup = 0.0
        s.room.sound("dash")

    def update(self, s, dt):
        direction = from_angle(s.aim)
        step = DIVE_SPEED * dt
        before = s.pos
        s.vel = (direction[0] * DIVE_SPEED, direction[1] * DIVE_SPEED)
        s.pos = s.room.grid.move(s.pos, (direction[0] * step, direction[1] * step), s.radius)
        moved = distance(before, s.pos)
        s.travelled += moved
        s.room.trail(s)
        struck = next((t for t in s.hostiles() if distance(s.pos, t.pos) < s.radius + t.radius + 0.1), None)
        if struck is not None:
            s.room.strike(s, struck, 1)
            self.finish(s)
            s.room.kill(s)
        elif moved < step * 0.5:
            self.finish(s)
            s.room.fx.append(("spark", s.pos, s.room.colour(s)))
            s.stun = 0.6
            s.fsm.change(STUNNED)
        elif s.travelled >= DIVE_LEN:
            self.finish(s)
            s.fsm.change(ENGAGE)

    @staticmethod
    def finish(s):
        s.vel = (0.0, 0.0)
        s.locked = False
        s.room.coordinator.release(s)
        s.cooldown = s.room.rng.uniform(1.0, 1.6)
        s.action = ""


ENGAGE, SEEK, FLOCK, WINDUP_, DIVE = Engage(), Seek(), Flock(), Windup(), Dive()
