"""Игровая логика «Подкидного дурака». Не зависит от Kivy, поэтому легко проверяется.

Экран передаёт в Game объект ui с тремя методами:
    ui.render(game)       — перерисовать экран
    ui.later(ms, fn)      — вызвать fn через ms миллисекунд
    ui.over(msg, result)  — партия окончена (result: 'win' / 'lose' / 'draw')
"""
import random

SUITS = "♠♥♦♣"
RANK_NAMES = {6: "6", 7: "7", 8: "8", 9: "9", 10: "10", 11: "В", 12: "Д", 13: "К", 14: "Т"}
HAND = 6
NAMES = {"you": "Вы", "cpu": "Соперник"}


def plural(n):
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} карта"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} карты"
    return f"{n} карт"


class Card:
    def __init__(self, rank, suit):
        self.r = rank
        self.s = suit

    def __str__(self):
        return RANK_NAMES[self.r] + self.s

    __repr__ = __str__

    @property
    def is_red(self):
        return self.s in "♥♦"


def beats(a, b, trump):
    """Бьёт ли карта a карту b."""
    if a.s == b.s:
        return a.r > b.r
    return a.s == trump and b.s != trump


class Game:
    def __init__(self, ui):
        self.ui = ui
        self.gen = 0
        self.phase = "busy"
        self.status = ""
        self.action = ("", False)
        self.new_game()

    # ---------- вспомогательное ----------
    def later(self, ms, fn):
        g = self.gen

        def run():
            if g == self.gen:      # игнорируем «старые» таймеры после новой игры
                fn()
        self.ui.later(ms, run)

    def say(self, text):
        self.status = text

    def set_action(self, text, enabled):
        self.action = (text, enabled)

    def changed(self):
        self.ui.render(self)

    @staticmethod
    def other(p):
        return "cpu" if p == "you" else "you"

    def sort_hand(self, p):
        t = self.trump
        self.hands[p].sort(key=lambda c: (c.s == t, c.r, c.s))

    def table_ranks(self):
        return {c.r for pair in self.table for c in pair if c}

    def table_cards(self):
        return [c for pair in self.table for c in pair if c]

    # ---------- новая игра ----------
    def new_game(self):
        self.gen += 1
        self.deck = [Card(r, s) for s in SUITS for r in RANK_NAMES]
        random.shuffle(self.deck)
        self.trump_card = self.deck[0]   # лежит внизу колоды; карты берём с конца
        self.trump = self.trump_card.s
        self.hands = {"you": [], "cpu": []}
        for _ in range(HAND):
            self.hands["you"].append(self.deck.pop())
            self.hands["cpu"].append(self.deck.pop())
        self.sort_hand("you")
        self.sort_hand("cpu")
        self.table = []
        self.discard = 0
        self.taking = False
        self.limit = HAND
        self.first = False
        self.phase = "busy"

        best, who = None, None
        for p in ("you", "cpu"):
            for c in self.hands[p]:
                if c.s == self.trump and (best is None or c.r < best):
                    best, who = c.r, p
        self.att = who or random.choice(["you", "cpu"])
        self.dfn = self.other(self.att)

        self.set_action("", False)
        self.say(f"Козырь — {self.trump}. Первым ходит: {NAMES[self.att]}.")
        self.changed()
        self.later(1400, self.start_round)

    # ---------- ход раунда ----------
    def start_round(self):
        self.table = []
        self.taking = False
        self.limit = min(HAND, len(self.hands[self.dfn]))
        self.attacker_turn(True)

    def attack_options(self):
        ranks = self.table_ranks()
        return [c for c in self.hands[self.att] if self.first or c.r in ranks]

    def attacker_turn(self, first):
        self.first = first
        if self.att == "you":
            if not first and not self.attack_options():
                self.phase = "busy"
                self.set_action("", False)
                self.say("Подкидывать больше нечего.")
                self.changed()
                self.later(800, self.end_round)
                return
            self.phase = "you_attack"
            if first:
                self.say("Ваш ход — выберите карту.")
                self.set_action("", False)
            elif self.taking:
                self.say("Соперник берёт. Подкиньте ещё или нажмите «Хватит».")
                self.set_action("Хватит", True)
            else:
                self.say("Подкиньте карту того же достоинства или нажмите «Бито».")
                self.set_action("Бито", True)
            self.changed()
        else:
            self.phase = "busy"
            self.set_action("", False)
            if first:
                self.say("Соперник ходит...")
            self.changed()
            self.later(900, self.cpu_attack_step)

    def cpu_attack_step(self):
        hand = self.hands["cpu"]
        ranks = self.table_ranks()
        cands = [c for c in hand if self.first or c.r in ranks]
        cands.sort(key=lambda c: (c.s == self.trump, c.r))
        card = cands[0] if cands else None
        # козыри без нужды не подкидываем, пока есть колода
        if card and not self.first and card.s == self.trump and self.deck:
            card = None
        if card is None:
            self.end_round()
            return
        hand.remove(card)
        self.table.append([card, None])
        self.say(f"Соперник ходит: {card}" if self.first else f"Соперник подкидывает: {card}")
        self.changed()
        self.after_attack()

    def after_attack(self):
        if self.taking:
            self.later(600, self.attacker_more)
        else:
            self.later(500, self.defender_turn)

    def defender_turn(self):
        last = self.table[-1][0]
        if self.dfn == "you":
            self.phase = "you_defend"
            can = any(beats(c, last, self.trump) for c in self.hands["you"])
            if can:
                self.say(f"Вам ходят: {last}. Побейте или нажмите «Взять».")
            else:
                self.say(f"Вам ходят: {last}. Побить нечем — нажмите «Взять».")
            self.set_action("Взять", True)
            self.changed()
        else:
            self.phase = "busy"
            self.set_action("", False)
            self.changed()
            self.later(800, self.cpu_defend_step)

    def cpu_defend_step(self):
        last = self.table[-1][0]
        hand = self.hands["cpu"]
        beaters = [c for c in hand if beats(c, last, self.trump)]
        beaters.sort(key=lambda c: (c.s == self.trump, c.r))
        card = beaters[0] if beaters else None
        # не тратим козырь на мелочь, пока в колоде много карт
        if card and card.s == self.trump and last.s != self.trump \
                and last.r <= 9 and len(self.deck) >= 4:
            card = None
        if card is None:
            self.taking = True
            self.say("Соперник берёт карты.")
            self.changed()
            self.later(700, self.attacker_more)
            return
        hand.remove(card)
        self.table[-1][1] = card
        self.say(f"Соперник бьёт: {card}")
        self.changed()
        self.after_defense()

    def after_defense(self):
        if not self.hands[self.dfn]:
            self.later(700, self.end_round)
        else:
            self.later(600, self.attacker_more)

    def attacker_more(self):
        if len(self.table) >= self.limit or not self.hands[self.att]:
            self.end_round()
        else:
            self.attacker_turn(False)

    def end_round(self):
        self.phase = "busy"
        self.set_action("", False)
        n = len(self.table_cards())
        if self.taking:
            who = "Вы забираете" if self.dfn == "you" else "Соперник забирает"
            self.say(f"{who}: {plural(n)}.")
        else:
            self.say("Бито!")
        self.changed()
        self.later(1000, self.finish_round)

    def finish_round(self):
        cards = self.table_cards()
        if self.taking:
            self.hands[self.dfn].extend(cards)
        else:
            self.discard += len(cards)
        self.table = []
        for p in (self.att, self.dfn):
            while len(self.hands[p]) < HAND and self.deck:
                self.hands[p].append(self.deck.pop())
        self.sort_hand("you")
        self.sort_hand("cpu")
        self.changed()

        if not self.deck:
            you_out = not self.hands["you"]
            cpu_out = not self.hands["cpu"]
            if you_out or cpu_out:
                if you_out and cpu_out:
                    msg, res = "Ничья!", "draw"
                elif you_out:
                    msg, res = "Вы выиграли! Соперник остался в дураках.", "win"
                else:
                    msg, res = "Вы остались в дураках. Выиграл соперник.", "lose"
                self.phase = "over"
                self.set_action("", False)
                self.say(msg)
                self.changed()
                self.later(500, lambda: self.ui.over(msg, res))
                return

        if not self.taking:
            self.att, self.dfn = self.dfn, self.att
        self.later(500, self.start_round)

    # ---------- действия игрока ----------
    def is_playable(self, card):
        if self.phase == "you_attack":
            return self.first or card.r in self.table_ranks()
        if self.phase == "you_defend" and self.table:
            return beats(card, self.table[-1][0], self.trump)
        return False

    def tap(self, i):
        """Игрок коснулся своей карты с номером i."""
        if self.phase not in ("you_attack", "you_defend"):
            return
        if not 0 <= i < len(self.hands["you"]):
            return
        card = self.hands["you"][i]
        if not self.is_playable(card):
            if self.phase == "you_attack":
                self.say("Так нельзя: нужна карта того же достоинства, что на столе.")
            else:
                self.say("Эта карта не бьёт. Выберите другую или нажмите «Взять».")
            self.changed()
            return
        self.hands["you"].pop(i)
        self.set_action("", False)
        if self.phase == "you_attack":
            self.phase = "busy"
            self.table.append([card, None])
            self.say(f"Вы ходите: {card}" if self.first else f"Вы подкидываете: {card}")
            self.changed()
            self.after_attack()
        else:
            self.phase = "busy"
            self.table[-1][1] = card
            self.say(f"Вы бьёте: {card}")
            self.changed()
            self.after_defense()

    def act(self):
        """Нажата большая кнопка («Бито» / «Хватит» / «Взять»)."""
        if self.phase == "you_attack" and not self.first:
            self.phase = "busy"
            self.end_round()
        elif self.phase == "you_defend":
            self.phase = "busy"
            self.taking = True
            self.set_action("", False)
            self.say("Вы берёте карты.")
            self.changed()
            self.later(600, self.attacker_more)
