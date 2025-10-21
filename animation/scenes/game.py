import pygame
import pygame.locals as pg
import threading
import time
import random

from audio.audio import *
from .. import constants as c
from ..shared_objects import SharedObjects
from ..opponent_hand import OpponentHand
from ..primary_hand import PrimaryHand
from ..assets import WILDWHEEL
from ..assets import WILDMORPH
from ..assets import DECK, CARDS, BDECK
from ..card import Card
from ..animatable import Animatable
from ..helpers import put_felt_background
from ..util import next_frame
from cardgame.biology_config import WILD_ANIMATION_COLORS

# Maps id => Card
cards = {}
# Maps id => OpponentHand
opponents = {}

hand = PrimaryHand()

wildcard_quadrants = []
wildcard_background = None
debug_system_label = None
input_overlay = None
escape_cancelled_flag = False



def track_card(surface, id):
    """
    This function can be used to tell the animation module to start tracking a
    card, opening up several animation functions.
    Parameters:
    -----------
    surface: a pygame.Surface object
    id: a unique identifier for this card (you must keep track of this
    identifier!)
    """
    cards[id] = Card(surface)


def add_opponent(name):
    """
    Adds an opponent to visual layer of game.
    Parameters:
    -----------
    name: a string that will subsequently be used as a lookup key for
        modifying the visuals of this opponent
    """
    # Temporary value: calling init will set each opponent to a position tuple.
    opponents[name] = None


def play_card(id, wild_color=None):
    """
    Moves the card with the given id to the play deck. This function operates
    on the primary player in the game.
    Parameters:
    -----------
    id: integer value uniquely identifying a card
    wild_color: (optional) int 0, 1, 2, or 3 (see _wildcard_morph)
    """
    if wild_color is not None:
        random_offset = False
    else:
        random_offset = True

    card = cards[id]
    hand.play(card, random_offset)

    if wild_color is not None:
        args = [wild_color, c.WILDCARD_MORPH_WAIT_TIME]
        threading.Thread(target=_wildcard_morph,
                         args=args, daemon=True).start()


def draw_card(id):
    """
    The card with the given id moves from the draw deck into the player's hand.
    The card becomes the focus card.
    Parameters:
    -----------
    id: integer value uniquely identifying a card
    """
    card = cards[id]

    # Avoid a card being in animatables list more than once if it has been
    # recycled
    animatables = SharedObjects.get_animatables()
    if card in animatables:
        animatables.remove(card)

    hand.draw(card)


def opponent_draw_card(opponent_id):
    """
    Moves an uno card from the draw deck to the opponent's hand.
    Parameters:
    -----------
    opponent_id: integer value uniquely identifying an opponent
    """
    opponent_hand = opponents[opponent_id]
    opponent_hand.draw()


def opponent_play_card(opponent_id, card_id, wild_color=None):
    """
    The card is revealed and moved to the play deck.
    Parameters:
    -----------
    opponent_id: integer value uniquely identifying an opponent
    card_id: integer value uniquely identifying a card
    wild_color: (optional) int 0, 1, 2, or 3 (see _wildcard_morph)
    """
    if wild_color is not None:
        random_offset = False
    else:
        random_offset = True

    opponent_hand = opponents[opponent_id]
    card = cards[card_id]
    opponent_hand.play(card, random_offset)

    if wild_color is not None:
        args = [wild_color, c.WILDCARD_MORPH_WAIT_TIME]
        threading.Thread(target=_wildcard_morph,
                         args=args, daemon=True).start()


def shift_hand(right=True):
    """
    Shifts the focus of the player's hand.
    Parameters:
    -----------
    right: if True, focus moves to the right. Else, moves to the left.
    Returns:
    --------
    The id of the new focus card
    """
    card = hand.shift(right)

    for cid in cards:
        if cards[cid] == card:
            return cid

    # Card should have been found
    raise Exception


def draw_to_play_deck(id):
    """
    Reveals a card on top of the draw deck and moves it to the play deck. Used
    at the beginning of game to follow conventional Uno rules of flipping the
    top card of draw deck to become the first play card.
    """
    card = cards[id]
    animatables = SharedObjects.get_animatables()
    animatables.append(card)

    # Move card to correct position and scale
    card.instant_scale(c.DRAW_DECK_SCALE)
    card.instant_move(x=c.DRAW_DECK_CENTER_X, y=c.DRAW_DECK_CENTER_Y)

    # Slide card from draw deck to play deck (scaling appropriately)
    card.move(
        new_centerx=c.PLAY_DECK_CENTER_X,
        new_centery=c.PLAY_DECK_CENTER_Y
    )

    card.scale(
        from_scale=c.DRAW_DECK_SCALE,
        to_scale=c.PLAY_DECK_SCALE
    )


def get_focus_id():
    """
    Returns the id of the focus card. If the player has no cards,
    -1 is returned.
    """
    try:
        card = hand.cards[hand.focus_index]
    except:
        return -1

    for cid in cards:
        if cards[cid] == card:
            return cid


def _wildcard_morph(color, wait):
    """
    The wildcard morphs into the chosen color after the given wait time. Use 
    after the player has picked their color from the wildcard wheel.
    Parameters:
    -----------
    color: 0 -> mavi, 1 -> kirmizi, 2 -> sari, 3 -> yesil
    wait: duration in seconds
    """
    if color < 0 or color >= len(WILD_ANIMATION_COLORS):
        raise Exception
    color_name = WILD_ANIMATION_COLORS[color]
    surf = WILDMORPH.get(color_name)
    if surf is None:
        raise Exception

    if wait < 0:
        raise Exception

    time.sleep(wait)

    sfx_morph.play()

    blank_card = Card(surf, c.PLAY_DECK_SCALE)
    blank_card.instant_move(c.PLAY_DECK_CENTER_X, c.PLAY_DECK_CENTER_Y)
    blank_card.scale(
        from_scale=0.0001,
        to_scale=c.PLAY_DECK_SCALE,
        duration=1
    )

    SharedObjects.get_disposable_animatables().append(blank_card)


def show_wildcard_wheel():
    """
    The wildward wheel is displayed in the middle of the screen.
    """
    # Check if quadrants are already being tracked in animatables. (Checking
    # just one quadrant should be sufficient)
    disposable_animatables = SharedObjects.get_disposable_animatables()
    if wildcard_quadrants[0] in disposable_animatables:
        return

    disposable_animatables.append(wildcard_background)

    cx, cy = (c.HALF_WINWIDTH, c.HALF_WINHEIGHT)
    # All quadrants will have the same dimensions
    quad_w, quad_h = wildcard_quadrants[0].rect.size

    quad_w /= 2
    quad_h /= 2

    # Position blue (top-right)
    wildcard_quadrants[0].instant_move(cx + quad_w, cy - quad_h)
    # Position blue (top-left)
    wildcard_quadrants[1].instant_move(cx - quad_w, cy - quad_h)
    # Position blue (bottom-left)
    wildcard_quadrants[2].instant_move(cx - quad_w, cy + quad_h)
    # Position blue (bottom-right)
    wildcard_quadrants[3].instant_move(cx + quad_w, cy + quad_h)

    # Start tracking quadrants in animatables
    for q in wildcard_quadrants:
        disposable_animatables.append(q)


def hide_wildcard_wheel():
    """
    The wildcard wheel is removed from the middle of the screen. Will raise an
    error if show_wildcard_wheel was not called before this function.
    """
    try:
        disposable_animatables = SharedObjects.get_disposable_animatables()
        for q in wildcard_quadrants:
            disposable_animatables.remove(q)
        disposable_animatables.remove(wildcard_background)
    except:
        raise Exception


def switch_wildcard_wheel_focus(quadrant):
    """
    The quadrant passed in move outward slightly and the rest of the quadrants
    get tucked in. There function is purely an animation and keeping track of
    which color is focused is up to the caller of this function.

    Parameters:
    -----------
    quadrant: an integer representing one of the four quadrants, which are laid
        out in the traditional mathematical way:
            0 -> Q1 (top-right)    : Mavi
            1 -> Q2 (top-left)     : Kirmizi
            2 -> Q3 (bottom-left)  : Sari
            3 -> Q4 (bottom-right) : Yesil
    """
    # Check for valid input
    if quadrant < 0 or quadrant > 3:
        raise Exception

    # DRY violation: this code was copied from above

    cx, cy = (c.HALF_WINWIDTH, c.HALF_WINHEIGHT)
    # All quadrants will have the same dimensions
    quad_w, quad_h = wildcard_quadrants[0].rect.size

    quad_w /= 2
    quad_h /= 2

    quad_position = [(1, -1), (-1, -1), (-1, 1), (1, 1)]

    tuck_in = set([0, 1, 2, 3])

    tuck_in = tuck_in.difference(set([quadrant]))

    for q in tuck_in:
        x, y = quad_position[q]
        wildcard_quadrants[q].move(
            new_centerx=cx + x*quad_w,
            new_centery=cy + y*quad_h,
            duration=c.SHIFT_HAND_DURATION
        )

    x, y = quad_position[quadrant]
    wildcard_quadrants[quadrant].move(
        new_centerx=cx + x*quad_w + x*c.WILDCARD_WHEEL_FOCUS_DISTANCE,
        new_centery=cy + y*quad_h + y*c.WILDCARD_WHEEL_FOCUS_DISTANCE,
        duration=c.SHIFT_HAND_DURATION
    )


def update_debug_system(system_name):
    """No-op retained for backward compatibility."""
    global debug_system_label
    if debug_system_label is not None:
        animatables = SharedObjects.get_animatables()
        if debug_system_label in animatables:
            animatables.remove(debug_system_label)
        debug_system_label = None


def _cleanup_input_overlay():
    global input_overlay
    if input_overlay is not None:
        disposable = SharedObjects.get_disposable_animatables()
        for item in input_overlay:
            if item in disposable:
                disposable.remove(item)
        input_overlay = None


def prompt_for_card_explanation(card):
    """
    Displays a text input overlay asking the player to describe the selected card.
    Returns the entered description or None if cancelled.
    """
    global input_overlay

    surface_height = SharedObjects.get_surface().get_rect().h
    title_font = pygame.font.SysFont("Arial", round(0.06 * surface_height), bold=True)
    base_font = pygame.font.SysFont("Arial", round(0.04 * surface_height))
    overlay_surf = pygame.Surface((c.WINWIDTH, c.WINHEIGHT), pygame.SRCALPHA)
    overlay_surf.fill((0, 0, 0, 210))
    overlay = Animatable(overlay_surf, c.HALF_WINWIDTH, c.HALF_WINHEIGHT, hidden=False)

    prompt_text = "Bino kartını açıkla"

    def render_wrapped(text, font, color, max_width):
        words = text.split()
        if not words:
            surface = font.render("", True, color)
            return surface
        lines = []
        current = words[0]
        for word in words[1:]:
            test_line = current + " " + word
            if font.size(test_line)[0] <= max_width:
                current = test_line
            else:
                lines.append(current)
                current = word
        lines.append(current)
        surfaces = [font.render(line, True, color) for line in lines]
        width = min(max_width, max(s.get_width() for s in surfaces))
        height = sum(s.get_height() for s in surfaces)
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        y = 0
        for s in surfaces:
            rect = s.get_rect()
            rect.centerx = width // 2
            rect.y = y
            surface.blit(s, rect)
            y += s.get_height()
        return surface

    max_text_width = int(c.WINWIDTH * 0.6)
    prompt_surf = render_wrapped(prompt_text, title_font, (255, 255, 255), max_text_width)
    prompt = Animatable(prompt_surf, c.HALF_WINWIDTH, c.HALF_WINHEIGHT * 0.35, hidden=False)

    instruction_surf = base_font.render("Kartı Bino'ya açıklayıp Enter'a bas (ESC ile iptal)", True, (200, 200, 200))
    instruction = Animatable(instruction_surf, c.HALF_WINWIDTH, c.HALF_WINHEIGHT * 0.45, hidden=False)

    input_text = ""
    input_surf = base_font.render("", True, (255, 255, 0))
    input_field = Animatable(input_surf, c.HALF_WINWIDTH, c.HALF_WINHEIGHT * 0.55, hidden=False)

    pygame.key.start_text_input()
    if pygame.scrap.get_init():
        pygame.scrap.set_mode(pygame.SCRAP_CLIPBOARD)

    disposable = SharedObjects.get_disposable_animatables()
    disposable.append(overlay)
    disposable.append(prompt)
    disposable.append(instruction)
    disposable.append(input_field)
    input_overlay = [overlay, prompt, instruction, input_field]

    accepted_text = None
    esc_cancelled = False
    collecting = True
    try:
        while collecting:
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    collecting = False
                    accepted_text = None
                    esc_cancelled = True
                    break
                if event.type == pygame.KEYDOWN:
                    if event.key == pg.K_RETURN:
                        accepted_text = input_text.strip()
                        collecting = False
                        break
                    elif event.key == pg.K_ESCAPE:
                        accepted_text = None
                        collecting = False
                        esc_cancelled = True
                        break
                    elif event.key == pg.K_BACKSPACE:
                        input_text = input_text[:-1]
                    elif event.key == pg.K_v and (event.mod & (pg.KMOD_CTRL | pg.KMOD_META)):
                        if pygame.scrap.get_init():
                            clipboard = pygame.scrap.get(pygame.SCRAP_TEXT)
                            if clipboard:
                                if isinstance(clipboard, bytes):
                                    try:
                                        clipboard = clipboard.decode("utf-8")
                                    except UnicodeDecodeError:
                                        clipboard = clipboard.decode("latin-1", errors="ignore")
                                input_text += str(clipboard).replace("\r\n", "\n").replace("\r", "\n")
                if event.type == pygame.TEXTINPUT:
                    input_text += event.text

            display_text = input_text + ("|" if pygame.time.get_ticks() // 500 % 2 == 0 else "")
            input_field_surface = render_wrapped(display_text, base_font, (255, 255, 0), max_text_width)
            input_center = input_field.rect.center
            input_field.original_surface = input_field_surface
            input_field.surface = input_field_surface
            input_field.rect = input_field_surface.get_rect(center=input_center)

            next_frame()
    finally:
        pygame.key.stop_text_input()
        _cleanup_input_overlay()
        if esc_cancelled:
            global escape_cancelled_flag
            escape_cancelled_flag = True
    return accepted_text


def consume_escape_cancelled():
    global escape_cancelled_flag
    if escape_cancelled_flag:
        escape_cancelled_flag = False
        return True
    return False


def reset():
    global wildcard_quadrants
    global cards, opponents, hand, debug_system_label

    wildcard_quadrants.clear()
    cards.clear()
    opponents.clear()
    hand = PrimaryHand()

    if debug_system_label is not None:
        animatables = SharedObjects.get_animatables()
        if debug_system_label in animatables:
            animatables.remove(debug_system_label)
    debug_system_label = None


def show():
    """
    Sets the background upon which all animations are drawn. Should be called
    after adding all players and cards.
    """
    global wildcard_background, wildcard_quadrants

    # Get animatables and clear any previous items
    animatables = SharedObjects.get_animatables()
    disposable_animatables = SharedObjects.get_disposable_animatables()
    animatables.clear()
    disposable_animatables.queue.clear()

    base_surf = SharedObjects.get_base_surface()
    base_surf = put_felt_background(base_surf)

    large_font = SharedObjects.get_large_font()

    # Show opponent name titles
    num_opponents = len(opponents)
    for i, name in enumerate(opponents):
        # Set to xy tuple
        # xy tuple for position of opponent hand
        x = (i+1)/(num_opponents+1) * c.WINWIDTH
        y = (1/10) * c.WINHEIGHT
        opponents[name] = OpponentHand(x, y + (1/10) * c.WINHEIGHT)
        name_surf = large_font.render(name, True, (255, 255, 255))
        name_rect = name_surf.get_rect()
        name_rect.center = (x, y)
        base_surf.blit(name_surf, name_rect)

    # Show draw deck
    draw_deck = Animatable(BDECK)
    draw_deck.instant_scale(c.DRAW_DECK_SCALE)
    draw_deck.instant_move(c.DRAW_DECK_CENTER_X, c.DRAW_DECK_CENTER_Y)

    rect = draw_deck.rect
    for i in range(5, 0, -1):
        base_surf.blit(draw_deck.surface, (rect.x - i, rect.y + 3*i))

    # No offset
    base_surf.blit(draw_deck.surface, rect)

    colors = [WILDWHEEL[color] for color in WILD_ANIMATION_COLORS]

    # Initalize wildcard wheel quadrants
    for color in colors:
        wildcard_quadrants.append(Animatable(color, hidden=False))
        wildcard_quadrants[-1].instant_scale(c.WILDCARD_WHEEL_SIZE)

    # Whilecard wheel background
    dim = c.WILDCARD_WHEEL_BACKGROUND_SIZE

    # Surface will be colored as border color and then filled in with
    # the background color
    background = pygame.Surface((dim, dim))
    background.fill(c.WILDCARD_BACKGROUND_BORDER_COLOR)

    t = c.WILDCARD_BORDER_THICKNESS
    interior = pygame.Surface((dim*t, dim*t))
    interior.fill(c.WILDCARD_BACKGROUND_COLOR)

    # Filling in background color
    background.blit(interior, (dim*(1-t)/2, dim*(1-t)/2))

    # Write prompt
    medium_font = SharedObjects.get_small_font()
    prompt = medium_font.render(
        "Bir renk sec (yon tuslarini kullan): ", True, (255, 255, 255))
    background.blit(prompt, (dim*(1-t), dim*(1-t)))

    confirm_msg = medium_font.render(
        "Secmek icin enter'a bas", True, (255, 255, 255))
    rect = confirm_msg.get_rect()
    # Position centered horizontally and 90% down the square
    rect.center = (dim*0.5, dim*0.9)
    background.blit(confirm_msg, rect)

    # Make the background an animatable for future drawi
    wildcard_background = Animatable(
        surface=background,
        centerx=c.HALF_WINWIDTH,
        centery=c.HALF_WINHEIGHT,
        hidden=False
    )

    update_debug_system(None)
