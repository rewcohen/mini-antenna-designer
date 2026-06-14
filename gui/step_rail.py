"""Persistent left step rail. Always visible, clickable, shows active step + help."""
from __future__ import annotations

from typing import Callable, List, Tuple
from tkinter import X, TOP, BOTH
import ttkbootstrap as ttk
from ttkbootstrap.constants import PRIMARY, SECONDARY

from gui.session import DesignSession, EVT_STEP, EVT_BAND, EVT_GENERATED

PAD_S, PAD_M = 4, 8

# (label, one-line help shown when active)
STEPS: List[Tuple[str, str]] = [
    ("1  Band", "Pick a frequency band, or define custom frequencies."),
    ("2  Board", "Set substrate size and material."),
    ("3  Trace", "Choose trace width and advanced meander options."),
    ("4  Generate", "Generate the antenna and review performance."),
    ("5  Export", "Export SVG/DXF/PDF or save to your library."),
]


class StepRail:
    """Vertical step buttons bound to ``session.active_step``."""

    def __init__(self, parent, session: DesignSession, on_select: Callable[[int], None]):
        self.session = session
        self.on_select = on_select
        self.frame = ttk.Frame(parent)
        self._buttons = []

        for i, (label, _help) in enumerate(STEPS):
            b = ttk.Button(self.frame, text=label, bootstyle=SECONDARY,
                           command=lambda i=i: self._select(i))
            b.pack(side=TOP, fill=X, pady=(0, PAD_S))
            self._buttons.append(b)

        self.help = ttk.Label(self.frame, text=STEPS[0][1], wraplength=130,
                              bootstyle=SECONDARY, justify="left")
        self.help.pack(side=TOP, fill=X, pady=(PAD_M, 0))

        session.subscribe(self._refresh)
        self._refresh(EVT_STEP)

    def _select(self, i: int):
        self.session.active_step = i
        self.session.notify(EVT_STEP)
        self.on_select(i)

    def _refresh(self, event: str):
        if event not in (EVT_STEP, EVT_BAND, EVT_GENERATED):
            return
        active = self.session.active_step
        for i, b in enumerate(self._buttons):
            done = self._is_done(i)
            mark = "✓ " if done else ""
            base = STEPS[i][0]
            b.configure(text=mark + base,
                        bootstyle=PRIMARY if i == active else SECONDARY)
        self.help.configure(text=STEPS[active][1])

    def _is_done(self, i: int) -> bool:
        s = self.session
        if i == 0:
            return s.band is not None or s.custom_freqs is not None
        if i in (1, 2):
            return s.band is not None or s.custom_freqs is not None
        if i == 3:
            return s.has_design
        if i == 4:
            return s.has_design
        return False
