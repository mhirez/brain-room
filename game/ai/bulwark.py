"""BULWARK (shield bot): walks at you behind a blast shield. Shots from the front are blocked.

It turns slowly, so the answer is to get round it, or to put it in its friends' line of fire.

Combat states:
    ENGAGE   thinking
    ADVANCE  closes in on its foe, turning its shield toward it (slowly: it can be flanked)
    GUARD    steps in front of the most hurt ally, shield toward the foe (it protects the squad)
    WINDUP   a short band in its colour shows the shield bash; it flashes white and locks
    BASH     lunges 2 tiles down the locked line: a hit costs a heart and shoves hard
    RECOVER  a short breather

Utility:  bash     sees its foe within 2.4 tiles, token free, reloaded:        0.95
          guard    an ally under 60% health is nearer the foe than it is:   0.4 + 0.6 x (1 - ally's health)
          advance  otherwise:                                               0.55
"""

import math

from game import config as C
from game.ai.agent import REACTION, Enemy
from game.ai.fsm import State
from game.geometry import angle_to, distance, from_angle, normalize

SHIELD_ARC = math.radians(65)        # half-width of the shield, either side of where it faces
TURN = C.TURN_RATE * 0.45            # it turns slowly: flank it
WINDUP = 0.6
BASH_RANGE = 2.4
BASH_LEN = 2.0
BASH_SPEED = 9.0


class Bulwark(Enemy):
    kind = "bulwark"
    name = "BULWARK"
    base_hp = 9.0
    speed = 2.1
    radius = 0.42
    worth = 150

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ward = None                 # the ally it is guarding
        self.travelled = 0.0

    def combat_state(self):
        return ENGAGE

    def states_for(self, action):
        return {"bash": (WINDUP_, BASH), "guard": (GUARD,), "advance": (ADVANCE,)}[action]

    # --- the shield --------------------------------------------------------------------------
    def shielded(self, direction) -> bool:
        """Does a hit travelling along `direction` land on the shield (it came from the front)?"""
        if self.state == "STUNNED":
            return False
        n, _ = normalize(direction)
        fx, fy = math.cos(self.facing), math.sin(self.facing)
        return -(fx * n[0] + fy * n[1]) > math.cos(SHIELD_ARC)

    def take_hit(self, damage, direction, source, attacker=None):
        if not self.dead and self.firewall <= 0 and self.shielded(direction):
            self.flash = 0.03
            self.room.shield_block(self)
            if not self.alert:
                self.become_alert(source, shout=True)
            return 0.0
        return super().take_hit(damage, direction, source, attacker)

    # --- deciding ----------------------------------------------------------------------------
    def hurt_ally(self):
        """The most hurt ally that stands nearer the foe than this one does (worth shielding)."""
        if self.foe is None:
            return None
        mine = distance(self.pos, self.foe.pos)
        allies = [e for e in self.room.enemies if e is not self and not e.dead and e.side == self.side
                  and e.health < 0.6 and distance(e.pos, self.foe.pos) < mine + 1.0]
        return min(allies, key=lambda e: e.health, default=None)

    def options(self):
        sees = self.senses.sees
        d = distance(self.pos, self.target())
        token = self.room.coordinator.can_attack(self, self.now)
        ward = self.hurt_ally()
        return {"bash": 0.95 if sees and d <= BASH_RANGE and token and self.cooldown <= 0 else 0.0,
                "guard": 0.4 + 0.6 * (1 - ward.health) if ward is not None and sees else 0.0,
                "advance": 0.55}

    def feasible(self, action):
        if action == "bash":
            return self.room.coordinator.acquire(self, self.now)
        if action == "guard":
            self.ward = self.hurt_ally()
            return self.ward is not None
        return True

    def shield_toward(self, point, dt):
        self.face(angle_to(self.pos, point), dt, TURN)


class Engage(State):
    name = "ENGAGE"

    def enter(self, b):
        b.think = REACTION
        b.windup = 0.0

    def update(self, b, dt):
        b.brake(dt)
        b.shield_toward(b.target(), dt)
        b.rethink(dt)


class Advance(State):
    name = "ADVANCE"

    def enter(self, b):
        b.timer = 0.0

    def update(self, b, dt):
        b.timer -= dt
        if b.timer <= 0:
            b.timer = 0.4
            b.go_to(b.target())
            b.spot = b.target()
        b.follow(dt, b.speed, face=False)
        b.shield_toward(b.target(), dt)
        b.rethink(dt)


class Guard(State):
    name = "GUARD"

    def enter(self, b):
        b.timer = 0.0

    def update(self, b, dt):
        ward = b.ward
        if ward is None or ward.dead or b.foe is None:
            b.action = ""
            b.think = 0.0
            b.rethink(dt)
            return
        b.timer -= dt
        if b.timer <= 0:                                  # stand between the ally and the foe
            b.timer = 0.3
            toward, _ = normalize((b.foe.pos[0] - ward.pos[0], b.foe.pos[1] - ward.pos[1]))
            b.spot = (ward.pos[0] + toward[0] * 1.2, ward.pos[1] + toward[1] * 1.2)
            b.go_to(b.spot)
        b.follow(dt, b.speed * 1.15, face=False)
        b.shield_toward(b.target(), dt)
        b.rethink(dt)


class Windup(State):
    name = "WINDUP"

    def enter(self, b):
        b.path = []
        b.windup = 0.0
        b.locked = False
        b.aim = angle_to(b.pos, b.target())
        b.room.sound("growl")

    def update(self, b, dt):
        b.brake(dt)
        windup = WINDUP * b.room.tuning["windup"]
        b.windup = min(1.0, b.windup + dt / windup)
        if not b.locked:
            b.aim = angle_to(b.pos, b.target())
            b.face(b.aim, dt, TURN * 2)
            if b.windup >= 1 - C.LOCK_TIME / windup:
                b.locked = True
        if b.windup >= 1:
            b.fsm.change(BASH)


class Bash(State):
    name = "BASH"

    def enter(self, b):
        b.travelled = 0.0
        b.windup = 0.0
        b.facing = b.aim
        b.room.sound("dash")

    def update(self, b, dt):
        direction = from_angle(b.aim)
        step = BASH_SPEED * dt
        before = b.pos
        b.pos = b.room.grid.move(b.pos, (direction[0] * step, direction[1] * step), b.radius)
        moved = distance(before, b.pos)
        b.travelled += moved
        struck = next((t for t in b.hostiles() if distance(b.pos, t.pos) < b.radius + t.radius + 0.15), None)
        if struck is not None:
            b.room.strike(b, struck, 1)
            if hasattr(struck, "vel"):
                struck.vel = (struck.vel[0] + direction[0] * 6, struck.vel[1] + direction[1] * 6)
        if struck is not None or moved < step * 0.5 or b.travelled >= BASH_LEN:
            b.locked = False
            b.room.coordinator.release(b)
            b.cooldown = b.room.rng.uniform(1.2, 1.8)
            b.action = ""
            b.fsm.change(RECOVER)


class Recover(State):
    name = "RECOVER"

    def enter(self, b):
        b.timer = 0.0

    def update(self, b, dt):
        b.timer += dt
        b.brake(dt)
        b.shield_toward(b.target(), dt)
        if b.timer > 0.5:
            b.fsm.change(ENGAGE)


ENGAGE, ADVANCE, GUARD, WINDUP_, BASH, RECOVER = Engage(), Advance(), Guard(), Windup(), Bash(), Recover()
