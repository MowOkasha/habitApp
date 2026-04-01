from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .models import Habit


DEFAULT_STORAGE_FILE = (
    Path.home() / "Library" / "Application Support" / "HabitPulseLocal" / "habits.json"
)


class HabitStore:
    def __init__(self, storage_file: Optional[Path] = None) -> None:
        self.storage_file = storage_file or DEFAULT_STORAGE_FILE
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.habits: list[Habit] = []

    def load(self) -> list[Habit]:
        if not self.storage_file.exists():
            self.habits = []
            return self.habits

        raw_text = self.storage_file.read_text(encoding="utf-8")
        if not raw_text.strip():
            self.habits = []
            return self.habits

        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            self.habits = []
            return self.habits

        habits_payload = payload.get("habits", [])
        self.habits = [Habit.from_dict(item) for item in habits_payload]
        return self.habits

    def save(self) -> None:
        payload = {
            "habits": [habit.to_dict() for habit in self.habits],
        }
        temp_file = self.storage_file.with_suffix(".tmp")
        temp_file.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        temp_file.replace(self.storage_file)

    def add_habit(
        self,
        name: str,
        section: str,
        cadence: str,
        mode: str,
        target_periods: int,
        *,
        check_in_enabled: bool,
        check_in_interval_hours: int,
    ) -> Habit:
        habit = Habit.create(
            name=name,
            section=section,
            cadence=cadence,
            mode=mode,
            target_periods=target_periods,
            check_in_enabled=check_in_enabled,
            check_in_interval_hours=check_in_interval_hours,
        )
        self.habits.append(habit)
        return habit

    def get_habit(self, habit_id: str) -> Optional[Habit]:
        for habit in self.habits:
            if habit.id == habit_id:
                return habit
        return None

    def sync_for_missed_days(self) -> bool:
        changed = False
        for habit in self.habits:
            if habit.sync_for_missed_periods():
                changed = True
        return changed

    def list_sections(self) -> list[str]:
        sections = {habit.section.strip() or "General" for habit in self.habits}
        if not sections:
            return ["General"]
        return sorted(sections)
