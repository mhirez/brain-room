import math

from game.geometry import Point, Tile, center, clamp, distance, tile_of
from game.pathfinding import astar

SOLID = frozenset("#XD")


class Grid:
    def __init__(self, rows: list[str]):
        self.rows = len(rows)
        self.cols = len(rows[0])
        self.tiles = [list(r) for r in rows]
        self._routes: dict = {}
        self._sight: dict = {}

    def at(self, c: int, r: int) -> str:
        return self.tiles[r][c] if 0 <= c < self.cols and 0 <= r < self.rows else "#"

    def solid(self, c: int, r: int) -> bool:
        return self.at(c, r) in SOLID

    def walkable(self, c: int, r: int) -> bool:
        return self.at(c, r) not in SOLID

    def set(self, c: int, r: int, ch: str):
        self.tiles[r][c] = ch
        self._routes.clear()
        self._sight.clear()

    def floor_tiles(self) -> list[Tile]:
        return [(c, r) for r in range(self.rows) for c in range(self.cols) if self.tiles[r][c] == "."]

    def near_cover(self, t: Tile) -> bool:
        c, r = t
        return any(self.solid(c + dc, r + dr) for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)))

    def line_of_sight(self, a: Point, b: Point) -> bool:
        x0, y0 = a
        dx, dy = b[0] - x0, b[1] - y0
        c, r = tile_of(a)
        end = tile_of(b)
        step_c = 1 if dx > 0 else -1
        step_r = 1 if dy > 0 else -1
        t_dx = abs(1 / dx) if dx else math.inf
        t_dy = abs(1 / dy) if dy else math.inf
        t_x = ((c + (dx > 0)) - x0) / dx if dx else math.inf
        t_y = ((r + (dy > 0)) - y0) / dy if dy else math.inf
        for _ in range(self.cols + self.rows + 2):
            if (c, r) == end:
                return True
            if abs(t_x - t_y) < 1e-9:
                if self.solid(c + step_c, r) and self.solid(c, r + step_r):
                    return False
                c, r = c + step_c, r + step_r
                t_x += t_dx
                t_y += t_dy
            elif t_x < t_y:
                if t_x > 1:
                    return True
                c += step_c
                t_x += t_dx
            else:
                if t_y > 1:
                    return True
                r += step_r
                t_y += t_dy
            if (c, r) != end and self.solid(c, r):
                return False
        return True

    def raycast(self, origin: Point, angle: float, max_dist: float) -> float:
        x0, y0 = origin
        dx, dy = math.cos(angle), math.sin(angle)
        c, r = tile_of(origin)
        step_c = 1 if dx > 0 else -1
        step_r = 1 if dy > 0 else -1
        t_dx = abs(1 / dx) if abs(dx) > 1e-12 else math.inf
        t_dy = abs(1 / dy) if abs(dy) > 1e-12 else math.inf
        t_x = ((c + (dx > 0)) - x0) / dx if abs(dx) > 1e-12 else math.inf
        t_y = ((r + (dy > 0)) - y0) / dy if abs(dy) > 1e-12 else math.inf
        while True:
            if t_x < t_y:
                t, t_x, c = t_x, t_x + t_dx, c + step_c
            else:
                t, t_y, r = t_y, t_y + t_dy, r + step_r
            if t >= max_dist:
                return max_dist
            if self.solid(c, r):
                return t

    def sees_tile(self, frm: Tile, to: Tile) -> bool:
        key = (frm, to) if frm <= to else (to, frm)
        seen = self._sight.get(key)
        if seen is None:
            seen = self._sight[key] = self.line_of_sight(center(frm), center(to))
        return seen

    def free(self, p: Point, radius: float) -> bool:
        x, y = p
        for r in range(int(math.floor(y - radius)), int(math.floor(y + radius)) + 1):
            for c in range(int(math.floor(x - radius)), int(math.floor(x + radius)) + 1):
                if not self.solid(c, r):
                    continue
                nx, ny = clamp(x, c, c + 1), clamp(y, r, r + 1)
                if (x - nx) ** 2 + (y - ny) ** 2 < radius * radius:
                    return False
        return True

    def resolve(self, p: Point, radius: float) -> Point:
        x, y = p
        for _ in range(3):
            pushed = False
            for r in range(int(math.floor(y - radius)), int(math.floor(y + radius)) + 1):
                for c in range(int(math.floor(x - radius)), int(math.floor(x + radius)) + 1):
                    if not self.solid(c, r):
                        continue
                    nx, ny = clamp(x, c, c + 1), clamp(y, r, r + 1)
                    ddx, ddy = x - nx, y - ny
                    d2 = ddx * ddx + ddy * ddy
                    if d2 >= radius * radius:
                        continue
                    if d2 > 1e-12:
                        d = math.sqrt(d2)
                        x += ddx / d * (radius - d)
                        y += ddy / d * (radius - d)
                    else:
                        exits = [(x - c + radius, -1, 0), (c + 1 - x + radius, 1, 0),
                                 (y - r + radius, 0, -1), (r + 1 - y + radius, 0, 1)]
                        push, sx, sy = min(exits)
                        x, y = x + sx * push, y + sy * push
                    pushed = True
            if not pushed:
                break
        return x, y

    def move(self, p: Point, delta: Point, radius: float) -> Point:
        length = math.hypot(*delta)
        steps = max(1, int(math.ceil(length / 0.2)))
        x, y = p
        for _ in range(steps):
            x, y = self.resolve((x + delta[0] / steps, y + delta[1] / steps), radius)
        return x, y

    def clear_line(self, a: Point, b: Point, radius: float) -> bool:
        n = max(1, int(distance(a, b) / 0.25))
        for i in range(1, n + 1):
            t = i / n
            if not self.free((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), radius):
                return False
        return True

    def nearest_walkable(self, t: Tile) -> Tile:
        if self.walkable(*t):
            return t
        best, best_d = t, math.inf
        for c, r in self.floor_tiles():
            d = (c - t[0]) ** 2 + (r - t[1]) ** 2
            if d < best_d:
                best, best_d = (c, r), d
        return best

    def route(self, start: Tile, goal: Tile, extra_cost=None) -> list[Tile] | None:
        goal = self.nearest_walkable(goal)
        if extra_cost is None:
            key = (start, goal)
            if key not in self._routes:
                self._routes[key] = astar(start, goal, self.walkable).path
            return self._routes[key]
        return astar(start, goal, self.walkable, extra_cost).path
