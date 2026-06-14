"""Step 4: generate the design (delegates the actual run to the app).

Motion here conveys *state*, not decoration (product register): while the backend
thread runs we show an honest indeterminate "working" bar — generation has no real
percentage to report — then settle to a full bar with an ease-out tween once a design
lands. Set ``ANTENNA_REDUCED_MOTION=1`` to drop the tweens and jump between states.
"""
from __future__ import annotations

import os
from typing import Callable
from tkinter import X, StringVar, DoubleVar
import ttkbootstrap as ttk
from ttkbootstrap.constants import PRIMARY, DANGER, SUCCESS

from gui.session import DesignSession, EVT_GENERATED, EVT_BAND

from gui.constants import PAD_S, PAD_M

# Honest opt-out for motion sensitivity / headless renders (no OS prefers-reduced-
# motion query in Tk). Any value other than ""/"0"/"false" disables the tweens.
REDUCED_MOTION = os.environ.get("ANTENNA_REDUCED_MOTION", "") not in ("", "0", "false")
_PULSE_MS = 18       # indeterminate cadence (~55fps): the "working" feel
_TWEEN_MS = 16       # ~60fps tween frames
_TWEEN_TOTAL = 260   # success fill duration (product 200-300ms state change)


class GenerateStep:
    def __init__(self, parent, session: DesignSession,
                 on_generate: Callable[[], None], on_stop: Callable[[], None]):
        self.session = session
        self.frame = ttk.Frame(parent)
        self._tween_job = None

        self.summary = StringVar(value="Pick a band first.")
        ttk.Label(self.frame, textvariable=self.summary, wraplength=330,
                  justify="left").pack(anchor="w", pady=(0, PAD_M))

        self.progress = DoubleVar(value=0.0)
        self.bar = ttk.Progressbar(self.frame, variable=self.progress, maximum=100,
                                   mode="determinate", bootstyle=PRIMARY)
        self.bar.pack(fill=X, pady=(0, PAD_M))

        btns = ttk.Frame(self.frame)
        btns.pack(fill=X)
        self.gen_btn = ttk.Button(btns, text="Generate Design", bootstyle=PRIMARY,
                                  command=on_generate)
        self.gen_btn.pack(side="left", expand=True, fill=X, padx=(0, PAD_S))
        self.stop_btn = ttk.Button(btns, text="Stop", bootstyle=DANGER,
                                   command=on_stop, state="disabled")
        self.stop_btn.pack(side="left")

        self.result = StringVar(value="")
        ttk.Label(self.frame, textvariable=self.result, wraplength=330,
                  justify="left").pack(anchor="w", pady=(PAD_M, 0))

        session.subscribe(self._refresh)
        self._refresh(EVT_BAND)

    def set_busy(self, busy: bool):
        self._cancel_tween()
        if busy:
            # Real work, unknown duration -> indeterminate motion, not a fake %.
            self.gen_btn.configure(state="disabled", text="Generating…")
            self.stop_btn.configure(state="normal")
            if REDUCED_MOTION:
                self.bar.configure(mode="determinate", bootstyle=PRIMARY)
                self.progress.set(40.0)
            else:
                self.bar.configure(mode="indeterminate", bootstyle="primary-striped")
                self.bar.start(_PULSE_MS)
        else:
            # Stop the working animation and reset to a neutral empty bar. The success
            # settle is driven from EVT_GENERATED (fires *after* this on the happy path);
            # a failed/cancelled run leaves the bar here at 0.
            self.bar.stop()
            self.gen_btn.configure(state="normal", text="Generate Design")
            self.stop_btn.configure(state="disabled")
            self.bar.configure(mode="determinate", bootstyle=PRIMARY)
            self.progress.set(0.0)

    # --- ease-out tween toward a target, on the UI thread ---
    def _tween_to(self, target: float):
        if REDUCED_MOTION:
            self.progress.set(target)
            return
        start = self.progress.get()
        steps = max(1, _TWEEN_TOTAL // _TWEEN_MS)

        def step(i: int = 1):
            t = i / steps
            eased = 1 - (1 - t) ** 3                     # ease-out-cubic, no bounce
            self.progress.set(start + (target - start) * eased)
            if i < steps:
                self._tween_job = self.frame.after(_TWEEN_MS, step, i + 1)
            else:
                self.progress.set(target)
                self._tween_job = None

        self._cancel_tween()
        step()

    def _cancel_tween(self):
        if self._tween_job is not None:
            try:
                self.frame.after_cancel(self._tween_job)
            except Exception:
                pass
            self._tween_job = None

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
        if event == EVT_GENERATED and self.session.results and self.session.has_design:
            r = self.session.results
            self.result.set(f"Design: {r.get('design_type', '?')}  "
                            f"({'OK' if r.get('success') else 'check warnings'})")
            # Design landed -> confident settle to a full SUCCESS bar.
            self.bar.configure(mode="determinate", bootstyle=SUCCESS)
            self._tween_to(100.0)
        elif event == EVT_GENERATED and not self.session.has_design:
            # Cleared (New) -> empty the bar and the result line.
            self._cancel_tween()
            self.result.set("")
            self.bar.configure(mode="determinate", bootstyle=PRIMARY)
            self.progress.set(0.0)
