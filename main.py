# -*- coding: utf-8 -*-
"""
چت‌بات هوش مصنوعی - نسخه‌ی کامل با:
- فونت و نمایش درست فارسی
- چت‌های جداگانه (مثل ChatGPT) + تاریخچه + حذف چت
- تنظیم سطح پاسخ (عمومی / نیمه‌تخصصی / تخصصی)
- کپی مطمئن پیام‌ها (متن اصلی، نه شکل‌بندی‌شده) + رفع مشکل هایلایت
- ضمیمه کردن فایل متنی (با درخواست مجوز دسترسی)
"""

import os
import json
import time
import threading
import requests
import arabic_reshaper
from bidi.algorithm import get_display

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.graphics import Color, RoundedRectangle

# ==========================================
# کلید API خودتون رو اینجا بذارید
# از سایت console.groq.com بگیرید
# ==========================================
API_KEY = "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"
URL = "https://api.groq.com/openai/v1/chat/completions"

BASE_PROMPT = "تو یک دستیار هوشمند و مفید هستی که به فارسی پاسخ می‌دی. همیشه پاسخ‌های دقیق، منسجم و منطقی بده."

LEVEL_PROMPTS = {
    "عمومی": "پاسخ‌هات رو ساده، روان و قابل فهم برای یک فرد عادی بده. از اصطلاحات تخصصی و پیچیده پرهیز کن.",
    "نیمه‌تخصصی": "پاسخ‌هات رو با جزئیات متوسط بده و از اصطلاحات تخصصی رایج استفاده کن، ولی همچنان قابل فهم باشه.",
    "تخصصی": "پاسخ‌هات رو کامل، دقیق و با عمق فنی/آکادمیک بده و از اصطلاحات تخصصی دقیق استفاده کن.",
}
LEVELS = ["عمومی", "نیمه‌تخصصی", "تخصصی"]

BG_COLOR = (0.06, 0.07, 0.09, 1)
USER_BUBBLE_COLOR = (0.15, 0.45, 0.85, 1)
BOT_BUBBLE_COLOR = (0.18, 0.19, 0.23, 1)
HEADER_COLOR = (0.1, 0.11, 0.14, 1)

Window.clearcolor = BG_COLOR
Window.softinput_mode = "below_target"

LabelBase.register(name="Vazir", fn_regular="Vazirmatn-Regular.ttf")


def fa(text):
    """متن فارسی رو برای نمایش درست توی Kivy آماده می‌کنه (چسبوندن حروف + جهت راست‌به‌چپ)"""
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception:
        return text


class ChatBubble(BoxLayout):
    def __init__(self, text, is_user, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint_y = None
        self.padding = (dp(4), dp(4))
        self.spacing = dp(2)

        self.raw_text = text  # متن اصلی (بدون شکل‌بندی) برای کپی درست
        bubble_color = USER_BUBBLE_COLOR if is_user else BOT_BUBBLE_COLOR

        self.input = TextInput(
            text=fa(text),
            font_name="Vazir",
            font_size=dp(15),
            readonly=True,
            multiline=True,
            size_hint_y=None,
            background_normal="",
            background_active="",
            background_color=(0, 0, 0, 0),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(0, 0, 0, 0),
            halign="right",
            padding=(dp(12), dp(6)),
        )
        self.input.bind(minimum_height=self._sync_height)
        self.add_widget(self.input)

        copy_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(26))
        self.copy_btn = Button(
            text=fa("کپی"),
            font_name="Vazir",
            font_size=dp(11),
            size_hint=(None, 1),
            width=dp(52),
            background_color=(0, 0, 0, 0.25),
            background_normal="",
            color=(1, 1, 1, 0.85),
        )
        self.copy_btn.bind(on_press=self.copy_to_clipboard)
        spacer = Label(size_hint_x=1)
        copy_row.add_widget(spacer)
        copy_row.add_widget(self.copy_btn)
        self.add_widget(copy_row)

        self.size_hint_x = 0.78
        if is_user:
            self.pos_hint = {"right": 1}
        else:
            self.pos_hint = {"x": 0}

        with self.canvas.before:
            Color(*bubble_color)
            self.bg_rect = RoundedRectangle(radius=[dp(16)])
        self.bind(pos=self._update_bg, size=self._update_bg)

    def _sync_height(self, *args):
        self.input.height = self.input.minimum_height
        self.height = self.input.height + dp(8) + dp(26)

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def set_text(self, new_text):
        self.raw_text = new_text
        self.input.text = fa(new_text)

    def copy_to_clipboard(self, *args):
        Clipboard.copy(self.raw_text)
        self.input.cancel_selection()
        original = self.copy_btn.text
        self.copy_btn.text = fa("کپی شد ✓")
        Clock.schedule_once(lambda dt: setattr(self.copy_btn, "text", original), 1.2)


class ChatApp(App):

    def build(self):
        self.title = "چت‌بات هوش مصنوعی"

        self.data_dir = self.user_data_dir
        self.sessions_dir = os.path.join(self.data_dir, "sessions")
        os.makedirs(self.sessions_dir, exist_ok=True)
        self.settings_file = os.path.join(self.data_dir, "settings.json")

        self.response_level = self.load_settings()
        self.current_session_id = str(int(time.time() * 1000))
        self.conversation_history = [{"role": "system", "content": self._full_system_prompt()}]

        self._request_android_permissions()

        root = BoxLayout(orientation="vertical")
        root.add_widget(self._build_header())

        body = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))

        self.scroll = ScrollView(size_hint=(1, 1))
        self.messages_box = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(12), padding=(dp(4), dp(8))
        )
        self.messages_box.bind(minimum_height=self.messages_box.setter("height"))
        self.scroll.add_widget(self.messages_box)
        body.add_widget(self.scroll)

        body.add_widget(self._build_input_row())
        root.add_widget(body)

        self.add_bubble("سلام! چطور می‌تونم کمکت کنم؟", is_user=False)
        if API_KEY == "اینجا_کلید_API_رو_بذار":
            self.add_bubble("⚠️ هنوز کلید API رو توی کد نذاشتید!", is_user=False)

        Window.bind(on_touch_down=self._on_global_touch)

        return root

    def _on_global_touch(self, window, touch):
        for bubble in list(self.messages_box.children):
            ti = bubble.input
            try:
                inside = ti.collide_point(*ti.to_widget(*touch.pos))
            except Exception:
                inside = False
            if not inside and (ti.selection_text or ti.focus):
                ti.cancel_selection()
                ti.focus = False
        return False

    def _request_android_permissions(self):
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
            ])
        except Exception:
            pass

    def _full_system_prompt(self):
        return BASE_PROMPT + " " + LEVEL_PROMPTS[self.response_level]

    def _build_header(self):
        header = BoxLayout(size_hint=(1, None), height=dp(56), padding=(dp(10), 0), spacing=dp(6))
        with header.canvas.before:
            Color(*HEADER_COLOR)
            self.header_rect = RoundedRectangle(radius=[0])
        header.bind(pos=self._update_header_bg, size=self._update_header_bg)

        menu_btn = Button(
            text=fa("چت‌ها"), font_name="Vazir", size_hint=(None, 1), width=dp(64),
            background_color=(0, 0, 0, 0), background_normal="", color=(1, 1, 1, 1),
        )
        menu_btn.bind(on_press=lambda *a: self.open_sessions_popup())
        header.add_widget(menu_btn)

        title = Label(text=fa("دستیار هوشمند"), font_name="Vazir", font_size=dp(17), color=(1, 1, 1, 1))
        header.add_widget(title)

        settings_btn = Button(
            text=fa("تنظیمات"), font_name="Vazir", size_hint=(None, 1), width=dp(80),
            background_color=(0, 0, 0, 0), background_normal="", color=(1, 1, 1, 1),
        )
        settings_btn.bind(on_press=lambda *a: self.open_settings_popup())
        header.add_widget(settings_btn)

        new_btn = Button(
            text="+", size_hint=(None, 1), width=dp(44),
            background_color=(0.15, 0.45, 0.85, 1), background_normal="", color=(1, 1, 1, 1),
        )
        new_btn.bind(on_press=lambda *a: self.new_chat())
        header.add_widget(new_btn)

        return header

    def _update_header_bg(self, instance, *args):
        self.header_rect.pos = instance.pos
        self.header_rect.size = instance.size

    def _build_input_row(self):
        input_row = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(52), spacing=dp(6))

        attach_btn = Button(
            text="+", size_hint=(None, 1), width=dp(44),
            background_color=(0.18, 0.19, 0.23, 1), background_normal="", color=(1, 1, 1, 1),
        )
        attach_btn.bind(on_press=lambda *a: self.pick_file())

        input_stack = FloatLayout(size_hint=(0.62, 1))

        self.text_input = TextInput(
            hint_text="",
            multiline=False,
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
            font_size=dp(16),
            background_color=(0.15, 0.16, 0.19, 1),
            foreground_color=(0, 0, 0, 0),
            cursor_color=(1, 1, 1, 1),
            padding=(dp(12), dp(12)),
        )
        self.text_input.bind(on_text_validate=self.on_send)
        self.text_input.bind(text=self._update_preview)

        self.preview_label = Label(
            text=fa("پیامت رو بنویس..."), font_name="Vazir", font_size=dp(16),
            color=(0.6, 0.6, 0.65, 1), size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
            halign="right", valign="middle",
        )
        self.preview_label.bind(size=lambda *a: setattr(
            self.preview_label, "text_size", self.preview_label.size
        ))

        input_stack.add_widget(self.text_input)
        input_stack.add_widget(self.preview_label)

        send_btn = Button(
            text=fa("ارسال"), font_name="Vazir", size_hint=(0.22, 1),
            background_color=(0.15, 0.45, 0.85, 1), background_normal="",
        )
        send_btn.bind(on_press=self.on_send)

        input_row.add_widget(attach_btn)
        input_row.add_widget(input_stack)
        input_row.add_widget(send_btn)
        return input_row

    def _update_preview(self, instance, value):
        if value:
            self.preview_label.text = fa(value)
            self.preview_label.color = (1, 1, 1, 1)
        else:
            self.preview_label.text = fa("پیامت رو بنویس...")
            self.preview_label.color = (0.6, 0.6, 0.65, 1)

    def pick_file(self):
        try:
            from plyer import filechooser
            filechooser.open_file(on_selection=self._file_selected)
        except Exception as e:
            self.add_bubble(f"امکان باز کردن فایل نبود: {e}", is_user=False)

    def _file_selected(self, selection):
        if not selection:
            return
        path = selection[0]

        def do_read(dt):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                current = self.text_input.text
                self.text_input.text = (current + "\n" + content).strip() if current else content
            except Exception as e:
                self.add_bubble(f"خطا در خوندن فایل: {e}", is_user=False)

        Clock.schedule_once(do_read)

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

        threading.Thread(target=self.get_ai_response, args=(user_text, thinking_bubble)).start()

    def get_ai_response(self, user_text, thinking_bubble):
        self.conversation_history.append({"role": "user", "content": user_text})

        headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": self.conversation_history,
            "temperature": 0.2,
            "max_tokens": 1500,
        }

        try:
            response = requests.post(URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            reply = result["choices"][0]["message"]["content"]
            self.conversation_history.append({"role": "assistant", "content": reply})
        except Exception as e:
            reply = f"خطا: {e}"

        def finish(dt):
            thinking_bubble.set_text(reply)
            self.save_current_session()

        Clock.schedule_once(finish)

    def _session_path(self, session_id):
        return os.path.join(self.sessions_dir, f"{session_id}.json")

    def save_current_session(self):
        has_content = any(m["role"] == "user" for m in self.conversation_history)
        if not has_content:
            return
        first_user_msg = next((m["content"] for m in self.conversation_history if m["role"] == "user"), "")
        title = (first_user_msg[:30] + "…") if len(first_user_msg) > 30 else first_user_msg
        payload = {
            "id": self.current_session_id,
            "title": title,
            "timestamp": int(time.time()),
            "messages": self.conversation_history,
        }
        try:
            with open(self._session_path(self.current_session_id), "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception as e:
            print("خطا در ذخیره‌ی چت:", e)

    def list_sessions(self):
        sessions = []
        if not os.path.isdir(self.sessions_dir):
            return sessions
        for fname in os.listdir(self.sessions_dir):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(self.sessions_dir, fname), "r", encoding="utf-8") as f:
                        data = json.load(f)
                    sessions.append(data)
                except Exception:
                    continue
        sessions.sort(key=lambda s: s.get("timestamp", 0), reverse=True)
        return sessions

    def delete_session(self, session_id):
        try:
            path = self._session_path(session_id)
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print("خطا در حذف چت:", e)

    def new_chat(self):
        self.save_current_session()
        self.current_session_id = str(int(time.time() * 1000))
        self.conversation_history = [{"role": "system", "content": self._full_system_prompt()}]
        self.messages_box.clear_widgets()
        self.add_bubble("چت جدید شروع شد. چطور می‌تونم کمکت کنم؟", is_user=False)

    def load_session(self, session_data):
        self.current_session_id = session_data["id"]
        self.conversation_history = session_data["messages"]
        self.messages_box.clear_widgets()
        for m in self.conversation_history:
            if m["role"] == "user":
                self.add_bubble(m["content"], is_user=True)
            elif m["role"] == "assistant":
                self.add_bubble(m["content"], is_user=False)

    def open_sessions_popup(self):
        self.save_current_session()

        popup = Popup(
            title=fa("چت‌های قبلی"), title_font="Vazir",
            size_hint=(0.9, 0.8), separator_color=(0.15, 0.45, 0.85, 1),
        )

        def build_list():
            sessions = self.list_sessions()
            content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10), size_hint_y=None)
            content.bind(minimum_height=content.setter("height"))

            if not sessions:
                content.add_widget(Label(
                    text=fa("هنوز چتی ذخیره نشده"), font_name="Vazir",
                    size_hint_y=None, height=dp(40),
                ))

            for s in sessions:
                row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(6))

                btn = Button(
                    text=fa(s.get("title") or "چت خالی"), font_name="Vazir",
                    background_color=(0.15, 0.16, 0.19, 1), background_normal="", color=(1, 1, 1, 1),
                )

                def make_open_handler(sess=s):
                    def handler(*a):
                        self.load_session(sess)
                        popup.dismiss()
                    return handler

                btn.bind(on_press=make_open_handler())

                del_btn = Button(
                    text="🗑", size_hint=(None, 1), width=dp(48),
                    background_color=(0.5, 0.15, 0.15, 1), background_normal="", color=(1, 1, 1, 1),
                )

                def make_delete_handler(sess=s):
                    def handler(*a):
                        self.confirm_delete(sess, refresh)
                    return handler

                del_btn.bind(on_press=make_delete_handler())

                row.add_widget(btn)
                row.add_widget(del_btn)
                content.add_widget(row)

            return content

        def refresh():
            scroll.clear_widgets()
            scroll.add_widget(build_list())

        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(build_list())

        popup.content = scroll
        popup.open()

    def confirm_delete(self, session_data, on_deleted):
        confirm_popup = Popup(
            title=fa("حذف چت"), title_font="Vazir",
            size_hint=(0.8, 0.35), separator_color=(0.5, 0.15, 0.15, 1),
        )

        content = BoxLayout(orientation="vertical", spacing=dp(14), padding=dp(16))
        content.add_widget(Label(
            text=fa(f'مطمئنید می‌خواید چت «{session_data.get("title") or "بدون‌عنوان"}» پاک بشه؟'),
            font_name="Vazir", halign="center",
        ))

        btn_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(10))

        cancel_btn = Button(
            text=fa("انصراف"), font_name="Vazir",
            background_color=(0.18, 0.19, 0.23, 1), background_normal="", color=(1, 1, 1, 1),
        )
        cancel_btn.bind(on_press=lambda *a: confirm_popup.dismiss())

        delete_btn = Button(
            text=fa("پاک کن"), font_name="Vazir",
            background_color=(0.6, 0.15, 0.15, 1), background_normal="", color=(1, 1, 1, 1),
        )

        def do_delete(*a):
            self.delete_session(session_data["id"])
            confirm_popup.dismiss()
            on_deleted()

        delete_btn.bind(on_press=do_delete)

        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(delete_btn)
        content.add_widget(btn_row)

        confirm_popup.content = content
        confirm_popup.open()

    def load_settings(self):
        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            level = data.get("level")
            if level in LEVELS:
                return level
        except Exception:
            pass
        return "نیمه‌تخصصی"

    def save_settings(self):
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump({"level": self.response_level}, f, ensure_ascii=False)
        except Exception as e:
            print("خطا در ذخیره‌ی تنظیمات:", e)

    def open_settings_popup(self):
        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(16))

        content.add_widget(Label(
            text=fa("سطح پاسخ‌دهی رو انتخاب کن:"), font_name="Vazir",
            size_hint_y=None, height=dp(36),
        ))

        popup = Popup(
            title=fa("تنظیمات"), title_font="Vazir",
            size_hint=(0.85, 0.5), separator_color=(0.15, 0.45, 0.85, 1),
        )

        for level in LEVELS:
            is_active = level == self.response_level
            btn = Button(
                text=fa(level + (" ✓" if is_active else "")), font_name="Vazir",
                size_hint_y=None, height=dp(48),
                background_color=(0.15, 0.45, 0.85, 1) if is_active else (0.18, 0.19, 0.23, 1),
                background_normal="", color=(1, 1, 1, 1),
            )

            def make_handler(lvl=level):
                def handler(*a):
                    self.response_level = lvl
                    self.save_settings()
                    if self.conversation_history and self.conversation_history[0]["role"] == "system":
                        self.conversation_history[0]["content"] = self._full_system_prompt()
                    popup.dismiss()
                return handler

            btn.bind(on_press=make_handler())
            content.add_widget(btn)

        popup.content = content
        popup.open()

    def on_pause(self):
        self.save_current_session()
        return True

    def on_stop(self):
        self.save_current_session()


if __name__ == "__main__":
    ChatApp().run()
