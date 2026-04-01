from __future__ import annotations

import tkinter as tk

from habit_pulse import HabitPulseApp


def main() -> None:
    root = tk.Tk()
    HabitPulseApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
