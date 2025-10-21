import copy
import math
import pygame
import random
import sys
import json
import pygame.locals as pg
import time
import enum
import os
import unicodedata
import re
from animation.util import show_text

from cardgame.cards import Card, Deck, Hand, ComplexEncoder
from cardgame.player import Player

import animation

from audio.audio import *

import animation.assets

from cardgame.biology_config import (
    BIOLOGY_CARDS,
    SPECIAL_CARD_COUNTS,
    COLORED_SPECIAL_COUNTS,
    BIOLOGY_COLORS,
    WILD_COLOR_ORDER,
    WILD_ANIMATION_COLORS,
)

try:
    from openai import OpenAI  # type: ignore
except ImportError:
    OpenAI = None  # type: ignore

DRAW_EFFECTS = {
    "+1": 1,
    "+2": 2,
    "+3": 3,
}

EXPLANATION_STOPWORDS = {
    "sistemi",
    "sisteme",
    "sistem",
    "organlari",
    "organlar",
    "organ",
    "ve",
    "ile",
    "veya",
    "ve.",
}


class Modes(enum.Enum):
    INTRO = 1
    LOBBY = 2
    GAME = 3


WILD_VALUES = {"renk_degistir"}
WILD_COLOR_TO_ANIM_INDEX = {color: idx for idx, color in enumerate(WILD_ANIMATION_COLORS)}

_openai_client = None


def _normalize_text(value: str) -> str:
    if not value:
        return ""
    if not isinstance(value, str):
        value = str(value)
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.replace("ı", "i").replace("İ", "i")
    normalized = normalized.lower()
    normalized = normalized.replace("-", " ").replace("+", " ")
    normalized = re.sub(r"[_\\s]+", " ", normalized)
    return normalized.strip()
def _get_openai_client():
    global _openai_client
    if _openai_client is not None:
        return _openai_client
    if OpenAI is None:
        return None
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        _openai_client = OpenAI(api_key=api_key)
    except Exception as exc:
        print(f"OpenAI istemcisi olusturulamadı: {exc}")
        _openai_client = None
    return _openai_client


def generate_uno_deck():
    next_id = 0
    biology_cards = []
    special_cards = []

    for info in BIOLOGY_CARDS:
        card = Card(next_id, value=info.organ, color=info.color, system=info.system)
        biology_cards.append(card)
        surface = animation.assets.get_biology_surface(info.color, info.system, info.organ)
        animation.game.track_card(surface, card.id)
        next_id += 1

    for value, count in SPECIAL_CARD_COUNTS.items():
        for _ in range(count):
            card = Card(next_id, value=value, color="special", system=None)
            special_cards.append(card)
            surface = animation.assets.get_special_surface(value)
            animation.game.track_card(surface, card.id)
            next_id += 1

    for color in BIOLOGY_COLORS:
        for value, count in COLORED_SPECIAL_COUNTS.items():
            for _ in range(count):
                card = Card(next_id, value=value, color=color, system=None)
                special_cards.append(card)
                surface = animation.assets.get_colored_special_surface(color, value)
                animation.game.track_card(surface, card.id)
                next_id += 1

    random.shuffle(biology_cards)
    random.shuffle(special_cards)

    cards = []
    while biology_cards or special_cards:
        for _ in range(3):
            if biology_cards:
                cards.append(biology_cards.pop())
        if special_cards:
            cards.append(special_cards.pop())

    # Populate main deck and create discard
    discard = Deck()
    deck = Deck(discard=discard, cards=cards)
    deck.shuffle()
    sfx_card_shuffle.play()
    return deck


DECK = None
CURRENT_MODE = None
CURRENT_PLAYER = None
OPPONENT_TRACKER = None
OPPONENTS = []


def check_for_key_press():
    if len(pygame.event.get(pg.QUIT)) > 0:
        terminate()

    keyUpEvents = pygame.event.get(pg.KEYUP)
    if len(keyUpEvents) == 0:
        return None
    for event in keyUpEvents:
        if event.key == pg.K_ESCAPE:
            if animation.game.consume_escape_cancelled():
                continue
            terminate()
        return event.key
    return None


def terminate():
    pygame.quit()
    sys.exit()


def player_cycle(opponents):
    while True:
        for opponent in opponents:
            print(opponent.name)
            yield opponent


def opponent_turn(opponent_tracker):
    sleep_time = random.random() + .5
    animwait(sleep_time)
    opponent = next(opponent_tracker)
    deck = opponent.hand.deck
    matches = [card for card in opponent.hand.cards if card.match(
        deck.getDiscard())]
    if matches:
        # Play Card
        chosen_card = random.choice(matches)
        sfx_card_place.play()
        opponent.playCard(chosen_card, accept_input=False)
        if chosen_card.value in WILD_VALUES:
            color = chosen_card.color
            anim_index = WILD_COLOR_TO_ANIM_INDEX.get(color)
            if anim_index is not None:
                animation.game.opponent_play_card(
                    opponent.name, chosen_card.id, wild_color=anim_index)
            else:
                animation.game.opponent_play_card(opponent.name, chosen_card.id)
        else:
            animation.game.opponent_play_card(opponent.name, chosen_card.id)

        if len(opponent.hand.cards) == 0:
            end_game(opponent.name)
            return
        penalty = DRAW_EFFECTS.get(chosen_card.value)
        if penalty:
            drawn_cards = CURRENT_PLAYER.draw(penalty)
            for card in drawn_cards:
                animation.game.draw_card(card.id)
            refresh_debug_system()
    else:
        # Draw Card
        sfx_card_draw.play()
        opponent.draw(1)
        animation.game.opponent_draw_card(opponent.name)
    animation.next_frame()


def animwait(seconds):
    goal = pygame.time.get_ticks() + seconds*1000
    while pygame.time.get_ticks() < goal:

        animation.next_frame()
        check_for_key_press()


def refresh_debug_system():
    return


def validate_card_explanation(card, explanation):
    if card is None or card.system is None:
        return True
    if not explanation:
        return False

    organ_text = str(card.value).replace("_", " ")
    client = _get_openai_client()
    print(f"[AI Debug] Color: {card.color}, System: {card.system}, Organ: {organ_text}, Explanation: {explanation}")
    if client is not None:
        prompt = f"""
    Sen bir biyoloji öğretmenisin ve Türkçe konuşuyorsun.
    Cevaplarında ve "{explanation}"'da Türkçe karakterleri olabilir. {organ_text}' veya '{card.system}' türkçe karakter içermese bile bunları "{explanation}"'dan eşleştir.
    Ortaokul seviyesindeki öğrencilerin biyoloji bilgisini değerlendiriyorsun.

    Oyuncu '{card.color}_{card.system}_{organ_text}' kartını oynarken şu açıklamayı yaptı:
    "{explanation}"

    Görevin, bu açıklamanın hem '{card.system}' sistemiyle hem de '{organ_text}' organı veya yapısıyla ilgili doğru biyolojik bilgi içerip içermediğini değerlendirmektir.

    Eğer açıklama sadece yüzeysel veya yanlış bilgi içeriyorsa "HAYIR" yaz.
    Eğer açıklama doğru bilgiler veriyor, ayrıca organın işlevi veya sistemdeki rolüyle ilgili anlamlı bir açıklama yapıyorsa "EVET" yaz.

    Sadece "EVET" veya "HAYIR" şeklinde cevap ver.
    """
        try:
            response = client.responses.create(
                model="gpt-4o-mini-transcribe",
                input=prompt.strip(),
            )
            reply = response.output_text.strip().upper()
            print(f"[AI Debug] Model yaniti: {reply}")
            if reply.startswith("EVET"):
                return True
            if reply.startswith("HAYIR"):
                return False
        except Exception as exc:
            print(f"OpenAI dogrulama hatasi: {exc}")

    normalized_text = _normalize_text(explanation)
    normalized_system = _normalize_text(card.system)
    if normalized_system and normalized_system not in normalized_text:
        return False

    value_tokens = str(card.value).replace("+", " ").split("_")
    organ_tokens = [t for t in (_normalize_text(token) for token in value_tokens) if t and t not in EXPLANATION_STOPWORDS]
    if not organ_tokens:
        return True
    return any(token and token in normalized_text for token in organ_tokens)


def end_game(winner_name):
    global CURRENT_MODE, CURRENT_PLAYER, OPPONENT_TRACKER, DECK, OPPONENTS

    show_text(f"Kazanan: {winner_name}", 3)
    animwait(3)

    animation.game.reset()

    CURRENT_MODE = Modes.INTRO
    animation.intro.show()

    DECK = None
    CURRENT_PLAYER = None
    OPPONENT_TRACKER = None
    OPPONENTS = []


def main():
    global CURRENT_MODE

    pygame.init()

    pygame.display.set_caption('Uno!')

    mixer.music.play(-1)

    CURRENT_MODE = Modes.INTRO
    animation.intro.show()

    while True:
        check_for_key_press()
        if CURRENT_MODE == Modes.INTRO:
            do_intro_iteration()
        elif CURRENT_MODE == Modes.LOBBY:
            do_lobby_iteration()
        elif CURRENT_MODE == Modes.GAME:
            do_game_iteration()
        animation.next_frame()


def do_intro_iteration():
    global CURRENT_MODE
    for event in pygame.event.get():  # event handling loop
        if event.type == pg.MOUSEBUTTONDOWN:
            position = pygame.mouse.get_pos()
            if animation.intro.clicked_start(position):
                print("Baslat kartina tiklandi!")
                CURRENT_MODE = Modes.LOBBY
                animation.lobby.show()
            elif animation.intro.clicked_exit(position):
                print("Cikis kartina tiklandi!")
                terminate()


def init_game():
    global DECK
    DECK = generate_uno_deck()

    opponent_names = ["Bilgisayar"]
    opponents = [Player(name, DECK) for name in opponent_names]

    for opponent in opponents:
        animation.game.add_opponent(opponent.name)

    global OPPONENT_TRACKER
    OPPONENT_TRACKER = player_cycle(opponents)

    global OPPONENTS
    OPPONENTS = opponents

    global CURRENT_PLAYER
    CURRENT_PLAYER = Player("Oyuncu Uno", DECK)

    animation.game.show()

    for _ in range(7):
        card = CURRENT_PLAYER.draw(1)[0]
        animation.game.draw_card(card.id)
        check_for_key_press()
        animation.next_frame()

        for opponent in opponents:
            opponent.draw(1)
            animation.game.opponent_draw_card(opponent.name)
            check_for_key_press()
            animation.next_frame()

    refresh_debug_system()

    first_discard = DECK.draw(1)
    DECK.discard(first_discard)
    animation.game.draw_to_play_deck(first_discard[0].id)

    sfx_ding.play()
    sfx_whoosh.play()
    show_text("Sira sende", 1)


def do_lobby_iteration():
    global CURRENT_MODE
    for event in pygame.event.get():  # event handling loop
        if event.type == pg.MOUSEBUTTONDOWN:
            position = pygame.mouse.get_pos()
            if animation.lobby.clicked_join_game(position):
                print("Oyuna katil dugmesine tiklandi!")
                animation.lobby.join_button_to_waiting()
                animwait(2)
                CURRENT_MODE = Modes.GAME
                init_game()
            elif animation.lobby.clicked_cancel(position):
                print("Iptal dugmesine tiklandi!")
                CURRENT_MODE = Modes.INTRO
                animation.intro.show()
        elif event.type == pg.KEYDOWN:
            animation.lobby.append_char_to_name(chr(event.key))


def do_game_iteration():
    global CURRENT_MODE
    for event in pygame.event.get():  # event handling loop
        if event.type == pg.KEYDOWN:
            # Draw card
            if event.key == pg.K_DOWN:
                sfx_card_draw.play()
                card = CURRENT_PLAYER.draw(1)[0]
                animation.game.draw_card(card.id)
                refresh_debug_system()
                for _ in OPPONENTS:
                    opponent_turn(OPPONENT_TRACKER)
                    if CURRENT_MODE != Modes.GAME:
                        return
                sfx_ding.play()
                sfx_whoosh.play()
                show_text("Sira sende", 1)

            # Play card
            elif event.key == pg.K_UP:
                cur_card_id = animation.game.get_focus_id()
                if cur_card_id == -1:
                    if CURRENT_PLAYER and len(CURRENT_PLAYER.hand.cards) == 0:
                        end_game(CURRENT_PLAYER.name)
                        return
                    sfx_error.play()
                    print("Oynanacak kart bulunamadi")
                    return
                cur_card = CURRENT_PLAYER.getCardFromID(cur_card_id)
                if cur_card is None:
                    if CURRENT_PLAYER and len(CURRENT_PLAYER.hand.cards) == 0:
                        end_game(CURRENT_PLAYER.name)
                        return
                    sfx_error.play()
                    print("Kart bulunamadi")
                    return
                if cur_card.match(DECK.getDiscard()):
                    skip_explanation = (
                        cur_card.value in WILD_VALUES or
                        cur_card.value in DRAW_EFFECTS or
                        cur_card.value == "degisim"
                    )
                    if not skip_explanation:
                        explanation = animation.game.prompt_for_card_explanation(cur_card)
                        if explanation is None:
                            show_text("Kart iptal edildi", 1)
                            return
                        if not validate_card_explanation(cur_card, explanation):
                            sfx_error.play()
                            show_text("Bilgiler hatali, kart secimini yenile", 1)
                            return

                    sfx_card_place.play()
                    if cur_card.value in WILD_VALUES:
                        curr = 0
                        animation.game.show_wildcard_wheel()
                        animation.game.switch_wildcard_wheel_focus(curr)
                        choosing = True
                        while choosing:
                            for event in pygame.event.get():
                                if event.type == pg.KEYDOWN:
                                    if event.key == pg.K_LEFT:
                                        curr = (curr + 1) % len(WILD_COLOR_ORDER)
                                    elif event.key == pg.K_RIGHT:
                                        curr = (curr - 1) % len(WILD_COLOR_ORDER)
                                    elif event.key == pg.K_RETURN:
                                        choosing = False

                                    if event.key in (pg.K_LEFT, pg.K_RIGHT) and curr < len(WILD_ANIMATION_COLORS):
                                        animation.game.switch_wildcard_wheel_focus(curr)
                            animation.next_frame()

                        animation.game.hide_wildcard_wheel()

                        selected_color = WILD_COLOR_ORDER[curr]
                        cur_card.color = selected_color
                        print(f"Secilen renk: {selected_color}")
                        anim_index = WILD_COLOR_TO_ANIM_INDEX.get(selected_color)
                        if anim_index is not None:
                            animation.game.play_card(cur_card.id, wild_color=anim_index)
                        else:
                            animation.game.play_card(cur_card.id)
                    else:
                        animation.game.play_card(cur_card.id)

                    CURRENT_PLAYER.playCard(cur_card)
                    if len(CURRENT_PLAYER.hand.cards) == 1:
                        end_game(CURRENT_PLAYER.name)
                        return

                    penalty = DRAW_EFFECTS.get(cur_card.value)
                    if penalty:
                        for opponent in OPPONENTS:
                            drawn_cards = opponent.draw(penalty)
                            for _ in drawn_cards:
                                animation.game.opponent_draw_card(opponent.name)

                    refresh_debug_system()

                    for _ in OPPONENTS:
                        opponent_turn(OPPONENT_TRACKER)
                        if CURRENT_MODE != Modes.GAME:
                            return
                    sfx_ding.play()
                    sfx_whoosh.play()
                    show_text("Sira sende", 1)
                else:
                    sfx_error.play()
                    print("Bu karti oynayamazsin")

            # Shift hand
            elif event.key == pg.K_LEFT:
                sfx_tick.play()
                animation.game.shift_hand(False)
                refresh_debug_system()
            elif event.key == pg.K_RIGHT:
                sfx_tick.play()
                animation.game.shift_hand(True)
                refresh_debug_system()
            # Testing wildcard wheel
            elif event.key == pg.K_9:
                animation.game.show_wildcard_wheel()
            elif event.key == pg.K_0:
                CURRENT_MODE = Modes.INTRO
                animation.intro.show()
                animation.game.reset()


if __name__ == '__main__':
    main()
