"""Подкидной дурак — приложение для Android (Python + Kivy).

Игровая логика лежит в engine.py, здесь только экран.
Запуск на компьютере для проверки:  pip install kivy  и  python main.py
"""
import datetime
import json
import os
import traceback

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup

from engine import RANK_NAMES, Game

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DejaVuSans.ttf")
RED = (0.78, 0.16, 0.16, 1)
DARK = (0.13, 0.13, 0.13, 1)
WHITE = (1, 1, 1, 1)


def make_label(**kw):
    kw.setdefault("font_name", FONT)
    lbl = Label(**kw)
    lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
    return lbl


def make_button(**kw):
    kw.setdefault("font_name", FONT)
    return Button(**kw)


class CardWidget(ButtonBehavior, FloatLayout):
    """Одна карта. card=None — рубашка."""

    def __init__(self, card=None, ok=False, dim=False, index=None, **kw):
        super().__init__(**kw)
        self.card = card
        self.ok = ok
        self.dim = dim
        self.index = index
        self.interactive = index is not None
        self.corner = None
        self.big = None
        if card is not None:
            col = RED if card.is_red else DARK
            self.corner = Label(text=f"{RANK_NAMES[card.r]}\n{card.s}", font_name=FONT, color=col,
                                halign="left", valign="top", size_hint=(None, None))
            self.big = Label(text=card.s, font_name=FONT, color=col,
                             halign="center", valign="middle", size_hint=(None, None))
            self.add_widget(self.corner)
            self.add_widget(self.big)
        self.bind(pos=self.redraw, size=self.redraw)
        self.redraw()

    def on_touch_down(self, touch):
        if not self.interactive:
            return False
        return super().on_touch_down(touch)

    def redraw(self, *args):
        x, y = self.pos
        w, h = self.size
        r = w * 0.12
        self.canvas.before.clear()
        with self.canvas.before:
            if self.card is None:
                Color(1, 1, 1, 1)
                RoundedRectangle(pos=(x, y), size=(w, h), radius=[r])
                Color(0.12, 0.31, 0.61, 1)
                RoundedRectangle(pos=(x + w * 0.06, y + w * 0.06),
                                 size=(w * 0.88, h - w * 0.12), radius=[w * 0.08])
                Color(0.6, 0.74, 0.94, 1)
                RoundedRectangle(pos=(x + w * 0.3, y + h * 0.5 - w * 0.2),
                                 size=(w * 0.4, w * 0.4), radius=[w * 0.1])
            else:
                Color(0, 0, 0, 0.35)
                RoundedRectangle(pos=(x + 1.5, y - 1.5), size=(w, h), radius=[r])
                if self.dim:
                    Color(0.8, 0.8, 0.8, 1)
                else:
                    Color(*WHITE)
                RoundedRectangle(pos=(x, y), size=(w, h), radius=[r])
                if self.ok:
                    Color(1, 0.76, 0.03, 1)
                    Line(rounded_rectangle=(x, y, w, h, r), width=dp(2.2))
        if self.corner is not None:
            self.corner.font_size = w * 0.26
            self.corner.size = (w * 0.5, h * 0.48)
            self.corner.text_size = self.corner.size
            self.corner.pos = (x + w * 0.07, y + h * 0.5)
            self.big.font_size = w * 0.6
            self.big.size = (w * 0.7, h * 0.5)
            self.big.text_size = self.big.size
            self.big.pos = (x + w * 0.3, y + h * 0.04)


class DurakApp(App):
    title = "Durak"

    # ---------- построение экрана ----------
    def build(self):
        Window.clearcolor = (0.08, 0.40, 0.23, 1)
        self.game = None
        self.popup = None
        self.stats = self.load_stats()

        root = BoxLayout(orientation="vertical", padding=[dp(6), dp(4)], spacing=dp(2))

        bar = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        self.score_lbl = make_label(text="", font_size=sp(13), halign="left", valign="middle")
        new_btn = make_button(text="Новая игра", size_hint_x=None, width=dp(120), font_size=sp(14))
        new_btn.bind(on_release=self.safe(self.on_new))
        bar.add_widget(self.score_lbl)
        bar.add_widget(new_btn)

        self.info_lbl = make_label(text="", size_hint_y=None, height=dp(26), font_size=sp(13),
                                   halign="center", valign="middle")
        self.field = FloatLayout()
        self.field.bind(size=self.on_field_resize, pos=self.on_field_resize)
        self.status_lbl = make_label(text="", size_hint_y=None, height=dp(54), font_size=sp(15),
                                     halign="center", valign="middle")
        self.act_btn = make_button(text="", size_hint_y=None, height=dp(56), font_size=sp(20),
                                   bold=True, background_normal="", background_color=(1, 0.76, 0.03, 1),
                                   color=(0.13, 0.13, 0.13, 1))
        self.act_btn.bind(on_release=self.safe(self.on_act))

        for w in (bar, self.info_lbl, self.field, self.status_lbl, self.act_btn):
            root.add_widget(w)

        self.show_score()
        Clock.schedule_once(self.safe(lambda dt: self.start_game()), 0.3)
        return root

    def start_game(self):
        self.game = Game(self)

    # ---------- интерфейс для engine.Game ----------
    def later(self, ms, fn):
        Clock.schedule_once(self.safe(lambda dt: fn()), ms / 1000.0)

    def render(self, g):
        self.info_lbl.text = (f"Козырь {g.trump} · Колода: {len(g.deck)}"
                              + (f" (внизу {g.trump_card})" if g.deck else "")
                              + f" · Бито: {g.discard}")
        self.status_lbl.text = g.status
        text, enabled = g.action
        self.act_btn.text = text
        self.act_btn.disabled = not enabled
        self.act_btn.opacity = 1 if text else 0
        self.layout_cards(g)

    def over(self, msg, res):
        key = {"win": "w", "lose": "l"}.get(res, "d")
        self.stats[key] = self.stats.get(key, 0) + 1
        self.save_stats()
        self.show_score()
        self.show_popup(msg, "Играть ещё", self.restart)

    # ---------- карты на столе ----------
    def on_field_resize(self, *args):
        if self.game is not None:
            self.layout_cards(self.game)

    def add_card(self, card, x, y, cw, ch, ok=False, dim=False, index=None):
        w = CardWidget(card=card, ok=ok, dim=dim, index=index,
                       size_hint=(None, None), size=(cw, ch), pos=(x, y))
        if index is not None:
            w.bind(on_release=self.safe(lambda inst: self.on_tap(inst.index)))
        self.field.add_widget(w)

    def layout_cards(self, g):
        field = self.field
        field.clear_widgets()
        fw, fh = field.size
        fx, fy = field.pos
        if fw < dp(50) or fh < dp(100):
            return
        cw = min(dp(74), fw / 5.4, fh / 6.8)
        ch = cw * 1.4
        pad = dp(4)

        # рука соперника (рубашками вверх)
        n = len(g.hands["cpu"])
        if n:
            step = min(cw * 0.45, (fw - 2 * pad - cw) / (n - 1)) if n > 1 else 0
            x0 = fx + (fw - (cw + step * (n - 1))) / 2
            for i in range(n):
                self.add_card(None, x0 + i * step, fy + fh - ch - pad, cw, ch)

        # ваша рука
        you = g.hands["you"]
        m = len(you)
        interactive = g.phase in ("you_attack", "you_defend")
        y0 = fy + pad
        if m:
            step = min(cw * 1.08, (fw - 2 * pad - cw) / (m - 1)) if m > 1 else 0
            x0 = fx + (fw - (cw + step * (m - 1))) / 2
            for i, card in enumerate(you):
                ok = interactive and g.is_playable(card)
                y = y0 + (ch * 0.14 if ok else 0)
                self.add_card(card, x0 + i * step, y, cw, ch,
                              ok=ok, dim=interactive and not ok, index=i)

        # стол: пары «атака + ответ»
        pairs = g.table
        if pairs:
            pw = cw * 1.3
            cols = max(1, int((fw - 2 * pad) // pw))
            rows = (len(pairs) + cols - 1) // cols
            rowh = ch * 1.22
            top_limit = fy + fh - ch - 2 * pad
            bottom_limit = y0 + ch * 1.2
            ytop = (top_limit + bottom_limit) / 2 + rows * rowh / 2
            for r in range(rows):
                items = pairs[r * cols:(r + 1) * cols]
                xs = fx + (fw - len(items) * pw) / 2
                by = ytop - (r + 1) * rowh
                for j, (a, d) in enumerate(items):
                    bx = xs + j * pw + (pw - cw * 1.22) / 2
                    self.add_card(a, bx, by + ch * 0.22, cw, ch)
                    if d is not None:
                        self.add_card(d, bx + cw * 0.22, by, cw, ch)

    # ---------- действия игрока ----------
    def on_tap(self, index):
        if self.game is not None:
            self.game.tap(index)

    def on_act(self, *args):
        if self.game is not None:
            self.game.act()

    def on_new(self, *args):
        if self.game is None:
            return
        if self.game.phase == "over":
            self.restart()
        else:
            self.show_popup("Прервать партию и начать заново?", "Да", self.restart, cancel_text="Нет")

    def restart(self):
        if self.game is not None:
            self.game.new_game()

    # ---------- окна-сообщения ----------
    def show_popup(self, text, ok_text, on_ok, cancel_text=None):
        if self.popup is not None:
            self.popup.dismiss()
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(12))
        box.add_widget(make_label(text=text, font_size=sp(17), halign="center", valign="middle"))
        buttons = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        popup = Popup(title="", separator_height=0, content=box, size_hint=(0.88, 0.4),
                      auto_dismiss=False)

        def ok_pressed(*a):
            popup.dismiss()
            self.popup = None
            on_ok()

        def cancel_pressed(*a):
            popup.dismiss()
            self.popup = None

        ok_btn = make_button(text=ok_text, font_size=sp(16))
        ok_btn.bind(on_release=self.safe(ok_pressed))
        buttons.add_widget(ok_btn)
        if cancel_text:
            cancel_btn = make_button(text=cancel_text, font_size=sp(16))
            cancel_btn.bind(on_release=self.safe(cancel_pressed))
            buttons.add_widget(cancel_btn)
        box.add_widget(buttons)
        self.popup = popup
        popup.open()

    # ---------- счёт ----------
    def stats_path(self):
        return os.path.join(self.user_data_dir, "stats.json")

    def load_stats(self):
        try:
            with open(self.stats_path(), encoding="utf-8") as f:
                data = json.load(f)
            return {"w": int(data.get("w", 0)), "l": int(data.get("l", 0)), "d": int(data.get("d", 0))}
        except (OSError, ValueError, TypeError):
            return {"w": 0, "l": 0, "d": 0}

    def save_stats(self):
        try:
            with open(self.stats_path(), "w", encoding="utf-8") as f:
                json.dump(self.stats, f)
        except OSError:
            pass

    def show_score(self):
        self.score_lbl.text = f"Победы: {self.stats['w']} · Поражения: {self.stats['l']}"

    # ---------- защита от вылетов ----------
    def safe(self, fn):
        """Любая ошибка внутри fn записывается в файл, игра начинается заново."""
        def run(*args):
            try:
                return fn(*args)
            except Exception:
                self.crash(traceback.format_exc())
        return run

    def crash(self, text):
        try:
            path = os.path.join(self.user_data_dir, "durak_error.log")
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n--- {datetime.datetime.now()} ---\n{text}")
        except OSError:
            pass
        try:
            self.show_popup("Что-то пошло не так. Начнём новую партию.", "Ок", self.restart)
        except Exception:
            pass


if __name__ == "__main__":
    DurakApp().run()
