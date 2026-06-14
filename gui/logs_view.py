"""View Logs dialog: a read-only tail view of the app's loguru log file.

The app logs (via loguru) to ``antenna_designer.log`` in the current working
directory (the repo root). This dialog shows the last ~500 lines of that file
in a read-only monospace text widget, with Refresh / Copy / Close actions.

Matches the style of the other ``gui/`` dialogs (see ``analysis_view.py``):
a ``ttk.Toplevel``, ``ScrolledText`` body, Escape-to-close + ``focus_set``,
and a Close button.
"""
from __future__ import annotations

from tkinter import BOTH, X, RIGHT, LEFT, TOP, BOTTOM
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as ttk
from ttkbootstrap.constants import SECONDARY, PRIMARY

from gui.constants import PAD_S, PAD_M

_TAIL_LINES = 500  # show only the last N lines so a huge log doesn't choke the widget


class LogsDialog:
    def __init__(self, parent, log_path="antenna_designer.log"):
        self.log_path = log_path

        self.win = ttk.Toplevel(parent)
        self.win.title("Logs")
        self.win.geometry("820x520")
        self.win.transient(parent)

        body = ttk.Frame(self.win, padding=PAD_S)
        body.pack(side=TOP, fill=BOTH, expand=True)

        self.txt = ScrolledText(body, font=("Consolas", 9), wrap="none")
        self.txt.pack(side=TOP, fill=BOTH, expand=True)

        btns = ttk.Frame(self.win, padding=PAD_M)
        btns.pack(side=BOTTOM, fill=X)
        ttk.Button(btns, text="Close", bootstyle=SECONDARY,
                   command=self.win.destroy).pack(side=RIGHT)
        ttk.Button(btns, text="Copy", bootstyle=SECONDARY,
                   command=self._copy).pack(side=RIGHT, padx=(0, PAD_S))
        ttk.Button(btns, text="Refresh", bootstyle=PRIMARY,
                   command=self._refresh).pack(side=LEFT)

        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.focus_set()
        self._refresh()

    def _read_log(self):
        """Return the last ~500 lines of the log, or a friendly fallback message."""
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception:
            return f"No log file found at {self.log_path}."
        if not lines:
            return f"No log file found at {self.log_path}."
        return "".join(lines[-_TAIL_LINES:])

    def _set_text(self, content):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", content)
        self.txt.configure(state="disabled")
        # Scroll to the bottom so the newest log entries are visible.
        self.txt.see("end")

    def _refresh(self):
        self._set_text(self._read_log())

    def _copy(self):
        try:
            shown = self.txt.get("1.0", "end-1c")
            self.win.clipboard_clear()
            self.win.clipboard_append(shown)
        except Exception:
            pass
