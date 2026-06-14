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
        self.material = StringVar(value=next(iter(_MATERIALS)))
        cb = ttk.Combobox(mat, textvariable=self.material, state="readonly",
                          values=list(_MATERIALS), width=28)
        cb.pack(fill=X)
        cb.bind("<<ComboboxSelected>>", self._on_material)
        self.info = ttk.Label(mat, text="")
        self.info.pack(anchor="w", pady=(PAD_S, 0))
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
        self.info.configure(text=f"εr = {eps}, thickness = {thick} mm")
        self.session.notify(EVT_INPUTS)
