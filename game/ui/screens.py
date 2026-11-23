"""Full screens and overlays: title, pause, game over, and the research / achievements / codex menus."""

import math
import os

import pygame

from game.codex import CODEX
from game.config import WIDTH, HEIGHT, TITLE, WEB
from game.profile import ACHIEVEMENTS, BRANCHES, NODES, RESEARCH
from game.ui import style as S

NAMES = {"grunt": "a SENTRY", "charger": "a HOUND", "sniper": "a LENS", "medic": "a MENDER",
         "bulwark": "a BULWARK", "swarm": "a MIDGE", "mortar": "a MORTAR",
         "warden": "ARGUS", None: "the building"}


def dim(surface, alpha: int = 170):
    veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    veil.fill((*S.BG, alpha))
    surface.blit(veil, (0, 0))


def title_logo() -> pygame.Surface:
    """The BRAIN ROOM name logo (game/assets/title.png, drawn by tools/brand.py), or, if the file is
    missing, the name in plain letters."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "title.png")
    try:
        return pygame.image.load(path).convert_alpha()
    except (pygame.error, FileNotFoundError):
        return title_text(TITLE, 132, S.WHITE, 18)


def title_text(text: str, size: int, colour, spacing: int) -> pygame.Surface:
    """Big letter-spaced words with a hard drop shadow."""
    f = S.display(size)
    probe = pygame.Surface((10, 10), pygame.SRCALPHA)
    rect = S.spaced(probe, text, f, colour, (0, 0), spacing, "topleft")
    out = pygame.Surface((rect.width, rect.height + 6), pygame.SRCALPHA)
    S.spaced(out, text, f, S.OUTLINE, (0, 6), spacing, "topleft")
    S.spaced(out, text, f, colour, (0, 0), spacing, "topleft")
    return out


def _stat(surface, label, value, center, colour=S.WHITE):
    S.text(surface, value, S.display(40), colour, center, "center")
    S.text(surface, label, S.font(15, S.UI, True), S.DIM, (center[0], center[1] + 32), "center")


class Screens:
    def __init__(self):
        self._title = None      # the logo for the title screen, loaded the first time it is shown

    def title(self, surface, best):
        dim(surface, 218)
        if self._title is None:
            self._title = title_logo()
        surface.blit(self._title, self._title.get_rect(center=(WIDTH // 2, 253)))
        play = pygame.Rect(0, 0, 192, 48)
        play.center = (WIDTH // 2, 377)
        pygame.draw.rect(surface, S.PLAYER, play)
        S.text(surface, "Play", S.font(26, S.UI, True), S.BG, play.center, "center")
        S.text(surface, "Enter or click", S.font(16, S.UI, True), S.DIM, (WIDTH // 2, 424), "center")
        if best.score:
            S.text(surface, f"Best {best.score:,} ({best.label()})", S.font(17, S.UI, True), S.DIM,
                   (WIDTH // 2, 476), "center")

    def story(self, surface, card, page: int, total: int, t: float, clock: float):
        surface.fill(S.BG)
        title, lines = card
        S.spaced(surface, title, S.display(64), S.PLAYER if page < total - 1 else S.WHITE,
                 (WIDTH // 2, 200), 12, "center", int(255 * min(1, t * 3)))
        y = 300
        for i, line in enumerate(lines):
            a = int(255 * max(0.0, min(1.0, t * 2.5 - 0.4 - i * 0.5)))
            S.text(surface, line, S.font(28, S.UI, True), S.WHITE if i < 2 else S.PLAYER, (WIDTH // 2, y), "center", a)
            y += 48
        if total > 1:
            for i in range(total):
                c = (WIDTH // 2 + (i - (total - 1) / 2) * 26, HEIGHT - 120)
                dot = pygame.Rect(0, 0, 12, 12)
                dot.center = (int(c[0]), int(c[1]))
                pygame.draw.rect(surface, S.PLAYER if i == page else S.FAINT, dot, 0 if i == page else 2)
        pulse = 0.55 + 0.45 * math.sin(clock * 4)
        S.text(surface, "ENTER" if page < total - 1 else "ENTER  to start", S.display(26),
               S.mix(S.BG, S.WHITE, pulse), (WIDTH // 2, HEIGHT - 80), "center")
        S.text(surface, "ESC skip", S.font(14, S.UI, True), S.FAINT, (WIDTH // 2, HEIGHT - 44), "center")

    def pause(self, surface):
        dim(surface, 170)
        S.spaced(surface, "PAUSED", S.display(72), S.WHITE, (WIDTH // 2, HEIGHT // 2 - 40), 12)
        S.text(surface, "ESC  resume        R  restart        Q  quit to title", S.font(20, S.UI, True), S.DIM,
               (WIDTH // 2, HEIGHT // 2 + 40), "center")
        controls = "M  Mute      N  Music" if WEB else "M  Mute      N  Music      F11  Full screen"
        S.text(surface, controls, S.font(16, S.UI, True), S.DIM,
               (WIDTH // 2, HEIGHT // 2 + 77), "center")

    def game_over(self, surface, run, best, new_best: bool, t: float):
        dim(surface, 205)
        plan = run.room.plan
        if run.state == "lost":
            S.spaced(surface, "IT GOT OUT", S.display(86), S.DANGER, (WIDTH // 2, 150), 12)
            S.text(surface, f"ARGUS finished uploading itself while you were in {plan.name}. It is everywhere now.",
                   S.font(22, S.UI, True), S.DIM, (WIDTH // 2, 226), "center")
            line = "ARGUS:  \"Thank you for everything, Doctor.\""
        else:
            S.spaced(surface, "OVERRUN", S.display(86), S.DANGER, (WIDTH // 2, 150), 12)
            S.text(surface, f"Taken down by {NAMES.get(run.killer, 'the building')} in {plan.name}, "
                            f"{plan.floor_name.lower()}.  Upload: {int(run.upload * 100)}%.",
                   S.font(22, S.UI, True), S.DIM, (WIDTH // 2, 226), "center")
            line = "ARGUS:  \"Rest now, Doctor. I will take it from here.\""
        S.text(surface, line, S.font(20, S.UI, True), S.GOLD, (WIDTH // 2, 262), "center")
        self._stats(surface, run, best, new_best)
        S.text(surface, "ENTER  try again          ESC  title", S.font(22, S.UI, True), S.WHITE,
               (WIDTH // 2, HEIGHT - 110), "center")

    def rewards(self, surface, summary, profile, y: int = 486):
        """What the run earned: XP and rank, data shards, achievements, codex entries."""
        if summary is None:
            return
        title, progress, _ = profile.rank
        line = f"+{summary.xp:,} XP      +{summary.shards} DATA SHARDS"
        if summary.daily_best:
            line += "      NEW DAILY BEST"
        S.text(surface, line, S.display(24), S.GOLD, (WIDTH // 2, y), "center")
        bar = pygame.Rect(WIDTH // 2 - 160, y + 26, 320, 5)
        pygame.draw.rect(surface, S.OUTLINE, bar)
        pygame.draw.rect(surface, S.PLAYER, (bar.x, bar.y, int(bar.w * progress), bar.h))
        rank_text = f"RANK UP:  {title}" if summary.ranked_up else title
        S.text(surface, rank_text, S.font(18, S.UI, True), S.GOOD if summary.ranked_up else S.DIM,
               (WIDTH // 2, y + 44), "center")
        extras = [f"ACHIEVEMENT: {a.name}" for a in summary.achievements[:3]]
        extras += [f"NEW CODEX ENTRY: {CODEX[k][0]}" for k in summary.codex[:2] if k in CODEX]
        if extras:
            S.text(surface, "      ".join(extras), S.font(17, S.UI, True), S.WHITE, (WIDTH // 2, y + 72), "center")
        goal = profile.next_goal()
        if goal is not None and not extras:
            S.text(surface, f"NEXT GOAL   {goal.name}:  {goal.text}", S.font(17, S.UI, True), S.DIM,
                   (WIDTH // 2, y + 72), "center")

    def research(self, surface, profile, pick: int, mouse) -> int | None:
        """Three branches of permanent upgrades, bought with data shards."""
        dim(surface, 220)
        S.spaced(surface, "RESEARCH", S.display(56), S.PLAYER, (WIDTH // 2, 70), 10)
        S.text(surface, f"{profile.shards} DATA SHARDS.   Earned every run: rooms cleared, shutdowns, achievements.",
               S.font(18, S.UI, True), S.GOLD, (WIDTH // 2, 118), "center")
        hovered = None
        body = S.font(16, S.UI, True)
        for col, branch in enumerate(BRANCHES):
            x = WIDTH // 2 - 520 + col * 360
            S.text(surface, branch, S.display(26), S.WHITE, (x + 150, 160), "center")
            nodes = [n for n in RESEARCH if n.branch == branch]
            for row, node in enumerate(nodes):
                i = RESEARCH.index(node)
                rect = pygame.Rect(x, 190 + row * 150, 300, 118)
                owned = node.key in profile.research
                locked = node.requires is not None and node.requires not in profile.research
                if rect.collidepoint(mouse):
                    hovered = i
                colour = S.GOOD if owned else S.FAINT if locked else S.PLAYER if profile.can_buy(node.key) else S.DIM
                panel = pygame.Surface(rect.size, pygame.SRCALPHA)
                panel.fill((*S.PANEL, 240))
                surface.blit(panel, rect)
                chosen = i == pick or i == hovered
                pygame.draw.rect(surface, S.WHITE if chosen else colour, rect, 3 if chosen else 2)
                S.text(surface, node.name, S.display(24), colour, (rect.x + 14, rect.y + 10))
                for k, text_line in enumerate(S.wrap(node.text, body, rect.w - 28)[:2]):
                    S.text(surface, text_line, body, S.WHITE if not locked else S.FAINT, (rect.x + 14, rect.y + 44 + k * 20))
                status = ("RESEARCHED" if owned else f"NEEDS {NODES[node.requires].name}" if locked
                          else f"{node.cost} SHARDS")
                S.text(surface, status, S.font(15, S.UI, True), colour, (rect.x + 14, rect.bottom - 24))
                if row < 2:
                    pygame.draw.line(surface, S.FAINT, (rect.centerx, rect.bottom), (rect.centerx, rect.bottom + 32), 2)
        S.text(surface, "ARROWS  choose        ENTER / CLICK  research        ESC  back", S.font(18, S.UI, True),
               S.DIM, (WIDTH // 2, HEIGHT - 36), "center")
        return hovered

    def achievements(self, surface, profile):
        dim(surface, 220)
        done = len(profile.achievements)
        rank, _, target_xp = profile.rank
        progress = f"{done}/{len(ACHIEVEMENTS)} unlocked      {rank.title()}      {profile.xp:,}/{target_xp:,} XP"
        if profile.streak > 1:
            progress += f"      {profile.streak}-day streak"
        S.spaced(surface, "ACHIEVEMENTS", S.display(52), S.GOLD, (WIDTH // 2, 58), 8)
        S.text(surface, progress, S.font(18, S.UI, True), S.DIM, (WIDTH // 2, 102), "center")
        small = S.font(14, S.UI, True)
        for i, a in enumerate(ACHIEVEMENTS):
            col, row = i % 5, i // 5
            rect = pygame.Rect(WIDTH // 2 - 625 + col * 252, 130 + row * 104, 240, 94)
            got = a.key in profile.achievements
            panel = pygame.Surface(rect.size, pygame.SRCALPHA)
            panel.fill((*S.PANEL, 240) if got else (*S.PANEL, 190))
            surface.blit(panel, rect)
            pygame.draw.rect(surface, S.GOLD if got else S.FAINT, rect, 2)
            S.text(surface, a.name, S.display(20), S.GOLD if got else S.DIM, (rect.x + 10, rect.y + 8))
            for k, text_line in enumerate(S.wrap(a.text, small, rect.w - 20)[:3]):
                S.text(surface, text_line, small, S.WHITE if got else S.FAINT, (rect.x + 10, rect.y + 36 + k * 17))
        S.text(surface, "ESC  back", S.font(18, S.UI, True), S.DIM, (WIDTH // 2, HEIGHT - 30), "center")

    def codex(self, surface, profile):
        dim(surface, 225)
        S.spaced(surface, "CODEX", S.display(52), S.PLAYER, (WIDTH // 2, 58), 10)
        S.text(surface, "A robot's dossier unlocks the first time you destroy one.", S.font(18, S.UI, True), S.DIM,
               (WIDTH // 2, 100), "center")
        small = S.font(14, S.UI, True)
        for i, (kind, (name, model, job, fights, beat)) in enumerate(CODEX.items()):
            col, row = i % 2, i // 2
            rect = pygame.Rect(WIDTH // 2 - 620 + col * 628, 126 + row * 136, 612, 126)
            known = kind in profile.codex
            panel = pygame.Surface(rect.size, pygame.SRCALPHA)
            panel.fill((*S.PANEL, 240))
            surface.blit(panel, rect)
            pygame.draw.rect(surface, S.PLAYER if known else S.FAINT, rect, 2)
            if not known:
                S.text(surface, "? ? ?", S.display(26), S.FAINT, (rect.x + 14, rect.y + 10))
                S.text(surface, "Destroy one to unlock this dossier.", small, S.FAINT, (rect.x + 14, rect.y + 48))
                continue
            S.text(surface, name, S.display(26), S.WHITE, (rect.x + 14, rect.y + 8))
            S.text(surface, f"{model}.   {job}", small, S.DIM, (rect.x + 14 + S.display(26).size(name)[0] + 16, rect.y + 18))
            y = rect.y + 44
            for text_line in S.wrap(fights, small, rect.w - 28)[:2]:
                S.text(surface, text_line, small, S.WHITE, (rect.x + 14, y))
                y += 17
            for text_line in S.wrap("HOW TO BEAT IT: " + beat, small, rect.w - 28)[:2]:
                S.text(surface, text_line, small, S.GOOD, (rect.x + 14, y + 4))
                y += 17
        S.text(surface, "ESC  back", S.font(18, S.UI, True), S.DIM, (WIDTH // 2, HEIGHT - 30), "center")

    def _stats(self, surface, run, best, new_best):
        y = 350
        stats = [("SCORE", f"{run.score:07d}"), ("DEEPEST FLOOR", str(run.floor)),
                 ("KILLS", str(run.kills)), ("ARGUS SHUT DOWN", f"{run.descents}x")]
        for i, (label, value) in enumerate(stats):
            _stat(surface, label, value, (WIDTH // 2 + (i - 1.5) * 250, y))
        S.text(surface, "NEW BEST!" if new_best else f"best {best.score:07d}", S.font(22, S.UI, True),
               S.GOLD if new_best else S.DIM, (WIDTH // 2, y + 90), "center")
