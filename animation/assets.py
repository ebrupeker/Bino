import pygame
from pathlib import Path
from typing import Dict, Tuple

from cardgame.biology_config import (
    BIOLOGY_CARDS,
    BIOLOGY_COLORS,
    DRAW_CARD_VALUES,
    SWAP_CARD_VALUE,
    FALLBACK_COLOR_MAP,
)

pygame.font.init()

ASSETS_PATH = Path(__file__).resolve().parent / "assets"


def _load_image(filename: str) -> pygame.Surface:
    return pygame.image.load(str(ASSETS_PATH / filename))


def _load_first_existing(basename: str) -> pygame.Surface:
    for ext in (".png", ".jpg", ".jpeg"):
        candidate = ASSETS_PATH / f"{basename}{ext}"
        if candidate.exists():
            return pygame.image.load(str(candidate))
    raise FileNotFoundError(f"Kart görseli bulunamadı: {basename}(.png/.jpg/.jpeg)")


def _build_placeholder(color: Tuple[int, int, int], text: str) -> pygame.Surface:
    width, height = 200, 300
    surface = pygame.Surface((width, height))
    surface.fill(color)
    border_color = (255, 255, 255)
    pygame.draw.rect(surface, border_color, surface.get_rect(), width=6)

    font = pygame.font.SysFont("arial", 36)
    text_surf = font.render(text, True, border_color)
    text_rect = text_surf.get_rect()
    text_rect.center = (width // 2, height // 2)
    surface.blit(text_surf, text_rect)
    return surface


LOGO = _load_image("Logo.png")
DASH = _load_image("Dashed_Border.png")
DECK = _load_image("Deck.png")
BDECK = _load_image("Bordered_Deck.png")
BLANK = _load_image("Blank.png")
FELT = _load_image("Green_Felt.jpg")
INSTRUCTIONS_LEFT = _load_image("instructions_left.png")
INSTRUCTIONS_RIGHT = _load_image("instructions_right.png")

WILDWHEEL = {
    "yesil": _load_image("Wildwheel_Green.png"),
    "kirmizi": _load_image("Wildwheel_Red.png"),
    "turuncu": _load_image("Wildwheel_Red.png"),
    "mavi": _load_image("Wildwheel_Blue.png"),
    "sari": _load_image("Wildwheel_Yellow.png"),
}

WILDMORPH = {
    "yesil": _load_image("Green_Wild.png"),
    "kirmizi": _load_image("Red_Wild.png"),
    "turuncu": _load_image("Red_Wild.png"),
    "mavi": _load_image("Blue_Wild.png"),
    "sari": _load_image("Yellow_Wild.png"),
}


def _biology_key(color: str, system: str, organ: str) -> str:
    return f"{color.lower()}_{system.lower()}_{organ.lower()}"


BIOLOGY_CARD_SURFACES: Dict[str, pygame.Surface] = {}

for info in BIOLOGY_CARDS:
    try:
        surface = _load_image(info.filename)
    except FileNotFoundError:
        fallback_color = FALLBACK_COLOR_MAP.get(info.color, FALLBACK_COLOR_MAP["special"])
        surface = _build_placeholder(fallback_color, info.organ.replace("_", " "))
    BIOLOGY_CARD_SURFACES[_biology_key(info.color, info.system, info.organ)] = surface


COLORED_SPECIAL_SURFACES: Dict[Tuple[str, str], pygame.Surface] = {}
for color in BIOLOGY_COLORS:
    for value in DRAW_CARD_VALUES + [SWAP_CARD_VALUE]:
        basename = f"{color}_{value}"
        surf = _load_first_existing(basename)
        COLORED_SPECIAL_SURFACES[(color, value)] = surf

SPECIAL_CARD_SURFACES: Dict[str, pygame.Surface] = {
    "renk_degistir": _load_image("Wild.png"),
}

# Legacy CARDS dict used by intro animation – populate with biology and special cards.
CARDS: Dict[str, pygame.Surface] = {}
for key, surface in BIOLOGY_CARD_SURFACES.items():
    CARDS[key.upper()] = surface
for (color, value), surface in COLORED_SPECIAL_SURFACES.items():
    CARDS[f"{color}_{value}".upper()] = surface
for value, surface in SPECIAL_CARD_SURFACES.items():
    CARDS[f"SPECIAL_{value.upper()}"] = surface


def get_biology_surface(color: str, system: str, organ: str) -> pygame.Surface:
    key = _biology_key(color, system, organ)
    try:
        return BIOLOGY_CARD_SURFACES[key]
    except KeyError as exc:
        fallback = _build_placeholder(FALLBACK_COLOR_MAP.get(color, FALLBACK_COLOR_MAP["special"]), organ.replace("_", " "))
        BIOLOGY_CARD_SURFACES[key] = fallback
        CARDS[key.upper()] = fallback
        return fallback


def get_special_surface(value: str) -> pygame.Surface:
    surface = SPECIAL_CARD_SURFACES.get(value)
    if surface is not None:
        return surface

    fallback = _build_placeholder(FALLBACK_COLOR_MAP["special"], value)
    SPECIAL_CARD_SURFACES[value] = fallback
    CARDS[f"SPECIAL_{value.upper()}"] = fallback
    return fallback


def get_colored_special_surface(color: str, value: str) -> pygame.Surface:
    key = (color, value)
    if key not in COLORED_SPECIAL_SURFACES:
        raise KeyError(f"Görsel bulunamadı: {color}_{value}")
    return COLORED_SPECIAL_SURFACES[key]
