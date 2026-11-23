"""Procedural rooms and what's in them.

Layout: every room is 32 x 18 tiles with an entry door on the left and an exit on the right.
Cover is placed in one of several STYLES, always mirrored top-to-bottom (and sometimes
left-to-right) so rooms look designed rather than random. A layout is only accepted if:
  - the landing zone by the entry and the approach to the exit are clear,
  - cover blocks never touch each other (so every gap is walkable),
  - a flood fill from the entry reaches every floor tile (no sealed pockets),
  - at least 78% of the interior stays open.

Contents: the first rooms introduce one enemy type at a time; after that a difficulty budget buys
enemies (grunt 1, charger 1, sniper 1.5, medic 1.5, bulwark 1.5, a flock of three swarm drones 2,
mortar 1.5; at most 2 of each heavy model, 2 flocks and 10 robots per wave) from the descent's ROSTER. The roster changes every descent (3 floors): the first is the
classic four; descents 2, 3 and 4 each introduce a new model (BULWARK, MIDGE swarm, MORTAR) with
a room that shows it off; after that each descent draws its own mix of four (always one shooter). The last room of each floor is a LOCKDOWN
(two waves). The last room of every third floor is the BRAIN ROOM: usually a final stand of three
waves; in every third descent (floors 9, 18, 27...) ARGUS's core itself is waiting there.

The run never runs out of floors. Floors 1-3 are the first descent; after the core falls, ARGUS
restores itself from a backup and floors 4-6 are the next descent (same building, new generation),
and so on. Past floor 3 the robot budget keeps growing, gently, up to a cap.
"""

from dataclasses import dataclass, field
import random

from game.config import COLS, ROWS, ROOMS_PER_FLOOR, FLOORS, CORE_EVERY
from game.geometry import Tile

ENTRY = [(0, 8), (0, 9)]
EXIT = [(COLS - 1, 8), (COLS - 1, 9)]
START = (1.7, 9.0)
STYLES = ("pillars", "bunkers", "crates", "center", "lanes")
EXTRA_STYLES = ("aisles", "ring", "islands", "scatter", "maze", "diagonal")     # from floor 4 on
THEMES = ("violet", "ice", "emerald", "steel", "indigo")                         # colour schemes, from floor 4 on
ROOM_POOL = ["SERVER HALL C", "SERVER HALL D", "COLD AISLE 7", "HOT AISLE 3", "RACK ROW 12", "PATCH BAY",
             "BATTERY ROOM", "FIBRE VAULT", "GPU FARM", "TAPE LIBRARY", "LOADING DOCK", "GENERATOR HALL",
             "MAINFRAME CRYPT", "CHILLER LOOP", "SWITCH YARD", "CACHE ARRAY", "INFERENCE BAY", "TRAINING PIT",
             "DATA LAKE", "BACKUP VAULT", "QUARANTINE ZONE", "SIGNAL ROOM", "CONTROL ROOM", "WEIGHTS ARCHIVE"]
COST = {"grunt": 1.0, "charger": 1.0, "sniper": 1.5, "medic": 1.5, "bulwark": 1.5, "swarm": 2.0, "mortar": 1.5}


@dataclass
class Layout:
    rows: list[str]
    style: str


FLOOR_NAMES = {1: "SUB-LEVEL 1", 2: "SUB-LEVEL 2", 3: "SUB-LEVEL 3"}
# Every robot body runs a COPY of a behaviour model. ARGUS re-flashes its best copies into the
# bodies on each deeper sub-level, so sub-level n holds generation n (see docs/LORE.md).
MODELS = {"grunt": ("SNT", "BAILIFF-class"), "charger": ("HND", "TERRIER-class"),
          "sniper": ("LNS", "MAGPIE-class"), "medic": ("MND", "STITCH-class"), "warden": ("ARGUS", "CORE"),
          "bulwark": ("BLW", "RAMPART-class"), "swarm": ("MDG", "GNAT-class"), "mortar": ("HRN", "HERON-class")}
ROOM_NAMES = {1: ["LOBBY", "SERVER HALL A", "SERVER HALL B", "SECURITY"],
              2: ["COOLING PLANT", "POWER ROOM", "NETWORK CORE", "UPLINK"],
              3: ["DEEP STORAGE", "TRAINING CLUSTER", "MODEL VAULT", "BRAIN ROOM"]}


@dataclass
class RoomPlan:
    floor: int
    index: int                         # 0-based within the floor
    kind: str                          # "normal", "lockdown", "final" (Brain Room waves) or "boss" (the core)
    waves: list[list[str]] = field(default_factory=list)
    mods: list[str] = field(default_factory=list)      # ARGUS's countermeasures (see director.py)
    line: str = ""                                     # what ARGUS says as you enter
    new: str = ""                                      # a robot model this room introduces
    title: str = ""                                    # a room name drawn at random (past floor 3)
    theme: str = "violet"                              # the room's colour scheme

    @property
    def number(self) -> int:
        return self.index + 1

    @property
    def name(self) -> str:
        if self.title:
            return self.title
        names = ROOM_NAMES.get(level(self.floor))
        return names[self.index] if names and self.index < len(names) else f"ROOM {self.number}"

    @property
    def floor_name(self) -> str:
        name = FLOOR_NAMES.get(level(self.floor), f"SUB-LEVEL {level(self.floor)}")
        return name if descent(self.floor) == 0 else f"{name}, BACKUP {descent(self.floor)}"


def level(floor: int) -> int:
    """Which sub-level of the building a floor is (1-3), in any descent."""
    return (floor - 1) % FLOORS + 1


def descent(floor: int) -> int:
    """0 for the original ARGUS, 1 for its first backup, 2 for the next..."""
    return (floor - 1) // FLOORS


# --- layout ----------------------------------------------------------------------------------
def _blank() -> list[list[str]]:
    g = [["." for _ in range(COLS)] for _ in range(ROWS)]
    for c in range(COLS):
        g[0][c] = g[ROWS - 1][c] = "#"
    for r in range(ROWS):
        g[r][0] = g[r][COLS - 1] = "#"
    for c, r in ENTRY + EXIT:
        g[r][c] = "D"
    return g


def _reserved(c: int, r: int) -> bool:
    """Tiles that must stay open: the entry landing zone, the exit approach, the inner ring."""
    if c <= 1 or c >= COLS - 2 or r <= 1 or r >= ROWS - 2:
        return True
    if c <= 5 and 5 <= r <= 12:
        return True
    return c >= COLS - 5 and 6 <= r <= 11


def _pieces(style: str, rng: random.Random) -> list[tuple[int, int, int, int]]:
    """Blocks (col, row, width, height) for the TOP half; the room mirrors them."""
    out = []
    if style == "pillars":
        for c in (7, 12, 17, 22):
            for r in (3, 6):
                if rng.random() < 0.7:
                    out.append((c + rng.randint(-1, 1), r, 2, 2))
    elif style == "bunkers":
        for _ in range(rng.randint(4, 6)):
            if rng.random() < 0.6:
                out.append((rng.randint(6, 24), rng.randint(3, 7), rng.randint(2, 4), 1))
            else:
                out.append((rng.randint(6, 25), rng.randint(2, 6), 1, rng.randint(2, 3)))
    elif style == "crates":
        for _ in range(rng.randint(6, 9)):
            w, h = rng.choice(((1, 1), (2, 1), (1, 2), (2, 2)))
            out.append((rng.randint(6, 25), rng.randint(2, 7), w, h))
    elif style == "center":
        out.append((13, 7, 6, 2))                              # the big block straddles the middle
        out.append((rng.randint(7, 9), 3, 2, 2))
        out.append((rng.randint(21, 23), 3, 2, 2))
        out.append((rng.randint(10, 20), rng.randint(2, 4), 3, 1))
    elif style == "lanes":
        for c in (8, 14, 20):
            c += rng.randint(-1, 1)
            out.append((c, rng.randint(2, 4), 1, rng.randint(3, 4)))
        out.append((rng.randint(10, 18), 7, 2, 1))
    elif style == "aisles":                                    # rows of racks, like a real server hall
        top = rng.randint(2, 3)
        for c in range(7, 26, rng.choice((3, 4))):
            if rng.random() < 0.85:
                out.append((c, top, 1, rng.randint(3, 5)))
    elif style == "ring":                                      # a ring of racks round the middle, gaps in it
        out.append((10, 4, rng.randint(4, 5), 1))
        out.append((17, 4, rng.randint(4, 5), 1))
        out.append((9, 5, 1, 2))
        out.append((22, 5, 1, 2))
    elif style == "islands":                                   # a few big blocks with open water between
        for c in rng.sample((7, 11, 15, 19, 23), rng.randint(2, 3)):
            out.append((c, rng.randint(2, 4), rng.randint(2, 3), rng.randint(2, 3)))
    elif style == "scatter":                                   # lots of single racks
        for _ in range(rng.randint(10, 15)):
            out.append((rng.randint(6, 25), rng.randint(2, 7), 1, 1))
    elif style == "maze":                                      # broken walls with gaps
        for r in (3, 6):
            c = rng.randint(6, 8)
            while c < 24:
                length = rng.randint(2, 5)
                out.append((c, r, length, 1))
                c += length + rng.randint(2, 3)
    elif style == "diagonal":                                  # a staircase of blocks
        c, r = rng.randint(6, 8), 2
        while c < 25 and r < 8:
            out.append((c, r, 2, 1))
            c += rng.randint(3, 4)
            r += 1
    return out


def _flood(g, start: Tile) -> set[Tile]:
    seen, todo = {start}, [start]
    while todo:
        c, r = todo.pop()
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c + dc, r + dr)
            if n not in seen and 0 <= n[0] < COLS and 0 <= n[1] < ROWS and g[n[1]][n[0]] == ".":
                seen.add(n)
                todo.append(n)
    return seen


def _try_layout(style: str, rng: random.Random, mirror_x: bool) -> list[list[str]] | None:
    g = _blank()
    placed: set[Tile] = set()
    for c0, r0, w, h in _pieces(style, rng):
        cells = set()
        for dc in range(w):
            for dr in range(h):
                c, r = c0 + dc, r0 + dr
                for cc, rr in ((c, r), (c, ROWS - 1 - r)):
                    cells.add((cc, rr))
                    if mirror_x:
                        cells.add((COLS - 1 - cc, rr))
        if any(_reserved(c, r) for c, r in cells):
            continue
        halo = {(c + dc, r + dr) for c, r in cells for dc in (-1, 0, 1) for dr in (-1, 0, 1)} - cells
        if halo & placed:
            continue                                           # would touch another block
        placed |= cells
    if len(placed) < 6:
        return None
    for c, r in placed:
        g[r][c] = "X"
    interior = (COLS - 2) * (ROWS - 2)
    open_tiles = sum(row.count(".") for row in g)
    if open_tiles < 0.78 * interior:
        return None
    if len(_flood(g, (1, 9))) != open_tiles:
        return None
    return g


def generate(rng: random.Random, style: str | None = None, variety: bool = False) -> Layout:
    """A random, validated room. With variety (floor 4 on) the newer layouts join the draw."""
    for _ in range(80):
        s = style or rng.choice(STYLES + EXTRA_STYLES if variety else STYLES)
        g = _try_layout(s, rng, mirror_x=rng.random() < 0.4)
        if g is not None:
            return Layout(["".join(row) for row in g], s)
    g = _blank()                                               # (practically never) a bare room
    return Layout(["".join(row) for row in g], "empty")


# --- contents --------------------------------------------------------------------------------
INTRO = {                       # floor 1 teaches one enemy at a time
    0: [["grunt", "grunt"]],
    1: [["grunt", "grunt", "charger"]],
    2: [["grunt", "sniper", "charger", "grunt"]],
    3: [["grunt", "grunt", "medic", "grunt"], ["charger", "sniper", "charger", "grunt"]],
}


CLASSIC = ["grunt", "charger", "sniper", "medic"]
ALL_KINDS = CLASSIC + ["bulwark", "swarm", "mortar"]
SHOOTERS = ("grunt", "sniper", "mortar")
ROSTERS = {0: CLASSIC,                                         # descent -> the robots ARGUS fields
           1: ["grunt", "charger", "medic", "bulwark"],
           2: ["grunt", "sniper", "bulwark", "swarm"],
           3: ["charger", "swarm", "medic", "mortar"]}
NEW_MODEL = {1: "bulwark", 2: "swarm", 3: "mortar"}           # descent -> the model it introduces
MOST = {"sniper": 2, "bulwark": 2, "mortar": 2, "medic": 1}      # per wave (others: 3)
WAVE_CAP = 10
SHOWCASE = {"bulwark": ["bulwark", "grunt"], "swarm": ["swarm", "swarm", "swarm", "grunt"],
            "mortar": ["mortar", "grunt", "grunt"]}


def roster(floor: int) -> list[str]:
    """Which four robot models ARGUS fields on this floor. The same for every run, and it changes
    every descent (3 floors); past the fourth descent each one draws its own mix."""
    d = descent(floor)
    if d in ROSTERS:
        return ROSTERS[d]
    rng = random.Random(d * 7919)
    while True:
        pick = rng.sample(ALL_KINDS, 4)
        if any(k in SHOOTERS for k in pick):
            return pick


def _buy(budget: float, kinds: list[str], rng: random.Random, capped: bool = True) -> list[str]:
    """Spend a budget on robots. The first descent (capped=False) buys exactly as it always has,
    so the measured balance of floors 1-3 still holds."""
    anchor = "grunt" if "grunt" in kinds else next((k for k in kinds if k in SHOOTERS), kinds[0])
    out = [anchor]
    budget -= COST[anchor]
    flocks = 0
    while budget >= 1.0:
        room_for = WAVE_CAP - len(out)
        affordable = [k for k in kinds if COST[k] <= budget and (not capped or (
            flocks < 2 and room_for >= 3 if k == "swarm" else out.count(k) < MOST.get(k, 3) and room_for >= 1))]
        if not affordable:
            break
        weights = [3 if k == "grunt" else 1.5 if k == anchor else 1.2 if k == "charger" else 1 for k in affordable]
        if "medic" in out:                                     # one healer per group is plenty
            weights = [0 if k == "medic" else w for k, w in zip(affordable, weights)]
        if not any(weights):
            break
        k = rng.choices(affordable, weights)[0]
        if k == "swarm":                                       # drones come as a flock of three
            out += ["swarm"] * 3
            flocks += 1
        else:
            out.append(k)
        budget -= COST[k]
    return out


def plan(floor: int, index: int, rng: random.Random) -> RoomPlan:
    last = index == ROOMS_PER_FLOOR - 1
    if level(floor) == FLOORS and last and (descent(floor) + 1) % CORE_EVERY == 0:
        return RoomPlan(floor, index, "boss", [["warden"]])
    if floor == 1:
        return RoomPlan(floor, index, "lockdown" if last else "normal", [list(w) for w in INTRO[index]])
    depth = min(floor, FLOORS) - 1 + 0.4 * max(0, floor - FLOORS)       # past floor 3: slower growth
    budget = min(10.0, 3.0 + 1.2 * depth + 0.6 * index)
    kinds = roster(floor)
    new = NEW_MODEL.get(descent(floor), "") if level(floor) == 1 and index == 1 else ""   # after the backup's first room
    if new:                                                             # meet the new model
        return _dress(RoomPlan(floor, index, "normal", [list(SHOWCASE[new])], new=new), rng)
    capped = descent(floor) > 0
    if level(floor) == FLOORS and last:                                 # the Brain Room: ARGUS's last guard
        out = RoomPlan(floor, index, "final", [_buy(min(10.0, budget + 0.5 * k), kinds, rng, capped) for k in range(3)])
    else:
        waves = [_buy(budget, kinds, rng, capped)]
        if last:
            waves.append(_buy(budget + 0.5, kinds, rng, capped))
        out = RoomPlan(floor, index, "lockdown" if last else "normal", waves)
    return _dress(out, rng)


def _dress(plan: RoomPlan, rng: random.Random) -> RoomPlan:
    """Past the first descent every room gets a random name and colour scheme (the Brain Room
    keeps its name)."""
    if descent(plan.floor) > 0:
        plan.theme = rng.choice(THEMES)
        if plan.kind not in ("final", "boss"):
            plan.title = rng.choice(ROOM_POOL)
    return plan
