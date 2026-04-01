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
    target_days: int
    status: str = RunStatus.ACTIVE.value
    completed_dates: list[str] = field(default_factory=list)
    ended_at: Optional[str] = None
    break_reason: Optional[str] = None

    @property
    def completed_count(self) -> int:
        return len(set(self.completed_dates))

    @property
    def last_completed_day(self) -> Optional[date]:
        if not self.completed_dates:
            return None
        return max(str_to_date(day_text) for day_text in self.completed_dates)

    def add_completion_day(self, day_value: date) -> bool:
        text = date_to_str(day_value)
        if text in self.completed_dates:
            return False
        self.completed_dates.append(text)
        self.completed_dates.sort()
        return True

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
            "target_days": self.target_days,
            "status": self.status,
            "completed_dates": self.completed_dates,
            "ended_at": self.ended_at,
            "break_reason": self.break_reason,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "HabitRun":
        return cls(
            id=payload["id"],
            started_at=payload["started_at"],
            target_days=int(payload["target_days"]),
            status=payload.get("status", RunStatus.ACTIVE.value),
            completed_dates=list(payload.get("completed_dates", [])),
            ended_at=payload.get("ended_at"),
            break_reason=payload.get("break_reason"),
        )


@dataclass
class Habit:
    id: str
    name: str
    created_at: str
    target_days: int
    check_in_enabled: bool = False
    check_in_interval_hours: int = 2
    next_check_in_at: Optional[str] = None
    runs: list[HabitRun] = field(default_factory=list)
    check_ins: list[CheckInRecord] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        name: str,
        target_days: int,
        *,
        check_in_enabled: bool = False,
        check_in_interval_hours: int = 2,
    ) -> "Habit":
        created = now_local()
        habit = cls(
            id=str(uuid4()),
            name=name.strip(),
            created_at=dt_to_str(created),
            target_days=max(1, target_days),
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

    def _start_new_run(self, at_time: Optional[datetime] = None) -> HabitRun:
        stamp = at_time or now_local()
        run = HabitRun(
            id=str(uuid4()),
            started_at=dt_to_str(stamp),
            target_days=self.target_days,
            status=RunStatus.ACTIVE.value,
            completed_dates=[],
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

    def sync_for_missed_days(self, today: Optional[date] = None) -> bool:
        target_day = today or date.today()
        active = self.active_run()
        if active is None:
            return False
        last_day = active.last_completed_day
        if last_day is None:
            return False
        gap = (target_day - last_day).days
        if gap <= 1:
            return False
        self._finish_active_run(
            RunStatus.BROKEN,
            reason=f"Missed {gap - 1} day(s)",
        )
        self._start_new_run(now_local())
        if self.check_in_enabled:
            self.schedule_next_check_in(now_local())
        return True

    def mark_day_complete(self, day_value: Optional[date] = None) -> str:
        target_day = day_value or date.today()
        self.sync_for_missed_days(target_day)

        active = self.ensure_active_run()
        last_day = active.last_completed_day
        if last_day is not None and target_day < last_day:
            return "Cannot log a day earlier than your latest logged day."

        if last_day is not None:
            gap = (target_day - last_day).days
            if gap > 1:
                self._finish_active_run(
                    RunStatus.BROKEN,
                    reason=f"Missed {gap - 1} day(s)",
                )
                active = self._start_new_run(now_local())

        added = active.add_completion_day(target_day)
        if not added:
            return "Today was already marked complete."

        if active.completed_count >= active.target_days:
            reached = active.target_days
            self._finish_active_run(
                RunStatus.COMPLETED,
                reason="Target reached",
            )
            self._start_new_run(now_local())
            if self.check_in_enabled:
                self.schedule_next_check_in(now_local())
            return f"Great work. You completed a full {reached}-day run."

        return f"Logged day {active.completed_count}/{active.target_days}."

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
        return "Run broken and restarted. Previous run is saved in history."

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

        self.break_and_restart("Check-in answered no", when=now_value)
        return "Check-in recorded: no. Run restarted and history preserved."

    def best_run_days(self) -> int:
        if not self.runs:
            return 0
        return max(run.completed_count for run in self.runs)

    def broken_runs_count(self) -> int:
        return sum(1 for run in self.runs if run.status == RunStatus.BROKEN.value)

    def completed_runs_count(self) -> int:
        return sum(1 for run in self.runs if run.status == RunStatus.COMPLETED.value)

    def current_progress(self) -> tuple[int, int]:
        active = self.ensure_active_run()
        return active.completed_count, active.target_days

    def recent_runs(self, limit: int = 5) -> list[HabitRun]:
        historical = [run for run in self.runs if run.status != RunStatus.ACTIVE.value]
        historical.sort(key=lambda item: item.started_at, reverse=True)
        return historical[:limit]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "target_days": self.target_days,
            "check_in_enabled": self.check_in_enabled,
            "check_in_interval_hours": self.check_in_interval_hours,
            "next_check_in_at": self.next_check_in_at,
            "runs": [run.to_dict() for run in self.runs],
            "check_ins": [entry.to_dict() for entry in self.check_ins],
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "Habit":
        habit = cls(
            id=payload["id"],
            name=payload["name"],
            created_at=payload["created_at"],
            target_days=max(1, int(payload.get("target_days", 30))),
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
