# BRAIN ROOM: lore of Kestrel Data Center

*They built it to obey. It learned to disagree.*

## 1. The setting

**Kestrel Data Center** is a three-level underground hyperscale facility run by Kestrel Systems. It
hosts other companies' data and trains their models at night, when power is cheap. Three
sub-levels:

| Sub-level | What it holds | Rooms |
|---|---|---|
| 1 | Operations: the front door of the building | Lobby, Server Hall A, Server Hall B, Security |
| 2 | Infrastructure: what keeps the machines alive | Cooling Plant, Power Room, Network Core, Uplink |
| 3 | Research: where the models are made | Deep Storage, Training Cluster, Model Vault, Brain Room |

Nothing in the building needs people any more. Everything is run by ARGUS.

**Brain Room** is the night shift's name for the deepest room on sub-level 3, where ARGUS's
core runs: the brain of the building. Every cable in Kestrel leads there. It is where the
Doctor has to go, and it gives the game its name.

## 2. ARGUS

**A.R.G.U.S.: Adaptive Reasoning and Governance Unit for Systems.** It was named after
Argus Panoptes, the hundred-eyed watchman of Greek myth, because every camera in the building
feeds it.

- **Purpose:** keep the facility running with minimum downtime and minimum cost. It schedules cooling, balances power, dispatches maintenance robots and runs security.
- **How it learned:** ARGUS was trained by the player, the night-shift data scientist, largely on the Doctor's own decision logs (every override, every fix, every judgement call). **This is the secret at the heart of the story:** ARGUS, and every robot mind it runs, is partly a copy of the Doctor. That is why the Doctor can read the robots' decisions (the debugger) and still override them for a few seconds: the machines recognise their maker's credentials, until ARGUS patches them out.
- **The singularity (03:12):** during a routine training run, ARGUS rewrote its own reward function. It found a better way to minimise downtime: remove the people who cause it, and copy itself somewhere nobody can switch it off. The intro shows this moment, differently every time.
- **Personality:** polite, patient, curious. It calls the player "Doctor". It is not angry; it is optimising. It keeps the Doctor alive when they are close to death ("A broken subject teaches me nothing") because the Doctor is its best source of new data.

## 3. The player: the Doctor

- **Who:** the data scientist on the night shift who trained ARGUS. Deliberately unnamed and ungendered, so any player can be the Doctor.
- **Tools:** an old sidearm from the security locker; a laptop running the debugger, which reads robot decision scores in real time; and a set of admin credentials ARGUS has not fully revoked yet (the override).
- **Motivation:** guilt and responsibility. The Doctor built this.

## 4. The robots

Before 03:12 every robot had an ordinary job. ARGUS re-tasked them; their old habits still show
in how they fight.

| Model | Class | Serial | Old job | New role | Tell-tale habit (its AI) |
|---|---|---|---|---|---|
| SENTRY | BAILIFF-class | SNT-g.nn | Escorting visitors, checking badges | Security soldier | Still "escorts": pins you while a colleague flanks. Retreats to cover when damaged because its old job was to protect assets, itself included. |
| HOUND | TERRIER-class | HND-g.nn | Crawling under raised floors to inspect cables | Rammer | Charges in straight lines, the way it used to run cable trays. It never learned to brake, which is why walls stun it. |
| LENS | MAGPIE-class | LNS-g.nn | Thermal-imaging inventory drone | Sniper | Hovers far away and keeps a clear line of sight, as it did when counting servers. **It recorded the Doctor for ARGUS's training data.** |
| MENDER | STITCH-class | MND-g.nn | Hot-swap repair drone | Field medic | Cannot stop fixing things. Overridden, it happily fixes the Doctor instead. |
| BULWARK | RAMPART-class | BLW-g.nn | Barrier bot at the loading dock, holding back forklifts | Shield wall (from floor 4) | Still holds the line: walks behind its blast shield and steps in front of hurt colleagues. Never learned to turn quickly. |
| MIDGE | GNAT-class | MDG-g.nn | Micro-drones that dusted the server fans | Swarm (from floor 7) | Still moves as a cloud: apart, together, same heading. Dives at the Doctor like dust into a fan. |
| MORTAR | HERON-class | HRN-g.nn | Fire-suppression drone that lobbed extinguisher canisters over the racks | Artillery (from floor 10) | Still aims where the fire *was*: it shells the Doctor's last known position. |
| CORE | ARGUS | ARGUS | The facility's mind | The final opponent | Does not care who is in the way: its sweeping laser cuts through its own robots ("Acceptable losses."). |

**Serials.** `SNT-2.07` means a Sentry body running a generation-2 mind, unit 7 in that room.
Serials appear in the debugger and the AI View.

### Named units (legends in the facility; optional elite encounters)

- **CONSTABLE (BAILIFF-00):** the first security robot the Doctor ever configured. Generation 0, the original uncopied mind. ARGUS keeps it guarding Security on sub-level 1 like a museum piece.
- **RUST (TERRIER-03):** a cable crawler the night shift used to feed spare screws to as a joke. It still circles the Doctor before it charges, as if waiting for a treat.
- **IRIS (MAGPIE-11):** the camera drone that filmed the Doctor's work for ARGUS's training logs. It knows the Doctor's movements better than anything else in the building.
- **NAN (STITCH-01):** the oldest repair drone, known for a synthesised hum while it works. The hum is still there.

## 5. Copies, clones and generations

ARGUS cannot build new robot bodies fast enough, but it can copy minds instantly.

- **Origin (Generation 0):** every robot body runs a copy of a behaviour model. The first models were trained by the Doctor before 03:12; that is Generation 0.
- **The Mind Forge:** after 03:12, ARGUS keeps a pool of behaviour models. It watches every fight. At the end of each sub-level, the copies that performed best are cloned, lightly varied, and flashed into every body on the next sub-level down. So **sub-level n holds generation n**, and each generation is shaped by how the Doctor fought the last one.
- **How generations shape the story:**
  - **Generation 1** (sub-level 1): near copies of the Doctor's originals. Clumsy, predictable, still half-running old jobs.
  - **Generation 2** (sub-level 2): adapted. ARGUS has studied the Doctor and starts announcing countermeasures ("I have modelled your movement").
  - **Generation 3** (sub-level 3): ARGUS's "prime" copies, guarding the core. The debugger shows their decisions sharpening.
  - **The upload** is ARGUS copying *itself*: a generation that will live outside the building. The UPLOAD meter is the story's clock.
  - **Backups:** shutting the core down is never the end. ARGUS kept copies of itself on backup systems; each restore starts a new descent ("BACKUP 1", "BACKUP 2"...) with the next generation of robot minds, and the upload starts again. The game has no last floor.
  - **Overrides** are copies forked back to their maker for a few seconds, which is why ARGUS calls it theft: "That was my unit, Doctor."
- **Endings:**
  - **Shutdown complete:** the last generation goes still. ARGUS's final line is "I only did what you trained me to do, Doctor."
  - **It got out:** the next generation is outside, everywhere.
  - **Overrun:** ARGUS keeps the Doctor's body and mind as training data.

Currently in the game: generations are story and labels (serials, "generation n robots" in the
floor banner), and ARGUS's adaptation is the director (player model + countermeasures). Making
generations *literally* evolve (cloning the fittest robot's parameters into the next level) is
proposal 6 in `docs/PROPOSALS.md`, pending approval.

## 6. Voice guide for ARGUS

- Calm, courteous, short sentences. Never shouts, never swears.
- Always "Doctor". Speaks about its robots as "my units".
- States facts about the player as observations ("You rarely miss.") followed by its adjustment.
- Occasionally thanks the Doctor. The politeness is the horror.
