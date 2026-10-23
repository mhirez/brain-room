import math

from game import config as C
from game.geometry import Point, angle_diff, angle_to, distance


class Senses:
    def __init__(self):
        self.suspicion = 0.0
        self.sees = False
        self.last_known: Point | None = None
        self.seen_at = -math.inf
        self.heard_at = -math.inf

    def age(self, now: float) -> float:
        return now - max(self.seen_at, self.heard_at)

    def heard(self, pos: Point, now: float):
        self.last_known = pos
        self.heard_at = now

    def switch(self, enemy, foe):
        self.last_known = foe.pos
        if enemy.room.grid.line_of_sight(enemy.pos, foe.pos):
            self.seen_at = enemy.room.time
        else:
            self.heard_at = enemy.room.time - 2.0

    def update(self, enemy, dt: float) -> str | None:
        target = enemy.foe
        if target is None:
            if enemy.side == "player":
                self.sees = False
                return None
            target = enemy.room.player

        sight_range = enemy.view_range
        half_angle = C.VIEW_HALF_ANGLE
        if enemy.alert:
            sight_range *= 1.2
            half_angle = C.ALERT_HALF_ANGLE

        distance_to_target = distance(enemy.pos, target.pos)
        in_view = distance_to_target <= C.PROXIMITY
        if not in_view and distance_to_target <= sight_range:
            direction = angle_to(enemy.pos, target.pos)
            in_view = abs(angle_diff(enemy.facing, direction)) <= half_angle

        self.sees = in_view and enemy.room.grid.line_of_sight(enemy.pos, target.pos)
        if self.sees:
            self.last_known = target.pos
            self.seen_at = enemy.room.time
        if enemy.alert:
            return None

        if not self.sees:
            self.suspicion = max(0.0, self.suspicion - dt * 0.4)
            return None

        notice_speed = 1.0
        if distance_to_target < 3:
            notice_speed = 2.5
        elif distance_to_target < 6:
            notice_speed = 1.5
        rate = notice_speed / C.NOTICE_TIME
        self.suspicion = min(1.0, self.suspicion + rate * dt)
        if self.suspicion >= 1.0:
            return "spotted"
        return None
