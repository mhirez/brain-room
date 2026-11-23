"""What an enemy knows about its foe: only what it has seen or heard (imperfect information).

(Its foe is normally the player. It can be an overridden traitor.)

SIGHT    a cone (100 degrees while calm, 220 once alert) that needs a clear line of sight;
         anything within 1.6 tiles is felt regardless.
NOTICING while calm, seeing the player fills a SUSPICION meter (faster up close). Full = "!".
         Partly full = "?": the enemy stops and stares (a double take), so a quick player can
         still break line of sight before being spotted.
HEARING  gunshots carry 11 tiles. A calm enemy goes to investigate; an alert one learns
         where the player is from the sound.
MEMORY   the last known position, and when it was last confirmed. Out of touch for 5 s, an
         alert enemy stops fighting and SEARCHes.
"""

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
        """Seconds since the player's position was last confirmed by sight or sound."""
        return now - max(self.seen_at, self.heard_at)

    def heard(self, pos: Point, now: float):
        self.last_known = pos
        self.heard_at = now

    def switch(self, enemy, foe):
        """Remember where the new target was last seen or heard."""
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
        # At close range the robot can notice a target in any direction.
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
