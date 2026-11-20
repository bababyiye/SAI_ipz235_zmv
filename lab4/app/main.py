import re
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from openai import APIConnectionError, APITimeoutError, NotFoundError, OpenAI

DEFAULT_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen3.5:9b"

# Палітра темної RPG-теми (Obsidian Dark)
BG_MAIN = "#0d1117"       # Основний чорний фон вікна
BG_PANEL = "#161b22"      # Фон карток і рамок
BG_INPUT = "#090c10"      # Фон текстових полів та інвентарю
BG_BTN = "#21262d"        # Фон стандартних кнопок
BG_BTN_HOVER = "#30363d"  # Наведення на кнопку
BORDER_COLOR = "#30363d"  # Колір рамок

FG_PRIMARY = "#f0f6fc"    # Основний білий текст
FG_MUTED = "#8b949e"      # Другорядний сірий текст
ACCENT_BLUE = "#58a6ff"   # Акцент для дій гравця та варіантів
ACCENT_GREEN = "#238636"  # Кнопка старту / виконання ходу
ACCENT_GREEN_H = "#2ea043"
ACCENT_RED = "#da3633"    # Кнопка зупинки / критичний HP
ACCENT_RED_H = "#f85149"
ACCENT_GOLD = "#f1c40f"   # Золото / кредити
ACCENT_AMBER = "#d29922"  # Системні повідомлення / середній HP

SETTINGS = {
    "Темне фентезі: Підземелля Карнаку": (
        "Ти — ведучий (Game Master) текстової RPG у стилі темного фентезі. "
        "Гравець — шукач пригод у занедбаних катакомбах під стародавнім містом Карнак. "
        "Початковий стан: HP=100, Золото=15, Інвентар: Смолоскип, Іржавий меч, Зілля лікування."
    ),
    "Кіберпанк 2088: Нео-Житомир": (
        "Ти — ведучий (Game Master) текстової кіберпанк-RPG у мегаполісі Нео-Житомир 2088 року. "
        "Гравець — нетраннер-одинак, який виконує небезпечне замовлення зі зламу корпоративного сервера. "
        "Початковий стан: HP=100, Золото=50, Інвентар: Кібердека, ЕМІ-граната, Стимулятор."
    ),
    "Космос: Аварія на станції «Оріон»": (
        "Ти — ведучий (Game Master) науково-фантастичної RPG на виживання. "
        "Гравець прокидається у пошкодженому відсіку орбітальної станції «Оріон» після метеоритного удару. "
        "Початковий стан: HP=100, Золото=0, Інвентар: Лазерний різак, Аптечка, Сканер."
    ),
    "Детектив: Тіні старого порту": (
        "Ти — ведучий (Game Master) детективної нуар-RPG 1930-х років. "
        "Гравець — приватний детектив, який розслідує зникнення важливого свідка у нічному порту. "
        "Початковий стан: HP=100, Золото=30, Інвентар: Револьвер, Блокнот, Ліхтарик."
    ),
}

SYSTEM_RULES = """
Правила ведення гри:
1. Пиши захопливо, атмосферно, українською мовою (4–6 речень на хід).
2. Реагуй логічно на дії гравця: небезпечні дії зменшують HP (на 10–35), використання аптечки/зілля відновлює HP (не більше 100) і прибирає предмет з інвентарю.
3. Не дозволяй гравцеві використовувати предмети, яких немає в інвентарі. Якщо HP опускається до 0, опиши фінал пригоди.
4. Наприкінці КОЖНОЇ відповіді з нового рядка обов'язково додай технічний рядок стану суворо у форматі:
[STATE: HP=100 | GOLD=15 | INV=Предмет 1, Предмет 2 | OPT1=Дія 1 | OPT2=Дія 2 | OPT3=Дія 3]
Не додавай жодного тексту після закриваючої дужки ].
5. Не пиши нумерований або маркований список варіантів дій у тексті сюжету — передавай варіанти вибору ЛИШЕ в полях OPT1, OPT2, OPT3 рядка [STATE: ...].
"""


class AIRPGQuestApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AI Game Master — Локальний текстовий RPG-квест (Qwen3.5)")
        self.root.geometry("1060x760")
        self.root.minsize(900, 640)
        self.root.configure(bg=BG_MAIN)

        self.messages = []
        self.is_generating = False
        self.stop_requested = False
        self.game_over = False
        self.turn_count = 0

        self.hp = 100
        self.gold = 0
        self.inventory = []

        self._setup_dark_theme()
        self._build_ui()

    def _setup_dark_theme(self):
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")

        # Налаштування випадаючого списку Combobox
        self.root.option_add("*TCombobox*Listbox.background", BG_INPUT)
        self.root.option_add("*TCombobox*Listbox.foreground", FG_PRIMARY)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT_BLUE)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#000000")

        self.style.configure("TFrame", background=BG_MAIN)
        self.style.configure("Panel.TFrame", background=BG_PANEL)

        self.style.configure(
            "TLabelframe",
            background=BG_PANEL,
            bordercolor=BORDER_COLOR,
            darkcolor=BORDER_COLOR,
            lightcolor=BORDER_COLOR,
            relief="solid",
        )
        self.style.configure(
            "TLabelframe.Label",
            background=BG_PANEL,
            foreground=ACCENT_BLUE,
            font=("Segoe UI", 9, "bold"),
        )

        self.style.configure("TLabel", background=BG_PANEL, foreground=FG_PRIMARY, font=("Segoe UI", 9))
        self.style.configure("Main.TLabel", background=BG_MAIN, foreground=FG_PRIMARY, font=("Segoe UI", 9))
        self.style.configure("Muted.TLabel", background=BG_PANEL, foreground=FG_MUTED, font=("Segoe UI", 9))
        self.style.configure("Gold.TLabel", background=BG_PANEL, foreground=ACCENT_GOLD, font=("Segoe UI", 10, "bold"))
        self.style.configure("Turn.TLabel", background=BG_PANEL, foreground=FG_PRIMARY, font=("Segoe UI", 11, "bold"))
        self.style.configure(
            "Status.TLabel",
            background=BG_PANEL,
            foreground=FG_PRIMARY,
            bordercolor=BORDER_COLOR,
            relief="solid",
            font=("Segoe UI", 9),
        )

        # Стандартні кнопки
        self.style.configure(
            "TButton",
            background=BG_BTN,
            foreground=FG_PRIMARY,
            bordercolor=BORDER_COLOR,
            focuscolor=ACCENT_BLUE,
            font=("Segoe UI", 9, "bold"),
            padding=(10, 5),
        )
        self.style.map(
            "TButton",
            background=[("active", BG_BTN_HOVER), ("disabled", "#12161c")],
            foreground=[("disabled", "#484f58")],
        )

        # Кнопка "Нова гра" / "Виконати хід" (зелена)
        self.style.configure(
            "Primary.TButton",
            background=ACCENT_GREEN,
            foreground="#ffffff",
            bordercolor=ACCENT_GREEN_H,
            font=("Segoe UI", 9, "bold"),
            padding=(12, 5),
        )
        self.style.map(
            "Primary.TButton",
            background=[("active", ACCENT_GREEN_H), ("disabled", "#152b1c")],
            foreground=[("disabled", "#567d62")],
        )

        # Кнопка "Стоп" (червона)
        self.style.configure(
            "Danger.TButton",
            background=ACCENT_RED,
            foreground="#ffffff",
            bordercolor=ACCENT_RED_H,
            font=("Segoe UI", 9, "bold"),
            padding=(10, 5),
        )
        self.style.map(
            "Danger.TButton",
            background=[("active", ACCENT_RED_H), ("disabled", "#2b1618")],
            foreground=[("disabled", "#7a494b")],
        )

        # Кнопки швидкого вибору дій
        self.style.configure(
            "Option.TButton",
            background="#16202e",
            foreground="#a5d6ff",
            bordercolor="#2f4b6e",
            font=("Segoe UI", 9),
            padding=(8, 6),
        )
        self.style.map(
            "Option.TButton",
            background=[("active", "#1f324a"), ("disabled", "#12161c")],
            foreground=[("active", "#ffffff"), ("disabled", "#484f58")],
        )

        # Поля вводу, Combobox, Spinbox
        self.style.configure(
            "TEntry",
            fieldbackground=BG_INPUT,
            foreground=FG_PRIMARY,
            insertcolor=FG_PRIMARY,
            bordercolor=BORDER_COLOR,
            padding=4,
        )
        self.style.configure(
            "TCombobox",
            fieldbackground=BG_INPUT,
            background=BG_BTN,
            foreground=FG_PRIMARY,
            arrowcolor=FG_PRIMARY,
            bordercolor=BORDER_COLOR,
            padding=4,
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", BG_INPUT)],
            foreground=[("readonly", FG_PRIMARY)],
            selectbackground=[("readonly", BG_INPUT)],
            selectforeground=[("readonly", FG_PRIMARY)],
        )
        self.style.configure(
            "TSpinbox",
            fieldbackground=BG_INPUT,
            background=BG_BTN,
            foreground=FG_PRIMARY,
            arrowcolor=FG_PRIMARY,
            bordercolor=BORDER_COLOR,
            padding=4,
        )

        # Прогрес-бари (HP та індикатор завантаження)
        self.style.configure(
            "HP.Horizontal.TProgressbar",
            troughcolor=BG_INPUT,
            background=ACCENT_GREEN_H,
            bordercolor=BORDER_COLOR,
            thickness=14,
        )
        self.style.configure(
            "Status.Horizontal.TProgressbar",
            troughcolor=BG_INPUT,
            background=ACCENT_BLUE,
            bordercolor=BORDER_COLOR,
            thickness=14,
        )

    def _build_ui(self):
        root_frame = ttk.Frame(self.root, padding=10)
        root_frame.pack(fill=tk.BOTH, expand=True)

        # --- Верхня панель налаштувань ---
        top_frame = ttk.LabelFrame(root_frame, text="Параметри гри та локальної LLM", padding=8)
        top_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(top_frame, text="Сеттинг:").grid(row=0, column=0, sticky=tk.W, padx=(0, 4))
        self.setting_var = tk.StringVar(value=list(SETTINGS.keys())[0])
        setting_cb = ttk.Combobox(
            top_frame, textvariable=self.setting_var, values=list(SETTINGS.keys()), state="readonly", width=34
        )
        setting_cb.grid(row=0, column=1, columnspan=2, sticky=tk.EW, padx=(0, 10))

        self.new_game_btn = ttk.Button(
            top_frame, text="▶ Нова гра", style="Primary.TButton", command=self.start_new_game
        )
        self.new_game_btn.grid(row=0, column=3, padx=(0, 6))

        ttk.Button(top_frame, text="Зберегти лог (.txt)", command=self.save_log).grid(row=0, column=4, padx=(0, 12))

        ttk.Label(top_frame, text="Base URL:").grid(row=0, column=5, sticky=tk.W, padx=(0, 4))
        self.url_var = tk.StringVar(value=DEFAULT_URL)
        ttk.Entry(top_frame, textvariable=self.url_var, width=24).grid(row=0, column=6, sticky=tk.W)

        # Другий рядок налаштувань генерації
        ttk.Label(top_frame, text="Модель:").grid(row=1, column=0, sticky=tk.W, pady=(8, 0), padx=(0, 4))
        self.model_var = tk.StringVar(value=DEFAULT_MODEL)
        ttk.Entry(top_frame, textvariable=self.model_var, width=16).grid(row=1, column=1, sticky=tk.W, pady=(8, 0))

        ttk.Label(top_frame, text="Temperature:").grid(row=1, column=2, sticky=tk.W, pady=(8, 0), padx=(0, 4))
        self.temp_var = tk.DoubleVar(value=0.7)
        ttk.Spinbox(
            top_frame, from_=0.0, to=1.5, increment=0.1, textvariable=self.temp_var, width=7
        ).grid(row=1, column=3, sticky=tk.W, pady=(8, 0))

        ttk.Label(top_frame, text="Max tokens:").grid(row=1, column=4, sticky=tk.W, pady=(8, 0), padx=(0, 4))
        self.max_tokens_var = tk.IntVar(value=650)
        ttk.Spinbox(
            top_frame, from_=100, to=2000, increment=50, textvariable=self.max_tokens_var, width=8
        ).grid(row=1, column=5, sticky=tk.W, pady=(8, 0))

        ttk.Label(top_frame, text="Контекст (num_ctx):").grid(row=1, column=6, sticky=tk.W, pady=(8, 0))
        self.ctx_var = tk.IntVar(value=4096)
        ttk.Spinbox(
            top_frame, from_=1024, to=16384, increment=1024, textvariable=self.ctx_var, width=8
        ).grid(row=1, column=7, sticky=tk.W, pady=(8, 0), padx=(4, 0))

        # --- Основна зона: зліва сюжет, справа стан персонажа ---
        center_frame = ttk.Frame(root_frame)
        center_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        story_frame = ttk.LabelFrame(center_frame, text="Журнал пригоди (стрімінг відповіді)", padding=8)
        story_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        self.story_text = scrolledtext.ScrolledText(
            story_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            state=tk.DISABLED,
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            insertbackground=FG_PRIMARY,
            selectbackground=ACCENT_BLUE,
            selectforeground="#000000",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
            highlightcolor=ACCENT_BLUE,
            padx=10,
            pady=8,
        )
        self.story_text.pack(fill=tk.BOTH, expand=True)
        self.story_text.tag_configure("player", foreground=ACCENT_BLUE, font=("Segoe UI", 10, "bold"))
        self.story_text.tag_configure("system_msg", foreground=ACCENT_AMBER, font=("Segoe UI", 10, "italic"))
        self.story_text.tag_configure("death_msg", foreground=ACCENT_RED_H, font=("Segoe UI", 10, "bold"))

        # Права панель: статус персонажа
        stats_frame = ttk.LabelFrame(center_frame, text="Стан персонажа", padding=10, width=265)
        stats_frame.pack(side=tk.RIGHT, fill=tk.Y)
        stats_frame.pack_propagate(False)

        self.turn_label = ttk.Label(stats_frame, text="Хід: 0", style="Turn.TLabel")
        self.turn_label.pack(anchor=tk.W, pady=(0, 10))

        self.hp_label = ttk.Label(stats_frame, text="Здоров'я (HP): 100 / 100", font=("Segoe UI", 9, "bold"))
        self.hp_label.pack(anchor=tk.W)
        self.hp_bar = ttk.Progressbar(stats_frame, maximum=100, value=100, style="HP.Horizontal.TProgressbar")
        self.hp_bar.pack(fill=tk.X, pady=(4, 12))

        self.gold_label = ttk.Label(stats_frame, text="Золото / Кредити: 0", style="Gold.TLabel")
        self.gold_label.pack(anchor=tk.W, pady=(0, 12))

        ttk.Label(stats_frame, text="Інвентар:", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(0, 4))
        self.inv_listbox = tk.Listbox(
            stats_frame,
            height=12,
            font=("Segoe UI", 9),
            bg=BG_INPUT,
            fg="#7ee787",
            selectbackground=ACCENT_BLUE,
            selectforeground="#000000",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
        )
        self.inv_listbox.pack(fill=tk.BOTH, expand=True)

        # --- Панель швидких варіантів дій ---
        opt_frame = ttk.LabelFrame(root_frame, text="Швидкі варіанти вибору (від Game Master)", padding=6)
        opt_frame.pack(fill=tk.X, pady=(0, 8))

        self.opt_buttons = []
        for idx in range(3):
            btn = ttk.Button(
                opt_frame,
                text=f"Варіант {idx + 1}",
                style="Option.TButton",
                command=lambda i=idx: self.choose_quick_option(i),
                state=tk.DISABLED,
            )
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
            self.opt_buttons.append(btn)

        # --- Ввід власної дії ---
        action_frame = ttk.Frame(root_frame)
        action_frame.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(action_frame, text="Ваша дія:", style="Main.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        self.action_var = tk.StringVar()
        self.action_entry = ttk.Entry(action_frame, textvariable=self.action_var, font=("Segoe UI", 10))
        self.action_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.action_entry.bind("<Return>", lambda _e: self.send_player_action())

        self.send_btn = ttk.Button(
            action_frame, text="Виконати хід", style="Primary.TButton", command=self.send_player_action, state=tk.DISABLED
        )
        self.send_btn.pack(side=tk.LEFT, padx=(0, 4))

        self.stop_btn = ttk.Button(
            action_frame, text="■ Стоп", style="Danger.TButton", command=self.stop_generation, state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT)

        # --- Статус-бар ---
        status_frame = ttk.Frame(root_frame)
        status_frame.pack(fill=tk.X)

        self.status_var = tk.StringVar(value="Натисніть «▶ Нова гра», щоб розпочати пригоду.")
        ttk.Label(status_frame, textvariable=self.status_var, style="Status.TLabel", anchor=tk.W, padding=(8, 4)).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        self.progress = ttk.Progressbar(
            status_frame, mode="indeterminate", length=150, style="Status.Horizontal.TProgressbar"
        )
        self.progress.pack(side=tk.RIGHT, padx=(6, 0))

    def _append_story(self, text: str, tag: str = None):
        self.story_text.config(state=tk.NORMAL)
        if tag:
            self.story_text.insert(tk.END, text, tag)
        else:
            self.story_text.insert(tk.END, text)
        self.story_text.see(tk.END)
        self.story_text.config(state=tk.DISABLED)

    def _clear_story(self):
        self.story_text.config(state=tk.NORMAL)
        self.story_text.delete("1.0", tk.END)
        self.story_text.config(state=tk.DISABLED)

    def _update_stats_ui(self, options=None):
        self.turn_label.config(text=f"Хід: {self.turn_count}")
        self.hp = max(0, min(100, self.hp))
        self.hp_label.config(text=f"Здоров'я (HP): {self.hp} / 100")
        self.hp_bar["value"] = self.hp

        # Динамічний колір шкали здоров'я
        if self.hp > 50:
            self.style.configure("HP.Horizontal.TProgressbar", background=ACCENT_GREEN_H)
        elif self.hp > 25:
            self.style.configure("HP.Horizontal.TProgressbar", background=ACCENT_AMBER)
        else:
            self.style.configure("HP.Horizontal.TProgressbar", background=ACCENT_RED_H)

        self.gold_label.config(text=f"Золото / Кредити: {self.gold}")

        self.inv_listbox.delete(0, tk.END)
        if self.inventory:
            for item in self.inventory:
                self.inv_listbox.insert(tk.END, f"✦ {item}")
        else:
            self.inv_listbox.insert(tk.END, "(порожньо)")

        if options:
            for i, btn in enumerate(self.opt_buttons):
                if i < len(options) and options[i]:
                    btn.config(text=options[i], state=tk.NORMAL if not self.game_over else tk.DISABLED)
                else:
                    btn.config(text="—", state=tk.DISABLED)

    def _parse_and_apply_state(self, full_text: str):
        match = re.search(r"\[STATE:\s*(.*?)\]", full_text, re.DOTALL)
        if not match:
            return
        state_str = match.group(1)
        parts = [p.strip() for p in state_str.split("|")]
        parsed_opts = ["", "", ""]

        for part in parts:
            if "=" not in part:
                continue
            key, val = part.split("=", 1)
            key = key.strip().upper()
            val = val.strip()

            if key == "HP":
                nums = re.findall(r"\d+", val)
                if nums:
                    self.hp = int(nums[0])
            elif key == "GOLD":
                nums = re.findall(r"\d+", val)
                if nums:
                    self.gold = int(nums[0])
            elif key == "INV":
                if val.lower() in ("порожньо", "немає", "none", "-", ""):
                    self.inventory = []
                else:
                    self.inventory = [x.strip() for x in val.split(",") if x.strip()]
            elif key == "OPT1":
                parsed_opts[0] = val
            elif key == "OPT2":
                parsed_opts[1] = val
            elif key == "OPT3":
                parsed_opts[2] = val

        if self.hp <= 0:
            self.game_over = True
            self._append_story("\n\n💀 Здоров'я впало до 0. Пригоду завершено! Натисніть «▶ Нова гра».", "death_msg")

        self._update_stats_ui(parsed_opts)

    def _validate_params(self):
        try:
            temp = float(self.temp_var.get())
            max_tok = int(self.max_tokens_var.get())
            num_ctx = int(self.ctx_var.get())
            if not (0.0 <= temp <= 2.0) or max_tok < 50 or num_ctx < 512:
                raise ValueError
            return temp, max_tok, num_ctx
        except ValueError:
            messagebox.showerror(
                "Некоректні параметри",
                "Перевірте параметри: temperature (0.0–2.0), max_tokens (>= 50), num_ctx (>= 512).",
            )
            return None

    def start_new_game(self):
        if self.is_generating:
            return
        params = self._validate_params()
        if not params:
            return

        setting_name = self.setting_var.get()
        system_prompt = SETTINGS[setting_name] + "\n" + SYSTEM_RULES

        self.messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Почни гру: опиши стартову локацію та запропонуй 3 перші дії."},
        ]
        self.turn_count = 1
        self.game_over = False
        self.hp = 100
        self.gold = 0
        self.inventory = []
        self._clear_story()
        self._update_stats_ui(["...", "...", "..."])
        self._append_story(f"=== {setting_name} ===\n\n", "system_msg")

        self._launch_turn(params)

    def choose_quick_option(self, idx: int):
        text = self.opt_buttons[idx].cget("text")
        if text and text not in ("—", "..."):
            self.action_var.set(text)
            self.send_player_action()

    def send_player_action(self):
        if self.is_generating:
            return
        if not self.messages:
            messagebox.showinfo("Гра не почата", "Спочатку натисніть «▶ Нова гра».")
            return
        if self.game_over:
            messagebox.showinfo("Гру завершено", "Ваш персонаж загинув. Натисніть «▶ Нова гра», щоб почати знову.")
            return

        action = self.action_var.get().strip()
        if not action:
            messagebox.showwarning("Порожня дія", "Введіть дію персонажа або натисніть одну з кнопок вибору.")
            return

        params = self._validate_params()
        if not params:
            return

        self.action_var.set("")
        self.turn_count += 1
        self._append_story(f"\n\n> Гравець (хід {self.turn_count}): {action}\n\n", "player")
        self.messages.append({"role": "user", "content": action})

        # Ковзне вікно контексту: system prompt + останні 12 повідомлень
        if len(self.messages) > 13:
            self.messages = [self.messages[0]] + self.messages[-12:]

        self._launch_turn(params)

    def stop_generation(self):
        if self.is_generating:
            self.stop_requested = True
            self.status_var.set("Зупинка генерації...")

    def _launch_turn(self, params):
        temp, max_tok, num_ctx = params
        self.is_generating = True
        self.stop_requested = False
        self.new_game_btn.config(state=tk.DISABLED)
        self.send_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        for btn in self.opt_buttons:
            btn.config(state=tk.DISABLED)
        self.progress.start(12)
        self.status_var.set("Game Master формує сцену...")

        threading.Thread(
            target=self._run_llm_turn,
            args=(self.url_var.get().strip(), self.model_var.get().strip(), temp, max_tok, num_ctx),
            daemon=True,
        ).start()

    def _run_llm_turn(self, base_url, model, temp, max_tok, num_ctx):
        start_t = time.perf_counter()
        first_t = None
        comp_tokens = None
        full_reply = ""
        printed_len = 0

        try:
            client = OpenAI(base_url=base_url, api_key="local", timeout=90.0)
            stream = client.chat.completions.create(
                model=model,
                messages=self.messages,
                temperature=temp,
                max_tokens=max_tok,
                stream=True,
                stream_options={"include_usage": True},
                reasoning_effort="none",
                extra_body={"options": {"num_ctx": num_ctx}},
            )

            for chunk in stream:
                if self.stop_requested:
                    break
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        if first_t is None:
                            first_t = time.perf_counter()
                            self.root.after(0, lambda: self.status_var.set("Стрімінг сюжету..."))
                        full_reply += delta.content

                        # Не показуємо технічний тег [STATE: ...] у вікні сюжету під час стрімінгу
                        state_pos = full_reply.find("[STATE:")
                        safe_end = state_pos if state_pos != -1 else max(0, len(full_reply) - 8)
                        if safe_end > printed_len:
                            piece = full_reply[printed_len:safe_end]
                            printed_len = safe_end
                            self.root.after(0, lambda p=piece: self._append_story(p))

                if chunk.usage:
                    comp_tokens = chunk.usage.completion_tokens

            state_pos = full_reply.find("[STATE:")
            final_clean_end = state_pos if state_pos != -1 else len(full_reply)
            if final_clean_end > printed_len:
                tail = full_reply[printed_len:final_clean_end].rstrip()
                self.root.after(0, lambda p=tail: self._append_story(p))

            end_t = time.perf_counter()
            if not full_reply.strip() and not self.stop_requested:
                raise RuntimeError("Модель повернула порожню відповідь.")

            self.messages.append({"role": "assistant", "content": full_reply})
            self.root.after(0, lambda r=full_reply: self._parse_and_apply_state(r))

            ttft = (first_t - start_t) if first_t else 0.0
            gen_t = (end_t - first_t) if first_t and end_t > first_t else 0.0
            speed_info = ""
            if comp_tokens and gen_t > 0:
                speed_info = f" | {comp_tokens} токенів ({max(comp_tokens - 1, 1) / gen_t:.1f} tok/s)"
            prefix = "Зупинено" if self.stop_requested else "Хід завершено"
            status_msg = f"{prefix} | TTFT: {ttft:.2f} с | Час: {end_t - start_t:.2f} с{speed_info}"
            self.root.after(0, lambda s=status_msg: self.status_var.set(s))

        except APIConnectionError:
            err = "Сервер Ollama не запущено або недоступний за вказаною адресою."
            self.root.after(0, lambda: self._on_error(err))
        except APITimeoutError:
            err = "Таймаут відповіді моделі. Спробуйте зменшити max_tokens або почати нову гру."
            self.root.after(0, lambda: self._on_error(err))
        except NotFoundError:
            err = f"Модель '{model}' не знайдена. Виконайте: ollama pull {model}"
            self.root.after(0, lambda: self._on_error(err))
        except Exception as exc:
            err = f"Помилка генерації: {exc}"
            self.root.after(0, lambda: self._on_error(err))
        finally:
            self.root.after(0, self._unlock_ui)

    def _on_error(self, msg: str):
        if self.messages and self.messages[-1]["role"] == "user":
            self.messages.pop()
            self.turn_count = max(0, self.turn_count - 1)
        self.status_var.set(f"Помилка: {msg}")
        messagebox.showerror("Помилка локальної моделі", msg)

    def _unlock_ui(self):
        self.is_generating = False
        self.stop_requested = False
        self.progress.stop()
        self.new_game_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        if not self.game_over and self.messages:
            self.send_btn.config(state=tk.NORMAL)
            for btn in self.opt_buttons:
                if btn.cget("text") not in ("—", "..."):
                    btn.config(state=tk.NORMAL)

    def save_log(self):
        content = self.story_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo("Порожній журнал", "Немає тексту для збереження.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile="rpg_adventure_log.txt",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.status_var.set(f"Журнал збережено у {path}")


if __name__ == "__main__":
    root = tk.Tk()
    app = AIRPGQuestApp(root)
    root.mainloop()