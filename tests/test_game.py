import random

import pygame

from game import upgrades
from game.player import Player
from game.run import Run
from tests.helpers import arena, place, step


def test_dash_moves_fast_and_bullets_pass_through():
    room = arena()
    p = room.player
    start = p.pos
    step(room, 0.02, move=(1, 0), dash=True)
    assert p.dashing
    step(room, 0.2, move=(1, 0))
    assert p.pos[0] - start[0] > 2.0
    room.player.dash_timer = 0.1
    before = p.hp
    assert not p.hurt(1) and p.hp == before


def test_being_hit_gives_a_moment_of_invulnerability():
    p = Player(pos=(5, 5))
    assert p.hurt(1) and p.hp == p.stats.max_hp - 1
    assert not p.hurt(1)


def test_ambush_does_double_damage_to_an_unaware_enemy():
    room = arena()
    g = place(room, "grunt", (12.0, 9.0), facing=0.0)
    before = g.hp
    room.damage_enemy(g, 1.0, (1, 0), room.player.pos)
    assert abs(before - g.hp - 2.0) < 1e-9 and g.alert


def test_clearing_a_room_opens_the_exit_and_walking_out_moves_on():
    run = Run(seed=3)
    for e in list(run.room.enemies):
        run.room.kill(e)
    run.update(1 / 60, (0, 0), (5, 5), False, False)
    assert run.room.state == "cleared"
    assert run.room.grid.at(31, 8) == "."
    first = run.room
    run.player.pos = (31.5, 9.0)
    run.update(1 / 60, (1, 0), (5, 5), False, False)
    assert run.room is not first and run.index == 1 and run.rooms_cleared == 1


def test_a_floor_ends_with_an_upgrade_installed_and_play_goes_on():
    run = Run(seed=4)
    run.index = 3
    run.room = run._make_room()
    for _ in range(2):                                           # both lockdown waves
        for e in list(run.room.enemies):
            run.room.kill(e)
        run.room.warps = []
        run.update(1 / 60, (0, 0), (5, 5), False, False)
        for e in list(run.room.enemies):
            run.room.kill(e)
    run.update(1 / 60, (0, 0), (5, 5), False, False)
    run.player.pos = (31.5, 9.0)
    run.update(1 / 60, (1, 0), (5, 5), False, False)
    assert run.state == "room" and run.floor == 2 and run.index == 0      # no menu: straight on
    assert len(run.taken) == 1
    title, text = run.notices[-1]
    assert title == "UPGRADE INSTALLED" and text.split(":")[0] in {u.name for u in upgrades.ALL}


def test_starting_at_the_boss():
    run = Run(seed=1, start_floor=9, start_room=4)
    assert run.room.plan.kind == "boss" and run.room.boss is not None


def test_upgrade_offers_respect_limits():
    p = Player(pos=(1, 1))
    offers = upgrades.offer(random.Random(0), ["ram"], p)
    assert all(u.key != "ram" for u in offers) and len(offers) == 3


def test_game_runs_title_to_play_with_ai_view_and_pause():
    from game.app import Game
    from game.bot import bot
    game = Game(seed=2, save_path=None, sound=False)
    game.scripted = bot
    seen = set()

    def key(k):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=""))

    def on_frame(g, n):
        seen.add(g.scenes.name)
        if n == 3:
            key(pygame.K_RETURN)
        if n == 200:
            key(pygame.K_TAB)
        if n == 400:
            key(pygame.K_ESCAPE)
        if n == 410:
            key(pygame.K_ESCAPE)

    game.run_loop(max_frames=1200, fixed_dt=1 / 60, on_frame=on_frame)
    assert {"TITLE", "PLAY"} <= seen and game.xray and not game.paused
    assert game.run.time > 10


def test_shots_ricochet_once_by_default():
    room = arena()
    p = room.player
    p.pos = (2.0, 9.0)
    step(room, 1 / 60, aim=(2.0, 20.0), firing=True)             # straight down at the wall
    bullet = next(b for b in room.bullets if b.owner is p)
    assert bullet.bounce == 1
    step(room, 0.6)
    assert bullet.dead or bullet.vel[1] < 0                      # it came back up
