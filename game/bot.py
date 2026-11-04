import math

from game.geometry import angle_to, center, distance, normalize, tile_of


def _off_line(origin, angle, point) -> tuple[float, float]:
    dx, dy = math.cos(angle), math.sin(angle)
    px, py = point[0] - origin[0], point[1] - origin[1]
    return px * dx + py * dy, px * dy - py * dx


def _away(angle, off) -> tuple[float, float]:
    sign = 1 if off >= 0 else -1
    return math.sin(angle) * sign, -math.cos(angle) * sign


def make_bot(reaction: float = 0.55, dodge: float = 2.5, wobble: float = 0.5, dash_bullets: bool = True,
             rewrites: bool = True, band: tuple[float, float] = (4.5, 7.5)):
    def play(run):
        return _bot(run, reaction, dodge, wobble, dash_bullets, rewrites, band)
    return play


def bot(run):
    return _bot(run, 0.55, 2.5, 0.5, True, True, (4.5, 7.5))


def _rewrite_target(room):
    p = room.player
    if p.charges <= 0 or any(e.side == "player" for e in room.enemies):
        return None
    candidates = [e for e in room.enemies if room.rewritable(e) == ""]
    argus = [e for e in room.enemies if e.side == "argus"]
    if not candidates or len(argus) < 3:
        return None
    medics = [e for e in candidates if e.kind == "medic"]
    return (medics or sorted(candidates, key=lambda e: -e.hp))[0].uid


def _bot(run, reaction, dodge, wobble_size, dash_bullets, rewrites, band):
    room, p = run.room, run.player
    grid = room.grid
    if room.state != "fight" or not room.enemies:
        goal = (grid.cols - 0.5, 9.0) if room.state == "cleared" else (8.5, 9.0)
        path = grid.route(grid.nearest_walkable(tile_of(p.pos)), tile_of(goal))
        nxt = center(path[1]) if path and len(path) > 1 else goal
        move, _ = normalize((nxt[0] - p.pos[0], nxt[1] - p.pos[1]))
        return move, (p.pos[0] + move[0], p.pos[1] + move[1]), False, False, None

    argus = [e for e in room.enemies if e.side == "argus"]
    if not argus:
        return (0, 0), p.pos, False, False, None
    seen = [e for e in argus if grid.line_of_sight(p.pos, e.pos)]
    pool = seen or argus
    medics = [e for e in pool if e.kind == "medic"]
    target = min(medics or pool, key=lambda e: distance(e.pos, p.pos))
    nearest = min(argus, key=lambda e: distance(e.pos, p.pos))
    d = distance(nearest.pos, p.pos)

    if seen:
        to = angle_to(p.pos, nearest.pos)
        side = 1 if (int(room.time / 2.5) % 2) else -1
        radial = -1.0 if d < band[0] else (0.8 if d > band[1] else 0.0)
        move = (math.cos(to + side * math.pi / 2) + math.cos(to) * radial,
                math.sin(to + side * math.pi / 2) + math.sin(to) * radial)
    else:
        path = grid.route(grid.nearest_walkable(tile_of(p.pos)), tile_of(target.pos))
        nxt = center(path[1]) if path and len(path) > 1 else target.pos
        move = (nxt[0] - p.pos[0], nxt[1] - p.pos[1])

    dash = False
    for e in argus:
        if e.windup > reaction and e.state in ("AIM", "WINDUP"):
            along, off = _off_line(e.pos, e.aim, p.pos)
            if along > 0 and abs(off) < 1.2:
                move = _away(e.aim, off)
                if e.locked and e.windup > 0.9 and p.dash_ready <= 0:
                    dash = True
    for b in room.bullets:
        if not b.hostile:
            continue
        heading = math.atan2(b.vel[1], b.vel[0])
        along, off = _off_line(b.pos, heading, p.pos)
        if 0 < along < dodge and abs(off) < 0.6:
            move = _away(heading, off)
            if dash_bullets and along / math.hypot(*b.vel) < 0.12 and p.dash_ready <= 0:
                dash = True
    wobble = (math.sin(room.time * 3.1) * wobble_size, math.cos(room.time * 2.3) * wobble_size)
    hack = _rewrite_target(room) if rewrites else None
    return move, (target.pos[0] + wobble[0], target.pos[1] + wobble[1]), target in seen, dash, hack
