"""Endless play: a Brain Room every third floor, ARGUS restores from a backup, and the floors never
run out or stop for a menu, while the difficulty stays capped and readable."""

import random

from game import upgrades
from game.config import UPLOAD_TIME
from game.room import tuning
from game.rooms import COST, ROOM_POOL, THEMES, descent, level, plan
from game.run import BACKUP_LINE, Run


def _clear_and_leave(run):
    for e in list(run.room.enemies):
        run.room.kill(e)
    run.update(1 / 60, (0, 0), (5, 5), False, False)
    run.player.pos = (31.5, 9.0)
    run.update(1 / 60, (1, 0), (5, 5), False, False)


def test_the_core_waits_every_third_floor_and_backups_are_named():
    rng = random.Random(1)
    assert [plan(f, 3, rng).kind for f in (3, 6, 12, 30)] == ["final"] * 4
    assert [plan(f, 3, rng).kind for f in (9, 18, 27)] == ["boss"] * 3            # the core, later on
    assert [plan(f, 3, rng).kind for f in (4, 5, 7)] == ["lockdown"] * 3
    four = plan(4, 0, rng)
    assert (level(4), descent(4)) == (1, 1)
    assert four.name in ROOM_POOL and four.floor_name == "SUB-LEVEL 1, BACKUP 1"     # random names past floor 3
    assert four.theme in THEMES and plan(1, 0, rng).name == "LOBBY"
    assert plan(6, 3, rng).name == "BRAIN ROOM"
    assert plan(2, 0, rng).floor_name == "SUB-LEVEL 2"                  # the first descent is unchanged


def test_difficulty_keeps_rising_but_stays_capped():
    assert tuning(3) == {"hp": 1.6, "windup": 0.8, "bullet": 1.16}        # floors 1-3 as before
    assert tuning(4)["hp"] > tuning(3)["hp"]
    deep = tuning(100)
    assert deep["hp"] == 4.0 and deep["bullet"] == 1.4 and deep["windup"] == 0.75
    rng = random.Random(2)
    for floor in (5, 20, 100):
        wave = plan(floor, 2, rng).waves[0]
        spent = sum(COST[k] for k in wave if k != "swarm") + COST["swarm"] * wave.count("swarm") / 3
        assert spent <= 10.0 and len(wave) <= 10


def test_after_the_brain_room_play_goes_straight_on_from_a_backup():
    run = Run(seed=5, start_floor=3, start_room=4)
    run.time = UPLOAD_TIME * 0.6                                        # 60% uploaded at the shutdown
    for _ in range(1200):                                               # the final stand: all three waves
        if run.floor == 4:
            break
        run.player.hp = 1
        _clear_and_leave(run)
        run.time = max(run.time, UPLOAD_TIME * 0.6)
    assert run.state == "room" and run.floor == 4 and run.index == 0 and run.descents == 1
    assert run.upload == 0.0 and run.player.hp == run.player.stats.max_hp
    assert run.room.plan.line == BACKUP_LINE
    assert run.room.plan.floor_name == "SUB-LEVEL 1, BACKUP 1"
    assert ("SHUTDOWN COMPLETE" in [t for t, _ in run.notices]) and run.stats["shutdowns"] == 1


def test_no_upgrades_left_means_straight_on_to_the_next_floor():
    run = Run(seed=6, start_floor=4, start_room=4)
    run.taken = [u.key for u in upgrades.ALL for _ in range(u.limit)]
    _clear_and_leave(run)
    for _ in range(600):                                                # the lockdown's second wave
        if run.floor == 5:
            break
        _clear_and_leave(run)
    assert run.state == "room" and run.floor == 5 and run.index == 0


def test_deep_floors_still_build_playable_rooms():
    run = Run(seed=7, start_floor=40)
    bosses = 0
    for _ in range(3000):                                               # floors 40-42, core included
        if run.floor >= 43:
            break
        for e in run.room.enemies:
            assert e.designation == "ARGUS" or e.designation.split("-")[1].startswith(f"{run.floor}.")
        bosses += run.room.plan.kind in ("boss", "final")
        _clear_and_leave(run)
    assert run.floor == 43 and run.state == "room" and bosses > 0


def test_the_game_never_stops_for_a_menu_after_a_shutdown():
    import pygame
    from game.app import Game
    game = Game(seed=3, save_path=None, sound=False, start_floor=3, start_room=4)
    game.scripted = lambda run: ((0, 0), (5.0, 5.0), False, False, None)
    seen, banners = [], []

    def key(k):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=""))

    def on_frame(g, n):
        if not seen or seen[-1] != g.scenes.name:
            seen.append(g.scenes.name)
        banners.append(g.banner[0])
        if n == 3:
            key(pygame.K_RETURN)                                        # title -> the Brain Room
        if g.scenes.name == "PLAY" and g.run.floor == 3 and g.run.state == "room":
            g.run.player.hp = g.run.player.stats.max_hp
            for e in list(g.run.room.enemies):
                g.run.room.kill(e)
            if g.run.room.state == "cleared":
                g.run.player.pos = (31.5, 9.0)

    game.run_loop(max_frames=900, fixed_dt=1 / 60, on_frame=on_frame)
    assert seen == ["TITLE", "PLAY"]                                    # no other screen, ever
    assert game.run.floor == 4 and game.run.descents == 1 and "SHUTDOWN COMPLETE" in banners
