from dataclasses import dataclass, field
import heapq
import math

SQRT2 = math.sqrt(2)
STEPS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
         (1, 1, SQRT2), (1, -1, SQRT2), (-1, 1, SQRT2), (-1, -1, SQRT2)]


@dataclass
class SearchResult:
    path: list[tuple[int, int]] | None
    cost: float = math.inf
    explored: set = field(default_factory=set)


def octile(a, b) -> float:
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    return (dx + dy) + (SQRT2 - 2) * min(dx, dy)


def astar(start, goal, walkable, extra_cost=None, max_nodes: int = 4000) -> SearchResult:
    if not walkable(*goal):
        return SearchResult(None)
    frontier = [(octile(start, goal), 0.0, start)]
    previous_tile = {}
    cheapest_cost = {start: 0.0}
    visited = set()

    while frontier and len(visited) < max_nodes:
        _, cost, tile = heapq.heappop(frontier)
        if tile in visited:
            continue
        if tile == goal:
            path = [tile]
            while tile in previous_tile:
                tile = previous_tile[tile]
                path.append(tile)
            path.reverse()
            return SearchResult(path, cost, visited)

        visited.add(tile)
        column, row = tile
        for dx, dy, step_cost in STEPS:
            next_column = column + dx
            next_row = row + dy
            neighbor = (next_column, next_row)
            if neighbor in visited or not walkable(next_column, next_row):
                continue
            if dx != 0 and dy != 0:
                if not walkable(next_column, row) or not walkable(column, next_row):
                    continue

            new_cost = cost + step_cost
            if extra_cost:
                new_cost += extra_cost(next_column, next_row)
            if new_cost < cheapest_cost.get(neighbor, math.inf):
                cheapest_cost[neighbor] = new_cost
                previous_tile[neighbor] = tile
                estimated_total = new_cost + octile(neighbor, goal)
                heapq.heappush(frontier, (estimated_total, new_cost, neighbor))

    return SearchResult(None, math.inf, visited)
