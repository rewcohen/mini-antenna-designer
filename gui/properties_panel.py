"""Right panel: live metrics, warnings, feed advice, radiation pattern."""
from __future__ import annotations

from tkinter import X, BOTH, StringVar
import ttkbootstrap as ttk
from ttkbootstrap.constants import SECONDARY, SUCCESS, WARNING, DANGER

from gui.session import DesignSession, EVT_GENERATED
from gui.scrollframe import ScrollFrame

from gui.constants import PAD_S, PAD_M


def _fmt_vswr(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return str(v)
    return ">10" if x >= 10 else f"{x:.2f}"


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
        ttk.Button(head, text="Analysis…", bootstyle="secondary-outline",
                   command=self._open_analysis).pack(side="right")
        self.chips = ttk.Frame(self.body)
        self.chips.pack(fill=X, pady=(PAD_S, PAD_M))

        self.summary = StringVar(value="No design yet.")
        ttk.Label(self.body, textvariable=self.summary, wraplength=250,
                  justify="left").pack(anchor="w")

        ttk.Label(self.body, text="Warnings", font=("", 10, "bold")).pack(
            anchor="w", pady=(PAD_M, PAD_S))
        self.warn = StringVar(value="—")
        ttk.Label(self.body, textvariable=self.warn, wraplength=250,
                  bootstyle=WARNING, justify="left").pack(anchor="w")

        ttk.Label(self.body, text="Feed & Pattern", font=("", 10, "bold")).pack(
            anchor="w", pady=(PAD_M, PAD_S))
        self.feed = StringVar(value="—")
        ttk.Label(self.body, textvariable=self.feed, wraplength=250,
                  justify="left").pack(anchor="w")

        ttk.Label(self.body, text="Recommendations", font=("", 10, "bold")).pack(
            anchor="w", pady=(PAD_M, PAD_S))
        self.recommend = StringVar(value="—")
        ttk.Label(self.body, textvariable=self.recommend, wraplength=250,
                  justify="left").pack(anchor="w")

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
            try:
                vnum = float(vswr)
                vtext, level = _fmt_vswr(vnum), _vswr_level(vnum)
            except (TypeError, ValueError):
                vtext, level = str(vswr), SECONDARY  # tuned designs may give "~2.5"
            chip = ttk.Label(self.chips, text=f"{f} MHz  VSWR {vtext}",
                             bootstyle=f"{level} inverse")
            chip.pack(anchor="w", pady=1)

        summ = metrics.get("summary", {})
        avg_gain_raw = summ.get("avg_gain_dbi", "—")
        try:
            gain_num = float(avg_gain_raw)
            gain_text = f"{gain_num:.1f} dBi"
        except (TypeError, ValueError):
            gain_num = None
            gain_text = f"{avg_gain_raw} dBi" if avg_gain_raw not in (None, "—") else "—"
        lines = [
            f"Avg VSWR: {_fmt_vswr(summ.get('avg_vswr', '—'))}",
            f"Avg gain: {gain_text}",
            f"Type: {r.get('design_type', '—')}",
        ]
        if gain_num is not None and gain_num < -5:
            lines.append("Very low gain — this design barely radiates.")
        self.summary.set("\n".join(lines))

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

        self.recommend.set(self._recommendations_text(r))

    @staticmethod
    def _recommendations_text(r: dict) -> str:
        """Summarize copper-wire alternatives for bands where the meander is unusable.

        ``feasibility`` is a per-band list (see assess_meander_feasibility); each
        infeasible band carries a ``reason`` plus an ``alternatives`` list. Anything
        viable / missing yields a calm default so the panel never dumps raw dicts.
        """
        feasibility = r.get("feasibility")
        if not isinstance(feasibility, list):
            return "—"

        lines = []
        for band in feasibility:
            if not isinstance(band, dict) or band.get("feasible", True):
                continue
            label = band.get("label") or "?"
            freq = band.get("freq_mhz")
            head = f"{label} {freq:.0f} MHz" if isinstance(freq, (int, float)) else str(label)
            reason = band.get("reason")
            lines.append(f"{head}: not viable on this board.")
            if reason:
                lines.append(f"  {reason}")
            alts = band.get("alternatives")
            if isinstance(alts, list) and alts:
                lines.append("  Build instead:")
                for alt in alts:
                    if not isinstance(alt, dict):
                        continue
                    name = alt.get("name") or "alternative"
                    detail = alt.get("feed_impedance") or alt.get("balun") or alt.get("notes")
                    lines.append(f"  • {name} ({detail})" if detail else f"  • {name}")

        return "\n".join(lines) if lines else "All bands radiate from the board — no wire build needed."
