import math
import os
import random
import sys
import time
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame  # noqa: E402

from game.app import Game  # noqa: E402
from game.bot import bot, make_bot  # noqa: E402
from game.config import COLS, ROWS, WIDTH, HEIGHT, TILE  # noqa: E402
from game.scenes import INTRO, OVER, PLAY, STORY  # noqa: E402
from game.ui import hud, style  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "images"
DT = 1 / 60
HOLD_FIRE = make_bot(rewrites=False)
WEAK = make_bot(reaction=0.8, dodge=1.5, wobble=1.0, dash_bullets=False)


def play(seed: int, floor: int = 1, room: int = 1, player=bot) -> Game:
    g = Game(seed=seed, start_floor=floor, start_room=room, save_path=None, sound=False)
    g.new_run()
    g.scenes.change(PLAY)
    g.scripted = player
    g.moved = True
    return g


def step(g: Game, seconds: float = DT):
    for _ in range(max(1, round(seconds / DT))):
        g.clock_time += DT
        if g.toasts:
            g.toasts[0][2] += DT
            if g.toasts[0][2] > hud.TOAST_TIME:
                g.toasts.pop(0)
        g.scenes.update(DT)
        g.fade = min(1.0, g.fade + 1 / 20)


def until(g: Game, moment, limit: float = 60.0) -> bool:
    for _ in range(round(limit / DT)):
        if moment(g):
            return True
        step(g)
    return moment(g)


def bright(g: Game, wave: float) -> bool:
    return math.sin(g.clock_time * wave) > 0.9


def save(g: Game, name: str, frames: int = 2):
    for _ in range(frames):
        g.tick(DT)
    write(g.screen, name)


def save_still(g: Game, name: str):
    g.scenes.current.draw(g, g.screen)
    write(g.screen, name)


def write(surface, name: str):
    pygame.image.save(surface, str(OUT / f"{name}.png"))


def argus_side(room) -> list:
    return [e for e in room.enemies if e.side == "argus"]


def on_screen(e, margin: float = 1.5) -> bool:
    return margin < e.pos[0] < COLS - margin and 3.0 < e.pos[1] < ROWS - margin


def incoming(room) -> bool:
    for b in room.bullets:
        if b.side != "argus":
            continue
        speed = math.hypot(*b.vel)
        for e in argus_side(room):
            if e is b.owner:
                continue
            dx, dy = e.pos[0] - b.pos[0], e.pos[1] - b.pos[1]
            d = math.hypot(dx, dy)
            if 0.4 < d < 3.0 and (dx * b.vel[0] + dy * b.vel[1]) / (d * speed) > 0.9:
                return True
    return False


def busy(room, robots: int = 3) -> bool:
    alert = [e for e in argus_side(room) if e.alert and on_screen(e, 1.0)]
    return (len(alert) >= robots and any(e.windup > 0.5 for e in alert)
            and any(b.side == "argus" for b in room.bullets))


def turned(room):
    return next((e for e in room.enemies if e.side == "player"), None)


def fighting_for_you(room) -> bool:
    e = turned(room)
    return (e is not None and room.time - room.last_rewrite[1] > 2.4 and on_screen(e)
            and (e.windup > 0.4 or any(b.owner is e for b in room.bullets)))


def thinking(room) -> list:
    found = [e for e in argus_side(room) if e.alert and e.scores and on_screen(e, 3.0) and 9 < e.pos[0] < 22]
    return sorted(found, key=lambda e: (room.rewritable(e) != "", not room_for_card(room, e), -len(e.scores)))


def room_for_card(room, e) -> bool:
    return not any(o is not e and 0 < o.pos[0] - e.pos[0] < 8.5 and abs(o.pos[1] - e.pos[1]) < 2.5
                   for o in room.enemies)


def hover(g: Game, e):
    g.aim_px = ((e.pos[0] + 0.6) * TILE, (e.pos[1] + 0.6) * TILE)


def title():
    g = Game(seed=5, save_path=None, sound=False)

    def fighting(g):
        demo = g.demo.room
        return demo.time > 2 and len([e for e in argus_side(demo) if e.alert]) >= 3 and bright(g, 4)

    found = until(g, fighting, 40)
    save(g, "title", 1)
    return found


def story():
    g = Game(seed=1, save_path=None, sound=False)
    g.scenes.change(STORY)
    step(g, 2.0)
    until(g, lambda g: bright(g, 4), 2)
    save(g, "story", 1)


def intro():
    g = Game(seed=24, save_path=None, sound=False)
    step(g, 6.1)
    g.scenes.change(INTRO)
    step(g, 5.8)
    save(g, "intro-1", 1)
    until(g, lambda g: g.cinematic.name == "SINGULARITY" and g.cinematic.shot_t > 5.4, 20)
    save(g, "intro-2", 1)
    until(g, lambda g: g.cinematic.name == "ARGUS" and g.cinematic.shot_t > 4.0, 20)
    save(g, "intro-3", 1)


def sync():
    g = play(39, 3, 2, HOLD_FIRE)
    room = g.run.room

    def readable(g):
        focus = thinking(room)
        return (room.time > 4 and busy(room, 4) and focus and room.rewritable(focus[0]) == ""
                and room_for_card(room, focus[0]) and bright(g, 10))

    found = until(g, readable, 30)
    g.syncing = True
    if thinking(room):
        hover(g, thinking(room)[0])
    save_still(g, "sync")
    return found


def crossfire():
    g = play(7, 1, 4, HOLD_FIRE)
    room = g.run.room

    def hit(g):
        tags = [p for p in g.fx.particles if p.kind == "text" and p.text == "CROSSFIRE"]
        return (1.2 < g.argus_time < 5.8 and tags and incoming(room)
                and all(p.y > 130 and math.dist((p.x, p.y), g.aim_px) > 90 for p in tags))

    found = until(g, hit, 10)
    save(g, "crossfire", 1)
    return found


def second_room(seed: int) -> Game:
    g = play(seed, 2, 1)
    until(g, lambda g: g.run.index == 1, 60)
    return g


def fight():
    g = second_room(31)
    room = g.run.room
    found = until(g, lambda g: 3.0 < g.argus_time < 5.5 and busy(room, 4), 8)
    save(g, "fight", 1)
    return found


def cleared():
    g = play(3, 1, 4)
    room = g.run.room
    found = until(g, lambda g: room.state != "fight", 60)
    step(g, 0.9)
    save(g, "cleared", 2)
    return found


def network():
    g = second_room(9)

    def sighting(g):
        panel = pygame.Rect(WIDTH - 262, HEIGHT - 194, 250, 150)
        clear = not any(panel.collidepoint(e.pos[0] * TILE, e.pos[1] * TILE) for e in g.run.room.enemies)
        return clear and any(link[4] < 0.3 for link in g.fx.links)

    found = until(g, sighting, 20)
    save(g, "network", 1)
    return found


def director():
    g = second_room(11)
    room = g.run.room

    def mapped(g):
        return [e for e in thinking(room) if e.uid in room.tactics.debug and len(room.tactics.debug[e.uid][1]) > 30]

    found = until(g, lambda g: room.time > 4 and mapped(g), 30)
    g.xray = True
    if mapped(g):
        hover(g, mapped(g)[0])
    save_still(g, "director")
    return found


def argus():
    g = play(5, 4, 2)
    step(g, 3.0)
    save(g, "argus", 1)


def rewritten():
    g = play(8, 2, 3)
    found = until(g, lambda g: fighting_for_you(g.run.room), 60)
    save(g, "rewritten", 1)
    return found


def boss():
    g = play(5, 9, 4)
    room = g.run.room
    found = until(g, lambda g: room.time > 3 and room.boss.state == "WINDUP" and room.boss.attack == "sweep"
                  and room.boss.windup > 0.6, 60)
    save(g, "boss", 1)
    rewrote = until(g, lambda g: fighting_for_you(room), 60)
    save(g, "boss-rewrite", 1)
    return found and rewrote


def lockdown():
    g = play(4, 1, 4)
    found = until(g, lambda g: g.run.room.wave == 1, 90)
    step(g, 0.45)
    save(g, "lockdown", 1)
    return found


def overrun():
    g = play(2, 3, 2, WEAK)
    found = until(g, lambda g: g.scenes.current is OVER, 240)
    step(g, 1.0)
    save(g, "overrun", 1)
    return found


def rooms():
    rng = random.Random(14)
    cell_w, cell_h = WIDTH // 3, HEIGHT // 3
    sheet = pygame.Surface((cell_w * 3 + 2, cell_h * 2 + 1))
    sheet.fill(style.OUTLINE)
    frame = pygame.Surface((WIDTH, HEIGHT))
    layouts, themes = set(), []
    while len(layouts) < 6:
        g = play(rng.randrange(10 ** 6), rng.randint(4, 14), rng.randint(1, 3))
        room = g.run.room
        if room.layout.style in layouts or themes.count(room.plan.theme) == 2:
            continue
        i = len(layouts)
        layouts.add(room.layout.style)
        themes.append(room.plan.theme)
        until(g, lambda g: room.time > 1.5 and all(e.alert for e in argus_side(room)), 8)
        g.renderer.draw(frame, room, g.fx, g.clock_time)
        cell = pygame.transform.smoothscale(frame, (cell_w, cell_h))
        sheet.blit(cell, ((i % 3) * (cell_w + 1), (i // 3) * (cell_h + 1)))
    write(sheet, "rooms")


SHOTS = {"title": title, "story": story, "intro": intro, "sync": sync, "crossfire": crossfire,
         "fight": fight, "cleared": cleared, "network": network, "rooms": rooms, "director": director,
         "argus": argus, "rewritten": rewritten, "boss": boss, "lockdown": lockdown, "overrun": overrun}
ALIASES = {"intro-1": "intro", "intro-2": "intro", "intro-3": "intro", "boss-rewrite": "boss"}


def main(names: list[str]):
    pygame.init()
    pygame.display.set_mode((WIDTH, HEIGHT))
    wanted = [ALIASES.get(n.removesuffix(".png"), n.removesuffix(".png")) for n in names] or list(SHOTS)
    unknown = [n for n in wanted if n not in SHOTS]
    if unknown:
        sys.exit(f"no picture called {', '.join(unknown)}; choose from: {' '.join(SHOTS)}")
    start = time.perf_counter()
    for name in dict.fromkeys(wanted):
        t = time.perf_counter()
        found = SHOTS[name]()
        note = "" if found is not False else "   (moment not reached: saved the last frame instead)"
        print(f"{name:<10} {time.perf_counter() - t:5.1f} s{note}")
    print(f"done in {time.perf_counter() - start:.1f} s: {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
