# Habit Pulse (Local macOS App)

Habit Pulse is a fully local desktop habit tracker for macOS with sectioned habits, streak tracking, open-ended tracking, and timed check-ins.

## Features

- Add habits under sections/folders such as Work, Gym, Study, or custom sections.
- Support cadence by habit: daily, weekly, or monthly.
- Support two habit types:
	- target streak (example: 30-day streak)
	- open-ended tracking (no fixed end)
- Color grid boxes per habit:
	- green = done
	- red = missed
	- neutral = pending
- Timed check-ins for selected habits (default every 2 hours):
	- prompt asks "Still going strong?"
	- Yes / No / Remind in 10 minutes
- Native macOS notifications for due timed check-ins.
- Full local history of completed runs, broken runs, and check-in answers.

## Local data

All data is stored only on your Mac:

`~/Library/Application Support/HabitPulseLocal/habits.json`

No cloud sync and no internet calls by the app.

## Build and install as a normal macOS app

From Terminal:

```bash
cd /Users/mabde/habit-pulse-local
chmod +x build_and_install_app.sh
./build_and_install_app.sh
```

This builds a native `.app` bundle with an app icon and installs it to:

- `/Applications/Habit Pulse.app`
- fallback: `~/Applications/Habit Pulse.app` if system Applications is not writable.

## Run in development mode

```bash
cd /Users/mabde/habit-pulse-local
python3 main.py
```
