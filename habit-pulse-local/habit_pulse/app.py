from __future__ import annotations

import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk
from typing import Optional

from .models import Habit, RunStatus, str_to_dt
from .store import HabitStore


class HabitPulseApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Habit Pulse Local")
        self.root.geometry("1100x760")
        self.root.minsize(980, 640)

        self.store = HabitStore()
        self.store.load()
        if self.store.sync_for_missed_days():
            self.store.save()

        self.name_var = tk.StringVar()
        self.target_days_var = tk.StringVar(value="30")
        self.check_in_var = tk.BooleanVar(value=False)
        self.interval_hours_var = tk.StringVar(value="2")
        self.status_var = tk.StringVar(value="Ready. All data stays local on this Mac.")

        self.cards_canvas: Optional[tk.Canvas] = None
        self.cards_frame: Optional[ttk.Frame] = None
        self.canvas_window: Optional[int] = None
        self.interval_spin: Optional[ttk.Spinbox] = None

        self._configure_styles()
        self._build_layout()
        self._render_cards()

        self.root.after(60_000, self._heartbeat)

    def _configure_styles(self) -> None:
        self.root.configure(background="#eff2eb")

        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Root.TFrame", background="#eff2eb")
        style.configure("Panel.TFrame", background="#f8faf5")
        style.configure("Card.TFrame", background="#fcfdf9", borderwidth=1, relief="solid")

        style.configure(
            "Heading.TLabel",
            background="#eff2eb",
            foreground="#213226",
            font=("Avenir Next", 28, "bold"),
        )
        style.configure(
            "Subheading.TLabel",
            background="#eff2eb",
            foreground="#4a5f50",
            font=("Avenir Next", 12),
        )
        style.configure(
            "Label.TLabel",
            background="#f8faf5",
            foreground="#2c3c31",
            font=("Avenir Next", 11),
        )
        style.configure(
            "CardTitle.TLabel",
            background="#fcfdf9",
            foreground="#1d2e22",
            font=("Avenir Next", 16, "bold"),
        )
        style.configure(
            "CardMeta.TLabel",
            background="#fcfdf9",
            foreground="#4b5f4f",
            font=("Avenir Next", 10),
        )
        style.configure(
            "Status.TLabel",
            background="#eff2eb",
            foreground="#2f4638",
            font=("Avenir Next", 10),
        )
        style.configure(
            "Pill.TLabel",
            background="#dde7d8",
            foreground="#2b3e31",
            padding=(8, 3),
            font=("Avenir Next", 10, "bold"),
        )

        style.configure("Accent.TButton", font=("Avenir Next", 10, "bold"))

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, style="Root.TFrame", padding=(20, 16, 20, 16))
        container.pack(fill="both", expand=True)

        header = ttk.Frame(container, style="Root.TFrame")
        header.pack(fill="x")

        ttk.Label(header, text="Habit Pulse", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Minimal local habit tracker with streak resets, history, and timed check-ins.",
            style="Subheading.TLabel",
        ).pack(anchor="w", pady=(0, 10))

        form = ttk.Frame(container, style="Panel.TFrame", padding=(14, 12, 14, 12))
        form.pack(fill="x")

        ttk.Label(form, text="Habit", style="Label.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(form, textvariable=self.name_var, width=28).grid(row=0, column=1, sticky="w", padx=(0, 14))

        ttk.Label(form, text="Target Days", style="Label.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 8))
        ttk.Spinbox(
            form,
            from_=1,
            to=365,
            width=6,
            textvariable=self.target_days_var,
        ).grid(row=0, column=3, sticky="w", padx=(0, 14))

        check_box = ttk.Checkbutton(
            form,
            text="Timed check-ins",
            variable=self.check_in_var,
            command=self._toggle_interval_state,
        )
        check_box.grid(row=0, column=4, sticky="w", padx=(0, 8))

        ttk.Label(form, text="Every (hours)", style="Label.TLabel").grid(row=0, column=5, sticky="w", padx=(0, 8))
        self.interval_spin = ttk.Spinbox(
            form,
            from_=1,
            to=24,
            width=6,
            textvariable=self.interval_hours_var,
        )
        self.interval_spin.grid(row=0, column=6, sticky="w", padx=(0, 14))

        ttk.Button(
            form,
            text="Add Habit",
            style="Accent.TButton",
            command=self._add_habit,
        ).grid(row=0, column=7, sticky="e")

        form.columnconfigure(1, weight=1)
        form.columnconfigure(7, weight=0)

        cards_outer = ttk.Frame(container, style="Root.TFrame")
        cards_outer.pack(fill="both", expand=True, pady=(12, 8))

        self.cards_canvas = tk.Canvas(
            cards_outer,
            background="#eff2eb",
            highlightthickness=0,
            bd=0,
        )
        scrollbar = ttk.Scrollbar(cards_outer, orient="vertical", command=self.cards_canvas.yview)
        self.cards_canvas.configure(yscrollcommand=scrollbar.set)

        self.cards_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.cards_frame = ttk.Frame(self.cards_canvas, style="Root.TFrame")
        self.canvas_window = self.cards_canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")

        self.cards_frame.bind("<Configure>", self._update_scroll_region)
        self.cards_canvas.bind("<Configure>", self._resize_canvas_window)
        self.cards_canvas.bind_all("<MouseWheel>", self._on_mouse_wheel)

        status = ttk.Label(container, textvariable=self.status_var, style="Status.TLabel")
        status.pack(fill="x")

        self._toggle_interval_state()

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        if self.cards_canvas is None:
            return
        self.cards_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _update_scroll_region(self, _event: tk.Event) -> None:
        if self.cards_canvas is None:
            return
        self.cards_canvas.configure(scrollregion=self.cards_canvas.bbox("all"))

    def _resize_canvas_window(self, event: tk.Event) -> None:
        if self.cards_canvas is None or self.canvas_window is None:
            return
        self.cards_canvas.itemconfigure(self.canvas_window, width=event.width)

    def _toggle_interval_state(self) -> None:
        if self.interval_spin is None:
            return
        if self.check_in_var.get():
            self.interval_spin.configure(state="normal")
        else:
            self.interval_spin.configure(state="disabled")

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)

    def _add_habit(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Missing habit name", "Please enter a habit name.")
            return

        try:
            target_days = int(self.target_days_var.get())
            if target_days < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid target", "Target days must be a number 1 or higher.")
            return

        check_in_enabled = self.check_in_var.get()
        interval_hours = 2
        if check_in_enabled:
            try:
                interval_hours = int(self.interval_hours_var.get())
                if interval_hours < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid interval", "Check-in interval must be 1 hour or more.")
                return

        habit = self.store.add_habit(
            name=name,
            target_days=target_days,
            check_in_enabled=check_in_enabled,
            check_in_interval_hours=interval_hours,
        )
        self.store.save()

        self.name_var.set("")
        self.target_days_var.set("30")
        self.check_in_var.set(False)
        self.interval_hours_var.set("2")
        self._toggle_interval_state()

        self._render_cards()
        self._set_status(f"Added habit: {habit.name}")

    def _get_habit(self, habit_id: str) -> Optional[Habit]:
        return self.store.get_habit(habit_id)

    def _mark_today_done(self, habit_id: str) -> None:
        habit = self._get_habit(habit_id)
        if habit is None:
            return

        message = habit.mark_day_complete(date.today())
        self.store.save()
        self._render_cards()
        self._set_status(f"{habit.name}: {message}")

    def _break_and_restart(self, habit_id: str) -> None:
        habit = self._get_habit(habit_id)
        if habit is None:
            return

        proceed = messagebox.askyesno(
            "Break run?",
            f"Break and restart your current run for '{habit.name}'?\nYour progress will be saved in history.",
        )
        if not proceed:
            return

        message = habit.break_and_restart("Manual reset")
        self.store.save()
        self._render_cards()
        self._set_status(f"{habit.name}: {message}")

    def _quick_check_in(self, habit_id: str, answer: bool) -> None:
        habit = self._get_habit(habit_id)
        if habit is None:
            return

        message = habit.respond_check_in(answer)
        self.store.save()
        self._render_cards()
        self._set_status(f"{habit.name}: {message}")

    def _format_due_text(self, habit: Habit) -> str:
        if not habit.next_check_in_at:
            return "not scheduled"

        try:
            due = str_to_dt(habit.next_check_in_at)
        except ValueError:
            return "not scheduled"

        delta = due - datetime.now()
        total_seconds = int(delta.total_seconds())
        if total_seconds <= 0:
            return "due now"

        hours, remainder = divmod(total_seconds, 3600)
        minutes = remainder // 60
        if hours > 0:
            return f"in {hours}h {minutes}m"
        return f"in {minutes}m"

    def _format_stamp(self, value: Optional[str]) -> str:
        if not value:
            return "-"
        try:
            parsed = str_to_dt(value)
            return parsed.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return value

    def _render_cards(self) -> None:
        if self.cards_frame is None:
            return

        for child in self.cards_frame.winfo_children():
            child.destroy()

        self.cards_frame.columnconfigure(0, weight=1)

        if not self.store.habits:
            empty = ttk.Frame(self.cards_frame, style="Card.TFrame", padding=(16, 14, 16, 14))
            empty.grid(row=0, column=0, sticky="ew", pady=8)
            ttk.Label(
                empty,
                text="No habits yet. Add one above to start tracking.",
                style="CardMeta.TLabel",
            ).pack(anchor="w")
            return

        for index, habit in enumerate(self.store.habits):
            card = ttk.Frame(self.cards_frame, style="Card.TFrame", padding=(14, 12, 14, 12))
            card.grid(row=index, column=0, sticky="ew", pady=8)
            card.columnconfigure(0, weight=1)

            header = ttk.Frame(card, style="Card.TFrame")
            header.grid(row=0, column=0, sticky="ew")
            header.columnconfigure(0, weight=1)

            ttk.Label(header, text=habit.name, style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
            if habit.check_in_enabled:
                ttk.Label(
                    header,
                    text=f"Check every {habit.check_in_interval_hours}h",
                    style="Pill.TLabel",
                ).grid(row=0, column=1, sticky="e")

            current, target = habit.current_progress()
            ttk.Label(
                card,
                text=f"Current run: {current}/{target} days",
                style="CardMeta.TLabel",
            ).grid(row=1, column=0, sticky="w", pady=(8, 2))

            bar = ttk.Progressbar(card, orient="horizontal", mode="determinate", maximum=max(1, target), value=current)
            bar.grid(row=2, column=0, sticky="ew", pady=(0, 8))

            stats_text = (
                f"Best run: {habit.best_run_days()} days   "
                f"Completed runs: {habit.completed_runs_count()}   "
                f"Broken runs: {habit.broken_runs_count()}"
            )
            ttk.Label(card, text=stats_text, style="CardMeta.TLabel").grid(row=3, column=0, sticky="w")

            if habit.check_in_enabled:
                ttk.Label(
                    card,
                    text=f"Next check-in: {self._format_due_text(habit)}",
                    style="CardMeta.TLabel",
                ).grid(row=4, column=0, sticky="w", pady=(3, 0))
                controls_row = 5
            else:
                controls_row = 4

            recent_runs = habit.recent_runs(limit=2)
            if recent_runs:
                summary_parts = []
                for run in recent_runs:
                    ended_label = self._format_stamp(run.ended_at)
                    summary_parts.append(
                        f"{run.status}: {run.completed_count}/{run.target_days} days (ended {ended_label})"
                    )
                ttk.Label(
                    card,
                    text="Recent: " + " | ".join(summary_parts),
                    style="CardMeta.TLabel",
                ).grid(row=controls_row, column=0, sticky="w", pady=(6, 0))
                controls_row += 1

            controls = ttk.Frame(card, style="Card.TFrame")
            controls.grid(row=controls_row, column=0, sticky="w", pady=(8, 0))

            ttk.Button(
                controls,
                text="Mark Today Complete",
                command=lambda habit_id=habit.id: self._mark_today_done(habit_id),
            ).pack(side="left", padx=(0, 8))

            ttk.Button(
                controls,
                text="Break + Restart",
                command=lambda habit_id=habit.id: self._break_and_restart(habit_id),
            ).pack(side="left", padx=(0, 8))

            ttk.Button(
                controls,
                text="History",
                command=lambda habit_id=habit.id: self._show_history(habit_id),
            ).pack(side="left", padx=(0, 8))

            if habit.check_in_enabled:
                ttk.Button(
                    controls,
                    text="Yes",
                    command=lambda habit_id=habit.id: self._quick_check_in(habit_id, True),
                ).pack(side="left", padx=(0, 6))
                ttk.Button(
                    controls,
                    text="No",
                    command=lambda habit_id=habit.id: self._quick_check_in(habit_id, False),
                ).pack(side="left")

    def _show_history(self, habit_id: str) -> None:
        habit = self._get_habit(habit_id)
        if habit is None:
            return

        window = tk.Toplevel(self.root)
        window.title(f"History - {habit.name}")
        window.geometry("780x520")

        text = tk.Text(
            window,
            wrap="word",
            padx=12,
            pady=12,
            bg="#fbfcf8",
            fg="#24362b",
            font=("Menlo", 11),
        )
        text.pack(fill="both", expand=True)

        lines = [
            f"Habit: {habit.name}",
            f"Target days: {habit.target_days}",
            f"Created: {self._format_stamp(habit.created_at)}",
            "",
            "Runs:",
        ]

        runs = list(habit.runs)
        runs.sort(key=lambda item: item.started_at, reverse=True)
        for idx, run in enumerate(runs, start=1):
            lines.append(
                f"{idx}. {run.status.upper()} | {run.completed_count}/{run.target_days} days | "
                f"start {self._format_stamp(run.started_at)} | end {self._format_stamp(run.ended_at)}"
            )
            if run.break_reason:
                lines.append(f"   reason: {run.break_reason}")

        lines.extend(["", "Timed check-ins:"])
        if not habit.check_ins:
            lines.append("No check-ins yet.")
        else:
            for check in habit.check_ins[-60:]:
                answer_label = "yes" if check.answer else "no"
                lines.append(f"- {self._format_stamp(check.timestamp)} -> {answer_label}")

        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")

    def _prompt_due_check_ins(self) -> bool:
        due_habits = [habit for habit in self.store.habits if habit.check_in_due(datetime.now())]
        if not due_habits:
            return False

        changed = False
        for habit in due_habits:
            answer = messagebox.askyesnocancel(
                "Still going strong?",
                (
                    f"Still going strong with '{habit.name}'?\n\n"
                    "Yes: keep run going\n"
                    "No: break run and restart\n"
                    "Cancel: remind me in 10 minutes"
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

    def _heartbeat(self) -> None:
        changed = self.store.sync_for_missed_days()
        if self._prompt_due_check_ins():
            changed = True

        if changed:
            self.store.save()

        self._render_cards()
        self.root.after(60_000, self._heartbeat)
