"""Step 2: substrate size and material."""
from __future__ import annotations

from tkinter import X, StringVar
import ttkbootstrap as ttk

from gui.session import DesignSession, EVT_INPUTS

from gui.constants import PAD_S, PAD_M

# name -> (epsilon_r, thickness_mm)
_MATERIALS = {
    "FR-4 (εr 4.3)": (4.3, 1.6),
    "Rogers RO4350B (εr 3.48)": (3.48, 1.524),
    "Rogers RO4003C (εr 3.38)": (3.38, 1.524),
    "PTFE/Teflon (εr 2.1)": (2.1, 1.6),
    "Rogers TMM10 (εr 10.2)": (10.2, 1.27),
    "Alumina (εr 9.8)": (9.8, 1.0),
}


class BoardStep:
    def __init__(self, parent, session: DesignSession):
        self.session = session
        self.frame = ttk.Frame(parent)

        size = ttk.LabelFrame(self.frame, text="Substrate Size (inches)", padding=PAD_M)
        size.pack(fill=X, pady=(0, PAD_M))
        self.w = StringVar(value=f"{session.substrate_width:g}")
        self.h = StringVar(value=f"{session.substrate_height:g}")
        ttk.Label(size, text="Width").grid(row=0, column=0, sticky="w")
        ttk.Entry(size, textvariable=self.w, width=8).grid(row=0, column=1, padx=PAD_S)
        ttk.Label(size, text="Height").grid(row=0, column=2, sticky="w", padx=(PAD_M, 0))
        ttk.Entry(size, textvariable=self.h, width=8).grid(row=0, column=3, padx=PAD_S)
        for var in (self.w, self.h):
            var.trace_add("write", self._on_size)

        mat = ttk.LabelFrame(self.frame, text="Material", padding=PAD_M)
        mat.pack(fill=X)
        self._sync = False
        self.material = StringVar(value=next(iter(_MATERIALS)))
        cb = ttk.Combobox(mat, textvariable=self.material, state="readonly",
                          values=list(_MATERIALS), width=28)
        cb.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, PAD_S))
        cb.bind("<<ComboboxSelected>>", self._on_material)
        ttk.Label(mat, text="Thickness (mm)").grid(row=1, column=0, sticky="w")
        self.thickness = StringVar(value=f"{session.substrate_thickness_mm:g}")
        ttk.Entry(mat, textvariable=self.thickness, width=8).grid(
            row=1, column=1, sticky="w", padx=PAD_S)
        self.thickness.trace_add("write", self._on_thickness)
        self.info = ttk.Label(mat, text="")
        self.info.grid(row=2, column=0, columnspan=2, sticky="w", pady=(PAD_S, 0))
        self._on_material()

    def _on_size(self, *_):
        try:
            self.session.substrate_width = max(1.0, min(12.0, float(self.w.get())))
            self.session.substrate_height = max(1.0, min(12.0, float(self.h.get())))
        except ValueError:
            return
        self.session.notify(EVT_INPUTS)

    def _on_material(self, *_):
        eps, thick = _MATERIALS[self.material.get()]
        self.session.substrate_epsilon = eps
        self.session.substrate_thickness_mm = thick
        self._sync = True
        try:
            self.thickness.set(f"{thick:g}")
        finally:
            self._sync = False
        self.info.configure(text=f"εr = {eps}, thickness = {thick} mm")
        self.session.notify(EVT_INPUTS)

    def _on_thickness(self, *_):
        if self._sync:
            return
        try:
            thick = max(0.1, min(6.0, float(self.thickness.get())))
        except ValueError:
            return
        self.session.substrate_thickness_mm = thick
        eps = self.session.substrate_epsilon
        self.info.configure(text=f"εr = {eps}, thickness = {thick} mm")
        self.session.notify(EVT_INPUTS)
