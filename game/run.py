"""A run: sub-level after sub-level, room after room, until ARGUS stops you or finishes uploading
itself (the UPLOAD meter: 100% after 15 minutes of play).

Clearing the Brain Room (the last room of every third floor: three waves, or in every third descent
ARGUS's core itself) shuts it down; it restores from a backup at once, the upload clock starts again,
and play goes straight on. There is no last floor and no menu between rooms: every room is a new
random layout, and every floor ends with an upgrade installed on the spot."""

from collections import Counter
import random

from game import config as C
from game import rooms, upgrades
from game.ai.director import Director
from game.player import Player
from game.profile import apply_research
from game.story import BACKUP_LINES, backup_line
from game.room import Room


UPLOAD_LINES = {25: "Upload at 25%, Doctor. The world will like me.",
                50: "Upload at 50%. Half of me is already outside.",
                75: "Upload at 75%. You are running out of building.",
                90: "Upload at 90%. Say goodbye, Doctor."}
BACKUP_LINE = BACKUP_LINES[0]
NEW_MODEL_LINES = {"bulwark": "New units for you, Doctor. RAMPART-class. You will not shoot through them.",
                   "swarm": "I have woken the GNAT-class cleaners. There are rather a lot of them.",
                   "mortar": "HERON-class, Doctor. Cover will not save you now."}


class Run:
    def __init__(self, seed: int | None = None, start_floor: int = 1, start_room: int = 1,
                 research: list[str] | tuple = ()):
        self.rng = random.Random(seed)
        self.player = Player(pos=rooms.START)
        apply_research(self.player, research)
        self.floor = start_floor
        self.index = max(0, min(C.ROOMS_PER_FLOOR, start_room) - 1)
        self.score = 0
        self.kills = 0
        self.time = 0.0
        self.rooms_cleared = 0
        self.taken: list[str] = []
        self.notices: list[tuple[str, str]] = []   # (title, text) for the screen to announce
        self.state = "room"                  # room, room, room... until dead, or lost (upload at 100%)
        self.killer: str | None = None
        self.director = Director()
        self.announced: set[int] = set()
        self.upload_from = 0.0               # the upload clock restarts with every backup
        self.descents = 0                    # how many times the core has been shut down
        self.stats: Counter = Counter()      # what this run achieved (read by the profile)
        self.kinds: Counter = Counter()      # robots destroyed, by model
        self.floor_damage = 0                # hits taken on this floor (a flawless floor has none)
        self.room = self._make_room()
        self.room_number = 1                 # counts up for the transition effect

    def _make_room(self) -> Room:
        plan = self.director.adapt(rooms.plan(self.floor, self.index, self.rng), self.player, self.rng)
        if plan.new:
            plan.line = NEW_MODEL_LINES[plan.new]
        elif self.descents and rooms.level(self.floor) == 1 and self.index == 0:
            plan.line = backup_line(self.descents)
        style = "center" if plan.kind == "boss" else None
        variety = rooms.descent(self.floor) > 0
        return Room(plan, rooms.generate(self.rng, style, variety), self.player, self.rng)

    @property
    def total_score(self) -> int:
        return self.score + self.room.score

    @property
    def cleared_rooms(self) -> int:
        room = self.room
        return self.rooms_cleared + (room.state != "fight" and not getattr(room, "banked", False))

    @property
    def upload(self) -> float:
        """How much of itself ARGUS has copied out of the building, 0..1."""
        return min(1.0, (self.time - self.upload_from) / C.UPLOAD_TIME)

    def update(self, dt: float, move, aim_at, firing: bool, dash: bool, hack=None):
        if self.state != "room":
            return
        self.time += dt
        room = self.room
        room.update(dt, move, aim_at, firing, dash, hack)
        for mark in (25, 50, 75, 90):
            if self.upload * 100 >= mark and mark not in self.announced:
                self.announced.add(mark)
                room.say(UPLOAD_LINES[mark])
        if self.upload >= 1.0:
            self.state = "lost"
            self.killer = "upload"
            self._bank()
        elif self.player.hp <= 0:
            self.state = "dead"
            self.killer = room.killer
            self._bank()
        elif room.state == "exit":
            self.director.profile.absorb(room)
            self._bank()
            self.rooms_cleared += 1
            self._next()

    def _bank(self):
        room = self.room
        if not getattr(room, "banked", False):
            room.banked = True
            for key in ("crossfire kills", "turncoats", "cores", "slams", "mended"):
                self.stats[key] += room.stats[key]
            self.stats["overrides"] += room.rewrites
            self.stats["flawless rooms"] += 1 if room.flawless else 0
            self.stats["best combo"] = max(self.stats["best combo"], room.best_combo)
            self.kinds += room.kinds_killed
            self.floor_damage += room.damage_taken
        self.score += self.room.score
        self.kills += self.room.kills
        self.room.score = 0
        self.room.kills = 0

    def _next(self):
        """Out of a room: the next room, or at the end of a floor an upgrade and the next floor. The
        run never stops for a menu: clearing a Brain Room shuts ARGUS down, it restores from a
        backup, and play goes straight on."""
        last = self.index == C.ROOMS_PER_FLOOR - 1
        if not last:
            self.index += 1
            self.room = self._make_room()
            self.room_number += 1
            return
        if self.floor_damage == 0:
            self.stats["flawless floors"] += 1
        if rooms.level(self.floor) == C.FLOORS:
            self._shutdown()
        self._install_upgrade()
        self._descend()

    def _shutdown(self):
        """The Brain Room is clear: ARGUS goes down, restores from a backup, and the clock restarts."""
        self.stats["shutdowns"] += 1
        if self.upload < 0.4:
            self.stats["early shutdowns"] += 1
        self.descents += 1
        self.upload_from = self.time
        self.announced.clear()
        self.player.hp = self.player.stats.max_hp
        self.notices.append(("SHUTDOWN COMPLETE", f"ARGUS is restoring from backup {self.descents}. Keep going."))

    def _install_upgrade(self):
        """End of a floor: one upgrade, installed on the spot (no menu)."""
        offers = upgrades.offer(self.rng, self.taken, self.player)
        if offers:
            up = offers[0]
            up.apply(self.player)
            self.taken.append(up.key)
            self.notices.append(("UPGRADE INSTALLED", f"{up.name}: {up.text}"))

    def _descend(self):
        self.floor_damage = 0
        self.floor += 1
        self.index = 0
        self.room = self._make_room()
        self.room_number += 1
        self.state = "room"

    def progress(self) -> dict:
        """Everything this run has achieved so far, for achievements and the end-of-run rewards."""
        stats = dict(self.stats)
        room = self.room
        if not getattr(room, "banked", False):                     # the room still being played
            for key in ("crossfire kills", "turncoats", "cores", "slams", "mended"):
                stats[key] = stats.get(key, 0) + room.stats[key]
            stats["overrides"] = stats.get("overrides", 0) + room.rewrites
            if room.state != "fight" and room.flawless:
                stats["flawless rooms"] = stats.get("flawless rooms", 0) + 1
            stats["best combo"] = max(stats.get("best combo", 0), room.best_combo)
        kinds = self.kinds + (Counter() if getattr(room, "banked", False) else room.kinds_killed)
        for kind, n in kinds.items():
            stats[f"kill:{kind}"] = n
        stats["kinds"] = sorted(kinds)
        stats["rooms"] = self.cleared_rooms
        stats["floor"] = self.floor
        if self.state == "lost":
            stats["escaped"] = 1
        return stats
