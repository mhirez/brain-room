from dataclasses import dataclass, field
import random

from game.config import COLS, ROWS, ROOMS_PER_FLOOR, FLOORS, CORE_EVERY
from game.geometry import Tile

ENTRY = [(0, 8), (0, 9)]
EXIT = [(COLS - 1, 8), (COLS - 1, 9)]
START = (1.7, 9.0)
STYLES = ("pillars", "bunkers", "crates", "center", "lanes")
EXTRA_STYLES = ("aisles", "ring", "islands", "scatter", "maze", "diagonal")
THEMES = ("violet", "ice", "emerald", "steel", "indigo")
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
MODELS = {"grunt": ("SNT", "BAILIFF-class"), "charger": ("HND", "TERRIER-class"),
          "sniper": ("LNS", "MAGPIE-class"), "medic": ("MND", "STITCH-class"), "warden": ("ARGUS", "CORE"),
          "bulwark": ("BLW", "RAMPART-class"), "swarm": ("MDG", "GNAT-class"), "mortar": ("HRN", "HERON-class")}
ROOM_NAMES = {1: ["LOBBY", "SERVER HALL A", "SERVER HALL B", "SECURITY"],
              2: ["COOLING PLANT", "POWER ROOM", "NETWORK CORE", "UPLINK"],
              3: ["DEEP STORAGE", "TRAINING CLUSTER", "MODEL VAULT", "BRAIN ROOM"]}


@dataclass
class RoomPlan:
    floor: int
    index: int
    kind: str
    waves: list[list[str]] = field(default_factory=list)
    mods: list[str] = field(default_factory=list)
    line: str = ""
    new: str = ""
    title: str = ""
    theme: str = "violet"

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
    return (floor - 1) % FLOORS + 1


def descent(floor: int) -> int:
    return (floor - 1) // FLOORS


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
    if c <= 1 or c >= COLS - 2 or r <= 1 or r >= ROWS - 2:
        return True
    if c <= 5 and 5 <= r <= 12:
        return True
    return c >= COLS - 5 and 6 <= r <= 11


def _pieces(style: str, rng: random.Random) -> list[tuple[int, int, int, int]]:
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
        out.append((13, 7, 6, 2))
        out.append((rng.randint(7, 9), 3, 2, 2))
        out.append((rng.randint(21, 23), 3, 2, 2))
        out.append((rng.randint(10, 20), rng.randint(2, 4), 3, 1))
    elif style == "lanes":
        for c in (8, 14, 20):
            c += rng.randint(-1, 1)
            out.append((c, rng.randint(2, 4), 1, rng.randint(3, 4)))
        out.append((rng.randint(10, 18), 7, 2, 1))
    elif style == "aisles":
        top = rng.randint(2, 3)
        for c in range(7, 26, rng.choice((3, 4))):
            if rng.random() < 0.85:
                out.append((c, top, 1, rng.randint(3, 5)))
    elif style == "ring":
        out.append((10, 4, rng.randint(4, 5), 1))
        out.append((17, 4, rng.randint(4, 5), 1))
        out.append((9, 5, 1, 2))
        out.append((22, 5, 1, 2))
    elif style == "islands":
        for c in rng.sample((7, 11, 15, 19, 23), rng.randint(2, 3)):
            out.append((c, rng.randint(2, 4), rng.randint(2, 3), rng.randint(2, 3)))
    elif style == "scatter":
        for _ in range(rng.randint(10, 15)):
            out.append((rng.randint(6, 25), rng.randint(2, 7), 1, 1))
    elif style == "maze":
        for r in (3, 6):
            c = rng.randint(6, 8)
            while c < 24:
                length = rng.randint(2, 5)
                out.append((c, r, length, 1))
                c += length + rng.randint(2, 3)
    elif style == "diagonal":
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
            continue
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
    for _ in range(80):
        s = style or rng.choice(STYLES + EXTRA_STYLES if variety else STYLES)
        g = _try_layout(s, rng, mirror_x=rng.random() < 0.4)
        if g is not None:
            return Layout(["".join(row) for row in g], s)
    g = _blank()
    return Layout(["".join(row) for row in g], "empty")


INTRO = {
    0: [["grunt", "grunt"]],
    1: [["grunt", "grunt", "charger"]],
    2: [["grunt", "sniper", "charger", "grunt"]],
    3: [["grunt", "grunt", "medic", "grunt"], ["charger", "sniper", "charger", "grunt"]],
}


CLASSIC = ["grunt", "charger", "sniper", "medic"]
ALL_KINDS = CLASSIC + ["bulwark", "swarm", "mortar"]
SHOOTERS = ("grunt", "sniper", "mortar")
ROSTERS = {0: CLASSIC,
           1: ["grunt", "charger", "medic", "bulwark"],
           2: ["grunt", "sniper", "bulwark", "swarm"],
           3: ["charger", "swarm", "medic", "mortar"]}
NEW_MODEL = {1: "bulwark", 2: "swarm", 3: "mortar"}
MOST = {"sniper": 2, "bulwark": 2, "mortar": 2, "medic": 1}
WAVE_CAP = 10
SHOWCASE = {"bulwark": ["bulwark", "grunt"], "swarm": ["swarm", "swarm", "swarm", "grunt"],
            "mortar": ["mortar", "grunt", "grunt"]}


def roster(floor: int) -> list[str]:
    d = descent(floor)
    if d in ROSTERS:
        return ROSTERS[d]
    rng = random.Random(d * 7919)
    while True:
        pick = rng.sample(ALL_KINDS, 4)
        if any(k in SHOOTERS for k in pick):
            return pick


def _buy(budget: float, kinds: list[str], rng: random.Random, capped: bool = True) -> list[str]:
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
        if "medic" in out:
            weights = [0 if k == "medic" else w for k, w in zip(affordable, weights)]
        if not any(weights):
            break
        k = rng.choices(affordable, weights)[0]
        if k == "swarm":
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
    depth = min(floor, FLOORS) - 1 + 0.4 * max(0, floor - FLOORS)
    budget = min(10.0, 3.0 + 1.2 * depth + 0.6 * index)
    kinds = roster(floor)
    new = NEW_MODEL.get(descent(floor), "") if level(floor) == 1 and index == 1 else ""
    if new:
        return _dress(RoomPlan(floor, index, "normal", [list(SHOWCASE[new])], new=new), rng)
    capped = descent(floor) > 0
    if level(floor) == FLOORS and last:
        out = RoomPlan(floor, index, "final", [_buy(min(10.0, budget + 0.5 * k), kinds, rng, capped) for k in range(3)])
    else:
        waves = [_buy(budget, kinds, rng, capped)]
        if last:
            waves.append(_buy(budget + 0.5, kinds, rng, capped))
        out = RoomPlan(floor, index, "lockdown" if last else "normal", waves)
    return _dress(out, rng)


def _dress(plan: RoomPlan, rng: random.Random) -> RoomPlan:
    if descent(plan.floor) > 0:
        plan.theme = rng.choice(THEMES)
        if plan.kind not in ("final", "boss"):
            plan.title = rng.choice(ROOM_POOL)
    return plan
