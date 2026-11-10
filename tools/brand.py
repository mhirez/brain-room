from pathlib import Path

import pygame

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "tools" / "web"
ASSETS = ROOT / "game" / "assets"
FONTS = ASSETS / "fonts"
DISPLAY_FONT = FONTS / "BarlowCondensed-Bold.ttf"
BG, CYAN = (27, 30, 36), (72, 200, 220)
WHITE, DIM = (236, 238, 242), (152, 159, 170)
TAGLINE = "THEY BUILT IT TO OBEY. IT LEARNED TO DISAGREE."


def spaced(text: str, font: pygame.font.Font, colour, spacing: int) -> pygame.Surface:
    letters = [font.render(char, True, colour) for char in text]
    width = sum(letter.get_width() for letter in letters) + spacing * (len(letters) - 1)
    image = pygame.Surface((width, font.get_height()), pygame.SRCALPHA)
    x = 0
    for letter in letters:
        image.blit(letter, (x, 0))
        x += letter.get_width() + spacing
    return image.subsurface(image.get_bounding_rect()).copy()


def name_logo(size: int) -> pygame.Surface:
    font = pygame.font.Font(str(DISPLAY_FONT), size)
    return spaced("BRAIN ROOM", font, WHITE, round(size * 0.045))


def wordmark(width: int, height: int, size: int, *, tagline=True) -> pygame.Surface:
    image = pygame.Surface((width, height))
    image.fill(BG)
    name = name_logo(size)
    if tagline:
        font = pygame.font.Font(str(FONTS / "BarlowSemiCondensed-SemiBold.ttf"), round(size * 0.1))
        tag = spaced(TAGLINE, font, DIM, round(size * 0.014))
        gap = round(name.get_height() * 0.32)
        top = (height - name.get_height() - gap - tag.get_height()) // 2
        image.blit(name, name.get_rect(midtop=(width // 2, top)))
        image.blit(tag, tag.get_rect(midtop=(width // 2, top + name.get_height() + gap)))
    else:
        image.blit(name, name.get_rect(center=(width // 2, height // 2)))
    return image


def app_icon(size: int) -> pygame.Surface:
    font = pygame.font.Font(str(DISPLAY_FONT), round(size * 0.82))
    letter = spaced("B", font, BG, 0)
    image = pygame.Surface((size, size))
    image.fill(CYAN)
    image.blit(letter, letter.get_rect(center=(size // 2, size // 2)))
    return image


def main():
    pygame.font.init()
    pygame.image.save(app_icon(64), str(WEB / "favicon.png"))
    pygame.image.save(wordmark(840, 180, 135, tagline=False), str(WEB / "wordmark.png"))
    pygame.image.save(wordmark(1200, 630, 190), str(WEB / "og-image.png"))
    pygame.image.save(app_icon(256), str(ASSETS / "logo.png"))
    pygame.image.save(name_logo(155), str(ASSETS / "title.png"))
    print("logo images written")


if __name__ == "__main__":
    main()
