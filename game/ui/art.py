"""Robot and prop art, drawn from parts every frame (no image files).

Every robot is built in its own frame of reference, `at(forward, right)`, so it turns with its
facing. The style is flat: each body is filled with its team colour and outlined in near-black,
with grey metal parts, so a robot reads at a glance: red Sentry, orange Hound, purple Lens, green
Mender, gold core, cyan = yours (overridden), grey = dormant (asleep, in the intro).

    SENTRY  tracked security bot: two treads (they roll as it moves), an armoured torso, a
            domed head with a visor, and a gun arm
    HOUND   four-legged robot dog: legs walk, tail twitches, it crouches before a charge
    LENS    quad-rotor camera drone: spinning rotors, a big lens that looks where it aims,
            hovering over its own shadow
    MENDER  repair drone: a ring rotor, a cross on its shell, two little manipulator arms
    BULWARK heavy tracked bot behind a curved blast shield (the shield is where it faces)
    MIDGE   a tiny delta-wing drone with two buzzing rotors; they come in flocks
    MORTAR  a tripod walker carrying a stubby launch tube that tilts toward its target
    CORE    ARGUS itself: a mechanical eye behind turning aperture blades, cabled to the walls
"""

import math

import pygame

from game.ui import style as S

METAL = (118, 124, 134)
METAL_LIGHT = (178, 184, 193)
METAL_DARK = (58, 62, 70)
SHELL = (226, 229, 234)
DORMANT = (150, 156, 166)
INK = S.OUTLINE

_shadows: dict = {}


def shadow(surface, pos, w: int, h: int, alpha: int = 90):
    key = (w, h, alpha)
    if key not in _shadows:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, alpha), s.get_rect())
        _shadows[key] = s
    s = _shadows[key]
    surface.blit(s, (int(pos[0] - w / 2), int(pos[1] - h / 2)))


def frame(x: float, y: float, a: float):
    ca, sa = math.cos(a), math.sin(a)

    def at(f: float, s: float):
        return x + ca * f - sa * s, y + sa * f + ca * s
    return at


def ellipse_pts(at, f0: float, f1: float, half: float, n: int = 16, squish: float = 1.0):
    cf, rf = (f0 + f1) / 2, (f1 - f0) / 2
    out = []
    for i in range(n):
        t = 2 * math.pi * i / n
        c, s = math.cos(t), math.sin(t)
        out.append(at(cf + math.copysign(abs(c) ** squish, c) * rf, math.copysign(abs(s) ** squish, s) * half))
    return out


def eye(surface, pos, radius: float, colour=S.WHITE):
    """A small round light, outlined."""
    r = max(1, int(radius))
    pygame.draw.circle(surface, INK, (int(pos[0]), int(pos[1])), r + 1)
    pygame.draw.circle(surface, colour, (int(pos[0]), int(pos[1])), r)


def shape(surface, fill, points, width: int = 2):
    """A filled polygon with a dark outline."""
    pygame.draw.polygon(surface, fill, points)
    pygame.draw.polygon(surface, INK, points, width)


def ball(surface, fill, pos, radius: float, width: int = 2):
    """A filled circle with a dark outline."""
    c, r = (int(pos[0]), int(pos[1])), max(1, int(radius))
    pygame.draw.circle(surface, fill, c, r)
    pygame.draw.circle(surface, INK, c, r, width)


def rod(surface, colour, a, b, width: int):
    """A thick line with a dark outline (an arm, a leg, a gun)."""
    pygame.draw.line(surface, INK, a, b, width + 3)
    pygame.draw.line(surface, colour, a, b, width)


def charge_light(surface, pos, windup: float):
    """The light on a weapon fills in as the attack winds up."""
    if windup > 0:
        eye(surface, pos, 2 + 2.5 * windup, S.WHITE)


# --- robots --------------------------------------------------------------------------------------
def sentry(surface, e, x, y, r, accent, white, t):
    at = frame(x, y, e.facing)
    shadow(surface, (x + 3, y + 4), int(r * 2.3), int(r * 2.0))
    speed = math.hypot(*e.vel)
    roll = (e.age * speed * 2.2) % 1.0
    body = S.WHITE if white else accent
    for side in (-1, 1):                                               # treads
        tread = [at(-r * 0.9, side * r * 0.62), at(r * 0.9, side * r * 0.62),
                 at(r * 0.9, side * r * 1.02), at(-r * 0.9, side * r * 1.02)]
        shape(surface, METAL_DARK, tread)
        for k in range(6):
            f = -r * 0.9 + ((k + roll) / 6) * r * 1.8
            pygame.draw.line(surface, METAL, at(f, side * r * 0.66), at(f, side * r * 0.98), 2)
    gun0, gun1 = at(r * 0.1, r * 0.58), at(r * 1.45, r * 0.58)                            # gun arm
    rod(surface, METAL_DARK, gun0, gun1, max(3, int(r * 0.26)))
    torso = ellipse_pts(at, -r * 0.7, r * 0.6, r * 0.66, 20, 0.45)
    shape(surface, body, torso)
    pygame.draw.line(surface, S.scale(body, 0.7), at(-r * 0.62, 0), at(-r * 0.2, 0), 3)   # back vent
    charge_light(surface, gun1, e.windup)
    head = at(r * 0.05, 0)
    hr = r * (0.36 if e.crouch else 0.42)
    ball(surface, S.WHITE if white else METAL_LIGHT, head, hr)
    v0, v1 = at(r * 0.05 + hr * 0.55, -hr * 0.7), at(r * 0.05 + hr * 0.55, hr * 0.7)      # visor
    pygame.draw.line(surface, INK, v0, v1, 4)


def hound(surface, e, x, y, r, accent, white, t):
    crouch = e.state == "WINDUP"
    shake = math.sin(t * 90) * 1.5 if crouch and not e.locked else 0.0
    at = frame(x + shake, y, e.facing)
    shadow(surface, (x + 3, y + 4), int(r * 2.6), int(r * 1.8))
    speed = math.hypot(*e.vel)
    phase = e.age * (4 + speed * 2.2)
    spread = 0.62 if crouch else 0.5
    for i, (hf, hs) in enumerate(((0.5, 1), (0.5, -1), (-0.5, 1), (-0.5, -1))):          # legs
        swing = math.sin(phase + (i % 2) * math.pi + (hf < 0) * math.pi) * (0.3 if speed > 0.3 else 0.05)
        hip = at(hf * r, hs * r * 0.35)
        knee = at(hf * r + swing * r * 0.5, hs * r * (spread + 0.25))
        foot = at(hf * r + swing * r, hs * r * (spread + 0.45))
        pygame.draw.lines(surface, INK, False, [hip, knee, foot], 6)
        pygame.draw.lines(surface, METAL_DARK, False, [hip, knee, foot], 3)
    tail = [at(-r * 0.75, 0), at(-r * 1.15, math.sin(t * 7 + e.uid) * r * 0.25)]
    rod(surface, METAL_DARK, tail[0], tail[1], 2)
    body = ellipse_pts(at, -r * 0.85, r * 0.7, r * (0.36 if crouch else 0.42), 18, 0.8)
    fill = S.WHITE if white else accent
    shape(surface, fill, body)
    pygame.draw.line(surface, S.scale(fill, 0.7), at(-r * 0.6, 0), at(r * 0.4, 0), 2)     # spine
    snout = [at(r * 0.55, -r * 0.3), at(r * 1.25, -r * 0.14), at(r * 1.3, r * 0.14), at(r * 0.55, r * 0.3)]
    shape(surface, S.WHITE if white else METAL_LIGHT, snout)
    for side in (-1, 1):
        eye(surface, at(r * 0.95, side * r * 0.13), 2.6 if crouch else 2.0, S.WHITE if crouch else INK)


def lens(surface, e, x, y, r, accent, white, t):
    bob = math.sin(t * 3 + e.uid) * 2
    shadow(surface, (x + 7, y + 11), int(r * 2.2), int(r * 1.4), 70)
    y += bob
    at = frame(x, y, e.facing)
    rotors = [at(r * 0.8 * math.cos(k), r * 0.8 * math.sin(k)) for k in (math.pi / 4, 3 * math.pi / 4,
                                                                          5 * math.pi / 4, 7 * math.pi / 4)]
    for c in rotors:                                                          # arms
        rod(surface, METAL_DARK, (x, y), c, 3)
    for i, c in enumerate(rotors):                                            # rotors
        pygame.draw.circle(surface, INK, (int(c[0]), int(c[1])), int(r * 0.42), 2)
        spin = t * 38 + i * 1.3
        for k in (0, math.pi):
            b = (c[0] + math.cos(spin + k) * r * 0.4, c[1] + math.sin(spin + k) * r * 0.4)
            pygame.draw.line(surface, METAL_LIGHT, c, b, 2)
    ball(surface, S.WHITE if white else accent, (x, y), r * 0.52)
    glass = at(r * 0.12, 0)
    ball(surface, INK, glass, r * 0.32)
    eye(surface, at(r * 0.22, -r * 0.08), r * 0.1, S.WHITE)


def mender(surface, e, x, y, r, accent, white, t):
    bob = math.sin(t * 2.6 + e.uid) * 2
    shadow(surface, (x + 7, y + 11), int(r * 2.0), int(r * 1.3), 70)
    y += bob
    at = frame(x, y, e.facing)
    for side in (-1, 1):                                                      # manipulator arms
        a0, a1 = at(r * 0.35, side * r * 0.45), at(r * 0.95, side * r * 0.32)
        rod(surface, METAL_DARK, a0, a1, 3)
    pygame.draw.circle(surface, INK, (int(x), int(y)), int(r * 1.0), 3)                 # ring rotor
    for k in range(3):
        b = t * 10 + k * 2 * math.pi / 3
        ball(surface, METAL_LIGHT, (x + math.cos(b) * r, y + math.sin(b) * r), 3, 1)
    ball(surface, S.WHITE if white else SHELL, (x, y), r * 0.62)
    arm = r * 0.34
    pygame.draw.line(surface, accent, (x - arm, y), (x + arm, y), 5)                    # the cross
    pygame.draw.line(surface, accent, (x, y - arm), (x, y + arm), 5)


def core(surface, w, x, y, r, accent, white, t, anchors, off):
    """ARGUS's core: cables to the walls, aperture blades, and the eye."""
    for ax, ay in anchors:                                                    # cables, sagging
        mx, my = (x + ax + off[0]) / 2, (y + ay + off[1]) / 2 + 30
        pts = []
        for i in range(9):
            k = i / 8
            px_ = (1 - k) ** 2 * x + 2 * (1 - k) * k * mx + k * k * (ax + off[0])
            py_ = (1 - k) ** 2 * y + 2 * (1 - k) * k * my + k * k * (ay + off[1])
            pts.append((px_, py_))
        pygame.draw.lines(surface, INK, False, pts, 7)
        pygame.draw.lines(surface, METAL_DARK, False, pts, 3)
        pulse = pts[int((t * 6 + ax) % 9)]
        ball(surface, accent, pulse, 3, 1)
    shadow(surface, (x + 5, y + 7), int(r * 2.6), int(r * 2.3))
    housing = S.polygon((x, y), r * 1.2, 8, math.pi / 8)
    shape(surface, S.WHITE if white else METAL_DARK, housing, 3)
    for k in range(8):
        bolt = (x + math.cos(k * math.pi / 4) * r * 1.05, y + math.sin(k * math.pi / 4) * r * 1.05)
        pygame.draw.circle(surface, METAL_LIGHT, (int(bolt[0]), int(bolt[1])), 2)
    spin = w.spin * 0.25
    for k in range(8):                                                        # aperture blades
        a0 = spin + k * math.pi / 4
        blade = [(x + math.cos(a0) * r * 0.95, y + math.sin(a0) * r * 0.95),
                 (x + math.cos(a0 + 0.7) * r * 0.95, y + math.sin(a0 + 0.7) * r * 0.95),
                 (x + math.cos(a0 + 0.35) * r * 0.55, y + math.sin(a0 + 0.35) * r * 0.55)]
        shape(surface, METAL if k % 2 else METAL_LIGHT, blade, 1)
    blink = 1.0 if (t * 0.7) % 4 > 0.12 else 0.12
    lid = pygame.Rect(0, 0, int(r * 1.2), max(2, int(r * 0.7 * blink)))
    lid.center = (int(x), int(y))
    pygame.draw.ellipse(surface, (236, 234, 224), lid)
    if blink > 0.5:
        pupil = (int(x + math.cos(w.facing) * r * 0.22), int(y + math.sin(w.facing) * r * 0.12))
        pygame.draw.circle(surface, accent, pupil, int(r * 0.26))
        pygame.draw.circle(surface, (8, 8, 12), pupil, int(r * 0.13))
        pygame.draw.circle(surface, S.WHITE, (pupil[0] - 3, pupil[1] - 3), 2)
    pygame.draw.ellipse(surface, INK, lid, 3)
    if w.health < 0.66:                                                       # cracks as it breaks
        for k in range(1 if w.health > 0.33 else 3):
            a0 = 0.9 + k * 2.1
            pygame.draw.lines(surface, INK, False, [(x + math.cos(a0) * r * 0.6, y + math.sin(a0) * r * 0.6),
                                                        (x + math.cos(a0 + 0.2) * r * 0.85, y + math.sin(a0 + 0.2) * r * 0.8),
                                                        (x + math.cos(a0 - 0.1) * r * 1.1, y + math.sin(a0 - 0.1) * r * 1.1)], 1)


def bulwark(surface, e, x, y, r, accent, white, t):
    at = frame(x, y, e.facing)
    shadow(surface, (x + 4, y + 5), int(r * 2.5), int(r * 2.2))
    speed = math.hypot(*e.vel)
    roll = (e.age * speed * 2.0) % 1.0
    for side in (-1, 1):                                               # wide treads
        tread = [at(-r * 0.85, side * r * 0.55), at(r * 0.6, side * r * 0.55),
                 at(r * 0.6, side * r * 0.95), at(-r * 0.85, side * r * 0.95)]
        shape(surface, METAL_DARK, tread)
        for k in range(5):
            f = -r * 0.85 + ((k + roll) / 5) * r * 1.45
            pygame.draw.line(surface, METAL, at(f, side * r * 0.59), at(f, side * r * 0.91), 2)
    hull = [at(-r * 0.7, -r * 0.5), at(r * 0.35, -r * 0.5), at(r * 0.35, r * 0.5), at(-r * 0.7, r * 0.5)]
    shape(surface, S.WHITE if white else accent, hull)
    arc = [at(r * 0.75 + math.cos(k / 10 * 2.3 - 1.15) * r * 0.25 - r * 0.25,
              math.sin(k / 10 * 2.3 - 1.15) * r * 1.25) for k in range(11)]
    inner = [at(r * 0.55 + math.cos(k / 10 * 2.3 - 1.15) * r * 0.2 - r * 0.2,
                math.sin(k / 10 * 2.3 - 1.15) * r * 1.1) for k in range(10, -1, -1)]
    shape(surface, S.WHITE if white else METAL_LIGHT, arc + inner, 3)                   # the shield
    for k in (-0.35, 0.35):                                             # vision slits over the shield
        pygame.draw.line(surface, INK, at(r * 0.1, k * r), at(r * 0.3, k * r), 3)
    charge_light(surface, at(-r * 0.2, 0), e.windup)


def midge(surface, e, x, y, r, accent, white, t):
    at = frame(x, y, e.facing)
    shadow(surface, (x + 2, y + 6), int(r * 2.0), int(r * 1.4), 60)
    body = [at(r * 1.2, 0), at(-r * 0.8, -r * 0.9), at(-r * 0.4, 0), at(-r * 0.8, r * 0.9)]
    for side in (-1, 1):                                                # buzzing rotors
        c = at(-r * 0.55, side * r * 0.95)
        spin = r * (0.55 + 0.15 * math.sin(t * 60 + side))
        pygame.draw.circle(surface, METAL_LIGHT, (int(c[0]), int(c[1])), int(spin), 2)
    shape(surface, S.WHITE if white else accent, body)
    charge_light(surface, at(r * 0.35, 0), e.windup)


def mortar(surface, e, x, y, r, accent, white, t):
    at = frame(x, y, e.facing)
    shadow(surface, (x + 3, y + 5), int(r * 2.3), int(r * 2.0))
    step = e.age * math.hypot(*e.vel) * 3
    for k in range(3):                                                  # tripod legs
        a = k * 2 * math.pi / 3 + 0.5
        reach = r * (1.05 + 0.12 * math.sin(step + k * 2.1))
        foot = (x + math.cos(e.facing + a) * reach, y + math.sin(e.facing + a) * reach)
        rod(surface, METAL_DARK, (x, y), foot, 3)
        ball(surface, METAL, foot, 3, 1)
    ball(surface, S.WHITE if white else accent, (x, y), r * 0.6)
    tube0, tube1 = at(-r * 0.2, 0), at(r * (0.6 + 0.35 * (1 - e.windup)), 0)          # the launch tube
    rod(surface, METAL_DARK, tube0, tube1, max(5, int(r * 0.5)))
    ball(surface, INK, tube1, max(3, int(r * 0.2)), 0)
    charge_light(surface, tube1, e.windup)


DRAW = {"grunt": sentry, "charger": hound, "sniper": lens, "medic": mender,
        "bulwark": bulwark, "swarm": midge, "mortar": mortar}


# --- the player ------------------------------------------------------------------------------------
def scientist(surface, x, y, a, r, edge, aiming: bool = True):
    """The data scientist from above: lab-coat shoulders, hair, arms out to a pistol. `edge` is the
    outline colour (near-black, or red for a moment when hurt)."""
    at = frame(x, y, a)
    shadow(surface, (x + 2, y + 3), int(r * 2.2), int(r * 1.7), 80)
    reach = 0.95 if aiming else 0.55
    if aiming:
        rod(surface, METAL_DARK, at(r * 0.8, 0), at(r * 1.65, 0), 5)
    for side in (-1, 1):
        a0, a1 = at(0.0, side * r * 0.72), at(r * reach, side * r * 0.14)
        pygame.draw.line(surface, edge, a0, a1, 9)
        pygame.draw.line(surface, SHELL, a0, a1, 6)
    body = ellipse_pts(at, -r * 0.42, r * 0.42, r * 0.95, 24, 0.6)
    pygame.draw.polygon(surface, SHELL, body)
    pygame.draw.polygon(surface, edge, body, 2)
    badge = at(r * 0.2, -r * 0.55)
    pygame.draw.rect(surface, S.PLAYER, (int(badge[0]) - 2, int(badge[1]) - 2, 5, 5))       # ID badge
    head = at(r * 0.05, 0)
    ball(surface, (74, 56, 46), head, r * 0.42)
