"""The intro movie and the new art: they run, they vary, they can be skipped; racks take hits."""

import pygame

from game.projectiles import Bullet
from game.ui.cinematic import SHOTS, Cinematic
from game.ui.fx import FX
from game.ui.render import Renderer
from tests.helpers import arena, place


def _screen():
    pygame.init()
    return pygame.display.set_mode((1280, 720))


def test_the_intro_plays_every_shot_and_ends():
    screen = _screen()
    film, renderer = Cinematic(7), Renderer()
    seen = set()
    for _ in range(int(sum(d for _, d in SHOTS) * 30) + 30):
        film.update(1 / 30)
        seen.add(film.name)
        film.draw(screen, renderer, film.t)
        if film.done:
            break
    assert film.done and seen == {name for name, _ in SHOTS}
    assert all(not e.dormant for e in film.room.enemies)          # every robot woke up
    assert film.room.grid.at(0, 8) == "D"                          # and the doors are locked


def test_the_intro_is_different_every_time():
    a, b = Cinematic(1), Cinematic(2)
    story_a = (a.minute, tuple(a.acts), a.first_words, a.room_name)
    story_b = (b.minute, tuple(b.acts), b.first_words, b.room_name)
    assert story_a != story_b


def test_the_intro_can_be_skipped():
    film = Cinematic(3)
    film.skip_shot()
    assert film.name == SHOTS[1][0]
    film.skip_all()
    assert film.done


def test_title_to_intro_to_game():
    from game.app import Game
    game = Game(seed=5, save_path=None, sound=False)
    seen = []

    def key(k):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode=""))

    def on_frame(g, n):
        if not seen or seen[-1] != g.scenes.name:
            seen.append(g.scenes.name)
        if n in (3, 40):
            key(pygame.K_RETURN)
        if n == 20:
            key(pygame.K_ESCAPE)                                   # skip the intro

    game.run_loop(max_frames=90, fixed_dt=1 / 60, on_frame=on_frame)
    assert seen[:4] == ["TITLE", "INTRO", "STORY", "PLAY"]


def _rack_events(room, seconds):
    events = []
    for _ in range(int(seconds * 60)):
        room.update(1 / 60, (0, 0), (room.player.pos[0] + 1, room.player.pos[1]), False, False)
        events += [ev for ev in room.fx if ev[0] == "rack"]
        room.fx.clear()
        room.sounds.clear()
    return events


def test_a_shot_stops_in_a_solid_rack_and_shoves_it_for_good():
    screen = _screen()
    room = arena(blocks=[(15, 6, 1, 6)])                            # one rack, tiles (15, 6..11)
    room.player.pos = (3.0, 3.0)
    shooter = place(room, "grunt", (10.0, 9.0))
    shot = Bullet((13.0, 9.0), (12.0, 0.0), 0.16, 1, "argus", shooter, bounce=1, life=2.0)
    room.bullets.append(shot)
    hits = _rack_events(room, 0.3)
    assert shot.dead and not room.bullets                           # no ricochet off a rack
    assert hits and hits[0][1] == (15, 9) and hits[0][2][0] > 0.9 and hits[0][3] == 1.0

    fx, renderer = FX(), Renderer()
    renderer.draw(screen, room, fx, 0.0)
    block = renderer.rack_of[(15, 9)]
    assert renderer.rack_of[(15, 6)] == block                       # the whole rack moves as one
    fx.consume(hits[:1])
    t = 0.0
    for _ in range(90):
        t += 1 / 60
        renderer.draw(screen, room, fx, t)
    assert renderer._rack_offset(block) == (2, 0)                   # pushed away from the shooter...
    assert renderer.rack_motion[block][2] == 0.0                    # ...stopped, and stays there
    for _ in range(40):                                             # however hard it is pushed
        fx.consume([("rack", (15, 9), (1.0, 0.0), 3.0)])
        t += 1 / 60
        renderer.draw(screen, room, fx, t)
    assert renderer._rack_offset(block)[0] <= 8


def test_everyones_shots_shove_racks_and_a_hound_hits_hardest():
    room = arena(blocks=[(15, 6, 1, 6)])
    room.player.pos = (12.0, 9.0)
    room.bullets.append(Bullet((13.0, 9.0), (12.0, 0.0), 0.12, 1, "player", room.player, bounce=1, life=2.0))
    mine = _rack_events(room, 0.3)
    assert mine and mine[0][3] == 0.5 and not room.bullets          # the Doctor's shot shoves it too
    hound = place(room, "charger", (14.4, 9.0))
    hound.aim = 0.0
    room.slam(hound)
    slams = [ev for ev in room.fx if ev[0] == "rack"]
    assert slams and slams[0][1] == (15, 9) and slams[0][3] == 3.0


def test_bullets_still_ricochet_off_the_outer_walls():
    room = arena()
    room.player.pos = (5.0, 9.0)
    shot = Bullet((5.0, 16.0), (0.0, 12.0), 0.12, 1, "player", room.player, bounce=1, life=2.0)
    room.bullets.append(shot)
    _rack_events(room, 0.2)
    assert not shot.dead and shot.vel[1] < 0 and shot.bounce == 0
