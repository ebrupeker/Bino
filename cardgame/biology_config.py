from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

CARD_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}

# Allowed colors/systems that will be used to build the biology deck
BIOLOGY_COLORS = ["yesil", "kirmizi", "turuncu", "mavi", "sari"]
BIOLOGY_SYSTEMS = ["dolasim", "solunum", "sindirim", "bosaltim"]

# Wild selection order (clockwise). First four entries correspond to wildcard wheel quadrants.
WILD_COLOR_ORDER = ["mavi", "kirmizi", "sari", "yesil", "turuncu"]
WILD_ANIMATION_COLORS = ["mavi", "kirmizi", "sari", "yesil"]

DRAW_CARD_VALUES = ["+1", "+2", "+3"]
SWAP_CARD_VALUE = "degisim"

COLORED_SPECIAL_COUNTS = {
    "+1": 2,
    "+2": 2,
    "+3": 2,
    "degisim": 2,
}


@dataclass(frozen=True)
class BiologyCardInfo:
    color: str
    system: str
    organ: str
    filename: str


def _normalize(value: str) -> str:
    return value.lower()


def _collect_biology_cards() -> List[BiologyCardInfo]:
    base_dir = Path(__file__).resolve().parent.parent
    assets_path = base_dir / "animation" / "assets"
    cards: List[BiologyCardInfo] = []

    for path in assets_path.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in CARD_IMAGE_EXTENSIONS:
            continue

        name_parts = path.stem.split("_")
        if len(name_parts) < 3:
            continue

        color = _normalize(name_parts[0])
        system = _normalize(name_parts[1])
        organ = "_".join(name_parts[2:])

        if color not in BIOLOGY_COLORS or system not in BIOLOGY_SYSTEMS:
            continue

        cards.append(BiologyCardInfo(color=color, system=system, organ=organ, filename=path.name))

    return cards


BIOLOGY_CARDS: List[BiologyCardInfo] = _collect_biology_cards()

# Special cards (+1, +2, renk degistir etc.) with the number of copies for each.
SPECIAL_CARD_COUNTS: Dict[str, int] = {
    "renk_degistir": 4,
}

# Colour palette (fallbacks) used when a dedicated asset is missing.
FALLBACK_COLOR_MAP: Dict[str, Tuple[int, int, int]] = {
    "yesil": (56, 142, 60),
    "kirmizi": (198, 40, 40),
    "turuncu": (239, 108, 0),
    "mavi": (25, 118, 210),
    "sari": (255, 202, 40),
    "special": (117, 117, 117),
}
