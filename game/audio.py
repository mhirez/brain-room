"""Sound effects and a background ambience, all synthesised at start-up (no audio files).

Zaps are soft pitch sweeps (mostly sine); hits and explosions are filtered noise; beeps and chimes
are decaying sines. The background is the server room at night: a slow breathing pad, fan hiss and
the odd echoing data blip, with no beat, in a seamless loop. If the mixer can't start (no audio
device, CI) everything becomes a silent no-op.
"""

from __future__ import annotations

from array import array
import math
import random

import pygame

try:
    import pygame.mixer    # the browser build only loads the mixer when asked by name
except ImportError:        # no mixer at all: Audio below becomes silent
    pass


class Audio:
    def __init__(self, enabled: bool = True):
        self.ok = False
        self.muted = False
        self.music_on = True
        self.sounds: dict[str, list[pygame.mixer.Sound]] = {}
        self.music: pygame.mixer.Sound | None = None
        self._next: dict[str, int] = {}
        self._cooldown: dict[str, int] = {}
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            pygame.mixer.set_num_channels(24)
            self.rate, _, self.channels = pygame.mixer.get_init()
            self._build()
            self.ok = True
        except (pygame.error, TypeError, ValueError, AttributeError):
            self.ok = False

    # --- synthesis -------------------------------------------------------------------------
    def _sound(self, samples: list[float], volume: float) -> pygame.mixer.Sound:
        peak = max(1e-6, max(abs(s) for s in samples))
        k = 32000 * volume / peak
        data = array("h", (int(s * k) for s in samples))
        if self.channels == 2:
            stereo = array("h")
            for v in data:
                stereo.append(v)
                stereo.append(v)
            data = stereo
        return pygame.mixer.Sound(buffer=data.tobytes())

    def _zap(self, seconds, f0, f1, square=0.5, noise=0.0, rng=None, curve=2.0):
        n = int(self.rate * seconds)
        out, phase = [], 0.0
        for i in range(n):
            t = i / n
            f = f1 + (f0 - f1) * (1 - t) ** curve
            phase += 2 * math.pi * f / self.rate
            s = math.sin(phase)
            tone = (1 - square) * s + square * (1 if s >= 0 else -1) * 0.6
            env = (1 - t) ** 1.5 * min(1.0, i / (self.rate * 0.002) + 0.02)
            out.append(env * (tone + (noise * (rng.random() * 2 - 1) if noise else 0.0)))
        return out

    def _noise(self, seconds, cutoff0, cutoff1, rng, decay=1.5, thump=0.0):
        n = int(self.rate * seconds)
        out, lp, phase = [], 0.0, 0.0
        for i in range(n):
            t = i / n
            cutoff = cutoff0 + (cutoff1 - cutoff0) * t
            lp += min(1.0, 2 * math.pi * cutoff / self.rate) * ((rng.random() * 2 - 1) - lp)
            phase += 2 * math.pi * (70 - 30 * t) / self.rate
            env = (1 - t) ** decay * min(1.0, i / (self.rate * 0.002) + 0.02)
            out.append(env * (lp * 2.5 + thump * math.sin(phase)))
        return out

    def _bell(self, seconds, partials):
        n = int(self.rate * seconds)
        return [sum(a * math.exp(-i / self.rate / d) * math.sin(2 * math.pi * f * i / self.rate) for f, a, d in partials)
                for i in range(n)]

    def _silence(self, seconds):
        return [0.0] * int(self.rate * seconds)

    def _build(self):
        rng = random.Random(7)
        z = self._zap
        arp = []
        for f in (523, 659, 784, 1047):
            arp += self._bell(0.1, [(f, 1.0, 0.08), (f * 2, 0.25, 0.05)])
        arp += self._bell(0.5, [(1047, 1.0, 0.25), (1568, 0.4, 0.2)])
        win = []
        for f in (392, 523, 659, 784, 1047, 1319):
            win += self._bell(0.13, [(f, 1.0, 0.1), (f * 1.5, 0.3, 0.08)])
        win += self._bell(1.0, [(1047, 1.0, 0.5), (1319, 0.6, 0.4), (1568, 0.5, 0.4)])
        siren = []
        for _ in range(2):
            siren += z(0.3, 520, 780, square=0.05, curve=1.0) + z(0.3, 780, 520, square=0.05, curve=1.0)
        self.sounds = {
            "shoot": [self._sound(z(0.05, 1150 + 60 * k, 520, square=0.08, noise=0.04, rng=rng), 0.11) for k in range(3)],
            "eshoot": [self._sound(z(0.08, 700 + 40 * k, 260, square=0.15, noise=0.05, rng=rng), 0.13) for k in range(3)],
            "snipe": [self._sound(z(0.18, 1800, 300, square=0.1, noise=0.3, rng=rng), 0.32)],
            "hit": [self._sound(self._noise(0.035, 3500, 1800, rng), 0.16) for _ in range(3)],
            "kill": [self._sound(self._noise(0.32, 1100, 180, rng, 1.3, thump=0.9), 0.42) for _ in range(2)],
            "boom": [self._sound(self._noise(1.0, 800, 70, rng, 1.1, thump=1.2), 0.6)],
            "hurt": [self._sound(z(0.28, 320, 90, square=0.25, noise=0.2, rng=rng, curve=1.0), 0.45)],
            "dash": [self._sound(self._noise(0.16, 600, 2800, rng, 0.9), 0.2)],
            "alert": [self._sound(self._bell(0.12, [(988, 1.0, 0.05)]) + self._bell(0.2, [(1318, 1.0, 0.08)]), 0.18)],
            "alarm": [self._sound(siren, 0.12)],
            "laser": [self._sound(z(0.85, 300, 1100, square=0.05, curve=0.6), 0.08)],
            "growl": [self._sound(z(0.5, 90, 150, square=0.35, noise=0.15, rng=rng, curve=0.5), 0.22)],
            "slam": [self._sound(self._noise(0.3, 900, 150, rng, 1.3, thump=1.0), 0.65)],
            "warp": [self._sound(z(0.3, 200, 1700, square=0.2, curve=0.5), 0.22)],
            "pickup": [self._sound(self._bell(0.25, [(1320, 1.0, 0.1), (1980, 0.5, 0.07)]), 0.3)],
            "clear": [self._sound(arp, 0.35)],
            "select": [self._sound(z(0.035, 1500, 1500, 0.5), 0.2)],
            "upgrade": [self._sound(self._bell(0.8, [(523, 1, 0.4), (659, 0.8, 0.4), (784, 0.7, 0.4)]), 0.35)],
            "start": [self._sound(z(0.45, 200, 1200, square=0.3, curve=0.7), 0.25)],
            "win": [self._sound(win, 0.4)],
            "lose": [self._sound(z(1.2, 400, 60, square=0.25, noise=0.1, rng=rng, curve=0.8), 0.4)],
            "sync_in": [self._sound(z(0.35, 900, 140, square=0.2, curve=0.6), 0.25)],
            "sync_out": [self._sound(z(0.25, 140, 700, square=0.2, curve=0.6), 0.2)],
            "hack": [self._sound(self._glitch(rng), 0.4)],
            "denied": [self._sound(z(0.08, 220, 220, 0.4) + self._silence(0.04) + z(0.1, 180, 180, 0.4), 0.2)],
            "charge": [self._sound(self._bell(0.4, [(1760, 1.0, 0.15), (2640, 0.5, 0.1)]), 0.3)],
        }
        self.music = self._sound(self._ambience(rng), 0.2)

    def _glitch(self, rng) -> list[float]:
        """The rewrite: a stuttering, rising digital chirp."""
        out = []
        for k in range(8):
            f = 300 + 180 * k + rng.uniform(-60, 60)
            out += self._zap(0.035, f, f * 1.6, square=0.8)
            out += self._silence(0.01 if k % 3 else 0.02)
        return out + self._zap(0.25, 900, 1800, square=0.4, curve=0.5)

    def _ambience(self, rng) -> list[float]:
        """The server room at night, an 8 s seamless loop with no beat: a soft A-minor pad that
        swells and fades once per loop (slightly detuned, so it shimmers), the hiss of cooling fans,
        and six quiet data blips with echoes. Built at half the mixer rate and doubled (it is all
        low and soft), so it costs little at start-up."""
        length, rate = 8.0, max(8000, self.rate // 2)
        n = int(length * rate)
        pad = [(round(f * length) / length, a) for f, a in               # whole cycles per loop: no seam
               ((110.0, 0.30), (164.81, 0.20), (220.0, 0.12), (261.63, 0.10), (329.63, 0.06))]
        pad += [(f + 1 / length, a * 0.5) for f, a in pad[:3]]           # a slow shimmer against the chord
        tau = 2 * math.pi
        hiss, lp = [0.0] * n, 0.0
        for i in range(n):
            lp += 0.03 * ((rng.random() * 2 - 1) - lp)
            hiss[i] = lp
        fade = int(0.5 * rate)                                           # the noise wraps with a crossfade
        for k in range(fade):
            w = k / fade
            hiss[k] = hiss[k] * w + hiss[n - fade + k] * (1 - w)
        out = [0.0] * n
        for i in range(n):
            t = i / rate
            breathe = 0.7 + 0.3 * math.sin(tau * t / length)
            chord = 0.0
            for f, a in pad:
                chord += a * math.sin(tau * f * t)
            out[i] = chord * breathe * 0.55 + hiss[i] * 0.8
        notes = (880.0, 1046.5, 1174.66, 1318.51, 1567.98)               # A minor pentatonic, up high
        for k in range(6):
            start = int((k + rng.uniform(0.1, 0.8)) * n / 6)
            f = rng.choice(notes)
            for echo in range(3):
                amp, at = 0.16 * 0.45 ** echo, start + int(echo * 0.19 * rate)
                for j in range(int(0.3 * rate)):
                    tt = j / rate
                    out[(at + j) % n] += amp * math.sin(tau * f * tt) * math.exp(-tt * 14)
        full = []                                                        # back up to the mixer rate
        for i in range(n):
            a, b = out[i], out[(i + 1) % n]
            full.append(a)
            full.append((a + b) / 2)
        return full

    # --- playback --------------------------------------------------------------------------
    def play(self, name: str):
        if not self.ok or self.muted or name not in self.sounds:
            return
        variants = self.sounds[name]
        i = self._next.get(name, 0)
        self._next[name] = (i + 1) % len(variants)
        variants[i].play()

    def start_music(self):
        if self.ok and self.music is not None and not self.muted and self.music_on:
            self.music.play(loops=-1, fade_ms=1500)

    def toggle_music(self):
        """N: the background on or off, without muting the effects."""
        self.music_on = not self.music_on
        if not self.ok or self.music is None:
            return
        if self.music_on and not self.muted:
            self.music.play(loops=-1, fade_ms=800)
        else:
            self.music.stop()

    def stop_music(self):
        if self.ok and self.music is not None:
            self.music.stop()

    def pause(self):
        """Hold every sound where it is (the pause screen is silent)."""
        if self.ok:
            pygame.mixer.pause()

    def resume(self):
        if self.ok:
            pygame.mixer.unpause()

    def toggle_mute(self):
        self.muted = not self.muted
        if self.ok:
            if self.muted:
                pygame.mixer.stop()
            elif self.music is not None and self.music_on:
                self.music.play(loops=-1)
