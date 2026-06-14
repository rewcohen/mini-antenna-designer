"""Right panel: live metrics, warnings, feed advice, radiation pattern."""
from __future__ import annotations

from tkinter import X, BOTH, StringVar
import ttkbootstrap as ttk
from ttkbootstrap.constants import SECONDARY, SUCCESS, WARNING, DANGER

from gui.session import DesignSession, EVT_GENERATED
from gui.scrollframe import ScrollFrame

PAD_S, PAD_M = 4, 8


def _vswr_level(vswr: float) -> str:
    if vswr <= 2.0:
        return SUCCESS
    if vswr <= 3.0:
        return WARNING
    return DANGER


class PropertiesPanel:
    def __init__(self, parent, session: DesignSession):
        self.session = session
        scroll = ScrollFrame(parent)
        self.frame = scroll.outer
        self.body = scroll.body

        head = ttk.Frame(self.body)
        head.pack(fill=X)
        ttk.Label(head, text="Performance", font=("", 10, "bold")).pack(side="left")
        ttk.Button(head, text="Analysis…", bootstyle=SECONDARY,
                   command=self._open_analysis).pack(side="right")
        self.chips = ttk.Frame(self.body)
        self.chips.pack(fill=X, pady=(PAD_S, PAD_M))

        self.summary = StringVar(value="No design yet.")
        ttk.Label(self.body, textvariable=self.summary, wraplength=250,
                  bootstyle=SECONDARY, justify="left").pack(anchor="w")

        ttk.Label(self.body, text="Warnings", font=("", 10, "bold")).pack(
            anchor="w", pady=(PAD_M, PAD_S))
        self.warn = StringVar(value="—")
        ttk.Label(self.body, textvariable=self.warn, wraplength=250,
                  bootstyle=WARNING, justify="left").pack(anchor="w")

        ttk.Label(self.body, text="Feed & Pattern", font=("", 10, "bold")).pack(
            anchor="w", pady=(PAD_M, PAD_S))
        self.feed = StringVar(value="—")
        ttk.Label(self.body, textvariable=self.feed, wraplength=250,
                  bootstyle=SECONDARY, justify="left").pack(anchor="w")

        session.subscribe(self._refresh)

    def _open_analysis(self):
        if not self.session.has_design:
            return
        from gui.analysis_view import AnalysisDialog
        AnalysisDialog(self.body.winfo_toplevel(), self.session)

    def _refresh(self, event: str):
        if event != EVT_GENERATED or not self.session.results:
            return
        r = self.session.results
        for w in self.chips.winfo_children():
            w.destroy()

        metrics = r.get("metrics", {})
        for key, m in metrics.items():
            if key == "summary" or not isinstance(m, dict):
                continue
            vswr = m.get("vswr")
            if vswr is None:
                continue
            f = key.replace("freq_", "").replace("_mhz", "")
            chip = ttk.Label(self.chips, text=f"{f} MHz  VSWR {vswr:.2f}",
                             bootstyle=f"{_vswr_level(vswr)} inverse")
            chip.pack(anchor="w", pady=1)

        summ = metrics.get("summary", {})
        self.summary.set(f"Avg VSWR: {summ.get('avg_vswr', '—')}\n"
                         f"Avg gain: {summ.get('avg_gain_dbi', '—')} dBi\n"
                         f"Type: {r.get('design_type', '—')}")

        warnings = (r.get("validation", {}) or {}).get("warnings", [])
        self.warn.set("\n".join(f"• {w}" for w in warnings) if warnings else "None")

        lines = []
        pat = r.get("radiation_pattern") or {}
        if pat:
            lines.append(f"Pattern: {pat.get('pattern_type', '—')}, "
                         f"max {pat.get('max_gain_dbi', 0):.1f} dBi")
        for fa in (r.get("feed_advice") or []):
            bal = "balun" if fa.get("balun_required") else "no balun"
            lines.append(f"{fa.get('label', '?')}: {fa.get('feed_impedance_str', '?')} ({bal})")
        self.feed.set("\n".join(lines) if lines else "—")
