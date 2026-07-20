# -*- coding: utf-8 -*-
"""
چت‌بات هوش مصنوعی - نسخه گرافیکی شیک (Kivy) با پشتیبانی از فونت فارسی
"""

import requests
import threading
import arabic_reshaper
from bidi.algorithm import get_display

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle

# ==========================================
# کلید API خودتون رو اینجا بذارید
# از سایت console.groq.com بگیرید
# ==========================================
API_KEY = "اینجا_کلید_API_رو_بذار"
URL = "https://api.groq.com/openai/v1/chat/completions"

# رنگ‌بندی
BG_COLOR = (0.06, 0.07, 0.09, 1)
USER_BUBBLE_COLOR = (0.15, 0.45, 0.85, 1)
BOT_BUBBLE_COLOR = (0.18, 0.19, 0.23, 1)
HEADER_COLOR = (0.1, 0.11, 0.14, 1)

Window.clearcolor = BG_COLOR

# ثبت فونت فارسی (فایل Vazirmatn-Regular.ttf باید کنار main.py باشه)
LabelBase.register(name="Vazir", fn_regular="Vazirmatn-Regular.ttf")


def fa(text):
    """
    متن فارسی رو برای نمایش درست توی Kivy آماده می‌کنه:
    حروف رو به‌هم می‌چسبونه (reshape) و جهت راست‌به‌چپ رو اصلاح می‌کنه (bidi)
    """
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


class ChatBubble(BoxLayout):
    """یک حباب پیام با پس‌زمینه رنگی و گوشه‌ی گرد"""

    def __init__(self, text, is_user, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint_y = None
        self.padding = (dp(14), dp(10))

        bubble_color = USER_BUBBLE_COLOR if is_user else BOT_BUBBLE_COLOR

        self.label = Label(
            text=fa(text),
            font_name="Vazir",
            color=(1, 1, 1, 1),
            font_size=dp(15),
            halign="right",
            valign="middle",
            size_hint_y=None,
        )
        self.label.bind(
            width=lambda *x: self.label.setter("text_size")(self.label, (self.label.width, None))
        )
        self.label.bind(texture_size=self._update_label_height)
        self.add_widget(self.label)

        self.size_hint_x = 0.78
        if is_user:
            self.pos_hint = {"right": 1}
        else:
            self.pos_hint = {"x": 0}

        with self.canvas.before:
            Color(*bubble_color)
            self.bg_rect = RoundedRectangle(radius=[dp(16)])
        self.bind(pos=self._update_bg, size=self._update_bg)

    def _update_label_height(self, *args):
        self.label.height = self.label.texture_size[1]
        self.height = self.label.height + dp(20)

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def set_text(self, new_text):
        self.label.text = fa(new_text)
        self.label.texture_update()
        self._update_label_height()


class ChatApp(App):

    def build(self):
        self.title = "چت‌بات هوش مصنوعی"
        self.conversation_history = [
            {"role": "system", "content": "تو یک دستیار هوشمند و مفید هستی که به فارسی جواب می‌دی."}
        ]

        root = BoxLayout(orientation="vertical")

        header = BoxLayout(size_hint=(1, None), height=dp(56), padding=(dp(16), 0))
        with header.canvas.before:
            Color(*HEADER_COLOR)
            self.header_rect = RoundedRectangle(radius=[0])
        header.bind(pos=self._update_header_bg, size=self._update_header_bg)
        header_label = Label(
            text=fa("دستیار هوشمند"),
            font_name="Vazir",
            font_size=dp(18),
            color=(1, 1, 1, 1),
        )
        header.add_widget(header_label)
        root.add_widget(header)

        body = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))

        self.scroll = ScrollView(size_hint=(1, 1))
        self.messages_box = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(12), padding=(dp(4), dp(8))
        )
        self.messages_box.bind(minimum_height=self.messages_box.setter("height"))
        self.scroll.add_widget(self.messages_box)
        body.add_widget(self.scroll)

        input_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(52), spacing=dp(8))
        self.text_input = TextInput(
            hint_text=fa("پیامت رو بنویس..."),
            font_name="Vazir",
            multiline=False,
            size_hint=(0.78, 1),
            font_size=dp(16),
            background_color=(0.15, 0.16, 0.19, 1),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(1, 1, 1, 1),
            padding=(dp(12), dp(12)),
        )
        self.text_input.bind(on_text_validate=self.on_send)

        send_btn = Button(
            text=fa("ارسال"),
            font_name="Vazir",
            size_hint=(0.22, 1),
            background_color=(0.15, 0.45, 0.85, 1),
            background_normal="",
        )
        send_btn.bind(on_press=self.on_send)

        input_row.add_widget(self.text_input)
        input_row.add_widget(send_btn)
        body.add_widget(input_row)

        root.add_widget(body)

        self.add_bubble("سلام! چطور می‌تونم کمکت کنم؟", is_user=False)
        if API_KEY == "اینجا_کلید_API_رو_بذار":
            self.add_bubble("⚠️ هنوز کلید API رو توی کد نذاشتید!", is_user=False)

        return root

    def _update_header_bg(self, instance, *args):
        self.header_rect.pos = instance.pos
        self.header_rect.size = instance.size

    def add_bubble(self, text, is_user):
        bubble = ChatBubble(text=text, is_user=is_user)
        self.messages_box.add_widget(bubble)
        Clock.schedule_once(lambda dt: setattr(self.scroll, "scroll_y", 0), 0.1)
        return bubble

    def on_send(self, *args):
        user_text = self.text_input.text.strip()
        if not user_text:
            return
        self.text_input.text = ""
        self.add_bubble(user_text, is_user=True)
        thinking_bubble = self.add_bubble("در حال فکر کردن...", is_user=False)

        threading.Thread(
            target=self.get_ai_response, args=(user_text, thinking_bubble)
        ).start()

    def get_ai_response(self, user_text, thinking_bubble):
        self.conversation_history.append({"role": "user", "content": user_text})

        headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": self.conversation_history,
            "temperature": 0.7,
            "max_tokens": 1024,
        }

        try:
            response = requests.post(URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            reply = result["choices"][0]["message"]["content"]
            self.conversation_history.append({"role": "assistant", "content": reply})
        except Exception as e:
            reply = f"خطا: {e}"

        Clock.schedule_once(lambda dt: thinking_bubble.set_text(reply))


if __name__ == "__main__":
    ChatApp().run()
