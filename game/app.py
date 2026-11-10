from pathlib import Path
import os
import random
import time

import pygame

from game.config import WIDTH, HEIGHT, FPS, TITLE, WEB
from game.ai.fsm import StateMachine
from game.audio import Audio
from game.profile import PROFILE_PATH, Profile, daily_seed
from game.run import Run
from game.save import Best, DEFAULT_PATH
from game.scenes import TITLE as TITLE_SCENE, PLAY
from game.ui import hud, style
from game.ui.fx import FX
from game.ui.render import Renderer
from game.ui.screens import Screens


LOGO = Path(__file__).resolve().parent / "assets" / "logo.png"


def _browser_title():
    if WEB:
        import platform
        return getattr(platform.window, "brainRoomTitle", None)
    return None


def _icon() -> pygame.Surface:
    try:
        return pygame.image.load(str(LOGO))
    except (pygame.error, FileNotFoundError):
        pass
    icon = pygame.Surface((32, 32), pygame.SRCALPHA)
    pts = [(28, 16), (6, 5), (12, 16), (6, 27)]
    pygame.draw.polygon(icon, (14, 50, 64), pts)
    pygame.draw.polygon(icon, (90, 235, 255), pts, 3)
    return icon


class Game:
    def __init__(self, seed: int | None = None, start_floor: int = 1, start_room: int = 1, xray: bool = False,
                 save_path: Path | None = DEFAULT_PATH, sound: bool = True):
        pygame.init()
        style.reset()
        pygame.display.set_caption(TITLE)
        pygame.display.set_icon(_icon())
        flags = 0 if WEB or os.environ.get("SDL_VIDEODRIVER") == "dummy" else pygame.SCALED | pygame.RESIZABLE
        try:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags, vsync=1)
        except pygame.error:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()
        self.clock_time = 0.0
        self.seed = seed
        self.rng = random.Random(seed)
        self.start_floor = start_floor
        self.start_room = start_room
        self.renderer = Renderer()
        self.screens = Screens()
        self.browser_title = _browser_title()
        self.leaderboard_result = (0, 0)
        self.fx = FX()
        self.demo_fx = FX(9)
        self.audio = Audio(sound)
        self.best = Best(save_path)
        self.profile = Profile(PROFILE_PATH if save_path is not None else None)
        self.new_best = False
        self.daily = ""
        self.summary = None
        self.toasts: list[list] = []
        self.pending_banner = None
        self.run: Run | None = None
        self.demo: Run | None = None
        self.seen_room = None
        self.xray = xray
        self.paused = False
        self.hushed = False
        self.show_fps = False
        self.frame_ms = 0.0
        self.dash_queued = False
        self.moved = False
        self.banner = ("", "")
        self.banner_style = "band"
        self.banner_time = 99.0
        self.fade = 1.0
        self.end_time = 0.0
        self.hovered = None
        self.aim_px = (WIDTH / 2, HEIGHT / 2)
        self.syncing = False
        self.hack_queued = None
        self.argus_time = 99.0
        self.story_seen = False
        self.story_page = 0
        self.story_time = 0.0
        self.cinematic = None
        self.scripted = None
        self.running = True
        self.scenes = StateMachine(self, TITLE_SCENE)

    def new_run(self, daily: bool = False):
        seed = self.rng.randrange(10 ** 9) if self.seed is None else self.seed
        self.daily = ""
        if daily:
            seed, self.daily = daily_seed()
        start = (1, 1) if daily else (self.start_floor, self.start_room)
        self.run = Run(seed, *start, research=self.profile.research)
        self.leaderboard_result = (0, 0)
        self.seen_room = None
        self.new_best = False
        self.summary = None
        self.fx.clear()

    def toast(self, title: str, text: str):
        self.toasts.append([title, text, 0.0])
        self.audio.play("upgrade")

    def mouse_position(self):
        if WEB:
            import platform
            position = getattr(platform.window, "brainRoomMousePosition", None)
            if position is not None:
                point = position()
                return point.x, point.y
        return pygame.mouse.get_pos()

    def handle(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN and event.key in (pygame.K_TAB, pygame.K_x):
            self.xray = not self.xray
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_m:
            self.audio.toggle_mute()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_n:
            self.audio.toggle_music()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
            self.show_fps = not self.show_fps
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11 and not WEB:
            pygame.display.toggle_fullscreen()
        elif event.type == pygame.WINDOWFOCUSLOST and self.scenes.current is PLAY and self.scripted is None:
            self.paused = True
        else:
            self.scenes.handle(event)

    def tick(self, dt: float):
        start = time.perf_counter()
        for event in pygame.event.get():
            self.handle(event)
        self.clock_time += dt
        hush = self.paused and self.scenes.current is PLAY
        if hush != self.hushed:
            self.hushed = hush
            if hush:
                self.audio.pause()
            else:
                self.audio.resume()
        if self.toasts and not self.paused:
            self.toasts[0][2] += dt
            if self.toasts[0][2] > hud.TOAST_TIME:
                self.toasts.pop(0)
        self.scenes.update(dt)
        self.scenes.current.draw(self, self.screen)
        if self.show_fps:
            style.text(self.screen, f"{self.clock.get_fps():.0f} FPS  {self.frame_ms:.1f} ms", style.mono(16, True),
                       style.GOOD, (8, HEIGHT - 24))
        pygame.display.flip()
        self.frame_ms += ((time.perf_counter() - start) * 1000 - self.frame_ms) * 0.05

    def run_loop(self, max_frames: int | None = None, fixed_dt: float | None = None, on_frame=None):
        frames = 0
        while self.running:
            dt = self.clock.tick(FPS) / 1000 if fixed_dt is None else fixed_dt
            self.tick(min(dt, 1 / 30))
            frames += 1
            if on_frame is not None:
                on_frame(self, frames)
            if max_frames is not None and frames >= max_frames:
                break
        pygame.quit()
        style.reset()

    async def run_async(self):
        import asyncio
        while self.running:
            self.tick(min(self.clock.tick(FPS) / 1000, 1 / 30))
            await asyncio.sleep(0)
