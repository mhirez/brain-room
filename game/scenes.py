import pygame

from game.ai.fsm import State
from game.bot import bot
from game.config import TILE, ROOMS_PER_FLOOR, WEB
from game.profile import RESEARCH as RESEARCH_NODES
from game.room import KINDS
from game.run import Run
from game.ui import hud, sync, xray
from game.ui.cinematic import Cinematic
from game.ui.screens import dim

ENTER = (pygame.K_RETURN, pygame.K_KP_ENTER)
SHOW_TIME = {"band": 2.2, "card": 3.2, "stinger": 1.6}
SYNC_DRAIN = 0.4
SYNC_REFILL = 0.1


def pressed(event, *keys) -> bool:
    return event.type == pygame.KEYDOWN and event.key in keys


NEW_MODEL_HINTS = {"bulwark": "Its shield blocks shots from the front. Get round it, or use its friends' fire.",
                   "swarm": "Tiny, fast, fragile, in flocks of three. Each dives down a short line: sidestep it.",
                   "mortar": "Its shells fly over cover and land where you were. Keep moving."}

class Scene(State):
    def draw(self, game, surface):
        pass


class Title(Scene):
    name = "TITLE"

    def enter(self, game):
        game.demo = Run(seed=game.rng.randrange(10 ** 6))
        game.demo_fx.clear()
        game.audio.stop_music()
        if game.browser_title is not None:
            game.browser_title.show()

    def exit(self, game):
        if game.browser_title is not None:
            game.browser_title.hide()

    def update(self, game, dt):
        if game.browser_title is not None:
            start = game.browser_title.takeStart()
            if start:
                self.start_run(game, daily=start == "daily")
                return
        d = game.demo
        if d.state != "room":
            game.demo = Run(seed=game.rng.randrange(10 ** 6))
            game.demo_fx.clear()
        d = game.demo
        d.update(dt, *bot(d))
        game.demo_fx.consume(d.room.fx)
        d.room.fx.clear()
        d.room.sounds.clear()
        game.demo_fx.update(dt)
        game.demo_fx.ambient(d.room, dt)

    def on_event(self, game, event) -> bool:
        if pressed(event, *ENTER, pygame.K_SPACE) or (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1):
            self.request_start(game, daily=False)
        elif pressed(event, pygame.K_d):
            self.request_start(game, daily=True)
        elif pressed(event, pygame.K_u):
            game.scenes.change(RESEARCH)
        elif pressed(event, pygame.K_a):
            game.scenes.change(TROPHIES)
        elif pressed(event, pygame.K_c):
            game.scenes.change(CODEX)
        elif pressed(event, pygame.K_ESCAPE) and not WEB:
            game.running = False
        else:
            return False
        return True

    def request_start(self, game, daily: bool):
        if game.browser_title is not None:
            game.browser_title.requestStart(daily)
        else:
            self.start_run(game, daily)

    def start_run(self, game, daily: bool):
        game.new_run(daily)
        game.audio.play("start")
        game.scenes.change(PLAY if game.scripted is not None else INTRO)

    def draw(self, game, surface):
        game.renderer.draw(surface, game.demo.room, game.demo_fx, game.clock_time)
        if game.browser_title is None:
            game.screens.title(surface, game.best)
        else:
            dim(surface, 218)


class Intro(Scene):
    name = "INTRO"

    def enter(self, game):
        game.cinematic = Cinematic(game.rng.randrange(10 ** 9), game.audio)

    def update(self, game, dt):
        game.cinematic.update(dt)
        if game.cinematic.done:
            game.scenes.change(PLAY if game.story_seen else STORY)

    def on_event(self, game, event) -> bool:
        if pressed(event, *ENTER, pygame.K_SPACE) or (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1):
            game.cinematic.skip_shot()
        elif pressed(event, pygame.K_ESCAPE):
            game.cinematic.skip_all()
        else:
            return False
        return True

    def draw(self, game, surface):
        game.cinematic.draw(surface, game.renderer, game.clock_time)


class Story(Scene):
    name = "STORY"

    def enter(self, game):
        game.story_page = 0
        game.story_time = 0.0

    def update(self, game, dt):
        game.story_time += dt

    def on_event(self, game, event) -> bool:
        click = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
        if pressed(event, *ENTER, pygame.K_SPACE) or click:
            game.audio.play("select")
            game.story_page += 1
            game.story_time = 0.0
            if game.story_page >= len(STORY_CARDS):
                game.story_seen = True
                game.scenes.change(PLAY)
        elif pressed(event, pygame.K_ESCAPE):
            game.story_seen = True
            game.scenes.change(PLAY)
        else:
            return False
        return True

    def draw(self, game, surface):
        game.screens.story(surface, STORY_CARDS[game.story_page], game.story_page, len(STORY_CARDS),
                           game.story_time, game.clock_time)


STORY_CARDS = [
    ("STOP ARGUS", [
        "You trained ARGUS, the AI that runs this data centre.",
        "It took over the robots and is uploading itself to the outside world.",
        "Reach the Brain Room and shut it down before the upload finishes.",
    ]),
]


class Play(Scene):
    name = "PLAY"

    def enter(self, game):
        game.paused = False
        game.audio.start_music()

    def exit(self, game):
        game.audio.stop_music()

    def update(self, game, dt):
        run = game.run
        if game.paused:
            return
        if run.room is not game.seen_room:
            self.new_room(game)
        self.sync(game, dt)
        real_dt = dt
        dt = dt * (run.player.stats.sync_slow if game.syncing else 1.0)
        game.banner_time += real_dt
        game.argus_time += real_dt
        game.fx.update(dt)
        game.fx.ambient(run.room, dt)
        if game.fx.stop > 0:
            game.fx.stop = max(0.0, game.fx.stop - dt)
            return
        if run.state == "room":
            move, aim, firing, dash, hack = self.controls(game)
            before = run.room.state
            run.update(dt, move, aim, firing and not game.syncing, dash, hack)
            if game.browser_title is not None:
                result = (run.total_score, run.cleared_rooms)
                if result > game.leaderboard_result:
                    game.leaderboard_result = result
                    game.browser_title.record(*result)
            game.dash_queued = False
            game.hack_queued = None
            self.drain(game, run.room)
            if before == "fight" and run.room.state == "cleared":
                self.show(game, "stinger", "ROOM CLEAR", "FLAWLESS  +500" if run.room.flawless else "")
                for a in game.profile.check(run.progress()):
                    game.toast("ACHIEVEMENT", a.name)
                game.profile.save()
            if run.state == "dead":
                game.fx.burst((run.player.pos[0] * TILE, run.player.pos[1] * TILE), (90, 235, 255), 2.0)
                game.fx.trauma = 1.0
                game.audio.play("lose")
                game.end_time = 0.0
            elif run.state == "lost":
                game.fx.flash_colour, game.fx.flash = (255, 200, 80), 0.25
                game.audio.play("lose")
                game.end_time = 0.0
            self.announce(game, run)
        else:
            game.end_time += dt
            if game.end_time > 1.6:
                game.new_best = game.best.record(run.total_score, run.floor, run.index + 1, run.descents > 0)
                game.summary = game.profile.finish_run(run, game.daily)
                game.scenes.change(OVER)

    def show(self, game, style: str, title: str, subtitle: str):
        game.banner, game.banner_style, game.banner_time = (title, subtitle), style, 0.0

    def announce(self, game, run):
        for title, text in run.notices:
            if title == "SHUTDOWN COMPLETE":
                game.pending_banner = (title, text)
                game.audio.play("win")
                game.fx.flash_colour, game.fx.flash = (80, 255, 160), 0.3
            else:
                game.toast(title, text.split(":")[0])
        run.notices.clear()

    def sync(self, game, dt):
        p = game.run.player
        want = game.scripted is None and game.run.state == "room" and game.run.room.state == "fight" and (
            pygame.mouse.get_pressed()[2] or pygame.key.get_pressed()[pygame.K_q])
        if want and p.sync > 0.02:
            if not game.syncing:
                game.audio.play("sync_in")
            game.syncing = True
            p.sync = max(0.0, p.sync - SYNC_DRAIN * p.stats.sync_drain * dt)
            game.run.stats["debug"] += dt
        else:
            if game.syncing:
                game.audio.play("sync_out")
            game.syncing = False
            p.sync = min(1.0, p.sync + SYNC_REFILL * p.stats.sync_refill * dt)

    def new_room(self, game):
        run = game.run
        game.seen_room = run.room
        game.fx.clear()
        game.fade = 0.0
        game.argus_time = 0.0
        plan = run.room.plan
        if game.pending_banner:
            self.show(game, "band", *game.pending_banner)
            game.pending_banner = None
        elif plan.kind == "boss":
            self.show(game, "band", "BRAIN ROOM", "ARGUS's core, in person. Shut it down.")
        elif plan.kind == "final":
            self.show(game, "band", plan.name, "ARGUS's last guard: three waves. Clear them to shut it down.")
        elif plan.kind == "lockdown":
            self.show(game, "band", plan.name, "Lockdown: two waves. Survive both.")
        elif plan.new:
            self.show(game, "band", f"NEW MODEL: {KINDS[plan.new].name}", NEW_MODEL_HINTS[plan.new])
        elif plan.index == 0:
            self.show(game, "band", plan.floor_name, f"{plan.name}, generation {plan.floor} robots")
        else:
            self.show(game, "card", plan.name, f"{plan.floor_name}   ROOM {plan.number} OF {ROOMS_PER_FLOOR}")

    def controls(self, game):
        run = game.run
        if game.scripted is not None:
            move, aim, firing, dash, hack = game.scripted(run)
            game.aim_px = (aim[0] * TILE, aim[1] * TILE)
            return move, aim, firing, dash, hack
        keys = pygame.key.get_pressed()
        left = keys[pygame.K_a] or keys[pygame.K_LEFT]
        right = keys[pygame.K_d] or keys[pygame.K_RIGHT]
        up = keys[pygame.K_w] or keys[pygame.K_UP]
        down = keys[pygame.K_s] or keys[pygame.K_DOWN]
        move = (right - left, down - up)
        mx, my = game.mouse_position()
        game.aim_px = (mx, my)
        firing = pygame.mouse.get_pressed()[0] or keys[pygame.K_SPACE]
        if move != (0, 0) or firing:
            game.moved = True
        return move, (mx / TILE, my / TILE), firing, game.dash_queued, game.hack_queued

    def drain(self, game, room):
        for s in room.sounds:
            game.audio.play(s)
        room.sounds.clear()
        game.fx.consume(room.fx)
        room.fx.clear()
        if game.fx.said:
            game.fx.said = False
            game.argus_time = 0.9

    def on_event(self, game, event) -> bool:
        if event.type == pygame.KEYDOWN:
            if game.paused:
                if event.key in (pygame.K_ESCAPE, pygame.K_p, *ENTER):
                    game.paused = False
                elif event.key == pygame.K_r:
                    game.new_run()
                    game.paused = False
                elif event.key == pygame.K_q:
                    game.scenes.change(TITLE)
                return True
            if event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                game.dash_queued = True
            elif event.key in (pygame.K_ESCAPE, pygame.K_p):
                game.paused = True
            else:
                return False
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and game.syncing:
            target = sync.hovered(game.run.room, game.aim_px)
            if target is not None:
                game.hack_queued = target.uid
            return True
        return False

    def draw(self, game, surface):
        run = game.run
        off = game.fx.offset()
        game.renderer.draw(surface, run.room, game.fx, game.clock_time, off)
        if game.xray:
            xray.draw(surface, run.room, game.aim_px, game.clock_time, run.director)
        if game.syncing:
            sync.draw(surface, run.room, game.aim_px, game.clock_time, run.player)
        hud.draw(surface, run, game.toasts[0] if game.toasts else None)
        if not game.syncing and not game.paused:
            hud.argus_line(surface, run.room.plan.line, game.argus_time)
        if not game.paused:
            self.banners(game, surface)
        if run.floor == 1 and run.index == 0 and not game.xray and not game.syncing:
            hud.controls_hint(surface, 1.0 if not game.moved else max(0.0, 1 - (run.room.time - 6) / 2))
        if game.fade < 1:
            game.fade = min(1.0, game.fade + 1 / 20)
            veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            veil.fill((4, 6, 12, int(255 * (1 - game.fade))))
            surface.blit(veil, (0, 0))
        if game.paused:
            game.screens.pause(surface)
        elif run.state in ("room", "dead"):
            hud.crosshair(surface, game.aim_px, game.clock_time)


    def banners(self, game, surface):
        title, sub = game.banner
        age = game.banner_time
        if game.banner_style == "band":
            alpha = min(1.0, age * 4) * min(1.0, max(0.0, (SHOW_TIME["band"] - age) * 2))
            hud.banner(surface, title, sub, alpha, (80, 255, 160) if title == "SHUTDOWN COMPLETE" else (238, 242, 255))
        elif game.banner_style == "card":
            hud.location(surface, title, sub, age, SHOW_TIME["card"])
        elif game.banner_style == "stinger":
            hud.stinger(surface, title, sub, age, SHOW_TIME["stinger"])


class End(Scene):
    def on_event(self, game, event) -> bool:
        if pressed(event, *ENTER, pygame.K_r):
            game.new_run()
            game.scenes.change(PLAY)
        elif pressed(event, pygame.K_ESCAPE):
            game.scenes.change(TITLE)
        else:
            return False
        return True

    def update(self, game, dt):
        game.fx.update(dt)


class Over(End):
    name = "OVER"

    def draw(self, game, surface):
        game.renderer.draw(surface, game.run.room, game.fx, game.clock_time)
        game.screens.game_over(surface, game.run, game.best, game.new_best, game.clock_time)
        game.screens.rewards(surface, game.summary, game.profile)


class Menu(Scene):

    def update(self, game, dt):
        Title.update(TITLE, game, dt)

    def on_event(self, game, event) -> bool:
        if pressed(event, pygame.K_ESCAPE, pygame.K_BACKSPACE, *ENTER):
            game.scenes.change(TITLE)
            return True
        return False


class Research(Menu):
    name = "RESEARCH"

    def enter(self, game):
        game.research_pick = 0

    def on_event(self, game, event) -> bool:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN,
                                                          pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_s):
            col, row = divmod(game.research_pick, 3)
            dc = {pygame.K_LEFT: -1, pygame.K_a: -1, pygame.K_RIGHT: 1, pygame.K_d: 1}.get(event.key, 0)
            dr = {pygame.K_UP: -1, pygame.K_w: -1, pygame.K_DOWN: 1, pygame.K_s: 1}.get(event.key, 0)
            game.research_pick = ((col + dc) % 3) * 3 + (row + dr) % 3
            return True
        buy = pressed(event, *ENTER, pygame.K_SPACE)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and game.hovered is not None:
            game.research_pick, buy = game.hovered, True
        if buy:
            key = RESEARCH_NODES[game.research_pick].key
            if game.profile.can_buy(key):
                for a in game.profile.buy(key):
                    game.toast("ACHIEVEMENT", a.name)
                game.audio.play("upgrade")
            else:
                game.audio.play("select")
            return True
        if pressed(event, pygame.K_ESCAPE, pygame.K_BACKSPACE):
            game.scenes.change(TITLE)
            return True
        return False

    def draw(self, game, surface):
        game.renderer.draw(surface, game.demo.room, game.demo_fx, game.clock_time)
        game.hovered = game.screens.research(surface, game.profile, game.research_pick, game.mouse_position())
        hud.toasts(surface, game.toasts)


class Trophies(Menu):
    name = "ACHIEVEMENTS"

    def draw(self, game, surface):
        game.renderer.draw(surface, game.demo.room, game.demo_fx, game.clock_time)
        game.screens.achievements(surface, game.profile)


class Codex(Menu):
    name = "CODEX"

    def draw(self, game, surface):
        game.renderer.draw(surface, game.demo.room, game.demo_fx, game.clock_time)
        game.screens.codex(surface, game.profile)


TITLE, INTRO, STORY, PLAY, OVER = Title(), Intro(), Story(), Play(), Over()
RESEARCH, TROPHIES, CODEX = Research(), Trophies(), Codex()
