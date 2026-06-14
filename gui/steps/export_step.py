"""Step 5: export and save (delegates to the app)."""
from __future__ import annotations

from typing import Callable
from tkinter import X, StringVar
import ttkbootstrap as ttk
from ttkbootstrap.constants import PRIMARY, SUCCESS

from gui.session import DesignSession, EVT_GENERATED

from gui.constants import PAD_S, PAD_M


class ExportStep:
    def __init__(self, parent, session: DesignSession,
                 on_export: Callable[[str], None], on_save: Callable[[], None]):
        self.session = session
        self.frame = ttk.Frame(parent)

        self.filename = StringVar(value="antenna_design")
        box = ttk.LabelFrame(self.frame, text="Export", padding=PAD_M)
        box.pack(fill=X, pady=(0, PAD_M))
        ttk.Label(box, text="Filename").pack(anchor="w")
        ttk.Entry(box, textvariable=self.filename).pack(fill=X, pady=(0, PAD_S))
        row = ttk.Frame(box)
        row.pack(fill=X)
        for fmt in ("svg", "dxf", "pdf"):
            ttk.Button(row, text=fmt.upper(), bootstyle="secondary-outline",
                       command=lambda f=fmt: on_export(f)).pack(
                side="left", expand=True, fill=X, padx=PAD_S)

        ttk.Button(self.frame, text="Save to Library", bootstyle=SUCCESS,
                   command=on_save).pack(fill=X)

        self.hint = ttk.Label(self.frame, text="Generate a design before exporting.")
        self.hint.pack(anchor="w", pady=(PAD_M, 0))
        session.subscribe(self._refresh)

    def _refresh(self, event: str):
        if event == EVT_GENERATED and self.session.has_design:
            self.hint.configure(text="Ready to export.")
