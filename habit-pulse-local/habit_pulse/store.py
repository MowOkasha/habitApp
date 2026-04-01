from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import AppSettings, DayJournalPage, FocusQuestion, Habit, TodoItem


DEFAULT_STORAGE_FILE = (
    Path.home() / "Library" / "Application Support" / "HabitPulseLocal" / "habits.json"
)


class HabitStore:
    def __init__(self, storage_file: Optional[Path] = None) -> None:
        self.storage_file = storage_file or DEFAULT_STORAGE_FILE
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)

        self.habits: list[Habit] = []
        self.questions: list[FocusQuestion] = []
        self.day_journals: list[DayJournalPage] = []
        self.todos: list[TodoItem] = []
        self.sections: list[str] = ["General"]
        self.settings: AppSettings = AppSettings()

    def load(self) -> None:
        if not self.storage_file.exists():
            self.habits = []
            self.questions = []
            self.day_journals = []
            self.todos = []
            self.sections = ["General"]
            self.settings = AppSettings()
            return

        raw_text = self.storage_file.read_text(encoding="utf-8")
        if not raw_text.strip():
            self.habits = []
            self.questions = []
            self.day_journals = []
            self.todos = []
            self.sections = ["General"]
            self.settings = AppSettings()
            return

        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            self.habits = []
            self.questions = []
            self.day_journals = []
            self.todos = []
            self.sections = ["General"]
            self.settings = AppSettings()
            return

        habits_payload = payload.get("habits", [])
        self.habits = [Habit.from_dict(item) for item in habits_payload]

        questions_payload = payload.get("questions", [])
        self.questions = [FocusQuestion.from_dict(item) for item in questions_payload]

        day_journals_payload = payload.get("day_journals", [])
        self.day_journals = [DayJournalPage.from_dict(item) for item in day_journals_payload]

        todos_payload = payload.get("todos", [])
        self.todos = [TodoItem.from_dict(item) for item in todos_payload]

        sections_payload = payload.get("sections", [])
        normalized_sections = [item.strip() for item in sections_payload if str(item).strip()]
        if not normalized_sections:
            normalized_sections = [habit.section for habit in self.habits if habit.section.strip()]
            normalized_sections.extend([todo.section for todo in self.todos if todo.section.strip()])
        if "General" not in normalized_sections:
            normalized_sections.append("General")
        self.sections = sorted(set(normalized_sections))

        self.settings = AppSettings.from_dict(payload.get("settings"))

    def save(self) -> None:
        payload = {
            "settings": self.settings.to_dict(),
            "sections": self.list_sections(),
            "habits": [habit.to_dict() for habit in self.habits],
            "questions": [question.to_dict() for question in self.questions],
            "day_journals": [page.to_dict() for page in self.day_journals],
            "todos": [todo.to_dict() for todo in self.todos],
        }
        temp_file = self.storage_file.with_suffix(".tmp")
        temp_file.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        temp_file.replace(self.storage_file)

    def list_sections(self) -> list[str]:
        combined = set(self.sections)
        for habit in self.habits:
            section = habit.section.strip() or "General"
            combined.add(section)
        for todo in self.todos:
            section = todo.section.strip() or "General"
            combined.add(section)
        if "General" not in combined:
            combined.add("General")
        return sorted(combined)

    def add_section(self, name: str) -> str:
        normalized = name.strip() or "General"
        if normalized not in self.sections:
            self.sections.append(normalized)
            self.sections.sort()
        return normalized

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
        normalized_section = self.add_section(section)
        habit = Habit.create(
            name=name,
            section=normalized_section,
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

    def update_habit(
        self,
        habit_id: str,
        *,
        name: str,
        section: str,
        cadence: str,
        mode: str,
        target_periods: int,
        check_in_enabled: bool,
        check_in_interval_hours: int,
    ) -> Optional[Habit]:
        habit = self.get_habit(habit_id)
        if habit is None:
            return None

        normalized_section = self.add_section(section)
        habit.reconfigure(
            name=name,
            section=normalized_section,
            cadence=cadence,
            mode=mode,
            target_periods=target_periods,
            check_in_enabled=check_in_enabled,
            check_in_interval_hours=check_in_interval_hours,
        )
        return habit

    def delete_habit(self, habit_id: str) -> bool:
        initial_count = len(self.habits)
        self.habits = [habit for habit in self.habits if habit.id != habit_id]
        return len(self.habits) != initial_count

    def sync_for_missed_days(self) -> bool:
        changed = False
        for habit in self.habits:
            if habit.sync_for_missed_periods():
                changed = True
        if self.sync_todo_rollover():
            changed = True
        return changed

    def add_question(
        self,
        *,
        text: str,
        cadence: str,
        times_per_period: int,
        video_path: Optional[str],
    ) -> FocusQuestion:
        question = FocusQuestion.create(
            text=text,
            cadence=cadence,
            times_per_period=times_per_period,
            video_path=video_path,
        )
        self.questions.append(question)
        return question

    def get_question(self, question_id: str) -> Optional[FocusQuestion]:
        for question in self.questions:
            if question.id == question_id:
                return question
        return None

    def update_question(
        self,
        question_id: str,
        *,
        text: str,
        cadence: str,
        times_per_period: int,
        video_path: Optional[str],
        enabled: bool,
    ) -> Optional[FocusQuestion]:
        question = self.get_question(question_id)
        if question is None:
            return None

        question.text = text.strip()
        question.cadence = cadence.strip().lower() or question.cadence
        question.times_per_period = max(1, int(times_per_period))
        question.video_path = (video_path or "").strip() or None
        question.enabled = enabled
        question.schedule_next(datetime.now())
        return question

    def toggle_question_enabled(self, question_id: str) -> Optional[FocusQuestion]:
        question = self.get_question(question_id)
        if question is None:
            return None
        question.enabled = not question.enabled
        question.schedule_next(datetime.now())
        return question

    def delete_question(self, question_id: str) -> bool:
        initial_count = len(self.questions)
        self.questions = [question for question in self.questions if question.id != question_id]
        return len(self.questions) != initial_count

    def due_questions(self, now_value: Optional[datetime] = None) -> list[FocusQuestion]:
        stamp = now_value or datetime.now()
        return [question for question in self.questions if question.is_due(stamp)]

    def set_dopamine_video_path(self, path: Optional[str]) -> None:
        self.settings.dopamine_video_path = (path or "").strip() or None

    def save_day_journal_page(self, day: str, note: str) -> DayJournalPage:
        normalized_day = day.strip()
        page = self.get_day_journal_page(normalized_day)
        if page is None:
            page = DayJournalPage.create(day=normalized_day, note=note)
            self.day_journals.append(page)
        else:
            page.note = note
            page.updated_at = datetime.now().isoformat(timespec="seconds")
        self.day_journals.sort(key=lambda item: item.day)
        return page

    def get_day_journal_page(self, day: str) -> Optional[DayJournalPage]:
        for page in self.day_journals:
            if page.day == day:
                return page
        return None

    def list_day_journal_days(self) -> list[str]:
        return sorted({page.day for page in self.day_journals})

    def add_todo(self, *, section: str, text: str) -> TodoItem:
        normalized_section = self.add_section(section)
        todo = TodoItem.create(section=normalized_section, text=text)
        self.todos.append(todo)
        return todo

    def get_todo(self, todo_id: str) -> Optional[TodoItem]:
        for todo in self.todos:
            if todo.id == todo_id:
                return todo
        return None

    def toggle_todo_done(self, todo_id: str) -> Optional[TodoItem]:
        todo = self.get_todo(todo_id)
        if todo is None:
            return None
        if todo.is_completed():
            todo.undo_done()
        else:
            todo.mark_done()
        return todo

    def undo_todo_done(self, todo_id: str) -> Optional[TodoItem]:
        todo = self.get_todo(todo_id)
        if todo is None:
            return None
        todo.undo_done()
        return todo

    def delete_todo(self, todo_id: str) -> bool:
        initial_count = len(self.todos)
        self.todos = [todo for todo in self.todos if todo.id != todo_id]
        return len(self.todos) != initial_count

    def sync_todo_rollover(self, now_value: Optional[datetime] = None) -> bool:
        changed = False
        stamp = now_value or datetime.now()
        for todo in self.todos:
            if todo.archive_if_due(stamp):
                changed = True
        return changed

    def active_todos(self) -> list[TodoItem]:
        return [todo for todo in self.todos if not todo.archived]

    def done_todos(self) -> list[TodoItem]:
        return [todo for todo in self.todos if todo.archived]
