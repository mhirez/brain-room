# Proposals under evaluation

## 6. Evolutionary AI: robots that are cloned from the fittest

### 6.1 The idea

At the end of each level, every robot is scored by a **fitness function**. The fittest robot's
"mind" is **cloned** (with small random mutations) into the robots of the next level. Robots
therefore inherit what worked against this particular player, while the **finite state machine
stays exactly as authored**: evolution changes numbers inside the states and transitions,
never the states themselves.

This matches the story in `docs/LORE.md` (ARGUS's Mind Forge, generation n on sub-level n), so
the mechanic and the fiction explain each other.

### 6.2 Feasibility: high

The codebase is already shaped for it:
- **Behaviour is parameterised.** Utility scores are weighted formulas (e.g. Sentry `shoot = 0.6 + 0.2·health + 0.2·range`, `cover = 0.75·(1−health) + 0.35·under fire`). Those weights become the genome.
- **The simulation is headless and deterministic** (`game/room.py`, seeded RNG), so fitness can be measured quickly and reproducibly.
- **Evaluation tools exist:** the bots (`tools/autoplay.py`) and parallel ablation with confidence intervals (`tools/ablation.py`) can measure whether evolution actually helps.
- **Cost:** the genetic operations run once per level (microseconds); no effect on frame rate.

Estimated work: 3–4 days (genome extraction 1 day, evolution loop 0.5 day, UI/lore surfacing 0.5 day, evaluation 1–2 days).

### 6.3 Design

**Genome (per robot type), with bounded values:**

| Robot | Genes (examples) | Bounds keep it fair |
|---|---|---|
| Sentry | shoot bias, cover weight, cover health threshold, strafe bias, flank weight, preferred range (min/max) | telegraph length is **not** a gene: warnings stay readable |
| Hound | charge range, circle radius, stalk aggression | charge windup fixed |
| Lens | preferred range, evade distance, relocate distance | laser track/lock times fixed |
| Mender | heal priority curve, shelter weight, flee distance | heal rate fixed |

**Fitness (measured per robot during a room):**

```
F = 3.0 · hits landed on the player
  + 1.0 · seconds survived / room length
  + 0.5 · damage absorbed by allies it healed (Menders)
  − 1.5 · crossfire hits it caused on allies
  − 0.5 · times it was overridden
```

**Selection and inheritance (end of each level):**

```
elite = top 2 robots of each type by fitness            (elitism)
for each robot of the next level:
    parent = tournament(elite)                          (size 2)
    genome = parent.genome.copy()
    if two parents exist and random() < 0.3:
        genome = uniform_crossover(parent_a, parent_b)
    genome = mutate(genome, sigma = 0.05, clamp to bounds)
    robot.genome = genome ; robot.generation = level
```

**"Inherits previous knowledge":**
- *Genetic (Darwinian):* the utility weights that worked.
- *Learned (Lamarckian):* the director's player profile is already carried from room to room; with evolution it can also seed the genome (e.g. a player who fights far away pushes preferred-range genes up).

**Staying strictly within the FSM:** the FSM classes (`PATROL → INVESTIGATE → SEARCH`,
`ENGAGE → AIM → FIRE`, `TAKE COVER → HIDE`, …) and every transition are unchanged. A genome only
changes **when** a transition's utility wins and the thresholds it compares against. Every
evolved robot therefore still passes the existing 57 tests of state behaviour. Add one test
proving that random genomes within bounds never produce an illegal transition.

**Guard rails:**
- Cap fitness-driven difficulty growth per generation.
- Keep the director's "mercy".
- Show genomes in the AI View (bars per gene, parent serial, generation) so the evolution is visible in the video.

### 6.4 How to show it works (report evidence)

- **Fitness curves** across generations (mean and best) over 100 bot runs.
- **Ablation:** evolution on vs off vs random mutation only, reporting hits per room with 95% CIs (existing tooling).
- **Specialisation test:**
  - a far-range bot should drive preferred-range genes up;
  - a hiding bot should raise flank weights.
- **Diversity:** gene variance per generation, to show the population doesn't collapse to one strategy.

### 6.5 Academic justification (for the proposal to the lecturer)

- **Module fit:** combines FSMs and utility decision making (core lecture topics) with adaptation, and works under imperfect information: fitness only uses what the robots actually achieved.
- **Game AI, not black-box ML:** evolution tunes a small set of interpretable parameters inside designer-authored states. Behaviour stays explainable, testable and readable, which is the distinction the lectures draw between game AI and academic AI.
- **Established in games research:**
  - real-time neuroevolution in NERO (Stanley, Bryant & Miikkulainen, 2005);
  - evolved content in Galactic Arms Race (Hastings, Guha & Stanley, 2009);
  - online adaptation with dynamic scripting (Spronck et al., 2006);
  - survey coverage in Yannakakis & Togelius (2018).
- **Measurable:** the existing bot and ablation framework can show the effect with confidence intervals, not anecdotes.

**One-paragraph pitch summary:** At the end of each level the robots are ranked by a fitness
function (hits landed, survival, penalties for friendly fire). The best robot's utility weights
are cloned with small mutations into the next level's robots, so each generation adapts to the
player. The finite state machines are unchanged; only the numerical parameters that drive
their transitions evolve, within bounds that keep attacks telegraphed and fair. The effect is
evaluated with automated players over 100 runs per condition, comparing evolution on, off and
random mutation.

**References** (verify editions and page numbers before citing):
- Eiben, A. E., & Smith, J. E. (2015). *Introduction to Evolutionary Computing* (2nd ed.). Springer.
- Hastings, E. J., Guha, R. K., & Stanley, K. O. (2009). Automatic content generation in the Galactic Arms Race video game. *IEEE Transactions on Computational Intelligence and AI in Games, 1*(4).
- Spronck, P., Ponsen, M., Sprinkhuizen-Kuyper, I., & Postma, E. (2006). Adaptive game AI with dynamic scripting. *Machine Learning, 63*(3).
- Stanley, K. O., Bryant, B. D., & Miikkulainen, R. (2005). Real-time neuroevolution in the NERO video game. *IEEE Transactions on Evolutionary Computation, 9*(6).
- Yannakakis, G. N., & Togelius, J. (2018). *Artificial Intelligence and Games*. Springer.

---

## 7. 3D feasibility

**Constraint from the module (Lecture 1):** "We don't need fantastic artwork, or an amazing user
interface, we just need to see functional AI creating a recognisable experience." Marks go to
the video and the report about the AI, so visual upgrades have limited marking value.

| Option | What it means | Effort | Risk to 27 Nov | Performance |
|---|---|---|---|---|
| A. Stay 2D (current renderer: lighting, procedural robot art, particles, intro movie) | none | none | none | ~3–4 ms/frame |
| B. 2.5D pre-rendered sprites | Model robots in Blender, render each at 16–32 angles into sprite sheets, draw them in pygame | 1–2 weeks (modelling and animation skill needed) | medium | fine |
| C. Python 3D engine (Ursina / Panda3D) on the same simulation | The game logic is renderer-independent (`room.py` and the AI run headless), so a 3D view can read the same state: rooms as meshes, robots as models, real lights | 2–3 weeks for decent quality; free CC0 asset kits (e.g. Kenney) cut modelling time | medium–high | fine for one room at a time |
| D. Port to Unity / Godot / Unreal | Rewrite the AI in C# / GDScript / C++ | 4–8 weeks | high | best tooling |

**Recommendation:** stay with A until the video and report are secure (early November). If time
remains, prototype C as a separate "3D view" mode: the AI code is untouched, so the risk is
contained. Avoid D before the deadline.

---

## 8. Web deployment (playable in a browser, no download)

### 8.1 Recommended route: pygbag (pygame-ce → WebAssembly)

pygbag packages a pygame-ce game into WebAssembly with a CPython runtime and an HTML5 canvas.
Output is a static folder that runs in Chrome, Firefox and Edge (test Safari separately).

**Changes this codebase needs:**
1. **Async main loop:** make `Game.run_loop` async and yield every frame (`await asyncio.sleep(0)`); `main.py` calls `asyncio.run(main())`. The browser cannot block.
2. **Fonts:** `pygame.font.SysFont` has no system fonts in the browser. Bundle `.ttf` files (open-licence fonts, e.g. from Google Fonts under the SIL OFL) and load them with `pygame.font.Font(path, size)`.
3. **Audio:** browsers start audio only after a user gesture; start the mixer after the first key press or click. Synthesising sounds at start-up is slower in WebAssembly, so pre-render them to `.ogg` files with a build script.
4. **Saves:** `saves/lockdown.json` lives in a virtual filesystem that doesn't persist. Use the browser's `localStorage` (pygbag exposes it through `platform.window`).
5. **Exclude tools:** `tools/ablation.py` uses `multiprocessing`, which is unavailable in the browser; it stays desktop-only (as do tests).
6. **Performance:** Python in WebAssembly runs roughly 2–5× slower. Profile A*, ray casts and the lighting pass. Possible fixes: halve the lighting ray count, cache the danger maps, or offer a "low effects" toggle.
7. **Window:** keep 1280×720 and let the page scale the canvas; turn off the custom cursor if the browser pointer is preferred.

**Build and publish:**

```bash
pip install pygbag
```

```bash
pygbag --build .
```

The output folder (`build/web`) is a static site. Upload it as an HTML5 project on itch.io
(zip upload, "playable in browser"), or serve it from GitHub Pages once the new repository
exists.

### 8.2 Alternatives

| Option | Effort | Notes |
|---|---|---|
| Rewrite in TypeScript with Phaser / HTML5 Canvas | 3–5 weeks | Best web performance; all AI rewritten |
| Godot HTML5 export | port to Godot first (see 7-D) | Good tooling; large rewrite |
| Unity WebGL | port to Unity first | Heavy downloads; large rewrite |

**Recommendation:** pygbag. It keeps the Python AI code intact, needs about 1–2 days of changes
(items 1–5), and produces a link a lecturer can open without installing anything. Do it after
the core coursework is finished, and keep the desktop build as the primary one for the video.
