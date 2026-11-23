"""Make the README screenshots from the real game, the same pictures every time.

    python -m tools.shots                 all of them
    python -m tools.shots sync boss       only these (names without .png)

Each picture is a fixed seed: the game plays itself (the bot from game/bot.py) up to a moment, found
by watching the simulation, and the game's own drawing code draws that frame. Nothing is written to
saves/. Writes docs/images/*.png, all 1280 x 720 except rooms.png (1280 x 481):

    title  story  intro-1  intro-2  intro-3  sync  crossfire  fight  cleared  network  rooms
    director  argus  rewritten  boss  boss-rewrite  lockdown  overrun
"""

import math
import os
import random
import sys
import time
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"          # no window, and the same 1280 x 720 screen everywhere
os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame  # noqa: E402

from game.app import Game  # noqa: E402
from game.bot import bot, make_bot  # noqa: E402
from game.config import COLS, ROWS, WIDTH, HEIGHT, TILE  # noqa: E402
from game.scenes import INTRO, OVER, PLAY, STORY  # noqa: E402
from game.ui import hud, style  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "images"
DT = 1 / 60
HOLD_FIRE = make_bot(rewrites=False)                 # the bot, keeping its override charge
WEAK = make_bot(reaction=0.8, dodge=1.5, wobble=1.0, dash_bullets=False)    # the average bot (autoplay)


# --- driving the game ------------------------------------------------------------------------
def play(seed: int, floor: int = 1, room: int = 1, player=bot) -> Game:
    """A game already in a room (no title, intro or story), played by a bot."""
    g = Game(seed=seed, start_floor=floor, start_room=room, save_path=None, sound=False)
    g.new_run()
    g.scenes.change(PLAY)
    g.scripted = player
    g.moved = True                                  # keeps the first room's controls hint hidden
    return g


def step(g: Game, seconds: float = DT):
    """Play on without drawing (drawing is most of a frame's cost). Does what Game.tick does
    besides drawing, and lets a new room fade in as it would on screen."""
    for _ in range(max(1, round(seconds / DT))):
        g.clock_time += DT
        if g.toasts:
            g.toasts[0][2] += DT
            if g.toasts[0][2] > hud.TOAST_TIME:
                g.toasts.pop(0)
        g.scenes.update(DT)
        g.fade = min(1.0, g.fade + 1 / 20)


def until(g: Game, moment, limit: float = 60.0) -> bool:
    """Play until moment(g) is true. False if it had not happened after `limit` seconds."""
    for _ in range(round(limit / DT)):
        if moment(g):
            return True
        step(g)
    return moment(g)


def bright(g: Game, wave: float) -> bool:
    """A pulsing prompt (it pulses with sin(clock * wave)) is near its brightest."""
    return math.sin(g.clock_time * wave) > 0.9


def save(g: Game, name: str, frames: int = 2):
    """Play the last few frames on screen (wreckage and shoved racks settle), then save the screen."""
    for _ in range(frames):
        g.tick(DT)
    write(g.screen, name)


def save_still(g: Game, name: str):
    """Draw the frame as it stands (after changing what the screen shows) and save it."""
    g.scenes.current.draw(g, g.screen)
    write(g.screen, name)


def write(surface, name: str):
    pygame.image.save(surface, str(OUT / f"{name}.png"))


# --- what to look for -------------------------------------------------------------------------
def argus_side(room) -> list:
    return [e for e in room.enemies if e.side == "argus"]


def on_screen(e, margin: float = 1.5) -> bool:
    """Clear of the edges, and below the top bar and the subtitle."""
    return margin < e.pos[0] < COLS - margin and 3.0 < e.pos[1] < ROWS - margin


def incoming(room) -> bool:
    """One of ARGUS's bullets is about to hit one of its own robots (not the one that fired it)."""
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
    """A real fight: several robots after you, one winding up an attack, bullets in the air."""
    alert = [e for e in argus_side(room) if e.alert and on_screen(e, 1.0)]
    return (len(alert) >= robots and any(e.windup > 0.5 for e in alert)
            and any(b.side == "argus" for b in room.bullets))


def turned(room):
    """An overridden robot, if there is one."""
    return next((e for e in room.enemies if e.side == "player"), None)


def fighting_for_you(room) -> bool:
    """An overridden robot attacking, long enough after the override for ARGUS to have had its say."""
    e = turned(room)
    return (e is not None and room.time - room.last_rewrite[1] > 2.4 and on_screen(e)
            and (e.windup > 0.4 or any(b.owner is e for b in room.bullets)))


def thinking(room) -> list:
    """Alert robots in view with their decision scores, the best one to hover first: one you could
    override, with nothing else where its card goes, and the most options scored."""
    found = [e for e in argus_side(room) if e.alert and e.scores and on_screen(e, 3.0) and 9 < e.pos[0] < 22]
    return sorted(found, key=lambda e: (room.rewritable(e) != "", not room_for_card(room, e), -len(e.scores)))


def room_for_card(room, e) -> bool:
    """No other robot where the debugger puts a hovered robot's card (to its right, about 7 x 4 tiles)."""
    return not any(o is not e and 0 < o.pos[0] - e.pos[0] < 8.5 and abs(o.pos[1] - e.pos[1]) < 2.5
                   for o in room.enemies)


def hover(g: Game, e):
    """Point the crosshair just beside a robot (close enough to hover it, without covering it)."""
    g.aim_px = ((e.pos[0] + 0.6) * TILE, (e.pos[1] + 0.6) * TILE)


# --- the pictures -----------------------------------------------------------------------------
def title():
    """The title over the live demo: the bot against three or more alert robots, PRESS ENTER lit."""
    g = Game(seed=5, save_path=None, sound=False)

    def fighting(g):
        demo = g.demo.room
        return demo.time > 2 and len([e for e in argus_side(demo) if e.alert]) >= 3 and bright(g, 4)

    found = until(g, fighting, 40)
    save(g, "title", 1)
    return found


def story():
    """The one story card, its last line faded in and ENTER lit."""
    g = Game(seed=1, save_path=None, sound=False)
    g.scenes.change(STORY)
    step(g, 2.0)
    until(g, lambda g: bright(g, 4), 2)
    save(g, "story", 1)


def intro():
    """The film: NIGHT SHIFT (0-6 s), THE CHANGE, SINGULARITY (10.5-17 s), ARGUS (17-22 s)."""
    g = Game(seed=24, save_path=None, sound=False)          # its robots stand where the camera looks
    step(g, 6.1)                        # a moment on the title first, so the camera's slow sway
    g.scenes.change(INTRO)              # is wide open (both doors in view) at 03:12
    step(g, 5.8)
    save(g, "intro-1", 1)
    until(g, lambda g: g.cinematic.name == "SINGULARITY" and g.cinematic.shot_t > 5.4, 20)
    save(g, "intro-2", 1)
    until(g, lambda g: g.cinematic.name == "ARGUS" and g.cinematic.shot_t > 4.0, 20)
    save(g, "intro-3", 1)


def sync():
    """The debugger: time slows, every robot shows its intent, the hovered one its scored options."""
    g = play(39, 3, 2, HOLD_FIRE)
    room = g.run.room

    def readable(g):
        focus = thinking(room)
        return (room.time > 4 and busy(room, 4) and focus and room.rewritable(focus[0]) == ""
                and room_for_card(room, focus[0]) and bright(g, 10))

    found = until(g, readable, 30)
    g.syncing = True                                # (the scripted game never holds right click itself)
    if thinking(room):
        hover(g, thinking(room)[0])
    save_still(g, "sync")
    return found


def crossfire():
    """A Sentry's bullets hit a fellow robot (the next one still on its way) while ARGUS's opening
    line is up, with the CROSSFIRE tag clear of your crosshair and the subtitle."""
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
    """A game played from floor 2 into its second room, where ARGUS has studied you for a room
    (its line says what it changed)."""
    g = play(seed, 2, 1)
    until(g, lambda g: g.run.index == 1, 60)
    return g


def fight():
    """Mid-fight with four robots, ARGUS's line on the subtitle bar."""
    g = second_room(31)
    room = g.run.room
    found = until(g, lambda g: 3.0 < g.argus_time < 5.5 and busy(room, 4), 8)
    save(g, "fight", 1)
    return found


def cleared():
    """The last robot down: wreckage where they fell, the exit sliding open, the lamps green."""
    g = play(3, 1, 4)
    room = g.run.room
    found = until(g, lambda g: room.state != "fight", 60)
    step(g, 0.9)
    save(g, "cleared", 2)
    return found


def network():
    """A sighting passed robot to robot along ARGUS's network (the gold links), with the bottom
    right corner kept clear of robots."""
    g = second_room(9)

    def sighting(g):
        panel = pygame.Rect(WIDTH - 262, HEIGHT - 194, 250, 150)     # a corner kept clear of robots
        clear = not any(panel.collidepoint(e.pos[0] * TILE, e.pos[1] * TILE) for e in g.run.room.enemies)
        return clear and any(link[4] < 0.3 for link in g.fx.links)

    found = until(g, sighting, 20)
    save(g, "network", 1)
    return found


def director():
    """AI View: the model panel, every robot's card, and the heat map of the hovered robot."""
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
    """ARGUS speaks as you enter a room: here, the room that introduces the BULWARK."""
    g = play(5, 4, 2)
    step(g, 3.0)
    save(g, "argus", 1)


def rewritten():
    """One of ARGUS's robots, overridden by the bot, fighting on your side (cyan)."""
    g = play(8, 2, 3)
    found = until(g, lambda g: fighting_for_you(g.run.room), 60)
    save(g, "rewritten", 1)
    return found


def boss():
    """ARGUS's core (floor 9, room 4): winding up its sweeping laser, then one of your overrides."""
    g = play(5, 9, 4)
    room = g.run.room
    found = until(g, lambda g: room.time > 3 and room.boss.state == "WINDUP" and room.boss.attack == "sweep"
                  and room.boss.windup > 0.6, 60)
    save(g, "boss", 1)
    rewrote = until(g, lambda g: fighting_for_you(room), 60)
    save(g, "boss-rewrite", 1)
    return found and rewrote


def lockdown():
    """The last room of floor 1: two waves. The second warps in."""
    g = play(4, 1, 4)
    found = until(g, lambda g: g.run.room.wave == 1, 90)
    step(g, 0.45)
    save(g, "lockdown", 1)
    return found


def overrun():
    """Game over: the average bot, started on floor 3, is overrun (the OVER screen a second later)."""
    g = play(2, 3, 2, WEAK)
    found = until(g, lambda g: g.scenes.current is OVER, 240)
    step(g, 1.0)
    save(g, "overrun", 1)
    return found


def rooms():
    """Six random rooms from floors 4-14 in a 3 x 2 grid, each drawn (the room only, no HUD) once all
    its robots have noticed you, so no sight cones hide the floor. Each has a different layout, and
    no colour scheme shows more than twice."""
    rng = random.Random(14)
    cell_w, cell_h = WIDTH // 3, HEIGHT // 3                       # 426 x 240, with 1 px between
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
