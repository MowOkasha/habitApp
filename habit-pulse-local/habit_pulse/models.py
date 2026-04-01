from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional
from uuid import uuid4


def now_local() -> datetime:
    return datetime.now()


def dt_to_str(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def str_to_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def date_to_str(value: date) -> str:
    return value.isoformat()


def str_to_date(value: str) -> date:
    return date.fromisoformat(value)


class RunStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    BROKEN = "broken"


class Cadence(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class HabitMode(str, Enum):
    TARGET = "target"
    OPEN_ENDED = "open-ended"


class QuestionCadence(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


def parse_cadence(value: Optional[str]) -> Cadence:
    if not value:
        return Cadence.DAILY
    normalized = value.strip().lower()
    try:
        return Cadence(normalized)
    except ValueError:
        return Cadence.DAILY


def parse_mode(value: Optional[str]) -> HabitMode:
    if not value:
        return HabitMode.TARGET
    normalized = value.strip().lower()
    if normalized in {"open", "open_ended"}:
        normalized = HabitMode.OPEN_ENDED.value
    try:
        return HabitMode(normalized)
    except ValueError:
        return HabitMode.TARGET


def parse_question_cadence(value: Optional[str]) -> QuestionCadence:
    if not value:
        return QuestionCadence.DAILY
    normalized = value.strip().lower()
    try:
        return QuestionCadence(normalized)
    except ValueError:
        return QuestionCadence.DAILY


def cadence_unit(cadence: Cadence) -> str:
    if cadence == Cadence.WEEKLY:
        return "week"
    if cadence == Cadence.MONTHLY:
        return "month"
    return "day"


def period_key_for_date(day_value: date, cadence: Cadence) -> str:
    if cadence == Cadence.WEEKLY:
        year_value, week_value, _ = day_value.isocalendar()
        return f"{year_value:04d}-W{week_value:02d}"
    if cadence == Cadence.MONTHLY:
        return f"{day_value.year:04d}-{day_value.month:02d}"
    return date_to_str(day_value)


def period_index_from_key(period_key: str, cadence: Cadence) -> int:
    if cadence == Cadence.WEEKLY:
        year_text, week_text = period_key.split("-W")
        monday = date.fromisocalendar(int(year_text), int(week_text), 1)
        return monday.toordinal()
    if cadence == Cadence.MONTHLY:
        year_text, month_text = period_key.split("-")
        return int(year_text) * 12 + int(month_text)
    return str_to_date(period_key).toordinal()


def period_key_from_index(index: int, cadence: Cadence) -> str:
    if cadence == Cadence.WEEKLY:
        monday = date.fromordinal(index)
        year_value, week_value, _ = monday.isocalendar()
        return f"{year_value:04d}-W{week_value:02d}"
    if cadence == Cadence.MONTHLY:
        year_value = index // 12
        month_value = index % 12
        if month_value == 0:
            year_value -= 1
            month_value = 12
        return f"{year_value:04d}-{month_value:02d}"
    return date.fromordinal(index).isoformat()


def period_key_shift(period_key: str, cadence: Cadence, offset: int) -> str:
    if offset == 0:
        return period_key

    if cadence == Cadence.WEEKLY:
        year_text, week_text = period_key.split("-W")
        monday = date.fromisocalendar(int(year_text), int(week_text), 1)
        moved = monday + timedelta(weeks=offset)
        return period_key_for_date(moved, cadence)

    if cadence == Cadence.MONTHLY:
        year_text, month_text = period_key.split("-")
        year_value = int(year_text)
        month_value = int(month_text)
        index = year_value * 12 + month_value + offset
        return period_key_from_index(index, cadence)

    day_value = str_to_date(period_key)
    moved = day_value + timedelta(days=offset)
    return period_key_for_date(moved, cadence)


def period_distance(current_key: str, previous_key: str, cadence: Cadence) -> int:
    current_index = period_index_from_key(current_key, cadence)
    previous_index = period_index_from_key(previous_key, cadence)
    if cadence == Cadence.WEEKLY:
        return (current_index - previous_index) // 7
    return current_index - previous_index


def period_label(period_key: str, cadence: Cadence) -> str:
    if cadence == Cadence.WEEKLY:
        return period_key.split("-W")[1]
    if cadence == Cadence.MONTHLY:
        year_text, month_text = period_key.split("-")
        month_start = date(int(year_text), int(month_text), 1)
        return month_start.strftime("%b")
    return period_key[-2:]


@dataclass
class CheckInRecord:
    timestamp: str
    answer: bool

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "answer": self.answer,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "CheckInRecord":
        return cls(
            timestamp=payload["timestamp"],
            answer=bool(payload["answer"]),
        )


@dataclass
class HabitRun:
    id: str
    started_at: str
    target_periods: int
    status: str = RunStatus.ACTIVE.value
    completed_periods: list[str] = field(default_factory=list)
    ended_at: Optional[str] = None
    break_reason: Optional[str] = None

    @property
    def completed_count(self) -> int:
        return len(set(self.completed_periods))

    def add_completion(self, period_key: str) -> bool:
        if period_key in self.completed_periods:
            return False
        self.completed_periods.append(period_key)
        self.completed_periods.sort()
        return True

    def last_completed_period(self, cadence: Cadence) -> Optional[str]:
        if not self.completed_periods:
            return None
        return max(
            self.completed_periods,
            key=lambda item: period_index_from_key(item, cadence),
        )

    def finalize(
        self,
        status: RunStatus,
        *,
        ended_at: Optional[datetime] = None,
        reason: Optional[str] = None,
    ) -> None:
        self.status = status.value
        self.ended_at = dt_to_str(ended_at or now_local())
        self.break_reason = reason

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "started_at": self.started_at,
            "target_periods": self.target_periods,
            "status": self.status,
            "completed_periods": self.completed_periods,
            "ended_at": self.ended_at,
            "break_reason": self.break_reason,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "HabitRun":
        target_periods = int(payload.get("target_periods", payload.get("target_days", 30)))
        completed_periods = list(payload.get("completed_periods", payload.get("completed_dates", [])))
        return cls(
            id=payload["id"],
            started_at=payload["started_at"],
            target_periods=max(0, target_periods),
            status=payload.get("status", RunStatus.ACTIVE.value),
            completed_periods=completed_periods,
            ended_at=payload.get("ended_at"),
            break_reason=payload.get("break_reason"),
        )


@dataclass
class Habit:
    id: str
    name: str
    section: str
    created_at: str
    cadence: str
    mode: str
    target_periods: int
    check_in_enabled: bool = False
    check_in_interval_hours: int = 2
    next_check_in_at: Optional[str] = None
    runs: list[HabitRun] = field(default_factory=list)
    check_ins: list[CheckInRecord] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        name: str,
        section: str,
        cadence: str,
        mode: str,
        target_periods: int,
        *,
        check_in_enabled: bool = False,
        check_in_interval_hours: int = 2,
    ) -> "Habit":
        created = now_local()
        cadence_value = parse_cadence(cadence)
        mode_value = parse_mode(mode)
        habit = cls(
            id=str(uuid4()),
            name=name.strip(),
            section=section.strip() or "General",
            created_at=dt_to_str(created),
            cadence=cadence_value.value,
            mode=mode_value.value,
            target_periods=max(1, target_periods),
            check_in_enabled=check_in_enabled,
            check_in_interval_hours=max(1, check_in_interval_hours),
            next_check_in_at=None,
            runs=[],
            check_ins=[],
        )
        habit._start_new_run(created)
        if habit.check_in_enabled:
            habit.schedule_next_check_in(created)
        return habit

    def cadence_enum(self) -> Cadence:
        return parse_cadence(self.cadence)

    def mode_enum(self) -> HabitMode:
        return parse_mode(self.mode)

    def unit_label(self) -> str:
        return cadence_unit(self.cadence_enum())

    def _start_new_run(self, at_time: Optional[datetime] = None) -> HabitRun:
        stamp = at_time or now_local()
        run = HabitRun(
            id=str(uuid4()),
            started_at=dt_to_str(stamp),
            target_periods=self.target_periods if self.mode_enum() == HabitMode.TARGET else 0,
            status=RunStatus.ACTIVE.value,
            completed_periods=[],
            ended_at=None,
        )
        self.runs.append(run)
        return run

    def active_run(self) -> Optional[HabitRun]:
        for run in reversed(self.runs):
            if run.status == RunStatus.ACTIVE.value:
                return run
        return None

    def ensure_active_run(self) -> HabitRun:
        active = self.active_run()
        if active is not None:
            return active
        return self._start_new_run(now_local())

    def _finish_active_run(
        self,
        status: RunStatus,
        *,
        reason: Optional[str] = None,
        at_time: Optional[datetime] = None,
    ) -> None:
        active = self.active_run()
        if active is None:
            return
        active.finalize(status=status, ended_at=at_time, reason=reason)

    def current_period_key(self, reference_date: Optional[date] = None) -> str:
        target_date = reference_date or date.today()
        return period_key_for_date(target_date, self.cadence_enum())

    def sync_for_missed_periods(self, reference_date: Optional[date] = None) -> bool:
        if self.mode_enum() == HabitMode.OPEN_ENDED:
            return False

        active = self.active_run()
        if active is None:
            return False

        cadence = self.cadence_enum()
        last_period = active.last_completed_period(cadence)
        if not last_period:
            return False

        current_period = self.current_period_key(reference_date)
        gap = period_distance(current_period, last_period, cadence)
        if gap <= 1:
            return False

        self._finish_active_run(
            RunStatus.BROKEN,
            reason=f"Missed {gap - 1} {self.unit_label()}(s)",
        )
        self._start_new_run(now_local())
        if self.check_in_enabled:
            self.schedule_next_check_in(now_local())
        return True

    def sync_for_missed_days(self, today: Optional[date] = None) -> bool:
        return self.sync_for_missed_periods(today)

    def mark_period_complete(self, reference_date: Optional[date] = None) -> str:
        target_date = reference_date or date.today()
        cadence = self.cadence_enum()
        current_period = period_key_for_date(target_date, cadence)

        if self.mode_enum() == HabitMode.TARGET:
            self.sync_for_missed_periods(target_date)

        active = self.ensure_active_run()
        last_period = active.last_completed_period(cadence)
        if last_period:
            gap = period_distance(current_period, last_period, cadence)
            if gap < 0:
                return "Cannot log a period earlier than your latest logged period."
            if self.mode_enum() == HabitMode.TARGET and gap > 1:
                self._finish_active_run(
                    RunStatus.BROKEN,
                    reason=f"Missed {gap - 1} {self.unit_label()}(s)",
                )
                active = self._start_new_run(now_local())

        added = active.add_completion(current_period)
        if not added:
            return f"This {self.unit_label()} is already marked complete."

        if self.mode_enum() == HabitMode.TARGET and active.completed_count >= self.target_periods:
            reached = self.target_periods
            self._finish_active_run(
                RunStatus.COMPLETED,
                reason="Target reached",
            )
            self._start_new_run(now_local())
            if self.check_in_enabled:
                self.schedule_next_check_in(now_local())
            return f"Excellent. You completed a full {reached}-{self.unit_label()} run."

        if self.mode_enum() == HabitMode.OPEN_ENDED:
            return f"Logged this {self.unit_label()} for an open-ended habit."

        active_count = active.completed_count
        return f"Logged {active_count}/{self.target_periods} {self.unit_label()}s."

    def break_and_restart(
        self,
        reason: str = "Manual reset",
        *,
        when: Optional[datetime] = None,
    ) -> str:
        now_value = when or now_local()
        self.ensure_active_run()
        self._finish_active_run(
            RunStatus.BROKEN,
            reason=reason,
            at_time=now_value,
        )
        self._start_new_run(now_value)
        if self.check_in_enabled:
            self.schedule_next_check_in(now_value)
        return "Run restarted. Previous run is saved in history."

    def reconfigure(
        self,
        *,
        name: str,
        section: str,
        cadence: str,
        mode: str,
        target_periods: int,
        check_in_enabled: bool,
        check_in_interval_hours: int,
    ) -> None:
        new_cadence = parse_cadence(cadence)
        new_mode = parse_mode(mode)
        normalized_target = max(1, int(target_periods))

        cadence_changed = new_cadence.value != self.cadence
        mode_changed = new_mode.value != self.mode
        target_changed = normalized_target != self.target_periods

        self.name = name.strip() or self.name
        self.section = section.strip() or "General"
        self.cadence = new_cadence.value
        self.mode = new_mode.value
        self.target_periods = normalized_target
        self.check_in_enabled = check_in_enabled
        self.check_in_interval_hours = max(1, int(check_in_interval_hours))

        active = self.ensure_active_run()

        if cadence_changed or mode_changed:
            self.break_and_restart("Configuration changed")
            active = self.ensure_active_run()

        if target_changed and self.mode_enum() == HabitMode.TARGET:
            active.target_periods = self.target_periods

        if not self.check_in_enabled:
            self.next_check_in_at = None
        elif self.next_check_in_at is None:
            self.schedule_next_check_in(now_local())

    def schedule_next_check_in(self, reference: Optional[datetime] = None) -> None:
        if not self.check_in_enabled:
            self.next_check_in_at = None
            return
        base = reference or now_local()
        next_due = base + timedelta(hours=max(1, self.check_in_interval_hours))
        self.next_check_in_at = dt_to_str(next_due)

    def check_in_due(self, now_value: Optional[datetime] = None) -> bool:
        if not self.check_in_enabled or not self.next_check_in_at:
            return False
        current = now_value or now_local()
        return str_to_dt(self.next_check_in_at) <= current

    def snooze_check_in(
        self,
        minutes: int = 10,
        *,
        when: Optional[datetime] = None,
    ) -> None:
        base = when or now_local()
        self.next_check_in_at = dt_to_str(base + timedelta(minutes=max(1, minutes)))

    def respond_check_in(
        self,
        answer: bool,
        *,
        when: Optional[datetime] = None,
    ) -> str:
        now_value = when or now_local()
        self.check_ins.append(
            CheckInRecord(
                timestamp=dt_to_str(now_value),
                answer=answer,
            )
        )

        if answer:
            self.schedule_next_check_in(now_value)
            return "Check-in recorded: yes."

        if self.mode_enum() == HabitMode.TARGET:
            self.break_and_restart("Check-in answered no", when=now_value)
            return "Check-in recorded: no. Run restarted and history preserved."

        self.schedule_next_check_in(now_value)
        return "Check-in recorded: no. Open-ended habit was not reset."

    def best_run_periods(self) -> int:
        if not self.runs:
            return 0
        return max(run.completed_count for run in self.runs)

    def broken_runs_count(self) -> int:
        return sum(1 for run in self.runs if run.status == RunStatus.BROKEN.value)

    def completed_runs_count(self) -> int:
        return sum(1 for run in self.runs if run.status == RunStatus.COMPLETED.value)

    def current_progress(self) -> tuple[int, int]:
        active = self.ensure_active_run()
        if self.mode_enum() == HabitMode.OPEN_ENDED:
            return active.completed_count, 0
        return active.completed_count, self.target_periods

    def recent_runs(self, limit: int = 5) -> list[HabitRun]:
        historical = [run for run in self.runs if run.status != RunStatus.ACTIVE.value]
        historical.sort(key=lambda item: item.started_at, reverse=True)
        return historical[:limit]

    def _open_window_size(self) -> int:
        cadence = self.cadence_enum()
        if cadence == Cadence.WEEKLY:
            return 12
        if cadence == Cadence.MONTHLY:
            return 12
        return 14

    def progress_boxes(
        self,
        reference_date: Optional[date] = None,
        *,
        max_boxes: Optional[int] = None,
    ) -> list[dict]:
        active = self.ensure_active_run()
        cadence = self.cadence_enum()
        mode = self.mode_enum()

        current_key = self.current_period_key(reference_date)
        done_set = set(active.completed_periods)

        boxes: list[dict] = []
        if mode == HabitMode.TARGET:
            start_date = str_to_dt(active.started_at).date()
            start_key = period_key_for_date(start_date, cadence)
            total = max(1, self.target_periods)

            for offset in range(total):
                key = period_key_shift(start_key, cadence, offset)
                distance_from_current = period_distance(current_key, key, cadence)
                if key in done_set:
                    status = "done"
                elif distance_from_current > 0:
                    status = "missed"
                else:
                    status = "pending"

                boxes.append(
                    {
                        "key": key,
                        "label": str(offset + 1),
                        "status": status,
                    }
                )

            if max_boxes and len(boxes) > max_boxes:
                return boxes[-max_boxes:]
            return boxes

        window = self._open_window_size()
        if max_boxes:
            window = max(1, min(window, max_boxes))

        for offset in range(window - 1, -1, -1):
            key = period_key_shift(current_key, cadence, -offset)
            if key in done_set:
                status = "done"
            elif offset == 0:
                status = "pending"
            else:
                status = "missed"

            boxes.append(
                {
                    "key": key,
                    "label": period_label(key, cadence),
                    "status": status,
                }
            )
        return boxes

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "section": self.section,
            "created_at": self.created_at,
            "cadence": self.cadence,
            "mode": self.mode,
            "target_periods": self.target_periods,
            "check_in_enabled": self.check_in_enabled,
            "check_in_interval_hours": self.check_in_interval_hours,
            "next_check_in_at": self.next_check_in_at,
            "runs": [run.to_dict() for run in self.runs],
            "check_ins": [entry.to_dict() for entry in self.check_ins],
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "Habit":
        cadence_value = parse_cadence(payload.get("cadence", Cadence.DAILY.value))
        mode_value = parse_mode(payload.get("mode", HabitMode.TARGET.value))
        target_periods = int(payload.get("target_periods", payload.get("target_days", 30)))

        habit = cls(
            id=payload["id"],
            name=payload["name"],
            section=payload.get("section", "General") or "General",
            created_at=payload["created_at"],
            cadence=cadence_value.value,
            mode=mode_value.value,
            target_periods=max(1, target_periods),
            check_in_enabled=bool(payload.get("check_in_enabled", False)),
            check_in_interval_hours=max(1, int(payload.get("check_in_interval_hours", 2))),
            next_check_in_at=payload.get("next_check_in_at"),
            runs=[HabitRun.from_dict(item) for item in payload.get("runs", [])],
            check_ins=[CheckInRecord.from_dict(item) for item in payload.get("check_ins", [])],
        )
        if not habit.runs:
            habit._start_new_run(now_local())
        if habit.check_in_enabled and habit.next_check_in_at is None:
            habit.schedule_next_check_in(now_local())
        return habit


@dataclass
class FocusQuestion:
    id: str
    text: str
    cadence: str
    times_per_period: int
    video_path: Optional[str]
    next_prompt_at: Optional[str]
    enabled: bool = True
    created_at: str = field(default_factory=lambda: dt_to_str(now_local()))

    @classmethod
    def create(
        cls,
        text: str,
        cadence: str,
        times_per_period: int,
        video_path: Optional[str],
    ) -> "FocusQuestion":
        question = cls(
            id=str(uuid4()),
            text=text.strip(),
            cadence=parse_question_cadence(cadence).value,
            times_per_period=max(1, int(times_per_period)),
            video_path=(video_path or "").strip() or None,
            next_prompt_at=None,
            enabled=True,
            created_at=dt_to_str(now_local()),
        )
        question.schedule_next(now_local())
        return question

    def cadence_enum(self) -> QuestionCadence:
        return parse_question_cadence(self.cadence)

    def period_hours(self) -> int:
        if self.cadence_enum() == QuestionCadence.WEEKLY:
            return 24 * 7
        return 24

    def prompt_interval_hours(self) -> float:
        return max(1.0, self.period_hours() / max(1, self.times_per_period))

    def schedule_next(self, reference: Optional[datetime] = None) -> None:
        base = reference or now_local()
        self.next_prompt_at = dt_to_str(base + timedelta(hours=self.prompt_interval_hours()))

    def is_due(self, now_value: Optional[datetime] = None) -> bool:
        if not self.enabled or not self.next_prompt_at:
            return False
        current = now_value or now_local()
        return str_to_dt(self.next_prompt_at) <= current

    def record_answer(self, answer: bool, when: Optional[datetime] = None) -> None:
        _ = answer
        self.schedule_next(when or now_local())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "cadence": self.cadence,
            "times_per_period": self.times_per_period,
            "video_path": self.video_path,
            "next_prompt_at": self.next_prompt_at,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "FocusQuestion":
        question = cls(
            id=payload["id"],
            text=payload.get("text", "").strip(),
            cadence=parse_question_cadence(payload.get("cadence")).value,
            times_per_period=max(1, int(payload.get("times_per_period", 1))),
            video_path=(payload.get("video_path") or "").strip() or None,
            next_prompt_at=payload.get("next_prompt_at"),
            enabled=bool(payload.get("enabled", True)),
            created_at=payload.get("created_at", dt_to_str(now_local())),
        )
        if question.next_prompt_at is None:
            question.schedule_next(now_local())
        return question


@dataclass
class AppSettings:
    dopamine_video_path: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "dopamine_video_path": self.dopamine_video_path,
        }

    @classmethod
    def from_dict(cls, payload: Optional[dict]) -> "AppSettings":
        if not payload:
            return cls()
        return cls(
            dopamine_video_path=(payload.get("dopamine_video_path") or "").strip() or None,
        )
