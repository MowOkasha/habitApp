from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from .models import Cadence, FocusQuestion, Habit, HabitMode, QuestionCadence, str_to_dt
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

        self.dopamine_video_var = tk.StringVar(value=self.store.settings.dopamine_video_path or "")

        self.habit_section_combo: Optional[ttk.Combobox] = None
        self.habit_target_spin: Optional[ttk.Spinbox] = None
        self.habit_interval_spin: Optional[ttk.Spinbox] = None

        self.cards_canvas: Optional[tk.Canvas] = None
        self.cards_frame: Optional[ttk.Frame] = None
        self.cards_window: Optional[int] = None

        self.habits_tree: Optional[ttk.Treeview] = None
        self.questions_tree: Optional[ttk.Treeview] = None

        self._configure_styles()
        self._build_layout()
        self._refresh_all_views()

        self.root.after(60_000, self._heartbeat)

    def _configure_styles(self) -> None:
        self.root.configure(background="#f0f3ec")

        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Root.TFrame", background="#f0f3ec")
        style.configure("Panel.TFrame", background="#f8faf5")
        style.configure("Card.TFrame", background="#fcfdf9", borderwidth=1, relief="solid")

        style.configure(
            "Heading.TLabel",
            background="#f0f3ec",
            foreground="#1f3127",
            font=("Avenir Next", 28, "bold"),
        )
        style.configure(
            "Subheading.TLabel",
            background="#f0f3ec",
            foreground="#4f6254",
            font=("Avenir Next", 12),
        )
        style.configure(
            "Label.TLabel",
            background="#f8faf5",
            foreground="#2d4033",
            font=("Avenir Next", 11),
        )
        style.configure(
            "SectionLabel.TLabel",
            background="#f0f3ec",
            foreground="#1f3127",
            font=("Avenir Next", 16, "bold"),
        )
        style.configure(
            "CardTitle.TLabel",
            background="#fcfdf9",
            foreground="#1b2c21",
            font=("Avenir Next", 14, "bold"),
        )
        style.configure(
            "CardMeta.TLabel",
            background="#fcfdf9",
            foreground="#4a5f4f",
            font=("Avenir Next", 10),
        )
        style.configure(
            "Pill.TLabel",
            background="#dde8d9",
            foreground="#2b3e31",
            padding=(8, 3),
            font=("Avenir Next", 9, "bold"),
        )
        style.configure(
            "Status.TLabel",
            background="#f0f3ec",
            foreground="#2f4638",
            font=("Avenir Next", 10),
        )
        style.configure("Accent.TButton", font=("Avenir Next", 10, "bold"))

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
            text="Cards by section, editable settings, and dopamine-aware prompt questions.",
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

        notebook.add(tracker_tab, text="Tracker")
        notebook.add(settings_tab, text="Settings")
        notebook.add(questions_tab, text="Questions")

        self._build_tracker_tab(tracker_tab)
        self._build_settings_tab(settings_tab)
        self._build_questions_tab(questions_tab)

        ttk.Label(container, textvariable=self.status_var, style="Status.TLabel").pack(fill="x", pady=(2, 0))

    def _build_tracker_tab(self, parent: ttk.Frame) -> None:
        form = ttk.Frame(parent, style="Panel.TFrame", padding=(12, 10, 12, 10))
        form.pack(fill="x", pady=(0, 8))

        ttk.Label(form, text="Section", style="Label.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 6))
        self.habit_section_combo = ttk.Combobox(
            form,
            textvariable=self.habit_section_var,
            values=self.store.list_sections(),
            width=16,
        )
        self.habit_section_combo.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(0, 6))

        ttk.Label(form, text="Habit", style="Label.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 8), pady=(0, 6))
        ttk.Entry(form, textvariable=self.habit_name_var, width=28).grid(row=0, column=3, sticky="w", padx=(0, 12), pady=(0, 6))

        ttk.Label(form, text="Cadence", style="Label.TLabel").grid(row=0, column=4, sticky="w", padx=(0, 8), pady=(0, 6))
        ttk.Combobox(
            form,
            textvariable=self.habit_cadence_var,
            values=[Cadence.DAILY.value, Cadence.WEEKLY.value, Cadence.MONTHLY.value],
            width=10,
            state="readonly",
        ).grid(row=0, column=5, sticky="w", padx=(0, 12), pady=(0, 6))

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

        ttk.Label(form, text="Target", style="Label.TLabel").grid(row=1, column=2, sticky="w", padx=(0, 8))
        self.habit_target_spin = ttk.Spinbox(
            form,
            from_=1,
            to=365,
            width=8,
            textvariable=self.habit_target_var,
        )
        self.habit_target_spin.grid(row=1, column=3, sticky="w", padx=(0, 12))

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

        ttk.Label(section_panel, text="Create section", style="Label.TLabel").pack(side="left", padx=(0, 8))
        ttk.Entry(section_panel, textvariable=self.section_add_var, width=24).pack(side="left", padx=(0, 8))
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

        ttk.Button(actions, text="Edit Habit", command=self._open_edit_selected_habit).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Delete Habit", command=self._delete_selected_habit).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Refresh", command=self._refresh_all_views).pack(side="left")

        self.habits_tree.bind("<Double-1>", lambda _event: self._open_edit_selected_habit())

    def _build_questions_tab(self, parent: ttk.Frame) -> None:
        dopamine_panel = ttk.Frame(parent, style="Panel.TFrame", padding=(12, 10, 12, 10))
        dopamine_panel.pack(fill="x", pady=(0, 8))

        ttk.Label(dopamine_panel, text="Default dopamine video", style="Label.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(dopamine_panel, textvariable=self.dopamine_video_var, width=72).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(dopamine_panel, text="Browse", command=self._browse_dopamine_video).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(dopamine_panel, text="Save", command=self._save_dopamine_video).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(dopamine_panel, text="Play", command=self._play_dopamine_video).grid(row=0, column=4)
        dopamine_panel.columnconfigure(1, weight=1)

        form = ttk.Frame(parent, style="Panel.TFrame", padding=(12, 10, 12, 10))
        form.pack(fill="x", pady=(0, 8))

        ttk.Label(form, text="Question", style="Label.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 6))
        ttk.Entry(form, textvariable=self.question_text_var, width=56).grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(0, 6))

        ttk.Label(form, text="Cadence", style="Label.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 8), pady=(0, 6))
        ttk.Combobox(
            form,
            textvariable=self.question_cadence_var,
            values=[QuestionCadence.DAILY.value, QuestionCadence.WEEKLY.value],
            width=10,
            state="readonly",
        ).grid(row=0, column=3, sticky="w", padx=(0, 12), pady=(0, 6))

        ttk.Label(form, text="Times", style="Label.TLabel").grid(row=0, column=4, sticky="w", padx=(0, 8), pady=(0, 6))
        ttk.Spinbox(form, from_=1, to=60, width=8, textvariable=self.question_times_var).grid(row=0, column=5, sticky="w", padx=(0, 12), pady=(0, 6))

        ttk.Label(form, text="Video", style="Label.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(form, textvariable=self.question_video_var, width=56).grid(row=1, column=1, sticky="w", padx=(0, 12))
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

        ttk.Button(actions, text="Edit Question", command=self._open_edit_selected_question).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Toggle Enabled", command=self._toggle_selected_question).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Delete Question", command=self._delete_selected_question).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Refresh", command=self._refresh_all_views).pack(side="left")

        self.questions_tree.bind("<Double-1>", lambda _event: self._open_edit_selected_question())

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

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        if self.cards_canvas is None:
            return
        self.cards_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _update_cards_scroll(self, _event: tk.Event) -> None:
        if self.cards_canvas is None:
            return
        self.cards_canvas.configure(scrollregion=self.cards_canvas.bbox("all"))

    def _resize_cards_window(self, event: tk.Event) -> None:
        if self.cards_canvas is None or self.cards_window is None:
            return
        self.cards_canvas.itemconfigure(self.cards_window, width=event.width)

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
        sections = self.store.list_sections()
        if self.habit_section_combo is not None:
            self.habit_section_combo.configure(values=sections)
        if not self.habit_section_var.get().strip():
            self.habit_section_var.set(sections[0])

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

    def _make_clickable(self, widget: tk.Widget, callback) -> None:
        widget.bind("<Button-1>", lambda _event: callback())
        for child in widget.winfo_children():
            if isinstance(child, (ttk.Button, tk.Button, ttk.Entry, ttk.Combobox, ttk.Spinbox)):
                continue
            self._make_clickable(child, callback)

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
            columns = 2
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
                    command=lambda selected=habit.id: self._mark_period_done(selected),
                ).pack(side="left", padx=(0, 8))
                ttk.Button(
                    actions,
                    text="Details",
                    command=lambda selected=habit.id: self._open_habit_details(selected),
                ).pack(side="left")

                self._make_clickable(card, lambda selected=habit.id: self._open_habit_details(selected))

    def _refresh_all_views(self) -> None:
        self._refresh_section_choices()
        self._render_tracker_cards()
        self._refresh_habits_tree()
        self._refresh_questions_tree()

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

        normalized = self.store.add_section(section)
        self.store.save()
        self.section_add_var.set("")
        self.habit_section_var.set(normalized)
        self._refresh_all_views()
        self._set_status(f"Added section '{normalized}'.")

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
        section_combo = ttk.Combobox(frame, textvariable=section_var, values=self.store.list_sections(), width=18)
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

        history_text.insert("1.0", "\n".join(lines))
        history_text.configure(state="disabled")

        actions = ttk.Frame(frame, style="Panel.TFrame")
        actions.pack(fill="x", pady=(8, 0))

        ttk.Button(
            actions,
            text="Mark Done",
            command=lambda: self._mark_period_done_and_refresh_dialog(habit.id, dialog),
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            actions,
            text="Edit",
            command=lambda: self._open_edit_habit_from_details(habit.id, dialog),
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            actions,
            text="Delete",
            command=lambda: self._delete_habit_from_details(habit.id, dialog),
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            actions,
            text="Restart",
            command=lambda: self._restart_habit_from_details(habit.id, dialog),
        ).pack(side="left", padx=(0, 8))

        if habit.check_in_enabled:
            ttk.Button(
                actions,
                text="Yes",
                command=lambda: self._respond_check_in_from_details(habit.id, True, dialog),
            ).pack(side="left", padx=(0, 6))
            ttk.Button(
                actions,
                text="No",
                command=lambda: self._respond_check_in_from_details(habit.id, False, dialog),
            ).pack(side="left", padx=(0, 8))

        ttk.Button(actions, text="Close", command=dialog.destroy).pack(side="right")

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
