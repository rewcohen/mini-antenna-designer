"""Step 4: generate the design (delegates the actual run to the app)."""
from __future__ import annotations

from typing import Callable
from tkinter import X, StringVar, DoubleVar
import ttkbootstrap as ttk
from ttkbootstrap.constants import PRIMARY, SECONDARY, DANGER

from gui.session import DesignSession, EVT_GENERATED, EVT_BAND

PAD_S, PAD_M = 4, 8


class GenerateStep:
    def __init__(self, parent, session: DesignSession,
                 on_generate: Callable[[], None], on_stop: Callable[[], None]):
        self.session = session
        self.frame = ttk.Frame(parent)

        self.summary = StringVar(value="Pick a band first.")
        ttk.Label(self.frame, textvariable=self.summary, wraplength=330,
                  bootstyle=SECONDARY, justify="left").pack(anchor="w", pady=(0, PAD_M))

        self.progress = DoubleVar(value=0.0)
        ttk.Progressbar(self.frame, variable=self.progress, maximum=100).pack(
            fill=X, pady=(0, PAD_M))

        btns = ttk.Frame(self.frame)
        btns.pack(fill=X)
        self.gen_btn = ttk.Button(btns, text="Generate Design", bootstyle=PRIMARY,
                                  command=on_generate)
        self.gen_btn.pack(side="left", expand=True, fill=X, padx=(0, PAD_S))
        ttk.Button(btns, text="Stop", bootstyle=DANGER, command=on_stop).pack(side="left")

        self.result = StringVar(value="")
        ttk.Label(self.frame, textvariable=self.result, wraplength=330,
                  justify="left").pack(anchor="w", pady=(PAD_M, 0))

        session.subscribe(self._refresh)
        self._refresh(EVT_BAND)

    def set_busy(self, busy: bool):
        self.gen_btn.configure(state="disabled" if busy else "normal")
        self.progress.set(40.0 if busy else (100.0 if self.session.has_design else 0.0))

    def _refresh(self, event: str):
        freqs = self.session.frequencies_mhz()
        name = self.session.band.name if self.session.band else None
        if freqs and name:
            self.summary.set(f"{name}: {freqs[0]:g}/{freqs[1]:g}/{freqs[2]:g} MHz"
                             f" on {self.session.substrate_width:g}×"
                             f"{self.session.substrate_height:g} in, "
                             f"{self.session.trace_width_mil:.0f} mil traces.")
        else:
            self.summary.set("Pick a band first.")
        if event == EVT_GENERATED and self.session.results:
            r = self.session.results
            self.result.set(f"Design: {r.get('design_type', '?')}  "
                            f"({'OK' if r.get('success') else 'check warnings'})")
            self.progress.set(100.0)
