import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pynput import keyboard, mouse
import pyautogui
import threading
import time
import json


# ==========================================================
# ВНЕШНИЙ ВИД
# ==========================================================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG = "#10141D"
SIDEBAR = "#151B27"
CARD = "#1B2331"
CARD_LIGHT = "#222D3E"
BLUE = "#3987F5"
BLUE_HOVER = "#2469CE"
GREEN = "#20A875"
RED = "#D94B5B"
TEXT = "#F2F5FA"
MUTED = "#929EB0"

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

app = ctk.CTk()
app.title("Keyboard Auto Clicker")
app.geometry("1120x780")
app.minsize(950, 680)
app.configure(fg_color=BG)


# ==========================================================
# ДАННЫЕ
# ==========================================================

events = []

recording = False
playing = False

record_start = 0
last_move_time = 0
last_move_position = None

stop_event = threading.Event()
events_lock = threading.Lock()

keyboard_listener = None
mouse_listener = None


# ==========================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================================

def set_status(text, color=MUTED):
    status_label.configure(text=text, text_color=color)


def update_event_count():
    count_label.configure(text=str(len(events)))


def key_to_string(key):
    if isinstance(key, keyboard.KeyCode):
        if key.char is not None:
            return key.char
        if key.vk is not None:
            return f"vk:{key.vk}"

    if isinstance(key, keyboard.Key):
        return key.name

    return str(key)


def key_to_pyautogui(name):
    aliases = {
        "ctrl_l": "ctrl",
        "ctrl_r": "ctrl",
        "shift_l": "shift",
        "shift_r": "shift",
        "alt_l": "alt",
        "alt_r": "alt",
        "cmd": "win",
        "cmd_l": "win",
        "cmd_r": "win",
        "caps_lock": "capslock",
        "page_up": "pageup",
        "page_down": "pagedown",
    }

    if name.startswith("vk:"):
        return None

    return aliases.get(name, name)


def add_event(action, **details):
    if not recording:
        return

    item = {
        "time": time.monotonic() - record_start,
        "action": action,
        "details": details
    }

    with events_lock:
        events.append(item)


# ==========================================================
# ЗАПИСЬ КЛАВИАТУРЫ
# ==========================================================

def on_key_press(key):
    if key == keyboard.Key.f6:
        app.after(0, play_macro)
        return

    if key == keyboard.Key.f7:
        app.after(0, stop_all)
        return

    if recording:
        add_event("key_down", key=key_to_string(key))


def on_key_release(key):
    if recording:
        add_event("key_up", key=key_to_string(key))


# ==========================================================
# ЗАПИСЬ МЫШИ
# ==========================================================

def on_mouse_move(x, y):
    global last_move_time, last_move_position

    if not recording:
        return

    now = time.monotonic()

    if now - last_move_time < 0.03:
        return

    position = (x, y)

    if position == last_move_position:
        return

    last_move_time = now
    last_move_position = position

    add_event("mouse_move", x=x, y=y)


def on_mouse_click(x, y, button, pressed):
    if not recording:
        return

    action = "mouse_down" if pressed else "mouse_up"

    add_event(
        action,
        x=x,
        y=y,
        button=button.name
    )


def on_mouse_scroll(x, y, dx, dy):
    if recording:
        add_event(
            "mouse_scroll",
            x=x,
            y=y,
            dx=dx,
            dy=dy
        )


# ==========================================================
# ЗАПИСЬ МАКРОСА
# ==========================================================

def start_recording():
    global recording, events
    global record_start, last_move_time, last_move_position

    if recording or playing:
        return

    with events_lock:
        events = []

    record_start = time.monotonic()
    last_move_time = 0
    last_move_position = None

    recording = True

    update_event_count()
    refresh_event_table()

    set_status("● Идёт запись", RED)

    record_button.configure(state="disabled")
    stop_button.configure(state="normal")
    play_button.configure(state="disabled")


def stop_recording():
    global recording

    if not recording:
        return

    recording = False

    update_event_count()
    refresh_event_table()

    set_status("Запись завершена", GREEN)

    record_button.configure(state="normal")
    stop_button.configure(state="disabled")
    play_button.configure(state="normal")


# ==========================================================
# ТАБЛИЦА МАКРОСА
# ==========================================================

def refresh_event_table():
    for item in event_table.get_children():
        event_table.delete(item)

    with events_lock:
        current_events = list(events)

    for index, item in enumerate(current_events):
        action = item.get("action", "")
        details = item.get("details", {})
        event_time = item.get("time", 0)

        if action == "key_down":
            description = f"Нажатие клавиши: {details.get('key', '')}"

        elif action == "key_up":
            description = f"Отпускание клавиши: {details.get('key', '')}"

        elif action == "mouse_move":
            description = (
                f"Перемещение: X={details.get('x')}, "
                f"Y={details.get('y')}"
            )

        elif action == "mouse_down":
            description = f"Нажатие мыши: {details.get('button')}"

        elif action == "mouse_up":
            description = f"Отпускание мыши: {details.get('button')}"

        elif action == "mouse_scroll":
            description = (
                f"Колёсико: X={details.get('dx')}, "
                f"Y={details.get('dy')}"
            )

        else:
            description = str(details)

        event_table.insert(
            "",
            "end",
            iid=str(index),
            values=(
                index + 1,
                round(event_time * 1000),
                action,
                description
            )
        )


def get_selected_index():
    selection = event_table.selection()

    if not selection:
        return None

    return int(selection[0])


def select_event(event=None):
    index = get_selected_index()

    if index is None:
        return

    with events_lock:
        if index >= len(events):
            return

        value = events[index]["time"] * 1000

    delay_entry.delete(0, "end")
    delay_entry.insert(0, str(round(value)))


# ==========================================================
# РЕДАКТИРОВАНИЕ МАКРОСА
# ==========================================================

def delete_event():
    if recording or playing:
        return

    index = get_selected_index()

    if index is None:
        messagebox.showinfo("Редактор", "Выбери действие в таблице.")
        return

    with events_lock:
        if index < len(events):
            events.pop(index)

    refresh_event_table()
    update_event_count()


def move_event(direction):
    if recording or playing:
        return

    index = get_selected_index()

    if index is None:
        messagebox.showinfo("Редактор", "Выбери действие в таблице.")
        return

    new_index = index + direction

    with events_lock:
        if new_index < 0 or new_index >= len(events):
            return

        events[index], events[new_index] = (
            events[new_index],
            events[index]
        )

        # Время оставляем привязанным к позиции в последовательности.
        events[index]["time"], events[new_index]["time"] = (
            events[new_index]["time"],
            events[index]["time"]
        )

    refresh_event_table()
    event_table.selection_set(str(new_index))


def edit_event_delay():
    if recording or playing:
        return

    index = get_selected_index()

    if index is None:
        messagebox.showinfo("Редактор", "Выбери действие в таблице.")
        return

    try:
        new_ms = float(delay_entry.get().replace(",", "."))

        if new_ms < 0:
            raise ValueError

    except ValueError:
        messagebox.showerror(
            "Ошибка",
            "Введи положительное время в миллисекундах."
        )
        return

    new_time = new_ms / 1000

    with events_lock:
        previous_time = events[index - 1]["time"] if index > 0 else 0

        if new_time < previous_time:
            messagebox.showerror(
                "Ошибка",
                "Время не может быть меньше времени предыдущего действия."
            )
            return

        difference = new_time - events[index]["time"]

        for i in range(index, len(events)):
            events[i]["time"] += difference

    refresh_event_table()
    event_table.selection_set(str(index))


# ==========================================================
# ВОСПРОИЗВЕДЕНИЕ
# ==========================================================

def playback_finished():
    set_status("Готово", GREEN)

    record_button.configure(state="normal")
    stop_button.configure(state="disabled")
    play_button.configure(state="normal")


def execute_macro():
    global playing

    pressed_keys = set()
    pressed_buttons = set()

    try:
        repeats = int(repeat_entry.get())
        speed = float(speed_entry.get().replace(",", "."))

        with events_lock:
            macro = [dict(item) for item in events]

        if not macro:
            return

        repeat_number = 0

        while not stop_event.is_set():

            if repeats != 0 and repeat_number >= repeats:
                break

            previous_time = 0

            for item in macro:
                if stop_event.is_set():
                    break

                current_time = item["time"]
                delay = (current_time - previous_time) / speed

                if stop_event.wait(max(0, delay)):
                    break

                previous_time = current_time

                action = item["action"]
                details = item["details"]

                if action == "key_down":
                    key_name = key_to_pyautogui(details["key"])

                    if key_name:
                        pyautogui.keyDown(key_name)
                        pressed_keys.add(key_name)

                elif action == "key_up":
                    key_name = key_to_pyautogui(details["key"])

                    if key_name:
                        pyautogui.keyUp(key_name)
                        pressed_keys.discard(key_name)

                elif action == "mouse_move":
                    pyautogui.moveTo(
                        details["x"],
                        details["y"]
                    )

                elif action == "mouse_down":
                    button = details["button"]

                    pyautogui.mouseDown(
                        x=details["x"],
                        y=details["y"],
                        button=button
                    )

                    pressed_buttons.add(button)

                elif action == "mouse_up":
                    button = details["button"]

                    pyautogui.mouseUp(
                        x=details["x"],
                        y=details["y"],
                        button=button
                    )

                    pressed_buttons.discard(button)

                elif action == "mouse_scroll":
                    pyautogui.moveTo(
                        details["x"],
                        details["y"]
                    )

                    pyautogui.hscroll(details["dx"])
                    pyautogui.scroll(details["dy"])

            repeat_number += 1

    except pyautogui.FailSafeException:
        print("Аварийная остановка PyAutoGUI.")

    except Exception as error:
        app.after(
            0,
            lambda e=str(error): messagebox.showerror(
                "Ошибка воспроизведения",
                e
            )
        )

    finally:
        for key_name in pressed_keys:
            try:
                pyautogui.keyUp(key_name)
            except Exception:
                pass

        for button in pressed_buttons:
            try:
                pyautogui.mouseUp(button=button)
            except Exception:
                pass

        playing = False
        stop_event.set()

        app.after(0, playback_finished)


def play_macro():
    global playing

    if recording or playing:
        return

    with events_lock:
        if not events:
            messagebox.showinfo("Макрос", "Сначала запиши макрос.")
            return

    try:
        repeats = int(repeat_entry.get())
        speed = float(speed_entry.get().replace(",", "."))

        if repeats < 0 or speed <= 0:
            raise ValueError

    except ValueError:
        messagebox.showerror(
            "Настройки",
            "Повторы должны быть целым числом от 0, "
            "скорость — числом больше нуля."
        )
        return

    playing = True
    stop_event.clear()

    set_status("▶ Воспроизведение", BLUE)

    record_button.configure(state="disabled")
    stop_button.configure(state="normal")
    play_button.configure(state="disabled")

    threading.Thread(
        target=execute_macro,
        daemon=True
    ).start()


def stop_all():
    if recording:
        stop_recording()

    if playing:
        stop_event.set()
        set_status("Остановка...", RED)


# ==========================================================
# СОХРАНЕНИЕ И ЗАГРУЗКА
# ==========================================================

def save_macro():
    with events_lock:
        data = list(events)

    if not data:
        messagebox.showinfo("Сохранение", "Нет действий для сохранения.")
        return

    path = filedialog.asksaveasfilename(
        defaultextension=".json",
        filetypes=[("Макросы", "*.json")]
    )

    if not path:
        return

    try:
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

        messagebox.showinfo("Сохранение", "Макрос сохранён.")

    except Exception as error:
        messagebox.showerror("Ошибка", str(error))


def load_macro():
    global events

    if recording or playing:
        messagebox.showwarning(
            "Загрузка",
            "Сначала останови запись или воспроизведение."
        )
        return

    path = filedialog.askopenfilename(
        filetypes=[("Макросы", "*.json")]
    )

    if not path:
        return

    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

        allowed = {
            "key_down", "key_up",
            "mouse_move", "mouse_down",
            "mouse_up", "mouse_scroll"
        }

        if not isinstance(data, list):
            raise ValueError("Неверный формат файла.")

        previous_time = -1

        for item in data:
            if not isinstance(item, dict):
                raise ValueError("Некорректное действие.")

            if item.get("action") not in allowed:
                raise ValueError("Неизвестное действие.")

            if not isinstance(item.get("details"), dict):
                raise ValueError("Некорректные данные.")

            event_time = item.get("time")

            if not isinstance(event_time, (int, float)):
                raise ValueError("Некорректное время.")

            if event_time < previous_time or event_time < 0:
                raise ValueError("Нарушен порядок времени.")

            previous_time = event_time

        with events_lock:
            events = data

        refresh_event_table()
        update_event_count()
        set_status("Макрос загружен", GREEN)

    except Exception as error:
        messagebox.showerror("Ошибка загрузки", str(error))


# ==========================================================
# ОСНОВНАЯ СТРУКТУРА ИНТЕРФЕЙСА
# ==========================================================

root_frame = ctk.CTkFrame(app, fg_color=BG, corner_radius=0)
root_frame.pack(fill="both", expand=True)

# Боковая панель

sidebar = ctk.CTkFrame(
    root_frame,
    width=220,
    fg_color=SIDEBAR,
    corner_radius=0
)
sidebar.pack(side="left", fill="y")
sidebar.pack_propagate(False)

logo = ctk.CTkLabel(
    sidebar,
    text="⌨  KEYFLOW",
    font=ctk.CTkFont(size=22, weight="bold"),
    text_color=TEXT
)
logo.pack(pady=(30, 35), padx=20)

nav_label = ctk.CTkLabel(
    sidebar,
    text="РАБОЧЕЕ ПРОСТРАНСТВО",
    text_color=MUTED,
    font=ctk.CTkFont(size=10, weight="bold")
)
nav_label.pack(anchor="w", padx=20, pady=(0, 10))


# Правая рабочая область

workspace = ctk.CTkFrame(
    root_frame,
    fg_color=BG,
    corner_radius=0
)
workspace.pack(side="left", fill="both", expand=True)


# Заголовок

header = ctk.CTkFrame(
    workspace,
    fg_color=BG,
    corner_radius=0,
    height=85
)
header.pack(fill="x", padx=30, pady=(20, 5))
header.pack_propagate(False)

header_title = ctk.CTkLabel(
    header,
    text="Keyboard Auto Clicker",
    font=ctk.CTkFont(size=27, weight="bold"),
    text_color=TEXT
)
header_title.pack(side="left", anchor="center")

header_version = ctk.CTkLabel(
    header,
    text="VERSION 6.0",
    text_color=MUTED,
    fg_color=CARD,
    corner_radius=8,
    padx=12,
    pady=7
)
header_version.pack(side="right", anchor="center")


# Вкладки

tabs = ctk.CTkTabview(
    workspace,
    fg_color=BG,
    segmented_button_fg_color=CARD,
    segmented_button_selected_color=BLUE,
    segmented_button_selected_hover_color=BLUE_HOVER,
    segmented_button_unselected_color=CARD,
    segmented_button_unselected_hover_color=CARD_LIGHT,
    text_color=TEXT,
    corner_radius=12
)
tabs.pack(fill="both", expand=True, padx=25, pady=10)

home_tab = tabs.add("Главная")
editor_tab = tabs.add("Редактор")
settings_tab = tabs.add("Настройки")


# ==========================================================
# БОКОВАЯ НАВИГАЦИЯ
# ==========================================================

def open_home():
    tabs.set("Главная")


def open_editor():
    tabs.set("Редактор")


def open_settings():
    tabs.set("Настройки")


def nav_button(text, command):
    button = ctk.CTkButton(
        sidebar,
        text=text,
        command=command,
        height=43,
        corner_radius=10,
        fg_color="transparent",
        hover_color=CARD_LIGHT,
        text_color=TEXT,
        anchor="w",
        font=ctk.CTkFont(size=14)
    )
    button.pack(fill="x", padx=12, pady=4)
    return button


nav_button("⌂   Главная", open_home)
nav_button("☷   Редактор макросов", open_editor)
nav_button("⚙   Настройки", open_settings)

sidebar_bottom = ctk.CTkFrame(
    sidebar,
    fg_color="transparent"
)
sidebar_bottom.pack(side="bottom", fill="x", padx=15, pady=20)

ctk.CTkLabel(
    sidebar_bottom,
    text="KEYFLOW",
    text_color=MUTED,
    font=ctk.CTkFont(size=11, weight="bold")
).pack(anchor="w")

ctk.CTkLabel(
    sidebar_bottom,
    text="Автоматизация действий",
    text_color=MUTED,
    font=ctk.CTkFont(size=10)
).pack(anchor="w", pady=(4, 0))


# ==========================================================
# ВКЛАДКА «ГЛАВНАЯ»
# ==========================================================

home_title = ctk.CTkLabel(
    home_tab,
    text="Добро пожаловать!",
    font=ctk.CTkFont(size=24, weight="bold"),
    text_color=TEXT
)
home_title.pack(anchor="w", padx=15, pady=(15, 3))

home_description = ctk.CTkLabel(
    home_tab,
    text="Записывай действия и воспроизводи их автоматически.",
    text_color=MUTED,
    font=ctk.CTkFont(size=13)
)
home_description.pack(anchor="w", padx=15, pady=(0, 20))


# Карточки статистики

stats_frame = ctk.CTkFrame(
    home_tab,
    fg_color="transparent"
)
stats_frame.pack(fill="x", padx=10, pady=5)

count_card = ctk.CTkFrame(
    stats_frame,
    fg_color=CARD,
    corner_radius=14,
    height=100
)
count_card.pack(side="left", fill="x", expand=True, padx=5)
count_card.pack_propagate(False)

ctk.CTkLabel(
    count_card,
    text="ЗАПИСАННЫЕ ДЕЙСТВИЯ",
    text_color=MUTED,
    font=ctk.CTkFont(size=11, weight="bold")
).pack(anchor="w", padx=18, pady=(15, 3))

count_label = ctk.CTkLabel(
    count_card,
    text="0",
    text_color=TEXT,
    font=ctk.CTkFont(size=27, weight="bold")
)
count_label.pack(anchor="w", padx=18)


status_card = ctk.CTkFrame(
    stats_frame,
    fg_color=CARD,
    corner_radius=14,
    height=100
)
status_card.pack(side="left", fill="x", expand=True, padx=5)
status_card.pack_propagate(False)

ctk.CTkLabel(
    status_card,
    text="СОСТОЯНИЕ",
    text_color=MUTED,
    font=ctk.CTkFont(size=11, weight="bold")
).pack(anchor="w", padx=18, pady=(15, 3))

status_label = ctk.CTkLabel(
    status_card,
    text="Готово",
    text_color=GREEN,
    font=ctk.CTkFont(size=20, weight="bold")
)
status_label.pack(anchor="w", padx=18)


# Карточка управления

control_card = ctk.CTkFrame(
    home_tab,
    fg_color=CARD,
    corner_radius=16
)
control_card.pack(fill="x", padx=15, pady=20)

ctk.CTkLabel(
    control_card,
    text="Управление записью",
    text_color=TEXT,
    font=ctk.CTkFont(size=19, weight="bold")
).pack(anchor="w", padx=20, pady=(18, 5))

ctk.CTkLabel(
    control_card,
    text="Запиши последовательность действий или запусти готовый макрос.",
    text_color=MUTED,
    font=ctk.CTkFont(size=12)
).pack(anchor="w", padx=20, pady=(0, 15))


button_row = ctk.CTkFrame(
    control_card,
    fg_color="transparent"
)
button_row.pack(fill="x", padx=15, pady=(0, 18))


record_button = ctk.CTkButton(
    button_row,
    text="●  Начать запись",
    command=start_recording,
    height=48,
    corner_radius=10,
    fg_color=RED,
    hover_color="#B93749",
    font=ctk.CTkFont(size=14, weight="bold")
)
record_button.pack(side="left", fill="x", expand=True, padx=5)


stop_button = ctk.CTkButton(
    button_row,
    text="■  Остановить",
    command=stop_all,
    height=48,
    corner_radius=10,
    fg_color=CARD_LIGHT,
    hover_color="#344258",
    font=ctk.CTkFont(size=14, weight="bold"),
    state="disabled"
)
stop_button.pack(side="left", fill="x", expand=True, padx=5)


play_button = ctk.CTkButton(
    button_row,
    text="▶  Воспроизвести",
    command=play_macro,
    height=48,
    corner_radius=10,
    fg_color=GREEN,
    hover_color="#167D57",
    font=ctk.CTkFont(size=14, weight="bold")
)
play_button.pack(side="left", fill="x", expand=True, padx=5)


# Быстрые действия

quick_title = ctk.CTkLabel(
    home_tab,
    text="Быстрые действия",
    font=ctk.CTkFont(size=18, weight="bold"),
    text_color=TEXT
)
quick_title.pack(anchor="w", padx=15, pady=(5, 10))


quick_frame = ctk.CTkFrame(
    home_tab,
    fg_color="transparent"
)
quick_frame.pack(fill="x", padx=10)


ctk.CTkButton(
    quick_frame,
    text="💾  Сохранить макрос",
    command=save_macro,
    height=42,
    fg_color=CARD,
    hover_color=CARD_LIGHT,
    text_color=TEXT
).pack(side="left", fill="x", expand=True, padx=5)


ctk.CTkButton(
    quick_frame,
    text="📂  Загрузить макрос",
    command=load_macro,
    height=42,
    fg_color=CARD,
    hover_color=CARD_LIGHT,
    text_color=TEXT
).pack(side="left", fill="x", expand=True, padx=5)


# Подсказка

ctk.CTkLabel(
    home_tab,
    text="Горячие клавиши: F6 — запуск   •   F7 — остановка",
    text_color=MUTED,
    font=ctk.CTkFont(size=12)
).pack(anchor="w", padx=15, pady=20)


# ==========================================================
# ВКЛАДКА «РЕДАКТОР»
# ==========================================================

editor_title = ctk.CTkLabel(
    editor_tab,
    text="Редактор макросов",
    text_color=TEXT,
    font=ctk.CTkFont(size=23, weight="bold")
)
editor_title.pack(anchor="w", padx=15, pady=(15, 5))

ctk.CTkLabel(
    editor_tab,
    text="Выбери действие в списке, чтобы изменить его.",
    text_color=MUTED
).pack(anchor="w", padx=15, pady=(0, 12))


table_container = ctk.CTkFrame(
    editor_tab,
    fg_color=CARD,
    corner_radius=12
)
table_container.pack(
    fill="both",
    expand=True,
    padx=10,
    pady=5
)


style = ttk.Style()
style.theme_use("default")

style.configure(
    "Treeview",
    background="#1B2331",
    foreground="#F2F5FA",
    fieldbackground="#1B2331",
    rowheight=31,
    borderwidth=0,
    font=("Segoe UI", 10)
)

style.configure(
    "Treeview.Heading",
    background="#283449",
    foreground="#FFFFFF",
    relief="flat",
    font=("Segoe UI", 10, "bold")
)

style.map(
    "Treeview",
    background=[("selected", "#286AC0")],
    foreground=[("selected", "#FFFFFF")]
)


columns = ("number", "time", "action", "details")

event_table = ttk.Treeview(
    table_container,
    columns=columns,
    show="headings",
    height=12
)

event_table.heading("number", text="№")
event_table.heading("time", text="Время, мс")
event_table.heading("action", text="Действие")
event_table.heading("details", text="Подробности")

event_table.column("number", width=45, anchor="center")
event_table.column("time", width=100, anchor="center")
event_table.column("action", width=130, anchor="center")
event_table.column("details", width=450, anchor="w")

scrollbar = ttk.Scrollbar(
    table_container,
    orient="vertical",
    command=event_table.yview
)

event_table.configure(yscrollcommand=scrollbar.set)

event_table.pack(
    side="left",
    fill="both",
    expand=True,
    padx=(8, 0),
    pady=8
)

scrollbar.pack(
    side="right",
    fill="y",
    padx=8,
    pady=8
)

event_table.bind("<<TreeviewSelect>>", select_event)


edit_card = ctk.CTkFrame(
    editor_tab,
    fg_color=CARD,
    corner_radius=12
)
edit_card.pack(fill="x", padx=10, pady=12)

ctk.CTkLabel(
    edit_card,
    text="Изменение выбранного действия",
    text_color=TEXT,
    font=ctk.CTkFont(size=15, weight="bold")
).pack(anchor="w", padx=15, pady=(12, 8))


edit_row = ctk.CTkFrame(
    edit_card,
    fg_color="transparent"
)
edit_row.pack(fill="x", padx=10, pady=(0, 12))


delay_entry = ctk.CTkEntry(
    edit_row,
    placeholder_text="Время в мс",
    width=110,
    height=38
)
delay_entry.pack(side="left", padx=5)


ctk.CTkButton(
    edit_row,
    text="Изменить время",
    command=edit_event_delay,
    height=38,
    width=125
).pack(side="left", padx=5)


ctk.CTkButton(
    edit_row,
    text="↑ Вверх",
    command=lambda: move_event(-1),
    height=38,
    width=85,
    fg_color=CARD_LIGHT,
    hover_color="#344258"
).pack(side="left", padx=5)


ctk.CTkButton(
    edit_row,
    text="↓ Вниз",
    command=lambda: move_event(1),
    height=38,
    width=85,
    fg_color=CARD_LIGHT,
    hover_color="#344258"
).pack(side="left", padx=5)


ctk.CTkButton(
    edit_row,
    text="Удалить",
    command=delete_event,
    height=38,
    width=90,
    fg_color=RED,
    hover_color="#B93749"
).pack(side="left", padx=5)


# ==========================================================
# ВКЛАДКА «НАСТРОЙКИ»
# ==========================================================

settings_title = ctk.CTkLabel(
    settings_tab,
    text="Настройки воспроизведения",
    text_color=TEXT,
    font=ctk.CTkFont(size=23, weight="bold")
)
settings_title.pack(anchor="w", padx=15, pady=(15, 5))


settings_description = ctk.CTkLabel(
    settings_tab,
    text="Настрой количество повторов и скорость выполнения макроса.",
    text_color=MUTED
)
settings_description.pack(anchor="w", padx=15, pady=(0, 20))


repeat_card = ctk.CTkFrame(
    settings_tab,
    fg_color=CARD,
    corner_radius=12
)
repeat_card.pack(fill="x", padx=15, pady=8)

ctk.CTkLabel(
    repeat_card,
    text="Количество повторов",
    text_color=TEXT,
    font=ctk.CTkFont(size=16, weight="bold")
).pack(anchor="w", padx=18, pady=(15, 3))

ctk.CTkLabel(
    repeat_card,
    text="Укажи, сколько раз нужно выполнить макрос. 0 — бесконечно.",
    text_color=MUTED
).pack(anchor="w", padx=18, pady=(0, 10))

repeat_entry = ctk.CTkEntry(
    repeat_card,
    width=130,
    height=40
)
repeat_entry.insert(0, "1")
repeat_entry.pack(anchor="w", padx=18, pady=(0, 15))


speed_card = ctk.CTkFrame(
    settings_tab,
    fg_color=CARD,
    corner_radius=12
)
speed_card.pack(fill="x", padx=15, pady=8)

ctk.CTkLabel(
    speed_card,
    text="Скорость воспроизведения",
    text_color=TEXT,
    font=ctk.CTkFont(size=16, weight="bold")
).pack(anchor="w", padx=18, pady=(15, 3))

ctk.CTkLabel(
    speed_card,
    text="1 — обычная скорость, 2 — в два раза быстрее, 0.5 — медленнее.",
    text_color=MUTED
).pack(anchor="w", padx=18, pady=(0, 10))

speed_entry = ctk.CTkEntry(
    speed_card,
    width=130,
    height=40
)
speed_entry.insert(0, "1")
speed_entry.pack(anchor="w", padx=18, pady=(0, 15))


hotkey_card = ctk.CTkFrame(
    settings_tab,
    fg_color=CARD,
    corner_radius=12
)
hotkey_card.pack(fill="x", padx=15, pady=8)

ctk.CTkLabel(
    hotkey_card,
    text="Горячие клавиши",
    text_color=TEXT,
    font=ctk.CTkFont(size=16, weight="bold")
).pack(anchor="w", padx=18, pady=(15, 8))

ctk.CTkLabel(
    hotkey_card,
    text="F6 — запустить макрос\nF7 — остановить запись или воспроизведение",
    text_color=MUTED,
    justify="left"
).pack(anchor="w", padx=18, pady=(0, 15))


# ==========================================================
# ГОРЯЧИЕ КЛАВИШИ И ЗАПУСК
# ==========================================================

def start_listeners():
    global keyboard_listener, mouse_listener

    keyboard_listener = keyboard.Listener(
        on_press=on_key_press,
        on_release=on_key_release
    )

    mouse_listener = mouse.Listener(
        on_move=on_mouse_move,
        on_click=on_mouse_click,
        on_scroll=on_mouse_scroll
    )

    keyboard_listener.start()
    mouse_listener.start()


def close_app():
    global recording

    recording = False
    stop_event.set()

    try:
        if keyboard_listener:
            keyboard_listener.stop()

        if mouse_listener:
            mouse_listener.stop()

    except Exception:
        pass

    app.destroy()


app.protocol("WM_DELETE_WINDOW", close_app)

start_listeners()

app.mainloop()