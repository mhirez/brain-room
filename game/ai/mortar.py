"""MORTAR (artillery drone): lobs shells OVER cover, at where you are or where it last saw you.

Cover doesn't stop a shell, so the answer is to keep moving. It fires on what it knows: a foe it
saw a moment ago is still a target (suppressing fire on the last known position), so hiding only
works if you also relocate.

Combat states:
    ENGAGE    thinking
    POSITION  walks to a scored spot 6-11 tiles from its foe
    AIM       a target ring in its colour follows you across the floor for 0.8 s, then flashes
              white and locks; the shell then flies for 0.9 s and its ring stays on the floor,
              closing in until impact (1.1-tile blast: it hurts robots too)
    EVADE     you got within 4 tiles: it backs off to the spot furthest from you

Utility:  evade     its foe is within 4 tiles:                                        0.95
          bombard   saw its foe in the last 3 s, 4-12 tiles away, token free, reloaded:  0.85
          position  otherwise:                                                         0.5
"""

from game import config as C
from game.ai.agent import REACTION, Enemy
from game.ai.fsm import State
from game.geometry import angle_to, center, distance

TRACK = 0.8
FLIGHT = 0.9
BLAST = 1.1
KNOWS_FOR = 3.0


class Mortar(Enemy):
    kind = "mortar"
    name = "MORTAR"
    base_hp = 4.5
    speed = 2.4
    radius = 0.34
    worth = 150
    view_range = 12.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spot_tile = None
        self.aim_point = self.pos

    def combat_state(self):
        return ENGAGE

    def states_for(self, action):
        return {"bombard": (AIM,), "position": (POSITION,), "evade": (EVADE,)}[action]

    def knows(self) -> bool:
        """It saw its foe recently enough to shell where it was."""
        return self.senses.sees or (self.senses.last_known is not None and self.senses.age(self.now) < KNOWS_FOR)

    def options(self):
        d = distance(self.pos, self.foe.pos) if self.foe is not None else 99.0
        aim_d = distance(self.pos, self.target())
        token = self.room.coordinator.can_attack(self, self.now)
        return {"evade": 0.95 if d < 4.0 else 0.0,
                "bombard": 0.85 if self.knows() and 4.0 <= aim_d <= 12.0 and token and self.cooldown <= 0 else 0.0,
                "position": 0.5}

    def feasible(self, action):
        tactics = self.room.tactics
        if action == "bombard":
            return self.room.coordinator.acquire(self, self.now)
        if action == "position":
            self.spot_tile = tactics.firing_spot(self, self.target(), 6.0, 11.0, radius=8, prefer_far=True)
            return self.spot_tile is not None
        if action == "evade":
            self.spot_tile = tactics.escape_spot(self, self.foe.pos)
            return self.spot_tile is not None
        return True


class Engage(State):
    name = "ENGAGE"

    def enter(self, m):
        m.think = REACTION
        m.windup = 0.0

    def update(self, m, dt):
        m.brake(dt)
        m.face(angle_to(m.pos, m.target()), dt)
        m.rethink(dt)


class Position(State):
    name = "POSITION"

    def enter(self, m):
        m.timer = 0.0
        m.room.tactics.claim(m, m.spot_tile)
        m.spot = center(m.spot_tile)
        m.go_to(m.spot)

    def exit(self, m):
        m.room.tactics.claim(m, None)

    def update(self, m, dt):
        m.timer += dt
        if m.follow(dt, m.speed) or m.timer > 5:
            m.action = ""
            m.think = min(m.think, 0.1)
        m.rethink(dt)


class Aim(State):
    name = "AIM"

    def enter(self, m):
        m.path = []
        m.windup = 0.0
        m.locked = False
        m.aim_point = m.target()
        m.room.sound("laser")

    def update(self, m, dt):
        m.brake(dt)
        total = (TRACK + C.LOCK_TIME) * m.room.tuning["windup"]
        m.windup = min(1.0, m.windup + dt / total)
        if not m.locked:
            m.aim_point = m.lead(8.0) if m.senses.sees else m.target()     # blind: the last known spot
            m.aim = angle_to(m.pos, m.aim_point)
            m.face(m.aim, dt)
            if m.windup >= 1 - C.LOCK_TIME / total:
                m.locked = True
        if m.windup >= 1:
            m.room.lob(m, m.aim_point, FLIGHT, BLAST)
            m.windup = 0.0
            m.locked = False
            m.room.coordinator.release(m)
            m.cooldown = m.room.rng.uniform(1.6, 2.4)
            m.action = ""
            m.fsm.change(ENGAGE)


class Evade(State):
    name = "EVADE"

    def enter(self, m):
        m.timer = 0.0
        m.room.tactics.claim(m, m.spot_tile)
        m.spot = center(m.spot_tile)
        m.go_to(m.spot)

    def exit(self, m):
        m.room.tactics.claim(m, None)

    def update(self, m, dt):
        m.timer += dt
        if m.follow(dt, m.speed * 1.3) or m.timer > 3:
            m.action = ""
            m.think = 0.0
        m.rethink(dt)


ENGAGE, POSITION, AIM, EVADE = Engage(), Position(), Aim(), Evade()
