import math

from game import config as C
from game.ai.agent import REACTION, Enemy, THINK_EVERY, muzzle
from game.ai.fsm import State
from game.geometry import angle_diff, angle_to, band, center, clamp, distance, from_angle, normalize

WINDUP = 0.6
BURST = 3
BURST_GAP = 0.12
FAN = math.radians(5)


class Grunt(Enemy):
    kind = "grunt"
    name = "SENTRY"
    base_hp = 7.0
    speed = 3.3
    radius = 0.36
    worth = 100

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cover_ban = 0.0
        self.spot_tile = None
        self.fan = FAN
        self.strafe_dir = 1
        self.shots_left = 0

    def combat_state(self):
        return ENGAGE

    def states_for(self, action):
        return {
            "shoot": (AIM, FIRE),
            "cover": (TAKE_COVER, HIDE),
            "strafe": (STRAFE,),
            "reposition": (REPOSITION,),
            "flank": (FLANK,),
        }[action]

    def allies_engaging_foe(self):
        allies = []
        for robot in self.room.enemies:
            if robot is self or robot.side != self.side:
                continue
            if robot.alert and robot.senses.sees and robot.foe is self.foe:
                allies.append(robot)
        return allies

    def options(self):
        scores = {"shoot": 0.0, "cover": 0.0, "strafe": 0.0, "reposition": 0.0, "flank": 0.0}
        sees_foe = self.senses.sees
        target_distance = distance(self.pos, self.target())
        remembers_foe = self.senses.age(self.now) < C.MEMORY_TIME
        can_attack = self.room.coordinator.can_attack(self, self.now)
        self.blocked = sees_foe and not self.clear_shot(self.foe.pos)

        if sees_foe and can_attack and self.cooldown <= 0 and not self.blocked:
            if target_distance < self.view_range:
                range_bonus = 0.2 * band(target_distance, 2.5, 8.5)
                scores["shoot"] = 0.6 + 0.2 * self.health + range_bonus

        incoming_fire = self.under_fire()
        if self.now >= self.cover_ban and (self.health < 0.6 or incoming_fire > 0.5):
            cover_score = 0.75 * (1 - self.health) + 0.35 * incoming_fire
            scores["cover"] = clamp(cover_score, 0, 1.2)

        if sees_foe:
            scores["strafe"] = 0.35 + 0.15 * band(target_distance, 3, 8)
            if self.blocked:
                scores["strafe"] += 0.2
            if target_distance < 2.5 or target_distance > 9:
                scores["reposition"] = 0.45
        elif remembers_foe:
            scores["reposition"] = 0.5

        if remembers_foe and self.health > 0.4 and (not sees_foe or not can_attack):
            if self.room.coordinator.flank_free(self) and self.allies_engaging_foe():
                scores["flank"] = 0.62
        return scores

    def feasible(self, action):
        tactics = self.room.tactics
        if action == "cover":
            self.spot_tile = tactics.cover_spot(self, self.target())
            if self.spot_tile is None:
                self.cover_ban = self.now + 1.0
                return False
        elif action == "reposition":
            self.spot_tile = tactics.firing_spot(self, self.target(), 3.0, 8.0)
            return self.spot_tile is not None or self.senses.last_known is not None
        elif action == "flank":
            pinners = self.allies_engaging_foe()
            if not pinners:
                return False
            anchor = min(pinners, key=lambda e: distance(e.pos, self.foe.pos))
            pinned_from = angle_to(self.foe.pos, anchor.pos)
            self.spot_tile = tactics.flank_spot(self, self.target(), pinned_from)
            return self.spot_tile is not None
        elif action == "shoot":
            return self.room.coordinator.acquire(self, self.now)
        return True


class Engage(State):
    name = "ENGAGE"

    def enter(self, sentry):
        sentry.think = REACTION
        sentry.windup = 0.0
        sentry.crouch = False
        sentry.room.tactics.claim(sentry, None)

    def update(self, sentry, dt):
        sentry.brake(dt)
        sentry.face_foe(dt)
        sentry.rethink(dt)


class Aim(State):
    name = "AIM"

    def enter(self, sentry):
        sentry.path = []
        sentry.windup = 0.0
        sentry.locked = False
        sentry.blind = 0.0
        sentry.aim = angle_to(sentry.pos, sentry.target())
        sentry.fan = FAN

    def update(self, sentry, dt):
        sentry.brake(dt)
        windup = WINDUP * sentry.room.tuning["windup"]
        sentry.windup = min(1.0, sentry.windup + dt / windup)
        if not sentry.locked:
            if sentry.senses.sees:
                sentry.blind = 0.0
                self.track_target(sentry)
            else:
                sentry.blind += dt
                if sentry.blind > 0.3:
                    sentry.room.coordinator.release(sentry)
                    sentry.windup = 0.0
                    sentry.fsm.change(ENGAGE)
                    return
            sentry.facing = sentry.aim
            if sentry.windup >= 1 - C.LOCK_TIME / windup:
                sentry.locked = True
        if sentry.windup >= 1:
            sentry.fsm.change(FIRE)

    def track_target(self, sentry):
        bullet_speed = C.ENEMY_BULLET_SPEED * sentry.room.tuning["bullet"]
        current_angle = angle_to(sentry.pos, sentry.foe.pos)
        predicted_angle = angle_to(sentry.pos, sentry.lead(bullet_speed))
        half_spread = angle_diff(current_angle, predicted_angle) / 2
        sentry.aim = current_angle + half_spread
        sentry.fan = half_spread
        if abs(half_spread) <= FAN:
            sentry.fan = FAN if half_spread >= 0 else -FAN


class Fire(State):
    name = "FIRE"

    def enter(self, sentry):
        sentry.shots_left = BURST
        sentry.timer = 0.0

    def update(self, sentry, dt):
        sentry.brake(dt)
        sentry.timer -= dt
        if sentry.timer <= 0 and sentry.shots_left > 0:
            shot_angle = sentry.aim + (sentry.shots_left - 2) * sentry.fan
            start = muzzle(sentry, shot_angle)
            speed = C.ENEMY_BULLET_SPEED * sentry.room.tuning["bullet"]
            sentry.room.enemy_shot(sentry, start, shot_angle, speed)
            sentry.shots_left -= 1
            sentry.timer = BURST_GAP
        if sentry.shots_left == 0 and sentry.timer <= 0:
            sentry.windup = 0.0
            sentry.locked = False
            sentry.room.coordinator.release(sentry)
            sentry.cooldown = sentry.room.rng.uniform(0.9, 1.4)
            sentry.action = ""
            sentry.fsm.change(ENGAGE)


class Strafe(State):
    name = "STRAFE"

    def enter(self, sentry):
        sentry.path = []
        sentry.timer = sentry.room.rng.uniform(0.8, 1.6)
        sentry.strafe_dir = sentry.room.rng.choice((-1, 1))

    def update(self, sentry, dt):
        sentry.timer -= dt
        if sentry.timer <= 0:
            sentry.strafe_dir *= -1
            sentry.timer = sentry.room.rng.uniform(0.8, 1.6)
        to_player = angle_to(sentry.pos, sentry.foe.pos)
        target_distance = distance(sentry.pos, sentry.foe.pos)
        side = from_angle(to_player + sentry.strafe_dir * math.pi / 2)
        radial = 0.0
        if target_distance <= 3.5:
            radial = -0.8
        elif target_distance >= 7.5:
            radial = 0.6
        want, _ = normalize((side[0] + math.cos(to_player) * radial, side[1] + math.sin(to_player) * radial))
        before = sentry.pos
        sentry.steer(want, dt, sentry.speed * 0.55)
        if distance(before, sentry.pos) < sentry.speed * 0.2 * dt:
            sentry.strafe_dir *= -1
        sentry.face(to_player, dt)
        sentry.rethink(dt)


class Reposition(State):
    name = "REPOSITION"

    def enter(self, sentry):
        sentry.timer = 0.0
        goal = center(sentry.spot_tile) if sentry.spot_tile else sentry.senses.last_known
        sentry.room.tactics.claim(sentry, sentry.spot_tile)
        sentry.spot = goal
        sentry.go_to(goal)

    def exit(self, sentry):
        sentry.room.tactics.claim(sentry, None)

    def update(self, sentry, dt):
        sentry.timer += dt
        arrived = sentry.follow(dt, sentry.speed, face=not sentry.senses.sees)
        if sentry.senses.sees:
            sentry.face(angle_to(sentry.pos, sentry.foe.pos), dt)
        if arrived or sentry.timer > 4:
            sentry.action = ""
            sentry.think = 0.0
        sentry.rethink(dt)


class Flank(State):
    name = "FLANK"

    def enter(self, sentry):
        sentry.timer = 0.0
        sentry.room.coordinator.take_flank(sentry)
        sentry.room.tactics.claim(sentry, sentry.spot_tile)
        sentry.spot = center(sentry.spot_tile)
        sentry.go_to(sentry.spot, sentry.room.tactics.danger_cost(sentry.target()))
        sentry.think = THINK_EVERY * 2

    def exit(self, sentry):
        sentry.room.coordinator.drop_flank(sentry)
        sentry.room.tactics.claim(sentry, None)

    def update(self, sentry, dt):
        sentry.timer += dt
        arrived = sentry.follow(dt, sentry.speed * 1.1)
        if arrived or sentry.timer > 5:
            sentry.action = ""
            sentry.think = 0.0
        sentry.rethink(dt)


class TakeCover(State):
    name = "TAKE COVER"

    def enter(self, sentry):
        sentry.timer = 0.0
        sentry.room.tactics.claim(sentry, sentry.spot_tile)
        sentry.spot = center(sentry.spot_tile)
        sentry.go_to(sentry.spot)

    def update(self, sentry, dt):
        sentry.timer += dt
        if sentry.follow(dt, sentry.speed * 1.15) or sentry.timer > 4:
            sentry.fsm.change(HIDE)


class Hide(State):
    name = "HIDE"

    def enter(self, sentry):
        sentry.timer = 0.0
        sentry.crouch = True
        sentry.hide_for = sentry.room.rng.uniform(1.2, 2.0)

    def exit(self, sentry):
        sentry.crouch = False
        sentry.room.tactics.claim(sentry, None)
        sentry.cover_ban = sentry.now + 3.0

    def update(self, sentry, dt):
        sentry.timer += dt
        sentry.brake(dt)
        sentry.face_foe(dt)
        close = sentry.senses.sees and distance(sentry.pos, sentry.foe.pos) < 2.5
        if sentry.timer > sentry.hide_for or close:
            sentry.action = ""
            sentry.fsm.change(ENGAGE)


ENGAGE, AIM, FIRE, STRAFE = Engage(), Aim(), Fire(), Strafe()
REPOSITION, FLANK, TAKE_COVER, HIDE = Reposition(), Flank(), TakeCover(), Hide()
