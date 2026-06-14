"""Step 3: trace width + advanced meander options."""
from __future__ import annotations

from tkinter import X, BooleanVar, StringVar
import ttkbootstrap as ttk
from ttkbootstrap.constants import ROUND

from gui.session import DesignSession, EVT_INPUTS

from gui.constants import PAD_S, PAD_M


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
        # Guard so slider <-> entry programmatic updates don't ping-pong.
        self._syncing = False

        tw = ttk.LabelFrame(self.frame, text="Trace Width (mil)", padding=PAD_M)
        tw.pack(fill=X, pady=(0, PAD_M))
        row = ttk.Frame(tw)
        row.pack(fill=X)
        self.trace_label = ttk.Label(row, text="")
        self.trace_label.pack(side="left", anchor="w")
        self.trace_var = StringVar(value=f"{session.trace_width_mil:.1f}")
        self.trace_entry = ttk.Entry(row, textvariable=self.trace_var, width=6)
        self.trace_entry.pack(side="right")
        self.trace_entry.bind("<Return>", self._on_trace_entry)
        self.trace_entry.bind("<FocusOut>", self._on_trace_entry)
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
        self.pad_info = ttk.Label(adv, text="")
        self.pad_info.pack(anchor="w", pady=(PAD_S, 0))

        self._update_trace_label()
        self._update_pad_info()

    def _slider(self, parent, label, lo, hi, value, attr):
        row = ttk.Frame(parent)
        row.pack(fill=X, pady=(PAD_S, 0))
        lab = ttk.Label(row, text=f"{label}: {value:g}")
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
        mil = round(float(v), 1)
        self.session.trace_width_mil = mil
        if not self._syncing:
            self._syncing = True
            try:
                self.trace_var.set(f"{mil:.1f}")
            finally:
                self._syncing = False
        self._update_trace_label()
        self._update_pad_info()
        self.session.notify(EVT_INPUTS)

    def _on_trace_entry(self, _event=None):
        # Ignore programmatic var updates triggered from _on_trace.
        if self._syncing:
            return
        try:
            mil = round(float(self.trace_var.get()), 1)
        except (TypeError, ValueError):
            # Invalid input: revert entry text to the current session value.
            self.trace_var.set(f"{self.session.trace_width_mil:.1f}")
            return
        mil = max(5.0, min(100.0, mil))
        self.session.trace_width_mil = mil
        self._syncing = True
        try:
            self.trace_scale.set(mil)
            self.trace_var.set(f"{mil:.1f}")
        finally:
            self._syncing = False
        self._update_trace_label()
        self._update_pad_info()
        self.session.notify(EVT_INPUTS)

    def _update_trace_label(self):
        mil = self.session.trace_width_mil
        self.trace_label.configure(text=f"{mil:.1f} mil — {_trace_quality(mil)}")

    def _on_pads(self):
        self.session.add_contact_pads = self.pads.get()
        self._update_pad_info()
        self.session.notify(EVT_INPUTS)

    def _update_pad_info(self):
        try:
            if self.pads.get():
                text = (f"Contact pads: 2× trace width "
                        f"(≈ {self.session.trace_width_mil * 2:.0f} mil)")
            else:
                text = "Contact pads: off"
        except (TypeError, ValueError):
            text = "Contact pads: —"
        self.pad_info.configure(text=text)
