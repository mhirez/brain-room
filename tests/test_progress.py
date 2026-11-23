"""The long game: combos and style kills, rank, research, achievements, rewards and saving."""

import datetime

from game.profile import ACHIEVEMENTS, RANKS, Profile, rank
from game.room import COMBO_WINDOW
from game.run import Run
from tests.helpers import arena, place


def test_quick_kills_build_a_combo_that_runs_out():
    room = arena()
    room.player.pos = (3.0, 9.0)
    robots = [place(room, "grunt", (10.0 + i, 9.0)) for i in range(4)]
    for e in robots[:3]:
        e.last_attacker = room.player
        room.kill(e)
    assert room.combo == 3 and room.multiplier == 1.5
    room.time += COMBO_WINDOW + 0.1
    assert room.combo_left() == 0.0
    robots[3].last_attacker = room.player
    room.kill(robots[3])
    assert room.combo == 1 and room.best_combo == 1.5


def test_kills_by_a_turned_robot_or_by_argus_itself_are_style_kills():
    room = arena()
    room.player.pos = (3.0, 9.0)
    traitor = place(room, "grunt", (10.0, 9.0))
    traitor.side = "player"
    victim = place(room, "grunt", (12.0, 9.0))
    victim.last_attacker = traitor
    score = room.score
    room.kill(victim)
    assert room.stats["turncoats"] == 1 and room.score - score == 125 + 150      # counts double in the combo
    other = place(room, "sniper", (14.0, 9.0))
    shooter = place(room, "grunt", (16.0, 9.0))
    other.last_attacker = shooter
    assert room.kill_style(other) == "CROSSFIRE"


def test_rank_climbs_forever():
    assert rank(0)[0] == "INTERN" and rank(RANKS[1][0])[0] == RANKS[1][1]
    title, progress, need = rank(RANKS[-1][0] + 60000)
    assert title == "CHIEF SCIENTIST +1" and 0 < progress < 1 and need > RANKS[-1][0] + 60000


def test_research_needs_shards_and_the_node_before_it():
    p = Profile(None)
    assert not p.can_buy("focus")                                   # no shards yet
    p.shards = 100
    assert not p.can_buy("reboot")                                  # needs DEEP FOCUS first
    p.buy("focus")
    p.buy("reboot")
    p.buy("spare")
    p.buy("coat")
    assert p.research == ["focus", "reboot", "spare", "coat"] and p.shards == 100 - 10 - 25 - 10 - 10
    assert "researcher" in p.achievements                          # 3+ upgrades researched
    run = Run(seed=1, research=p.research)
    s = run.player.stats
    assert run.player.charges == 2 and s.max_hp == 7 and run.player.hp == 7
    assert s.sync_drain == 0.75 and s.sync_refill == 1.5


def test_achievements_unlock_from_what_a_run_did_and_the_next_goal_moves_on():
    p = Profile(None)
    assert p.next_goal() is ACHIEVEMENTS[0]
    new = p.check({"rooms": 1, "crossfire kills": 5, "kill:bulwark": 1, "floor": 10})
    names = {a.key for a in new}
    assert {"first_room", "crossfire", "crossfire5", "shield", "backup", "deep"} <= names
    assert p.next_goal().key == "first_run"
    assert not p.check({"rooms": 1})                                # nothing twice


def test_a_run_pays_out_once_even_if_it_reaches_two_end_screens():
    p = Profile(None)
    run = Run(seed=2)
    run.score, run.rooms_cleared, run.kills = 3000, 4, 10
    first = p.finish_run(run, today=datetime.date(2026, 9, 27))
    assert first.xp >= 300 and first.shards >= 4 and p.lifetime["runs"] == 1
    run.score, run.rooms_cleared = 5000, 6                          # kept going after a shutdown
    second = p.finish_run(run, today=datetime.date(2026, 9, 27))
    assert second.xp < first.xp and p.lifetime["runs"] == 1          # only the difference is paid
    assert p.xp == first.xp + second.xp


def test_the_streak_counts_consecutive_days_and_daily_runs_keep_a_best():
    p = Profile(None)
    for day in (26, 27):
        p.finish_run(Run(seed=day), today=datetime.date(2026, 9, day))
    assert p.streak == 2
    p.finish_run(Run(seed=3), today=datetime.date(2026, 9, 30))
    assert p.streak == 1
    run = Run(seed=4)
    run.score = 1234
    summary = p.finish_run(run, daily="2026-09-30", today=datetime.date(2026, 9, 30))
    assert summary.daily_best and p.daily["2026-09-30"] == 1234 and "daily" in p.achievements


def test_the_profile_is_saved_between_sessions(tmp_path):
    path = tmp_path / "profile.json"
    p = Profile(path)
    p.shards = 30
    p.buy("coat")
    p.codex.append("grunt")
    p.save()
    again = Profile(path)
    assert again.research == ["coat"] and again.shards == 20 and again.codex == ["grunt"]


def test_new_robot_kills_unlock_codex_entries():
    p = Profile(None)
    run = Run(seed=5)
    victim = place(run.room, "bulwark", (12.0, 9.0))
    victim.last_attacker = run.player
    run.room.kill(victim)
    summary = p.finish_run(run, today=datetime.date(2026, 9, 27))
    assert "bulwark" in summary.codex and "bulwark" in p.codex and "shield" in p.achievements
