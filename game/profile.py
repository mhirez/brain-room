from dataclasses import dataclass, field
import datetime
from pathlib import Path

from game.save import Store

PROFILE_PATH = Path(__file__).resolve().parent.parent / "saves" / "profile.json"
WEB_KEY = "brain-room-profile"

RANKS = [(0, "INTERN"), (800, "JUNIOR ANALYST"), (2500, "DATA SCIENTIST"), (6000, "SENIOR SCIENTIST"),
         (12000, "LEAD SCIENTIST"), (25000, "PRINCIPAL SCIENTIST"), (50000, "DIRECTOR OF AI"),
         (90000, "CHIEF SCIENTIST")]
BEYOND = 50000


def rank(xp: int) -> tuple[str, float, int]:
    top = RANKS[-1][0]
    if xp >= top:
        stars, into = divmod(xp - top, BEYOND)
        title = RANKS[-1][1] + ("" if stars == 0 else f" +{stars}")
        return title, into / BEYOND, top + (stars + 1) * BEYOND
    for (lo, title), (hi, _) in zip(RANKS, RANKS[1:]):
        if xp < hi:
            return title, (xp - lo) / (hi - lo), hi
    return RANKS[-1][1], 0.0, top


@dataclass(frozen=True)
class Node:
    key: str
    branch: str
    name: str
    text: str
    cost: int
    requires: str | None


RESEARCH = [
    Node("focus", "DEBUGGER", "DEEP FOCUS", "The debugger drains 25% slower.", 10, None),
    Node("reboot", "DEBUGGER", "QUICK REBOOT", "The debugger refills 50% faster.", 25, "focus"),
    Node("overclock", "DEBUGGER", "OVERCLOCK", "Time slows further while you debug.", 50, "reboot"),
    Node("spare", "OVERRIDE", "SPARE KEY", "Start every run with 2 override charges.", 10, None),
    Node("rootkit", "OVERRIDE", "ROOT KIT", "Overridden robots fight for you 3 s longer.", 25, "spare"),
    Node("chain", "OVERRIDE", "CHAIN REACTION", "Overload blasts are 50% stronger.", 50, "rootkit"),
    Node("coat", "FIELD KIT", "KEVLAR LAB COAT", "+1 max health.", 10, None),
    Node("sprinter", "FIELD KIT", "SPRINTER", "Dash recharges 15% faster.", 25, "coat"),
    Node("medic", "FIELD KIT", "FIELD MEDIC", "One heart back after every cleared room.", 50, "sprinter"),
]
NODES = {n.key: n for n in RESEARCH}
BRANCHES = ["DEBUGGER", "OVERRIDE", "FIELD KIT"]


def apply_research(player, keys):
    s = player.stats
    for key in keys:
        if key == "focus":
            s.sync_drain *= 0.75
        elif key == "reboot":
            s.sync_refill *= 1.5
        elif key == "overclock":
            s.sync_slow = 0.14
        elif key == "spare":
            player.charges = max(player.charges, 2)
        elif key == "rootkit":
            s.rewrite_time += 3.0
        elif key == "chain":
            s.overload *= 1.5
        elif key == "coat":
            s.max_hp += 1
            player.hp += 1
        elif key == "sprinter":
            s.dash_cooldown *= 0.85
        elif key == "medic":
            s.repair += 1


@dataclass(frozen=True)
class Achievement:
    key: str
    name: str
    text: str
    check: object


def _n(stats, key):
    return stats.get(key, 0)


ACHIEVEMENTS = [
    Achievement("first_room", "FIRST CONTACT", "Clear a room.", lambda s, p: _n(s, "rooms") >= 1),
    Achievement("first_run", "NIGHT SHIFT", "Finish your first run.", lambda s, p: _n(s, "finished") >= 1),
    Achievement("crossfire", "CROSSFIRE", "Let a robot destroy another robot.", lambda s, p: _n(s, "crossfire kills") >= 1),
    Achievement("untouchable", "UNTOUCHABLE", "Clear a room without being hit.", lambda s, p: _n(s, "flawless rooms") >= 1),
    Achievement("walltamer", "WALL TAMER", "Daze a Hound against a wall.", lambda s, p: _n(s, "slams") >= 1),
    Achievement("turncoat", "TURNCOAT", "Let an overridden robot destroy one of ARGUS's.", lambda s, p: _n(s, "turncoats") >= 1),
    Achievement("combo", "COMBO ARTIST", "Reach a x3 combo.", lambda s, p: _n(s, "best combo") >= 3.0),
    Achievement("bedside", "BEDSIDE MANNER", "Be healed by an overridden Mender.", lambda s, p: _n(s, "mended") >= 1),
    Achievement("read_room", "READ THE ROOM", "Spend 60 s in the debugger in one run.", lambda s, p: _n(s, "debug") >= 60),
    Achievement("deprecated", "DEPRECATED", "Clear a Brain Room: shut ARGUS down.", lambda s, p: _n(s, "shutdowns") >= 1),
    Achievement("backup", "GENERATION GAP", "Reach floor 4, ARGUS's first backup.", lambda s, p: _n(s, "floor") >= 4),
    Achievement("shield", "SHIELD BREAKER", "Destroy a BULWARK.", lambda s, p: _n(s, "kill:bulwark") >= 1),
    Achievement("crossfire5", "FRIENDLY FIRE ISN'T", "5 crossfire kills in one run.", lambda s, p: _n(s, "crossfire kills") >= 5),
    Achievement("flawless_floor", "FLAWLESS SHIFT", "Clear a whole floor without being hit.", lambda s, p: _n(s, "flawless floors") >= 1),
    Achievement("early", "EARLY SHUTDOWN", "Shut ARGUS down before the upload reaches 40%.", lambda s, p: _n(s, "early shutdowns") >= 1),
    Achievement("pest", "PEST CONTROL", "Destroy 10 MIDGE drones in one run.", lambda s, p: _n(s, "kill:swarm") >= 10),
    Achievement("admin", "ADMIN PRIVILEGES", "Override 10 robots (over all your runs).", lambda s, p: p.lifetime.get("overrides", 0) >= 10),
    Achievement("battery", "COUNTER-BATTERY", "Destroy a MORTAR.", lambda s, p: _n(s, "kill:mortar") >= 1),
    Achievement("eye", "EYE TO EYE", "Destroy ARGUS's core (floor 9).", lambda s, p: _n(s, "cores") >= 1),
    Achievement("deep", "DEEP DIVE", "Reach floor 10.", lambda s, p: _n(s, "floor") >= 10),
    Achievement("daily", "DAILY DOCTOR", "Finish a daily run.", lambda s, p: _n(s, "daily") >= 1),
    Achievement("researcher", "RESEARCHER", "Complete 3 research upgrades.", lambda s, p: len(p.research) >= 3),
    Achievement("regular", "NIGHT SHIFT REGULAR", "Finish 10 runs.", lambda s, p: p.lifetime.get("runs", 0) >= 10),
    Achievement("it_got_out", "IT GOT OUT", "Let the upload reach 100%.", lambda s, p: _n(s, "escaped") >= 1),
    Achievement("abyss", "THE ABYSS", "Reach floor 20.", lambda s, p: _n(s, "floor") >= 20),
]
BY_KEY = {a.key: a for a in ACHIEVEMENTS}


@dataclass
class Summary:
    xp: int = 0
    shards: int = 0
    rank_before: str = ""
    rank_after: str = ""
    progress: float = 0.0
    achievements: list = field(default_factory=list)
    codex: list = field(default_factory=list)
    streak: int = 1
    daily_best: bool = False

    @property
    def ranked_up(self) -> bool:
        return self.rank_after != self.rank_before


class Profile:
    def __init__(self, path: Path | None = PROFILE_PATH):
        self.store = Store(path, WEB_KEY)
        d = self.store.read()
        self.xp = int(d.get("xp", 0))
        self.shards = int(d.get("shards", 0))
        self.research: list[str] = [k for k in d.get("research", []) if k in NODES]
        self.achievements: list[str] = [k for k in d.get("achievements", []) if k in BY_KEY]
        self.codex: list[str] = list(d.get("codex", []))
        self.lifetime: dict = dict(d.get("lifetime", {}))
        self.daily: dict = dict(d.get("daily", {}))
        self.streak = int(d.get("streak", 0))
        self.last_day = d.get("last_day", "")

    def save(self):
        self.store.write({"xp": self.xp, "shards": self.shards, "research": self.research,
                          "achievements": self.achievements, "codex": self.codex,
                          "lifetime": self.lifetime,
                          "daily": self.daily, "streak": self.streak, "last_day": self.last_day})

    @property
    def rank(self) -> tuple[str, float, int]:
        return rank(self.xp)

    def next_goal(self) -> Achievement | None:
        return next((a for a in ACHIEVEMENTS if a.key not in self.achievements), None)

    def can_buy(self, key: str) -> bool:
        n = NODES[key]
        return key not in self.research and self.shards >= n.cost and (n.requires is None or n.requires in self.research)

    def buy(self, key: str) -> list[Achievement]:
        if not self.can_buy(key):
            return []
        self.shards -= NODES[key].cost
        self.research.append(key)
        won = self.check({})
        self.save()
        return won

    def check(self, stats: dict) -> list[Achievement]:
        new = [a for a in ACHIEVEMENTS if a.key not in self.achievements and a.check(stats, self)]
        self.achievements += [a.key for a in new]
        return new

    def finish_run(self, run, daily: str = "", today: datetime.date | None = None) -> Summary:
        today = today or datetime.date.today()
        stats = run.progress()
        stats["finished"] = 1
        if daily:
            stats["daily"] = 1
        paid = getattr(run, "paid", None)
        now = {"score": run.total_score, "floor": run.floor, "rooms": run.rooms_cleared, "kills": run.kills,
               "shutdowns": stats.get("shutdowns", 0), "overrides": stats.get("overrides", 0),
               "crossfire kills": stats.get("crossfire kills", 0)}
        was = paid or {"score": 0, "floor": 1, "rooms": 0, "kills": 0, "shutdowns": 0, "overrides": 0,
                       "crossfire kills": 0}
        gain = {k: max(0, now[k] - was[k]) for k in now}
        run.paid = now
        before = self.rank[0]
        life = self.lifetime
        life["runs"] = life.get("runs", 0) + (0 if paid else 1)
        for key in ("kills", "overrides", "crossfire kills", "shutdowns"):
            life[key] = life.get(key, 0) + gain[key]
        life["deepest"] = max(life.get("deepest", 0), run.floor)
        life["best combo"] = max(life.get("best combo", 0), stats.get("best combo", 0))
        new = self.check(stats)
        codex = [k for k in stats.get("kinds", []) if k not in self.codex]
        self.codex += codex
        xp = gain["score"] // 10 + 60 * gain["floor"] + 150 * gain["shutdowns"] + 50 * len(new)
        shards = gain["rooms"] + 8 * gain["shutdowns"] + 3 * len(new) + (3 if daily and not paid else 0)
        self.xp += xp
        self.shards += shards
        yesterday = (today - datetime.timedelta(days=1)).isoformat()
        if self.last_day == yesterday:
            self.streak += 1
        elif self.last_day != today.isoformat():
            self.streak = 1
        self.last_day = today.isoformat()
        daily_best = False
        if daily:
            daily_best = run.total_score > self.daily.get(daily, -1)
            if daily_best:
                self.daily[daily] = run.total_score
        self.save()
        title, progress, _ = self.rank
        return Summary(xp, shards, before, title, progress, new, codex, self.streak, daily_best)


def daily_seed(day: datetime.date | None = None) -> tuple[int, str]:
    day = day or datetime.date.today()
    return int(day.strftime("%Y%m%d")), day.isoformat()
