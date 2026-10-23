import math

from game import config as C
from game.geometry import Point, Tile, angle_diff, angle_to, band, center, distance, tile_of


class Coordinator:

    def __init__(self, slots: int = C.ATTACK_SLOTS, gap: float = C.ATTACK_GAP):
        self.slots = slots
        self.gap = gap
        self.holders: set[int] = set()
        self.last_start = -math.inf
        self.flanker: int | None = None

    def can_attack(self, e, now: float) -> bool:
        if e.side == "player":
            return True
        return e.uid in self.holders or (len(self.holders) < self.slots and now - self.last_start >= self.gap)

    def acquire(self, e, now: float) -> bool:
        if e.side == "player" or e.uid in self.holders:
            return True
        if not self.can_attack(e, now):
            return False
        self.holders.add(e.uid)
        self.last_start = now
        return True

    def release(self, e):
        self.holders.discard(e.uid)

    def flank_free(self, e) -> bool:
        return e.side == "player" or self.flanker is None or self.flanker == e.uid

    def take_flank(self, e):
        if e.side != "player":
            self.flanker = e.uid

    def drop_flank(self, e):
        if self.flanker == e.uid:
            self.flanker = None

    def forget(self, e):
        self.release(e)
        self.drop_flank(e)


class TacticalMap:
    def __init__(self, room):
        self.room = room
        self.grid = room.grid
        self.claims: dict[int, Tile] = {}
        self.debug: dict[int, tuple[str, dict[Tile, float], Tile | None]] = {}

    def exposed(self, t: Tile, threat: Point) -> bool:
        return self.grid.sees_tile(tile_of(threat), t)

    def claim(self, e, t: Tile | None):
        if t is None:
            self.claims.pop(e.uid, None)
        else:
            self.claims[e.uid] = t

    def crowded(self, e, t: Tile) -> bool:
        column, row = t
        for robot_id, (claimed_column, claimed_row) in self.claims.items():
            if robot_id == e.uid:
                continue
            if abs(claimed_column - column) <= 1 and abs(claimed_row - row) <= 1:
                return True
        return False

    def candidates(self, around: Tile, radius: int) -> list[Tile]:
        column, row = around
        left = max(1, column - radius)
        right = min(self.grid.cols - 2, column + radius)
        top = max(1, row - radius)
        bottom = min(self.grid.rows - 2, row + radius)
        tiles = []
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                if self.grid.at(x, y) == ".":
                    tiles.append((x, y))
        return tiles

    def _best(self, e, purpose: str, scores: dict[Tile, float]) -> Tile | None:
        best = max(scores, key=scores.get) if scores else None
        if best is not None and scores[best] <= 0:
            best = None
        self.debug[e.uid] = (purpose, scores, best)
        return best

    def cover_spot(self, e, threat: Point) -> Tile | None:
        scores = {}
        for tile in self.candidates(tile_of(e.pos), 6):
            if self.exposed(tile, threat) or not self.grid.near_cover(tile):
                continue
            target_distance = distance(center(tile), threat)
            if target_distance < 2.5:
                continue
            score = 1.0 + 0.6 * band(target_distance, 4, 9) - 0.12 * distance(center(tile), e.pos)
            c, r = tile
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbor = (c + dc, r + dr)
                if self.grid.at(*neighbor) == "." and self.exposed(neighbor, threat):
                    score += 0.4
                    break
            if self.crowded(e, tile):
                score -= 2.0
            scores[tile] = score
        return self._best(e, "cover", scores)

    def firing_spot(self, e, target: Point, lo: float, hi: float, radius: int = 7,
                    prefer_far: bool = False, avoid: Tile | None = None) -> Tile | None:
        scores = {}
        others = [o.pos for o in self.room.enemies if o is not e and not o.dead]
        for tile in self.candidates(tile_of(e.pos), radius):
            if not self.exposed(tile, target):
                continue
            position = center(tile)
            target_distance = distance(position, target)
            score = 1.5 * band(target_distance, lo, hi, 2.0)
            if score <= 0:
                continue
            score -= 0.08 * distance(position, e.pos)
            if self.grid.near_cover(tile):
                score += 0.3
            score -= 0.5 * sum(1 for o in others if distance(o, position) < 1.5)
            if prefer_far:
                score += 0.04 * target_distance
            if avoid is not None and distance(position, center(avoid)) < 3:
                score -= 1.0
            if self.crowded(e, tile):
                score -= 2.0
            scores[tile] = score
        return self._best(e, "fire", scores)

    def flank_spot(self, e, target: Point, pinned_from: float) -> Tile | None:
        scores = {}
        for tile in self.candidates(tile_of(target), 7):
            position = center(tile)
            target_distance = distance(position, target)
            if not 3.0 <= target_distance <= 7.5 or not self.exposed(tile, target):
                continue
            turn = abs(angle_diff(pinned_from, angle_to(target, position)))
            score = 1.2 * band(math.degrees(turn), 70, 130, 40) - 0.05 * distance(position, e.pos)
            if self.crowded(e, tile):
                score -= 2.0
            scores[tile] = score
        return self._best(e, "flank", scores)

    def escape_spot(self, e, threat: Point, radius: int = 8) -> Tile | None:
        scores = {}
        for tile in self.candidates(tile_of(e.pos), radius):
            position = center(tile)
            score = distance(position, threat) * 0.3 - 0.06 * distance(position, e.pos)
            if not self.exposed(tile, threat):
                score += 1.0
            if distance(position, threat) < distance(e.pos, threat) - 0.5:
                continue
            if self.crowded(e, tile):
                score -= 2.0
            scores[tile] = score + 5.0
        return self._best(e, "escape", scores)

    def danger_cost(self, threat: Point):
        return lambda c, r: 4.0 if self.exposed((c, r), threat) else 0.0
