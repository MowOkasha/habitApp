from setuptools import setup

APP = ["main.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "assets/HabitPulse.icns",
    "packages": ["habit_pulse"],
    "plist": {
        "CFBundleName": "Habit Pulse",
        "CFBundleDisplayName": "Habit Pulse",
        "CFBundleIdentifier": "local.habitpulse.app",
    },
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
)
