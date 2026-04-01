from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from collections import defaultdict
from datetime import date, datetime
from tkinter import messagebox, ttk
from typing import Optional

from .models import Cadence, Habit, HabitMode, str_to_dt
from .store import HabitStore


class HabitPulseApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Habit Pulse")
        self.root.geometry("1220x820")
        self.root.minsize(1040, 700)

        self.store = HabitStore()
        self.store.load()
        if self.store.sync_for_missed_days():
            self.store.save()

        self.section_var = tk.StringVar(value="General")
        self.name_var = tk.StringVar()
        self.cadence_var = tk.StringVar(value=Cadence.DAILY.value)
        self.mode_var = tk.StringVar(value=HabitMode.TARGET.value)
        self.target_periods_var = tk.StringVar(value="30")
        self.check_in_var = tk.BooleanVar(value=False)
        self.interval_hours_var = tk.StringVar(value="2")
        self.status_var = tk.StringVar(value="Ready. Data is local on this Mac.")

        self.cards_canvas: Optional[tk.Canvas] = None
        self.cards_frame: Optional[ttk.Frame] = None
        self.canvas_window: Optional[int] = None

        self.section_combo: Optional[ttk.Combobox] = None
        self.target_spin: Optional[ttk.Spinbox] = None
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
            foreground="#1f3127",
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
            foreground="#19291f",
            font=("Avenir Next", 16, "bold"),
        )
        style.configure(
            "CardMeta.TLabel",
            background="#fcfdf9",
            foreground="#4a5f4f",
            font=("Avenir Next", 10),
        )
        style.configure(
            "SectionTitle.TLabel",
            background="#eff2eb",
            foreground="#1f3127",
            font=("Avenir Next", 15, "bold"),
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
            text="Sectioned habits with daily, weekly, monthly tracking and timed check-ins.",
            style="Subheading.TLabel",
        ).pack(anchor="w", pady=(0, 10))

        form = ttk.Frame(container, style="Panel.TFrame", padding=(14, 12, 14, 12))
        form.pack(fill="x")

        ttk.Label(form, text="Section", style="Label.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        self.section_combo = ttk.Combobox(
            form,
            textvariable=self.section_var,
            values=self.store.list_sections(),
            width=16,
        )
        self.section_combo.grid(row=0, column=1, sticky="w", padx=(0, 16), pady=(0, 8))

        ttk.Label(form, text="Habit", style="Label.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 8), pady=(0, 8))
        ttk.Entry(form, textvariable=self.name_var, width=28).grid(row=0, column=3, sticky="w", padx=(0, 16), pady=(0, 8))

        ttk.Label(form, text="Cadence", style="Label.TLabel").grid(row=0, column=4, sticky="w", padx=(0, 8), pady=(0, 8))
        cadence_combo = ttk.Combobox(
            form,
            textvariable=self.cadence_var,
            values=[Cadence.DAILY.value, Cadence.WEEKLY.value, Cadence.MONTHLY.value],
            width=10,
            state="readonly",
        )
        cadence_combo.grid(row=0, column=5, sticky="w", padx=(0, 16), pady=(0, 8))

        ttk.Label(form, text="Type", style="Label.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 8))
        mode_combo = ttk.Combobox(
            form,
            textvariable=self.mode_var,
            values=[HabitMode.TARGET.value, HabitMode.OPEN_ENDED.value],
            width=16,
            state="readonly",
        )
        mode_combo.grid(row=1, column=1, sticky="w", padx=(0, 16))
        mode_combo.bind("<<ComboboxSelected>>", lambda _event: self._toggle_target_state())

        ttk.Label(form, text="Target Periods", style="Label.TLabel").grid(row=1, column=2, sticky="w", padx=(0, 8))
        self.target_spin = ttk.Spinbox(
            form,
            from_=1,
            to=365,
            width=8,
            textvariable=self.target_periods_var,
        )
        self.target_spin.grid(row=1, column=3, sticky="w", padx=(0, 16))

        ttk.Checkbutton(
            form,
            text="Timed check-ins",
            variable=self.check_in_var,
            command=self._toggle_interval_state,
        ).grid(row=1, column=4, sticky="w", padx=(0, 8))

        ttk.Label(form, text="Every (hours)", style="Label.TLabel").grid(row=1, column=5, sticky="w", padx=(0, 8))
        self.interval_spin = ttk.Spinbox(
            form,
            from_=1,
            to=24,
            width=6,
            textvariable=self.interval_hours_var,
        )
        self.interval_spin.grid(row=1, column=6, sticky="w", padx=(0, 16))

        ttk.Button(
            form,
            text="Add Habit",
            style="Accent.TButton",
            command=self._add_habit,
        ).grid(row=1, column=7, sticky="e")

        form.columnconfigure(7, weight=1)

        legend = ttk.Frame(container, style="Root.TFrame")
        legend.pack(fill="x", pady=(8, 4))
        self._legend_chip(legend, "Done", "#5fbf72").pack(side="left", padx=(0, 8))
        self._legend_chip(legend, "Missed", "#e06d6d").pack(side="left", padx=(0, 8))
        self._legend_chip(legend, "Pending", "#d4dccf").pack(side="left", padx=(0, 8))

        cards_outer = ttk.Frame(container, style="Root.TFrame")
        cards_outer.pack(fill="both", expand=True, pady=(6, 8))

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

        self._refresh_section_choices()
        self._toggle_target_state()
        self._toggle_interval_state()

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

    def _refresh_section_choices(self) -> None:
        if self.section_combo is None:
            return
        values = self.store.list_sections()
        self.section_combo.configure(values=values)
        if not self.section_var.get().strip():
            self.section_var.set(values[0])

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
        self.interval_spin.configure(state="normal" if self.check_in_var.get() else "disabled")

    def _toggle_target_state(self) -> None:
        if self.target_spin is None:
            return
        is_target = self.mode_var.get() == HabitMode.TARGET.value
        self.target_spin.configure(state="normal" if is_target else "disabled")

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)

    def _add_habit(self) -> None:
        section = self.section_var.get().strip() or "General"
        name = self.name_var.get().strip()
        cadence = self.cadence_var.get().strip().lower() or Cadence.DAILY.value
        mode = self.mode_var.get().strip().lower() or HabitMode.TARGET.value

        if not name:
            messagebox.showerror("Missing habit name", "Please enter a habit name.")
            return

        target_periods = 1
        if mode == HabitMode.TARGET.value:
            try:
                target_periods = int(self.target_periods_var.get())
                if target_periods < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid target", "Target periods must be a number 1 or higher.")
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
            section=section,
            cadence=cadence,
            mode=mode,
            target_periods=target_periods,
            check_in_enabled=check_in_enabled,
            check_in_interval_hours=interval_hours,
        )
        self.store.save()

        self.name_var.set("")
        self.target_periods_var.set("30")
        self.check_in_var.set(False)
        self.interval_hours_var.set("2")
        self._toggle_target_state()
        self._toggle_interval_state()
        self._refresh_section_choices()

        self._render_cards()
        self._set_status(f"Added habit: {habit.name} in section {habit.section}.")

    def _get_habit(self, habit_id: str) -> Optional[Habit]:
        return self.store.get_habit(habit_id)

    def _mark_current_period_done(self, habit_id: str) -> None:
        habit = self._get_habit(habit_id)
        if habit is None:
            return

        message = habit.mark_period_complete(date.today())
        self.store.save()
        self._render_cards()
        self._set_status(f"{habit.name}: {message}")

    def _restart_habit(self, habit_id: str) -> None:
        habit = self._get_habit(habit_id)
        if habit is None:
            return

        action_text = "Break and restart" if habit.mode == HabitMode.TARGET.value else "Start a fresh run"
        proceed = messagebox.askyesno(
            "Restart run?",
            (
                f"{action_text} for '{habit.name}'?\n"
                "Your previous run history will be preserved."
            ),
        )
        if not proceed:
            return

        reason = "Manual reset" if habit.mode == HabitMode.TARGET.value else "Started new open-ended run"
        message = habit.break_and_restart(reason)
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

    def _cadence_label(self, cadence: str) -> str:
        if cadence == Cadence.WEEKLY.value:
            return "Week"
        if cadence == Cadence.MONTHLY.value:
            return "Month"
        return "Day"

    def _render_period_boxes(self, parent: ttk.Frame, habit: Habit, row_index: int) -> None:
        box_frame = tk.Frame(parent, background="#fcfdf9")
        box_frame.grid(row=row_index, column=0, sticky="w", pady=(6, 2))

        colors = {
            "done": "#5fbf72",
            "missed": "#e06d6d",
            "pending": "#d4dccf",
        }

        boxes = habit.progress_boxes(date.today())
        label_width = 4 if habit.cadence == Cadence.MONTHLY.value else 3
        max_per_row = 15

        for idx, box in enumerate(boxes):
            row_index = idx // max_per_row
            col_index = idx % max_per_row
            status = box.get("status", "pending")
            tk.Label(
                box_frame,
                text=box.get("label", ""),
                width=label_width,
                bg=colors.get(status, colors["pending"]),
                fg="#18271e",
                font=("Avenir Next", 9, "bold"),
                padx=1,
                pady=3,
            ).grid(row=row_index, column=col_index, padx=2, pady=2, sticky="nsew")

    def _render_habit_card(self, parent: ttk.Frame, habit: Habit, row_index: int) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=(14, 12, 14, 12))
        card.grid(row=row_index, column=0, sticky="ew", pady=6)
        card.columnconfigure(0, weight=1)

        header = ttk.Frame(card, style="Card.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        cadence_title = habit.cadence.title()
        mode_title = "Open-ended" if habit.mode == HabitMode.OPEN_ENDED.value else "Target"

        ttk.Label(header, text=habit.name, style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text=f"{cadence_title} | {mode_title}",
            style="Pill.TLabel",
        ).grid(row=0, column=1, sticky="e")

        current, target = habit.current_progress()
        unit = habit.unit_label()
        if habit.mode == HabitMode.TARGET.value:
            progress_text = f"Current run: {current}/{target} {unit}s"
        else:
            progress_text = f"Open-ended run completions: {current} {unit}s"

        ttk.Label(card, text=progress_text, style="CardMeta.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 2))

        stats_text = (
            f"Best run: {habit.best_run_periods()} {unit}s   "
            f"Completed runs: {habit.completed_runs_count()}   "
            f"Broken runs: {habit.broken_runs_count()}"
        )
        ttk.Label(card, text=stats_text, style="CardMeta.TLabel").grid(row=2, column=0, sticky="w")

        self._render_period_boxes(card, habit, 3)

        if habit.check_in_enabled:
            ttk.Label(
                card,
                text=f"Next check-in: {self._format_due_text(habit)}",
                style="CardMeta.TLabel",
            ).grid(row=4, column=0, sticky="w", pady=(6, 0))
            controls_row = 5
        else:
            controls_row = 4

        recent_runs = habit.recent_runs(limit=2)
        if recent_runs:
            summary_parts = []
            for run in recent_runs:
                ended_label = self._format_stamp(run.ended_at)
                target_text = f"/{run.target_periods}" if run.target_periods > 0 else ""
                summary_parts.append(
                    f"{run.status}: {run.completed_count}{target_text} {unit}s (ended {ended_label})"
                )
            ttk.Label(
                card,
                text="Recent: " + " | ".join(summary_parts),
                style="CardMeta.TLabel",
            ).grid(row=controls_row, column=0, sticky="w", pady=(6, 0))
            controls_row += 1

        controls = ttk.Frame(card, style="Card.TFrame")
        controls.grid(row=controls_row, column=0, sticky="w", pady=(8, 0))

        mark_text = f"Mark {self._cadence_label(habit.cadence)} Done"
        ttk.Button(
            controls,
            text=mark_text,
            command=lambda selected_id=habit.id: self._mark_current_period_done(selected_id),
        ).pack(side="left", padx=(0, 8))

        reset_text = "Break + Restart" if habit.mode == HabitMode.TARGET.value else "Start New Run"
        ttk.Button(
            controls,
            text=reset_text,
            command=lambda selected_id=habit.id: self._restart_habit(selected_id),
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            controls,
            text="History",
            command=lambda selected_id=habit.id: self._show_history(selected_id),
        ).pack(side="left", padx=(0, 8))

        if habit.check_in_enabled:
            ttk.Button(
                controls,
                text="Yes",
                command=lambda selected_id=habit.id: self._quick_check_in(selected_id, True),
            ).pack(side="left", padx=(0, 6))
            ttk.Button(
                controls,
                text="No",
                command=lambda selected_id=habit.id: self._quick_check_in(selected_id, False),
            ).pack(side="left")

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

        grouped: dict[str, list[Habit]] = defaultdict(list)
        for habit in self.store.habits:
            grouped[habit.section.strip() or "General"].append(habit)

        section_row = 0
        for section_name in sorted(grouped.keys()):
            section_frame = ttk.Frame(self.cards_frame, style="Root.TFrame")
            section_frame.grid(row=section_row, column=0, sticky="ew", pady=(2, 10))
            section_frame.columnconfigure(0, weight=1)

            ttk.Label(section_frame, text=section_name, style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(4, 2))
            habits = grouped[section_name]
            habits.sort(key=lambda item: item.name.lower())
            for idx, habit in enumerate(habits, start=1):
                self._render_habit_card(section_frame, habit, idx)

            section_row += 1

    def _show_history(self, habit_id: str) -> None:
        habit = self._get_habit(habit_id)
        if habit is None:
            return

        window = tk.Toplevel(self.root)
        window.title(f"History - {habit.name}")
        window.geometry("820x560")

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

        target_label = str(habit.target_periods) if habit.mode == HabitMode.TARGET.value else "open-ended"
        lines = [
            f"Habit: {habit.name}",
            f"Section: {habit.section}",
            f"Cadence: {habit.cadence}",
            f"Mode: {habit.mode}",
            f"Target: {target_label}",
            f"Created: {self._format_stamp(habit.created_at)}",
            "",
            "Runs:",
        ]

        unit = habit.unit_label()
        runs = list(habit.runs)
        runs.sort(key=lambda item: item.started_at, reverse=True)
        for idx, run in enumerate(runs, start=1):
            target_text = f"/{run.target_periods}" if run.target_periods > 0 else ""
            lines.append(
                f"{idx}. {run.status.upper()} | {run.completed_count}{target_text} {unit}s | "
                f"start {self._format_stamp(run.started_at)} | end {self._format_stamp(run.ended_at)}"
            )
            if run.break_reason:
                lines.append(f"   reason: {run.break_reason}")

        lines.extend(["", "Timed check-ins:"])
        if not habit.check_ins:
            lines.append("No check-ins yet.")
        else:
            for check in habit.check_ins[-100:]:
                answer_label = "yes" if check.answer else "no"
                lines.append(f"- {self._format_stamp(check.timestamp)} -> {answer_label}")

        text.insert("1.0", "\n".join(lines))
        text.configure(state="disabled")

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

    def _prompt_due_check_ins(self) -> bool:
        due_habits = [habit for habit in self.store.habits if habit.check_in_due(datetime.now())]
        if not due_habits:
            return False

        changed = False
        for habit in due_habits:
            self._send_macos_notification(
                "Habit Pulse",
                f"Still going strong with {habit.name}?",
            )

            answer = messagebox.askyesnocancel(
                "Still going strong?",
                (
                    f"Still going strong with '{habit.name}'?\n\n"
                    "Yes: keep going\n"
                    "No: record break/reset based on habit type\n"
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
