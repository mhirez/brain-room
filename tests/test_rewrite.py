"""SYNC / rewrite: the player turns an ARGUS unit, which then fights for the player with its own AI."""

import math

from tests.helpers import arena, place, step


def test_a_rewritten_sentry_turns_on_its_squad_and_the_squad_turns_on_it():
    room = arena()
    room.player.pos = (3.0, 3.0)
    traitor = place(room, "grunt", (12.0, 9.0), alert=True)
    loyal = place(room, "grunt", (18.0, 9.0), alert=True)
    assert room.rewrite(traitor) == "OVERRIDDEN"
    assert traitor.side == "player" and traitor.foe is loyal and room.player.charges == 0
    step(room, 0.5)
    assert loyal.foe is traitor                                  # a traitor in the ranks comes first
    hp = loyal.hp
    step(room, 4.0)
    assert loyal.hp < hp or loyal.dead                          # the traitor shot it


def test_an_overridden_mender_heals_the_player():
    room = arena()
    p = room.player
    p.hp = 2
    medic = place(room, "medic", (5.0, 9.0), alert=True)
    place(room, "grunt", (28.0, 2.0))                           # keeps the room from clearing
    assert room.rewrite(medic) == "OVERRIDDEN"
    step(room, 6.0)
    assert p.hp > 2 and medic.patient is p


def test_time_runs_out_and_it_overloads():
    room = arena()
    room.player.pos = (3.0, 3.0)
    unit = place(room, "grunt", (12.0, 9.0), alert=True)
    near = place(room, "grunt", (13.5, 9.0), alert=True)
    far = place(room, "grunt", (25.0, 15.0), alert=True)
    room.rewrite(unit)
    unit.turned_until = room.time + 0.01
    hp_near, hp_far = near.hp, far.hp
    step(room, 1 / 30)
    assert unit.dead
    assert near.hp < hp_near or near.dead
    assert far.hp == hp_far


def test_rewrite_needs_a_charge_line_of_sight_and_no_firewall():
    room = arena(blocks=[(8, 6, 1, 6)])
    room.player.pos = (3.0, 9.0)
    behind = place(room, "grunt", (12.0, 9.0), alert=True)
    shielded = place(room, "grunt", (5.0, 4.0), alert=True)
    shielded.firewall = 1.0
    assert room.rewrite(behind) == "NO LINE OF SIGHT"
    assert room.rewrite(shielded).startswith("FIREWALL")
    room.damage_enemy(shielded, 1.0, (1, 0), room.player.pos)
    assert shielded.firewall == 0 and shielded.hp == shielded.max_hp   # the firewall took the hit
    room.player.charges = 0
    assert room.rewrite(shielded) == "NO CHARGE"
    room.player.charges = 1
    assert room.rewrite(shielded) == "OVERRIDDEN"


def test_argus_itself_cannot_be_rewritten():
    room = arena()
    boss = place(room, "warden", (20.0, 9.0))
    assert room.rewrite(boss) == "IMMUNE"


def test_kills_refill_charges():
    room = arena()
    p = room.player
    p.charges = 0
    for i in range(5):
        e = place(room, "grunt", (20.0, 2.0 + 2.5 * i))
        room.kill(e)
    assert p.charges == 1


def test_the_room_clears_when_only_rewritten_units_are_left():
    room = arena()
    room.player.pos = (3.0, 3.0)
    unit = place(room, "grunt", (12.0, 9.0), alert=True)
    room.rewrite(unit)
    step(room, 0.1)
    assert room.state == "cleared" and not room.enemies


# Sealed vaults: racks all round one floor tile. Nothing inside can see out or be seen.
VAULT_A = [(25, 2, 3, 1), (25, 4, 3, 1), (25, 3, 1, 1), (27, 3, 1, 1)]      # inside: (26.5, 3.5)
VAULT_B = [(25, 13, 3, 1), (25, 15, 3, 1), (25, 14, 1, 1), (27, 14, 1, 1)]  # inside: (26.5, 14.5)
HACKABLE = ("grunt", "charger", "sniper", "medic", "bulwark", "swarm", "mortar")


def test_a_unit_that_gives_up_searching_stays_with_you_when_its_lost_foe_dies():
    """A long override (ROOT ACCESS, ROOT KIT): its foe slips out of sight, it searches until it gives
    up, then the foe is destroyed elsewhere. It used to calm down, watch you instead, 'spot' you and
    crash the game (AttributeError: 'NoneType' object has no attribute 'pos')."""
    room = arena(blocks=VAULT_A + VAULT_B)
    p = room.player
    p.pos = (3.0, 9.0)
    unit = place(room, "grunt", (8.0, 9.0), facing=0.0)
    foe = place(room, "grunt", (14.0, 9.0), facing=0.0)           # in the open, in the unit's sight
    place(room, "grunt", (26.5, 14.5))                             # sealed in: keeps the room hostile
    assert room.rewrite(unit) == "OVERRIDDEN" and unit.foe is foe
    unit.turned_until = room.time + 120.0                          # a long override: no overload here
    step(room, 0.5)
    assert unit.senses.sees                                        # it is fighting its foe...
    foe.pos, foe.path = (26.5, 3.5), []                            # ...which is now sealed behind racks
    searched = False
    for _ in range(20 * 60):                                       # memory runs out: SEARCH, then give up
        step(room, 1 / 60)
        searched = searched or unit.state == "SEARCH"
        if searched and unit.state != "SEARCH":
            break
    gave_up = (unit.state, unit.alert, unit.foe)
    room.damage_enemy(foe, 100.0, (1.0, 0.0), p.pos)               # its lost foe is destroyed
    assert foe.dead and room.state == "fight"
    step(room, 3.0)                                                # it walks back to you, in plain view
    assert searched and gave_up == ("ESCORT", True, None)          # gave up: forgot the foe, stayed alert
    assert unit.side == "player" and not unit.dead
    assert unit.state == "ESCORT" and unit.alert and unit.foe is None


def test_an_overridden_unit_with_nobody_to_fight_never_grows_suspicious_of_you():
    for kind in HACKABLE:
        room = arena(blocks=VAULT_B)
        p = room.player
        p.pos = (3.0, 9.0)
        unit = place(room, kind, (6.0, 9.0), facing=math.pi)       # facing you, 3 tiles away, in plain view
        place(room, "grunt", (26.5, 14.5))                         # sealed in: hostile room, no foe in sight
        assert room.rewrite(unit) == "OVERRIDDEN" and unit.foe is None
        unit.alert = False                                         # shortcut: calm, as a give-up used to leave it
        for _ in range(90):                                        # 1.5 s, frame by frame
            step(room, 1 / 60)
            assert unit.senses.suspicion == 0.0 and not unit.senses.sees, (
                f"{unit.name} watches you: suspicion {unit.senses.suspicion:.2f}")
        assert unit.side == "player" and not unit.dead and unit.foe is None


def traitor_attacking():
    """An overridden Sentry that has just started an attack (AIM) on the only ARGUS unit it can see."""
    room = arena()
    room.player.pos = (3.0, 3.0)
    traitor = place(room, "grunt", (12.0, 9.0), facing=0.0, alert=True)
    target = place(room, "grunt", (18.0, 9.0), facing=math.pi, alert=True)
    place(room, "grunt", (28.0, 2.0))                           # out of sight: keeps the room from clearing
    assert room.rewrite(traitor) == "OVERRIDDEN"
    target.cooldown = 99.0                                      # it doesn't shoot back
    traitor.cooldown = 0.0
    while traitor.state != "AIM" and room.time < 2.0:
        step(room, 1 / 60)
    assert traitor.state == "AIM" and traitor.foe is target     # its own decision: shoot the target
    return room, traitor, target


def holds(room, e) -> bool:
    """Does e hold one of ARGUS's attack tokens or its flanker slot?"""
    return e.uid in room.coordinator.holders or room.coordinator.flanker == e.uid


def test_overridden_units_never_hold_argus_tokens_or_its_flanker_slot():
    room = arena()
    p = room.player
    p.pos = (3.0, 3.0)
    p.charges = 2                                               # two overrides at once (SPARE KEY)
    place(room, "grunt", (20.0, 9.0), facing=math.pi, alert=True)
    place(room, "grunt", (20.0, 15.0), facing=math.pi, alert=True)
    traitors = [place(room, "grunt", (14.0, 8.0), facing=0.0, alert=True),
                place(room, "grunt", (14.0, 12.0), facing=0.0, alert=True)]
    for t in traitors:
        assert room.rewrite(t) == "OVERRIDDEN"
    attacked = set()
    while room.time < 7.5 and room.state == "fight":           # an override lasts 8 s
        step(room, 1 / 60)
        attacked |= {t.uid for t in traitors if t.state in ("AIM", "FIRE")}
        held = [t.designation for t in traitors if holds(room, t)]
        assert not held, (f"t={room.time:.2f} s: {held} hold ARGUS's holders={sorted(room.coordinator.holders)} "
                          f"or flanker={room.coordinator.flanker}")
    assert attacked                                             # they did attack, with no token


def test_an_overridden_sentry_flanks_without_taking_argus_flanker_slot():
    room = arena(blocks=[(8, 5, 1, 9)])
    p = room.player
    p.pos = (11.0, 2.0)
    p.charges = 2
    target = place(room, "grunt", (11.0, 3.5), alert=True)
    pinner = place(room, "grunt", (5.0, 3.0), facing=math.pi / 2, alert=True)
    flanker = place(room, "grunt", (14.0, 9.0), alert=True)
    for t in (pinner, flanker):
        assert room.rewrite(t) == "OVERRIDDEN" and t.foe is target
    target.pos, target.path = (5.0, 9.0), []                    # shortcut: it ducks behind the wall
    step(room, 1 / 60)
    assert pinner.senses.sees and not flanker.senses.sees       # one has it pinned, the other lost it
    flanker.decide()
    assert flanker.state == "FLANK"                             # goes round, as ARGUS's Sentries do
    assert room.coordinator.flanker is None and room.coordinator.flank_free(target)


def test_argus_can_use_all_its_tokens_while_an_overridden_unit_attacks():
    room = arena()                                              # sub-level 1: ARGUS has 2 attack tokens
    room.player.pos = (3.0, 3.0)
    traitor = place(room, "grunt", (12.0, 9.0), facing=0.0, alert=True)
    first = place(room, "grunt", (18.0, 6.0), facing=math.pi, alert=True)
    second = place(room, "grunt", (18.0, 12.0), facing=math.pi, alert=True)
    assert room.rewrite(traitor) == "OVERRIDDEN"
    for e in (first, second):                                   # both target the traitor, and decide
        e.choose_foe()                                          # only when the test says so
        e.think = 99.0
    traitor.cooldown = 0.0
    while traitor.state != "AIM" and room.time < 2.0:
        step(room, 1 / 60)
    assert traitor.state == "AIM"                               # the traitor started an attack
    step(room, 0.4)                                             # past the 0.35 s gap between attack starts
    first.cooldown = 0.0
    first.decide()
    step(room, 0.4)                                             # the traitor is mid-burst (FIRE)
    second.cooldown = 0.0
    second.decide()
    assert traitor.state == "FIRE" and first.state == second.state == "AIM"
    assert room.coordinator.holders == {first.uid, second.uid}  # both tokens are ARGUS's to use


def test_a_unit_whose_target_dies_mid_attack_escorts_you_holding_no_token():
    room, traitor, target = traitor_attacking()
    room.damage_enemy(target, target.hp + 1.0, (1.0, 0.0), room.player.pos)   # you finish it first (Room.kill)
    assert target.dead and traitor.state == "ESCORT"
    assert not holds(room, traitor)


def test_a_unit_left_with_no_foe_escorts_you_holding_no_token():
    room, traitor, _ = traitor_attacking()
    traitor.foe = None                                          # shortcut: nobody to fight (Enemy.update)
    step(room, 1 / 60)
    assert traitor.state == "ESCORT"
    assert not holds(room, traitor)


def test_a_unit_whose_target_is_overridden_too_escorts_you_holding_no_token():
    room, traitor, target = traitor_attacking()
    room.player.charges = 1
    assert room.rewrite(target) == "OVERRIDDEN"                 # you override its target too
    traitor.decide()                                            # nobody left to fight (Enemy.decide)
    assert traitor.state == "ESCORT" and traitor.foe is None
    assert not holds(room, traitor)
