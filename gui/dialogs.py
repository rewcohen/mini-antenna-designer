"""Helper tool dialogs ported from the legacy UI: Antenna Wizard and Tune.

Both adapt their result into the shared session (geometry/results/svg) and call
``on_apply(result_dict)`` so the host app can refresh canvas + properties.
"""
from __future__ import annotations

from typing import Callable
from tkinter import (Toplevel, Listbox, StringVar, END, WORD, LEFT, RIGHT, BOTH, X,
                     messagebox)
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as ttk
from ttkbootstrap.constants import PRIMARY, SECONDARY

from wizard import AntennaWizard

PAD = 10


class WizardDialog:
    """Guided service/mode -> design options -> spec, optionally load into designer."""

    def __init__(self, parent, session, on_apply: Callable[[dict], None]):
        self.session = session
        self.on_apply = on_apply
        try:
            self.wiz = AntennaWizard(substrate_width_in=session.substrate_width,
                                     substrate_height_in=session.substrate_height)
        except Exception:
            self.wiz = AntennaWizard()

        self.win = ttk.Toplevel(parent)
        self.win.title("Antenna Selection Wizard")
        self.win.geometry("760x620")
        self.win.transient(parent)

        self.services = self.wiz.list_services()
        self.modes = self.wiz.list_modes()
        self.svc_labels = [s["name"] for s in self.services]
        self.mode_labels = [m["label"] for m in self.modes]
        self._ctx = None
        self._spec = None

        top = ttk.Frame(self.win, padding=PAD)
        top.pack(fill=X)
        ttk.Label(top, text="1. What service is this antenna for?").grid(row=0, column=0, sticky="w")
        self.svc_var = StringVar(value=self.svc_labels[0])
        svc_cb = ttk.Combobox(top, textvariable=self.svc_var, values=self.svc_labels,
                              state="readonly", width=40)
        svc_cb.grid(row=0, column=1, sticky="w", padx=6, pady=3)
        ttk.Label(top, text="2. Transmit, receive, or both?").grid(row=1, column=0, sticky="w")
        self.mode_var = StringVar(value=self.mode_labels[-1])
        mode_cb = ttk.Combobox(top, textvariable=self.mode_var, values=self.mode_labels,
                               state="readonly", width=40)
        mode_cb.grid(row=1, column=1, sticky="w", padx=6, pady=3)
        self.info = ttk.Label(top, text="", bootstyle=SECONDARY, wraplength=720, justify="left")
        self.info.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        mid = ttk.Frame(self.win, padding=(PAD, 0))
        mid.pack(fill=BOTH, expand=True)
        ttk.Label(mid, text="3. Possible designs (select one):").pack(anchor="w")
        self.options = Listbox(mid, height=7)
        self.options.pack(fill=X, pady=3)
        self.spec_text = ScrolledText(mid, height=16, wrap=WORD)
        self.spec_text.pack(fill=BOTH, expand=True, pady=3)

        svc_cb.bind("<<ComboboxSelected>>", lambda _e: self._find())
        mode_cb.bind("<<ComboboxSelected>>", lambda _e: self._find())

        btns = ttk.Frame(self.win, padding=PAD)
        btns.pack(fill=X)
        ttk.Button(btns, text="Find Designs", command=self._find).pack(side=LEFT, padx=3)
        ttk.Button(btns, text="Build Spec", command=self._build).pack(side=LEFT, padx=3)
        ttk.Button(btns, text="Use Meander in Designer", bootstyle=PRIMARY,
                   command=self._use).pack(side=LEFT, padx=3)
        ttk.Button(btns, text="Close", bootstyle=SECONDARY,
                   command=self.win.destroy).pack(side=RIGHT, padx=3)
        self._find()

    def _svc_key(self):
        return self.services[self.svc_labels.index(self.svc_var.get())]["key"]

    def _mode_key(self):
        return self.modes[self.mode_labels.index(self.mode_var.get())]["key"]

    def _find(self):
        try:
            ctx = self.wiz.get_design_options(self._svc_key(), self._mode_key())
        except Exception as e:
            messagebox.showerror("Wizard", f"Could not load designs: {e}", parent=self.win)
            return
        self._ctx = ctx
        self.info.config(text=f"{ctx['service']['notes']}  |  "
                              f"{ctx['frequencies_mhz'][0]:.1f} MHz, "
                              f"wavelength {ctx['wavelength_in']} in")
        self.options.delete(0, END)
        for o in ctx["options"]:
            mark = "[OK]" if o["feasible"] else "[NO]"
            self.options.insert(END, f"{mark} {o['name']}  -  {o['summary']}")
        for i, o in enumerate(ctx["options"]):
            if o["feasible"]:
                self.options.selection_set(i)
                break

    def _build(self):
        if not self._ctx:
            self._find()
        sel = self.options.curselection()
        if not sel:
            messagebox.showinfo("Wizard", "Select a design option first.", parent=self.win)
            return
        try:
            spec = self.wiz.build_spec(self._svc_key(), self._mode_key(), sel[0])
        except Exception as e:
            messagebox.showerror("Wizard", f"Could not build spec: {e}", parent=self.win)
            return
        self.spec_text.delete("1.0", END)
        self.spec_text.insert(END, spec["spec_text"])
        self._spec = spec

    def _use(self):
        if not self._spec:
            self._build()
        if not self._spec or self._spec.get("kind") != "meander":
            messagebox.showinfo("Wizard", "Build a meander spec first to load it.", parent=self.win)
            return
        self.on_apply(self._spec.get("design", {}))
        messagebox.showinfo("Wizard", "Loaded into the designer.", parent=self.win)
        self.win.destroy()


class TuneDialog:
    """Adjust levers (incl. target gain) and preview expected results; apply to design."""

    def __init__(self, parent, session, on_apply: Callable[[dict], None]):
        from tune import evaluate_design
        self._evaluate = evaluate_design
        self.session = session
        self.on_apply = on_apply
        self._result = None

        res = session.results or {}
        freqs = session.frequencies_mhz()
        f_default = ",".join(f"{x:g}" for x in freqs) if freqs else "2442"

        self.win = ttk.Toplevel(parent)
        self.win.title("Tune Antenna Design")
        self.win.geometry("720x640")
        self.win.transient(parent)

        form = ttk.Frame(self.win, padding=PAD)
        form.pack(fill=X)
        self.vars = {
            "freqs": StringVar(value=f_default),
            "sw": StringVar(value=f"{session.substrate_width:g}"),
            "sh": StringVar(value=f"{session.substrate_height:g}"),
            "tw": StringVar(value=f"{session.trace_width_mil:g}"),
            "tg": StringVar(value=""),
        }
        labels = [("Frequencies (MHz, comma-sep)", "freqs"), ("Substrate width (in)", "sw"),
                  ("Substrate height (in)", "sh"), ("Trace width (mil)", "tw"),
                  ("Target gain (dBi, blank=none)", "tg")]
        for i, (lbl, key) in enumerate(labels):
            ttk.Label(form, text=lbl).grid(row=i, column=0, sticky="w", pady=2)
            ttk.Entry(form, textvariable=self.vars[key], width=28).grid(
                row=i, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Mode").grid(row=len(labels), column=0, sticky="w", pady=2)
        self.mode_var = StringVar(value=res.get("_mode", "both"))
        ttk.Combobox(form, textvariable=self.mode_var, values=["tx", "rx", "both"],
                     state="readonly", width=26).grid(row=len(labels), column=1, sticky="w", padx=6)

        self.out = ScrolledText(self.win, height=24, wrap=WORD)
        self.out.pack(fill=BOTH, expand=True, padx=PAD, pady=6)

        btns = ttk.Frame(self.win, padding=PAD)
        btns.pack(fill=X)
        ttk.Button(btns, text="Recalculate", command=self._recalc).pack(side=LEFT, padx=3)
        ttk.Button(btns, text="Apply to Current Design", bootstyle=PRIMARY,
                   command=self._apply).pack(side=LEFT, padx=3)
        ttk.Button(btns, text="Close", bootstyle=SECONDARY,
                   command=self.win.destroy).pack(side=RIGHT, padx=3)
        self._recalc()

    def _recalc(self):
        try:
            freqs = [float(x) for x in self.vars["freqs"].get().split(",") if x.strip()]
            sw = float(self.vars["sw"].get())
            sh = float(self.vars["sh"].get())
            tw = float(self.vars["tw"].get())
            tg_raw = self.vars["tg"].get().strip()
            tg = float(tg_raw) if tg_raw else None
        except ValueError:
            messagebox.showerror("Tune", "Check numeric fields.", parent=self.win)
            return
        r = self._evaluate(freqs, sw, sh, tw, self.mode_var.get(), target_gain_dbi=tg)
        self._result = r
        lines = [
            f"EXPECTED RESULTS  ({sw:g}x{sh:g} in, {tw:g} mil, {self.mode_var.get()})",
            "=" * 56,
            f"Best gain: {r['best_gain_dbi']} dBi   |   Lowest efficiency: {r['worst_efficiency_pct']}%",
            f"Pattern: {r['pattern']['type']} (max {r['pattern']['max_gain_dbi']} dBi "
            f"@ {r['pattern']['max_gain_dir_deg']} deg)",
            "", "Per band:",
        ]
        for b in r["bands"]:
            ok = "OK" if b["feasible"] else "NOT VIABLE"
            lines.append(f"  {b['label']} {b['freq_mhz']:.0f} MHz [{ok}]: "
                         f"gain {b['gain_dbi']:.1f} dBi, eff {b['efficiency_pct']:.0f}%, "
                         f"Z {b['impedance']}")
        if r.get("warnings"):
            lines += ["", "WARNINGS:"] + [f"  ! {w}" for w in r["warnings"]]
        if r.get("tips"):
            lines += ["", "TIPS:"] + [f"  - {t}" for t in r["tips"]]
        self.out.delete("1.0", END)
        self.out.insert(END, "\n".join(lines))

    def _apply(self):
        if not self._result:
            self._recalc()
        r = self._result
        if not r:
            return
        self.session.substrate_width, self.session.substrate_height = r["substrate_in"]
        design = dict(r["design"])
        design.setdefault("geometry", r["geometry"])
        self.on_apply(design)
        messagebox.showinfo("Tune", "Applied. Save it via the Export step.", parent=self.win)
        self.win.destroy()
