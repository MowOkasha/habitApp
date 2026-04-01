# Habit Pulse (Local Mac App)

Habit Pulse is a fully local desktop habit tracker for macOS. It stores all data on your machine and never uses the internet.

## What this app does

- Add habits with custom targets (for example, 30-day streaks).
- Track day-by-day progress in minimalist habit cards (boxes).
- Break and restart runs while preserving all previous failed and completed runs.
- Mark special habits for timed check-ins.
- Prompt every N hours (default 2): "Still going strong?" with Yes / No / Remind later.
- Keep permanent local history of runs and check-ins.

## Run on your Mac

1. Open Terminal.
2. Go to the project folder:

```bash
cd /Users/mabde/habit-pulse-local
```

3. Start the app:

```bash
python3 main.py
```

## Local data location

The app saves data to:

`~/Library/Application Support/HabitPulseLocal/habits.json`

Nothing is uploaded to any server.

## Notes

- Intel Macs are fully supported.
- Check-ins appear while the app is running.
- If you answer No for a timed check-in, the current run is broken and restarted, and your previous progress is kept in history.
