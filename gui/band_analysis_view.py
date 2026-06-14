"""Pre-generation band feasibility dialog.

Opened from Step 1 (Band) before any antenna is generated. Summarizes the
result of ``BandAnalysis.analyze_band_compatibility`` plus
``BandAnalysis.suggest_alternatives`` in a readable, scrollable Toplevel.

Every dict access is guarded with ``.get(...)`` so a missing key from the
analysis backend never crashes the GUI.
"""
from __future__ import annotations

from tkinter import X, BOTH, LEFT, RIGHT, W
import ttkbootstrap as ttk
from ttkbootstrap.constants import PRIMARY, DANGER

from presets import BandPresets, BandAnalysis

from gui.constants import PAD_S, PAD_M


class BandAnalysisDialog:
    """Read-only feasibility report for a selected band + substrate size."""

    def __init__(self, parent, band, substrate_width: float = 4.0,
                 substrate_height: float = 2.0):
        self.band = band

        # Run the analysis defensively -- a backend error should still show a
        # usable dialog rather than propagate.
        try:
            analysis = BandAnalysis.analyze_band_compatibility(
                band, substrate_width, substrate_height)
        except Exception as exc:  # pragma: no cover - defensive
            analysis = {"warnings": [f"Analysis failed: {exc}"]}
        if not isinstance(analysis, dict):
            analysis = {}

        try:
            alternatives = BandAnalysis.suggest_alternatives(band) or []
        except Exception:  # pragma: no cover - defensive
            alternatives = []

        all_bands = BandPresets.get_all_bands()

        self.win = ttk.Toplevel(parent)
        self.win.title("Band Analysis")
        self.win.geometry("520x600")
        self.win.transient(parent)

        body = ttk.Frame(self.win, padding=PAD_M)
        body.pack(fill=BOTH, expand=True)

        # --- Band header -------------------------------------------------
        name = getattr(band, "name", "Unknown band")
        ttk.Label(body, text=name, font=("", 13, "bold")).pack(anchor=W)
        freqs = getattr(band, "frequencies", None) or ()
        if freqs:
            freq_text = " / ".join(f"{f:g}" for f in freqs) + " MHz"
            ttk.Label(body, text=freq_text, bootstyle="secondary").pack(
                anchor=W, pady=(0, PAD_S))
        desc = getattr(band, "description", "")
        if desc:
            ttk.Label(body, text=desc, wraplength=480, justify="left",
                      bootstyle="secondary").pack(anchor=W, pady=(0, PAD_S))

        ttk.Separator(body).pack(fill=X, pady=PAD_S)

        # --- Feasibility score ------------------------------------------
        score = analysis.get("feasibility_score")
        if score is not None:
            style = PRIMARY if score >= 7 else (
                "warning" if score >= 5 else DANGER)
            ttk.Label(body, text=f"Feasibility: {score:.1f} / 10",
                      font=("", 12, "bold"), bootstyle=style).pack(anchor=W)

        # --- Quick characteristics --------------------------------------
        for label, key in (("Design complexity", "design_complexity"),
                           ("Size constraints", "size_constraints"),
                           ("Expected performance", "expected_performance")):
            val = analysis.get(key)
            if val:
                ttk.Label(body, text=f"{label}: {val}").pack(
                    anchor=W, pady=(PAD_S, 0))

        # --- Recommended antenna types ----------------------------------
        rec = analysis.get("recommended_antenna_types") or []
        if rec:
            ttk.Label(body, text="Recommended antenna types:",
                      font=("", 10, "bold")).pack(anchor=W, pady=(PAD_M, 0))
            ttk.Label(body, text=", ".join(str(r) for r in rec),
                      wraplength=480, justify="left").pack(anchor=W)

        # --- Optimization notes -----------------------------------------
        self._bullet_section(body, "Optimization notes:",
                             analysis.get("optimization_notes"))

        # --- Warnings ---------------------------------------------------
        self._bullet_section(body, "Warnings:", analysis.get("warnings"),
                             bootstyle=DANGER)

        # --- Suggested alternatives -------------------------------------
        if alternatives:
            ttk.Label(body, text="Suggested alternatives:",
                      font=("", 10, "bold")).pack(anchor=W, pady=(PAD_M, 0))
            for item in alternatives:
                try:
                    alt_key, reason = item
                except (TypeError, ValueError):
                    alt_key, reason = str(item), ""
                alt_band = all_bands.get(alt_key)
                alt_name = getattr(alt_band, "name", alt_key)
                text = f"- {alt_name}"
                if reason:
                    text += f": {reason}"
                ttk.Label(body, text=text, wraplength=480,
                          justify="left").pack(anchor=W)

        # --- Footer -----------------------------------------------------
        btns = ttk.Frame(self.win, padding=PAD_M)
        btns.pack(fill=X)
        ttk.Button(btns, text="Close", bootstyle=PRIMARY,
                   command=self.win.destroy).pack(side=RIGHT)

        self.win.bind("<Escape>", lambda _e: self.win.destroy())
        self.win.focus_set()

    def _bullet_section(self, parent, title, items, bootstyle=None):
        """Render a bold title followed by a bulleted list, if non-empty."""
        items = items or []
        if not items:
            return
        ttk.Label(parent, text=title, font=("", 10, "bold")).pack(
            anchor=W, pady=(PAD_M, 0))
        for note in items:
            kw = {"bootstyle": bootstyle} if bootstyle else {}
            ttk.Label(parent, text=f"- {note}", wraplength=480,
                      justify="left", **kw).pack(anchor=W)
