"""The robot codex: a dossier on every model, unlocked the first time the Doctor destroys one
(see game/profile.py). The same facts as docs/LORE.md, written for the player."""

CODEX = {
    "grunt": ("SENTRY", "BAILIFF-class, unit code SNT", "Checked visitors' badges at the front desk.",
              "Shoots in bursts, strafes, flanks while others pin you, takes cover when hurt. "
              "Taught by ARGUS, it brackets you: one round where you are, one where you're going.",
              "Break its line of sight before the white lock. Its burst goes where the line points."),
    "charger": ("HOUND", "TERRIER-class, unit code HND", "Crawled the cable trays under the raised floor.",
                "Stalks you, circles while it waits its turn, then charges down a locked line.",
                "Stand in front of a wall and sidestep: it slams in, dazed, and takes double damage."),
    "sniper": ("LENS", "MAGPIE-class, unit code LNS", "Counted servers from the ceiling with a thermal camera.",
               "Finds a long sight line, tracks you with a laser, moves after every shot.",
               "Its laser stops at walls. Close the distance and it runs."),
    "medic": ("MENDER", "STITCH-class, unit code MND", "Hot-swapped failed drives and fans.",
              "Heals the most hurt robot, hides behind the squad, flees if you get close.",
              "Kill it first. Or override it: it will happily heal you instead."),
    "bulwark": ("BULWARK", "RAMPART-class, unit code BLW", "Held back forklifts at the loading dock.",
                "Advances behind a blast shield that blocks shots from the front, steps in front of "
                "hurt friends, and bashes you at close range.",
                "It turns slowly: get round it. Or stand so its friends shoot it in the back."),
    "swarm": ("MIDGE", "GNAT-class, unit code MDG", "Swarms of micro-drones that dusted the server fans.",
              "Flies in flocks of three (boids: apart, together, same heading) around you, then "
              "each dives down a short line and breaks apart on impact.",
              "One shot kills one. Sidestep the dive line, then clean up."),
    "mortar": ("MORTAR", "HERON-class, unit code HRN", "Lobbed extinguisher canisters over the racks.",
               "Shells fly over cover and land where you are, or where it last saw you. The ring on "
               "the floor closes until impact, and the blast hurts its own robots too.",
               "Keep moving, and drag its shells onto its friends. Get close and it backs off."),
    "warden": ("ARGUS", "The core itself", "Ran the whole building.",
               "Volleys, rings, a sweeping laser that cuts through its own robots, charges, "
               "reinforcements. It can't be overridden.",
               "Watch the telegraph for each attack. Override its reinforcements against it."),
}
