"""Step 4: generate the design (delegates the actual run to the app).

Motion here conveys *state*, not decoration (product register): while the backend
thread runs we show an honest indeterminate "working" bar — generation has no real
percentage to report — then settle to a full bar with an ease-out tween once a design
lands. Set ``ANTENNA_REDUCED_MOTION=1`` to drop the tweens and jump between states.
"""
from __future__ import annotations

import math
import os
from typing import Callable, Optional
from tkinter import X, StringVar, DoubleVar
import ttkbootstrap as ttk
from ttkbootstrap.constants import PRIMARY, DANGER, SUCCESS

from design import AdvancedMeanderTrace
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

    def _estimate_line(self, freqs) -> Optional[str]:
        """Per-band target trace-length estimate, mirroring legacy ui.py's preview.

        Returns a short feasibility line (target lengths in inches + a fit hint)
        or ``None`` if the inputs can't be turned into a sensible estimate. Any
        bad/missing input is swallowed: the caller just drops the extra line.
        """
        try:
            s = self.session
            meander = AdvancedMeanderTrace(s.substrate_width, s.substrate_height)
            meander.substrate_epsilon = s.substrate_epsilon
            meander.substrate_thickness = s.substrate_thickness_mm / 1000.0  # mm -> m
            trace_w_m = s.trace_width_mil / 39370.0                          # mil -> m

            lengths_in = []
            for freq in freqs:
                e_eff = meander.calculate_effective_permittivity(
                    s.substrate_epsilon, meander.substrate_thickness, trace_w_m)
                l_m = meander.calculate_target_length(
                    freq * 1e6, e_eff, s.coupling_factor)
                lengths_in.append(l_m * 39.3701)  # m -> in

            if not lengths_in or not all(math.isfinite(x) for x in lengths_in):
                return None

            total_in = sum(lengths_in)
            diag_in = math.hypot(s.substrate_width, s.substrate_height)
            line = ("Est. target length: "
                    + " / ".join(f"{x:.1f}" for x in lengths_in)
                    + f" in  (total {total_in:.1f} in, board diag {diag_in:.1f} in)")

            # Rough serpentine-capacity heuristic: usable trace per band before the
            # meander gets dense. Honest, not a hard limit.
            capacity_in = s.substrate_width * s.substrate_height * 8
            if max(lengths_in) > capacity_in:
                line += " — tight fit, expect dense meander"
            return line
        except Exception:
            return None

    def _refresh(self, event: str):
        freqs = self.session.frequencies_mhz()
        name = self.session.band.name if self.session.band else None
        if freqs and name:
            text = (f"{name}: {freqs[0]:g}/{freqs[1]:g}/{freqs[2]:g} MHz"
                    f" on {self.session.substrate_width:g}×"
                    f"{self.session.substrate_height:g} in, "
                    f"{self.session.trace_width_mil:.0f} mil traces.")
            est = self._estimate_line(freqs)
            if est:
                text += "\n" + est
            self.summary.set(text)
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
