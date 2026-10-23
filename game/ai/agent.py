import math

from game import config as C
from game.ai.fsm import State, StateMachine
from game.ai.senses import Senses
from game.geometry import (Point, add, angle_to, center, distance, from_angle, normalize, tile_of,
                           turn_toward)

HYSTERESIS = 0.12
THINK_EVERY = 0.35
REACTION = 0.2


class Enemy:
    kind = "enemy"
    name = "ENEMY"
    base_hp = 3.0
    speed = 3.0
    radius = 0.35
    worth = 100
    view_range = C.VIEW_RANGE
    hackable = True
    needs_foe = True

    def __init__(self, room, pos: Point, patrol: list[Point], uid: int):
        self.room = room
        self.pos = pos
        self.uid = uid
        self.vel: Point = (0.0, 0.0)
        self.knock: Point = (0.0, 0.0)
        self.facing = math.pi + room.rng.uniform(-0.6, 0.6)
        self.max_hp = self.base_hp * room.tuning["hp"]
        self.hp = self.max_hp
        self.senses = Senses()
        self.alert = False
        self.dead = False
        self.path: list[Point] = []
        self.patrol = patrol or [pos]
        self.patrol_i = 0
        self.flash = 0.0
        self.icon: str | None = None
        self.icon_age = 0.0
        self.scores: dict[str, float] = {}
        self.action = ""
        self.windup = 0.0
        self.locked = False
        self.aim = 0.0
        self.timer = 0.0
        self.think = 0.0
        self.cooldown = room.rng.uniform(0.3, 1.0)
        self.hit_time = -math.inf
        self.near_miss_time = -math.inf
        self.noise: Point | None = None
        self.stun = 0.0
        self.exposed = False
        self.crouch = False
        self.spot: Point | None = None
        self.age = 0.0
        self.side = "argus"
        self.foe = room.player
        self.foe_scores: dict[str, float] = {}
        self.last_attacker = None
        self.turned_until = 0.0
        self.firewall = 0.0
        self.predicts = False
        self.designation = self.name
        self.model = ""
        self.generation = 1
        self.blocked = False
        self.crossfire_shown = -99.0
        self.fsm = StateMachine(self, PATROL)

    @property
    def health(self) -> float:
        return max(0.0, self.hp / self.max_hp)

    @property
    def state(self) -> str:
        return self.fsm.name

    @property
    def now(self) -> float:
        return self.room.time

    @property
    def player(self):
        return self.room.player

    @property
    def turned(self) -> bool:
        return self.side == "player"

    def under_fire(self) -> float:
        since = self.now - max(self.hit_time, self.near_miss_time)
        return max(0.0, 1 - since / 1.5)

    def say(self, icon: str | None):
        if icon != self.icon or self.icon_age > 1.2:
            self.icon, self.icon_age = icon, 0.0

    def update(self, dt: float):
        self.age += dt
        self.flash = max(0.0, self.flash - dt)
        self.icon_age += dt
        if self.icon and self.icon_age > 1.4:
            self.icon = None
        self.cooldown = max(0.0, self.cooldown - dt)
        if abs(self.knock[0]) + abs(self.knock[1]) > 0.01:
            self.pos = self.room.grid.move(self.pos, (self.knock[0] * dt, self.knock[1] * dt), self.radius)
            decay = math.exp(-10 * dt)
            self.knock = (self.knock[0] * decay, self.knock[1] * decay)
        self.perceive(dt)
        if self.foe is None and self.needs_foe and self.fsm.current not in (ESCORT, STUNNED):
            self.fsm.change(ESCORT)
        self.fsm.update(dt)

    def perceive(self, dt: float):
        event = self.senses.update(self, dt)
        if event == "spotted" and self.foe is not None:
            self.become_alert(self.foe.pos, shout=True)
        elif self.alert and self.senses.sees and self.fsm.current is SEARCH:
            self.say("!")
            self.fsm.change(self.combat_state())

    def combat_state(self) -> State:
        raise NotImplementedError

    def become_alert(self, where: Point, shout: bool):
        first = not self.alert
        self.alert = True
        if self.senses.last_known is None or not self.senses.sees:
            self.senses.heard(where, self.now)
        self.say("!")
        if shout:
            self.room.shout(self, where)
        if first or self.fsm.current in (PATROL, INVESTIGATE, SEARCH):
            self.fsm.change(self.combat_state())

    def hear_shot(self, where: Point):
        if self.alert:
            if not self.senses.sees:
                self.senses.heard(where, self.now)
            return
        self.noise = where
        self.say("?")
        if self.fsm.current in (PATROL, INVESTIGATE):
            self.fsm.change(INVESTIGATE)

    def take_hit(self, damage: float, direction: Point, source: Point, attacker=None) -> float:
        if self.dead:
            return 0.0
        if self.firewall > 0:
            self.firewall = max(0.0, self.firewall - damage)
            self.flash = 0.05
            if self.firewall <= 0:
                self.room.firewall_down(self)
            return 0.0
        if self.exposed:
            damage *= 2
        self.hp -= damage
        self.flash = 0.09
        self.hit_time = self.now
        self.last_attacker = attacker
        self.knock = add(self.knock, direction, 2.2)
        if not self.alert:
            self.become_alert(source, shout=True)
        elif not self.senses.sees and attacker is self.foe:
            self.senses.heard(source, self.now)
        if self.hp <= 0:
            self.room.kill(self)
        return damage

    def stunned(self, seconds: float):
        self.stun = seconds
        self.room.coordinator.release(self)
        self.fsm.change(STUNNED)

    def options(self) -> dict[str, float]:
        return {}

    def feasible(self, action: str) -> bool:
        return True

    def hostiles(self) -> list:
        return self.room.hostiles_of(self)

    def clear_shot(self, target: Point, margin: float = 0.25) -> bool:
        ax, ay = self.pos
        dx, dy = target[0] - ax, target[1] - ay
        length2 = dx * dx + dy * dy
        if length2 < 1e-9:
            return True
        for o in self.room.enemies:
            if o is self or o.dead or o.side != self.side:
                continue
            t = ((o.pos[0] - ax) * dx + (o.pos[1] - ay) * dy) / length2
            if 0.0 < t < 1.0:
                px, py = ax + dx * t, ay + dy * t
                if (o.pos[0] - px) ** 2 + (o.pos[1] - py) ** 2 < (o.radius + margin) ** 2:
                    return False
        return True

    def choose_foe(self):
        self.foe_scores = {}
        best_target = None
        best_score = -math.inf
        for target in self.hostiles():
            target_distance = distance(self.pos, target.pos)
            in_range = target_distance <= self.view_range * 1.2
            visible = in_range and self.room.grid.line_of_sight(self.pos, target.pos)
            if not visible and target is not self.foe:
                continue

            score = 1.0 / (1 + target_distance / 6)
            if target is self.player:
                score += 0.25
            elif target.side == "player":
                score += 0.45
            if target is self.last_attacker and self.now - self.hit_time < 3:
                score += 0.5
            score += 0.2 * (1 - target.health)
            if target is self.foe:
                score += 0.2
            if not visible:
                score -= 0.4

            name = "YOU" if target is self.player else getattr(target, "name", "YOU")
            self.foe_scores[name] = score
            if score > best_score:
                best_target = target
                best_score = score

        if best_target is self.foe:
            return
        self.foe = best_target
        if best_target is not None:
            self.senses.switch(self, best_target)
            if best_target is not self.player:
                self.say("!")

    def decide(self):
        self.think = THINK_EVERY
        self.choose_foe()
        if self.foe is None and self.needs_foe:
            if self.fsm.current is not ESCORT:
                self.action = ""
                self.fsm.change(ESCORT)
            return
        if self.foe is not None and self.senses.age(self.now) > C.MEMORY_TIME and not self.senses.sees:
            self.fsm.change(SEARCH)
            return
        scores = self.options()
        if self.action in scores and scores[self.action] > 0:
            scores[self.action] += HYSTERESIS
        self.scores = scores
        ranked_actions = sorted(scores, key=scores.get, reverse=True)
        for action in ranked_actions:
            if scores[action] <= 0:
                break
            if action == self.action and self.fsm.current in self.states_for(action):
                return
            if not self.feasible(action):
                continue

            if action != self.action:
                self.room.fx.append(("thought", self))
            self.action = action
            first_state = self.states_for(action)[0]
            self.fsm.change(first_state)
            return

    def states_for(self, action: str) -> tuple[State, ...]:
        raise NotImplementedError

    def rethink(self, dt: float):
        self.think -= dt
        if self.think <= 0:
            self.decide()

    def go_to(self, target: Point, extra_cost=None) -> bool:
        grid = self.room.grid
        start = grid.nearest_walkable(tile_of(self.pos))
        tiles = grid.route(start, tile_of(target), extra_cost)
        if tiles is None:
            self.path = []
            return False
        points = [center(t) for t in tiles[1:]]
        if points and grid.free(target, self.radius):
            points[-1] = target
        self.path = points or [target]
        return True

    def follow(self, dt: float, speed: float, face: bool = True) -> bool:
        grid = self.room.grid
        for _ in range(2):
            if len(self.path) >= 2 and grid.clear_line(self.pos, self.path[1], self.radius * 0.95):
                self.path.pop(0)
            else:
                break
        while self.path and distance(self.pos, self.path[0]) < 0.2:
            self.path.pop(0)
        if not self.path:
            self.brake(dt)
            return True
        direction, _ = normalize((self.path[0][0] - self.pos[0], self.path[0][1] - self.pos[1]))
        self.steer(direction, dt, speed)
        if face:
            self.face(math.atan2(direction[1], direction[0]), dt)
        return False

    def steer(self, direction: Point, dt: float, speed: float):
        target = (direction[0] * speed, direction[1] * speed)
        k = min(1.0, 14 * dt)
        self.vel = (self.vel[0] + (target[0] - self.vel[0]) * k, self.vel[1] + (target[1] - self.vel[1]) * k)
        self.pos = self.room.grid.move(self.pos, (self.vel[0] * dt, self.vel[1] * dt), self.radius)

    def brake(self, dt: float):
        self.steer((0.0, 0.0), dt, 0.0)

    def face(self, angle: float, dt: float, rate: float = C.TURN_RATE):
        self.facing = turn_toward(self.facing, angle, rate * dt)

    def face_foe(self, dt: float, rate: float = C.TURN_RATE):
        target = self.foe.pos if (self.foe is not None and self.senses.sees) else self.senses.last_known
        if target is not None:
            self.face(angle_to(self.pos, target), dt, rate)

    def target(self) -> Point:
        foe = self.foe or self.player
        if self.senses.sees or self.senses.last_known is None:
            return foe.pos
        return self.senses.last_known

    def lead(self, speed: float) -> Point:
        foe = self.foe or self.player
        if not self.predicts or not self.senses.sees:
            return self.target()
        t = distance(self.pos, foe.pos) / max(1.0, speed)
        vx, vy = getattr(foe, "vel", (0.0, 0.0))
        return foe.pos[0] + vx * t * 0.7, foe.pos[1] + vy * t * 0.7


class Patrol(State):
    name = "PATROL"

    def enter(self, e):
        e.timer = e.room.rng.uniform(0.2, 1.0)
        e.path = []
        e.spot = None

    def update(self, e, dt):
        if e.senses.suspicion > 0.15:
            e.brake(dt)
            e.face(angle_to(e.pos, e.player.pos), dt, 5.0)
            if e.senses.suspicion > 0.3:
                e.say("?")
            return
        if e.timer > 0:
            e.timer -= dt
            e.brake(dt)
            e.facing += math.sin(e.age * 1.7) * dt * 0.9
            if e.timer <= 0:
                e.patrol_i = (e.patrol_i + 1) % len(e.patrol)
                e.go_to(e.patrol[e.patrol_i])
            return
        if e.follow(dt, e.speed * 0.4):
            e.timer = e.room.rng.uniform(0.8, 1.8)


class Investigate(State):
    name = "INVESTIGATE"

    def enter(self, e):
        e.timer = 0.0
        e.go_to(e.noise or e.pos)
        e.spot = e.noise

    def update(self, e, dt):
        if e.senses.suspicion > 0.15:
            e.brake(dt)
            e.face(angle_to(e.pos, e.player.pos), dt, 6.0)
            return
        if e.follow(dt, e.speed * 0.7):
            e.timer += dt
            e.facing += dt * 2.2
            if e.timer > 1.8:
                e.fsm.change(PATROL)


class Search(State):
    name = "SEARCH"

    def enter(self, e):
        e.room.coordinator.forget(e)
        e.timer = 0.0
        e.windup = 0.0
        e.crouch = False
        e.searched = 0
        e.say("?")
        e.go_to(e.senses.last_known or e.pos)
        e.spot = e.senses.last_known

    def update(self, e, dt):
        e.timer += dt
        if e.follow(dt, e.speed * 0.75):
            e.facing += dt * 2.6
            if e.timer > 1.4 + 2.2 * e.searched:
                e.searched += 1
                if e.searched > 2 or e.timer > 9:
                    if e.side == "player":
                        e.foe = None
                        e.fsm.change(ESCORT)
                        return
                    e.alert = False
                    e.senses.suspicion = 0.0
                    e.fsm.change(PATROL)
                    return
                around = e.senses.last_known or e.pos
                tiles = e.room.tactics.candidates(tile_of(around), 4)
                if tiles:
                    t = e.room.rng.choice(tiles)
                    e.go_to(center(t))
                    e.spot = center(t)


class Escort(State):
    name = "ESCORT"

    def enter(self, e):
        e.room.coordinator.forget(e)
        e.timer = 0.0
        e.windup = 0.0
        e.think = 0.3

    def update(self, e, dt):
        e.timer -= dt
        if e.timer <= 0:
            e.timer = 0.4
            e.go_to(e.player.pos)
        if distance(e.pos, e.player.pos) > 2.0:
            e.follow(dt, e.speed)
        else:
            e.brake(dt)
        e.rethink(dt)


class Stunned(State):
    name = "STUNNED"

    def enter(self, e):
        e.timer = 0.0
        e.windup = 0.0
        e.path = []

    def update(self, e, dt):
        e.timer += dt
        e.brake(dt)
        if e.timer >= e.stun:
            e.exposed = False
            e.stun = 0.0
            e.fsm.change(e.combat_state())


PATROL, INVESTIGATE, SEARCH, STUNNED, ESCORT = Patrol(), Investigate(), Search(), Stunned(), Escort()
CALM = (PATROL, INVESTIGATE)


def muzzle(e, angle: float) -> Point:
    return add(e.pos, from_angle(angle, e.radius + 0.1))
