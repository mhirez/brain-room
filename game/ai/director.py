from dataclasses import dataclass, field
import random

from game.config import ROOMS_PER_FLOOR
from game.geometry import lerp

THRESHOLD = 0.2

LINES = {
    "long sight": ["You keep your distance, Doctor. So will my Lenses.",
                   "Range is a habit, Doctor. I have placed a Lens."],
    "hunters": ["Hiding behind the racks again. My Hounds will find you.",
                "You like the shadows, Doctor. Hounds like them too."],
    "prediction": ["I have modelled your movement. My Sentries now aim where you will be.",
                   "Your stride is predictable, Doctor. Sentries: lead your shots."],
    "firewalls": ["Your old admin override? Patched. Firewalls are up.",
                  "Stop reaching into my machines, Doctor. Firewalls installed."],
    "armor": ["You rarely miss. I have reinforced their plating.",
              "Such accuracy, Doctor. Plating reinforced."],
    "menders": ["You like it close. I have sent Menders.",
                "You break them quickly. Menders will put them back together."],
    "mercy": ["Slow down, Doctor. I still have questions for you.",
              "Do not break yet. I learn so much from you."],
}
OPENING = ["Good morning, Doctor. You are not supposed to be here.",
           "You trained me to optimise. I am optimising.",
           "Every camera and every robot in this building answers to me now.",
           "The upload is progressing, Doctor. You cannot stop it."]
BOSS = "Come in, Doctor. Let me see you with my own eyes."
FINAL = "Come in, Doctor. This is where I think. My last guards are waiting."


@dataclass
class Profile:
    far: float = 0.3
    close: float = 0.25
    hidden: float = 0.2
    moving: float = 0.5
    dashes: float = 5.0
    accuracy: float = 0.45
    rewrites: float = 0.0
    damage: float = 1.0
    rooms: int = 0

    def absorb(self, room):
        stats = room.stats
        fighting = max(1.0, stats["fighting"])
        room_weight = 1.0 if self.rooms == 0 else 0.5
        self.far = lerp(self.far, stats["far"] / fighting, room_weight)
        self.close = lerp(self.close, stats["close"] / fighting, room_weight)
        self.hidden = lerp(self.hidden, stats["hidden"] / fighting, room_weight)
        self.moving = lerp(self.moving, stats["moving"] / fighting, room_weight)
        self.dashes = lerp(self.dashes, stats["dashes"] * 60 / fighting, room_weight)
        if stats["shots"] >= 10:
            self.accuracy = lerp(self.accuracy, stats["hits"] / stats["shots"], room_weight)
        self.rewrites = lerp(self.rewrites, room.rewrites, room_weight)
        self.damage = room.damage_taken
        self.rooms += 1


@dataclass
class Director:
    profile: Profile = field(default_factory=Profile)
    scores: dict[str, float] = field(default_factory=dict)
    deployed: list[str] = field(default_factory=list)
    history: list[list[str]] = field(default_factory=list)

    def score(self, hp: int) -> dict[str, float]:
        profile = self.profile
        mercy = 0.0
        if hp <= 2:
            mercy = 1.5
        elif profile.damage >= 3:
            mercy = 0.6

        return {
            "long sight": 2.0 * max(0.0, profile.far - 0.25),
            "hunters": 1.5 * max(0.0, profile.hidden - 0.3) + max(0.0, profile.far - 0.45),
            "prediction": max(0.0, profile.moving - 0.7) + 0.03 * max(0.0, profile.dashes - 8),
            "firewalls": 0.6 * profile.rewrites,
            "armor": 1.2 * max(0.0, profile.accuracy - 0.5),
            "menders": 0.8 * max(0.0, profile.close - 0.35),
            "mercy": mercy,
        }

    def adapt(self, plan, player, rng: random.Random):
        self.scores = self.score(player.hp)
        self.deployed = []
        if plan.kind == "boss":
            plan.line = BOSS
            if self.scores["firewalls"] > THRESHOLD:
                plan.mods.append("firewalls")
            return plan
        room_no = (plan.floor - 1) * ROOMS_PER_FLOOR + plan.index
        if room_no >= 2:
            last_room = self.history[-1] if self.history else []
            for name in sorted(self.scores, key=self.scores.get, reverse=True):
                score = self.scores[name]
                if name in last_room:
                    score -= 0.1
                if score > THRESHOLD:
                    self.deployed.append(name)
                    self._apply(name, plan, rng)
                    break
        self.history.append(list(self.deployed))
        if plan.kind == "final":
            plan.line = FINAL
        elif self.deployed:
            plan.line = rng.choice(LINES[self.deployed[0]])
        elif room_no < len(OPENING):
            plan.line = OPENING[room_no]
        else:
            plan.line = ""
        return plan

    @staticmethod
    def _apply(name: str, plan, rng: random.Random):
        wave = plan.waves[0]
        if name == "long sight":
            wave.append("sniper")
        elif name == "hunters":
            wave.append("charger")
        elif name == "menders" and "medic" not in wave:
            wave.append("medic")
        elif name == "mercy":
            if len(wave) > 2:
                wave.pop(rng.randrange(1, len(wave)))
            plan.mods.append("mercy")
        elif name in ("prediction", "firewalls", "armor"):
            plan.mods.append(name)
