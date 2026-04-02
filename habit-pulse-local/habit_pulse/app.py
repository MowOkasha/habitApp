from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from tkinter import font as tkfont
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from .models import Cadence, FocusQuestion, Habit, HabitMode, QuestionCadence, TodoItem, str_to_date, str_to_dt
from .store import HabitStore


class HabitPulseApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Habit Pulse")
        self.root.geometry("1260x860")
        self.root.minsize(1080, 720)

        self.store = HabitStore()
        self.store.load()
        if self.store.sync_for_missed_days():
            self.store.save()

        self.status_var = tk.StringVar(value="Ready.")

        self.habit_section_var = tk.StringVar(value="General")
        self.habit_name_var = tk.StringVar()
        self.habit_cadence_var = tk.StringVar(value=Cadence.DAILY.value)
        self.habit_mode_var = tk.StringVar(value=HabitMode.TARGET.value)
        self.habit_target_var = tk.StringVar(value="30")
        self.habit_check_in_var = tk.BooleanVar(value=False)
        self.habit_interval_var = tk.StringVar(value="2")

        self.section_add_var = tk.StringVar(value="")

        self.question_text_var = tk.StringVar(value="")
        self.question_cadence_var = tk.StringVar(value=QuestionCadence.DAILY.value)
        self.question_times_var = tk.StringVar(value="3")
        self.question_video_var = tk.StringVar(value="")

        self.todo_section_var = tk.StringVar(value="General")
        self.todo_text_var = tk.StringVar(value="")

        self.journal_day_var = tk.StringVar(value=date.today().isoformat())
        self.journal_display_day_var = tk.StringVar(value="")
        self.journal_header_var = tk.StringVar(value="Daily Journal")
        self.journal_page_var = tk.StringVar(value="Page 1 / 1")

        self.dopamine_video_var = tk.StringVar(value=self.store.settings.dopamine_video_path or "")

        self.habit_section_combo: Optional[ttk.Combobox] = None
        self.habit_target_spin: Optional[ttk.Spinbox] = None
        self.habit_interval_spin: Optional[ttk.Spinbox] = None
        self.todo_section_combo: Optional[ttk.Combobox] = None

        self.cards_canvas: Optional[tk.Canvas] = None
        self.cards_frame: Optional[ttk.Frame] = None
        self.cards_window: Optional[int] = None

        self.todo_active_canvas: Optional[tk.Canvas] = None
        self.todo_active_frame: Optional[ttk.Frame] = None
        self.todo_done_canvas: Optional[tk.Canvas] = None
        self.todo_done_frame: Optional[ttk.Frame] = None
        self.todo_active_window: Optional[int] = None
        self.todo_done_window: Optional[int] = None

        self.day_journal_text: Optional[tk.Text] = None

        self.habits_tree: Optional[ttk.Treeview] = None
        self.questions_tree: Optional[ttk.Treeview] = None

        self.todo_font = tkfont.Font(family="Avenir Next", size=11)
        self.todo_done_font = tkfont.Font(family="Avenir Next", size=11, overstrike=1)

        self._configure_styles()
        self._build_layout()
        self._refresh_all_views()

        self.root.after(60_000, self._heartbeat)

    def _configure_styles(self) -> None:
        app_bg = "#f2eedb"
        panel_bg = "#fffdf5"
        panel_alt = "#ede6cf"
        card_bg = "#fffaf0"
        ink = "#161511"
        muted_ink = "#5a564a"
        accent = "#2e8b57"
        accent_hover = "#2a7d4f"
        accent_press = "#216640"
        danger = "#b94a48"
        focus = "#1d4ed8"

        self.root.configure(background=app_bg)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Root.TFrame", background=app_bg)
        style.configure("Panel.TFrame", background=panel_bg, borderwidth=2, relief="solid")
        style.configure("Card.TFrame", background=card_bg, borderwidth=2, relief="solid")

        style.configure("Heading.TLabel", background=app_bg, foreground=ink, font=("Menlo", 30, "bold"))
        style.configure("Subheading.TLabel", background=app_bg, foreground=muted_ink, font=("Avenir Next", 12))
        style.configure("Label.TLabel", background=panel_bg, foreground=ink, font=("Avenir Next", 11))
        style.configure("SectionLabel.TLabel", background=app_bg, foreground=ink, font=("Menlo", 14, "bold"))
        style.configure("CardTitle.TLabel", background=card_bg, foreground=ink, font=("Menlo", 13, "bold"))
        style.configure("CardMeta.TLabel", background=card_bg, foreground=muted_ink, font=("Menlo", 10))
        style.configure("Pill.TLabel", background=panel_alt, foreground=ink, padding=(8, 3), font=("Menlo", 9, "bold"))
        style.configure("Status.TLabel", background=app_bg, foreground=ink, font=("Menlo", 10))

        style.configure("TButton", font=("Menlo", 10, "bold"), padding=(12, 6), borderwidth=2, relief="raised")
        style.configure("Accent.TButton", font=("Menlo", 10, "bold"), padding=(12, 6), borderwidth=2, relief="raised", background=accent, foreground="#ffffff")
        style.configure("Danger.TButton", font=("Menlo", 10, "bold"), padding=(12, 6), borderwidth=2, relief="raised", background=danger, foreground="#ffffff")
        style.map(
            "TButton",
            background=[("pressed", panel_alt), ("active", "#f4f0df")],
            relief=[("pressed", "sunken"), ("!pressed", "raised")],
        )
        style.map(
            "Accent.TButton",
            background=[("pressed", accent_press), ("active", accent_hover)],
            foreground=[("disabled", "#e6e6e6")],
            relief=[("pressed", "sunken"), ("!pressed", "raised")],
        )
        style.map(
            "Danger.TButton",
            background=[("pressed", "#923636"), ("active", "#a84341")],
            foreground=[("disabled", "#e6e6e6")],
        )

        style.configure("TNotebook", background=app_bg, borderwidth=0)
        style.configure("TNotebook.Tab", background=panel_alt, foreground=ink, padding=(12, 8), font=("Menlo", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", panel_bg), ("active", "#e2dac1")])

        style.configure("Treeview", background=panel_bg, fieldbackground=panel_bg, foreground=ink, rowheight=26, borderwidth=1)
        style.configure("Treeview.Heading", background=panel_alt, foreground=ink, font=("Menlo", 10, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", "#d7e6d8")], foreground=[("selected", ink)])

        style.configure("TEntry", fieldbackground="#ffffff", bordercolor="#2b2a25", lightcolor="#2b2a25", darkcolor="#2b2a25", padding=(6, 4))
        style.configure("TCombobox", fieldbackground="#ffffff", bordercolor="#2b2a25", lightcolor="#2b2a25", darkcolor="#2b2a25", padding=(4, 3))
        style.configure("TSpinbox", fieldbackground="#ffffff", bordercolor="#2b2a25", lightcolor="#2b2a25", darkcolor="#2b2a25", padding=(4, 3))
        style.map(
            "TEntry",
            bordercolor=[("focus", focus)],
            lightcolor=[("focus", focus)],
            darkcolor=[("focus", focus)],
            fieldbackground=[("focus", "#f6fbff")],
        )
        style.map(
            "TCombobox",
            bordercolor=[("focus", focus)],
            lightcolor=[("focus", focus)],
            darkcolor=[("focus", focus)],
            fieldbackground=[("focus", "#f6fbff")],
        )
        style.map(
            "TSpinbox",
            bordercolor=[("focus", focus)],
            lightcolor=[("focus", focus)],
            darkcolor=[("focus", focus)],
            fieldbackground=[("focus", "#f6fbff")],
        )

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, style="Root.TFrame", padding=(18, 14, 18, 14))
        container.pack(fill="both", expand=True)

        header = ttk.Frame(container, style="Root.TFrame")
        header.pack(fill="x")

        title_frame = ttk.Frame(header, style="Root.TFrame")
        title_frame.pack(side="left", fill="x", expand=True)

        ttk.Label(title_frame, text="Habit Pulse", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(
            title_frame,
            text="Minimal tracker with journals, focused prompts, and sectioned workflows.",
            style="Subheading.TLabel",
        ).pack(anchor="w")

        header_actions = ttk.Frame(header, style="Root.TFrame")
        header_actions.pack(side="right", anchor="n")

        ttk.Button(
            header_actions,
            text="Dopamine",
            style="Accent.TButton",
            command=self._play_dopamine_video,
        ).pack(side="right")

        notebook = ttk.Notebook(container)
        notebook.pack(fill="both", expand=True, pady=(10, 6))

        tracker_tab = ttk.Frame(notebook, style="Root.TFrame", padding=(8, 8, 8, 8))
        settings_tab = ttk.Frame(notebook, style="Root.TFrame", padding=(8, 8, 8, 8))
        questions_tab = ttk.Frame(notebook, style="Root.TFrame", padding=(8, 8, 8, 8))
        journal_tab = ttk.Frame(notebook, style="Root.TFrame", padding=(8, 8, 8, 8))
        todo_tab = ttk.Frame(notebook, style="Root.TFrame", padding=(8, 8, 8, 8))

        notebook.add(tracker_tab, text="Tracker")
        notebook.add(settings_tab, text="Settings")
        notebook.add(questions_tab, text="Questions")
        notebook.add(journal_tab, text="Journal")
        notebook.add(todo_tab, text="Todo")

        self._build_tracker_tab(tracker_tab)
        self._build_settings_tab(settings_tab)
        self._build_questions_tab(questions_tab)
        self._build_journal_tab(journal_tab)
        self._build_todo_tab(todo_tab)

        ttk.Label(container, textvariable=self.status_var, style="Status.TLabel").pack(fill="x", pady=(2, 0))

    def _build_tracker_tab(self, parent: ttk.Frame) -> None:
        form = ttk.Frame(parent, style="Panel.TFrame", padding=(12, 10, 12, 10))
        form.pack(fill="x", pady=(0, 8))

        ttk.Label(form, text="Section", style="Label.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 6))
        self.habit_section_combo = ttk.Combobox(
            form,
            textvariable=self.habit_section_var,
            values=self.store.list_habit_sections(),
            width=16,
        )
        self.habit_section_combo.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(0, 6))
        self._attach_focus_hint(self.habit_section_combo, "habit section")

        ttk.Label(form, text="Habit", style="Label.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 8), pady=(0, 6))
        habit_name_entry = ttk.Entry(form, textvariable=self.habit_name_var, width=28)
        habit_name_entry.grid(row=0, column=3, sticky="w", padx=(0, 12), pady=(0, 6))
        self._attach_focus_hint(habit_name_entry, "habit name")

        ttk.Label(form, text="Cadence", style="Label.TLabel").grid(row=0, column=4, sticky="w", padx=(0, 8), pady=(0, 6))
        cadence_combo = ttk.Combobox(
            form,
            textvariable=self.habit_cadence_var,
            values=[Cadence.DAILY.value, Cadence.WEEKLY.value, Cadence.MONTHLY.value],
            width=10,
            state="readonly",
        )
        cadence_combo.grid(row=0, column=5, sticky="w", padx=(0, 12), pady=(0, 6))
        self._attach_focus_hint(cadence_combo, "habit cadence")

        ttk.Label(form, text="Type", style="Label.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 8))
        mode_combo = ttk.Combobox(
            form,
            textvariable=self.habit_mode_var,
            values=[HabitMode.TARGET.value, HabitMode.OPEN_ENDED.value],
            width=16,
            state="readonly",
        )
        mode_combo.grid(row=1, column=1, sticky="w", padx=(0, 12))
        mode_combo.bind("<<ComboboxSelected>>", lambda _event: self._toggle_habit_target_state())
        self._attach_focus_hint(mode_combo, "habit type")

        ttk.Label(form, text="Target", style="Label.TLabel").grid(row=1, column=2, sticky="w", padx=(0, 8))
        self.habit_target_spin = ttk.Spinbox(
            form,
            from_=1,
            to=365,
            width=8,
            textvariable=self.habit_target_var,
        )
        self.habit_target_spin.grid(row=1, column=3, sticky="w", padx=(0, 12))
        self._attach_focus_hint(self.habit_target_spin, "habit target")

        ttk.Checkbutton(
            form,
            text="Timed check-ins",
            variable=self.habit_check_in_var,
            command=self._toggle_habit_interval_state,
        ).grid(row=1, column=4, sticky="w", padx=(0, 8))

        ttk.Label(form, text="Every (hours)", style="Label.TLabel").grid(row=1, column=5, sticky="w", padx=(0, 8))
        self.habit_interval_spin = ttk.Spinbox(
            form,
            from_=1,
            to=24,
            width=6,
            textvariable=self.habit_interval_var,
        )
        self.habit_interval_spin.grid(row=1, column=6, sticky="w", padx=(0, 12))
        self._attach_focus_hint(self.habit_interval_spin, "check-in interval")

        ttk.Button(
            form,
            text="Add Habit",
            style="Accent.TButton",
            command=self._add_habit,
        ).grid(row=1, column=7, sticky="e")

        form.columnconfigure(7, weight=1)

        legend = ttk.Frame(parent, style="Root.TFrame")
        legend.pack(fill="x", pady=(0, 8))
        self._legend_chip(legend, "Done", "#5fbf72").pack(side="left", padx=(0, 8))
        self._legend_chip(legend, "Missed", "#e06d6d").pack(side="left", padx=(0, 8))
        self._legend_chip(legend, "Pending", "#d4dccf").pack(side="left", padx=(0, 8))

        cards_outer = ttk.Frame(parent, style="Root.TFrame")
        cards_outer.pack(fill="both", expand=True)

        self.cards_canvas = tk.Canvas(cards_outer, background="#f0f3ec", highlightthickness=0, bd=0)
        cards_scroll = ttk.Scrollbar(cards_outer, orient="vertical", command=self.cards_canvas.yview)
        self.cards_canvas.configure(yscrollcommand=cards_scroll.set)

        self.cards_canvas.pack(side="left", fill="both", expand=True)
        cards_scroll.pack(side="right", fill="y")

        self.cards_frame = ttk.Frame(self.cards_canvas, style="Root.TFrame")
        self.cards_window = self.cards_canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")

        self.cards_frame.bind("<Configure>", self._update_cards_scroll)
        self.cards_canvas.bind("<Configure>", self._resize_cards_window)
        self.cards_canvas.bind_all("<MouseWheel>", self._on_mouse_wheel)

        self._toggle_habit_target_state()
        self._toggle_habit_interval_state()

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        section_panel = ttk.Frame(parent, style="Panel.TFrame", padding=(12, 10, 12, 10))
        section_panel.pack(fill="x", pady=(0, 8))

        ttk.Label(section_panel, text="Create habit section", style="Label.TLabel").pack(side="left", padx=(0, 8))
        section_entry = ttk.Entry(section_panel, textvariable=self.section_add_var, width=24)
        section_entry.pack(side="left", padx=(0, 8))
        self._attach_focus_hint(section_entry, "new section")
        ttk.Button(section_panel, text="Add Section", command=self._add_section).pack(side="left")

        tree_panel = ttk.Frame(parent, style="Panel.TFrame", padding=(8, 8, 8, 8))
        tree_panel.pack(fill="both", expand=True)

        columns = ("name", "section", "cadence", "mode", "target", "check_in")
        self.habits_tree = ttk.Treeview(tree_panel, columns=columns, show="headings", height=14)
        self.habits_tree.heading("name", text="Habit")
        self.habits_tree.heading("section", text="Section")
        self.habits_tree.heading("cadence", text="Cadence")
        self.habits_tree.heading("mode", text="Type")
        self.habits_tree.heading("target", text="Target")
        self.habits_tree.heading("check_in", text="Check-ins")

        self.habits_tree.column("name", width=230)
        self.habits_tree.column("section", width=130)
        self.habits_tree.column("cadence", width=90)
        self.habits_tree.column("mode", width=110)
        self.habits_tree.column("target", width=90)
        self.habits_tree.column("check_in", width=120)

        habit_scroll = ttk.Scrollbar(tree_panel, orient="vertical", command=self.habits_tree.yview)
        self.habits_tree.configure(yscrollcommand=habit_scroll.set)

        self.habits_tree.pack(side="left", fill="both", expand=True)
        habit_scroll.pack(side="right", fill="y")

        actions = ttk.Frame(parent, style="Root.TFrame")
        actions.pack(fill="x", pady=(8, 0))

        ttk.Button(actions, text="Edit Habit", style="Accent.TButton", command=self._open_edit_selected_habit).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Delete Habit", style="Danger.TButton", command=self._delete_selected_habit).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Refresh", command=self._refresh_all_views).pack(side="left")

        self.habits_tree.bind("<Double-1>", lambda _event: self._open_edit_selected_habit())

    def _build_questions_tab(self, parent: ttk.Frame) -> None:
        dopamine_panel = ttk.Frame(parent, style="Panel.TFrame", padding=(12, 10, 12, 10))
        dopamine_panel.pack(fill="x", pady=(0, 8))

        ttk.Label(dopamine_panel, text="Default dopamine video", style="Label.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        dopamine_entry = ttk.Entry(dopamine_panel, textvariable=self.dopamine_video_var, width=72)
        dopamine_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self._attach_focus_hint(dopamine_entry, "dopamine video path")
        ttk.Button(dopamine_panel, text="Browse", command=self._browse_dopamine_video).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(dopamine_panel, text="Save", command=self._save_dopamine_video).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(dopamine_panel, text="Play", command=self._play_dopamine_video).grid(row=0, column=4)
        dopamine_panel.columnconfigure(1, weight=1)

        form = ttk.Frame(parent, style="Panel.TFrame", padding=(12, 10, 12, 10))
        form.pack(fill="x", pady=(0, 8))

        ttk.Label(form, text="Question", style="Label.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 6))
        question_entry = ttk.Entry(form, textvariable=self.question_text_var, width=56)
        question_entry.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(0, 6))
        self._attach_focus_hint(question_entry, "question text")

        ttk.Label(form, text="Cadence", style="Label.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 8), pady=(0, 6))
        question_cadence_combo = ttk.Combobox(
            form,
            textvariable=self.question_cadence_var,
            values=[QuestionCadence.DAILY.value, QuestionCadence.WEEKLY.value],
            width=10,
            state="readonly",
        )
        question_cadence_combo.grid(row=0, column=3, sticky="w", padx=(0, 12), pady=(0, 6))
        self._attach_focus_hint(question_cadence_combo, "question cadence")

        ttk.Label(form, text="Times", style="Label.TLabel").grid(row=0, column=4, sticky="w", padx=(0, 8), pady=(0, 6))
        question_times_spin = ttk.Spinbox(form, from_=1, to=60, width=8, textvariable=self.question_times_var)
        question_times_spin.grid(row=0, column=5, sticky="w", padx=(0, 12), pady=(0, 6))
        self._attach_focus_hint(question_times_spin, "question frequency")

        ttk.Label(form, text="Video", style="Label.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 8))
        question_video_entry = ttk.Entry(form, textvariable=self.question_video_var, width=56)
        question_video_entry.grid(row=1, column=1, sticky="w", padx=(0, 12))
        self._attach_focus_hint(question_video_entry, "question video path")
        ttk.Button(form, text="Browse", command=self._browse_question_video).grid(row=1, column=2, sticky="w", padx=(0, 8))
        ttk.Button(form, text="Add Question", style="Accent.TButton", command=self._add_question).grid(row=1, column=3, sticky="w")

        tree_panel = ttk.Frame(parent, style="Panel.TFrame", padding=(8, 8, 8, 8))
        tree_panel.pack(fill="both", expand=True)

        columns = ("text", "cadence", "times", "enabled", "next", "video")
        self.questions_tree = ttk.Treeview(tree_panel, columns=columns, show="headings", height=12)
        self.questions_tree.heading("text", text="Question")
        self.questions_tree.heading("cadence", text="Cadence")
        self.questions_tree.heading("times", text="Times")
        self.questions_tree.heading("enabled", text="Enabled")
        self.questions_tree.heading("next", text="Next")
        self.questions_tree.heading("video", text="Video")

        self.questions_tree.column("text", width=300)
        self.questions_tree.column("cadence", width=90)
        self.questions_tree.column("times", width=70)
        self.questions_tree.column("enabled", width=75)
        self.questions_tree.column("next", width=160)
        self.questions_tree.column("video", width=320)

        question_scroll = ttk.Scrollbar(tree_panel, orient="vertical", command=self.questions_tree.yview)
        self.questions_tree.configure(yscrollcommand=question_scroll.set)

        self.questions_tree.pack(side="left", fill="both", expand=True)
        question_scroll.pack(side="right", fill="y")

        actions = ttk.Frame(parent, style="Root.TFrame")
        actions.pack(fill="x", pady=(8, 0))

        ttk.Button(actions, text="Edit Question", style="Accent.TButton", command=self._open_edit_selected_question).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Toggle Enabled", command=self._toggle_selected_question).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Delete Question", style="Danger.TButton", command=self._delete_selected_question).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Refresh", command=self._refresh_all_views).pack(side="left")

        self.questions_tree.bind("<Double-1>", lambda _event: self._open_edit_selected_question())

    def _build_journal_tab(self, parent: ttk.Frame) -> None:
        nav = ttk.Frame(parent, style="Panel.TFrame", padding=(12, 10, 12, 10))
        nav.pack(fill="x", pady=(0, 8))

        ttk.Button(nav, text="< Prev Page", command=lambda: self._flip_day_journal_page(-1)).pack(side="left", padx=(0, 8))
        ttk.Button(nav, text="Next Page >", command=lambda: self._flip_day_journal_page(1)).pack(side="left", padx=(0, 12))

        ttk.Label(nav, text="Day", style="Label.TLabel").pack(side="left", padx=(0, 8))
        day_entry = ttk.Entry(nav, textvariable=self.journal_day_var, width=14)
        day_entry.pack(side="left", padx=(0, 8))
        self._attach_focus_hint(day_entry, "journal day")

        ttk.Button(nav, text="Load", command=self._load_day_journal_from_input).pack(side="left", padx=(0, 8))
        ttk.Button(nav, text="Today", command=self._jump_to_today_journal).pack(side="left", padx=(0, 12))
        ttk.Button(nav, text="Save Page", style="Accent.TButton", command=self._save_day_journal_page).pack(side="left")

        ttk.Label(nav, textvariable=self.journal_page_var, style="CardMeta.TLabel").pack(side="right")
        ttk.Label(nav, textvariable=self.journal_display_day_var, style="SectionLabel.TLabel").pack(side="right", padx=(0, 12))

        shell = ttk.Frame(parent, style="Panel.TFrame", padding=(18, 14, 18, 14))
        shell.pack(fill="both", expand=True)

        book = tk.Frame(shell, bg="#efe2c3", bd=0, padx=26, pady=20)
        book.pack(fill="both", expand=True)

        left_page = tk.Frame(book, bg="#fbf3de", bd=1, relief="solid")
        left_page.pack(fill="both", expand=True)

        header = tk.Label(
            left_page,
            textvariable=self.journal_header_var,
            bg="#fbf3de",
            fg="#4a3f2a",
            font=("Menlo", 14, "bold"),
            anchor="w",
            padx=12,
            pady=8,
        )
        header.pack(fill="x")

        self.day_journal_text = tk.Text(
            left_page,
            wrap="word",
            bg="#fff9ec",
            fg="#3a2f22",
            insertbackground="#2c2419",
            font=("Georgia", 13),
            padx=16,
            pady=12,
            undo=True,
        )
        self.day_journal_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._style_text_focus(self.day_journal_text)
        self._attach_focus_hint(self.day_journal_text, "daily journal page")

    def _build_todo_tab(self, parent: ttk.Frame) -> None:
        form = ttk.Frame(parent, style="Panel.TFrame", padding=(12, 10, 12, 10))
        form.pack(fill="x", pady=(0, 8))

        ttk.Label(form, text="Section", style="Label.TLabel").pack(side="left", padx=(0, 8))
        self.todo_section_combo = ttk.Combobox(form, textvariable=self.todo_section_var, values=self.store.list_todo_sections(), width=18)
        self.todo_section_combo.pack(side="left", padx=(0, 12))
        self._attach_focus_hint(self.todo_section_combo, "todo section")

        ttk.Label(form, text="Todo", style="Label.TLabel").pack(side="left", padx=(0, 8))
        todo_entry = ttk.Entry(form, textvariable=self.todo_text_var, width=52)
        todo_entry.pack(side="left", padx=(0, 12), fill="x", expand=True)
        self._attach_focus_hint(todo_entry, "todo input")

        ttk.Button(form, text="Add Todo", style="Accent.TButton", command=self._add_todo).pack(side="left")

        panels = ttk.Frame(parent, style="Root.TFrame")
        panels.pack(fill="both", expand=True)
        panels.columnconfigure(0, weight=1)
        panels.columnconfigure(1, weight=1)
        panels.rowconfigure(0, weight=1)

        active_panel = ttk.Frame(panels, style="Panel.TFrame", padding=(10, 10, 10, 10))
        active_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ttk.Label(active_panel, text="Checklist", style="SectionLabel.TLabel").pack(anchor="w", pady=(0, 6))

        self.todo_active_canvas = tk.Canvas(active_panel, background="#f8faf5", highlightthickness=0, bd=0)
        active_scroll = ttk.Scrollbar(active_panel, orient="vertical", command=self.todo_active_canvas.yview)
        self.todo_active_canvas.configure(yscrollcommand=active_scroll.set)
        self.todo_active_canvas.pack(side="left", fill="both", expand=True)
        active_scroll.pack(side="right", fill="y")

        self.todo_active_frame = ttk.Frame(self.todo_active_canvas, style="Panel.TFrame")
        self.todo_active_window = self.todo_active_canvas.create_window((0, 0), window=self.todo_active_frame, anchor="nw")
        self.todo_active_frame.bind("<Configure>", self._update_todo_active_scroll)
        self.todo_active_canvas.bind("<Configure>", self._resize_todo_active_window)

        done_panel = ttk.Frame(panels, style="Panel.TFrame", padding=(10, 10, 10, 10))
        done_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ttk.Label(done_panel, text="Done (24h archive)", style="SectionLabel.TLabel").pack(anchor="w", pady=(0, 6))

        self.todo_done_canvas = tk.Canvas(done_panel, background="#f8faf5", highlightthickness=0, bd=0)
        done_scroll = ttk.Scrollbar(done_panel, orient="vertical", command=self.todo_done_canvas.yview)
        self.todo_done_canvas.configure(yscrollcommand=done_scroll.set)
        self.todo_done_canvas.pack(side="left", fill="both", expand=True)
        done_scroll.pack(side="right", fill="y")

        self.todo_done_frame = ttk.Frame(self.todo_done_canvas, style="Panel.TFrame")
        self.todo_done_window = self.todo_done_canvas.create_window((0, 0), window=self.todo_done_frame, anchor="nw")
        self.todo_done_frame.bind("<Configure>", self._update_todo_done_scroll)
        self.todo_done_canvas.bind("<Configure>", self._resize_todo_done_window)

    def _legend_chip(self, parent: ttk.Frame, text: str, color: str) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            bg=color,
            fg="#16231b",
            font=("Avenir Next", 10, "bold"),
            padx=10,
            pady=2,
        )

    def _attach_focus_hint(self, widget: tk.Widget, label: str) -> None:
        widget.bind(
            "<FocusIn>",
            lambda _event, text=label: self._set_status(f"Typing in {text}..."),
            add="+",
        )

    def _style_text_focus(self, widget: tk.Text) -> None:
        widget.configure(highlightthickness=2, highlightbackground="#2b2a25", highlightcolor="#1d4ed8")
        widget.bind(
            "<FocusIn>",
            lambda _event: widget.configure(highlightbackground="#1d4ed8"),
            add="+",
        )
        widget.bind(
            "<FocusOut>",
            lambda _event: widget.configure(highlightbackground="#2b2a25"),
            add="+",
        )

    def _bind_single_click(self, widget: tk.Widget, callback) -> None:
        def _click(_event: tk.Event) -> None:
            callback()

        widget.bind("<Button-1>", _click, add="+")

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        target: Optional[tk.Canvas] = None
        widget = event.widget
        while widget is not None:
            if widget in {self.cards_canvas, self.todo_active_canvas, self.todo_done_canvas}:
                target = widget  # type: ignore[assignment]
                break
            widget = widget.master
        if target is None:
            target = self.cards_canvas
        if target is None:
            return
        target.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _update_cards_scroll(self, _event: tk.Event) -> None:
        if self.cards_canvas is None:
            return
        self.cards_canvas.configure(scrollregion=self.cards_canvas.bbox("all"))

    def _resize_cards_window(self, event: tk.Event) -> None:
        if self.cards_canvas is None or self.cards_window is None:
            return
        self.cards_canvas.itemconfigure(self.cards_window, width=event.width)

    def _update_todo_active_scroll(self, _event: tk.Event) -> None:
        if self.todo_active_canvas is None:
            return
        self.todo_active_canvas.configure(scrollregion=self.todo_active_canvas.bbox("all"))

    def _resize_todo_active_window(self, event: tk.Event) -> None:
        if self.todo_active_canvas is None or self.todo_active_window is None:
            return
        self.todo_active_canvas.itemconfigure(self.todo_active_window, width=event.width)

    def _update_todo_done_scroll(self, _event: tk.Event) -> None:
        if self.todo_done_canvas is None:
            return
        self.todo_done_canvas.configure(scrollregion=self.todo_done_canvas.bbox("all"))

    def _resize_todo_done_window(self, event: tk.Event) -> None:
        if self.todo_done_canvas is None or self.todo_done_window is None:
            return
        self.todo_done_canvas.itemconfigure(self.todo_done_window, width=event.width)

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)

    def _toggle_habit_target_state(self) -> None:
        if self.habit_target_spin is None:
            return
        is_target = self.habit_mode_var.get() == HabitMode.TARGET.value
        self.habit_target_spin.configure(state="normal" if is_target else "disabled")

    def _toggle_habit_interval_state(self) -> None:
        if self.habit_interval_spin is None:
            return
        enabled = self.habit_check_in_var.get()
        self.habit_interval_spin.configure(state="normal" if enabled else "disabled")

    def _format_stamp(self, value: Optional[str]) -> str:
        if not value:
            return "-"
        try:
            return str_to_dt(value).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return value

    def _format_due_text(self, habit: Habit) -> str:
        if not habit.next_check_in_at:
            return "not scheduled"
        try:
            due = str_to_dt(habit.next_check_in_at)
        except ValueError:
            return "not scheduled"

        delta = due - datetime.now()
        seconds = int(delta.total_seconds())
        if seconds <= 0:
            return "due now"

        hours, rem = divmod(seconds, 3600)
        minutes = rem // 60
        if hours > 0:
            return f"in {hours}h {minutes}m"
        return f"in {minutes}m"

    def _refresh_section_choices(self) -> None:
        habit_sections = self.store.list_habit_sections()
        todo_sections = self.store.list_todo_sections()
        if self.habit_section_combo is not None:
            self.habit_section_combo.configure(values=habit_sections)
        if self.todo_section_combo is not None:
            self.todo_section_combo.configure(values=todo_sections)
        if not self.habit_section_var.get().strip():
            self.habit_section_var.set(habit_sections[0])
        if not self.todo_section_var.get().strip():
            self.todo_section_var.set(todo_sections[0])

    def _refresh_habits_tree(self) -> None:
        if self.habits_tree is None:
            return
        for row in self.habits_tree.get_children():
            self.habits_tree.delete(row)

        habits = sorted(self.store.habits, key=lambda item: (item.section.lower(), item.name.lower()))
        for habit in habits:
            target_label = str(habit.target_periods) if habit.mode == HabitMode.TARGET.value else "open"
            check_in_label = f"{habit.check_in_interval_hours}h" if habit.check_in_enabled else "off"
            self.habits_tree.insert(
                "",
                "end",
                iid=habit.id,
                values=(
                    habit.name,
                    habit.section,
                    habit.cadence,
                    habit.mode,
                    target_label,
                    check_in_label,
                ),
            )

    def _refresh_questions_tree(self) -> None:
        if self.questions_tree is None:
            return
        for row in self.questions_tree.get_children():
            self.questions_tree.delete(row)

        questions = sorted(self.store.questions, key=lambda item: item.created_at, reverse=True)
        for question in questions:
            self.questions_tree.insert(
                "",
                "end",
                iid=question.id,
                values=(
                    question.text,
                    question.cadence,
                    question.times_per_period,
                    "yes" if question.enabled else "no",
                    self._format_stamp(question.next_prompt_at),
                    question.video_path or "",
                ),
            )

    def _normalize_day_value(self, day_text: str) -> Optional[str]:
        normalized = day_text.strip()
        if not normalized:
            return None
        try:
            return str_to_date(normalized).isoformat()
        except ValueError:
            return None

    def _journal_days(self) -> list[str]:
        days = set(self.store.list_day_journal_days())
        days.add(date.today().isoformat())
        current = self._normalize_day_value(self.journal_day_var.get())
        if current:
            days.add(current)
        return sorted(days)

    def _refresh_day_journal_view(self) -> None:
        if self.day_journal_text is None:
            return

        normalized = self._normalize_day_value(self.journal_day_var.get())
        if normalized is None:
            normalized = date.today().isoformat()
            self.journal_day_var.set(normalized)

        page = self.store.get_day_journal_page(normalized)
        content = page.note if page else ""

        day_value = str_to_date(normalized)
        self.journal_display_day_var.set(day_value.strftime("%a %d %b %Y"))
        self.journal_header_var.set(day_value.strftime("Daily Journal - %A, %b %d, %Y"))

        self.day_journal_text.delete("1.0", "end")
        self.day_journal_text.insert("1.0", content)

        days = self._journal_days()
        page_index = days.index(normalized) + 1 if normalized in days else 1
        self.journal_page_var.set(f"Page {page_index} / {max(1, len(days))}")

    def _load_day_journal_from_input(self) -> None:
        normalized = self._normalize_day_value(self.journal_day_var.get())
        if normalized is None:
            messagebox.showerror("Invalid day", "Use date format YYYY-MM-DD.")
            return
        self.journal_day_var.set(normalized)
        self._refresh_day_journal_view()

    def _save_day_journal_page(self) -> None:
        if self.day_journal_text is None:
            return
        normalized = self._normalize_day_value(self.journal_day_var.get())
        if normalized is None:
            messagebox.showerror("Invalid day", "Use date format YYYY-MM-DD.")
            return
        note = self.day_journal_text.get("1.0", "end").strip()
        self.store.save_day_journal_page(normalized, note)
        self.store.save()
        self._refresh_day_journal_view()
        self._set_status(f"Saved daily journal page for {normalized}.")

    def _jump_to_today_journal(self) -> None:
        self.journal_day_var.set(date.today().isoformat())
        self._refresh_day_journal_view()

    def _flip_day_journal_page(self, offset: int) -> None:
        days = self._journal_days()
        if not days:
            self.journal_day_var.set(date.today().isoformat())
            self._refresh_day_journal_view()
            return

        current = self._normalize_day_value(self.journal_day_var.get()) or days[-1]
        if current not in days:
            days.append(current)
            days.sort()

        index = days.index(current)
        next_index = max(0, min(len(days) - 1, index + offset))
        self.journal_day_var.set(days[next_index])
        self._refresh_day_journal_view()

    def _render_todo_row(self, parent: ttk.Frame, todo: TodoItem, *, archived_panel: bool) -> None:
        row = ttk.Frame(parent, style="Panel.TFrame", padding=(6, 4, 6, 4))
        row.pack(fill="x", pady=2)

        done_value = tk.BooleanVar(value=todo.is_completed())
        ttk.Checkbutton(
            row,
            variable=done_value,
            command=lambda selected=todo.id: self._toggle_todo(selected),
        ).pack(side="left", padx=(0, 6))

        label = tk.Label(
            row,
            text=todo.text,
            bg="#f8faf5",
            fg="#274030" if not todo.is_completed() else "#6c7d70",
            font=self.todo_done_font if todo.is_completed() else self.todo_font,
            anchor="w",
            justify="left",
            wraplength=420,
        )
        label.pack(side="left", fill="x", expand=True)

        if todo.is_completed() and not archived_panel:
            remaining_hours = todo.hours_until_archive(datetime.now())
            hours_value = int(remaining_hours)
            minutes_value = int((remaining_hours - hours_value) * 60)
            ttk.Label(
                row,
                text=f"Moves to done in {hours_value}h {minutes_value:02d}m",
                style="CardMeta.TLabel",
            ).pack(side="left", padx=(8, 8))

        if todo.is_completed():
            ttk.Button(row, text="Undo", style="Accent.TButton", command=lambda selected=todo.id: self._undo_todo(selected)).pack(side="left", padx=(0, 6))

        ttk.Button(row, text="Delete", style="Danger.TButton", command=lambda selected=todo.id: self._delete_todo(selected)).pack(side="left")

    def _refresh_todo_views(self) -> None:
        if self.todo_active_frame is None or self.todo_done_frame is None:
            return

        if self.store.sync_todo_rollover():
            self.store.save()

        for child in self.todo_active_frame.winfo_children():
            child.destroy()
        for child in self.todo_done_frame.winfo_children():
            child.destroy()

        active_items = sorted(
            self.store.active_todos(),
            key=lambda item: (item.section.lower(), item.is_completed(), item.created_at),
        )
        done_items = sorted(
            self.store.done_todos(),
            key=lambda item: (item.section.lower(), item.completed_at or item.created_at),
            reverse=True,
        )

        if not active_items:
            ttk.Label(self.todo_active_frame, text="No active todos yet.", style="CardMeta.TLabel").pack(anchor="w", pady=8)
        else:
            grouped_active: dict[str, list[TodoItem]] = defaultdict(list)
            for todo in active_items:
                grouped_active[todo.section.strip() or "General"].append(todo)

            for section_name in sorted(grouped_active.keys()):
                section_frame = ttk.Frame(self.todo_active_frame, style="Panel.TFrame", padding=(2, 2, 2, 6))
                section_frame.pack(fill="x", pady=(0, 6))
                ttk.Label(section_frame, text=section_name, style="SectionLabel.TLabel").pack(anchor="w", pady=(0, 2))
                for todo in grouped_active[section_name]:
                    self._render_todo_row(section_frame, todo, archived_panel=False)

        if not done_items:
            ttk.Label(self.todo_done_frame, text="Nothing in done archive yet.", style="CardMeta.TLabel").pack(anchor="w", pady=8)
        else:
            grouped_done: dict[str, list[TodoItem]] = defaultdict(list)
            for todo in done_items:
                grouped_done[todo.section.strip() or "General"].append(todo)

            for section_name in sorted(grouped_done.keys()):
                section_frame = ttk.Frame(self.todo_done_frame, style="Panel.TFrame", padding=(2, 2, 2, 6))
                section_frame.pack(fill="x", pady=(0, 6))
                ttk.Label(section_frame, text=section_name, style="SectionLabel.TLabel").pack(anchor="w", pady=(0, 2))
                for todo in grouped_done[section_name]:
                    self._render_todo_row(section_frame, todo, archived_panel=True)

    def _add_todo(self) -> None:
        section = self.todo_section_var.get().strip() or "General"
        text = self.todo_text_var.get().strip()
        if not text:
            messagebox.showerror("Invalid todo", "Todo text cannot be empty.")
            return

        todo = self.store.add_todo(section=section, text=text)
        self.store.save()
        self.todo_text_var.set("")
        self._refresh_all_views()
        self._set_status(f"Added todo in section '{todo.section}'.")

    def _toggle_todo(self, todo_id: str) -> None:
        todo = self.store.toggle_todo_done(todo_id)
        if todo is None:
            return
        self.store.save()
        self._refresh_todo_views()
        if todo.is_completed():
            self._set_status("Todo checked. It will move to done after 24 hours.")
        else:
            self._set_status("Todo unchecked and restored.")

    def _undo_todo(self, todo_id: str) -> None:
        todo = self.store.undo_todo_done(todo_id)
        if todo is None:
            return
        self.store.save()
        self._refresh_todo_views()
        self._set_status("Todo moved back to active list.")

    def _delete_todo(self, todo_id: str) -> None:
        if not self.store.delete_todo(todo_id):
            return
        self.store.save()
        self._refresh_todo_views()
        self._set_status("Todo deleted.")

    def _make_clickable(self, widget: tk.Widget, callback) -> None:
        self._bind_single_click(widget, callback)

    def _render_boxes_compact(self, parent: tk.Widget, habit: Habit) -> None:
        frame = tk.Frame(parent, background="#fcfdf9")
        frame.pack(anchor="w", pady=(6, 2))

        colors = {
            "done": "#5fbf72",
            "missed": "#e06d6d",
            "pending": "#d4dccf",
        }

        boxes = habit.progress_boxes(max_boxes=12)
        for idx, box in enumerate(boxes):
            status = box.get("status", "pending")
            tk.Label(
                frame,
                text=box.get("label", ""),
                width=3,
                bg=colors.get(status, colors["pending"]),
                fg="#16231b",
                font=("Avenir Next", 9, "bold"),
                padx=1,
                pady=2,
            ).grid(row=0, column=idx, padx=2, pady=1)

    def _render_tracker_cards(self) -> None:
        if self.cards_frame is None:
            return

        for child in self.cards_frame.winfo_children():
            child.destroy()

        if not self.store.habits:
            empty = ttk.Frame(self.cards_frame, style="Card.TFrame", padding=(16, 12, 16, 12))
            empty.pack(fill="x", pady=8)
            ttk.Label(
                empty,
                text="No habits yet. Add one from the form above.",
                style="CardMeta.TLabel",
            ).pack(anchor="w")
            return

        grouped: dict[str, list[Habit]] = defaultdict(list)
        for habit in self.store.habits:
            grouped[habit.section.strip() or "General"].append(habit)

        for section_name in sorted(grouped.keys()):
            section_frame = ttk.Frame(self.cards_frame, style="Root.TFrame")
            section_frame.pack(fill="x", pady=(2, 10))

            ttk.Label(section_frame, text=section_name, style="SectionLabel.TLabel").pack(anchor="w", pady=(0, 4))

            grid = ttk.Frame(section_frame, style="Root.TFrame")
            grid.pack(fill="x")

            habits = sorted(grouped[section_name], key=lambda item: item.name.lower())
            width_value = self.cards_canvas.winfo_width() if self.cards_canvas is not None else self.root.winfo_width()
            if width_value >= 1320:
                columns = 3
            elif width_value >= 920:
                columns = 2
            else:
                columns = 1
            for idx, habit in enumerate(habits):
                row_index = idx // columns
                col_index = idx % columns

                card = ttk.Frame(grid, style="Card.TFrame", padding=(12, 10, 12, 10))
                card.grid(row=row_index, column=col_index, sticky="nsew", padx=(0, 10), pady=(0, 10))
                grid.columnconfigure(col_index, weight=1)

                header = ttk.Frame(card, style="Card.TFrame")
                header.pack(fill="x")
                header.columnconfigure(0, weight=1)

                ttk.Label(header, text=habit.name, style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
                ttk.Label(header, text=f"{habit.cadence} | {habit.mode}", style="Pill.TLabel").grid(row=0, column=1, sticky="e")

                current, target = habit.current_progress()
                if habit.mode == HabitMode.TARGET.value:
                    progress = f"{current}/{target} {habit.unit_label()}s"
                else:
                    progress = f"{current} {habit.unit_label()}s completed"

                ttk.Label(card, text=f"Progress: {progress}", style="CardMeta.TLabel").pack(anchor="w", pady=(6, 0))

                if habit.check_in_enabled:
                    ttk.Label(card, text=f"Next check-in: {self._format_due_text(habit)}", style="CardMeta.TLabel").pack(anchor="w", pady=(2, 0))

                self._render_boxes_compact(card, habit)

                actions = ttk.Frame(card, style="Card.TFrame")
                actions.pack(fill="x", pady=(8, 0))

                ttk.Button(
                    actions,
                    text="Mark Done",
                    style="Accent.TButton",
                    command=lambda selected=habit.id: self._mark_period_done(selected),
                ).pack(side="left", padx=(0, 8))
                ttk.Button(
                    actions,
                    text="Details",
                    command=lambda selected=habit.id: self._open_habit_details(selected),
                ).pack(side="left")

                self._make_clickable(card, lambda selected=habit.id: self._open_habit_details(selected))

    def _refresh_all_views(self) -> None:
        if self.store.sync_for_missed_days():
            self.store.save()
        self._refresh_section_choices()
        self._render_tracker_cards()
        self._refresh_habits_tree()
        self._refresh_questions_tree()
        self._refresh_day_journal_view()
        self._refresh_todo_views()

    def _validate_habit_form(
        self,
        *,
        name: str,
        mode: str,
        target_text: str,
        check_in_enabled: bool,
        interval_text: str,
    ) -> tuple[bool, int, int]:
        if not name.strip():
            messagebox.showerror("Invalid habit", "Habit name is required.")
            return False, 1, 1

        target_periods = 1
        if mode == HabitMode.TARGET.value:
            try:
                target_periods = int(target_text)
                if target_periods < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid target", "Target periods must be 1 or higher.")
                return False, 1, 1

        interval_hours = 2
        if check_in_enabled:
            try:
                interval_hours = int(interval_text)
                if interval_hours < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid interval", "Check-in interval must be 1 hour or higher.")
                return False, target_periods, 1

        return True, target_periods, interval_hours

    def _add_habit(self) -> None:
        section = self.habit_section_var.get().strip() or "General"
        name = self.habit_name_var.get().strip()
        cadence = self.habit_cadence_var.get().strip().lower() or Cadence.DAILY.value
        mode = self.habit_mode_var.get().strip().lower() or HabitMode.TARGET.value

        valid, target_periods, interval_hours = self._validate_habit_form(
            name=name,
            mode=mode,
            target_text=self.habit_target_var.get(),
            check_in_enabled=self.habit_check_in_var.get(),
            interval_text=self.habit_interval_var.get(),
        )
        if not valid:
            return

        habit = self.store.add_habit(
            name=name,
            section=section,
            cadence=cadence,
            mode=mode,
            target_periods=target_periods,
            check_in_enabled=self.habit_check_in_var.get(),
            check_in_interval_hours=interval_hours,
        )
        self.store.save()

        self.habit_name_var.set("")
        self.habit_target_var.set("30")
        self.habit_check_in_var.set(False)
        self.habit_interval_var.set("2")
        self._toggle_habit_target_state()
        self._toggle_habit_interval_state()

        self._refresh_all_views()
        self._set_status(f"Added habit '{habit.name}' under section '{habit.section}'.")

    def _add_section(self) -> None:
        section = self.section_add_var.get().strip()
        if not section:
            messagebox.showerror("Invalid section", "Section name cannot be empty.")
            return

        normalized = self.store.add_habit_section(section)
        self.store.save()
        self.section_add_var.set("")
        self.habit_section_var.set(normalized)
        self._refresh_all_views()
        self._set_status(f"Added habit section '{normalized}'.")

    def _get_selected_habit(self) -> Optional[Habit]:
        if self.habits_tree is None:
            return None
        selected = self.habits_tree.selection()
        if not selected:
            return None
        return self.store.get_habit(selected[0])

    def _open_edit_selected_habit(self) -> None:
        habit = self._get_selected_habit()
        if habit is None:
            messagebox.showinfo("No habit selected", "Select a habit from the table first.")
            return
        self._open_edit_habit_dialog(habit)

    def _open_edit_habit_dialog(self, habit: Habit) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Habit - {habit.name}")
        dialog.geometry("560x310")

        section_var = tk.StringVar(value=habit.section)
        name_var = tk.StringVar(value=habit.name)
        cadence_var = tk.StringVar(value=habit.cadence)
        mode_var = tk.StringVar(value=habit.mode)
        target_var = tk.StringVar(value=str(habit.target_periods))
        check_var = tk.BooleanVar(value=habit.check_in_enabled)
        interval_var = tk.StringVar(value=str(habit.check_in_interval_hours))

        frame = ttk.Frame(dialog, style="Panel.TFrame", padding=(14, 12, 14, 12))
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Section", style="Label.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        section_combo = ttk.Combobox(frame, textvariable=section_var, values=self.store.list_habit_sections(), width=18)
        section_combo.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(0, 8))

        ttk.Label(frame, text="Habit", style="Label.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 8), pady=(0, 8))
        ttk.Entry(frame, textvariable=name_var, width=24).grid(row=0, column=3, sticky="w", pady=(0, 8))

        ttk.Label(frame, text="Cadence", style="Label.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        ttk.Combobox(
            frame,
            textvariable=cadence_var,
            values=[Cadence.DAILY.value, Cadence.WEEKLY.value, Cadence.MONTHLY.value],
            width=12,
            state="readonly",
        ).grid(row=1, column=1, sticky="w", padx=(0, 12), pady=(0, 8))

        ttk.Label(frame, text="Type", style="Label.TLabel").grid(row=1, column=2, sticky="w", padx=(0, 8), pady=(0, 8))
        mode_combo = ttk.Combobox(
            frame,
            textvariable=mode_var,
            values=[HabitMode.TARGET.value, HabitMode.OPEN_ENDED.value],
            width=14,
            state="readonly",
        )
        mode_combo.grid(row=1, column=3, sticky="w", pady=(0, 8))

        ttk.Label(frame, text="Target", style="Label.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 8))
        target_spin = ttk.Spinbox(frame, from_=1, to=365, width=10, textvariable=target_var)
        target_spin.grid(row=2, column=1, sticky="w", padx=(0, 12))

        ttk.Checkbutton(frame, text="Timed check-ins", variable=check_var).grid(row=2, column=2, sticky="w", padx=(0, 8))

        ttk.Label(frame, text="Every (hours)", style="Label.TLabel").grid(row=2, column=3, sticky="w", padx=(0, 8))
        interval_spin = ttk.Spinbox(frame, from_=1, to=24, width=8, textvariable=interval_var)
        interval_spin.grid(row=2, column=3, sticky="e")

        def toggle_target() -> None:
            target_spin.configure(state="normal" if mode_var.get() == HabitMode.TARGET.value else "disabled")

        def toggle_interval() -> None:
            interval_spin.configure(state="normal" if check_var.get() else "disabled")

        mode_combo.bind("<<ComboboxSelected>>", lambda _event: toggle_target())
        check_var.trace_add("write", lambda *_args: toggle_interval())

        toggle_target()
        toggle_interval()

        actions = ttk.Frame(frame, style="Panel.TFrame")
        actions.grid(row=3, column=0, columnspan=4, sticky="e", pady=(18, 0))

        def save_changes() -> None:
            valid, target_periods, interval_hours = self._validate_habit_form(
                name=name_var.get(),
                mode=mode_var.get(),
                target_text=target_var.get(),
                check_in_enabled=check_var.get(),
                interval_text=interval_var.get(),
            )
            if not valid:
                return

            updated = self.store.update_habit(
                habit.id,
                name=name_var.get(),
                section=section_var.get(),
                cadence=cadence_var.get(),
                mode=mode_var.get(),
                target_periods=target_periods,
                check_in_enabled=check_var.get(),
                check_in_interval_hours=interval_hours,
            )
            if updated is None:
                messagebox.showerror("Update failed", "Habit could not be updated.")
                return

            self.store.save()
            self._refresh_all_views()
            self._set_status(f"Updated habit '{updated.name}'.")
            dialog.destroy()

        ttk.Button(actions, text="Cancel", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(actions, text="Save", style="Accent.TButton", command=save_changes).pack(side="right")

    def _delete_selected_habit(self) -> None:
        habit = self._get_selected_habit()
        if habit is None:
            messagebox.showinfo("No habit selected", "Select a habit from the table first.")
            return

        confirm = messagebox.askyesno(
            "Delete habit",
            f"Delete '{habit.name}' from section '{habit.section}'?\nThis cannot be undone.",
        )
        if not confirm:
            return

        if self.store.delete_habit(habit.id):
            self.store.save()
            self._refresh_all_views()
            self._set_status(f"Deleted habit '{habit.name}'.")

    def _mark_period_done(self, habit_id: str) -> None:
        habit = self.store.get_habit(habit_id)
        if habit is None:
            return

        message = habit.mark_period_complete()
        self.store.save()
        self._refresh_all_views()
        self._set_status(f"{habit.name}: {message}")

    def _open_habit_details(self, habit_id: str) -> None:
        habit = self.store.get_habit(habit_id)
        if habit is None:
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Habit Details - {habit.name}")
        dialog.geometry("720x560")

        frame = ttk.Frame(dialog, style="Panel.TFrame", padding=(14, 12, 14, 12))
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=habit.name, style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=f"Section: {habit.section} | {habit.cadence} | {habit.mode}",
            style="CardMeta.TLabel",
        ).pack(anchor="w", pady=(2, 6))

        current, target = habit.current_progress()
        if habit.mode == HabitMode.TARGET.value:
            progress_text = f"Current run: {current}/{target} {habit.unit_label()}s"
        else:
            progress_text = f"Open-ended run completions: {current} {habit.unit_label()}s"

        ttk.Label(frame, text=progress_text, style="CardMeta.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                f"Best run: {habit.best_run_periods()} {habit.unit_label()}s | "
                f"Completed runs: {habit.completed_runs_count()} | Broken runs: {habit.broken_runs_count()}"
            ),
            style="CardMeta.TLabel",
        ).pack(anchor="w", pady=(2, 8))

        boxes_outer = ttk.Frame(frame, style="Panel.TFrame")
        boxes_outer.pack(fill="x", pady=(4, 10))

        boxes_inner = tk.Frame(boxes_outer, background="#f8faf5")
        boxes_inner.pack(anchor="w")

        colors = {
            "done": "#5fbf72",
            "missed": "#e06d6d",
            "pending": "#d4dccf",
        }
        boxes = habit.progress_boxes(max_boxes=40)
        max_per_row = 20
        for idx, box in enumerate(boxes):
            row_index = idx // max_per_row
            col_index = idx % max_per_row
            tk.Label(
                boxes_inner,
                text=box.get("label", ""),
                width=3,
                bg=colors.get(box.get("status", "pending"), "#d4dccf"),
                fg="#17271e",
                font=("Avenir Next", 9, "bold"),
                padx=1,
                pady=2,
            ).grid(row=row_index, column=col_index, padx=2, pady=2)

        history_text = tk.Text(
            frame,
            wrap="word",
            height=10,
            bg="#fbfcf8",
            fg="#24362b",
            font=("Menlo", 10),
        )
        history_text.pack(fill="both", expand=True)

        lines = ["Recent runs:"]
        for run in habit.recent_runs(limit=8):
            target_label = f"/{run.target_periods}" if run.target_periods > 0 else ""
            lines.append(
                f"- {run.status.upper()} {run.completed_count}{target_label} {habit.unit_label()}s | "
                f"ended {self._format_stamp(run.ended_at)}"
            )
            if run.break_reason:
                lines.append(f"  reason: {run.break_reason}")

        if habit.check_ins:
            lines.append("")
            lines.append("Recent check-ins:")
            for entry in habit.check_ins[-20:]:
                answer_label = "yes" if entry.answer else "no"
                lines.append(f"- {self._format_stamp(entry.timestamp)} -> {answer_label}")

        if habit.journal_entries:
            lines.append("")
            lines.append("Recent journal notes:")
            for entry in habit.recent_journal_entries(limit=10):
                lines.append(f"- [{entry.day}] {self._format_stamp(entry.timestamp)}")
                lines.append(f"  {entry.note}")

        history_text.insert("1.0", "\n".join(lines))
        history_text.configure(state="disabled")

        actions = ttk.Frame(frame, style="Panel.TFrame")
        actions.pack(fill="x", pady=(8, 0))

        left_actions = ttk.Frame(actions, style="Panel.TFrame")
        left_actions.pack(side="left")

        right_actions = ttk.Frame(actions, style="Panel.TFrame")
        right_actions.pack(side="right")

        ttk.Button(
            left_actions,
            text="Mark Done",
            style="Accent.TButton",
            command=lambda: self._mark_period_done_and_refresh_dialog(habit.id, dialog),
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            left_actions,
            text="Journal",
            command=lambda: self._open_habit_journal_dialog(habit.id),
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            left_actions,
            text="Edit",
            command=lambda: self._open_edit_habit_from_details(habit.id, dialog),
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            left_actions,
            text="Restart",
            command=lambda: self._restart_habit_from_details(habit.id, dialog),
        ).pack(side="left", padx=(0, 8))

        if habit.check_in_enabled:
            ttk.Button(
                left_actions,
                text="Yes",
                command=lambda: self._respond_check_in_from_details(habit.id, True, dialog),
            ).pack(side="left", padx=(0, 6))
            ttk.Button(
                left_actions,
                text="No",
                command=lambda: self._respond_check_in_from_details(habit.id, False, dialog),
            ).pack(side="left", padx=(0, 8))

        ttk.Button(
            right_actions,
            text="Delete",
            style="Danger.TButton",
            command=lambda: self._delete_habit_from_details(habit.id, dialog),
        ).pack(side="left", padx=(0, 8))

        ttk.Button(right_actions, text="Close", command=dialog.destroy).pack(side="left")

    def _mark_period_done_and_refresh_dialog(self, habit_id: str, dialog: tk.Toplevel) -> None:
        self._mark_period_done(habit_id)
        dialog.destroy()
        self._open_habit_details(habit_id)

    def _open_edit_habit_from_details(self, habit_id: str, dialog: tk.Toplevel) -> None:
        habit = self.store.get_habit(habit_id)
        if habit is None:
            return
        dialog.destroy()
        self._open_edit_habit_dialog(habit)

    def _delete_habit_from_details(self, habit_id: str, dialog: tk.Toplevel) -> None:
        habit = self.store.get_habit(habit_id)
        if habit is None:
            return
        confirm = messagebox.askyesno("Delete habit", f"Delete '{habit.name}'?")
        if not confirm:
            return
        self.store.delete_habit(habit_id)
        self.store.save()
        self._refresh_all_views()
        self._set_status(f"Deleted habit '{habit.name}'.")
        dialog.destroy()

    def _restart_habit_from_details(self, habit_id: str, dialog: tk.Toplevel) -> None:
        habit = self.store.get_habit(habit_id)
        if habit is None:
            return
        habit.break_and_restart("Manual reset")
        self.store.save()
        self._refresh_all_views()
        self._set_status(f"Restarted '{habit.name}'.")
        dialog.destroy()
        self._open_habit_details(habit_id)

    def _respond_check_in_from_details(self, habit_id: str, answer: bool, dialog: tk.Toplevel) -> None:
        habit = self.store.get_habit(habit_id)
        if habit is None:
            return
        message = habit.respond_check_in(answer)
        self.store.save()
        self._refresh_all_views()
        self._set_status(f"{habit.name}: {message}")
        dialog.destroy()
        self._open_habit_details(habit_id)

    def _open_habit_journal_dialog(self, habit_id: str) -> None:
        habit = self.store.get_habit(habit_id)
        if habit is None:
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Habit Journal - {habit.name}")
        dialog.geometry("760x620")

        frame = ttk.Frame(dialog, style="Panel.TFrame", padding=(14, 12, 14, 12))
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=f"{habit.name} Journal", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Record what you did each day.", style="CardMeta.TLabel").pack(anchor="w", pady=(2, 8))

        controls = ttk.Frame(frame, style="Panel.TFrame")
        controls.pack(fill="x", pady=(0, 8))

        day_var = tk.StringVar(value=date.today().isoformat())
        ttk.Label(controls, text="Day", style="Label.TLabel").pack(side="left", padx=(0, 8))
        day_entry = ttk.Entry(controls, textvariable=day_var, width=14)
        day_entry.pack(side="left", padx=(0, 12))
        self._attach_focus_hint(day_entry, "habit journal day")

        history_text = tk.Text(
            frame,
            wrap="word",
            height=16,
            bg="#fbfcf8",
            fg="#24362b",
            font=("Menlo", 10),
            state="disabled",
        )
        history_text.pack(fill="both", expand=True)
        self._style_text_focus(history_text)

        compose_label = ttk.Label(frame, text="New note", style="Label.TLabel")
        compose_label.pack(anchor="w", pady=(8, 4))

        compose_text = tk.Text(
            frame,
            wrap="word",
            height=5,
            bg="#fffdf7",
            fg="#2d4033",
            font=("Avenir Next", 11),
            insertbackground="#1f3127",
        )
        compose_text.pack(fill="x")
        self._style_text_focus(compose_text)
        self._attach_focus_hint(compose_text, "habit journal note")

        def refresh_history() -> None:
            lines: list[str] = []
            for entry in habit.recent_journal_entries(limit=200):
                lines.append(f"[{entry.day}] {self._format_stamp(entry.timestamp)}")
                lines.append(entry.note)
                lines.append("")
            if not lines:
                lines = ["No journal notes yet."]
            history_text.configure(state="normal")
            history_text.delete("1.0", "end")
            history_text.insert("1.0", "\n".join(lines).strip())
            history_text.configure(state="disabled")

        refresh_history()

        actions = ttk.Frame(frame, style="Panel.TFrame")
        actions.pack(fill="x", pady=(10, 0))

        def save_note() -> None:
            note = compose_text.get("1.0", "end").strip()
            if not note:
                messagebox.showerror("Invalid note", "Journal note cannot be empty.")
                return

            normalized_day = self._normalize_day_value(day_var.get())
            if normalized_day is None:
                messagebox.showerror("Invalid day", "Use date format YYYY-MM-DD.")
                return

            habit.add_journal_entry(note, day_value=str_to_date(normalized_day), when=datetime.now())
            self.store.save()
            compose_text.delete("1.0", "end")
            refresh_history()
            self._refresh_all_views()
            self._set_status(f"Saved journal note for {habit.name} on {normalized_day}.")

        ttk.Button(actions, text="Save Note", style="Accent.TButton", command=save_note).pack(side="left")
        ttk.Button(actions, text="Close", command=dialog.destroy).pack(side="right")

    def _browse_video_file(self) -> Optional[str]:
        selected = filedialog.askopenfilename(
            title="Select Video",
            filetypes=[
                ("Video files", "*.mp4 *.mov *.m4v *.avi *.mkv *.webm"),
                ("All files", "*.*"),
            ],
        )
        return selected or None

    def _play_video(self, path: Optional[str]) -> bool:
        if not path:
            return False
        file_path = Path(path)
        if not file_path.exists():
            messagebox.showerror("Video not found", f"The file does not exist:\n{path}")
            return False
        subprocess.Popen(["open", str(file_path)])
        return True

    def _browse_dopamine_video(self) -> None:
        selected = self._browse_video_file()
        if not selected:
            return
        self.dopamine_video_var.set(selected)

    def _save_dopamine_video(self) -> None:
        path = self.dopamine_video_var.get().strip() or None
        self.store.set_dopamine_video_path(path)
        self.store.save()
        self._set_status("Saved dopamine video path.")

    def _play_dopamine_video(self) -> None:
        path = self.store.settings.dopamine_video_path or self.dopamine_video_var.get().strip() or None
        if not path:
            messagebox.showinfo("No video selected", "Select a dopamine video in the Questions tab first.")
            return
        if self._play_video(path):
            self._set_status("Opened dopamine video.")

    def _validate_question_form(self, *, text: str, times_text: str) -> tuple[bool, int]:
        if not text.strip():
            messagebox.showerror("Invalid question", "Question text is required.")
            return False, 1
        try:
            times = int(times_text)
            if times < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid frequency", "Times value must be 1 or higher.")
            return False, 1
        return True, times

    def _browse_question_video(self) -> None:
        selected = self._browse_video_file()
        if not selected:
            return
        self.question_video_var.set(selected)

    def _add_question(self) -> None:
        valid, times = self._validate_question_form(
            text=self.question_text_var.get(),
            times_text=self.question_times_var.get(),
        )
        if not valid:
            return

        question = self.store.add_question(
            text=self.question_text_var.get(),
            cadence=self.question_cadence_var.get(),
            times_per_period=times,
            video_path=self.question_video_var.get().strip() or None,
        )
        self.store.save()

        self.question_text_var.set("")
        self.question_times_var.set("3")
        self.question_video_var.set("")

        self._refresh_questions_tree()
        self._set_status(f"Added question '{question.text[:40]}'.")

    def _get_selected_question(self) -> Optional[FocusQuestion]:
        if self.questions_tree is None:
            return None
        selected = self.questions_tree.selection()
        if not selected:
            return None
        return self.store.get_question(selected[0])

    def _open_edit_selected_question(self) -> None:
        question = self._get_selected_question()
        if question is None:
            messagebox.showinfo("No question selected", "Select a question from the table first.")
            return
        self._open_edit_question_dialog(question)

    def _open_edit_question_dialog(self, question: FocusQuestion) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Question")
        dialog.geometry("680x280")

        text_var = tk.StringVar(value=question.text)
        cadence_var = tk.StringVar(value=question.cadence)
        times_var = tk.StringVar(value=str(question.times_per_period))
        video_var = tk.StringVar(value=question.video_path or "")
        enabled_var = tk.BooleanVar(value=question.enabled)

        frame = ttk.Frame(dialog, style="Panel.TFrame", padding=(14, 12, 14, 12))
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Question", style="Label.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        ttk.Entry(frame, textvariable=text_var, width=64).grid(row=0, column=1, columnspan=3, sticky="w", pady=(0, 8))

        ttk.Label(frame, text="Cadence", style="Label.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        ttk.Combobox(
            frame,
            textvariable=cadence_var,
            values=[QuestionCadence.DAILY.value, QuestionCadence.WEEKLY.value],
            width=12,
            state="readonly",
        ).grid(row=1, column=1, sticky="w", padx=(0, 12), pady=(0, 8))

        ttk.Label(frame, text="Times", style="Label.TLabel").grid(row=1, column=2, sticky="w", padx=(0, 8), pady=(0, 8))
        ttk.Spinbox(frame, from_=1, to=60, width=8, textvariable=times_var).grid(row=1, column=3, sticky="w", pady=(0, 8))

        ttk.Label(frame, text="Video", style="Label.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(frame, textvariable=video_var, width=52).grid(row=2, column=1, columnspan=2, sticky="w", padx=(0, 8))

        def browse_video() -> None:
            selected = self._browse_video_file()
            if selected:
                video_var.set(selected)

        ttk.Button(frame, text="Browse", command=browse_video).grid(row=2, column=3, sticky="w")
        ttk.Checkbutton(frame, text="Enabled", variable=enabled_var).grid(row=3, column=0, sticky="w", pady=(10, 0))

        actions = ttk.Frame(frame, style="Panel.TFrame")
        actions.grid(row=4, column=0, columnspan=4, sticky="e", pady=(18, 0))

        def save_changes() -> None:
            valid, times_value = self._validate_question_form(text=text_var.get(), times_text=times_var.get())
            if not valid:
                return

            updated = self.store.update_question(
                question.id,
                text=text_var.get(),
                cadence=cadence_var.get(),
                times_per_period=times_value,
                video_path=video_var.get().strip() or None,
                enabled=enabled_var.get(),
            )
            if updated is None:
                messagebox.showerror("Update failed", "Question could not be updated.")
                return

            self.store.save()
            self._refresh_questions_tree()
            self._set_status("Updated question.")
            dialog.destroy()

        ttk.Button(actions, text="Cancel", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(actions, text="Save", style="Accent.TButton", command=save_changes).pack(side="right")

    def _toggle_selected_question(self) -> None:
        question = self._get_selected_question()
        if question is None:
            messagebox.showinfo("No question selected", "Select a question from the table first.")
            return

        updated = self.store.toggle_question_enabled(question.id)
        if updated is None:
            return
        self.store.save()
        self._refresh_questions_tree()
        self._set_status(f"Question '{updated.text[:28]}' is now {'enabled' if updated.enabled else 'disabled'}.")

    def _delete_selected_question(self) -> None:
        question = self._get_selected_question()
        if question is None:
            messagebox.showinfo("No question selected", "Select a question from the table first.")
            return

        confirm = messagebox.askyesno("Delete question", "Delete this question?")
        if not confirm:
            return

        if self.store.delete_question(question.id):
            self.store.save()
            self._refresh_questions_tree()
            self._set_status("Question deleted.")

    def _send_macos_notification(self, title: str, message: str) -> None:
        if sys.platform != "darwin":
            return
        safe_title = title.replace('"', '\\"')
        safe_message = message.replace('"', '\\"')
        script = f'display notification "{safe_message}" with title "{safe_title}"'
        subprocess.run(
            ["osascript", "-e", script],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _prompt_due_habit_check_ins(self) -> bool:
        due_habits = [habit for habit in self.store.habits if habit.check_in_due(datetime.now())]
        if not due_habits:
            return False

        changed = False
        for habit in due_habits:
            self._send_macos_notification("Habit Pulse", f"Still going strong with {habit.name}?")

            answer = messagebox.askyesnocancel(
                "Still going strong?",
                (
                    f"Still going strong with '{habit.name}'?\n\n"
                    "Yes: keep going\n"
                    "No: apply habit reset logic\n"
                    "Cancel: remind in 10 minutes"
                ),
            )
            now_value = datetime.now()

            if answer is None:
                habit.snooze_check_in(minutes=10, when=now_value)
                self._set_status(f"Snoozed check-in for {habit.name} by 10 minutes.")
                changed = True
                continue

            message = habit.respond_check_in(answer, when=now_value)
            self._set_status(f"{habit.name}: {message}")
            changed = True

        return changed

    def _prompt_due_questions(self) -> bool:
        due_questions = self.store.due_questions(datetime.now())
        if not due_questions:
            return False

        changed = False
        for question in due_questions:
            self._send_macos_notification("Focus Question", question.text)
            answer = messagebox.askyesno(
                "Question Prompt",
                f"{question.text}\n\nYes: keep focused\nNo: open assigned video",
            )
            now_value = datetime.now()

            if not answer and question.video_path:
                self._play_video(question.video_path)

            question.record_answer(answer, when=now_value)
            changed = True
            if answer:
                self._set_status("Question answered yes.")
            elif question.video_path:
                self._set_status("Question answered no. Video opened.")
            else:
                self._set_status("Question answered no. No video configured.")

        return changed

    def _heartbeat(self) -> None:
        changed = self.store.sync_for_missed_days()

        if self._prompt_due_habit_check_ins():
            changed = True
        if self._prompt_due_questions():
            changed = True

        if changed:
            self.store.save()
            self._refresh_all_views()

        self.root.after(60_000, self._heartbeat)
