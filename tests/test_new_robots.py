"""The robots that arrive in later descents: BULWARK (shield), MIDGE (swarm), MORTAR (artillery),
and the rosters that change every three floors."""

import math
import random

from game.ai import mortar, swarm
from game.room import Room
from game.rooms import ALL_KINDS, CLASSIC, SHOOTERS, generate, plan, roster
from game.player import Player
from tests.helpers import arena, place, step


def test_a_bulwark_blocks_shots_from_the_front_but_not_from_behind():
    room = arena()
    room.player.pos = (4.0, 9.0)
    b = place(room, "bulwark", (12.0, 9.0), alert=True)
    b.facing = math.pi                                                  # shield toward the player
    hp = b.hp
    room.damage_enemy(b, 1.0, (1.0, 0.0), room.player.pos)              # a shot travelling right, into the shield
    assert b.hp == hp
    room.damage_enemy(b, 1.0, (-1.0, 0.0), (20.0, 9.0))                 # from behind
    assert b.hp < hp


def test_a_bulwark_steps_in_front_of_a_hurt_ally():
    room = arena()
    room.player.pos = (4.0, 9.0)
    b = place(room, "bulwark", (14.0, 9.0), alert=True)
    friend = place(room, "grunt", (9.0, 9.0), alert=True)
    friend.hp = friend.max_hp * 0.2
    b.senses.sees = True
    options = b.options()
    assert options["guard"] > options["advance"]
    assert b.feasible("guard") and b.ward is friend


def test_midges_keep_apart_while_they_flock():
    room = arena()
    room.player.pos = (4.0, 9.0)
    a = place(room, "swarm", (12.0, 9.0), alert=True)
    place(room, "swarm", (12.3, 9.0), alert=True)                       # far too close, to its right
    push = a.steering()
    assert push[0] < 0                                                  # separation wins: it veers away


def test_a_midge_dive_costs_a_heart_and_breaks_the_drone():
    room = arena()
    room.player.pos = (6.0, 9.0)
    d = place(room, "swarm", (9.0, 9.0), alert=True)
    d.aim = math.pi
    d.fsm.change(swarm.DIVE)
    hp = room.player.hp
    step(room, 0.4)
    assert room.player.hp == hp - 1 and d.dead


def test_a_mortar_shells_where_it_last_saw_you():
    room = arena(blocks=[(10, 6, 1, 6)])                                # a wall of racks between them
    room.player.pos = (5.0, 9.0)
    m = place(room, "mortar", (15.0, 9.0), alert=True)
    m.senses.sees = False
    m.senses.last_known = (6.0, 9.0)                                    # it saw you a moment ago
    m.cooldown = 0.0
    assert m.knows() and m.options()["bombard"] > 0.8
    m.fsm.change(mortar.AIM)
    step(room, 1.2)
    assert room.shells and math.dist(room.shells[0].target, (6.0, 9.0)) < 0.01


def test_a_shell_blast_hurts_the_player_and_argus_own_robots():
    room = arena()
    room.player.pos = (8.0, 9.0)
    m = place(room, "mortar", (18.0, 9.0), alert=True)
    friend = place(room, "grunt", (8.6, 9.0), alert=True)
    hp, fhp = room.player.hp, friend.hp
    room.lob(m, (8.2, 9.0), 0.5, 1.1)
    step(room, 0.6)
    assert room.player.hp == hp - 1 and friend.hp < fhp and room.stats["crossfire"] >= 1


def test_the_roster_changes_every_descent_and_always_has_a_shooter():
    assert all(roster(f) == CLASSIC for f in (1, 2, 3))
    assert "bulwark" in roster(4) and "swarm" in roster(7) and "mortar" in roster(10)
    rosters = [tuple(roster(3 * d + 1)) for d in range(40)]
    assert len(set(rosters)) > 10                                       # they keep changing
    assert all(any(k in SHOOTERS for k in r) and len(r) == 4 for r in rosters)
    rng = random.Random(4)
    for floor, new in ((4, "bulwark"), (7, "swarm"), (10, "mortar")):
        intro = plan(floor, 1, rng)
        assert intro.new == new and new in intro.waves[0]


def test_every_model_spawns_and_fights_without_errors():
    rng = random.Random(9)
    for kind in ALL_KINDS:
        room = Room(plan(5, 0, rng), generate(rng), Player(pos=(2.0, 9.0)), rng)
        room.enemies = []
        e = room._spawn(kind, (16.0, 9.0))
        e.become_alert(room.player.pos, shout=False)
        for _ in range(240):
            room.update(1 / 60, (0, 1), (16.0, 9.0), True, False)
            room.fx.clear()
            room.sounds.clear()
        assert e.designation.startswith(("SNT", "HND", "LNS", "MND", "BLW", "MDG", "HRN"))
