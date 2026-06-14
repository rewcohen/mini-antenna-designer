"""Step 3: trace width + advanced meander options."""
from __future__ import annotations

from tkinter import X, BooleanVar
import ttkbootstrap as ttk
from ttkbootstrap.constants import SECONDARY, ROUND

from gui.session import DesignSession, EVT_INPUTS

PAD_S, PAD_M = 4, 8


def _trace_quality(mil: float) -> str:
    if mil < 5:
        return "Invalid (<5 mil)"
    if mil < 8:
        return "Tight"
    if mil <= 50:
        return "Good"
    return "Wide"


class TraceStep:
    def __init__(self, parent, session: DesignSession):
        self.session = session
        self.frame = ttk.Frame(parent)

        tw = ttk.LabelFrame(self.frame, text="Trace Width (mil)", padding=PAD_M)
        tw.pack(fill=X, pady=(0, PAD_M))
        self.trace_label = ttk.Label(tw, text="")
        self.trace_label.pack(anchor="w")
        self.trace_scale = ttk.Scale(tw, from_=5, to=100, value=session.trace_width_mil,
                                     command=self._on_trace)
        self.trace_scale.pack(fill=X)

        adv = ttk.LabelFrame(self.frame, text="Advanced", padding=PAD_M)
        adv.pack(fill=X)
        self.coupling = self._slider(adv, "Coupling factor", 0.80, 0.98,
                                     session.coupling_factor, "coupling_factor")
        self.bend = self._slider(adv, "Bend radius (mm)", 0.5, 3.0,
                                 session.bend_radius_mm, "bend_radius_mm")
        self.density = self._slider(adv, "Meander density", 0.5, 2.0,
                                    session.meander_density, "meander_density")
        self.pads = BooleanVar(value=session.add_contact_pads)
        ttk.Checkbutton(adv, text="Add contact pads for soldering", variable=self.pads,
                        bootstyle="round-toggle", command=self._on_pads).pack(
            anchor="w", pady=(PAD_S, 0))

        self._update_trace_label()

    def _slider(self, parent, label, lo, hi, value, attr):
        row = ttk.Frame(parent)
        row.pack(fill=X, pady=(PAD_S, 0))
        lab = ttk.Label(row, text=f"{label}: {value:g}", bootstyle=SECONDARY)
        lab.pack(anchor="w")
        s = ttk.Scale(row, from_=lo, to=hi, value=value,
                      command=lambda v, a=attr, l=lab, t=label: self._on_slider(a, l, t, v))
        s.pack(fill=X)
        return s

    def _on_slider(self, attr, label, title, v):
        val = round(float(v), 3)
        setattr(self.session, attr, val)
        label.configure(text=f"{title}: {val:g}")
        self.session.notify(EVT_INPUTS)

    def _on_trace(self, v):
        self.session.trace_width_mil = round(float(v), 1)
        self._update_trace_label()
        self.session.notify(EVT_INPUTS)

    def _update_trace_label(self):
        mil = self.session.trace_width_mil
        self.trace_label.configure(text=f"{mil:.1f} mil — {_trace_quality(mil)}")

    def _on_pads(self):
        self.session.add_contact_pads = self.pads.get()
        self.session.notify(EVT_INPUTS)
