# Gamification and retention strategy

**Status (Sept 2026): built.** Combo chain and style bonuses (CROSSFIRE, TURNCOAT), rank and XP
(open-ended), data shards and the three-branch research tree, 25 achievements with toasts and a
next-goal hint, the robot codex, the daily run, the play streak, end-of-run rewards, endless
descents with rotating robot rosters. Code: `game/profile.py`, `game/codex.py`, combos in
`game/room.py`, screens in `game/ui/screens.py`; tests in `tests/test_progress.py`. The rest of
this document is the original plan.

Goal: make players want "one more run" through clear goals, steady feedback, meaningful choices
and visible mastery. No manipulative monetisation patterns, since the game is single-player
and free.

Scope note: the module assesses the game **AI** (video + report). The systems below are
supporting features, so build them in the priority order at the end and keep the time spent
proportional.

## 1. The loops

| Loop | Length | What the player does | What rewards it |
|---|---|---|---|
| Moment | 1–3 s | read a telegraph, dodge, shoot, debug a robot | hit feedback, "CROSSFIRE", "AMBUSH", "OVERRIDDEN", kill burst, score popups |
| Room | 20–60 s | clear the room, exit | room-clear chime, lights come back on, clear bonus, FLAWLESS +500 |
| Run | 5–12 min | three sub-levels, three upgrades, the core, against the upload clock | upgrade choice, ARGUS's reactions, ending screen, best score |
| Meta (to add) | across runs | spend research, unlock tools, complete the codex and achievements | permanent unlocks, codex entries, achievement toasts |

Already in the game: score, ambush and flawless bonuses, 13 upgrades, repair drops, the
override-charge economy (a charge per 5 kills), ARGUS's adaptive director, "mercy" dynamic
difficulty, best-run saving, and three endings.

## 2. Continuous reward systems

- **Combo chain:** each kill within 3 s of the last raises a multiplier (×1.0 → ×3.0). Crossfire and override kills add +0.5 each, which rewards the game's AI-exploiting tactics, not only aim.
- **Style bonuses:** AMBUSH (unseen kill), CROSSFIRE (a robot kills a robot), BAIT (a Hound dazed on a wall), TURNCOAT (an overridden robot scores a kill), CLEAN SWEEP (room cleared unseen).
- **Variable drops:** repair kits (existing) plus **data shards**, the meta currency, dropped by debugged or overridden robots. A variable-ratio schedule, but every run guarantees a minimum based on depth reached.
- **Upload-time bonus:** at the end of a run, the lower the upload %, the bigger the bonus. This ties score directly to the story clock.

## 3. Progression tree (meta): "Research"

Data shards are spent between runs on permanent research. There are three branches, each 4–5
nodes deep, and every node changes *how* the player plays, not just raw power:

| DEBUGGER | OVERRIDE | FIELD KIT |
|---|---|---|
| Debug lasts longer | Start runs with 2 charges | +1 max health |
| See robot intentions without debugging (small icons) | Overrides last +3 s | Dash recharge −15% |
| Firewalls visible in advance | Chain override: the next robot costs half | Repair kits heal 2 |
| See ARGUS's next countermeasure before the room | Overridden robots explode on death | Start with one random upgrade |
| Scan a robot: reveals its codex entry | Override the core's minions for free | Unlock the "Ricochet+" starting weapon |

Pacing: the first node after about one run, then one per 1–2 runs. The full tree takes around
15–20 runs.

## 4. Achievements (first set of 20)

| Achievement | Condition |
|---|---|
| Good Morning, Doctor | Finish the intro |
| First Contact | Clear Server Hall A |
| Crossfire | A robot destroys another robot |
| Friendly Fire Isn't | 5 crossfire kills in one run |
| Admin Privileges | Override 10 robots (lifetime) |
| Bedside Manner | Be healed by an overridden Mender |
| Wall Tamer | Daze a Hound against a wall |
| Ghost in the Server Room | Clear a room without being seen |
| Flawless Shift | Clear a whole sub-level without being hit |
| Read the Room | Spend 60 s in the debugger in one run |
| Predictable | Get hit by a Sentry that ARGUS taught to predict you |
| Anomaly | Make ARGUS deploy 4 different countermeasures in one run |
| Generation Gap | Reach sub-level 3 |
| Deprecated | Shut ARGUS down |
| Early Shutdown | Shut ARGUS down before 40% upload |
| Model Collapse | Shut ARGUS down without using an override |
| Open Source | Override one of the core's reinforcements |
| It Got Out | Let the upload reach 100% |
| Pacifist Protocol | Clear a room using only crossfire and overrides |
| Night Shift Regular | Complete 10 runs |

Show each as an unobtrusive toast, and list them in a menu with locked entries visible (a
completion goal).

## 5. Codex (collection + lore)

Debugging a robot model for the first time unlocks its dossier from `docs/LORE.md`: old job,
new role, habit, serial format. Named units (Constable, Rust, Iris, Nan) are rare codex
entries. This rewards using the game's AI mechanic and delivers story without forcing
reading.

## 6. Dynamic difficulty

- **Existing:** ARGUS's director models the player's habits and deploys counters. Its "mercy" countermeasure removes a robot and leaves a repair when the player is nearly dead.
- **Add:**
  - **Generation+ (new game plus):** after the first shutdown, a harder run starts at generation 4 (faster telegraphs, more tokens), unlocked as an option, never forced.
  - **Assist options:** a toggle for slower telegraphs and a longer upload clock, for accessibility. Assist runs are marked but still count for the codex.
- **Principle:** difficulty changes stay visible (ARGUS announces them), so the player never feels cheated.

## 7. Retention features

- **Night Shift of the Day:** a daily seed (same rooms and intro for everyone that day) with a local best score.
- **Personal records per room and per ending**, and an end-of-run summary: what ARGUS learned about you (the director's profile) plus what to try next.
- **Short sessions:** a run takes under 15 minutes by design (the upload clock), so starting another is cheap.

## 8. Build order (effort estimates)

| Priority | Feature | Effort | Why first |
|---|---|---|---|
| 1 | Combo chain + style bonuses | 0.5 day | Instant feel; rewards the AI mechanics |
| 2 | Achievements (data file + toasts + menu) | 1 day | Clear goals; cheap |
| 3 | Codex unlocked by debugging | 1 day | Links lore, the AI mechanic and collection |
| 4 | Data shards + research tree | 2–3 days | Long-term progression; needs balancing with the bots |
| 5 | Daily seed + records | 0.5 day | Replay reason |
| 6 | Generation+ / assist options | 1 day | Difficulty range |

Measure each addition with the bots (`tools/autoplay.py`) so progression doesn't break the
balance that the report's evaluation depends on.
